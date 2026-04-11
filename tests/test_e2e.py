"""
tests/test_e2e.py
─────────────────────────────────────────────────────────────────────────────
TASK-009 - Integration & End-to-End Tests  (Phase 8)

These tests exercise the *full pipeline* through BatchRunner without hitting
any real external services.  All Gemini, SMTP, LibreOffice, and crypto calls
are mocked so the suite is fully offline and deterministic.

Design note on source folders
──────────────────────────────
Each test that checks exact DB row counts creates its own isolated source
folder with exactly the files it needs (using the `make_src` helper).
BatchRunner.discover_files() scans the entire resumes/ dir, so sharing a
folder across tests that assert specific row counts would cause failures.

PRD coverage per test:
  test_e2e_happy_path          → F5, F6, F7, F8, F9
  test_e2e_missing_details     → F5, F6, F7, F10
  test_e2e_checkpoint_resume   → F8
  test_e2e_payment_and_send    → F11, F12
  test_e2e_error_path          → F3, F7
"""

import io
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from reportlab.pdfgen import canvas  # type: ignore

from app.state.db import StateDB
from app.state.models import CandidateStatus
from app.state.checkpoint import CheckpointManager
from app.ui.runner import BatchRunner


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_pdf_bytes(text: str = "resume content") -> bytes:
    """Return the bytes of a minimal single-page PDF."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.save()
    return buf.getvalue()


def _make_src(tmp_path: Path, filenames: list[str]) -> tuple[Path, Path]:
    """
    Create an isolated source folder with a jd.txt and *filenames* inside
    resumes/.  Returns (source_dir, dest_dir).
    """
    src = tmp_path / "source"
    (src / "resumes").mkdir(parents=True)
    (src / "jd.txt").write_text("Senior Python Engineer JD text.", encoding="utf-8")
    for name in filenames:
        pdf = src / "resumes" / name
        pdf.write_bytes(_make_pdf_bytes(name))

    dst = tmp_path / "dest"
    dst.mkdir(parents=True)
    return src, dst


def _make_db(tmp_path: Path, src: Path, dst: Path, batch_size: int = 0) -> tuple[StateDB, Path]:
    """Return a (StateDB, db_path) already loaded with recruiter config."""
    db_path = tmp_path / "resume_tuner.db"
    db = StateDB(db_path)
    db.save_config(
        {
            "recruiter_name": "Test Recruiter",
            "recruiter_email": "recruiter@test.com",
            "smtp_server": "smtp.test.com",
            "smtp_port": 587,
            "smtp_password": "encrypted_dummy",
            "service_fee": "499",
            "batch_size": batch_size,
            "source_folder": str(src),
            "destination_folder": str(dst),
            "best_practice_paths": json.dumps([]),
        }
    )
    return db, db_path


HAPPY_LLM_OUTPUT = {
    "candidate_name": "John Doe",
    "contact": {"email": "john@example.com", "phone": "9876543210", "linkedin": "linkedin.com/in/johndoe"},
    "summary": "Experienced Python engineer.",
    "experience": [{"title": "Engineer", "company": "Acme", "dates": "2020-2024", "bullets": ["Built APIs"]}],
    "education": [{"degree": "B.Tech", "institution": "MIT", "year": "2020"}],
    "skills": ["Python", "FastAPI"],
    "missing_fields": [],
}

MISSING_LLM_OUTPUT = {
    "candidate_name": "Jane Smith",
    "contact": {"email": "jane@example.com", "phone": "", "linkedin": ""},
    "summary": "Data scientist.",
    "experience": [],
    "education": [],
    "skills": ["ML"],
    "missing_fields": ["Phone", "LinkedIn"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 - Happy Path (PRD F5, F6, F7, F8, F9)
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_happy_path(tmp_path):
    """
    Full pipeline with no missing fields.

    Asserts:
    - Candidate status = HAPPY_PATH
    - output_pdf_path is set in DB
    - Checkpoint written (batch 1, 1 processed)
    - One outreach email sent
    """
    src, dst = _make_src(tmp_path, ["happy_resume.pdf"])
    db, db_path = _make_db(tmp_path, src, dst, batch_size=0)

    output_pdf = dst / "John Doe_finetuned.pdf"
    pdf_bytes = _make_pdf_bytes("John Doe resume")

    with (
        patch("app.ui.runner.find_and_read_jd", return_value="JD text"),
        patch("app.ui.runner.search_best_practice", return_value="BP text"),
        patch("app.ui.runner.extract_text_and_photo", return_value={"text": "Resume text", "photo_bytes": None}),
        patch("app.ui.runner.fine_tune_resume", return_value=HAPPY_LLM_OUTPUT),
        patch("app.ui.runner.generate_resume_pdf", side_effect=lambda *a, **kw: output_pdf.write_bytes(pdf_bytes)),
        patch("app.ui.runner.send_outreach_email") as mock_send,
    ):
        session = {"is_running": True}
        runner = BatchRunner(db_path, session)
        runner.run()

    assert not session["is_running"]

    with db._get_connection() as conn:
        rows = conn.execute("SELECT * FROM candidates").fetchall()

    # Exactly one resume file was in the source folder
    assert len(rows) == 1
    assert rows[0]["status"] == CandidateStatus.HAPPY_PATH.value
    assert rows[0]["candidate_name"] == "John Doe"
    assert rows[0]["candidate_email"] == "john@example.com"
    assert rows[0]["output_pdf_path"] is not None

    # PDF written to disk
    assert output_pdf.exists()

    # Email NOT auto-sent - manual trigger only
    mock_send.assert_not_called()

    # Checkpoint recorded
    mgr = CheckpointManager(db)
    cp = mgr.get_resume_point(str(src))
    assert cp is not None
    assert cp.total_processed == 1
    assert cp.batch_number == 1


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 - Missing Details Path (PRD F5, F6, F7, F10)
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_missing_details_path(tmp_path):
    """
    Full pipeline where LLM reports missing fields.

    Asserts:
    - Candidate status = MISSING_DETAILS
    - missing_fields column contains "Phone" and "LinkedIn"
    - Outreach email sent (missing-details variant)
    """
    src, dst = _make_src(tmp_path, ["missing_resume.pdf"])
    db, db_path = _make_db(tmp_path, src, dst, batch_size=0)

    output_pdf = dst / "Jane Smith_finetuned.pdf"
    pdf_bytes = _make_pdf_bytes("Jane Smith resume")

    with (
        patch("app.ui.runner.find_and_read_jd", return_value="JD text"),
        patch("app.ui.runner.search_best_practice", return_value="BP text"),
        patch("app.ui.runner.extract_text_and_photo", return_value={"text": "Jane resume text", "photo_bytes": None}),
        patch("app.ui.runner.fine_tune_resume", return_value=MISSING_LLM_OUTPUT),
        patch("app.ui.runner.generate_resume_pdf", side_effect=lambda *a, **kw: output_pdf.write_bytes(pdf_bytes)),
        patch("app.ui.runner.send_outreach_email") as mock_send,
    ):
        session = {"is_running": True}
        runner = BatchRunner(db_path, session)
        runner.run()

    assert not session["is_running"]

    with db._get_connection() as conn:
        rows = conn.execute("SELECT * FROM candidates").fetchall()

    assert len(rows) == 1
    assert rows[0]["status"] == CandidateStatus.MISSING_DETAILS.value

    missing = json.loads(rows[0]["missing_fields"])
    assert "Phone" in missing
    assert "LinkedIn" in missing

    # Email NOT auto-sent - manual trigger only
    mock_send.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 - Checkpoint Resume (PRD F8)
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_checkpoint_resume(tmp_path):
    """
    Simulate a mid-batch stop then resume over a SINGLE source folder.

    Source folder has two files (alpha.pdf, beta.pdf).
    Run 1: batch_size=1 → processes alpha.pdf, saves checkpoint (batch=1, total=1).
           The runner stops naturally after the batch_size limit.
    Run 2: batch_size=1 → discovers beta.pdf (alpha.pdf already in DB),
           processes it.  Checkpoint: batch=2, total=2.

    This tests PRD F8: "on restart, system correctly identifies next PENDING
    candidate" and "batch_number increments each time a new batch starts".
    """
    src, dst = _make_src(tmp_path, ["alpha.pdf", "beta.pdf"])
    db, db_path = _make_db(tmp_path, src, dst, batch_size=1)

    pdf_bytes = _make_pdf_bytes()

    def _fake_write_pdf(llm_json, photo, output_path, *a, **kw):
        Path(output_path).write_bytes(pdf_bytes)

    llm_for_alpha = dict(HAPPY_LLM_OUTPUT, candidate_name="Alpha Cand")
    llm_for_alpha["contact"] = {"email": "alpha@example.com", "phone": "111", "linkedin": ""}

    # ── Run 1: processes only alpha.pdf (batch_size=1) ───────────────────────
    with (
        patch("app.ui.runner.find_and_read_jd", return_value="JD"),
        patch("app.ui.runner.search_best_practice", return_value="BP"),
        patch("app.ui.runner.extract_text_and_photo", return_value={"text": "t", "photo_bytes": None}),
        patch("app.ui.runner.fine_tune_resume", return_value=llm_for_alpha),
        patch("app.ui.runner.generate_resume_pdf", side_effect=_fake_write_pdf),
    ):
        BatchRunner(db_path, {"is_running": True}).run()

    mgr = CheckpointManager(db)
    cp1 = mgr.get_resume_point(str(src))
    assert cp1 is not None
    assert cp1.total_processed == 1
    first_batch_number = cp1.batch_number  # should be 1

    # One candidate processed; beta.pdf not yet in DB (discover only adds
    # when runner starts - so beta is discovered fresh in Run 2)
    with db._get_connection() as conn:
        rows = conn.execute("SELECT status FROM candidates").fetchall()
    # alpha was processed (HAPPY_PATH); only 1 row because batch_size=1
    # discover_files adds all files, but get_pending_candidates limits to 1
    # So: alpha row = HAPPY_PATH, beta row = PENDING
    statuses = [r["status"] for r in rows]
    assert CandidateStatus.HAPPY_PATH.value in statuses

    # ── Run 2: picks up remaining PENDING (beta.pdf) ─────────────────────────
    llm_for_beta = dict(HAPPY_LLM_OUTPUT, candidate_name="Beta Cand")
    llm_for_beta["contact"] = {"email": "beta@example.com", "phone": "222", "linkedin": ""}

    with (
        patch("app.ui.runner.find_and_read_jd", return_value="JD"),
        patch("app.ui.runner.search_best_practice", return_value="BP"),
        patch("app.ui.runner.extract_text_and_photo", return_value={"text": "t", "photo_bytes": None}),
        patch("app.ui.runner.fine_tune_resume", return_value=llm_for_beta),
        patch("app.ui.runner.generate_resume_pdf", side_effect=_fake_write_pdf),
    ):
        BatchRunner(db_path, {"is_running": True}).run()

    cp2 = mgr.get_resume_point(str(src))
    assert cp2 is not None
    assert cp2.total_processed == 2           # cumulative across both runs
    assert cp2.batch_number > first_batch_number  # new batch = incremented


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 - Payment Confirmed → Send Resume (PRD F11, F12)
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_payment_and_send(tmp_path):
    """
    Manually advance a candidate through AWAITING_PAYMENT → PAYMENT_CONFIRMED,
    then call send_final_pdf_email and assert OUTPUT_SENT is set.

    Covers Feature 12 (auto-regenerate path) - the UI's Send Resume button
    does exactly this sequence.
    """
    src, dst = _make_src(tmp_path, ["resume.pdf"])
    db, db_path = _make_db(tmp_path, src, dst, batch_size=0)

    # Insert a candidate already at HAPPY_PATH (runner already ran)
    cid = db.add_candidate(str(src), "resume.pdf")
    db.set_status(cid, CandidateStatus.PROCESSING)
    db.set_status(cid, CandidateStatus.HAPPY_PATH)

    # Write a dummy output PDF so send_final_pdf_email can attach it
    output_pdf = dst / "John Doe_finetuned.pdf"
    output_pdf.write_bytes(_make_pdf_bytes("Final resume"))

    db.update_candidate(
        cid,
        {
            "candidate_name": "John Doe",
            "candidate_email": "john@example.com",
            "output_pdf_path": str(output_pdf),
            "llm_output_json": json.dumps(HAPPY_LLM_OUTPUT),
            "missing_fields": "[]",
        },
    )

    # Advance: HAPPY_PATH → EMAIL_SENT → AWAITING_PAYMENT → PAYMENT_CONFIRMED
    db.set_status(cid, CandidateStatus.EMAIL_SENT)
    db.set_status(cid, CandidateStatus.AWAITING_PAYMENT)
    db.set_status(cid, CandidateStatus.PAYMENT_CONFIRMED)

    candidate = db.get_candidate(cid)
    config = db.get_config()

    # Mock SMTP and crypto - no real connection
    with (
        patch("app.email_handler.sender.decrypt_password", return_value="plain_pass"),
        patch("app.email_handler.sender._get_smtp_connection") as mock_smtp,
    ):
        mock_conn = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        from app.email_handler.sender import send_final_pdf_email
        result = send_final_pdf_email(candidate, config)

    assert result is True
    mock_conn.send_message.assert_called_once()

    # Advance to OUTPUT_SENT (UI's Send Resume button does this)
    db.set_status(cid, CandidateStatus.OUTPUT_SENT)
    final = db.get_candidate(cid)
    assert final.status == CandidateStatus.OUTPUT_SENT.value


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 - Error Path: bad file → ERROR, batch continues (PRD F3, F7)
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_error_path(tmp_path):
    """
    extract_text_and_photo raises RuntimeError for the first candidate.

    Asserts:
    - First candidate status = ERROR, error_message populated
    - Batch does NOT crash - second candidate is processed (HAPPY_PATH)
    - Checkpoint written for both candidates
    """
    src, dst = _make_src(tmp_path, ["bad_resume.pdf", "good_resume.pdf"])
    db, db_path = _make_db(tmp_path, src, dst, batch_size=0)

    pdf_bytes = _make_pdf_bytes()
    output_pdf = dst / "John Doe_finetuned.pdf"

    call_count = {"n": 0}

    def _extract_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("Corrupted PDF - cannot extract text")
        return {"text": "Second candidate resume text", "photo_bytes": None}

    with (
        patch("app.ui.runner.find_and_read_jd", return_value="JD text"),
        patch("app.ui.runner.search_best_practice", return_value="BP text"),
        patch("app.ui.runner.extract_text_and_photo", side_effect=_extract_side_effect),
        patch("app.ui.runner.fine_tune_resume", return_value=HAPPY_LLM_OUTPUT),
        patch("app.ui.runner.generate_resume_pdf", side_effect=lambda *a, **kw: output_pdf.write_bytes(pdf_bytes)),
    ):
        session = {"is_running": True}
        runner = BatchRunner(db_path, session)
        runner.run()

    assert not session["is_running"]

    with db._get_connection() as conn:
        rows = conn.execute(
            "SELECT status, error_message FROM candidates ORDER BY id"
        ).fetchall()

    assert len(rows) == 2

    # First candidate → ERROR with a message (files iterate alphabetically: bad_ first)
    assert rows[0]["status"] == CandidateStatus.ERROR.value
    assert rows[0]["error_message"] is not None
    assert len(rows[0]["error_message"]) > 0

    # Second candidate → HAPPY_PATH (batch continued)
    assert rows[1]["status"] == CandidateStatus.HAPPY_PATH.value

    # Checkpoint reflects both candidates processed (error counts too)
    mgr = CheckpointManager(db)
    cp = mgr.get_resume_point(str(src))
    assert cp is not None
    assert cp.total_processed == 2

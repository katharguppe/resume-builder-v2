"""
Shared pytest fixtures for the resume_finetuner test suite.

Fixtures here are auto-discovered by pytest and available in ALL test files.
External I/O (LibreOffice, Gemini, SMTP) is mocked per-test — conftest only
sets up file-system and DB state.
"""
import io
import json
import pytest
from pathlib import Path

from reportlab.pdfgen import canvas  # type: ignore

from app.state.db import StateDB


# ─────────────────────────────────────────────────────────────────────────────
# PDF helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_simple_pdf(path: Path, text: str = "Sample resume content.") -> None:
    """Write a minimal single-page PDF to *path* using reportlab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.save()
    path.write_bytes(buf.getvalue())


# ─────────────────────────────────────────────────────────────────────────────
# Folder fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def source_folder(tmp_path: Path) -> Path:
    """
    Build a source folder with:
      source/
        jd.txt
        resumes/
          happy_resume.pdf
          missing_resume.pdf
    Returns the *source* Path.
    """
    src = tmp_path / "source"
    resumes = src / "resumes"
    resumes.mkdir(parents=True)

    (src / "jd.txt").write_text(
        "We are looking for a Senior Python Engineer with 5+ years of experience "
        "in FastAPI, PostgreSQL, and cloud deployments.",
        encoding="utf-8",
    )
    _make_simple_pdf(resumes / "happy_resume.pdf", "John Doe – happy path resume")
    _make_simple_pdf(resumes / "missing_resume.pdf", "Jane Smith – missing fields resume")

    return src


@pytest.fixture()
def dest_folder(tmp_path: Path) -> Path:
    """Destination folder where fine-tuned PDFs and sub-dirs are written."""
    dst = tmp_path / "dest"
    dst.mkdir(parents=True)
    return dst


# ─────────────────────────────────────────────────────────────────────────────
# Database fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def configured_db(tmp_path: Path, source_folder: Path, dest_folder: Path):
    """
    Return a (StateDB, db_path) tuple that already has a full recruiter config
    saved.  SMTP password is stored as a plain string here — the runner's
    decrypt_password call is mocked in each E2E test.
    """
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
            "batch_size": 0,
            "source_folder": str(source_folder),
            "destination_folder": str(dest_folder),
            "best_practice_paths": json.dumps([]),
        }
    )

    return db, db_path

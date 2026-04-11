import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import dataclasses

from app.state.db import StateDB, VALID_TRANSITIONS
from app.state.models import CandidateStatus
from app.ui.runner import BatchRunner


def test_email_sent_in_valid_transitions():
    """HAPPY_PATH and MISSING_DETAILS must transition to EMAIL_SENT, not directly to AWAITING_PAYMENT."""
    assert CandidateStatus.EMAIL_SENT in VALID_TRANSITIONS[CandidateStatus.HAPPY_PATH]
    assert CandidateStatus.EMAIL_SENT in VALID_TRANSITIONS[CandidateStatus.MISSING_DETAILS]
    assert CandidateStatus.AWAITING_PAYMENT not in VALID_TRANSITIONS[CandidateStatus.HAPPY_PATH]
    assert CandidateStatus.AWAITING_PAYMENT not in VALID_TRANSITIONS[CandidateStatus.MISSING_DETAILS]


def test_email_sent_transitions_to_awaiting_payment():
    """EMAIL_SENT must be a valid transition source leading to AWAITING_PAYMENT."""
    assert CandidateStatus.EMAIL_SENT in VALID_TRANSITIONS
    assert CandidateStatus.AWAITING_PAYMENT in VALID_TRANSITIONS[CandidateStatus.EMAIL_SENT]


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "resume_tuner.db"
    db = StateDB(db_path)

    db.save_config({
        "recruiter_name": "Test Recruiter",
        "recruiter_email": "recruiter@test.com",
        "smtp_server": "smtp.test.com",
        "smtp_port": 587,
        "smtp_password": "encrypted_pass",
        "service_fee": "100",
        "batch_size": 1,
        "destination_folder": str(tmp_path / "dest"),
        "best_practice_paths": json.dumps([])
    })

    (tmp_path / "dest").mkdir(parents=True, exist_ok=True)

    return db, db_path, tmp_path


@patch('app.ui.runner.find_and_read_jd')
@patch('app.ui.runner.search_best_practice')
@patch('app.ui.runner.convert_doc_to_pdf')
@patch('app.ui.runner.extract_text_and_photo')
@patch('app.ui.runner.fine_tune_resume')
@patch('app.ui.runner.generate_resume_pdf')
@patch('app.ui.runner.send_outreach_email')
def test_batch_runner_happy_path(
    mock_send, mock_pdf, mock_tune, mock_extract,
    mock_convert, mock_search, mock_jd, temp_db
):
    db, db_path, tmp_path = temp_db

    mock_jd.return_value = "Mock JD"
    mock_search.return_value = "Mock BP"
    mock_extract.return_value = {"text": "Resume text", "photo_bytes": None}
    mock_tune.return_value = {
        "candidate_name": "John Doe",
        "missing_fields": [],
        "contact": {"email": "john@example.com"}
    }

    source_folder = tmp_path / "source"
    resumes_dir = source_folder / "resumes"
    resumes_dir.mkdir(parents=True)
    (resumes_dir / "test.pdf").touch()

    db.save_config({"source_folder": str(source_folder)})

    session_state = {"is_running": True}
    runner = BatchRunner(db_path, session_state)
    runner.run()

    assert not session_state["is_running"]

    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM candidates")
        cands = cursor.fetchall()

    assert len(cands) == 1
    assert cands[0]["status"] == CandidateStatus.HAPPY_PATH.value
    assert cands[0]["candidate_name"] == "John Doe"

    mock_extract.assert_called_once()
    mock_tune.assert_called_once()
    mock_pdf.assert_called_once()
    mock_send.assert_not_called()


@patch('app.ui.runner.find_and_read_jd')
@patch('app.ui.runner.extract_text_and_photo')
@patch('app.ui.runner.fine_tune_resume')
@patch('app.ui.runner.generate_resume_pdf')
@patch('app.ui.runner.send_outreach_email')
def test_batch_runner_missing_details(
    mock_send, mock_pdf, mock_tune, mock_extract,
    mock_jd, temp_db
):
    db, db_path, tmp_path = temp_db

    mock_jd.return_value = "Mock JD"
    mock_extract.return_value = {"text": "Resume text", "photo_bytes": None}
    mock_tune.return_value = {
        "candidate_name": "Jane Smith",
        "missing_fields": ["Phone", "LinkedIn"],
        "contact": {"email": "jane@example.com"}
    }

    source_folder = tmp_path / "source"
    resumes_dir = source_folder / "resumes"
    resumes_dir.mkdir(parents=True)
    (resumes_dir / "test.doc").touch()

    db.save_config({
        "source_folder": str(source_folder),
        "best_practice_paths": json.dumps(["foo"])
    })

    with patch('app.ui.runner.load_best_practice_files') as mock_bp_load, \
         patch('app.ui.runner.convert_doc_to_pdf') as mock_convert:

        mock_bp_load.return_value = "Mock BP Text"
        mock_convert.return_value = tmp_path / "dest" / "converted" / "test.pdf"

        session_state = {"is_running": True}
        runner = BatchRunner(db_path, session_state)
        runner.run()

    assert not session_state["is_running"]

    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM candidates")
        cands = cursor.fetchall()

    assert len(cands) == 1
    assert cands[0]["status"] == CandidateStatus.MISSING_DETAILS.value
    assert "Phone" in json.loads(cands[0]["missing_fields"])

    mock_extract.assert_called_once()
    mock_tune.assert_called_once()
    mock_pdf.assert_called_once()
    mock_send.assert_not_called()


@patch('app.ui.runner.find_and_read_jd')
@patch('app.ui.runner.extract_text_and_photo')
@patch('app.ui.runner.fine_tune_resume')
@patch('app.ui.runner.generate_resume_pdf')
@patch('app.ui.runner.send_outreach_email')
def test_runner_does_not_auto_send_email(
    mock_send, mock_pdf, mock_tune, mock_extract,
    mock_jd, temp_db
):
    """BatchRunner must never call send_outreach_email - email is manual only."""
    db, db_path, tmp_path = temp_db

    mock_jd.return_value = "Mock JD"
    mock_extract.return_value = {"text": "Resume text", "photo_bytes": None}
    mock_tune.return_value = {
        "candidate_name": "John Doe",
        "missing_fields": [],
        "contact": {"email": "john@example.com"}
    }

    source_folder = tmp_path / "source"
    resumes_dir = source_folder / "resumes"
    resumes_dir.mkdir(parents=True)
    (resumes_dir / "test.pdf").touch()
    db.save_config({"source_folder": str(source_folder)})

    session_state = {"is_running": True}
    BatchRunner(db_path, session_state).run()

    mock_send.assert_not_called()


@patch('app.ui.runner.find_and_read_jd')
@patch('app.ui.runner.extract_text_and_photo')
@patch('app.ui.runner.fine_tune_resume')
@patch('app.ui.runner.generate_resume_pdf')
def test_runner_does_not_pre_decrypt_smtp_password(
    mock_pdf, mock_tune, mock_extract, mock_jd, temp_db
):
    """BatchRunner must not call decrypt_password - decryption belongs to sender.py only."""
    db, db_path, tmp_path = temp_db

    mock_jd.return_value = "Mock JD"
    mock_extract.return_value = {"text": "Resume text", "photo_bytes": None}
    mock_tune.return_value = {
        "candidate_name": "John Doe",
        "missing_fields": [],
        "contact": {"email": "john@example.com"}
    }

    source_folder = tmp_path / "source"
    resumes_dir = source_folder / "resumes"
    resumes_dir.mkdir(parents=True)
    (resumes_dir / "test.pdf").touch()
    db.save_config({"source_folder": str(source_folder)})

    import app.ui.runner as runner_module
    assert not hasattr(runner_module, 'decrypt_password'), \
        "decrypt_password must not be imported in runner - decryption belongs to sender.py only"


def test_payment_confirmed_can_reach_output_sent():
    """Send Email checkbox for PAYMENT_CONFIRMED must be able to set OUTPUT_SENT."""
    assert CandidateStatus.OUTPUT_SENT in VALID_TRANSITIONS[CandidateStatus.PAYMENT_CONFIRMED]

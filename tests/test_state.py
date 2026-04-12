import pytest
import tempfile
import sqlite3
from pathlib import Path
from app.state.models import CandidateStatus
from app.state.db import StateDB
from app.state.checkpoint import CheckpointManager

@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield Path(path)
    Path(path).unlink(missing_ok=True)

@pytest.fixture
def state_db(temp_db_path):
    return StateDB(temp_db_path)

@pytest.fixture
def cp_mgr(state_db):
    return CheckpointManager(state_db)

def test_init_tables(temp_db_path, state_db):
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    
    # Check candidates
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='candidates'")
    assert cursor.fetchone() is not None
    
    # Check checkpoints
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'")
    assert cursor.fetchone() is not None
    
    # Check recruiter_config
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recruiter_config'")
    assert cursor.fetchone() is not None
    conn.close()

def test_add_and_get_candidate(state_db):
    cand_id = state_db.add_candidate("/src", "resume.pdf")
    assert cand_id > 0
    
    cand = state_db.get_candidate(cand_id)
    assert cand is not None
    assert cand.source_folder == "/src"
    assert cand.source_filename == "resume.pdf"
    assert cand.status == CandidateStatus.PENDING

def test_valid_status_transitions(state_db):
    cand_id = state_db.add_candidate("/src", "resume.pdf")
    
    # PENDING -> PROCESSING
    state_db.set_status(cand_id, CandidateStatus.PROCESSING)
    cand = state_db.get_candidate(cand_id)
    assert cand.status == CandidateStatus.PROCESSING

    # PROCESSING -> HAPPY_PATH
    state_db.set_status(cand_id, CandidateStatus.HAPPY_PATH)
    cand = state_db.get_candidate(cand_id)
    assert cand.status == CandidateStatus.HAPPY_PATH

def test_invalid_status_transitions(state_db):
    cand_id = state_db.add_candidate("/src", "resume.pdf")
    
    # PENDING -> HAPPY_PATH (Invalid)
    with pytest.raises(ValueError, match="Invalid transition"):
        state_db.set_status(cand_id, CandidateStatus.HAPPY_PATH)

def test_update_candidate(state_db):
    cand_id = state_db.add_candidate("/src", "resume.pdf")
    
    # Cannot update status via update_candidate
    with pytest.raises(ValueError, match="Status must be updated via set_status()"):
        state_db.update_candidate(cand_id, {"status": "PROCESSING"})
        
    state_db.update_candidate(cand_id, {"candidate_name": "John Doe", "missing_fields": "[\"phone\"]"})
    cand = state_db.get_candidate(cand_id)
    assert cand.candidate_name == "John Doe"
    assert cand.missing_fields == "[\"phone\"]"

def test_get_pending_candidates(state_db):
    state_db.add_candidate("/src", "r1.pdf")
    state_db.add_candidate("/src", "r2.pdf")
    state_db.add_candidate("/src2", "r3.pdf")
    state_db.add_candidate("/src", "r4.pdf")
    
    pends = state_db.get_pending_candidates("/src")
    assert len(pends) == 3
    
    # change one status
    state_db.set_status(pends[0].id, CandidateStatus.PROCESSING)
    
    pends_after = state_db.get_pending_candidates("/src")
    assert len(pends_after) == 2

def test_config_crud(state_db):
    # Get empty
    cfg = state_db.get_config()
    assert cfg is None
    
    # Insert
    state_db.save_config({"recruiter_name": "Bob", "batch_size": 10})
    cfg2 = state_db.get_config()
    assert cfg2.recruiter_name == "Bob"
    assert cfg2.batch_size == 10
    
    # Update
    state_db.save_config({"recruiter_name": "Alice", "service_fee": "500"})
    cfg3 = state_db.get_config()
    assert cfg3.recruiter_name == "Alice"
    assert cfg3.batch_size == 10
    assert cfg3.service_fee == "500"

def test_checkpoint_save_and_read(cp_mgr):
    # empty
    assert cp_mgr.get_resume_point("/src") is None

    cp_mgr.save_checkpoint(1, 5, "res1.pdf", 1, "/src")
    cp_mgr.save_checkpoint(1, 5, "res2.pdf", 2, "/src")

    cp = cp_mgr.get_resume_point("/src")
    assert cp is not None
    assert cp.last_processed_filename == "res2.pdf"
    assert cp.total_processed == 2


# ── Phase 2: SubmissionStatus + SubmissionRecord ──────────────────────────────

from app.state.models import SubmissionStatus, SubmissionRecord
from app.state.db import AuthDB, SubmissionsDB


@pytest.fixture
def submissions_db(tmp_path):
    db_path = tmp_path / "test_subs.db"
    AuthDB(db_path)  # users table must exist for FK
    return SubmissionsDB(db_path)


@pytest.fixture
def user_and_submissions_db(tmp_path):
    db_path = tmp_path / "test_subs.db"
    auth_db = AuthDB(db_path)
    subs_db = SubmissionsDB(db_path)
    user_id = auth_db.create_user("test@example.com")
    return user_id, subs_db


def test_create_submission(user_and_submissions_db):
    user_id, subs_db = user_and_submissions_db
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-abc")
    assert isinstance(sub_id, int)
    assert sub_id > 0


def test_get_submission(user_and_submissions_db):
    user_id, subs_db = user_and_submissions_db
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-abc")
    rec = subs_db.get_submission(sub_id)
    assert rec is not None
    assert rec.user_id == user_id
    assert rec.session_token == "tok-abc"
    assert rec.status == SubmissionStatus.PENDING.value
    assert rec.revision_count == 0


def test_get_submission_not_found(user_and_submissions_db):
    _, subs_db = user_and_submissions_db
    assert subs_db.get_submission(9999) is None


def test_update_submission(user_and_submissions_db):
    user_id, subs_db = user_and_submissions_db
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-xyz")
    subs_db.update_submission(sub_id, {
        "resume_raw_text": "John Doe resume",
        "resume_fields_json": '{"candidate_name": "John Doe"}',
    })
    rec = subs_db.get_submission(sub_id)
    assert rec.resume_raw_text == "John Doe resume"
    assert rec.resume_fields_json == '{"candidate_name": "John Doe"}'


def test_update_submission_status_blocked(user_and_submissions_db):
    user_id, subs_db = user_and_submissions_db
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-s")
    with pytest.raises(ValueError, match="set_status"):
        subs_db.update_submission(sub_id, {"status": "PROCESSING"})


def test_set_status(user_and_submissions_db):
    user_id, subs_db = user_and_submissions_db
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-st")
    subs_db.set_status(sub_id, SubmissionStatus.PROCESSING)
    rec = subs_db.get_submission(sub_id)
    assert rec.status == SubmissionStatus.PROCESSING.value


def test_set_status_to_error_from_any(user_and_submissions_db):
    user_id, subs_db = user_and_submissions_db
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-err")
    subs_db.set_status(sub_id, SubmissionStatus.ERROR)
    rec = subs_db.get_submission(sub_id)
    assert rec.status == SubmissionStatus.ERROR.value


def test_get_submissions_by_user(user_and_submissions_db):
    user_id, subs_db = user_and_submissions_db
    subs_db.create_submission(user_id=user_id, session_token="tok-1")
    subs_db.create_submission(user_id=user_id, session_token="tok-2")
    results = subs_db.get_submissions_by_user(user_id)
    assert len(results) == 2


def test_submission_status_values():
    assert SubmissionStatus.PENDING.value == "PENDING"
    assert SubmissionStatus.PROCESSING.value == "PROCESSING"
    assert SubmissionStatus.REVIEW_READY.value == "REVIEW_READY"
    assert SubmissionStatus.REVISION_REQUESTED.value == "REVISION_REQUESTED"
    assert SubmissionStatus.REVISION_EXHAUSTED.value == "REVISION_EXHAUSTED"
    assert SubmissionStatus.ACCEPTED.value == "ACCEPTED"
    assert SubmissionStatus.PAYMENT_PENDING.value == "PAYMENT_PENDING"
    assert SubmissionStatus.PAYMENT_CONFIRMED.value == "PAYMENT_CONFIRMED"
    assert SubmissionStatus.DOWNLOAD_READY.value == "DOWNLOAD_READY"
    assert SubmissionStatus.DOWNLOADED.value == "DOWNLOADED"
    assert SubmissionStatus.ERROR.value == "ERROR"


def test_submission_record_fields():
    rec = SubmissionRecord(
        id=1,
        user_id=2,
        session_token="tok",
        resume_raw_text="raw",
        resume_fields_json='{"candidate_name": "Alice"}',
        resume_photo_path=None,
        jd_raw_text="jd text",
        jd_fields_json='{"job_title": "Engineer"}',
        status="PENDING",
        revision_count=0,
        error_message=None,
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )
    assert rec.user_id == 2
    assert rec.revision_count == 0
    assert rec.resume_photo_path is None

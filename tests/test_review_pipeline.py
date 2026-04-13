"""
Tests for _run_rewrite_pipeline helper defined in app/ui/pages/3_Review.py.

Streamlit is stubbed out so the page module can be imported safely.
The helper function is extracted and tested in isolation with mocked
LLM, scoring, and PDF dependencies.
"""
import sys
import json
import dataclasses
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Stub streamlit before any page import ──────────────────────────────────
_st_mock = MagicMock()
_st_mock.session_state = MagicMock()
_st_mock.session_state.get.return_value = None   # no auth token → main() returns early
_st_mock.stop = MagicMock()                       # st.stop() is a no-op
sys.modules["streamlit"] = _st_mock

# ── Import the review page module ──────────────────────────────────────────
import importlib.util as _ilu
_page_path = Path(__file__).parent.parent / "app" / "ui" / "pages" / "3_Review.py"
_spec = _ilu.spec_from_file_location("review_page_module", str(_page_path))
_review_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_review_mod)

_run_rewrite_pipeline = _review_mod._run_rewrite_pipeline


# ── Fixtures ───────────────────────────────────────────────────────────────

from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionStatus, SubmissionRecord
from app.scoring import ATSScore


@pytest.fixture
def db_and_submission(tmp_path):
    db_path = tmp_path / "test.db"
    auth_db = AuthDB(db_path)
    subs_db = SubmissionsDB(db_path)
    user_id = auth_db.create_user("test@x.com")
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-pipeline")

    resume_fields = {
        "candidate_name": "Alice",
        "email": "a@b.com",
        "phone": "555",
        "current_title": "Engineer",
        "skills": ["Python", "SQL"],
        "experience_summary": "5 years",
    }
    jd_fields = {
        "job_title": "Senior Engineer",
        "company": "ACME",
        "required_skills": ["Python"],
        "preferred_skills": ["SQL"],
        "experience_required": "5 years",
        "education_required": "BS",
        "key_responsibilities": ["Build APIs"],
    }
    subs_db.update_submission(sub_id, {
        "resume_raw_text": "Alice resume raw",
        "resume_fields_json": json.dumps(resume_fields),
        "jd_raw_text": "Senior Engineer at ACME",
        "jd_fields_json": json.dumps(jd_fields),
    })
    subs_db.set_status(sub_id, SubmissionStatus.PROCESSING)

    submission = subs_db.get_submission(sub_id)
    return subs_db, submission, tmp_path / "output"


LLM_OUTPUT = {
    "candidate_name": "Alice",
    "contact": {"email": "a@b.com", "phone": "555", "linkedin": ""},
    "summary": "Strong engineer with 5 years experience.",
    "experience": [],
    "education": [],
    "skills": ["Python", "SQL"],
    "missing_fields": [],
}


# ── Tests ───────────────────────────────────────────────────────────────────

def test_pipeline_sets_review_ready(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    ats_val = ATSScore(total=75, keyword_match=20, skills_coverage=22,
                       experience_clarity=18, structure_completeness=15,
                       keyword_matched=[], skills_matched=["Python"], skills_missing=[])
    with patch.object(_review_mod, "rewrite_resume", return_value=LLM_OUTPUT), \
         patch.object(_review_mod, "search_best_practice", return_value="Best practice text"), \
         patch.object(_review_mod, "compute_ats_score", return_value=ats_val), \
         patch.object(_review_mod, "generate_resume_pdf", return_value=True):
        _run_rewrite_pipeline(submission, subs_db, output_dir)

    updated = subs_db.get_submission(submission.id)
    assert updated.status == SubmissionStatus.REVIEW_READY.value
    assert updated.llm_output_json is not None
    assert updated.ats_score_json is not None
    assert updated.output_pdf_path is not None
    assert str(submission.id) in updated.output_pdf_path


def test_pipeline_stores_llm_output_json(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    ats_val = ATSScore(total=80, keyword_match=25, skills_coverage=25,
                       experience_clarity=15, structure_completeness=15,
                       keyword_matched=[], skills_matched=[], skills_missing=[])
    with patch.object(_review_mod, "rewrite_resume", return_value=LLM_OUTPUT), \
         patch.object(_review_mod, "search_best_practice", return_value="Best practice text"), \
         patch.object(_review_mod, "compute_ats_score", return_value=ats_val), \
         patch.object(_review_mod, "generate_resume_pdf", return_value=True):
        _run_rewrite_pipeline(submission, subs_db, output_dir)

    updated = subs_db.get_submission(submission.id)
    stored = json.loads(updated.llm_output_json)
    assert stored["candidate_name"] == "Alice"
    assert stored["summary"] == "Strong engineer with 5 years experience."


def test_pipeline_raises_on_llm_failure(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    with patch.object(_review_mod, "rewrite_resume", side_effect=ValueError("LLM failed")), \
         patch.object(_review_mod, "search_best_practice", return_value="bp"), \
         patch.object(_review_mod, "compute_ats_score", return_value=MagicMock()), \
         patch.object(_review_mod, "generate_resume_pdf", return_value=True):
        with pytest.raises(ValueError, match="LLM failed"):
            _run_rewrite_pipeline(submission, subs_db, output_dir)


def test_pipeline_raises_on_pdf_failure(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    ats_val = ATSScore(total=70, keyword_match=20, skills_coverage=20,
                       experience_clarity=15, structure_completeness=15,
                       keyword_matched=[], skills_matched=[], skills_missing=[])
    with patch.object(_review_mod, "rewrite_resume", return_value=LLM_OUTPUT), \
         patch.object(_review_mod, "search_best_practice", return_value="bp"), \
         patch.object(_review_mod, "compute_ats_score", return_value=ats_val), \
         patch.object(_review_mod, "generate_resume_pdf", return_value=False):
        with pytest.raises(RuntimeError, match="PDF generation failed"):
            _run_rewrite_pipeline(submission, subs_db, output_dir)


def test_pipeline_calls_rewrite_with_best_practice(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    mock_ats_val = ATSScore(total=70, keyword_match=20, skills_coverage=20,
                            experience_clarity=15, structure_completeness=15,
                            keyword_matched=[], skills_matched=[], skills_missing=[])
    with patch.object(_review_mod, "search_best_practice", return_value="Generic best practice") as mock_bp, \
         patch.object(_review_mod, "rewrite_resume", return_value=LLM_OUTPUT) as mock_rewrite, \
         patch.object(_review_mod, "compute_ats_score", return_value=mock_ats_val), \
         patch.object(_review_mod, "generate_resume_pdf", return_value=True):
        _run_rewrite_pipeline(submission, subs_db, output_dir)

    mock_bp.assert_called_once_with("Senior Engineer")
    mock_rewrite.assert_called_once_with(
        submission.resume_raw_text,
        submission.jd_raw_text,
        "Generic best practice",
    )

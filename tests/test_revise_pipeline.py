"""
Tests for _run_revision_pipeline helper in app/ui/pages/4_Revise.py.
Streamlit stubbed out so page can be imported without a running server.
"""
import sys
import json
import dataclasses
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Stub streamlit before any page import ──────────────────────────────────
_st_mock = MagicMock()
_st_mock.session_state = MagicMock()
_st_mock.session_state.get.return_value = None
_st_mock.stop = MagicMock()
sys.modules["streamlit"] = _st_mock

# ── Import the revise page module ──────────────────────────────────────────
import importlib.util as _ilu
_page_path = Path(__file__).parent.parent / "app" / "ui" / "pages" / "4_Revise.py"
_spec = _ilu.spec_from_file_location("revise_page_module", str(_page_path))
_revise_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_revise_mod)

_run_revision_pipeline = _revise_mod._run_revision_pipeline

# ── Fixtures ───────────────────────────────────────────────────────────────
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionStatus
from app.scoring import ATSScore


@pytest.fixture
def db_and_submission(tmp_path):
    db_path = tmp_path / "test.db"
    auth_db = AuthDB(db_path)
    subs_db = SubmissionsDB(db_path)
    user_id = auth_db.create_user("test@x.com")
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-revise")

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
    subs_db.set_status(sub_id, SubmissionStatus.REVISION_REQUESTED)
    submission = subs_db.get_submission(sub_id)
    return subs_db, submission, tmp_path / "output"


LLM_OUTPUT = {
    "candidate_name": "Alice",
    "contact": {"email": "a@b.com", "phone": "555", "linkedin": ""},
    "summary": "Revised: Strong engineer with 5 years experience.",
    "experience": [],
    "education": [],
    "skills": ["Python", "SQL"],
    "missing_fields": [],
}


def _make_ats():
    return ATSScore(
        total=78, keyword_match=22, skills_coverage=23,
        experience_clarity=18, structure_completeness=15,
        keyword_matched=[], skills_matched=["Python"], skills_missing=[],
    )


# ── Tests ───────────────────────────────────────────────────────────────────

def test_revision_pipeline_sets_review_ready(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    with patch.object(_revise_mod, "rewrite_resume", return_value=LLM_OUTPUT), \
         patch.object(_revise_mod, "search_best_practice", return_value="bp"), \
         patch.object(_revise_mod, "compute_ats_score", return_value=_make_ats()), \
         patch.object(_revise_mod, "generate_resume_pdf", return_value=True):
        _run_revision_pipeline(submission, subs_db, output_dir, "Make summary shorter")

    updated = subs_db.get_submission(submission.id)
    assert updated.status == SubmissionStatus.REVIEW_READY.value


def test_revision_pipeline_stores_updated_llm_output(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    with patch.object(_revise_mod, "rewrite_resume", return_value=LLM_OUTPUT), \
         patch.object(_revise_mod, "search_best_practice", return_value="bp"), \
         patch.object(_revise_mod, "compute_ats_score", return_value=_make_ats()), \
         patch.object(_revise_mod, "generate_resume_pdf", return_value=True):
        _run_revision_pipeline(submission, subs_db, output_dir, "Make summary shorter")

    updated = subs_db.get_submission(submission.id)
    stored = json.loads(updated.llm_output_json)
    assert stored["summary"] == "Revised: Strong engineer with 5 years experience."


def test_revision_pipeline_raises_on_llm_failure(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    with patch.object(_revise_mod, "rewrite_resume", side_effect=ValueError("LLM down")), \
         patch.object(_revise_mod, "search_best_practice", return_value="bp"), \
         patch.object(_revise_mod, "compute_ats_score", return_value=_make_ats()), \
         patch.object(_revise_mod, "generate_resume_pdf", return_value=True):
        with pytest.raises(ValueError, match="LLM down"):
            _run_revision_pipeline(submission, subs_db, output_dir, "hint")


def test_revision_pipeline_raises_on_pdf_failure(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    with patch.object(_revise_mod, "rewrite_resume", return_value=LLM_OUTPUT), \
         patch.object(_revise_mod, "search_best_practice", return_value="bp"), \
         patch.object(_revise_mod, "compute_ats_score", return_value=_make_ats()), \
         patch.object(_revise_mod, "generate_resume_pdf", return_value=False):
        with pytest.raises(RuntimeError, match="PDF generation failed"):
            _run_revision_pipeline(submission, subs_db, output_dir, "hint")


def test_revision_pipeline_passes_hint_to_rewrite(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    with patch.object(_revise_mod, "rewrite_resume", return_value=LLM_OUTPUT) as mock_rewrite, \
         patch.object(_revise_mod, "search_best_practice", return_value="bp"), \
         patch.object(_revise_mod, "compute_ats_score", return_value=_make_ats()), \
         patch.object(_revise_mod, "generate_resume_pdf", return_value=True):
        _run_revision_pipeline(submission, subs_db, output_dir, "Emphasise leadership skills")

    mock_rewrite.assert_called_once_with(
        submission.resume_raw_text,
        submission.jd_raw_text,
        "bp",
        revision_hint="Emphasise leadership skills",
    )


def test_revision_pipeline_calls_best_practice(db_and_submission):
    subs_db, submission, output_dir = db_and_submission
    with patch.object(_revise_mod, "search_best_practice", return_value="generic bp") as mock_bp, \
         patch.object(_revise_mod, "rewrite_resume", return_value=LLM_OUTPUT), \
         patch.object(_revise_mod, "compute_ats_score", return_value=_make_ats()), \
         patch.object(_revise_mod, "generate_resume_pdf", return_value=True):
        _run_revision_pipeline(submission, subs_db, output_dir, "hint")

    mock_bp.assert_called_once_with("Senior Engineer")

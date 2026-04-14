"""
Tests for helper functions in app/ui/pages/5_Skills.py.

Streamlit is stubbed out so the page module can be imported safely.
Only pure helper functions are tested here — no st.* calls.
"""
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Stub streamlit before page import ─────────────────────────────────────
_st_mock = MagicMock()
_st_mock.session_state = {}
_st_mock.stop = MagicMock()
sys.modules["streamlit"] = _st_mock

# ── Import the skills page module ──────────────────────────────────────────
import importlib.util as _ilu
_page_path = Path(__file__).parent.parent / "app" / "ui" / "pages" / "5_Skills.py"
_spec = _ilu.spec_from_file_location("skills_page_module", str(_page_path))
_skills_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_skills_mod)

_init_skills_state = _skills_mod._init_skills_state
_save_skills = _skills_mod._save_skills


# ── Fixtures ───────────────────────────────────────────────────────────────

from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionStatus


@pytest.fixture
def db_and_submission(tmp_path):
    db_path = tmp_path / "test.db"
    auth_db = AuthDB(db_path)
    subs_db = SubmissionsDB(db_path)
    user_id = auth_db.create_user("test@x.com")
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-skills")
    llm_output = {
        "candidate_name": "Alice",
        "contact": {"email": "a@b.com", "phone": "123", "linkedin": ""},
        "summary": "Summary text",
        "experience": [],
        "education": [],
        "skills": ["Python", "Leadership", "Salesforce"],
        "missing_fields": [],
    }
    subs_db.update_submission(sub_id, {"llm_output_json": json.dumps(llm_output)})
    subs_db.set_status(sub_id, SubmissionStatus.REVIEW_READY)
    return subs_db, sub_id, llm_output


# ── _init_skills_state ─────────────────────────────────────────────────────

def test_init_skills_state_returns_skills_list(db_and_submission):
    subs_db, sub_id, llm_output = db_and_submission
    result = _init_skills_state(json.dumps(llm_output))
    assert result == ["Python", "Leadership", "Salesforce"]


def test_init_skills_state_empty_skills():
    llm_output = {"skills": []}
    result = _init_skills_state(json.dumps(llm_output))
    assert result == []


def test_init_skills_state_missing_skills_key():
    result = _init_skills_state(json.dumps({}))
    assert result == []


def test_init_skills_state_returns_list():
    result = _init_skills_state(json.dumps({"skills": ["A", "B"]}))
    assert isinstance(result, list)


# ── _save_skills ───────────────────────────────────────────────────────────

def test_save_skills_persists_flat_list(db_and_submission):
    subs_db, sub_id, llm_output = db_and_submission
    new_skills = ["Python", "SQL", "Leadership"]
    _save_skills(subs_db, sub_id, json.dumps(llm_output), new_skills)

    updated = subs_db.get_submission(sub_id)
    saved = json.loads(updated.llm_output_json)
    assert saved["skills"] == ["Python", "SQL", "Leadership"]


def test_save_skills_preserves_other_llm_output_fields(db_and_submission):
    subs_db, sub_id, llm_output = db_and_submission
    _save_skills(subs_db, sub_id, json.dumps(llm_output), ["NewSkill"])

    updated = subs_db.get_submission(sub_id)
    saved = json.loads(updated.llm_output_json)
    assert saved["candidate_name"] == "Alice"
    assert saved["summary"] == "Summary text"


def test_save_skills_empty_list(db_and_submission):
    subs_db, sub_id, llm_output = db_and_submission
    _save_skills(subs_db, sub_id, json.dumps(llm_output), [])

    updated = subs_db.get_submission(sub_id)
    saved = json.loads(updated.llm_output_json)
    assert saved["skills"] == []

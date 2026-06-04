# Phase 5 — Revision Request Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `4_Revise.py` revision page + add `revision_hint` support to the LLM layer, enabling candidates to request up to 3 guided re-runs of the resume rewrite pipeline.

**Architecture:** `revision_hint` is threaded through `build_finetuning_prompt` → `finetuner.rewrite_resume` → `provider.rewrite_resume` as a default-empty kwarg (zero regression to existing callers). `4_Revise.py` owns its own `_run_revision_pipeline` helper mirroring `3_Review.py`'s, but passing the hint. `3_Review.py` gets a one-line fix replacing the Phase 5 stub with `st.switch_page`.

**Tech Stack:** Python 3.13, Streamlit, SQLite (via `app.state.db`), pytest, `unittest.mock`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app/llm/prompt_builder.py` | Modify | Add `revision_hint=""` param; append REVISION REQUEST block to prompt |
| `app/llm/finetuner.py` | Modify | Add `revision_hint=""` to `rewrite_resume` + `rewrite_resume_deepseek`; pass to prompt |
| `app/llm/provider.py` | Modify | Add `revision_hint=""` to `rewrite_resume`; pass to both adapters |
| `app/ui/pages/3_Review.py` | Modify | Replace `st.info(...)` stub with `st.switch_page("pages/4_Revise.py")` (line ~295) |
| `app/ui/pages/4_Revise.py` | Create | Auth guard, draft expander, revision form, pipeline helper, redirect |
| `tests/test_prompt_builder.py` | Modify | Add 2 tests for revision_hint injection |
| `tests/test_provider.py` | Modify | Update 2 existing call-signature tests + add 2 hint pass-through tests |
| `tests/test_revise_pipeline.py` | Create | 6 tests for `_run_revision_pipeline` |

**Test count:** 204 (current) → 214 (after all tasks)

---

### Task 1: Add `revision_hint` to `build_finetuning_prompt`

**Files:**
- Modify: `app/llm/prompt_builder.py`
- Test: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_prompt_builder.py`:

```python
from app.llm.prompt_builder import build_finetuning_prompt


def test_build_finetuning_prompt_includes_revision_hint():
    prompt = build_finetuning_prompt(
        "resume text", "jd text", "best practice", "Alice",
        revision_hint="Make the summary shorter and more direct.",
    )
    assert "REVISION REQUEST" in prompt
    assert "Make the summary shorter and more direct." in prompt


def test_build_finetuning_prompt_no_hint_unchanged():
    prompt_default = build_finetuning_prompt("resume", "jd", "bp", "Alice")
    prompt_empty = build_finetuning_prompt("resume", "jd", "bp", "Alice", revision_hint="")
    assert "REVISION REQUEST" not in prompt_default
    assert prompt_default == prompt_empty
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_prompt_builder.py::test_build_finetuning_prompt_includes_revision_hint tests/test_prompt_builder.py::test_build_finetuning_prompt_no_hint_unchanged -v
```

Expected: `TypeError: build_finetuning_prompt() got an unexpected keyword argument 'revision_hint'`

- [ ] **Step 3: Implement in `app/llm/prompt_builder.py`**

Change the signature of `build_finetuning_prompt` from:

```python
def build_finetuning_prompt(resume_text: str, jd_text: str, best_practice_text: str, candidate_name: str) -> str:
```

to:

```python
def build_finetuning_prompt(
    resume_text: str,
    jd_text: str,
    best_practice_text: str,
    candidate_name: str,
    revision_hint: str = "",
) -> str:
```

Then replace the final `return prompt.strip()` at the end of the function with:

```python
    if revision_hint.strip():
        prompt += f"\n\n=== REVISION REQUEST ===\n{revision_hint.strip()}\nApply this specific feedback when rewriting the resume."

    return prompt.strip()
```

- [ ] **Step 4: Run the full prompt_builder test file**

```
pytest tests/test_prompt_builder.py -v
```

Expected: all 6 tests PASS (4 existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add app/llm/prompt_builder.py tests/test_prompt_builder.py
git commit -m "[PHASE-05] add: revision_hint support in build_finetuning_prompt"
```

---

### Task 2: Thread `revision_hint` through `finetuner.py`

**Files:**
- Modify: `app/llm/finetuner.py`

No new tests here — hint reaches the prompt (covered by Task 1) and provider routing (covered by Task 3). This task is wiring only.

- [ ] **Step 1: Add `revision_hint=""` to `rewrite_resume` in `app/llm/finetuner.py`**

Change the signature from:

```python
def rewrite_resume(resume_text: str, jd_text: str, best_practice: str) -> dict:
```

to:

```python
def rewrite_resume(resume_text: str, jd_text: str, best_practice: str, revision_hint: str = "") -> dict:
```

Change the `build_finetuning_prompt` call inside the function from:

```python
    prompt = build_finetuning_prompt(resume_text, jd_text, best_practice, candidate_name)
```

to:

```python
    prompt = build_finetuning_prompt(resume_text, jd_text, best_practice, candidate_name, revision_hint=revision_hint)
```

- [ ] **Step 2: Add `revision_hint=""` to `rewrite_resume_deepseek` in `app/llm/finetuner.py`**

Change the signature from:

```python
def rewrite_resume_deepseek(resume_text: str, jd_text: str, best_practice: str) -> dict:
```

to:

```python
def rewrite_resume_deepseek(resume_text: str, jd_text: str, best_practice: str, revision_hint: str = "") -> dict:
```

Change the `build_finetuning_prompt` call inside the function from:

```python
    prompt = build_finetuning_prompt(resume_text, jd_text, best_practice, candidate_name)
```

to:

```python
    prompt = build_finetuning_prompt(resume_text, jd_text, best_practice, candidate_name, revision_hint=revision_hint)
```

- [ ] **Step 3: Run full test suite to verify no regressions**

```
pytest tests/ -v --tb=short
```

Expected: all 206 tests PASS (default `revision_hint=""` means all existing callers are unaffected)

- [ ] **Step 4: Commit**

```bash
git add app/llm/finetuner.py
git commit -m "[PHASE-05] add: revision_hint param in finetuner rewrite functions"
```

---

### Task 3: Thread `revision_hint` through `provider.py` + fix provider tests

**Files:**
- Modify: `app/llm/provider.py`
- Modify: `tests/test_provider.py`

> **Why update existing tests?** After adding `revision_hint=""` to the provider, it calls adapters as `rewrite_resume_claude(..., revision_hint="")`. The two existing tests use `assert_called_once_with` with only 3 positional args — they will fail because mock sees the extra kwarg. The fix is to update those assertions to include `revision_hint=""`.

- [ ] **Step 1: Write the two new failing tests**

Add to the bottom of `tests/test_provider.py`:

```python
def test_rewrite_resume_passes_hint_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_REWRITE_PROVIDER", "claude")
    expected = {"candidate_name": "Alice", "summary": "Revised."}
    with patch("app.llm.provider.rewrite_resume_claude", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        prov.rewrite_resume("resume", "jd", "bp", revision_hint="Focus on Python skills")
    mock_fn.assert_called_once_with("resume", "jd", "bp", revision_hint="Focus on Python skills")


def test_rewrite_resume_passes_hint_to_deepseek(monkeypatch):
    monkeypatch.setenv("LLM_REWRITE_PROVIDER", "deepseek")
    expected = {"candidate_name": "Bob", "summary": "Revised."}
    with patch("app.llm.provider.rewrite_resume_deepseek", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        prov.rewrite_resume("resume", "jd", "bp", revision_hint="Focus on Python skills")
    mock_fn.assert_called_once_with("resume", "jd", "bp", revision_hint="Focus on Python skills")
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_provider.py::test_rewrite_resume_passes_hint_to_claude tests/test_provider.py::test_rewrite_resume_passes_hint_to_deepseek -v
```

Expected: `TypeError: rewrite_resume() got an unexpected keyword argument 'revision_hint'`

- [ ] **Step 3: Implement in `app/llm/provider.py`**

Change the `rewrite_resume` function from:

```python
def rewrite_resume(resume_text: str, jd_text: str, best_practice: str) -> dict:
    """Route resume rewriting to the configured REWRITE provider."""
    provider = os.getenv("LLM_REWRITE_PROVIDER", "claude").lower()
    if provider == "claude":
        return rewrite_resume_claude(resume_text, jd_text, best_practice)
    if provider == "deepseek":
        return rewrite_resume_deepseek(resume_text, jd_text, best_practice)
    raise NotImplementedError(
        f"REWRITE provider '{provider}' is not implemented. "
        "Set LLM_REWRITE_PROVIDER=claude or LLM_REWRITE_PROVIDER=deepseek."
    )
```

to:

```python
def rewrite_resume(resume_text: str, jd_text: str, best_practice: str, revision_hint: str = "") -> dict:
    """Route resume rewriting to the configured REWRITE provider."""
    provider = os.getenv("LLM_REWRITE_PROVIDER", "claude").lower()
    if provider == "claude":
        return rewrite_resume_claude(resume_text, jd_text, best_practice, revision_hint=revision_hint)
    if provider == "deepseek":
        return rewrite_resume_deepseek(resume_text, jd_text, best_practice, revision_hint=revision_hint)
    raise NotImplementedError(
        f"REWRITE provider '{provider}' is not implemented. "
        "Set LLM_REWRITE_PROVIDER=claude or LLM_REWRITE_PROVIDER=deepseek."
    )
```

- [ ] **Step 4: Update the two existing call-signature tests in `tests/test_provider.py`**

Find `test_rewrite_resume_routes_to_claude` and update its assertion from:

```python
    mock_fn.assert_called_once_with("resume", "jd", "best practice")
```

to:

```python
    mock_fn.assert_called_once_with("resume", "jd", "best practice", revision_hint="")
```

Find `test_rewrite_resume_routes_to_deepseek` and update its assertion from:

```python
    mock_fn.assert_called_once_with("resume", "jd", "best practice")
```

to:

```python
    mock_fn.assert_called_once_with("resume", "jd", "best practice", revision_hint="")
```

- [ ] **Step 5: Run all provider tests**

```
pytest tests/test_provider.py -v
```

Expected: all 9 tests PASS (7 existing + 2 new)

- [ ] **Step 6: Run full test suite**

```
pytest tests/ -v --tb=short
```

Expected: all 208 tests PASS

- [ ] **Step 7: Commit**

```bash
git add app/llm/provider.py tests/test_provider.py
git commit -m "[PHASE-05] add: revision_hint pass-through in provider.rewrite_resume"
```

---

### Task 4: Fix `3_Review.py` stub

**Files:**
- Modify: `app/ui/pages/3_Review.py` (the `col_revise` block, around line 289-296)

- [ ] **Step 1: Replace the stub**

Find this block in `app/ui/pages/3_Review.py`:

```python
            if st.button(f"↺ Request Revision ({revisions_remaining} left)"):
                subs_db.update_submission(submission.id, {
                    "revision_count": (submission.revision_count or 0) + 1,
                })
                subs_db.set_status(submission.id, SubmissionStatus.REVISION_REQUESTED)
                st.info("Revision requested. Revision flow will be available in Phase 5.")
                st.rerun()
```

Replace it with:

```python
            if st.button(f"↺ Request Revision ({revisions_remaining} left)"):
                subs_db.update_submission(submission.id, {
                    "revision_count": (submission.revision_count or 0) + 1,
                })
                subs_db.set_status(submission.id, SubmissionStatus.REVISION_REQUESTED)
                st.switch_page("pages/4_Revise.py")
```

- [ ] **Step 2: Verify existing review pipeline tests still pass**

```
pytest tests/test_review_pipeline.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add app/ui/pages/3_Review.py
git commit -m "[PHASE-05] fix: switch_page to 4_Revise.py on revision request"
```

---

### Task 5: Build `4_Revise.py` — tests first, then full page

**Files:**
- Create: `tests/test_revise_pipeline.py`
- Create: `app/ui/pages/4_Revise.py`

- [ ] **Step 1: Create `tests/test_revise_pipeline.py`**

```python
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
```

- [ ] **Step 2: Run to verify they fail (4_Revise.py not yet created)**

```
pytest tests/test_revise_pipeline.py -v
```

Expected: `FileNotFoundError` or `ModuleNotFoundError` — `4_Revise.py` does not exist yet

- [ ] **Step 3: Create `app/ui/pages/4_Revise.py`**

```python
"""
Phase 5 - Revision Request Page
Candidate provides a hint for what to change; pipeline re-runs with that hint.
"""
import dataclasses
import json
import logging
import os
from pathlib import Path

import streamlit as st

from app.best_practice.searcher import search_best_practice
from app.composer.pdf_writer import generate_resume_pdf
from app.llm.provider import rewrite_resume
from app.scoring import compute_ats_score
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionRecord, SubmissionStatus

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "data/output"))
MAX_REVISIONS = 3  # CLAUDE.md §3: revision cap per session


# ── Pipeline helper (testable, no st.* calls) ─────────────────────────────

def _run_revision_pipeline(
    submission: SubmissionRecord,
    subs_db: SubmissionsDB,
    output_dir: Path,
    revision_hint: str,
) -> None:
    """
    Re-run REWRITE pipeline with a candidate-supplied revision hint.
    Updates llm_output_json, ats_score_json, output_pdf_path, advances to REVIEW_READY.
    Raises on any failure — caller must catch and set ERROR status.
    """
    resume_fields = json.loads(submission.resume_fields_json or "{}")
    jd_fields = json.loads(submission.jd_fields_json or "{}")
    job_title = jd_fields.get("job_title", "")

    best_practice = search_best_practice(job_title)
    llm_output = rewrite_resume(
        submission.resume_raw_text or "",
        submission.jd_raw_text or "",
        best_practice,
        revision_hint=revision_hint,
    )

    ats = compute_ats_score(resume_fields, jd_fields)

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{submission.id}_resume.pdf"

    photo_bytes = None
    if submission.resume_photo_path and Path(submission.resume_photo_path).exists():
        photo_bytes = Path(submission.resume_photo_path).read_bytes()

    ok = generate_resume_pdf(llm_output, photo_bytes, pdf_path)
    if not ok:
        raise RuntimeError("PDF generation failed")

    subs_db.update_submission(submission.id, {
        "llm_output_json": json.dumps(llm_output),
        "ats_score_json": json.dumps(dataclasses.asdict(ats)),
        "output_pdf_path": str(pdf_path),
    })
    subs_db.set_status(submission.id, SubmissionStatus.REVIEW_READY)


# ── DB helpers ─────────────────────────────────────────────────────────────

def _get_auth_db() -> AuthDB:
    if "auth_db" not in st.session_state:
        st.session_state["auth_db"] = AuthDB(DB_PATH)
    return st.session_state["auth_db"]


def _get_subs_db() -> SubmissionsDB:
    if "subs_db" not in st.session_state:
        st.session_state["subs_db"] = SubmissionsDB(DB_PATH)
    return st.session_state["subs_db"]


def _require_auth():
    """Returns (user_id, token) or calls st.stop()."""
    token = st.session_state.get("auth_token")
    if not token:
        st.warning("Please sign in first.")
        st.stop()
        return None, None
    session = _get_auth_db().get_session(token)
    if session is None:
        st.warning("Session expired. Please sign in again.")
        for key in ("auth_token", "auth_email"):
            st.session_state.pop(key, None)
        st.stop()
        return None, None
    return session.user_id, token


def _render_draft(llm_output: dict) -> None:
    """Minimal read-only draft renderer for the expander."""
    name = llm_output.get("candidate_name", "")
    if name:
        st.markdown(f"### {name}")

    summary = llm_output.get("summary", "")
    if summary:
        st.markdown("**Summary**")
        st.write(summary)

    experience = llm_output.get("experience", [])
    if experience:
        st.markdown("**Experience**")
        for exp in experience:
            st.markdown(
                f"**{exp.get('title', '')}** — {exp.get('company', '')} | {exp.get('dates', '')}"
            )
            for bullet in exp.get("bullets", []):
                st.markdown(f"- {bullet}")

    skills = llm_output.get("skills", [])
    if skills:
        st.markdown("**Skills**")
        st.write(", ".join(skills))


# ── Page entry point ────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="JobOS - Revise", page_icon="↺")

    _user_id, _token = _require_auth()
    if not _token:
        return

    subs_db = _get_subs_db()

    sub_id = st.session_state.get("current_submission_id")
    if not sub_id:
        st.error("No active submission found. Please upload your resume first.")
        if st.button("Go to Upload"):
            st.switch_page("pages/1_Upload.py")
        return

    submission = subs_db.get_submission(int(sub_id))
    if submission is None:
        st.error(f"Submission #{sub_id} not found.")
        return

    # ── Belt-and-suspenders: only REVISION_REQUESTED may proceed ───────────
    if submission.status != SubmissionStatus.REVISION_REQUESTED.value:
        st.info(f"Submission status: **{submission.status}**. No revision pending.")
        if st.button("← Back to Review"):
            st.switch_page("pages/3_Review.py")
        return

    revisions_used = submission.revision_count or 0
    st.caption(f"Submission #{sub_id} | Revision {revisions_used} of {MAX_REVISIONS}")
    st.title("Request a Revision")

    # ── Current draft (collapsible) ─────────────────────────────────────────
    llm_output = json.loads(submission.llm_output_json or "{}")
    with st.expander("Current AI Draft", expanded=False):
        _render_draft(llm_output)

    # ── Revision form ───────────────────────────────────────────────────────
    with st.form("revision_form"):
        hint = st.text_area(
            "What would you like changed?",
            height=120,
            placeholder=(
                "e.g. Make the summary more concise. "
                "Emphasise leadership experience. Add AWS keywords."
            ),
        )
        submitted = st.form_submit_button("↺ Submit Revision")

    if submitted:
        if not hint.strip():
            st.warning("Please describe what you'd like changed before submitting.")
            st.stop()

        with st.spinner("Applying revision (~5-10s)..."):
            try:
                _run_revision_pipeline(submission, subs_db, OUTPUT_DIR, hint.strip())
            except Exception as e:
                logger.error(f"Revision pipeline failed for submission #{sub_id}: {e}")
                subs_db.update_submission(submission.id, {"error_message": str(e)})
                subs_db.set_status(submission.id, SubmissionStatus.ERROR)
                st.error(f"Revision failed: {e}")
                return

        st.switch_page("pages/3_Review.py")


main()
```

- [ ] **Step 4: Run the revise pipeline tests**

```
pytest tests/test_revise_pipeline.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Run full test suite**

```
pytest tests/ -v --tb=short
```

Expected: all 214 tests PASS (204 + 2 prompt + 2 provider hint + 6 revise pipeline; updated 2 provider tests stay in count)

- [ ] **Step 6: Commit**

```bash
git add app/ui/pages/4_Revise.py tests/test_revise_pipeline.py
git commit -m "[PHASE-05] add: 4_Revise.py page + _run_revision_pipeline helper"
```

---

### Task 6: Final verification + checkpoint commit

- [ ] **Step 1: Run full test suite one final time**

```
pytest tests/ -v --tb=short
```

Expected: 214 tests PASS, 0 failures, 0 errors

- [ ] **Step 2: Checkpoint commit**

```bash
git commit --allow-empty -m "[PHASE-05] checkpoint: revision request complete - 214 tests passing"
```

---

## Out of Scope

- Phase 6 (missing info panel in 4_Revise.py)
- Personalization / experience level / tone (Phase 8)
- Payment / download (Phase 10)

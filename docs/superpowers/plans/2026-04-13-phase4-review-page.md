# Phase 4: Resume Review Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the candidate-facing review page (`3_Review.py`) that triggers the LLM rewrite pipeline (PROCESSING → REVIEW_READY), displays ATS score, missing info panel, JD alignment, and AI-generated resume as structured text, with Accept / Request Revision / Back controls.

**Architecture:** On page load with status=PROCESSING, a helper function `_run_rewrite_pipeline` fetches best-practice text via DuckDuckGo, calls the provider-routed LLM rewrite, computes ATS score, generates a PDF, persists all outputs to DB, and advances status to REVIEW_READY. On REVIEW_READY, the page renders a two-column layout: scoring panel (left) + resume display with JD alignment (right) and action controls at the bottom. Provider routing (DeepSeek V3 for rewrite, Gemini Flash for extract) is implemented as new adapter functions in `finetuner.py` routed via `provider.py`.

**Tech Stack:** Python 3.13, Streamlit, SQLite (WAL), `openai` SDK (DeepSeek OpenAI-compat), `google-generativeai` SDK (Gemini), `reportlab`/`PyMuPDF` (PDF), `duckduckgo-search` (best practice), `dataclasses` (ATSScore/MissingItem)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app/state/models.py` | Modify | Add `llm_output_json`, `output_pdf_path` to `SubmissionRecord` |
| `app/state/db.py` | Modify | Add columns + migration guard + update `_SUBMISSION_UPDATE_COLUMNS` |
| `app/llm/finetuner.py` | Modify | Add `rewrite_resume_deepseek`, `extract_resume_fields_gemini`, `extract_jd_fields_gemini` |
| `app/llm/provider.py` | Modify | Add `rewrite_resume()` routing; wire gemini into extract routing |
| `app/ui/pages/3_Review.py` | Create | Full review page: auth guard, pipeline trigger, display, actions |
| `tests/test_state.py` | Modify | Add round-trip tests for new columns |
| `tests/test_llm.py` | Modify | Add tests for three new adapter functions |
| `tests/test_provider.py` | Modify | Replace gemini-raises stub test; add rewrite routing tests |
| `tests/test_review_pipeline.py` | Create | Tests for `_run_rewrite_pipeline` helper |

---

## Task 1: DB Schema + Model — Add `llm_output_json` and `output_pdf_path`

**Files:**
- Modify: `app/state/models.py`
- Modify: `app/state/db.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1.1 — Write the failing tests**

Append to `tests/test_state.py`:

```python
def test_submission_record_has_new_fields():
    """SubmissionRecord must accept llm_output_json and output_pdf_path."""
    rec = SubmissionRecord(
        id=1, user_id=2, session_token="tok",
        resume_raw_text=None, resume_fields_json=None, resume_photo_path=None,
        jd_raw_text=None, jd_fields_json=None, ats_score_json=None,
        llm_output_json='{"candidate_name":"Alice"}',
        output_pdf_path="/data/output/1_resume.pdf",
        status="PENDING", revision_count=0,
        error_message=None, created_at=None, updated_at=None,
    )
    assert rec.llm_output_json == '{"candidate_name":"Alice"}'
    assert rec.output_pdf_path == "/data/output/1_resume.pdf"


def test_submission_record_new_fields_default_none():
    """New fields must be Optional with None default so existing code still works."""
    rec = SubmissionRecord(
        id=1, user_id=2, session_token="tok",
        resume_raw_text=None, resume_fields_json=None, resume_photo_path=None,
        jd_raw_text=None, jd_fields_json=None, ats_score_json=None,
        status="PENDING", revision_count=0,
        error_message=None, created_at=None, updated_at=None,
    )
    assert rec.llm_output_json is None
    assert rec.output_pdf_path is None


def test_new_columns_round_trip(user_and_submissions_db):
    """llm_output_json and output_pdf_path must persist through update + fetch."""
    user_id, subs_db = user_and_submissions_db
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-newcols")
    llm_json = '{"candidate_name":"Bob","summary":"Great."}'
    pdf_path = "/data/output/42_resume.pdf"
    subs_db.update_submission(sub_id, {
        "llm_output_json": llm_json,
        "output_pdf_path": pdf_path,
    })
    rec = subs_db.get_submission(sub_id)
    assert rec.llm_output_json == llm_json
    assert rec.output_pdf_path == pdf_path


def test_update_submission_rejects_unknown_column(user_and_submissions_db):
    """update_submission must raise on unknown column names."""
    user_id, subs_db = user_and_submissions_db
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-bad")
    with pytest.raises(ValueError, match="unknown columns"):
        subs_db.update_submission(sub_id, {"nonexistent_col": "value"})
```

- [ ] **Step 1.2 — Run failing tests**

```bash
cd D:/staging/resume-builder-v2
python -m pytest tests/test_state.py::test_submission_record_has_new_fields tests/test_state.py::test_submission_record_new_fields_default_none tests/test_state.py::test_new_columns_round_trip tests/test_state.py::test_update_submission_rejects_unknown_column -v
```

Expected: `FAILED` (SubmissionRecord does not accept `llm_output_json`)

- [ ] **Step 1.3 — Update `app/state/models.py`**

Replace the `SubmissionRecord` dataclass (add two Optional fields with defaults at the end, before `status`; keep existing field order for backward compat with DB column order):

```python
@dataclass
class SubmissionRecord:
    id: Optional[int]
    user_id: int
    session_token: str
    resume_raw_text: Optional[str]
    resume_fields_json: Optional[str]
    resume_photo_path: Optional[str]
    jd_raw_text: Optional[str]
    jd_fields_json: Optional[str]
    ats_score_json: Optional[str]
    status: str
    revision_count: int
    error_message: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    llm_output_json: Optional[str] = None
    output_pdf_path: Optional[str] = None
```

- [ ] **Step 1.4 — Update `app/state/db.py`**

In `SubmissionsDB._init_db`, after the existing `ats_score_json` migration guard, add:

```python
if "llm_output_json" not in existing_cols:
    conn.execute("ALTER TABLE submissions ADD COLUMN llm_output_json TEXT")
if "output_pdf_path" not in existing_cols:
    conn.execute("ALTER TABLE submissions ADD COLUMN output_pdf_path TEXT")
```

Also update `_SUBMISSION_UPDATE_COLUMNS`:

```python
_SUBMISSION_UPDATE_COLUMNS = frozenset({
    "resume_raw_text", "resume_fields_json", "resume_photo_path",
    "jd_raw_text", "jd_fields_json", "ats_score_json",
    "llm_output_json", "output_pdf_path",
    "revision_count", "error_message",
})
```

- [ ] **Step 1.5 — Run failing tests again (expect pass)**

```bash
python -m pytest tests/test_state.py::test_submission_record_has_new_fields tests/test_state.py::test_submission_record_new_fields_default_none tests/test_state.py::test_new_columns_round_trip tests/test_state.py::test_update_submission_rejects_unknown_column -v
```

Expected: all 4 PASSED

- [ ] **Step 1.6 — Verify full suite still green**

```bash
python -m pytest tests/test_state.py -v
```

Expected: all existing tests PASS (new fields have defaults, so `test_submission_record_fields` still passes without providing them)

- [ ] **Step 1.7 — Commit**

```bash
git add app/state/models.py app/state/db.py tests/test_state.py
git commit -m "[PHASE-04] add: llm_output_json + output_pdf_path columns to SubmissionRecord + SubmissionsDB"
```

---

## Task 2: Gemini Flash Extract Adapters

**Files:**
- Modify: `app/llm/finetuner.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 2.1 — Write failing tests**

Append to `tests/test_llm.py`:

```python
# ── Gemini Flash extract adapters ───────────────────────────────────────────

from app.llm.finetuner import extract_resume_fields_gemini, extract_jd_fields_gemini


def _make_gemini_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


RESUME_FIELDS_JSON = '{"candidate_name":"Alice","email":"a@b.com","phone":"555","current_title":"Engineer","skills":["Python"],"experience_summary":"5 years"}'
JD_FIELDS_JSON = '{"job_title":"SWE","company":"ACME","required_skills":["Python"],"preferred_skills":[],"experience_required":"3y","education_required":"BS","key_responsibilities":["Build APIs"]}'


@patch("app.llm.finetuner.genai")
def test_extract_resume_fields_gemini_happy_path(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = _make_gemini_response(RESUME_FIELDS_JSON)

    result = extract_resume_fields_gemini("Alice resume text")

    mock_genai.configure.assert_called_once()
    assert result["candidate_name"] == "Alice"
    assert result["skills"] == ["Python"]


@patch("app.llm.finetuner.genai")
def test_extract_resume_fields_gemini_retry_then_pass(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.side_effect = [
        _make_gemini_response("not json"),
        _make_gemini_response(RESUME_FIELDS_JSON),
    ]

    result = extract_resume_fields_gemini("resume")
    assert result["candidate_name"] == "Alice"
    assert mock_model.generate_content.call_count == 2


@patch("app.llm.finetuner.genai")
def test_extract_resume_fields_gemini_raises_after_max_retries(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = _make_gemini_response("bad json always")

    with pytest.raises(ValueError, match="extract_resume_fields_gemini"):
        extract_resume_fields_gemini("resume")


@patch("app.llm.finetuner.genai")
def test_extract_jd_fields_gemini_happy_path(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = _make_gemini_response(JD_FIELDS_JSON)

    result = extract_jd_fields_gemini("SWE role at ACME")
    assert result["job_title"] == "SWE"
    assert "Python" in result["required_skills"]
```

- [ ] **Step 2.2 — Run failing tests**

```bash
python -m pytest tests/test_llm.py::test_extract_resume_fields_gemini_happy_path tests/test_llm.py::test_extract_resume_fields_gemini_retry_then_pass tests/test_llm.py::test_extract_resume_fields_gemini_raises_after_max_retries tests/test_llm.py::test_extract_jd_fields_gemini_happy_path -v
```

Expected: `FAILED` (cannot import `extract_resume_fields_gemini`)

- [ ] **Step 2.3 — Add Gemini adapters to `app/llm/finetuner.py`**

Add at the top of `finetuner.py` (after existing imports):

```python
import google.generativeai as genai
```

Add after the existing `extract_jd_fields_claude` function:

```python
def extract_resume_fields_gemini(resume_text: str) -> dict:
    """
    EXTRACT pass using Gemini Flash.
    Returns same schema as extract_resume_fields_claude.
    """
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.LLM_EXTRACT_MODEL)
    prompt = build_resume_fields_prompt(resume_text)

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = model.generate_content(prompt)
            return json.loads(_strip_markdown_fences(response.text))
        except json.JSONDecodeError as e:
            logger.warning(
                f"extract_resume_fields_gemini attempt {attempt}/{config.MAX_LLM_RETRIES} bad JSON: {e}"
            )
            if attempt == config.MAX_LLM_RETRIES:
                raise ValueError(
                    "Failed to obtain valid JSON from extract_resume_fields_gemini after max retries"
                )
        except Exception as e:
            logger.error(f"Unexpected error in extract_resume_fields_gemini: {e}")
            raise


def extract_jd_fields_gemini(jd_text: str) -> dict:
    """
    JD field extraction using Gemini Flash.
    Returns same schema as extract_jd_fields_claude.
    """
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.LLM_EXTRACT_MODEL)
    prompt = build_jd_extraction_prompt(jd_text)

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = model.generate_content(prompt)
            return json.loads(_strip_markdown_fences(response.text))
        except json.JSONDecodeError as e:
            logger.warning(
                f"extract_jd_fields_gemini attempt {attempt}/{config.MAX_LLM_RETRIES} bad JSON: {e}"
            )
            if attempt == config.MAX_LLM_RETRIES:
                raise ValueError(
                    "Failed to obtain valid JSON from extract_jd_fields_gemini after max retries"
                )
        except Exception as e:
            logger.error(f"Unexpected error in extract_jd_fields_gemini: {e}")
            raise
```

- [ ] **Step 2.4 — Run tests (expect pass)**

```bash
python -m pytest tests/test_llm.py::test_extract_resume_fields_gemini_happy_path tests/test_llm.py::test_extract_resume_fields_gemini_retry_then_pass tests/test_llm.py::test_extract_resume_fields_gemini_raises_after_max_retries tests/test_llm.py::test_extract_jd_fields_gemini_happy_path -v
```

Expected: 4 PASSED

- [ ] **Step 2.5 — Commit**

```bash
git add app/llm/finetuner.py tests/test_llm.py
git commit -m "[PHASE-04] add: Gemini Flash extract adapters (extract_resume_fields_gemini, extract_jd_fields_gemini)"
```

---

## Task 3: DeepSeek V3 Rewrite Adapter

**Files:**
- Modify: `app/llm/finetuner.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 3.1 — Write failing test**

Append to `tests/test_llm.py`:

```python
# ── DeepSeek V3 rewrite adapter ─────────────────────────────────────────────

from app.llm.finetuner import rewrite_resume_deepseek

DEEPSEEK_REWRITE_JSON = json.dumps({
    "candidate_name": "Alice",
    "contact": {"email": "a@b.com", "phone": "555", "linkedin": ""},
    "summary": "Strong engineer.",
    "experience": [],
    "education": [],
    "skills": ["Python"],
    "missing_fields": [],
})


def _make_deepseek_response(text: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = text
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@patch("app.llm.finetuner._get_client")
@patch("app.llm.finetuner.OpenAI")
def test_rewrite_resume_deepseek_happy_path(mock_openai_cls, mock_get_client):
    mock_ds_client = MagicMock()
    mock_openai_cls.return_value = mock_ds_client
    # extract_fields (Claude) still called first to get candidate name
    mock_get_client.return_value.messages.create.return_value = _make_message(EXTRACT_JSON)
    mock_ds_client.chat.completions.create.return_value = _make_deepseek_response(DEEPSEEK_REWRITE_JSON)

    result = rewrite_resume_deepseek("Alice resume", "SWE JD", "best practice")

    assert result["candidate_name"] == "Alice"
    assert result["summary"] == "Strong engineer."
    mock_ds_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_ds_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "deepseek-chat"


@patch("app.llm.finetuner._get_client")
@patch("app.llm.finetuner.OpenAI")
def test_rewrite_resume_deepseek_retry_then_pass(mock_openai_cls, mock_get_client):
    mock_ds_client = MagicMock()
    mock_openai_cls.return_value = mock_ds_client
    mock_get_client.return_value.messages.create.return_value = _make_message(EXTRACT_JSON)
    mock_ds_client.chat.completions.create.side_effect = [
        _make_deepseek_response("bad json"),
        _make_deepseek_response(DEEPSEEK_REWRITE_JSON),
    ]

    result = rewrite_resume_deepseek("resume", "jd", "bp")
    assert result["candidate_name"] == "Alice"
    assert mock_ds_client.chat.completions.create.call_count == 2


@patch("app.llm.finetuner._get_client")
@patch("app.llm.finetuner.OpenAI")
def test_rewrite_resume_deepseek_raises_after_max_retries(mock_openai_cls, mock_get_client):
    mock_ds_client = MagicMock()
    mock_openai_cls.return_value = mock_ds_client
    mock_get_client.return_value.messages.create.return_value = _make_message(EXTRACT_JSON)
    mock_ds_client.chat.completions.create.return_value = _make_deepseek_response("not json")

    with pytest.raises(ValueError, match="rewrite_resume_deepseek"):
        rewrite_resume_deepseek("resume", "jd", "bp")
```

- [ ] **Step 3.2 — Run failing tests**

```bash
python -m pytest tests/test_llm.py::test_rewrite_resume_deepseek_happy_path tests/test_llm.py::test_rewrite_resume_deepseek_retry_then_pass tests/test_llm.py::test_rewrite_resume_deepseek_raises_after_max_retries -v
```

Expected: `FAILED` (cannot import `rewrite_resume_deepseek`)

- [ ] **Step 3.3 — Add DeepSeek adapter to `app/llm/finetuner.py`**

Add at the top of `finetuner.py` (after existing imports):

```python
from openai import OpenAI
```

Add after `extract_jd_fields_gemini`:

```python
def rewrite_resume_deepseek(resume_text: str, jd_text: str, best_practice: str) -> dict:
    """
    REWRITE pass using DeepSeek V3 (OpenAI-compatible API).
    Same prompt schema and output format as rewrite_resume (Claude).
    Calls extract_fields (Claude Haiku) first to get candidate name.
    """
    fields = extract_fields(resume_text)
    candidate_name = fields.get("candidate_name") or "Unknown"
    prompt = build_finetuning_prompt(resume_text, jd_text, best_practice, candidate_name)

    ds_client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = ds_client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=4096,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert resume writer. "
                            "Respond ONLY with valid JSON matching the specified schema. "
                            "No markdown, no explanation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return json.loads(_strip_markdown_fences(response.choices[0].message.content))
        except json.JSONDecodeError as e:
            logger.warning(
                f"rewrite_resume_deepseek attempt {attempt}/{config.MAX_LLM_RETRIES} bad JSON: {e}"
            )
            if attempt == config.MAX_LLM_RETRIES:
                raise ValueError(
                    "Failed to obtain valid JSON from rewrite_resume_deepseek after max retries"
                )
        except Exception as e:
            logger.error(f"Unexpected error in rewrite_resume_deepseek: {e}")
            raise
```

- [ ] **Step 3.4 — Run tests (expect pass)**

```bash
python -m pytest tests/test_llm.py::test_rewrite_resume_deepseek_happy_path tests/test_llm.py::test_rewrite_resume_deepseek_retry_then_pass tests/test_llm.py::test_rewrite_resume_deepseek_raises_after_max_retries -v
```

Expected: 3 PASSED

- [ ] **Step 3.5 — Full test_llm.py green**

```bash
python -m pytest tests/test_llm.py -v
```

Expected: all PASSED

- [ ] **Step 3.6 — Commit**

```bash
git add app/llm/finetuner.py tests/test_llm.py
git commit -m "[PHASE-04] add: DeepSeek V3 rewrite adapter (rewrite_resume_deepseek)"
```

---

## Task 4: Provider Routing — `rewrite_resume` + Gemini Extract Wiring

**Files:**
- Modify: `app/llm/provider.py`
- Modify: `tests/test_provider.py`

- [ ] **Step 4.1 — Update `tests/test_provider.py`**

Replace the file entirely with the following (adds new tests; removes the now-incorrect gemini-raises test; keeps all existing Claude tests):

```python
import pytest
from unittest.mock import patch


# ── Extract routing (Claude) ─────────────────────────────────────────────────

def test_extract_resume_fields_routes_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "claude")
    expected = {"candidate_name": "Alice", "email": "", "phone": "",
                "current_title": "Engineer", "skills": ["Python"], "experience_summary": ""}
    with patch("app.llm.provider.extract_resume_fields_claude", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.extract_resume_fields("Alice resume")
    mock_fn.assert_called_once_with("Alice resume")
    assert result["candidate_name"] == "Alice"


def test_extract_jd_fields_routes_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "claude")
    expected = {"job_title": "SWE", "company": "", "required_skills": ["Python"],
                "preferred_skills": [], "experience_required": "", "education_required": "",
                "key_responsibilities": []}
    with patch("app.llm.provider.extract_jd_fields_claude", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.extract_jd_fields("Python SWE role")
    mock_fn.assert_called_once_with("Python SWE role")
    assert result["job_title"] == "SWE"


# ── Extract routing (Gemini) ─────────────────────────────────────────────────

def test_extract_resume_fields_routes_to_gemini(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "gemini")
    expected = {"candidate_name": "Bob", "email": "", "phone": "",
                "current_title": "PM", "skills": [], "experience_summary": ""}
    with patch("app.llm.provider.extract_resume_fields_gemini", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.extract_resume_fields("Bob resume")
    mock_fn.assert_called_once_with("Bob resume")
    assert result["candidate_name"] == "Bob"


def test_extract_jd_fields_routes_to_gemini(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "gemini")
    expected = {"job_title": "PM", "company": "Corp", "required_skills": [],
                "preferred_skills": [], "experience_required": "", "education_required": "",
                "key_responsibilities": []}
    with patch("app.llm.provider.extract_jd_fields_gemini", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.extract_jd_fields("PM role at Corp")
    mock_fn.assert_called_once_with("PM role at Corp")
    assert result["job_title"] == "PM"


def test_extract_resume_fields_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "unknown_provider")
    import app.llm.provider as prov
    with pytest.raises(NotImplementedError):
        prov.extract_resume_fields("any text")


def test_extract_jd_fields_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "unknown_provider")
    import app.llm.provider as prov
    with pytest.raises(NotImplementedError):
        prov.extract_jd_fields("any jd")


# ── Rewrite routing ──────────────────────────────────────────────────────────

def test_rewrite_resume_routes_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_REWRITE_PROVIDER", "claude")
    expected = {"candidate_name": "Alice", "summary": "Good."}
    with patch("app.llm.provider.rewrite_resume_claude", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.rewrite_resume("resume", "jd", "best practice")
    mock_fn.assert_called_once_with("resume", "jd", "best practice")
    assert result["summary"] == "Good."


def test_rewrite_resume_routes_to_deepseek(monkeypatch):
    monkeypatch.setenv("LLM_REWRITE_PROVIDER", "deepseek")
    expected = {"candidate_name": "Bob", "summary": "Expert."}
    with patch("app.llm.provider.rewrite_resume_deepseek", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.rewrite_resume("resume", "jd", "best practice")
    mock_fn.assert_called_once_with("resume", "jd", "best practice")
    assert result["summary"] == "Expert."


def test_rewrite_resume_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_REWRITE_PROVIDER", "unknown_llm")
    import app.llm.provider as prov
    with pytest.raises(NotImplementedError, match="unknown_llm"):
        prov.rewrite_resume("resume", "jd", "bp")
```

- [ ] **Step 4.2 — Run failing tests**

```bash
python -m pytest tests/test_provider.py -v
```

Expected: several FAILED (gemini routing and rewrite routing not implemented; also `rewrite_resume_claude` not defined in provider)

- [ ] **Step 4.3 — Update `app/llm/provider.py`**

Replace the entire file:

```python
"""
Provider routing layer for LLM calls.

EXTRACT provider: set LLM_EXTRACT_PROVIDER env var
  claude   → Claude Haiku  (extract_resume_fields_claude / extract_jd_fields_claude)
  gemini   → Gemini Flash  (extract_resume_fields_gemini / extract_jd_fields_gemini)

REWRITE provider: set LLM_REWRITE_PROVIDER env var
  claude   → Claude Sonnet (rewrite_resume in finetuner)
  deepseek → DeepSeek V3   (rewrite_resume_deepseek in finetuner)
"""
import logging
import os

from app.llm.finetuner import (
    extract_resume_fields_claude,
    extract_jd_fields_claude,
    extract_resume_fields_gemini,
    extract_jd_fields_gemini,
    rewrite_resume as rewrite_resume_claude,
    rewrite_resume_deepseek,
)

logger = logging.getLogger(__name__)


def extract_resume_fields(resume_text: str) -> dict:
    """Route resume field extraction to the configured EXTRACT provider."""
    provider = os.getenv("LLM_EXTRACT_PROVIDER", "claude").lower()
    if provider == "claude":
        return extract_resume_fields_claude(resume_text)
    if provider == "gemini":
        return extract_resume_fields_gemini(resume_text)
    raise NotImplementedError(
        f"EXTRACT provider '{provider}' is not implemented. "
        "Set LLM_EXTRACT_PROVIDER=claude or LLM_EXTRACT_PROVIDER=gemini."
    )


def extract_jd_fields(jd_text: str) -> dict:
    """Route JD field extraction to the configured EXTRACT provider."""
    provider = os.getenv("LLM_EXTRACT_PROVIDER", "claude").lower()
    if provider == "claude":
        return extract_jd_fields_claude(jd_text)
    if provider == "gemini":
        return extract_jd_fields_gemini(jd_text)
    raise NotImplementedError(
        f"EXTRACT provider '{provider}' is not implemented. "
        "Set LLM_EXTRACT_PROVIDER=claude or LLM_EXTRACT_PROVIDER=gemini."
    )


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

- [ ] **Step 4.4 — Run tests (expect pass)**

```bash
python -m pytest tests/test_provider.py -v
```

Expected: all PASSED

- [ ] **Step 4.5 — Commit**

```bash
git add app/llm/provider.py tests/test_provider.py
git commit -m "[PHASE-04] add: rewrite_resume routing + gemini extract wiring in provider.py"
```

---

## Task 5: `_run_rewrite_pipeline` Helper + Tests

**Files:**
- Create: `app/ui/pages/3_Review.py` (stub with helper only)
- Create: `tests/test_review_pipeline.py`

- [ ] **Step 5.1 — Write failing tests**

Create `tests/test_review_pipeline.py`:

```python
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
from unittest.mock import MagicMock, patch, call

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
    ats_val = MagicMock(total=75, keyword_match=20, skills_coverage=22,
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
    ats_val = MagicMock(total=80, keyword_match=25, skills_coverage=25,
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
    ats_val = MagicMock(total=70, keyword_match=20, skills_coverage=20,
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
    mock_ats_val = MagicMock(total=70, keyword_match=20, skills_coverage=20,
                              experience_clarity=15, structure_completeness=15,
                              keyword_matched=[], skills_matched=[], skills_missing=[])
    from unittest.mock import patch as _patch
    with _patch.object(_review_mod, "search_best_practice", return_value="Generic best practice") as mock_bp, \
         _patch.object(_review_mod, "rewrite_resume", return_value=LLM_OUTPUT) as mock_rewrite, \
         _patch.object(_review_mod, "compute_ats_score", return_value=mock_ats_val), \
         _patch.object(_review_mod, "generate_resume_pdf", return_value=True):
        _run_rewrite_pipeline(submission, subs_db, output_dir)

    mock_bp.assert_called_once_with("Senior Engineer")
    mock_rewrite.assert_called_once_with(
        submission.resume_raw_text,
        submission.jd_raw_text,
        "Generic best practice",
    )
```

- [ ] **Step 5.2 — Run failing tests**

```bash
python -m pytest tests/test_review_pipeline.py -v
```

Expected: `ERROR` (3_Review.py does not exist yet)

- [ ] **Step 5.3 — Create `app/ui/pages/3_Review.py` with helper only**

Create the file with just the imports and `_run_rewrite_pipeline` (main() is a stub for now):

```python
"""
Phase 4 - Review Page
Candidate-facing review: ATS score, missing info, AI-generated resume, accept/revise controls.
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
from app.scoring import compute_ats_score, detect_missing
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionRecord, SubmissionStatus

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "data/output"))


# ── Pipeline helper (testable, no st.* calls) ─────────────────────────────

def _run_rewrite_pipeline(
    submission: SubmissionRecord,
    subs_db: SubmissionsDB,
    output_dir: Path,
) -> None:
    """
    Run PROCESSING → REVIEW_READY pipeline.
    Fetches best practice, calls LLM rewrite, scores, generates PDF,
    persists all outputs to DB, advances status.
    Raises on any failure — caller must catch and set ERROR status.
    """
    resume_fields = json.loads(submission.resume_fields_json or "{}")
    jd_fields = json.loads(submission.jd_fields_json or "{}")
    job_title = jd_fields.get("job_title", "")

    best_practice = search_best_practice(job_title)
    llm_output = rewrite_resume(submission.resume_raw_text or "", submission.jd_raw_text or "", best_practice)

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


# ── Page entry point ────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="JobOS - Review", page_icon="📄")
    st.title("Review Your AI-Tuned Resume")
    st.info("Review page coming soon.")


main()
```

- [ ] **Step 5.4 — Run tests (expect pass)**

```bash
python -m pytest tests/test_review_pipeline.py -v
```

Expected: all 5 PASSED

- [ ] **Step 5.5 — Commit**

```bash
git add app/ui/pages/3_Review.py tests/test_review_pipeline.py
git commit -m "[PHASE-04] add: _run_rewrite_pipeline helper + tests (pipeline stub, full review page next)"
```

---

## Task 6: Full `3_Review.py` Page

**Files:**
- Modify: `app/ui/pages/3_Review.py`

Replace the stub `main()` with the complete implementation. The `_run_rewrite_pipeline` function and imports at the top stay unchanged.

- [ ] **Step 6.1 — Replace `main()` in `app/ui/pages/3_Review.py`**

Replace only the `main()` function and the final `main()` call at the bottom:

```python
def _get_auth_db() -> AuthDB:
    if "auth_db" not in st.session_state:
        st.session_state["auth_db"] = AuthDB(DB_PATH)
    return st.session_state["auth_db"]


def _get_subs_db() -> SubmissionsDB:
    if "subs_db" not in st.session_state:
        st.session_state["subs_db"] = SubmissionsDB(DB_PATH)
    return st.session_state["subs_db"]


def _require_auth():
    """Returns (user_id, token) or stops the page."""
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


def _render_ats_panel(ats_dict: dict) -> None:
    """Render ATS score breakdown in the left column."""
    total = ats_dict.get("total", 0)
    st.metric("ATS Score", f"{total} / 100")
    st.progress(
        min(ats_dict.get("keyword_match", 0) / 30, 1.0),
        text=f"Keyword Match: {ats_dict.get('keyword_match', 0)}/30",
    )
    st.progress(
        min(ats_dict.get("skills_coverage", 0) / 30, 1.0),
        text=f"Skills Coverage: {ats_dict.get('skills_coverage', 0)}/30",
    )
    st.progress(
        min(ats_dict.get("experience_clarity", 0) / 20, 1.0),
        text=f"Experience Clarity: {ats_dict.get('experience_clarity', 0)}/20",
    )
    st.progress(
        min(ats_dict.get("structure_completeness", 0) / 20, 1.0),
        text=f"Structure: {ats_dict.get('structure_completeness', 0)}/20",
    )


def _render_missing_panel(resume_fields: dict) -> None:
    """Render missing info panel (severity ranked) below ATS score."""
    missing_items = detect_missing(resume_fields)
    if not missing_items:
        st.success("No critical missing information detected.")
        return
    st.subheader("Missing Info")
    for item in missing_items:
        badge = "🔴" if item.severity == "HIGH" else ("🟡" if item.severity == "MEDIUM" else "⚪")
        st.markdown(f"{badge} **{item.label}** — {item.hint}")


def _render_jd_alignment(llm_output: dict, jd_fields: dict) -> None:
    """Show which required JD skills appear in the AI resume."""
    required = jd_fields.get("required_skills", [])
    preferred = jd_fields.get("preferred_skills", [])
    resume_skills_lower = {s.lower() for s in llm_output.get("skills", [])}

    if not required and not preferred:
        return

    st.subheader("JD Alignment")
    all_skills = [(s, "Required") for s in required] + [(s, "Preferred") for s in preferred]
    matched = [s for s, _ in all_skills if s.lower() in resume_skills_lower]
    unmatched = [s for s, _ in all_skills if s.lower() not in resume_skills_lower]

    if matched:
        st.markdown("**Matched:** " + " ".join(f"`{s}`" for s in matched))
    if unmatched:
        st.markdown("**Missing from resume:** " + " ".join(f"`{s}`" for s in unmatched))


def _render_resume_text(llm_output: dict) -> None:
    """Render AI-generated resume as structured read-only text."""
    st.subheader("AI-Generated Resume")

    name = llm_output.get("candidate_name", "")
    contact = llm_output.get("contact", {})
    if name:
        st.markdown(f"### {name}")
    contact_parts = [
        v for v in [contact.get("email"), contact.get("phone"), contact.get("linkedin")]
        if v
    ]
    if contact_parts:
        st.caption(" | ".join(contact_parts))

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

    education = llm_output.get("education", [])
    if education:
        st.markdown("**Education**")
        for edu in education:
            st.markdown(
                f"{edu.get('degree', '')}, {edu.get('institution', '')} ({edu.get('year', '')})"
            )

    skills = llm_output.get("skills", [])
    if skills:
        st.markdown("**Skills**")
        st.write(", ".join(skills))


def main():
    st.set_page_config(page_title="JobOS - Review", page_icon="📄")

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

    status = submission.status

    # ── PROCESSING: run pipeline ────────────────────────────────────────────
    if status == SubmissionStatus.PROCESSING.value:
        with st.spinner("Generating your AI-tuned resume (~5-10s)..."):
            try:
                _run_rewrite_pipeline(submission, subs_db, OUTPUT_DIR)
            except Exception as e:
                logger.error(f"Pipeline failed for submission #{sub_id}: {e}")
                subs_db.update_submission(submission.id, {"error_message": str(e)})
                subs_db.set_status(submission.id, SubmissionStatus.ERROR)
                st.error(f"Failed to generate resume: {e}")
                return
        st.rerun()

    # ── Status guard ────────────────────────────────────────────────────────
    _REVIEWABLE = {SubmissionStatus.REVIEW_READY.value, SubmissionStatus.REVISION_REQUESTED.value}
    if status not in _REVIEWABLE:
        st.info(f"Submission status: **{status}**. Nothing to review yet.")
        if st.button("← Back to Upload"):
            st.switch_page("pages/1_Upload.py")
        return

    # ── Load persisted data ─────────────────────────────────────────────────
    llm_output = json.loads(submission.llm_output_json or "{}")
    ats_dict = json.loads(submission.ats_score_json or "{}")
    resume_fields = json.loads(submission.resume_fields_json or "{}")
    jd_fields = json.loads(submission.jd_fields_json or "{}")

    st.caption(f"Submission #{sub_id} | Status: {status}")

    # ── Two-column layout ───────────────────────────────────────────────────
    col_left, col_right = st.columns([2, 3])

    with col_left:
        _render_ats_panel(ats_dict)
        st.divider()
        _render_missing_panel(resume_fields)

    with col_right:
        _render_jd_alignment(llm_output, jd_fields)
        st.divider()
        _render_resume_text(llm_output)

        # PDF download button
        pdf_path = submission.output_pdf_path
        if pdf_path and Path(pdf_path).exists():
            pdf_bytes = Path(pdf_path).read_bytes()
            st.download_button(
                label="⬇ Download PDF",
                data=pdf_bytes,
                file_name=f"resume_{sub_id}.pdf",
                mime="application/pdf",
            )
        else:
            st.caption("PDF not available for download.")

    # ── Action bar ─────────────────────────────────────────────────────────
    st.divider()
    revisions_remaining = 3 - (submission.revision_count or 0)
    col_back, col_revise, col_accept = st.columns([1, 2, 1])

    with col_back:
        if st.button("← Back"):
            st.switch_page("pages/1_Upload.py")

    with col_revise:
        if revisions_remaining > 0:
            if st.button(f"↺ Request Revision ({revisions_remaining} left)"):
                subs_db.update_submission(submission.id, {
                    "revision_count": (submission.revision_count or 0) + 1,
                })
                subs_db.set_status(submission.id, SubmissionStatus.REVISION_REQUESTED)
                st.info("Revision requested. Revision flow will be available in Phase 5.")
                st.rerun()
        else:
            st.caption("No revisions remaining (max 3 used).")

    with col_accept:
        if st.button("✓ Accept Draft", type="primary"):
            subs_db.set_status(submission.id, SubmissionStatus.ACCEPTED)
            st.success("Draft accepted! Payment and download will be available in Phase 10.")
            st.rerun()


main()
```

- [ ] **Step 6.2 — Verify pipeline tests still pass after full main() is added**

```bash
python -m pytest tests/test_review_pipeline.py -v
```

Expected: all 5 PASSED (the `_run_rewrite_pipeline` function is unchanged)

- [ ] **Step 6.3 — Run full test suite**

```bash
python -m pytest -v 2>&1 | tail -20
```

Expected: 183+ tests PASSED, 0 FAILED

- [ ] **Step 6.4 — Commit**

```bash
git add app/ui/pages/3_Review.py
git commit -m "[PHASE-04] add: full 3_Review.py page (ATS panel, missing info, resume display, accept/revise)"
```

---

## Task 7: Full Test Run + Spec Compliance

- [ ] **Step 7.1 — Run complete test suite**

```bash
python -m pytest -v --tb=short 2>&1 | tee /tmp/phase4_test_output.txt
```

Expected: green on all tests. Count must be ≥ 183 (existing baseline). If anything fails, fix before proceeding.

- [ ] **Step 7.2 — Spec compliance checklist**

Verify each item manually:

```
[ ] Module boundary (CLAUDE.md §4): only files in approved scope modified
    → app/state/models.py, app/state/db.py, app/llm/finetuner.py,
      app/llm/provider.py, app/ui/pages/3_Review.py — all approved
[ ] v1 preserved modules untouched (CLAUDE.md §9):
    → app/composer/, app/ingestor/, app/best_practice/, app/email_handler/ — NOT touched
[ ] Critical Rules (CLAUDE.md §3):
    → No hardcoded API keys — all via config.* / os.getenv ✓
    → No auto-email send ✓
    → WAL mode: SubmissionsDB already sets WAL in _init_db ✓
    → ATS score in-process (no LLM): compute_ats_score called directly ✓
[ ] LLM providers via env var only:
    → deepseek-chat is hardcoded in rewrite_resume_deepseek — acceptable
      (model name is internal to DeepSeek, not a user-facing model string)
      Alternatively: read from os.getenv("DEEPSEEK_REWRITE_MODEL", "deepseek-chat")
      Apply this fix if strict env-var discipline is required.
[ ] Status machine (CLAUDE.md §6):
    → PROCESSING → REVIEW_READY ✓
    → REVIEW_READY → REVISION_REQUESTED ✓
    → REVIEW_READY → ACCEPTED ✓
[ ] Revision cap enforced:
    → revisions_remaining = 3 - revision_count; button hidden when 0 ✓
[ ] Git format (CLAUDE.md §8): [PHASE-04] prefix used in all commits ✓
```

- [ ] **Step 7.3 — Fix strict env-var model name (if required by §3 check above)**

If you decide to make `deepseek-chat` configurable via env var, in `app/llm/finetuner.py` inside `rewrite_resume_deepseek`, change:

```python
model="deepseek-chat",
```
to:
```python
model=os.getenv("DEEPSEEK_REWRITE_MODEL", "deepseek-chat"),
```

Add `import os` at the top of finetuner.py if not already present (it already imports `os` via `config`, so check). Then run tests again to confirm nothing breaks.

- [ ] **Step 7.4 — Final commit if Step 7.3 was applied**

```bash
git add app/llm/finetuner.py
git commit -m "[PHASE-04] fix: read deepseek model name from DEEPSEEK_REWRITE_MODEL env var"
```

---

## Completion Checklist (CLAUDE.md §STEP A-F)

After all tasks above pass:

- [ ] Run `python -m pytest -v` → show full output (STEP A)
- [ ] Walk through spec compliance table above (STEP B)
- [ ] Invoke `superpowers:requesting-code-review` with pytest output + spec (STEP C)
- [ ] Produce walkthrough diff `git diff --staged` or `git log --oneline` (STEP D)
- [ ] STOP and wait for commit approval (STEP E)
- [ ] `git add <specific files>` + `git commit` + `git push` (STEP F)

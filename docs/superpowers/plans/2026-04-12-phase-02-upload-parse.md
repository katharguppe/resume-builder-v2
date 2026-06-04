# Phase 2: Resume + JD Upload + Parse

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow authenticated users to upload a resume (PDF/DOC/DOCX) and a job description (paste or upload), extract structured fields from both using the LLM EXTRACT provider, and persist everything to SQLite linked to the user session.

**Architecture:** A new `SubmissionsDB` class is added to `app/state/db.py`. A new `app/llm/provider.py` routes extract calls by env var (`LLM_EXTRACT_PROVIDER`); only the Claude adapter is wired up now — Gemini is a stub. `app/ingestor/jd_extractor.py` is a thin ingestor-layer wrapper that delegates to provider. The Streamlit Upload page (`app/ui/pages/1_Upload.py`) gates on auth, collects files + JD text, calls extractors, and stores the submission record.

**Tech Stack:** Python 3.13, SQLite WAL, pdfplumber, PyMuPDF/fitz, LibreOffice (Docker), Streamlit, Anthropic SDK (Claude Haiku), python-dotenv

---

## Prerequisite: Phase 1 Must Be Available

Phase 2 depends on `AuthDB`, `app/auth/`, and `app/ui/pages/0_Login.py` from Phase 1. These are on branch `feature/phase-01-auth` but **not yet merged to master**.

**Before starting Phase 2, choose one:**
- Option A: Merge `feature/phase-01-auth` into `master`, then branch from master
- Option B: Branch `feature/phase-02-upload-parse` directly from `feature/phase-01-auth`

Option B avoids blocking on a PR review. The plan assumes Option B.

---

## Open Scope Decision — Resolved

**Q: Does Phase 2 include the LLM `extract_fields` call, or stop at raw text?**

**Answer: YES — Phase 2 calls the LLM.** The task spec says "Store parsed resume_fields + jd_fields in DB linked to user session." "Parsed" means structured JSON, not raw text. Downstream phases (Phase 3 ATS scoring) read these fields directly.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/state/models.py` | Modify | Add `SubmissionStatus` enum (v2 statuses) + `SubmissionRecord` dataclass |
| `app/state/db.py` | Modify | Add `SubmissionsDB` class — submissions table + CRUD |
| `app/config.py` | Modify | Add `LLM_EXTRACT_PROVIDER`, `LLM_REWRITE_PROVIDER`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY` |
| `app/llm/prompt_builder.py` | Modify | Add `build_jd_extraction_prompt()` + `build_resume_fields_prompt()` |
| `app/llm/finetuner.py` | Modify | Add `extract_resume_fields_claude()` + `extract_jd_fields_claude()` |
| `app/llm/provider.py` | Create | Provider routing: `extract_resume_fields()` + `extract_jd_fields()` (Claude only; Gemini stub) |
| `app/ingestor/jd_extractor.py` | Create | `extract_jd_fields(jd_text)` — thin wrapper over `provider.extract_jd_fields()` |
| `app/ui/pages/1_Upload.py` | Create | Streamlit upload page: auth gate, resume + JD inputs, extract + store |
| `tests/test_state.py` | Modify | Add `SubmissionsDB` CRUD tests |
| `tests/test_provider.py` | Create | Provider routing + Claude adapter tests (mocked Anthropic client) |
| `tests/test_ingestor.py` | Modify | Add `jd_extractor.extract_jd_fields()` tests (mocked provider) |

---

## DB Schema

```sql
-- One submission per upload session; linked to authenticated user
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token TEXT NOT NULL,
    resume_raw_text TEXT,
    resume_fields_json TEXT,      -- JSON: candidate_name, email, phone, current_title, skills, experience_summary
    resume_photo_path TEXT,       -- relative path: data/photos/{uuid}.jpg or NULL
    jd_raw_text TEXT,
    jd_fields_json TEXT,          -- JSON: job_title, company, required_skills, preferred_skills, experience_required, education_required, key_responsibilities
    status TEXT NOT NULL DEFAULT 'PENDING',
    revision_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## Task 1: Branch Setup

**Files:** none (git ops only)

- [ ] **Step 1: Create branch from Phase 1**

```bash
git checkout feature/phase-01-auth
git pull origin feature/phase-01-auth
git checkout -b feature/phase-02-upload-parse
```

- [ ] **Step 2: Verify baseline tests pass**

```bash
pytest -v --tb=short
```

Expected: 107 tests passing (Phase 1 baseline). If any fail, stop and fix before proceeding.

- [ ] **Step 3: Create photo storage directory**

```bash
mkdir -p data/photos
echo "# Resume headshot photos extracted from uploaded PDFs" > data/photos/.gitkeep
```

---

## Task 2: DB Models — SubmissionStatus + SubmissionRecord

**Files:**
- Modify: `app/state/models.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Write failing test for SubmissionStatus**

Add to `tests/test_state.py`:

```python
from app.state.models import SubmissionStatus, SubmissionRecord

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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_state.py::test_submission_status_values tests/test_state.py::test_submission_record_fields -v
```

Expected: FAIL — `SubmissionStatus` and `SubmissionRecord` not yet defined.

- [ ] **Step 3: Add SubmissionStatus + SubmissionRecord to models.py**

Append to `app/state/models.py` (after the existing dataclasses):

```python
class SubmissionStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    REVIEW_READY = "REVIEW_READY"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    REVISION_EXHAUSTED = "REVISION_EXHAUSTED"
    ACCEPTED = "ACCEPTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    DOWNLOAD_READY = "DOWNLOAD_READY"
    DOWNLOADED = "DOWNLOADED"
    ERROR = "ERROR"


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
    status: str
    revision_count: int
    error_message: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_state.py::test_submission_status_values tests/test_state.py::test_submission_record_fields -v
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/state/models.py tests/test_state.py
git commit -m "[PHASE-02] add: SubmissionStatus enum + SubmissionRecord dataclass"
```

---

## Task 3: SubmissionsDB Class

**Files:**
- Modify: `app/state/db.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Write failing tests for SubmissionsDB**

Add to `tests/test_state.py`:

```python
import pytest
from pathlib import Path
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionStatus


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_state.py::test_create_submission tests/test_state.py::test_get_submission -v
```

Expected: FAIL — `SubmissionsDB` not defined.

- [ ] **Step 3: Add SubmissionsDB to app/state/db.py**

First, update the import line at the top of `app/state/db.py`:

```python
from .models import (
    CandidateStatus, CandidateRecord, ConfigRecord,
    SubmissionStatus, SubmissionRecord,
)
```

Then append at the end of the file:

```python
class SubmissionsDB(_SqliteDB):
    """Stores resume+JD submissions per authenticated user session."""

    def __init__(self, db_path: Path):
        super().__init__(db_path)
        self._init_db()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT NOT NULL,
                    resume_raw_text TEXT,
                    resume_fields_json TEXT,
                    resume_photo_path TEXT,
                    jd_raw_text TEXT,
                    jd_fields_json TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    revision_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def create_submission(self, user_id: int, session_token: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO submissions (user_id, session_token, status)
                   VALUES (?, ?, ?)""",
                (user_id, session_token, SubmissionStatus.PENDING.value),
            )
            conn.commit()
            return cursor.lastrowid

    def get_submission(self, submission_id: int) -> Optional[SubmissionRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return SubmissionRecord(**dict(row))

    def update_submission(self, submission_id: int, updates: Dict[str, Any]):
        if not updates:
            return
        if "status" in updates:
            raise ValueError("Status must be updated via set_status()")
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(updates.values())
        values.append(submission_id)
        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE submissions SET {set_clause} WHERE id = ?", values
            )
            conn.commit()

    def set_status(self, submission_id: int, new_status: SubmissionStatus):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE submissions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_status.value, submission_id),
            )
            conn.commit()

    def get_submissions_by_user(self, user_id: int) -> List[SubmissionRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM submissions WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            )
            return [SubmissionRecord(**dict(row)) for row in cursor.fetchall()]
```

Note: `set_status` does **not** validate transitions yet — full state machine enforcement added in Phase 4. ERROR is always reachable.

- [ ] **Step 4: Run all SubmissionsDB tests**

```bash
pytest tests/test_state.py -v -k "submission"
```

Expected: 8 tests PASS.

- [ ] **Step 5: Run full test suite — no regressions**

```bash
pytest -v --tb=short
```

Expected: 107 + 10 = ~117 passing. All original tests green.

- [ ] **Step 6: Commit**

```bash
git add app/state/db.py app/state/models.py tests/test_state.py
git commit -m "[PHASE-02] add: SubmissionsDB class + submissions table in SQLite"
```

---

## Task 4: Config — Provider Env Vars

**Files:**
- Modify: `app/config.py`

No tests needed — config is loaded from env; tested implicitly by provider tests.

- [ ] **Step 1: Add provider fields to Config dataclass in app/config.py**

Add after the existing `ANTHROPIC_API_KEY` line:

```python
# LLM provider selection (claude | gemini | deepseek)
LLM_EXTRACT_PROVIDER: str = os.getenv("LLM_EXTRACT_PROVIDER", "claude")
LLM_REWRITE_PROVIDER: str = os.getenv("LLM_REWRITE_PROVIDER", "claude")
# Provider API keys
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
pytest tests/test_llm.py -v
```

Expected: all existing LLM tests PASS.

- [ ] **Step 3: Commit**

```bash
git add app/config.py
git commit -m "[PHASE-02] add: LLM_EXTRACT_PROVIDER + LLM_REWRITE_PROVIDER config env vars"
```

---

## Task 5: Prompt Builder — JD Extraction + v2 Resume Fields Prompts

**Files:**
- Modify: `app/llm/prompt_builder.py`
- Create: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_prompt_builder.py`:

```python
from app.llm.prompt_builder import (
    build_jd_extraction_prompt,
    build_resume_fields_prompt,
)


def test_build_jd_extraction_prompt_contains_jd_text():
    prompt = build_jd_extraction_prompt("We need a Python engineer with 5 years experience.")
    assert "Python engineer" in prompt
    assert "job_title" in prompt
    assert "required_skills" in prompt
    assert "preferred_skills" in prompt
    assert "key_responsibilities" in prompt


def test_build_jd_extraction_prompt_returns_string():
    result = build_jd_extraction_prompt("any jd text")
    assert isinstance(result, str)
    assert len(result) > 50


def test_build_resume_fields_prompt_contains_resume_text():
    prompt = build_resume_fields_prompt("Alice Smith, Software Engineer, Python, Java")
    assert "Alice Smith" in prompt
    assert "candidate_name" in prompt
    assert "skills" in prompt
    assert "current_title" in prompt
    assert "experience_summary" in prompt


def test_build_resume_fields_prompt_returns_string():
    result = build_resume_fields_prompt("any resume text")
    assert isinstance(result, str)
    assert len(result) > 50
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_prompt_builder.py -v
```

Expected: FAIL — functions not yet defined.

- [ ] **Step 3: Append prompts to app/llm/prompt_builder.py**

```python
def build_jd_extraction_prompt(jd_text: str) -> str:
    """
    Prompt for the EXTRACT provider to pull structured fields from a Job Description.
    Used by jd_extractor.py for Phase 2 upload and Phase 3 ATS scoring.
    """
    return f"""Extract structured fields from the Job Description below.

Respond ONLY with valid JSON matching this schema exactly - no markdown, no explanation:
{{
  "job_title": "string",
  "company": "string",
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "experience_required": "string",
  "education_required": "string",
  "key_responsibilities": ["string"]
}}

Use empty string "" for scalar fields not found. Use [] for list fields not found.

=== JOB DESCRIPTION ===
{jd_text}""".strip()


def build_resume_fields_prompt(resume_text: str) -> str:
    """
    Prompt for the EXTRACT provider to pull structured fields from a resume.
    Returns richer schema than v1 extract_fields() - used for ATS scoring (Phase 3).
    The v1 extract_fields() (name/email/phone only) is preserved separately for backward compat.
    """
    return f"""Extract structured fields from the resume below.

Respond ONLY with valid JSON matching this schema exactly - no markdown, no explanation:
{{
  "candidate_name": "string",
  "email": "string",
  "phone": "string",
  "current_title": "string",
  "skills": ["string"],
  "experience_summary": "string"
}}

Use empty string "" for scalar fields not found. Use [] for skills if none found.

=== RESUME ===
{resume_text}""".strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_prompt_builder.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/llm/prompt_builder.py tests/test_prompt_builder.py
git commit -m "[PHASE-02] add: JD extraction prompt + v2 resume fields prompt"
```

---

## Task 6: Finetuner Extensions — Claude Adapters for JD + v2 Resume

**Files:**
- Modify: `app/llm/finetuner.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_llm.py` (verify `pytest` and `unittest.mock` already imported):

```python
from unittest.mock import patch, MagicMock
from app.llm.finetuner import extract_resume_fields_claude, extract_jd_fields_claude


def _mock_llm_response(json_str: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=json_str)]
    return msg


def test_extract_resume_fields_claude_returns_dict():
    payload = '{"candidate_name":"Alice","email":"a@b.com","phone":"555","current_title":"Engineer","skills":["Python"],"experience_summary":"5 years"}'
    with patch("app.llm.finetuner._get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_llm_response(payload)
        result = extract_resume_fields_claude("Alice resume text")
    assert result["candidate_name"] == "Alice"
    assert result["skills"] == ["Python"]
    assert result["current_title"] == "Engineer"


def test_extract_resume_fields_claude_retries_on_bad_json():
    good = '{"candidate_name":"Bob","email":"","phone":"","current_title":"","skills":[],"experience_summary":""}'
    responses = [_mock_llm_response("not json"), _mock_llm_response(good)]
    with patch("app.llm.finetuner._get_client") as mock_client:
        mock_client.return_value.messages.create.side_effect = responses
        result = extract_resume_fields_claude("Bob resume text")
    assert result["candidate_name"] == "Bob"


def test_extract_jd_fields_claude_returns_dict():
    payload = '{"job_title":"SWE","company":"ACME","required_skills":["Python","SQL"],"preferred_skills":[],"experience_required":"3 years","education_required":"BS","key_responsibilities":["Build APIs"]}'
    with patch("app.llm.finetuner._get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_llm_response(payload)
        result = extract_jd_fields_claude("We need a SWE at ACME")
    assert result["job_title"] == "SWE"
    assert "Python" in result["required_skills"]


def test_extract_jd_fields_claude_raises_after_max_retries():
    with patch("app.llm.finetuner._get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_llm_response("not valid json")
        with pytest.raises(ValueError, match="max retries"):
            extract_jd_fields_claude("some jd text")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm.py::test_extract_resume_fields_claude_returns_dict tests/test_llm.py::test_extract_jd_fields_claude_returns_dict -v
```

Expected: FAIL — functions not defined.

- [ ] **Step 3: Append functions to app/llm/finetuner.py**

```python
def extract_resume_fields_claude(resume_text: str) -> dict:
    """
    v2 EXTRACT pass (Claude adapter).
    Returns richer schema than v1 extract_fields():
      candidate_name, email, phone, current_title, skills[], experience_summary
    v1 extract_fields() is preserved unchanged for backward compat.
    """
    from app.llm.prompt_builder import build_resume_fields_prompt
    prompt = build_resume_fields_prompt(resume_text)
    client = _get_client()

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = client.messages.create(
                model=config.LLM_EXTRACT_MODEL,
                max_tokens=512,
                system="You are a resume parser. Respond ONLY with valid JSON. No markdown, no explanation.",
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(_strip_markdown_fences(response.content[0].text))
        except json.JSONDecodeError as e:
            logger.warning(f"extract_resume_fields_claude attempt {attempt}/{config.MAX_LLM_RETRIES} bad JSON: {e}")
            if attempt == config.MAX_LLM_RETRIES:
                raise ValueError("Failed to obtain valid JSON from extract_resume_fields_claude after max retries")
        except Exception as e:
            logger.error(f"Unexpected error in extract_resume_fields_claude: {e}")
            raise


def extract_jd_fields_claude(jd_text: str) -> dict:
    """
    JD field extraction (Claude adapter).
    Returns: job_title, company, required_skills[], preferred_skills[],
             experience_required, education_required, key_responsibilities[]
    """
    from app.llm.prompt_builder import build_jd_extraction_prompt
    prompt = build_jd_extraction_prompt(jd_text)
    client = _get_client()

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = client.messages.create(
                model=config.LLM_EXTRACT_MODEL,
                max_tokens=1024,
                system="You are a job description parser. Respond ONLY with valid JSON. No markdown, no explanation.",
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(_strip_markdown_fences(response.content[0].text))
        except json.JSONDecodeError as e:
            logger.warning(f"extract_jd_fields_claude attempt {attempt}/{config.MAX_LLM_RETRIES} bad JSON: {e}")
            if attempt == config.MAX_LLM_RETRIES:
                raise ValueError("Failed to obtain valid JSON from extract_jd_fields_claude after max retries")
        except Exception as e:
            logger.error(f"Unexpected error in extract_jd_fields_claude: {e}")
            raise
```

- [ ] **Step 4: Run all new finetuner tests**

```bash
pytest tests/test_llm.py -v -k "resume_fields or jd_fields"
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run full test suite — no regressions**

```bash
pytest -v --tb=short
```

Expected: all prior tests still green.

- [ ] **Step 6: Commit**

```bash
git add app/llm/finetuner.py tests/test_llm.py
git commit -m "[PHASE-02] add: extract_resume_fields_claude + extract_jd_fields_claude adapters"
```

---

## Task 7: Provider Routing Module

**Files:**
- Create: `app/llm/provider.py`
- Create: `tests/test_provider.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_provider.py`:

```python
import pytest
from unittest.mock import patch


def test_extract_resume_fields_routes_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "claude")
    expected = {"candidate_name": "Alice", "email": "", "phone": "",
                "current_title": "Engineer", "skills": ["Python"], "experience_summary": ""}
    with patch("app.llm.provider.extract_resume_fields_claude", return_value=expected) as mock_fn:
        from importlib import reload
        import app.llm.provider as prov
        reload(prov)
        result = prov.extract_resume_fields("Alice resume")
    mock_fn.assert_called_once_with("Alice resume")
    assert result["candidate_name"] == "Alice"


def test_extract_jd_fields_routes_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "claude")
    expected = {"job_title": "SWE", "company": "", "required_skills": ["Python"],
                "preferred_skills": [], "experience_required": "", "education_required": "",
                "key_responsibilities": []}
    with patch("app.llm.provider.extract_jd_fields_claude", return_value=expected) as mock_fn:
        from importlib import reload
        import app.llm.provider as prov
        reload(prov)
        result = prov.extract_jd_fields("Python SWE role")
    mock_fn.assert_called_once_with("Python SWE role")
    assert result["job_title"] == "SWE"


def test_extract_resume_fields_gemini_raises_not_implemented(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "gemini")
    from importlib import reload
    import app.llm.provider as prov
    reload(prov)
    with pytest.raises(NotImplementedError, match="gemini"):
        prov.extract_resume_fields("any text")


def test_extract_jd_fields_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "unknown_provider")
    from importlib import reload
    import app.llm.provider as prov
    reload(prov)
    with pytest.raises(NotImplementedError):
        prov.extract_jd_fields("any jd")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_provider.py -v
```

Expected: FAIL — `app.llm.provider` module not found.

- [ ] **Step 3: Create app/llm/provider.py**

```python
"""
Provider routing layer for LLM calls.
Routes extract_* calls based on LLM_EXTRACT_PROVIDER env var.

Supported providers:
  claude   - Claude Haiku (extract) / Claude Sonnet (rewrite). IMPLEMENTED.
  gemini   - Gemini 2.0 Flash. STUB - raises NotImplementedError.
  deepseek - DeepSeek V3. STUB - raises NotImplementedError (rewrite only, future).
"""
import logging
from app.config import config
from app.llm.finetuner import (
    extract_resume_fields_claude,
    extract_jd_fields_claude,
)

logger = logging.getLogger(__name__)


def extract_resume_fields(resume_text: str) -> dict:
    """Route resume field extraction to the configured EXTRACT provider."""
    provider = config.LLM_EXTRACT_PROVIDER.lower()
    if provider == "claude":
        return extract_resume_fields_claude(resume_text)
    raise NotImplementedError(
        f"EXTRACT provider '{provider}' is not implemented. "
        "Set LLM_EXTRACT_PROVIDER=claude or add the adapter to finetuner.py."
    )


def extract_jd_fields(jd_text: str) -> dict:
    """Route JD field extraction to the configured EXTRACT provider."""
    provider = config.LLM_EXTRACT_PROVIDER.lower()
    if provider == "claude":
        return extract_jd_fields_claude(jd_text)
    raise NotImplementedError(
        f"EXTRACT provider '{provider}' is not implemented. "
        "Set LLM_EXTRACT_PROVIDER=claude or add the adapter to finetuner.py."
    )
```

- [ ] **Step 4: Run provider tests**

```bash
pytest tests/test_provider.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v --tb=short
```

Expected: all prior tests still green.

- [ ] **Step 6: Commit**

```bash
git add app/llm/provider.py tests/test_provider.py
git commit -m "[PHASE-02] add: provider.py routing hub for LLM extract calls"
```

---

## Task 8: JD Extractor Module

**Files:**
- Create: `app/ingestor/jd_extractor.py`
- Modify: `tests/test_ingestor.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_ingestor.py`:

```python
from unittest.mock import patch
from app.ingestor.jd_extractor import extract_jd_fields


def test_extract_jd_fields_returns_dict():
    expected = {
        "job_title": "Backend Engineer",
        "company": "ACME",
        "required_skills": ["Python", "PostgreSQL"],
        "preferred_skills": ["Docker"],
        "experience_required": "3+ years",
        "education_required": "BS Computer Science",
        "key_responsibilities": ["Design APIs", "Write tests"],
    }
    with patch("app.ingestor.jd_extractor.provider.extract_jd_fields", return_value=expected):
        result = extract_jd_fields("We need a Backend Engineer at ACME...")
    assert result["job_title"] == "Backend Engineer"
    assert "Python" in result["required_skills"]


def test_extract_jd_fields_empty_text():
    expected = {
        "job_title": "", "company": "", "required_skills": [],
        "preferred_skills": [], "experience_required": "",
        "education_required": "", "key_responsibilities": [],
    }
    with patch("app.ingestor.jd_extractor.provider.extract_jd_fields", return_value=expected):
        result = extract_jd_fields("")
    assert result["required_skills"] == []
    assert result["job_title"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ingestor.py::test_extract_jd_fields_returns_dict tests/test_ingestor.py::test_extract_jd_fields_empty_text -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create app/ingestor/jd_extractor.py**

```python
"""
JD field extraction - ingestor layer.
Delegates to app.llm.provider so LLM_EXTRACT_PROVIDER controls routing.
"""
import logging
from app.llm import provider

logger = logging.getLogger(__name__)


def extract_jd_fields(jd_text: str) -> dict:
    """
    Extract structured fields from a Job Description string.

    Returns dict with keys:
        job_title, company, required_skills, preferred_skills,
        experience_required, education_required, key_responsibilities

    Raises ValueError if the LLM returns malformed JSON after max retries.
    Raises NotImplementedError if LLM_EXTRACT_PROVIDER is not yet implemented.
    """
    logger.info("Extracting JD fields via provider")
    return provider.extract_jd_fields(jd_text)
```

- [ ] **Step 4: Run JD extractor tests**

```bash
pytest tests/test_ingestor.py -v -k "jd_fields"
```

Expected: 2 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v --tb=short
```

Expected: all prior tests green.

- [ ] **Step 6: Commit**

```bash
git add app/ingestor/jd_extractor.py tests/test_ingestor.py
git commit -m "[PHASE-02] add: jd_extractor.py - JD field extraction via provider"
```

---

## Task 9: Upload UI Page

**Files:**
- Create: `app/ui/pages/1_Upload.py`

UI pages are not unit-tested directly. Business logic (extraction + DB) is already tested by prior tasks. This task wires everything into Streamlit.

- [ ] **Step 1: Create app/ui/pages/1_Upload.py**

```python
"""
Phase 2 - Upload Page
Allows an authenticated user to:
  1. Upload their resume (PDF / DOC / DOCX)
  2. Provide a Job Description (paste text OR upload PDF / DOC / DOCX)
  3. Extract raw text + structured fields from both
  4. Store a Submission record in SQLite linked to their session
"""
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path

import streamlit as st

from app.ingestor.extractor import extract_text, extract_text_and_photo
from app.ingestor.jd_extractor import extract_jd_fields
from app.llm.provider import extract_resume_fields
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionStatus

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))
PHOTOS_DIR = Path("data/photos")


def _get_auth_db() -> AuthDB:
    if "auth_db" not in st.session_state:
        st.session_state["auth_db"] = AuthDB(DB_PATH)
    return st.session_state["auth_db"]


def _get_subs_db() -> SubmissionsDB:
    if "subs_db" not in st.session_state:
        st.session_state["subs_db"] = SubmissionsDB(DB_PATH)
    return st.session_state["subs_db"]


def _require_auth():
    """Stop page render if not authenticated. Returns (user_id, token)."""
    token = st.session_state.get("auth_token")
    if not token:
        st.warning("Please sign in first.")
        st.stop()
    session = _get_auth_db().get_session(token)
    if session is None:
        st.warning("Session expired. Please sign in again.")
        for key in ("auth_token", "auth_email"):
            st.session_state.pop(key, None)
        st.stop()
    return session.user_id, token


def _save_uploaded_to_temp(uploaded_file) -> Path:
    """Write a Streamlit UploadedFile to a named temp file. Caller must unlink."""
    suffix = Path(uploaded_file.name).suffix.lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.read())
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


def _save_photo(photo_bytes: bytes) -> str:
    """Save headshot bytes to data/photos/ and return relative path string."""
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    photo_path = PHOTOS_DIR / f"{uuid.uuid4()}.jpg"
    photo_path.write_bytes(photo_bytes)
    return str(photo_path)


def main():
    st.set_page_config(page_title="JobOS - Upload", page_icon="=")
    st.title("Upload Resume + Job Description")

    user_id, token = _require_auth()
    st.caption(f"Signed in as {st.session_state.get('auth_email', '')}")

    st.subheader("1. Resume")
    resume_file = st.file_uploader(
        "Upload your resume (PDF, DOC, or DOCX)",
        type=["pdf", "doc", "docx"],
        key="resume_uploader",
    )

    st.subheader("2. Job Description")
    jd_tab_paste, jd_tab_file = st.tabs(["Paste Text", "Upload File"])

    with jd_tab_paste:
        jd_text_input = st.text_area(
            "Paste the Job Description here",
            height=200,
            key="jd_text_input",
            placeholder="Copy and paste the full job description...",
        )

    with jd_tab_file:
        jd_file = st.file_uploader(
            "Or upload a JD file (PDF, DOC, DOCX)",
            type=["pdf", "doc", "docx"],
            key="jd_uploader",
        )

    if st.button("Submit", type="primary"):
        if not resume_file:
            st.error("Please upload your resume.")
            st.stop()

        jd_text_final = jd_text_input.strip() if jd_text_input else ""
        if not jd_text_final and not jd_file:
            st.error("Please provide a Job Description (paste text or upload a file).")
            st.stop()

        with st.spinner("Extracting resume text and photo..."):
            resume_tmp = _save_uploaded_to_temp(resume_file)
            try:
                resume_result = extract_text_and_photo(resume_tmp)
                resume_raw = resume_result["text"]
                photo_bytes = resume_result.get("photo_bytes")
            except Exception as e:
                logger.error(f"Resume extraction failed: {e}")
                st.error(f"Could not read resume: {e}")
                st.stop()
            finally:
                resume_tmp.unlink(missing_ok=True)

        if not jd_text_final and jd_file:
            with st.spinner("Extracting Job Description text..."):
                jd_tmp = _save_uploaded_to_temp(jd_file)
                try:
                    jd_text_final = extract_text(jd_tmp)
                except Exception as e:
                    logger.error(f"JD file extraction failed: {e}")
                    st.error(f"Could not read JD file: {e}")
                    st.stop()
                finally:
                    jd_tmp.unlink(missing_ok=True)

        with st.spinner("Extracting resume fields (LLM)..."):
            try:
                resume_fields = extract_resume_fields(resume_raw)
            except Exception as e:
                logger.error(f"Resume LLM extraction failed: {e}")
                st.error(f"Resume field extraction failed: {e}")
                st.stop()

        with st.spinner("Extracting Job Description fields (LLM)..."):
            try:
                jd_fields = extract_jd_fields(jd_text_final)
            except Exception as e:
                logger.error(f"JD LLM extraction failed: {e}")
                st.error(f"JD field extraction failed: {e}")
                st.stop()

        photo_path = None
        if photo_bytes:
            try:
                photo_path = _save_photo(photo_bytes)
            except Exception as e:
                logger.warning(f"Photo save failed (non-fatal): {e}")

        subs_db = _get_subs_db()
        sub_id = subs_db.create_submission(user_id=user_id, session_token=token)
        subs_db.update_submission(sub_id, {
            "resume_raw_text": resume_raw,
            "resume_fields_json": json.dumps(resume_fields),
            "resume_photo_path": photo_path,
            "jd_raw_text": jd_text_final,
            "jd_fields_json": json.dumps(jd_fields),
        })

        st.session_state["current_submission_id"] = sub_id
        candidate_name = resume_fields.get("candidate_name") or "Unknown"
        job_title = jd_fields.get("job_title") or "Unknown"

        st.success(f"Upload complete! Submission #{sub_id} created.")
        st.info(f"Candidate: **{candidate_name}** | Role: **{job_title}**")
        st.caption("Proceed to the next step to view ATS score and review.")


main()
```

- [ ] **Step 2: Verify no syntax errors**

```bash
python -m py_compile app/ui/pages/1_Upload.py && echo "Syntax OK"
```

Expected: `Syntax OK`

- [ ] **Step 3: Run full test suite**

```bash
pytest -v --tb=short
```

Expected: all existing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add app/ui/pages/1_Upload.py data/photos/.gitkeep
git commit -m "[PHASE-02] add: Upload page - resume + JD upload with LLM field extraction"
```

---

## Task 10: Final Test Run + Checkpoint

- [ ] **Step 1: Run full test suite**

```bash
pytest -v --tb=short 2>&1 | tee /tmp/phase02_pytest.txt
```

Expected final count: 107 (Phase 1 baseline) + ~24 new tests = **~131 tests passing**.

- [ ] **Step 2: Verify v1 preserved modules untouched**

```bash
git diff feature/phase-01-auth -- app/ingestor/extractor.py app/ingestor/converter.py app/composer/ app/email_handler/
```

Expected: empty output (no changes to v1 preserved files).

- [ ] **Step 3: Verify branch name and commit format**

```bash
git log --oneline feature/phase-01-auth..HEAD
```

Expected: all commits prefixed `[PHASE-02]`.

- [ ] **Step 4: Push branch**

```bash
git push -u origin feature/phase-02-upload-parse
```

---

## Acceptance Criteria Checklist

- [ ] Resume upload accepts PDF, DOC, DOCX - text + photo extracted
- [ ] JD accepts pasted text OR uploaded file (PDF/DOC/DOCX)
- [ ] Upload page requires active auth session (stops if not authenticated)
- [ ] `submissions` table created with WAL mode in `resume_builder.db`
- [ ] `SubmissionsDB.create_submission()` stores user_id + session_token
- [ ] `resume_fields_json` and `jd_fields_json` stored as JSON strings in DB
- [ ] `resume_photo_path` stores relative path to saved headshot (or NULL)
- [ ] `current_submission_id` stored in `st.session_state` for downstream pages
- [ ] `LLM_EXTRACT_PROVIDER=claude` works; `gemini` raises NotImplementedError clearly
- [ ] v1 `extract_fields()` in `finetuner.py` unchanged - v1 tests still pass
- [ ] `app/ingestor/extractor.py` headshot heuristic untouched
- [ ] All 107 Phase 1 tests still green
- [ ] New tests cover: SubmissionsDB CRUD, provider routing, jd_extractor, prompt_builder

---

## Notes / Deferred

- **Gemini + DeepSeek adapters** deferred. Both raise `NotImplementedError` with a message pointing to `LLM_EXTRACT_PROVIDER=claude`.
- **Status machine transition validation** for `SubmissionsDB.set_status()` deferred to Phase 4 (Review page).
- **Upload error recovery** (partial uploads, LLM timeout): submission stays PENDING. Phase 4 handles re-try UX.
- **DOC/DOCX JD upload** calls `extractor.extract_text()` which uses existing `converter.py` + LibreOffice in Docker. PDF is native pdfplumber.

# Page Chop Fix + Print Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the abrupt page-truncation bug in the ATS resume PDF, then add a second "Print" resume output following the JobOS 9-section ideal structure — both unlocked by one payment.

**Architecture:** (1) Remove the post-build fitz deletion loop from `pdf_writer.py` — ReportLab paginates naturally. (2) Extend the LLM prompt schema to capture print-specific fields (`print_fields`, `company_intro`, `city` per role). (3) New `app/composer/print_writer.py` generates the Print PDF from the enriched JSON. (4) Both PDFs generated together in `_run_rewrite_pipeline` and `_run_revision_pipeline`. (5) Download page shows two buttons after payment. ATS pipeline is untouched beyond the deletion-loop removal.

**Tech Stack:** Python 3.13, ReportLab, PyMuPDF (fitz) in tests only, SQLite WAL, Streamlit

---

## File Map

| Action | File | Change |
|---|---|---|
| Modify | `app/composer/pdf_writer.py` | Remove fitz import + page deletion loop |
| Modify | `tests/test_composer.py` | Update page-truncation test |
| Modify | `app/state/models.py` | Add `output_print_pdf_path` field |
| Modify | `app/state/db.py` | DB migration + whitelist column |
| Modify | `app/llm/prompt_builder.py` | Extend OUTPUT SCHEMA with print_fields |
| Create | `app/composer/print_writer.py` | `generate_print_pdf()` |
| Modify | `app/composer/__init__.py` | Export `generate_print_pdf` |
| Modify | `app/ui/pages/3_Review.py` | Call `generate_print_pdf` in pipeline |
| Modify | `app/ui/pages/4_Revise.py` | Call `generate_print_pdf` in pipeline |
| Modify | `app/ui/pages/6_Download.py` | Two download buttons after payment |
| Create | `tests/test_print_writer.py` | Unit tests for print_writer |
| Modify | `tests/test_review_pipeline.py` | Verify print PDF path stored |
| Modify | `tests/test_revise_pipeline.py` | Verify print PDF path stored |

---

## Task 1: Fix Page Chop Bug

**Files:**
- Modify: `app/composer/pdf_writer.py:6` (remove fitz import)
- Modify: `app/composer/pdf_writer.py:252-270` (remove deletion block)
- Modify: `tests/test_composer.py:109-133` (update page cap test)

- [ ] **Step 1: Update the failing test (TDD first)**

In `tests/test_composer.py`, replace the entire `test_max_2_pages_long_content` function (lines 109–133) with:

```python
def test_long_resume_not_truncated(tmp_path):
    """Long resume must NOT be truncated — content flows across pages naturally."""
    big_json = {
        "candidate_name": "Long Resume Person",
        "contact": {"email": "long@test.com", "phone": "555-1234", "linkedin": "li.com/long"},
        "summary": "A very experienced professional. " * 10,
        "experience": [
            {
                "title": f"Engineer Level {i}",
                "company": f"MegaCorp {i}",
                "dates": f"200{i % 10} - 201{i % 10}",
                "bullets": [f"Accomplished milestone {j} for project {i}" for j in range(8)],
            }
            for i in range(20)
        ],
        "education": [{"degree": "B.S. CS", "institution": "State U", "year": "2000"}],
        "skills": [f"Skill{k}" for k in range(40)],
    }
    output_pdf = tmp_path / "long_resume.pdf"
    result = generate_resume_pdf(big_json, None, output_pdf)
    assert result is True
    doc = fitz.open(str(output_pdf))
    page_count = len(doc)
    doc.close()
    assert page_count > 2, (
        f"Expected long resume to span >2 pages without truncation, got {page_count}"
    )
```

- [ ] **Step 2: Run test to verify it fails (truncation is still in place)**

```
cd D:/staging/resume-builder-v2
pytest tests/test_composer.py::test_long_resume_not_truncated -v
```

Expected: FAIL — "Expected long resume to span >2 pages without truncation, got 2"

- [ ] **Step 3: Remove the fitz import and deletion block from pdf_writer.py**

In `app/composer/pdf_writer.py`:

Remove line 6:
```python
import fitz  # PyMuPDF
```

Replace lines 252–266 (the block starting with `buffer.seek(0)` after `doc.build(...)`) with:

```python
        doc.build(elements, onFirstPage=_draw_photo_first_page)

        buffer.seek(0)
        output_path.write_bytes(buffer.read())
        buffer.close()
```

The full end of the `try` block in `generate_resume_pdf` now reads:

```python
        doc.build(elements, onFirstPage=_draw_photo_first_page)

        buffer.seek(0)
        output_path.write_bytes(buffer.read())
        buffer.close()

        logger.info(f"Successfully generated PDF: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        return False
```

- [ ] **Step 4: Run full composer test suite**

```
pytest tests/test_composer.py -v
```

Expected: All tests PASS. Note: `test_generate_resume_pdf_without_photo` and `test_generate_resume_pdf_with_photo` assert `len(doc) <= 2` — those fixtures use a single-experience resume that naturally fits in ≤2 pages, so they continue to pass.

- [ ] **Step 5: Commit**

```bash
git add app/composer/pdf_writer.py tests/test_composer.py
git commit -m "[BETA01] fix: remove hard 2-page truncation — ATS resume flows naturally

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: DB Migration + Model Update

**Files:**
- Modify: `app/state/models.py:37`
- Modify: `app/state/db.py:409-410` (migration block) and `app/state/db.py:435-438` (whitelist)

- [ ] **Step 1: Write the failing test**

In `tests/test_state.py`, add at the end of the file:

```python
def test_output_print_pdf_path_column_exists(tmp_path):
    """output_print_pdf_path column must exist and be settable after migration."""
    db_path = tmp_path / "test_print_col.db"
    from app.state.db import AuthDB, SubmissionsDB
    auth_db = AuthDB(db_path)
    subs_db = SubmissionsDB(db_path)
    user_id = auth_db.create_user("printcol@test.com")
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-printcol")
    # Should not raise
    subs_db.update_submission(sub_id, {"output_print_pdf_path": "/tmp/print.pdf"})
    sub = subs_db.get_submission(sub_id)
    assert sub.output_print_pdf_path == "/tmp/print.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_state.py::test_output_print_pdf_path_column_exists -v
```

Expected: FAIL — either AttributeError or ValueError "unknown columns: {'output_print_pdf_path'}"

- [ ] **Step 3: Add field to SubmissionRecord in models.py**

In `app/state/models.py`, the `SubmissionRecord` dataclass currently ends at:
```python
    payment_link_id: Optional[str] = None
    payment_id: Optional[str] = None
```

Add the new field after `payment_id`:
```python
    payment_link_id: Optional[str] = None
    payment_id: Optional[str] = None
    output_print_pdf_path: Optional[str] = None
```

- [ ] **Step 4: Add DB migration in db.py**

In `app/state/db.py`, the migration block currently ends at (approximately line 409):
```python
            if "payment_id" not in existing_cols:
                conn.execute("ALTER TABLE submissions ADD COLUMN payment_id TEXT")
            conn.commit()
```

Add the new migration line before `conn.commit()`:
```python
            if "payment_id" not in existing_cols:
                conn.execute("ALTER TABLE submissions ADD COLUMN payment_id TEXT")
            if "output_print_pdf_path" not in existing_cols:
                conn.execute("ALTER TABLE submissions ADD COLUMN output_print_pdf_path TEXT")
            conn.commit()
```

- [ ] **Step 5: Add column to the whitelist in db.py**

In `app/state/db.py`, `_SUBMISSION_UPDATE_COLUMNS` currently reads:
```python
    _SUBMISSION_UPDATE_COLUMNS = frozenset({
        "resume_raw_text", "resume_fields_json", "resume_photo_path",
        "jd_raw_text", "jd_fields_json", "ats_score_json",
        "llm_output_json", "output_pdf_path",
        "revision_count", "error_message",
        "payment_link_id", "payment_id",
    })
```

Replace with:
```python
    _SUBMISSION_UPDATE_COLUMNS = frozenset({
        "resume_raw_text", "resume_fields_json", "resume_photo_path",
        "jd_raw_text", "jd_fields_json", "ats_score_json",
        "llm_output_json", "output_pdf_path", "output_print_pdf_path",
        "revision_count", "error_message",
        "payment_link_id", "payment_id",
    })
```

- [ ] **Step 6: Run test to verify it passes**

```
pytest tests/test_state.py::test_output_print_pdf_path_column_exists -v
```

Expected: PASS

- [ ] **Step 7: Run full state test suite**

```
pytest tests/test_state.py -v
```

Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add app/state/models.py app/state/db.py tests/test_state.py
git commit -m "[BETA01] add: output_print_pdf_path column — DB migration + model

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Extend LLM Prompt Schema

**Files:**
- Modify: `app/llm/prompt_builder.py:510-519` (OUTPUT SCHEMA section)

- [ ] **Step 1: Write the failing test**

In `tests/test_prompt_builder.py`, add at the end:

```python
def test_finetuning_prompt_includes_print_fields():
    prompt = build_finetuning_prompt("resume text", "jd text", "best practice", "Alice")
    assert "print_fields" in prompt
    assert "company_intro" in prompt
    assert "core_skills" in prompt
    assert "languages" in prompt
    assert "notice_period" in prompt


def test_finetuning_prompt_experience_has_city_and_company_intro():
    prompt = build_finetuning_prompt("resume text", "jd text", "best practice", "Alice")
    # Both new experience fields must appear in schema
    assert '"city"' in prompt
    assert '"company_intro"' in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_prompt_builder.py::test_finetuning_prompt_includes_print_fields tests/test_prompt_builder.py::test_finetuning_prompt_experience_has_city_and_company_intro -v
```

Expected: Both FAIL — "print_fields" not in prompt

- [ ] **Step 3: Update build_finetuning_prompt OUTPUT SCHEMA**

In `app/llm/prompt_builder.py`, find the `=== OUTPUT SCHEMA ===` block inside `build_finetuning_prompt` (lines ~510–521). It currently reads:

```python
=== OUTPUT SCHEMA ===
You must respond with ONLY valid JSON matching this schema exactly. No markdown blocks, no conversational text.
{{
  "candidate_name": "{candidate_name}",
  "contact": {{ "email": "string", "phone": "string", "linkedin": "string" }},
  "summary": "string - 3-4 lines, JD-aligned",
  "experience": [ {{ "title": "string", "company": "string", "dates": "string", "bullets": ["string"] }} ],
  "education": [ {{ "degree": "string", "institution": "string", "year": "string" }} ],
  "skills": ["string"],
  "missing_fields": ["string - any field that was blank or unclear in source resume"]
}}
```

Replace the entire `=== OUTPUT SCHEMA ===` block with:

```python
=== OUTPUT SCHEMA ===
You must respond with ONLY valid JSON matching this schema exactly. No markdown blocks, no conversational text.
{{
  "candidate_name": "{candidate_name}",
  "contact": {{ "email": "string", "phone": "string", "linkedin": "string" }},
  "summary": "string - 3-4 lines, JD-aligned",
  "experience": [
    {{
      "title": "string",
      "company": "string",
      "city": "string - city where role was based, or empty string if not found",
      "dates": "string - Month-Year format e.g. Jan 2020 - Mar 2023",
      "company_intro": "string - one line describing what the company does, or empty string if not found",
      "bullets": ["string"]
    }}
  ],
  "education": [ {{ "degree": "string", "institution": "string", "year": "string" }} ],
  "skills": ["string"],
  "missing_fields": ["string - any field that was blank or unclear in source resume"],
  "print_fields": {{
    "gender": "string extracted from resume, or [MISSING: Gender]",
    "dob": "string in DD-MMM-YYYY format extracted from resume, or [MISSING: Date of Birth]",
    "age": "string - integer age calculated from DOB if DOB found, else empty string",
    "city": "string - candidate current city from resume, or [MISSING: City]",
    "open_to_relocate": false,
    "notice_period": "string extracted from resume e.g. 30 days, 2 months, or [MISSING: Notice Period]",
    "portfolio_url": "string - GitHub/Behance/ArtStation/portfolio URL if found, else empty string",
    "core_skills": ["string - up to 5 core technical or domain skills from the resume"],
    "tools_platforms": ["string - up to 5 tools and platforms from the resume"],
    "soft_skills": ["string - up to 5 soft skills from the resume"],
    "psychometric_type": "string - 16Personalities type if mentioned in resume e.g. ENFJ, else [MISSING: Psychometric Type]",
    "languages": [ {{ "language": "string", "proficiency": "string e.g. Native, Full Professional, Conversational" }} ],
    "certifications": [ {{ "name": "string", "issuing_body": "string", "year": "string" }} ],
    "awards": ["string - one-liner award or recognition"]
  }}
}}
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_prompt_builder.py -v
```

Expected: All PASS including the two new tests

- [ ] **Step 5: Commit**

```bash
git add app/llm/prompt_builder.py tests/test_prompt_builder.py
git commit -m "[BETA01] add: extend LLM output schema with print_fields and experience city/company_intro

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Print PDF Writer

**Files:**
- Create: `app/composer/print_writer.py`
- Modify: `app/composer/__init__.py`
- Create: `tests/test_print_writer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_print_writer.py`:

```python
"""
Tests for app/composer/print_writer.py — JobOS Print Resume PDF generator.
"""
import base64
import pytest
import fitz
from pathlib import Path

from app.composer.print_writer import generate_print_pdf, _apply_recency_rule, _extract_start_year

# Tiny valid 1×1 PNG (same as test_composer.py)
VALID_PNG_B64 = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


@pytest.fixture
def photo_bytes():
    return base64.b64decode(VALID_PNG_B64)


@pytest.fixture
def full_json():
    return {
        "candidate_name": "Priya Sharma",
        "contact": {
            "email": "priya@example.com",
            "phone": "+91 98765 43210",
            "linkedin": "linkedin.com/in/priyasharma",
        },
        "summary": "Sales professional with 8 years in FMCG. Specialist in key account management.",
        "experience": [
            {
                "title": "Senior Sales Manager",
                "company": "FoodCo India",
                "city": "Mumbai",
                "dates": "Jan 2020 - Present",
                "company_intro": "Leading FMCG distributor serving 50,000 retail outlets.",
                "bullets": ["Grew revenue by 40%", "Led team of 12"],
            },
            {
                "title": "Area Sales Executive",
                "company": "BeverageCorp",
                "city": "Pune",
                "dates": "Jun 2016 - Dec 2019",
                "company_intro": "National beverage brand with ₹500Cr turnover.",
                "bullets": ["Exceeded target by 120%", "Opened 200 new accounts", "Won Best Performer 2018"],
            },
            {
                "title": "Sales Representative",
                "company": "StartupX",
                "city": "Bangalore",
                "dates": "Jan 2014 - May 2016",
                "company_intro": "B2B SaaS startup.",
                "bullets": ["Managed 50 accounts", "Cold-called 100 leads/week", "CRM data entry", "Extra bullet 4"],
            },
        ],
        "education": [
            {"degree": "MBA Marketing", "institution": "Symbiosis Institute", "year": "2013"}
        ],
        "skills": ["Negotiation", "Key Accounts", "CRM"],
        "missing_fields": [],
        "print_fields": {
            "gender": "Female",
            "dob": "15-Mar-1990",
            "age": "35",
            "city": "Mumbai",
            "open_to_relocate": True,
            "notice_period": "30 days",
            "portfolio_url": "",
            "core_skills": ["Key Account Management", "Channel Sales", "Revenue Growth"],
            "tools_platforms": ["Salesforce", "Excel", "SAP"],
            "soft_skills": ["Negotiation", "Leadership", "Communication"],
            "psychometric_type": "[MISSING: Psychometric Type]",
            "languages": [
                {"language": "English", "proficiency": "Full Professional"},
                {"language": "Hindi", "proficiency": "Native"},
            ],
            "certifications": [
                {"name": "Certified Sales Professional", "issuing_body": "ISM", "year": "2018"}
            ],
            "awards": ["Best Regional Manager 2022 — FoodCo India"],
        },
    }


@pytest.fixture
def minimal_json():
    """JSON with only mandatory fields — everything else missing."""
    return {
        "candidate_name": "John Doe",
        "contact": {"email": "john@doe.com", "phone": "", "linkedin": ""},
        "summary": "A summary.",
        "experience": [],
        "education": [],
        "skills": [],
        "missing_fields": [],
        "print_fields": {},
    }


# ── Core generation tests ──────────────────────────────────────────────────

def test_generate_print_pdf_returns_true_and_creates_file(tmp_path, full_json):
    out = tmp_path / "print.pdf"
    result = generate_print_pdf(full_json, None, out)
    assert result is True
    assert out.exists()
    assert out.stat().st_size > 0


def test_generate_print_pdf_with_photo(tmp_path, full_json, photo_bytes):
    out = tmp_path / "print_photo.pdf"
    result = generate_print_pdf(full_json, photo_bytes, out)
    assert result is True
    assert out.exists()


def test_generate_print_pdf_missing_fields_show_in_red(tmp_path, minimal_json):
    out = tmp_path / "print_missing.pdf"
    result = generate_print_pdf(minimal_json, None, out)
    assert result is True
    doc = fitz.open(str(out))
    text = "".join(p.get_text() for p in doc)
    doc.close()
    assert "MISSING" in text


def test_generate_print_pdf_candidate_name_in_output(tmp_path, full_json):
    out = tmp_path / "print_name.pdf"
    generate_print_pdf(full_json, None, out)
    doc = fitz.open(str(out))
    text = doc[0].get_text()
    doc.close()
    assert "Priya Sharma" in text


def test_generate_print_pdf_section_headers_present(tmp_path, full_json):
    out = tmp_path / "print_sections.pdf"
    generate_print_pdf(full_json, None, out)
    doc = fitz.open(str(out))
    text = "".join(p.get_text() for p in doc)
    doc.close()
    for header in ("Profile Links", "Professional Summary", "Skills", "Professional Experience",
                   "Education", "Languages", "Certifications", "Awards"):
        assert header in text, f"Section '{header}' missing from Print PDF"


def test_generate_print_pdf_certifications_absent_when_empty(tmp_path, full_json):
    full_json["print_fields"]["certifications"] = []
    out = tmp_path / "print_no_certs.pdf"
    generate_print_pdf(full_json, None, out)
    doc = fitz.open(str(out))
    text = "".join(p.get_text() for p in doc)
    doc.close()
    assert "Certifications" not in text


def test_generate_print_pdf_awards_absent_when_empty(tmp_path, full_json):
    full_json["print_fields"]["awards"] = []
    out = tmp_path / "print_no_awards.pdf"
    generate_print_pdf(full_json, None, out)
    doc = fitz.open(str(out))
    text = "".join(p.get_text() for p in doc)
    doc.close()
    assert "Awards" not in text


def test_generate_print_pdf_returns_true_on_bad_photo(tmp_path, full_json):
    out = tmp_path / "print_bad_photo.pdf"
    result = generate_print_pdf(full_json, b"not an image", out)
    assert result is True
    assert out.exists()


# ── Recency rule tests ─────────────────────────────────────────────────────

def test_recency_rule_role_0_and_1_keep_all_bullets():
    experience = [
        {"title": "R0", "company": "C", "dates": "Jan 2022 - Present", "bullets": ["b1", "b2", "b3", "b4", "b5"]},
        {"title": "R1", "company": "C", "dates": "Jan 2018 - Dec 2021", "bullets": ["b1", "b2", "b3", "b4"]},
    ]
    result = _apply_recency_rule(experience)
    assert len(result[0]["bullets"]) == 5
    assert len(result[1]["bullets"]) == 4


def test_recency_rule_role_2_and_beyond_max_3_bullets():
    experience = [
        {"title": "R0", "company": "C", "dates": "2022 - Present", "bullets": ["b1"]},
        {"title": "R1", "company": "C", "dates": "2019 - 2022", "bullets": ["b1"]},
        {"title": "R2", "company": "C", "dates": "2016 - 2019", "bullets": ["b1", "b2", "b3", "b4", "b5"]},
        {"title": "R3", "company": "C", "dates": "2013 - 2016", "bullets": ["b1", "b2", "b3", "b4"]},
    ]
    result = _apply_recency_rule(experience)
    assert len(result[2]["bullets"]) == 3
    assert len(result[3]["bullets"]) == 3


def test_recency_rule_old_role_max_1_bullet():
    # Role starting 12 years ago (start year <= current_year - 10)
    experience = [
        {"title": "R0", "company": "C", "dates": "2022 - Present", "bullets": ["b1"]},
        {"title": "R1", "company": "C", "dates": "2019 - 2022", "bullets": ["b1"]},
        {"title": "Old", "company": "C", "dates": "2010 - 2014", "bullets": ["b1", "b2", "b3"]},
    ]
    result = _apply_recency_rule(experience)
    assert len(result[2]["bullets"]) == 1


def test_recency_rule_does_not_mutate_original():
    experience = [
        {"title": "R0", "company": "C", "dates": "2022 - Present", "bullets": ["b1"]},
        {"title": "R1", "company": "C", "dates": "2019 - 2022", "bullets": ["b1"]},
        {"title": "R2", "company": "C", "dates": "2016 - 2019", "bullets": ["b1", "b2", "b3", "b4"]},
    ]
    original_bullets = len(experience[2]["bullets"])
    _apply_recency_rule(experience)
    assert len(experience[2]["bullets"]) == original_bullets  # original unchanged


# ── Start year extraction tests ────────────────────────────────────────────

def test_extract_start_year_month_year_format():
    assert _extract_start_year("Jan 2019 - Dec 2022") == 2019


def test_extract_start_year_year_only():
    assert _extract_start_year("2015 - Present") == 2015


def test_extract_start_year_empty_string():
    assert _extract_start_year("") is None


def test_extract_start_year_none():
    assert _extract_start_year(None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_print_writer.py -v
```

Expected: All FAIL — "ModuleNotFoundError: No module named 'app.composer.print_writer'"

- [ ] **Step 3: Create app/composer/print_writer.py**

```python
"""
Print Resume PDF Composer — JobOS Ideal Resume Structure (9 sections).

Separate from pdf_writer.py (ATS resume). ATS pipeline is NOT touched.
Entry point: generate_print_pdf(json_data, photo_bytes, output_path) -> bool
"""
import io
import logging
import pathlib
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether
from reportlab.lib.utils import ImageReader

from .photo_handler import process_photo_for_pdf
from .pdf_writer import highlight_missing

logger = logging.getLogger(__name__)

_CURRENT_YEAR = datetime.now().year


def _extract_start_year(dates_str: str) -> int | None:
    """Extract first 4-digit year from a dates string like 'Jan 2019 - Dec 2022'."""
    if not dates_str:
        return None
    m = re.search(r'\b(19|20)\d{2}\b', dates_str)
    return int(m.group()) if m else None


def _apply_recency_rule(experience: list) -> list:
    """
    Return a copy of experience list with bullets trimmed by recency:
      - Index 0, 1 (latest two roles): all bullets kept
      - Index 2+: max 3 bullets
      - Any role whose start year < (_CURRENT_YEAR - 10): max 1 bullet

    Does NOT mutate the input list or its dicts.
    """
    result = []
    for i, exp in enumerate(experience):
        exp_copy = dict(exp)
        bullets = list(exp_copy.get("bullets", []))
        start_year = _extract_start_year(exp_copy.get("dates", ""))
        is_old = start_year is not None and start_year < (_CURRENT_YEAR - 10)

        if is_old:
            bullets = bullets[:1]
        elif i >= 2:
            bullets = bullets[:3]
        # i == 0 or 1: keep all bullets

        exp_copy["bullets"] = bullets
        result.append(exp_copy)
    return result


def generate_print_pdf(
    json_data: dict,
    photo_bytes: bytes | None,
    output_path: pathlib.Path,
) -> bool:
    """
    Generate a Print-format resume PDF following the JobOS 9-section structure.

    Sections:
      1 Personal Details   2 Profile Links        3 Professional Summary
      4 Skills             5 Professional Experience  6 Education
      7 Languages          8 Certifications (cond)    9 Awards (optional)

    Sections 8 and 9 are omitted entirely when data is absent.
    Missing fields render as red [MISSING: X] text via highlight_missing().
    Recency Rule is applied to experience bullets at generation time.

    Returns True on success, False on any exception.
    """
    try:
        page_w, page_h = A4
        margin = 2 * cm
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=margin,
            leftMargin=margin,
            topMargin=margin,
            bottomMargin=margin,
        )

        styles = getSampleStyleSheet()
        teal = colors.HexColor("#1B6B6B")

        title_style = ParagraphStyle(
            "PrintTitle", parent=styles["Heading1"],
            fontName="Helvetica-Bold", fontSize=16, spaceAfter=4,
        )
        name_style = ParagraphStyle(
            "PrintName", parent=title_style, rightIndent=3.5 * cm,
        )
        section_style = ParagraphStyle(
            "PrintSection", parent=styles["Heading2"],
            fontName="Helvetica-Bold", fontSize=11,
            spaceBefore=10, spaceAfter=2, textColor=teal,
        )
        body_style = ParagraphStyle(
            "PrintBody", parent=styles["Normal"],
            fontName="Helvetica", fontSize=9.5, spaceAfter=3, leading=13,
        )
        contact_style = ParagraphStyle("PrintContact", parent=body_style, spaceAfter=2)
        contact_line_style = ParagraphStyle(
            "PrintContactLine", parent=contact_style, rightIndent=3.5 * cm,
        )
        role_title_style = ParagraphStyle(
            "PrintRoleTitle", parent=body_style,
            fontName="Helvetica-Bold", fontSize=9.5, spaceAfter=1,
        )
        role_meta_style = ParagraphStyle(
            "PrintRoleMeta", parent=body_style,
            fontSize=9, textColor=colors.HexColor("#555555"), spaceAfter=2,
        )
        bullet_style = ParagraphStyle(
            "PrintBullet", parent=body_style, leftIndent=12, bulletIndent=4,
        )

        def section_heading(title):
            return [
                Paragraph(title, section_style),
                HRFlowable(width="100%", thickness=0.5, color=teal, spaceAfter=3),
            ]

        pf = json_data.get("print_fields") or {}
        contact = json_data.get("contact") or {}

        # ── Photo setup (same pattern as ATS writer) ──────────────────────
        photo_io = None
        if photo_bytes:
            _raw = process_photo_for_pdf(photo_bytes)
            if _raw:
                try:
                    ImageReader(_raw)
                    _raw.seek(0)
                    photo_io = _raw
                except Exception as e:
                    logger.warning("Print PDF photo rejected: %s", e)

        def _draw_photo_first_page(canvas, doc):
            if not photo_io:
                return
            img_w = img_h = 3 * cm
            radius = 0.2 * cm
            x = page_w - margin - img_w
            y = page_h - margin - img_h
            canvas.saveState()
            p = canvas.beginPath()
            p.roundRect(x, y, img_w, img_h, radius)
            canvas.clipPath(p, stroke=0)
            photo_io.seek(0)
            canvas.drawImage(ImageReader(photo_io), x, y, img_w, img_h)
            canvas.restoreState()

        elements = []

        # ── Section 1 — Personal Details ─────────────────────────────────
        name_text = highlight_missing(json_data.get("candidate_name") or "[MISSING: Name]")
        elements.append(Paragraph(name_text, name_style if photo_io else title_style))

        phone = contact.get("phone") or "[MISSING: Phone]"
        email = contact.get("email") or "[MISSING: Email]"
        contact_line = highlight_missing(f"{phone} | {email}")
        elements.append(Paragraph(contact_line, contact_line_style if photo_io else contact_style))

        gender = pf.get("gender") or "[MISSING: Gender]"
        dob = pf.get("dob") or "[MISSING: Date of Birth]"
        age = pf.get("age") or ""
        city = pf.get("city") or "[MISSING: City]"
        open_relocate = pf.get("open_to_relocate", False)
        notice = pf.get("notice_period") or "[MISSING: Notice Period]"

        dob_age = f"{dob} (Age: {age})" if age else dob
        city_text = f"{city} | Open to Relocate" if open_relocate else city

        for label, value in [
            ("Gender", gender),
            ("DOB", dob_age),
            ("City", city_text),
            ("Notice Period", notice),
        ]:
            elements.append(Paragraph(
                highlight_missing(f"<b>{label}:</b> {value}"),
                body_style,
            ))

        elements.append(Spacer(1, 6))

        # ── Section 2 — Profile Links ─────────────────────────────────────
        elements.extend(section_heading("Profile Links"))
        linkedin = contact.get("linkedin") or "[MISSING: LinkedIn]"
        elements.append(Paragraph(highlight_missing(f"<b>LinkedIn:</b> {linkedin}"), body_style))
        portfolio = pf.get("portfolio_url") or ""
        if portfolio:
            elements.append(Paragraph(highlight_missing(f"<b>Portfolio:</b> {portfolio}"), body_style))

        # ── Section 3 — Professional Summary ─────────────────────────────
        summary = json_data.get("summary") or ""
        if summary:
            elements.extend(section_heading("Professional Summary"))
            elements.append(Paragraph(highlight_missing(summary), body_style))

        # ── Section 4 — Skills ────────────────────────────────────────────
        core_skills = pf.get("core_skills") or []
        tools = pf.get("tools_platforms") or []
        soft = pf.get("soft_skills") or []
        psychometric = pf.get("psychometric_type") or "[MISSING: Psychometric Type]"

        if core_skills or tools or soft:
            elements.extend(section_heading("Skills"))
            if core_skills:
                elements.append(Paragraph(
                    highlight_missing(f"<b>Core Technical:</b> {', '.join(core_skills[:5])}"),
                    body_style,
                ))
            if tools:
                elements.append(Paragraph(
                    highlight_missing(f"<b>Tools & Platforms:</b> {', '.join(tools[:5])}"),
                    body_style,
                ))
            if soft:
                elements.append(Paragraph(
                    highlight_missing(f"<b>Soft Skills:</b> {', '.join(soft[:5])}"),
                    body_style,
                ))
            elements.append(Paragraph(
                highlight_missing(f"<b>Psychometric Type:</b> {psychometric}"),
                body_style,
            ))

        # ── Section 5 — Professional Experience ──────────────────────────
        exp_list = json_data.get("experience") or []
        if exp_list:
            elements.extend(section_heading("Professional Experience"))
            for exp in _apply_recency_rule(exp_list):
                title = highlight_missing(exp.get("title") or "")
                company = highlight_missing(exp.get("company") or "")
                role_city = highlight_missing(exp.get("city") or "")
                dates = highlight_missing(exp.get("dates") or "")
                company_intro = highlight_missing(exp.get("company_intro") or "")

                meta_parts = [p for p in [company, role_city, dates] if p]
                block = [
                    Paragraph(title, role_title_style),
                    Paragraph(" | ".join(meta_parts), role_meta_style),
                ]
                if company_intro:
                    block.append(Paragraph(f"<i>{company_intro}</i>", role_meta_style))
                for b in exp.get("bullets") or []:
                    block.append(Paragraph(f"• {highlight_missing(b)}", bullet_style))
                elements.append(KeepTogether(block))
                elements.append(Spacer(1, 5))

        # ── Section 6 — Education ─────────────────────────────────────────
        edu_list = json_data.get("education") or []
        if edu_list:
            elements.extend(section_heading("Education"))
            for edu in edu_list:
                degree = highlight_missing(edu.get("degree") or "")
                inst = highlight_missing(edu.get("institution") or "")
                year = highlight_missing(edu.get("year") or "")
                elements.append(Paragraph(f"<b>{degree}</b>, {inst} ({year})", body_style))

        # ── Section 7 — Languages ─────────────────────────────────────────
        languages = pf.get("languages") or []
        if languages:
            elements.extend(section_heading("Languages"))
            parts = [
                f"{highlight_missing(la.get('language') or '')} — "
                f"{highlight_missing(la.get('proficiency') or '')}"
                for la in languages
            ]
            elements.append(Paragraph(" | ".join(parts), body_style))

        # ── Section 8 — Certifications (conditional) ─────────────────────
        certs = pf.get("certifications") or []
        if certs:
            elements.extend(section_heading("Certifications"))
            for cert in certs:
                name = highlight_missing(cert.get("name") or "")
                issuer = highlight_missing(cert.get("issuing_body") or "")
                year = highlight_missing(cert.get("year") or "")
                elements.append(Paragraph(f"{name} | {issuer} | {year}", body_style))

        # ── Section 9 — Awards & Recognition (optional) ──────────────────
        awards = pf.get("awards") or []
        if awards:
            elements.extend(section_heading("Awards & Recognition"))
            for award in awards:
                elements.append(Paragraph(highlight_missing(str(award)), body_style))

        doc.build(elements, onFirstPage=_draw_photo_first_page)

        buffer.seek(0)
        output_path.write_bytes(buffer.read())
        buffer.close()

        logger.info("Successfully generated Print PDF: %s", output_path)
        return True

    except Exception as e:
        logger.error("Failed to generate Print PDF: %s", e)
        return False
```

- [ ] **Step 4: Export from app/composer/__init__.py**

Replace the contents of `app/composer/__init__.py` with:

```python
"""
PDF Composer Module

This module takes the LLM's structured JSON output and a photo (optional)
and generates a professionally formatted PDF resume.
"""

from .pdf_writer import generate_resume_pdf
from .print_writer import generate_print_pdf

__all__ = ["generate_resume_pdf", "generate_print_pdf"]
```

- [ ] **Step 5: Run print writer tests**

```
pytest tests/test_print_writer.py -v
```

Expected: All PASS

- [ ] **Step 6: Run full composer suite to confirm no regression**

```
pytest tests/test_composer.py tests/test_print_writer.py -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add app/composer/print_writer.py app/composer/__init__.py tests/test_print_writer.py
git commit -m "[BETA01] add: print_writer.py — JobOS 9-section Print Resume PDF generator

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Wire Print PDF into Review + Revise Pipelines

**Files:**
- Modify: `app/ui/pages/3_Review.py`
- Modify: `app/ui/pages/4_Revise.py`
- Modify: `tests/test_review_pipeline.py`
- Modify: `tests/test_revise_pipeline.py`

- [ ] **Step 1: Add failing test for _run_rewrite_pipeline**

In `tests/test_review_pipeline.py`, find the existing test that calls `_run_rewrite_pipeline` and checks `output_pdf_path`. Add a new test after it:

```python
def test_run_rewrite_pipeline_stores_print_pdf_path(db_and_submission):
    """_run_rewrite_pipeline must generate Print PDF and store output_print_pdf_path."""
    subs_db, sub_id, tmp_path = db_and_submission

    fake_llm_output = {
        "candidate_name": "Alice",
        "contact": {"email": "a@b.com", "phone": "555", "linkedin": ""},
        "summary": "Summary text.",
        "experience": [{"title": "Dev", "company": "Corp", "city": "", "dates": "2020-2023",
                        "company_intro": "", "bullets": ["Built things"]}],
        "education": [{"degree": "BSc", "institution": "Uni", "year": "2015"}],
        "skills": ["Python"],
        "missing_fields": [],
        "print_fields": {
            "gender": "", "dob": "", "age": "", "city": "",
            "open_to_relocate": False, "notice_period": "",
            "portfolio_url": "", "core_skills": [], "tools_platforms": [],
            "soft_skills": [], "psychometric_type": "",
            "languages": [], "certifications": [], "awards": [],
        },
    }
    fake_ats = ATSScore(overall=75, keyword=70, skills=80, structure=75, details={})

    with patch("app.llm.provider.rewrite_resume", return_value=fake_llm_output), \
         patch("app.best_practice.searcher.search_best_practice", return_value="bp"), \
         patch("app.scoring.compute_ats_score", return_value=fake_ats):
        sub = subs_db.get_submission(sub_id)
        _run_rewrite_pipeline(sub, subs_db, tmp_path)

    sub = subs_db.get_submission(sub_id)
    assert sub.output_print_pdf_path is not None
    assert Path(sub.output_print_pdf_path).exists()
```

You will also need to find the `db_and_submission` fixture in `tests/test_review_pipeline.py` — it returns `(subs_db, sub_id, output_dir)`. Check how it is defined and match the unpacking above. If the fixture only returns `(subs_db, sub_id)`, update the test accordingly.

Look at the fixture on lines 40-80 of `tests/test_review_pipeline.py` before writing the test — match the exact return values.

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_review_pipeline.py::test_run_rewrite_pipeline_stores_print_pdf_path -v
```

Expected: FAIL — `sub.output_print_pdf_path` is None

- [ ] **Step 3: Update _run_rewrite_pipeline in 3_Review.py**

In `app/ui/pages/3_Review.py`:

Add import at the top (after `from app.composer.pdf_writer import generate_resume_pdf`):
```python
from app.composer.print_writer import generate_print_pdf
```

In `_run_rewrite_pipeline`, after the existing `ok = generate_resume_pdf(...)` block, add:

```python
    ok = generate_resume_pdf(llm_output, photo_bytes, pdf_path)
    if not ok:
        raise RuntimeError("PDF generation failed")

    print_pdf_path = output_dir / f"{submission.id}_print.pdf"
    print_ok = generate_print_pdf(llm_output, photo_bytes, print_pdf_path)
    if not print_ok:
        logger.warning("Print PDF generation failed for submission %s — ATS PDF unaffected", submission.id)
        print_pdf_path = None

    subs_db.update_submission(submission.id, {
        "llm_output_json": json.dumps(llm_output),
        "ats_score_json": json.dumps(dataclasses.asdict(ats)),
        "output_pdf_path": str(pdf_path),
        **({"output_print_pdf_path": str(print_pdf_path)} if print_pdf_path else {}),
    })
    subs_db.set_status(submission.id, SubmissionStatus.REVIEW_READY)
```

- [ ] **Step 4: Run review pipeline test**

```
pytest tests/test_review_pipeline.py -v
```

Expected: All PASS

- [ ] **Step 5: Add failing test for _run_revision_pipeline**

In `tests/test_revise_pipeline.py`, add a new test (same pattern as Step 1 but for `_run_revision_pipeline`):

```python
def test_run_revision_pipeline_stores_print_pdf_path(db_and_submission):
    """_run_revision_pipeline must regenerate Print PDF and store output_print_pdf_path."""
    subs_db, sub_id, tmp_path = db_and_submission

    fake_llm_output = {
        "candidate_name": "Alice",
        "contact": {"email": "a@b.com", "phone": "555", "linkedin": ""},
        "summary": "Revised summary.",
        "experience": [{"title": "Dev", "company": "Corp", "city": "", "dates": "2020-2023",
                        "company_intro": "", "bullets": ["Revised bullet"]}],
        "education": [{"degree": "BSc", "institution": "Uni", "year": "2015"}],
        "skills": ["Python"],
        "missing_fields": [],
        "print_fields": {
            "gender": "", "dob": "", "age": "", "city": "",
            "open_to_relocate": False, "notice_period": "",
            "portfolio_url": "", "core_skills": [], "tools_platforms": [],
            "soft_skills": [], "psychometric_type": "",
            "languages": [], "certifications": [], "awards": [],
        },
    }
    fake_ats = ATSScore(overall=75, keyword=70, skills=80, structure=75, details={})

    with patch("app.llm.provider.rewrite_resume", return_value=fake_llm_output), \
         patch("app.best_practice.searcher.search_best_practice", return_value="bp"), \
         patch("app.scoring.compute_ats_score", return_value=fake_ats):
        sub = subs_db.get_submission(sub_id)
        _run_revision_pipeline(sub, subs_db, tmp_path, revision_hint="Make it shorter")

    sub = subs_db.get_submission(sub_id)
    assert sub.output_print_pdf_path is not None
    assert Path(sub.output_print_pdf_path).exists()
```

Again: check the exact `db_and_submission` fixture return values in `test_revise_pipeline.py` before writing the test.

- [ ] **Step 6: Run test to verify it fails**

```
pytest tests/test_revise_pipeline.py::test_run_revision_pipeline_stores_print_pdf_path -v
```

Expected: FAIL

- [ ] **Step 7: Update _run_revision_pipeline in 4_Revise.py**

In `app/ui/pages/4_Revise.py`:

Add import:
```python
from app.composer.print_writer import generate_print_pdf
```

In `_run_revision_pipeline`, after `ok = generate_resume_pdf(...)`, add (same pattern as 3_Review.py):

```python
    ok = generate_resume_pdf(llm_output, photo_bytes, pdf_path)
    if not ok:
        raise RuntimeError("PDF generation failed")

    print_pdf_path = output_dir / f"{submission.id}_print.pdf"
    print_ok = generate_print_pdf(llm_output, photo_bytes, print_pdf_path)
    if not print_ok:
        logger.warning("Print PDF generation failed for submission %s — ATS PDF unaffected", submission.id)
        print_pdf_path = None

    updated_raw = (submission.resume_raw_text or "") + f"\n\n[USER-PROVIDED IN REVISION]: {revision_hint}"

    subs_db.update_submission(submission.id, {
        "llm_output_json": json.dumps(llm_output),
        "ats_score_json": json.dumps(dataclasses.asdict(ats)),
        "output_pdf_path": str(pdf_path),
        "resume_raw_text": updated_raw,
        **({"output_print_pdf_path": str(print_pdf_path)} if print_pdf_path else {}),
    })
    subs_db.set_status(submission.id, SubmissionStatus.REVIEW_READY)
```

- [ ] **Step 8: Run revise pipeline test**

```
pytest tests/test_revise_pipeline.py -v
```

Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add app/ui/pages/3_Review.py app/ui/pages/4_Revise.py \
        tests/test_review_pipeline.py tests/test_revise_pipeline.py
git commit -m "[BETA01] add: generate Print PDF in rewrite + revision pipelines

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Download Page — Two Download Buttons

**Files:**
- Modify: `app/ui/pages/6_Download.py`

- [ ] **Step 1: Update _render_clean_download to show both buttons**

In `app/ui/pages/6_Download.py`, replace the entire `_render_clean_download` function:

**Current:**
```python
def _render_clean_download(submission: SubmissionRecord, subs_db: SubmissionsDB) -> None:
    """Serve the clean PDF and set status to DOWNLOADED."""
    st.success("Payment confirmed! Your resume is ready.")
    pdf_path = Path(submission.output_pdf_path or "")
    if not pdf_path.exists():
        st.error("PDF file not found. Please contact support.")
        return

    pdf_bytes = pdf_path.read_bytes()
    clicked = st.download_button(
        label="Download Resume (PDF)",
        data=pdf_bytes,
        file_name="resume.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )
    if clicked and submission.status != SubmissionStatus.DOWNLOADED.value:
        subs_db.set_status(submission.id, SubmissionStatus.DOWNLOADED)
        logger.info("Submission %s marked DOWNLOADED", submission.id)
```

**Replace with:**
```python
def _render_clean_download(submission: SubmissionRecord, subs_db: SubmissionsDB) -> None:
    """Serve both clean PDFs (ATS + Print) and set status to DOWNLOADED."""
    st.success("Payment confirmed! Your resumes are ready.")

    pdf_path = Path(submission.output_pdf_path or "")
    if not pdf_path.exists():
        st.error("ATS resume file not found. Please contact support.")
        return

    col1, col2 = st.columns(2)

    with col1:
        pdf_bytes = pdf_path.read_bytes()
        clicked_ats = st.download_button(
            label="\u2b07 Download ATS Resume",
            data=pdf_bytes,
            file_name="resume_ats.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
            help="Optimised for Applicant Tracking Systems and online job portals.",
        )

    with col2:
        print_path = Path(submission.output_print_pdf_path or "")
        if print_path.exists():
            print_bytes = print_path.read_bytes()
            st.download_button(
                label="\u2b07 Download Print Resume",
                data=print_bytes,
                file_name="resume_print.pdf",
                mime="application/pdf",
                type="secondary",
                use_container_width=True,
                help="Formatted for printing and in-person submission.",
            )
        else:
            st.button(
                "\u2b07 Download Print Resume",
                disabled=True,
                use_container_width=True,
                help="Print version unavailable. Please contact support.",
            )

    if clicked_ats and submission.status != SubmissionStatus.DOWNLOADED.value:
        subs_db.set_status(submission.id, SubmissionStatus.DOWNLOADED)
        logger.info("Submission %s marked DOWNLOADED", submission.id)
```

- [ ] **Step 2: Run full test suite to confirm no regressions**

```
pytest --tb=short -q
```

Expected: All existing tests pass. The download page has no unit tests that exercise `_render_clean_download` directly (it uses `st.*` calls), so no new tests are needed here — the pipeline tests cover the data path.

- [ ] **Step 3: Commit**

```bash
git add app/ui/pages/6_Download.py
git commit -m "[BETA01] add: two download buttons on Download page — ATS + Print

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Final Verification + Push

- [ ] **Step 1: Run full test suite**

```
pytest --tb=short -q
```

Expected: All tests pass. Count should be ≥ 421 (baseline) + new tests added in this plan.

- [ ] **Step 2: Push to origin**

```bash
git push origin feature/phase-02-upload-parse
```

Expected: Render auto-deploys. Wait ~3 minutes for deploy to complete.

- [ ] **Step 3: Smoke test on live URL**

Verify at https://jobos-resume-builder.onrender.com:
1. Upload a short resume + JD → Review page → confirm ATS resume generates cleanly
2. Upload a long resume (10+ roles) → confirm Review page shows resume (not chopped)
3. Accept → Download page → confirm two download buttons appear (ATS + Print)
4. Download ATS PDF → verify not truncated mid-page
5. Download Print PDF → verify 9-section layout

---

## Self-Review Notes

**Spec coverage check:**
- [x] Page chop fix — Task 1
- [x] Schema extension (print_fields, city, company_intro) — Task 3
- [x] New print_writer.py — Task 4
- [x] DB migration + model — Task 2
- [x] Pipeline wiring (3_Review + 4_Revise) — Task 5
- [x] Download page two buttons — Task 6
- [x] ATS pipeline untouched beyond deletion-loop removal — verified: pdf_writer.py changes limited to Task 1 only
- [x] Print PDF failure is non-blocking — Task 5 Step 3/7 uses warning + None guard
- [x] One payment unlocks both — Task 6 shows both buttons in `_render_clean_download` (post-payment state)

**Type consistency:**
- `generate_print_pdf` signature matches usage in Tasks 4 and 5: `(json_data: dict, photo_bytes: bytes | None, output_path: pathlib.Path) -> bool`
- `_apply_recency_rule` and `_extract_start_year` used in both tests and implementation
- `output_print_pdf_path` column name is consistent across models.py, db.py, 3_Review.py, 4_Revise.py, 6_Download.py

**Task 5 note:** The `db_and_submission` fixture in test files returns values that must be verified before writing the test. The plan instructs the implementer to check the fixture definition before unpacking — this prevents a signature mismatch.

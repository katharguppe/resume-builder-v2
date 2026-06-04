# Design: Page Chop Fix + Print Resume Output
**Date:** 2026-05-25
**Branch:** feature/phase-02-upload-parse
**Status:** Approved

---

## Background

Two client observations from beta:

1. **Page chop bug** — long resumes are abruptly cut mid-content at page 2.
2. **Print Resume** — candidate needs a second output: a human-readable "Print" resume following the JobOS Ideal Resume Structure, in addition to the existing ATS resume.

The ATS resume and its entire pipeline are **not touched** except for removing the page deletion bug.

---

## Fix 1 — Page Chop

### Root Cause
`app/composer/pdf_writer.py` lines 257–265 run a `fitz` loop that physically deletes every page beyond page 2 after ReportLab builds the document. This amputates content mid-sentence on long resumes.

### Fix
Remove the `fitz` page-deletion block entirely. ReportLab's `SimpleDocTemplate` handles pagination naturally. The ATS resume will flow to however many pages the content requires with no artificial cap.

**Files changed:** `app/composer/pdf_writer.py` only.
**Risk:** Zero — removing a destructive post-processing step.

---

## Feature — Print Resume

### Design Philosophy (from client PDF)
Every section answers a specific recruiter question. Target: 1 page. Hard limit: 1.5 pages.
No hobbies. No interests. No references. No objective statements.

### Approach: New `app/composer/print_writer.py`
ATS pipeline (`pdf_writer.py`) is byte-for-byte unchanged. Print PDF logic lives in a dedicated module.

---

## Part 1 — Schema Extension

The LLM prompt (`build_finetuning_prompt` in `app/llm/prompt_builder.py`) is extended to request `print_fields` in the same JSON response. All existing ATS fields (`candidate_name`, `contact`, `summary`, `experience`, `education`, `skills`) are **unchanged**.

### New top-level key: `print_fields`

```json
"print_fields": {
  "gender": "",
  "dob": "",
  "age": "",
  "city": "",
  "open_to_relocate": false,
  "notice_period": "",
  "portfolio_url": "",
  "core_skills": [],
  "tools_platforms": [],
  "soft_skills": [],
  "psychometric_type": "",
  "languages": [
    { "language": "", "proficiency": "" }
  ],
  "certifications": [
    { "name": "", "issuing_body": "", "year": "" }
  ],
  "awards": []
}
```

### New fields on each `experience[]` entry (ignored by ATS writer)

```json
"city": "",
"company_intro": ""
```

### Missing field handling
Fields not found in the resume are set to `"[MISSING: <field>]"` (string) or empty list. The existing `highlight_missing()` helper renders these in red in the Print PDF. The Missing Info panel (Phase 6) will surface them to the candidate.

`psychometric_type` cannot be extracted from a resume. It will always be `[MISSING: Psychometric Type]` unless the candidate adds it via revision hint.

---

## Part 2 — Print PDF Writer

**File:** `app/composer/print_writer.py`
**Entry point:** `generate_print_pdf(json_data: dict, photo_bytes: bytes | None, output_path: pathlib.Path) -> bool`

### Layout — 9 Sections (JobOS Ideal Resume Structure)

| Section | Content | Source |
|---|---|---|
| 1 — Personal Details | Name, Mobile, Email, Photo, Gender, DOB+Age, City/Relocate, Notice Period | `candidate_name`, `contact`, `print_fields` |
| 2 — Profile Links | LinkedIn (mandatory), Portfolio/GitHub (optional) | `contact.linkedin`, `print_fields.portfolio_url` |
| 3 — Professional Summary | 50–80 words | `summary` |
| 4 — Skills | Core (≤5), Tools (≤5), Soft (≤5), Psychometric Type | `print_fields.*` |
| 5 — Professional Experience | Designation, Company, City, Company intro, Dates, KPI bullets | `experience[]` + new fields |
| 6 — Education | Degree, Institution, Year (no grades) | `education[]` |
| 7 — Languages | Language + Proficiency | `print_fields.languages` |
| 8 — Certifications | Name, Issuing Body, Year (conditional) | `print_fields.certifications` |
| 9 — Awards & Recognition | One-liners (optional) | `print_fields.awards` |

### Recency Rule (Section 5)
Applied at PDF generation time — no LLM involvement:
- Role index 0 and 1 (latest two): all bullets rendered
- Role index 2+: max 3 bullets
- Roles with start year older than 10 years from current year: max 1 bullet, or omit if no bullets

### Visual Style
- Same teal (`#1B6B6B`) section headings and HR dividers as ATS resume
- Same font stack (Helvetica)
- Same 2cm margins
- Photo: top-right, 3×3cm, rounded corners (reuses `photo_handler.py`)
- Missing fields in red via `highlight_missing()` (imported from `pdf_writer.py`)
- Page limit: The JobOS spec calls for 1.5 pages. **No hard fitz deletion is applied** (that's the bug we just fixed). The Recency Rule is the structural enforcer — it reduces bullet count on older roles so the output naturally fits within 1.5 pages. If content still overflows, it flows gracefully rather than being amputated.

---

## Part 3 — DB Migration

**File:** `app/state/db.py`
Add column via a column-existence check before `ALTER TABLE` (SQLite does not support `ALTER TABLE ... IF NOT EXISTS`). Pattern already used in this codebase: query `PRAGMA table_info(submissions)`, check if column present, run `ALTER TABLE` only if absent.

```python
# In AuthDB / SubmissionsDB._migrate() or equivalent
cols = {row["name"] for row in conn.execute("PRAGMA table_info(submissions)")}
if "output_print_pdf_path" not in cols:
    conn.execute("ALTER TABLE submissions ADD COLUMN output_print_pdf_path TEXT")
```

**File:** `app/state/models.py`
Add field:
```python
output_print_pdf_path: Optional[str] = None
```

---

## Part 4 — Pipeline Changes

### `app/ui/pages/3_Review.py`
After `generate_resume_pdf()` succeeds, call `generate_print_pdf()` with the same `json_data` and `photo_bytes`. Store the path in `output_print_pdf_path`.

### `app/ui/pages/4_Revise.py`
Same pattern — regenerate both PDFs on each revision.

Both calls are independent. If `generate_print_pdf()` fails, log a warning but do not block the ATS flow. The ATS resume is the primary output.

---

## Part 5 — Download Page (`app/ui/pages/6_Download.py`)

After payment confirmed, render two download buttons side by side:

```
[⬇ Download ATS Resume]     [⬇ Download Print Resume]
```

- One payment unlocks both.
- If `output_print_pdf_path` is None or file missing: show the Print button as disabled with caption "Print version unavailable — contact support."
- Status machine unchanged (PAYMENT_CONFIRMED → DOWNLOADED covers both).

---

## Out of Scope

- No changes to ATS scoring logic
- No changes to `pdf_writer.py` beyond removing the deletion loop
- No new payment tier for the Print resume
- No UI changes to Upload, Review, Revise, or Skills pages beyond regenerating the Print PDF

---

## Test Coverage

- Unit test: `generate_print_pdf()` with full data → PDF created
- Unit test: `generate_print_pdf()` with missing fields → `[MISSING]` markers in PDF, returns True
- Unit test: recency rule — role index 2 gets max 3 bullets, role >10 years gets ≤1
- Unit test: page chop fix — long resume generates > 2 pages without truncation
- Integration test: full pipeline generates both PDFs for a submission
- Download page: both buttons present after PAYMENT_CONFIRMED

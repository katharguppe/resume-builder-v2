# Phase 4 Design: Resume Review Page
**Date:** 2026-04-13
**Branch:** feature/phase-02-upload-parse
**Scope:** `app/ui/pages/3_Review.py` + `app/llm/` (provider routing + adapters) + `app/state/` (schema additions)

---

## 1. Goal

Implement the candidate-facing review page that:
- Triggers the LLM rewrite pipeline (PROCESSING → REVIEW_READY)
- Displays ATS score breakdown, missing info panel, JD alignment highlights, and AI-generated resume as structured text
- Offers Accept / Request Revision / Back controls

No live editing. Read-only output. Revision button gated on `revision_count < 3`.

---

## 2. Files Changed

| File | Change Type |
|---|---|
| `app/state/models.py` | Add `llm_output_json`, `output_pdf_path` fields to `SubmissionRecord` |
| `app/state/db.py` | Add `llm_output_json`, `output_pdf_path` columns (ALTER TABLE migration guard); add to `_SUBMISSION_UPDATE_COLUMNS` |
| `app/llm/finetuner.py` | Add `rewrite_resume_deepseek()`, `extract_resume_fields_gemini()`, `extract_jd_fields_gemini()` |
| `app/llm/provider.py` | Add `rewrite_resume()` routing; extend extract routing for gemini |
| `app/ui/pages/3_Review.py` | New file — full review page |

**v1 preserved modules (do not touch):** `app/composer/`, `app/ingestor/`, `app/email_handler/`, `app/best_practice/`

---

## 3. DB Schema Additions

Two new columns in `submissions` table:

```sql
ALTER TABLE submissions ADD COLUMN llm_output_json TEXT;
ALTER TABLE submissions ADD COLUMN output_pdf_path TEXT;
```

Migration guard (same pattern as `ats_score_json` in Phase 3):
```python
existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(submissions)")}
if "llm_output_json" not in existing_cols:
    conn.execute("ALTER TABLE submissions ADD COLUMN llm_output_json TEXT")
if "output_pdf_path" not in existing_cols:
    conn.execute("ALTER TABLE submissions ADD COLUMN output_pdf_path TEXT")
```

`SubmissionRecord` dataclass additions:
```python
llm_output_json: Optional[str]   # JSON string of rewritten resume dict
output_pdf_path: Optional[str]   # path to generated PDF on disk
```

`SubmissionsDB._SUBMISSION_UPDATE_COLUMNS` additions:
```python
"llm_output_json", "output_pdf_path"
```

---

## 4. LLM Provider Layer

### 4a. `finetuner.py` — New Adapter Functions

**`rewrite_resume_deepseek(resume_text, jd_text, best_practice) -> dict`**
- OpenAI-compatible client: `base_url=https://api.deepseek.com`, `api_key=DEEPSEEK_API_KEY`
- Model: `deepseek-chat` (DeepSeek V3)
- Same prompt (`build_finetuning_prompt`), same JSON schema, same retry logic as Claude rewrite
- `max_tokens=4096`

**`extract_resume_fields_gemini(resume_text) -> dict`**
- `google-generativeai` SDK: `genai.configure(api_key=GEMINI_API_KEY)`
- Model: `gemini-2.0-flash` (read from `LLM_EXTRACT_MODEL` env var when provider=gemini)
- Uses `build_resume_fields_prompt`, same retry logic

**`extract_jd_fields_gemini(jd_text) -> dict`**
- Same pattern, uses `build_jd_extraction_prompt`

All three functions: retry up to `MAX_LLM_RETRIES`, raise `ValueError` on exhaustion.

### 4b. `provider.py` — New Routing Function

```python
def rewrite_resume(resume_text: str, jd_text: str, best_practice: str) -> dict:
    provider = os.getenv("LLM_REWRITE_PROVIDER", "claude").lower()
    if provider == "claude":
        return finetuner.rewrite_resume(resume_text, jd_text, best_practice)
    if provider == "deepseek":
        return finetuner.rewrite_resume_deepseek(resume_text, jd_text, best_practice)
    raise NotImplementedError(f"REWRITE provider '{provider}' not implemented.")
```

Extend existing `extract_resume_fields` / `extract_jd_fields`:
```python
# add gemini branch
if provider == "gemini":
    return finetuner.extract_resume_fields_gemini(resume_text)
```

---

## 5. `app/ui/pages/3_Review.py` — Page Design

### 5a. Auth & Guard

- Validate session token (same pattern as `1_Upload.py`)
- If `current_submission_id` not in `st.session_state`: show error + button to Upload page → `st.stop()`
- Load `SubmissionRecord` from `SubmissionsDB`

### 5b. PROCESSING → REVIEW_READY Pipeline

Triggered when `submission.status == "PROCESSING"`:

```
1. Show st.spinner("Generating your AI-tuned resume (~5-10s)...")
2. Load resume_fields = json.loads(submission.resume_fields_json)
3. Load jd_fields    = json.loads(submission.jd_fields_json)
4. job_title = jd_fields.get("job_title", "")
   best_practice = search_best_practice(job_title)   # app/best_practice/searcher.py; falls back to generic template on failure
5. llm_output = provider.rewrite_resume(resume_raw_text, jd_raw_text, best_practice)
   # provider.rewrite_resume routes to finetuner; finetuner calls extract_fields internally for candidate_name
6. ats_score  = compute_ats_score(resume_fields, jd_fields)   # ATSScore dataclass
7. missing    = detect_missing(resume_fields)                  # list[MissingItem]
8. PDF → data/output/{submission_id}_resume.pdf
9. subs_db.update_submission(id, {
       llm_output_json: json.dumps(llm_output),
       ats_score_json:  json.dumps(ats_score.__dict__),  # or dataclasses.asdict
       output_pdf_path: str(pdf_path),
   })
10. subs_db.set_status(id, REVIEW_READY)
11. st.rerun()
```

On any exception: `set_status(ERROR)`, `update_submission({error_message: str(e)})`, `st.error(...)`, `st.stop()`.

### 5c. Review Layout

Two-column layout (`st.columns([2, 3])`):

**Left column — Scoring Panel:**
```
st.metric("ATS Score", f"{ats_score.total}/100")
st.progress(ats_score.keyword_match / 30, "Keyword Match")
st.progress(ats_score.skills_coverage / 30, "Skills Coverage")
st.progress(ats_score.experience_clarity / 20, "Experience Clarity")
st.progress(ats_score.structure_completeness / 20, "Structure")

st.subheader("Missing Info")
for item in missing_items:
    badge = "🔴" if item.severity == "HIGH" else ("🟡" if item.severity == "MEDIUM" else "⚪")
    st.write(f"{badge} **{item.field}** — {item.message}")
```

**Right column — Resume + JD Alignment:**
```
JD Alignment:
  - Required skills: green chip if in resume skills, red if not
  - (derived from jd_fields["required_skills"] vs llm_output["skills"])

Resume Sections (read-only):
  st.subheader("Summary")      → st.write(llm_output["summary"])
  st.subheader("Experience")   → for each role: title, company|dates, bullets
  st.subheader("Education")    → for each: degree, institution, year
  st.subheader("Skills")       → comma-joined

PDF Download:
  st.download_button("Download PDF", pdf_bytes, "resume.pdf", "application/pdf")
```

### 5d. Action Bar

```python
revisions_remaining = 3 - submission.revision_count
col_back, col_revise, col_accept = st.columns([1, 1, 1])

col_back.button("← Back", on_click=lambda: st.switch_page("pages/1_Upload.py"))

if revisions_remaining > 0:
    col_revise.button(
        f"Request Revision ({revisions_remaining} left)",
        on_click=_handle_revision
    )
else:
    col_revise.caption("No revisions remaining")

col_accept.button("✓ Accept Draft", type="primary", on_click=_handle_accept)
```

`_handle_revision`: `set_status(REVISION_REQUESTED)`, `update_submission({revision_count: count+1})` → show info "Revision flow coming in Phase 5" (Phase 5 page not yet built).

`_handle_accept`: `set_status(ACCEPTED)` → show info "Payment flow coming in Phase 10" (Phase 10 page not yet built).

### 5e. Status Guards

If status is not in `{PROCESSING, REVIEW_READY, REVISION_REQUESTED}`:
- Show `st.info(f"Submission status: {status}. Nothing to review.")` + Back button.

---

## 6. Status Machine Impact

```
PROCESSING  →  REVIEW_READY       (triggered on 3_Review.py load)
REVIEW_READY → REVISION_REQUESTED  (Request Revision button)
REVIEW_READY → ACCEPTED            (Accept Draft button)
```

No other status transitions touched in Phase 4.

---

## 7. File Outputs

- Generated PDFs: `data/output/{submission_id}_resume.pdf`
- `data/output/` created with `mkdir(parents=True, exist_ok=True)` on write

---

## 8. Error Handling

| Failure point | Action |
|---|---|
| LLM rewrite raises | set ERROR status, store error_message, st.error, st.stop |
| ATS score raises | same |
| PDF generation fails | set ERROR status, store error_message, st.error, st.stop |
| Submission not found | st.error("Submission not found") + Back button |
| PDF not found on disk (for download) | st.warning("PDF not available — try accepting again") |

---

## 9. Tests (to generate after implementation)

- `tests/test_provider.py` — `rewrite_resume` routing, gemini/deepseek stub branches
- `tests/test_review_page.py` — page logic unit tests (mocked DB + LLM)
- `tests/test_db_submissions.py` — new columns round-trip

All existing 183 tests must remain green.

---

## 10. Out of Scope for Phase 4

- Phase 5 (Revision flow — `4_Revise.py`)
- Phase 10 (Payment / Download — `6_Download.py`)
- Gemini rewrite adapter (Gemini is EXTRACT only; REWRITE default is DeepSeek/Claude)
- Real-time JD keyword diff highlighting beyond skill chip matching

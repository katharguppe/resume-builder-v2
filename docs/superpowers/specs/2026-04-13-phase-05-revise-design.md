# Phase 5 — Revision Request: Design Spec
Date: 2026-04-13
Branch: feature/phase-02-upload-parse

## Scope

`app/ui/pages/4_Revise.py` + LLM layer revision_hint support (`app/llm/`).
No DB schema changes. No changes to `app/ui/pages/3_Review.py` internals beyond
replacing the Phase 5 stub with `st.switch_page("pages/4_Revise.py")`.

## Decisions

| Question | Decision | Reason |
|---|---|---|
| Pipeline location | Own `_run_revision_pipeline` in 4_Revise.py | Zero regression risk; CLAUDE.md §0 — do not rewrite what works |
| revision_hint storage | In-memory only, not persisted to DB | YAGNI — no audit requirement in spec |
| revision_hint required | Yes — blank hint blocked before pipeline runs | Blank hint = identical output = wasted revision slot |
| Post-revision navigation | 4_Revise.py runs pipeline, then switch_page to 3_Review.py | Clean separation: revise page owns collection + re-run, review page owns display |

## Architecture & Data Flow

```
Candidate on 3_Review.py
  → clicks "↺ Request Revision (N left)"
  → DB: revision_count +1, status → REVISION_REQUESTED
  → st.switch_page("pages/4_Revise.py")        ← replaces Phase 5 stub

4_Revise.py
  → auth guard (_require_auth)
  → load submission from current_submission_id
  → guard: status must be REVISION_REQUESTED
  → show current AI draft (collapsible expander, read-only)
  → st.form: text_area("What would you like changed?") + submit button
  → blank hint → st.warning + st.stop()
  → _run_revision_pipeline(submission, subs_db, output_dir, hint)
      → rewrite_resume(resume_text, jd_text, best_practice, revision_hint=hint)
      → compute_ats_score, generate_resume_pdf
      → DB: llm_output_json, ats_score_json, output_pdf_path updated
      → status → REVIEW_READY
  → st.switch_page("pages/3_Review.py")

LLM layer (backward-compatible default hint=""):
  prompt_builder.build_finetuning_prompt(..., revision_hint="")
    → appends "=== REVISION REQUEST ===" block only when hint is non-empty
  finetuner.rewrite_resume(..., revision_hint="")
  finetuner.rewrite_resume_deepseek(..., revision_hint="")
  provider.rewrite_resume(..., revision_hint="")
    → all pass hint through; existing callers unchanged
```

## `4_Revise.py` Page Layout

1. **Auth guard** — `_require_auth()` (same pattern as 3_Review.py)
2. **Load submission** — `current_submission_id` from session_state; error + stop if missing
3. **Status guard** — only proceed if `status == REVISION_REQUESTED`; wrong status → info + back button + stop
4. **Header** — `st.caption("Submission #N | Revision X of 3")`
5. **Current draft** — `st.expander("Current AI Draft", expanded=False)` with inline minimal renderer (name, summary, experience bullets, skills; ~25 lines; not imported from 3_Review.py to avoid fragile Streamlit page imports)
6. **Revision form** — `st.form("revision_form")` containing:
   - `st.text_area("What would you like changed?", height=120)`
   - `st.form_submit_button("↺ Submit Revision")`
   - Blank-hint validation: `st.warning` + `st.stop()`
7. **Pipeline** — `st.spinner("Applying revision (~5-10s)...")` wrapping `_run_revision_pipeline`; errors → `st.error`, set ERROR status, return
8. **Redirect** — `st.switch_page("pages/3_Review.py")`
9. **REVISION_EXHAUSTED belt-and-suspenders** — if `revision_count >= MAX_REVISIONS` and status is not `REVISION_REQUESTED`, show "No revisions remaining" + back button (3_Review.py already prevents reaching this state, but 4_Revise.py must not blindly execute)

## LLM Layer Changes

### `prompt_builder.build_finetuning_prompt`
```python
def build_finetuning_prompt(
    resume_text: str, jd_text: str,
    best_practice_text: str, candidate_name: str,
    revision_hint: str = "",
) -> str:
    ...
    if revision_hint.strip():
        prompt += f"\n\n=== REVISION REQUEST ===\n{revision_hint.strip()}\nApply this feedback when rewriting."
    return prompt.strip()
```

### `finetuner.rewrite_resume` and `rewrite_resume_deepseek`
Add `revision_hint: str = ""` parameter; pass to `build_finetuning_prompt`.

### `provider.rewrite_resume`
Add `revision_hint: str = ""` parameter; pass to both adapters.

## Files Changed

| File | Change |
|---|---|
| `app/llm/prompt_builder.py` | Add `revision_hint=""` param to `build_finetuning_prompt` |
| `app/llm/finetuner.py` | Add `revision_hint=""` to `rewrite_resume` + `rewrite_resume_deepseek` |
| `app/llm/provider.py` | Add `revision_hint=""` to `rewrite_resume` |
| `app/ui/pages/3_Review.py` | Replace stub `st.info(...)` with `st.switch_page("pages/4_Revise.py")` |
| `app/ui/pages/4_Revise.py` | New page (auth guard, draft display, form, pipeline, redirect) |
| `tests/test_revise_pipeline.py` | New — 6 tests for `_run_revision_pipeline` |
| `tests/test_prompt_builder.py` | Extend — 2 tests for revision_hint injection |
| `tests/test_provider_rewrite.py` | Extend — 2 tests for hint pass-through |

## Test Plan

### `tests/test_revise_pipeline.py` (new, 6 tests)
- `test_revision_pipeline_sets_review_ready`
- `test_revision_pipeline_stores_updated_llm_output`
- `test_revision_pipeline_raises_on_llm_failure`
- `test_revision_pipeline_raises_on_pdf_failure`
- `test_revision_pipeline_passes_hint_to_rewrite`
- `test_revision_pipeline_calls_best_practice`

### `tests/test_prompt_builder.py` (extend, 2 new tests)
- `test_build_finetuning_prompt_includes_revision_hint`
- `test_build_finetuning_prompt_no_hint_unchanged`

### `tests/test_provider_rewrite.py` (extend, 2 new tests)
- `test_rewrite_resume_passes_hint_claude`
- `test_rewrite_resume_passes_hint_deepseek`

All existing 204 tests must stay green — all LLM signature changes default to `revision_hint=""`.

## Out of Scope (Phase 5)
- Phase 6 (missing info panel in 4_Revise.py)
- Phase 7+ (skills builder, personalization)
- Payment / download (Phase 10)

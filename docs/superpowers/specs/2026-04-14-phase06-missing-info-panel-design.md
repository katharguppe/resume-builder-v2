# Phase 6 — Missing Information Engine: Design Spec
**Date:** 2026-04-14
**Branch:** feature/phase-02-upload-parse
**Status:** Approved (Option B)

---

## Scope

Extend the existing missing-info scoring engine with section grouping, then build a reusable Streamlit component that renders a severity-ranked, collapsible panel with lightweight click-to-highlight. Show the panel on both the Review page and the Revision page.

This is **informational only** — no auto-editing, no LLM calls.

---

## 1. Model Change — `app/scoring/models.py`

Add a `section` field to `MissingItem` with an empty-string default (fully backwards-compatible with all 15 existing tests):

```python
@dataclass
class MissingItem:
    field: str
    label: str
    severity: str   # "HIGH" | "MEDIUM" | "LOW"
    hint: str
    section: str = ""  # "Experience" | "Education" | "Skills" | "Contact" | "Summary"
```

---

## 2. Scoring Engine — `app/scoring/missing_info.py`

Assign `section` to each of the 6 existing detections. No new detection rules; no changes to existing field names, severity levels, or hints.

| field            | severity | section    |
|------------------|----------|------------|
| work_dates       | HIGH     | Experience |
| current_title    | HIGH     | Contact    |
| achievements     | MEDIUM   | Experience |
| company_names    | MEDIUM   | Experience |
| certifications   | LOW      | Education  |
| social_links     | LOW      | Contact    |

The return order (HIGH → MEDIUM → LOW) is unchanged.

---

## 3. UI Component — `app/ui/components/missing_panel.py`

Single public function:

```python
def render_missing_panel(
    resume_fields: dict,
    resume_raw_text: str,
    key_prefix: str = "",
) -> None
```

### Behaviour

- Calls `detect_missing(resume_fields, resume_raw_text)` internally.
- If no items → `st.success("No critical missing information detected.")`.
- Groups items by severity: HIGH, MEDIUM, LOW (only renders groups that have items).
- Each group rendered as an `st.expander`:
  - HIGH group: `expanded=True` by default.
  - MEDIUM and LOW groups: `expanded=False` by default.
- Each item row inside the expander:
  - Section badge: small grey label showing `item.section`
  - `**item.label**` in bold
  - `— item.hint` as plain text
  - A small `st.button("Focus", key=f"{key_prefix}focus_{item.field}")` that sets
    `st.session_state["highlight_section"] = item.section`

### Group labels

| severity | expander title             |
|----------|---------------------------|
| HIGH     | 🔴 High Priority (n items) |
| MEDIUM   | 🟡 Medium Priority (n items) |
| LOW      | ⚪ Low Priority (n items)  |

---

## 4. Review Page — `3_Review.py`

### Replace inline panel

Remove the existing `_render_missing_panel()` helper. Replace the call site with:

```python
from app.ui.components.missing_panel import render_missing_panel
# ...
render_missing_panel(resume_fields, submission.resume_raw_text or "", key_prefix="review_")
```

### Section highlight in resume renderer

In `_render_resume_text()`, read `st.session_state.get("highlight_section", "")` and prefix the matching section heading with a `⚠ Fix needed here` callout:

- "Experience" → before the **Experience** block
- "Education"  → before the **Education** block
- "Skills"     → before the **Skills** block
- "Summary"    → before the **Summary** block
- "Contact"    → before the contact line

The callout uses `st.warning(f"⚠ {section}: fix needed here")` placed immediately above the section. No change to the actual data rendered.

---

## 5. Revision Page — `4_Revise.py`

Add the panel above the revision form. Gives candidates context on what's missing before they write their hint.

```python
from app.ui.components.missing_panel import render_missing_panel
# ...
resume_fields = json.loads(submission.resume_fields_json or "{}")
render_missing_panel(resume_fields, submission.resume_raw_text or "", key_prefix="revise_")
st.divider()
# ... existing revision form ...
```

No other changes to `4_Revise.py`.

---

## 6. Tests

### Extend `tests/test_missing_info.py`

- Assert each of the 6 items returns the correct `section` value.
- Assert `section` is always a non-empty string.

### New `tests/test_missing_panel.py`

Pure Python, no Streamlit calls. Tests:
- Grouping logic: given a list of `MissingItem` objects, verify items are grouped correctly by severity.
- Empty list path: no items → success path (mock `st.success`).
- `key_prefix` propagation: button keys include the prefix.

Tests use `unittest.mock.patch` to stub `streamlit` calls so no Streamlit runtime is needed.

---

## 7. Module Boundary Compliance (CLAUDE.md §4)

Files touched:
- `app/scoring/models.py` — model field addition
- `app/scoring/missing_info.py` — section assignment
- `app/ui/components/missing_panel.py` — **new**
- `app/ui/pages/3_Review.py` — replace inline helper, add highlight
- `app/ui/pages/4_Revise.py` — add panel call
- `tests/test_missing_info.py` — extend
- `tests/test_missing_panel.py` — **new**

No files outside Phase 6 scope. No v1 preserved modules touched (ingestor, composer, email_handler untouched). No LLM calls. No auto-editing.

---

## 8. What This Does NOT Do

- No auto-editing of resume content
- No LLM calls (pure regex + in-process Python)
- No changes to v1 red-field PDF behaviour (composer untouched)
- No new detection rules beyond the 6 from Phase 3

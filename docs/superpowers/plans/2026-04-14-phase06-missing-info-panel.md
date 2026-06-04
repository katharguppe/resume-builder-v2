# Phase 6 — Missing Information Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `MissingItem` with a `section` field, assign sections in `detect_missing()`, build a reusable collapsible `render_missing_panel()` Streamlit component with click-to-highlight, and wire it into both the Review and Revision pages.

**Architecture:** Pure-Python extension to the scoring model + a new `app/ui/components/missing_panel.py` module. The component groups items by severity using `st.expander`, and sets `st.session_state["highlight_section"]` on Focus button click. The Review page resume renderer reads that key to show a `st.warning` callout above the relevant section.

**Tech Stack:** Python 3.13, Streamlit, `unittest.mock` (for panel tests), pytest

---

## File Map

| Action   | File                                       | Responsibility                                              |
|----------|--------------------------------------------|-------------------------------------------------------------|
| Modify   | `app/scoring/models.py`                    | Add `section: str = ""` to `MissingItem`                    |
| Modify   | `app/scoring/missing_info.py`              | Assign `section` to each of the 6 items                     |
| Create   | `app/ui/components/__init__.py`            | Package marker (empty)                                      |
| Create   | `app/ui/components/missing_panel.py`       | `_group_by_severity()` + `render_missing_panel()`           |
| Modify   | `app/ui/pages/3_Review.py`                 | Replace inline `_render_missing_panel`, add section callout |
| Modify   | `app/ui/pages/4_Revise.py`                 | Add `render_missing_panel()` above revision form            |
| Modify   | `tests/test_missing_info.py`               | Add section-assertion tests                                  |
| Create   | `tests/test_missing_panel.py`              | Tests for grouping logic + mocked render paths              |

---

## Task 1: Add `section` field to `MissingItem`

**Files:**
- Modify: `app/scoring/models.py`
- Modify: `tests/test_missing_info.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_missing_info.py`:

```python
def test_missing_item_has_section_field():
    """MissingItem must accept and store a section value."""
    from app.scoring.models import MissingItem
    item = MissingItem(
        field="work_dates",
        label="Work experience dates",
        severity="HIGH",
        hint="Add dates.",
        section="Experience",
    )
    assert item.section == "Experience"


def test_missing_item_section_defaults_to_empty_string():
    """section field must be optional (backwards-compatible)."""
    from app.scoring.models import MissingItem
    item = MissingItem(field="x", label="x", severity="HIGH", hint="x")
    assert item.section == ""
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_missing_info.py::test_missing_item_has_section_field -v
```
Expected: `TypeError: MissingItem.__init__() got an unexpected keyword argument 'section'`

- [ ] **Step 3: Add `section` field to `MissingItem`**

Open `app/scoring/models.py`. Change:

```python
@dataclass
class MissingItem:
    field: str
    label: str
    severity: str   # "HIGH" | "MEDIUM" | "LOW"
    hint: str
```

To:

```python
@dataclass
class MissingItem:
    field: str
    label: str
    severity: str   # "HIGH" | "MEDIUM" | "LOW"
    hint: str
    section: str = ""  # "Experience" | "Education" | "Skills" | "Contact" | "Summary"
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/test_missing_info.py -v
```
Expected: all existing tests + the 2 new ones pass.

- [ ] **Step 5: Commit**

```bash
git add app/scoring/models.py tests/test_missing_info.py
git commit -m "[PHASE-06] add: section field to MissingItem model"
```

---

## Task 2: Assign sections in `detect_missing()`

**Files:**
- Modify: `app/scoring/missing_info.py`
- Modify: `tests/test_missing_info.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_missing_info.py`:

```python
def test_detect_missing_sections_are_non_empty():
    """Every returned MissingItem must have a non-empty section."""
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(current_title=""), "")
    for item in items:
        assert item.section != "", f"field={item.field!r} has empty section"


def test_detect_missing_work_dates_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(), "no dates here")
    match = next(i for i in items if i.field == "work_dates")
    assert match.section == "Experience"


def test_detect_missing_current_title_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(current_title=""), "Senior Engineer at Acme 2019-2022")
    match = next(i for i in items if i.field == "current_title")
    assert match.section == "Contact"


def test_detect_missing_achievements_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(), "Engineer at Acme Ltd 2019-2022")
    match = next(i for i in items if i.field == "achievements")
    assert match.section == "Experience"


def test_detect_missing_company_names_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(), "Engineer 2019-2022")
    match = next(i for i in items if i.field == "company_names")
    assert match.section == "Experience"


def test_detect_missing_certifications_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(), "Engineer at Acme 2019-2022 reduced latency by 30%")
    match = next(i for i in items if i.field == "certifications")
    assert match.section == "Education"


def test_detect_missing_social_links_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(), "Engineer at Acme 2019-2022 reduced latency by 30%")
    match = next(i for i in items if i.field == "social_links")
    assert match.section == "Contact"
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_missing_info.py::test_detect_missing_sections_are_non_empty -v
```
Expected: `AssertionError: field='work_dates' has empty section`

- [ ] **Step 3: Assign sections in `detect_missing()`**

Open `app/scoring/missing_info.py`. Replace the full body of `detect_missing` with:

```python
def detect_missing(resume_fields: dict, resume_raw_text: str) -> List[MissingItem]:
    """
    Detect missing or weak resume fields. No LLM calls.

    Args:
        resume_fields: Dict from extract_resume_fields.
        resume_raw_text: Full raw text from the resume PDF/DOC.

    Returns:
        List of MissingItem sorted HIGH -> MEDIUM -> LOW.
    """
    if not isinstance(resume_raw_text, str):
        resume_raw_text = ""
    items: List[MissingItem] = []

    # HIGH
    if not _DATE_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="work_dates",
            label="Work experience dates",
            severity="HIGH",
            section="Experience",
            hint="Add start and end year (e.g. 2020-2023) to each role.",
        ))
    if not resume_fields.get("current_title", "").strip():
        items.append(MissingItem(
            field="current_title",
            label="Current job title",
            severity="HIGH",
            section="Contact",
            hint="Add your most recent job title below your name.",
        ))

    # MEDIUM
    if not _ACHIEVEMENT_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="achievements",
            label="Measurable achievements",
            severity="MEDIUM",
            section="Experience",
            hint="Quantify your impact with numbers (e.g. 'Reduced costs by 30%').",
        ))
    if not _COMPANY_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="company_names",
            label="Employer names",
            severity="MEDIUM",
            section="Experience",
            hint="Add the company name next to each role you have held.",
        ))

    # LOW
    if not _CERT_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="certifications",
            label="Certifications",
            severity="LOW",
            section="Education",
            hint="Add any certifications, online courses, or training.",
        ))
    if not _SOCIAL_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="social_links",
            label="LinkedIn / GitHub",
            severity="LOW",
            section="Contact",
            hint="Add your LinkedIn profile URL or GitHub handle.",
        ))

    return items
```

- [ ] **Step 4: Run all missing_info tests**

```
pytest tests/test_missing_info.py -v
```
Expected: all tests pass (existing 15 + new 7 = 22 total).

- [ ] **Step 5: Commit**

```bash
git add app/scoring/missing_info.py tests/test_missing_info.py
git commit -m "[PHASE-06] add: section assignment to detect_missing items"
```

---

## Task 3: Build `app/ui/components/missing_panel.py`

**Files:**
- Create: `app/ui/components/__init__.py`
- Create: `app/ui/components/missing_panel.py`
- Create: `tests/test_missing_panel.py`

- [ ] **Step 1: Write failing tests for the grouping helper**

Create `tests/test_missing_panel.py`:

```python
"""Tests for app/ui/components/missing_panel.py — no Streamlit runtime needed."""
from app.scoring.models import MissingItem


def _item(field, severity, section="Experience"):
    return MissingItem(field=field, label=field, severity=severity,
                       hint="hint", section=section)


# ---------------------------------------------------------------------------
# _group_by_severity
# ---------------------------------------------------------------------------

def test_group_by_severity_empty():
    from app.ui.components.missing_panel import _group_by_severity
    groups = _group_by_severity([])
    assert groups == {"HIGH": [], "MEDIUM": [], "LOW": []}


def test_group_by_severity_single_high():
    from app.ui.components.missing_panel import _group_by_severity
    item = _item("work_dates", "HIGH")
    groups = _group_by_severity([item])
    assert groups["HIGH"] == [item]
    assert groups["MEDIUM"] == []
    assert groups["LOW"] == []


def test_group_by_severity_mixed():
    from app.ui.components.missing_panel import _group_by_severity
    h = _item("work_dates", "HIGH")
    m = _item("achievements", "MEDIUM")
    lo = _item("certifications", "LOW")
    groups = _group_by_severity([h, m, lo])
    assert groups["HIGH"] == [h]
    assert groups["MEDIUM"] == [m]
    assert groups["LOW"] == [lo]


def test_group_by_severity_multiple_same():
    from app.ui.components.missing_panel import _group_by_severity
    h1 = _item("work_dates", "HIGH")
    h2 = _item("current_title", "HIGH", section="Contact")
    groups = _group_by_severity([h1, h2])
    assert len(groups["HIGH"]) == 2


# ---------------------------------------------------------------------------
# render_missing_panel — mocked Streamlit
# ---------------------------------------------------------------------------

def test_render_missing_panel_no_items_calls_success(monkeypatch):
    """When detect_missing returns [], should call st.success."""
    import app.ui.components.missing_panel as mod
    import streamlit as st

    success_calls = []
    monkeypatch.setattr(mod, "detect_missing", lambda *a: [])
    monkeypatch.setattr(st, "success", lambda msg: success_calls.append(msg))

    mod.render_missing_panel({}, "")
    assert len(success_calls) == 1
    assert "No critical" in success_calls[0]


def test_render_missing_panel_calls_expander_for_high(monkeypatch):
    """When HIGH items exist, st.expander must be called."""
    import app.ui.components.missing_panel as mod
    import streamlit as st
    from unittest.mock import MagicMock

    item = _item("work_dates", "HIGH", "Experience")
    monkeypatch.setattr(mod, "detect_missing", lambda *a: [item])

    expander_titles = []
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=None)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    def fake_expander(title, expanded=False):
        expander_titles.append(title)
        return mock_ctx

    monkeypatch.setattr(st, "expander", fake_expander)
    monkeypatch.setattr(st, "columns", lambda spec: [MagicMock(), MagicMock()])

    mod.render_missing_panel({}, "text")
    assert any("High Priority" in t for t in expander_titles)


def test_render_missing_panel_key_prefix_in_button(monkeypatch):
    """Button key must include key_prefix to avoid widget ID collisions."""
    import app.ui.components.missing_panel as mod
    import streamlit as st
    from unittest.mock import MagicMock

    item = _item("work_dates", "HIGH", "Experience")
    monkeypatch.setattr(mod, "detect_missing", lambda *a: [item])

    button_keys = []

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=None)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(st, "expander", lambda *a, **kw: mock_ctx)
    monkeypatch.setattr(st, "columns", lambda spec: [MagicMock(), MagicMock()])

    def fake_button(label, key=None):
        button_keys.append(key)
        return False

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "markdown", lambda *a, **kw: None)

    mod.render_missing_panel({}, "text", key_prefix="review_")
    assert any(k and k.startswith("review_") for k in button_keys)
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_missing_panel.py::test_group_by_severity_empty -v
```
Expected: `ModuleNotFoundError: No module named 'app.ui.components'`

- [ ] **Step 3: Create package marker**

Create `app/ui/components/__init__.py` (empty file):

```python
```

- [ ] **Step 4: Create `missing_panel.py`**

Create `app/ui/components/missing_panel.py`:

```python
"""
Phase 6 - Missing Info Panel
Reusable Streamlit component: severity-ranked collapsible panel with
click-to-highlight. Informational only — no auto-editing.
"""
from typing import Dict, List

import streamlit as st

from app.scoring import detect_missing
from app.scoring.models import MissingItem

_SEVERITY_CONFIG = [
    ("HIGH",   "🔴 High Priority",    True),
    ("MEDIUM", "🟡 Medium Priority",  False),
    ("LOW",    "⚪ Low Priority",      False),
]


def _group_by_severity(items: List[MissingItem]) -> Dict[str, List[MissingItem]]:
    """Group a list of MissingItems by severity key. Pure Python, no Streamlit."""
    groups: Dict[str, List[MissingItem]] = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for item in items:
        if item.severity in groups:
            groups[item.severity].append(item)
    return groups


def render_missing_panel(
    resume_fields: dict,
    resume_raw_text: str,
    key_prefix: str = "",
) -> None:
    """
    Render a severity-ranked collapsible missing-info panel.

    Args:
        resume_fields:   Dict from extract_resume_fields (or DB JSON).
        resume_raw_text: Full raw text from the resume.
        key_prefix:      Prefix for Streamlit widget keys — use different
                         values on each page to avoid duplicate widget IDs.
                         e.g. "review_" on 3_Review.py, "revise_" on 4_Revise.py
    """
    items = detect_missing(resume_fields, resume_raw_text)
    if not items:
        st.success("No critical missing information detected.")
        return

    groups = _group_by_severity(items)

    for severity, label, expanded in _SEVERITY_CONFIG:
        group_items = groups[severity]
        if not group_items:
            continue
        n = len(group_items)
        title = f"{label} ({n} item{'s' if n > 1 else ''})"
        with st.expander(title, expanded=expanded):
            for item in group_items:
                col_text, col_btn = st.columns([4, 1])
                with col_text:
                    st.markdown(
                        f"`{item.section}` **{item.label}** — {item.hint}"
                    )
                with col_btn:
                    if st.button(
                        "Focus",
                        key=f"{key_prefix}focus_{item.field}",
                    ):
                        st.session_state["highlight_section"] = item.section
```

- [ ] **Step 5: Run all panel tests**

```
pytest tests/test_missing_panel.py -v
```
Expected: all 7 tests pass.

- [ ] **Step 6: Run full suite to confirm nothing broken**

```
pytest -v --tb=short
```
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/ui/components/__init__.py app/ui/components/missing_panel.py tests/test_missing_panel.py
git commit -m "[PHASE-06] add: missing_panel component with severity groups and click-to-highlight"
```

---

## Task 4: Update `3_Review.py` — replace inline panel + add section highlight

**Files:**
- Modify: `app/ui/pages/3_Review.py`

No new unit tests needed — `_render_resume_text` is a Streamlit render helper with no independently testable logic. The component itself is tested in Task 3.

- [ ] **Step 1: Add import for new component**

In `app/ui/pages/3_Review.py`, find the existing imports block and add:

```python
from app.ui.components.missing_panel import render_missing_panel
```

The existing import line for detect_missing can be kept (still used in the now-removed inline helper removal check) — actually, after removing `_render_missing_panel`, `detect_missing` will no longer be imported directly by this file. Change:

```python
from app.scoring import compute_ats_score, detect_missing
```

To:

```python
from app.scoring import compute_ats_score
```

- [ ] **Step 2: Remove `_render_missing_panel` helper**

Delete the entire function from `3_Review.py` (lines 123–133):

```python
def _render_missing_panel(resume_fields: dict, resume_raw_text: str) -> None:
    """Render missing info panel (severity ranked) below ATS score."""
    missing_items = detect_missing(resume_fields, resume_raw_text)
    if not missing_items:
        st.success("No critical missing information detected.")
        return
    st.subheader("Missing Info")
    for item in missing_items:
        badge = "🔴" if item.severity == "HIGH" else ("🟡" if item.severity == "MEDIUM" else "⚪")
        st.markdown(f"{badge} **{item.label}** — {item.hint}")
```

- [ ] **Step 3: Replace call site in `main()`**

Find (line ~259):

```python
        _render_missing_panel(resume_fields, submission.resume_raw_text or "")
```

Replace with:

```python
        st.subheader("Missing Info")
        render_missing_panel(resume_fields, submission.resume_raw_text or "", key_prefix="review_")
```

- [ ] **Step 4: Add `_render_section_highlight` helper**

Add this new function immediately before `_render_resume_text`:

```python
def _render_section_highlight(section: str) -> None:
    """Show a callout if this section is focused via missing panel."""
    if st.session_state.get("highlight_section") == section:
        st.warning(f"⚠ Fix needed here: {section}")
```

- [ ] **Step 5: Add callouts to `_render_resume_text`**

Modify `_render_resume_text` to call `_render_section_highlight` before each section block. Full updated function:

```python
def _render_resume_text(llm_output: dict) -> None:
    """Render AI-generated resume as structured read-only text."""
    st.subheader("AI-Generated Resume")

    name = llm_output.get("candidate_name", "")
    contact = llm_output.get("contact", {})
    if name:
        st.markdown(f"### {name}")
    _render_section_highlight("Contact")
    contact_parts = [
        v for v in [contact.get("email"), contact.get("phone"), contact.get("linkedin")]
        if v
    ]
    if contact_parts:
        st.caption(" | ".join(contact_parts))

    summary = llm_output.get("summary", "")
    _render_section_highlight("Summary")
    if summary:
        st.markdown("**Summary**")
        st.write(summary)

    experience = llm_output.get("experience", [])
    _render_section_highlight("Experience")
    if experience:
        st.markdown("**Experience**")
        for exp in experience:
            st.markdown(
                f"**{exp.get('title', '')}** — {exp.get('company', '')} | {exp.get('dates', '')}"
            )
            for bullet in exp.get("bullets", []):
                st.markdown(f"- {bullet}")

    education = llm_output.get("education", [])
    _render_section_highlight("Education")
    if education:
        st.markdown("**Education**")
        for edu in education:
            st.markdown(
                f"{edu.get('degree', '')}, {edu.get('institution', '')} ({edu.get('year', '')})"
            )

    skills = llm_output.get("skills", [])
    _render_section_highlight("Skills")
    if skills:
        st.markdown("**Skills**")
        st.write(", ".join(skills))
```

- [ ] **Step 6: Run full test suite**

```
pytest -v --tb=short
```
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/ui/pages/3_Review.py
git commit -m "[PHASE-06] refactor: replace inline missing panel with reusable component + section highlight"
```

---

## Task 5: Update `4_Revise.py` — add missing panel above revision form

**Files:**
- Modify: `app/ui/pages/4_Revise.py`

- [ ] **Step 1: Add import**

In `app/ui/pages/4_Revise.py`, add to the imports block:

```python
from app.ui.components.missing_panel import render_missing_panel
```

- [ ] **Step 2: Load `resume_fields` and render panel in `main()`**

Find the section after the revision cap guard and the `st.caption(...)` line (around line 169), just before the `st.title("Request a Revision")` call. Add the panel render. The section currently looks like:

```python
    revisions_used = submission.revision_count or 0
    st.caption(f"Submission #{sub_id} | Revision {revisions_used} of {MAX_REVISIONS}")
    st.title("Request a Revision")

    # ── Current draft (collapsible) ─────────────────────────────────────────
    llm_output = json.loads(submission.llm_output_json or "{}")
```

Change to:

```python
    revisions_used = submission.revision_count or 0
    st.caption(f"Submission #{sub_id} | Revision {revisions_used} of {MAX_REVISIONS}")
    st.title("Request a Revision")

    # ── Missing info panel ──────────────────────────────────────────────────
    resume_fields = json.loads(submission.resume_fields_json or "{}")
    with st.expander("Missing Info — what to address in your revision", expanded=True):
        render_missing_panel(resume_fields, submission.resume_raw_text or "", key_prefix="revise_")
    st.divider()

    # ── Current draft (collapsible) ─────────────────────────────────────────
    llm_output = json.loads(submission.llm_output_json or "{}")
```

- [ ] **Step 3: Run full test suite**

```
pytest -v --tb=short
```
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add app/ui/pages/4_Revise.py
git commit -m "[PHASE-06] add: missing info panel on Revision page"
```

---

## Task 6: Final verification

- [ ] **Step 1: Run full test suite and capture output**

```
pytest -v
```
Expected: all tests pass. Count must be ≥ 214 (prior baseline) + 2 (model) + 7 (missing_info sections) + 7 (panel) = ≥ 230 total. Record exact count.

- [ ] **Step 2: Verify no v1 files were touched**

```bash
git diff HEAD~5 --name-only | grep -E "ingestor|composer|email_handler|best_practice"
```
Expected: no output (none of those paths modified).

- [ ] **Step 3: Checkpoint commit**

```bash
git add -p   # review staged changes one more time
git commit -m "[PHASE-06] checkpoint: missing info panel complete - <N> tests passing"
```
Replace `<N>` with the actual test count from Step 1.

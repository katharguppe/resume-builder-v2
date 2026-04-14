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

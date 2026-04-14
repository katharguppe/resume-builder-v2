"""
Phase 7 — Skills Builder Page

Candidate reviews, edits, and saves the skills section of their AI resume.
Groups are derived in-process from YAML keyword files (Core/Tools/Functional/Domain).
Suggestions come from the JD via the EXTRACT provider.

Session state:
  st.session_state["skills_working"]     : List[str] — live working copy
  st.session_state["skills_suggestions"] : List[str] — JD hints, loaded once
"""
import json
import logging
import os
from pathlib import Path
from typing import List

import streamlit as st

from app.skills import group_skills, suggest_skills
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionStatus

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))


# ── Testable helpers (no st.* calls) ──────────────────────────────────────

def _init_skills_state(llm_output_json_str: str) -> List[str]:
    """Extract skills list from llm_output_json string. Returns [] on any error."""
    try:
        data = json.loads(llm_output_json_str or "{}")
        return list(data.get("skills") or [])
    except (json.JSONDecodeError, TypeError):
        return []


def _save_skills(
    subs_db: SubmissionsDB,
    submission_id: int,
    llm_output_json_str: str,
    new_skills: List[str],
) -> None:
    """
    Patch skills key in llm_output_json and persist to DB.
    All other fields in llm_output_json are preserved unchanged.
    """
    try:
        data = json.loads(llm_output_json_str or "{}")
    except (json.JSONDecodeError, TypeError):
        data = {}
    data["skills"] = new_skills
    subs_db.update_submission(submission_id, {"llm_output_json": json.dumps(data)})


# ── Page entry point ───────────────────────────────────────────────────────

def main():
    st.title("Skills Builder")
    st.caption("Review and refine the skills on your resume.")

    session_token = st.session_state.get("session_token")
    if not session_token:
        st.warning("Please log in first.")
        st.stop()

    auth_db = AuthDB(DB_PATH)
    subs_db = SubmissionsDB(DB_PATH)

    user = auth_db.get_user_by_token(session_token)
    if not user:
        st.warning("Session expired. Please log in again.")
        st.stop()

    submission = subs_db.get_latest_submission(user.id)
    accessible_statuses = {
        SubmissionStatus.REVIEW_READY,
        SubmissionStatus.REVISION_REQUESTED,
        SubmissionStatus.REVISION_EXHAUSTED,
        SubmissionStatus.ACCEPTED,
    }
    if not submission or submission.status not in accessible_statuses:
        st.info("No resume ready yet. Please upload and process your resume first.")
        st.stop()

    # ── Initialise session state (once per page load) ──────────────────────
    if "skills_working" not in st.session_state:
        st.session_state["skills_working"] = _init_skills_state(
            submission.llm_output_json or "{}"
        )
    if "skills_suggestions" not in st.session_state:
        resume_fields = json.loads(submission.resume_fields_json or "{}")
        jd_fields = json.loads(submission.jd_fields_json or "{}")
        with st.spinner("Loading suggestions from your Job Description..."):
            st.session_state["skills_suggestions"] = suggest_skills(jd_fields, resume_fields)

    working: List[str] = st.session_state["skills_working"]
    suggestions: List[str] = st.session_state["skills_suggestions"]

    # ── Layout ─────────────────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        _render_current_skills(working)

    with col_right:
        _render_suggestions(working, suggestions)

    st.divider()
    if st.button("Save Skills", type="primary", use_container_width=True):
        _save_skills(subs_db, submission.id, submission.llm_output_json or "{}", working)
        st.toast("Skills saved.")


def _render_current_skills(working: List[str]) -> None:
    st.subheader("Your Skills")
    groups = group_skills(working)

    for group_name, bucket in [
        ("Core", groups.core),
        ("Tools", groups.tools),
        ("Functional", groups.functional),
        ("Domain", groups.domain),
    ]:
        with st.expander(f"{group_name} ({len(bucket)})", expanded=True):
            for skill in list(bucket):
                c1, c2 = st.columns([5, 1])
                c1.write(skill)
                if c2.button("x", key=f"remove_{skill}", help=f"Remove {skill}"):
                    if skill in st.session_state["skills_working"]:
                        st.session_state["skills_working"].remove(skill)
                    st.rerun()

    st.divider()
    with st.form("add_skill_form", clear_on_submit=True):
        new_skill = st.text_input("Add a skill", placeholder="e.g. Budget Management")
        if st.form_submit_button("Add") and new_skill.strip():
            if new_skill.strip() not in st.session_state["skills_working"]:
                st.session_state["skills_working"].append(new_skill.strip())
            st.rerun()


def _render_suggestions(working: List[str], suggestions: List[str]) -> None:
    st.subheader("Suggested from JD")
    working_lower = {s.lower() for s in working}
    pending = [s for s in suggestions if s.lower() not in working_lower]

    if not pending:
        st.caption("No additional suggestions — your skills look well-matched to the JD.")
        return

    for suggestion in pending:
        c1, c2 = st.columns([5, 1])
        c1.write(suggestion)
        if c2.button("+", key=f"add_sug_{suggestion}", help=f"Add {suggestion}"):
            if suggestion not in st.session_state["skills_working"]:
                st.session_state["skills_working"].append(suggestion)
            st.rerun()


if __name__ == "__main__":
    main()

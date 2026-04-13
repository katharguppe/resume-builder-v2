"""
Phase 5 - Revision Request Page
Candidate provides a hint for what to change; pipeline re-runs with that hint.
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
from app.scoring import compute_ats_score
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionRecord, SubmissionStatus

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "data/output"))
MAX_REVISIONS = 3  # CLAUDE.md §3: revision cap per session


# ── Pipeline helper (testable, no st.* calls) ─────────────────────────────

def _run_revision_pipeline(
    submission: SubmissionRecord,
    subs_db: SubmissionsDB,
    output_dir: Path,
    revision_hint: str,
) -> None:
    """
    Re-run REWRITE pipeline with a candidate-supplied revision hint.
    Updates llm_output_json, ats_score_json, output_pdf_path, advances to REVIEW_READY.
    Raises on any failure — caller must catch and set ERROR status.
    """
    resume_fields = json.loads(submission.resume_fields_json or "{}")
    jd_fields = json.loads(submission.jd_fields_json or "{}")
    job_title = jd_fields.get("job_title", "")

    best_practice = search_best_practice(job_title)
    llm_output = rewrite_resume(
        submission.resume_raw_text or "",
        submission.jd_raw_text or "",
        best_practice,
        revision_hint=revision_hint,
    )

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


# ── DB helpers ─────────────────────────────────────────────────────────────

def _get_auth_db() -> AuthDB:
    if "auth_db" not in st.session_state:
        st.session_state["auth_db"] = AuthDB(DB_PATH)
    return st.session_state["auth_db"]


def _get_subs_db() -> SubmissionsDB:
    if "subs_db" not in st.session_state:
        st.session_state["subs_db"] = SubmissionsDB(DB_PATH)
    return st.session_state["subs_db"]


def _require_auth():
    """Returns (user_id, token) or calls st.stop()."""
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


def _render_draft(llm_output: dict) -> None:
    """Minimal read-only draft renderer for the expander."""
    name = llm_output.get("candidate_name", "")
    if name:
        st.markdown(f"### {name}")

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

    skills = llm_output.get("skills", [])
    if skills:
        st.markdown("**Skills**")
        st.write(", ".join(skills))


# ── Page entry point ────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="JobOS - Revise", page_icon="↺")

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

    # ── Belt-and-suspenders: only REVISION_REQUESTED may proceed ───────────
    if submission.status != SubmissionStatus.REVISION_REQUESTED.value:
        st.info(f"Submission status: **{submission.status}**. No revision pending.")
        if st.button("← Back to Review"):
            st.switch_page("pages/3_Review.py")
        return

    # ── Revision cap guard (belt-and-suspenders per CLAUDE.md §3) ──────────
    if (submission.revision_count or 0) > MAX_REVISIONS:
        st.warning(f"Maximum revisions ({MAX_REVISIONS}) already used.")
        if st.button("← Back to Review"):
            st.switch_page("pages/3_Review.py")
        return

    revisions_used = submission.revision_count or 0
    st.caption(f"Submission #{sub_id} | Revision {revisions_used} of {MAX_REVISIONS}")
    st.title("Request a Revision")

    # ── Current draft (collapsible) ─────────────────────────────────────────
    llm_output = json.loads(submission.llm_output_json or "{}")
    with st.expander("Current AI Draft", expanded=False):
        _render_draft(llm_output)

    # ── Revision form ───────────────────────────────────────────────────────
    with st.form("revision_form"):
        hint = st.text_area(
            "What would you like changed?",
            height=120,
            placeholder=(
                "e.g. Make the summary more concise. "
                "Emphasise leadership experience. Add AWS keywords."
            ),
        )
        submitted = st.form_submit_button("↺ Submit Revision")

    if submitted:
        if not hint.strip():
            st.warning("Please describe what you'd like changed before submitting.")
            st.stop()

        with st.spinner("Applying revision (~5-10s)..."):
            try:
                _run_revision_pipeline(submission, subs_db, OUTPUT_DIR, hint.strip())
            except Exception as e:
                logger.error(f"Revision pipeline failed for submission #{sub_id}: {e}")
                subs_db.update_submission(submission.id, {"error_message": str(e)})
                subs_db.set_status(submission.id, SubmissionStatus.ERROR)
                st.error(f"Revision failed: {e}")
                return

        st.switch_page("pages/3_Review.py")


main()

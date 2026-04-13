"""
Phase 4 - Review Page
Candidate-facing review: ATS score, missing info, AI-generated resume, accept/revise controls.
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
from app.scoring import compute_ats_score, detect_missing
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionRecord, SubmissionStatus

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "data/output"))
MAX_REVISIONS = 3  # CLAUDE.md §3: revision cap per session


# ── Pipeline helper (testable, no st.* calls) ─────────────────────────────

def _run_rewrite_pipeline(
    submission: SubmissionRecord,
    subs_db: SubmissionsDB,
    output_dir: Path,
) -> None:
    """
    Run PROCESSING → REVIEW_READY pipeline.
    Fetches best practice, calls LLM rewrite, scores, generates PDF,
    persists all outputs to DB, advances status.
    Raises on any failure — caller must catch and set ERROR status.
    """
    resume_fields = json.loads(submission.resume_fields_json or "{}")
    jd_fields = json.loads(submission.jd_fields_json or "{}")
    job_title = jd_fields.get("job_title", "")

    best_practice = search_best_practice(job_title)
    llm_output = rewrite_resume(submission.resume_raw_text or "", submission.jd_raw_text or "", best_practice)

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


# ── DB helpers (cached in session_state) ───────────────────────────────────

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


# ── Render helpers (no st.stop calls) ──────────────────────────────────────

def _render_ats_panel(ats_dict: dict) -> None:
    """Render ATS score breakdown in the left column."""
    total = ats_dict.get("total", 0)
    st.metric("ATS Score", f"{total} / 100")
    st.progress(
        min(ats_dict.get("keyword_match", 0) / 30, 1.0),
        text=f"Keyword Match: {ats_dict.get('keyword_match', 0)}/30",
    )
    st.progress(
        min(ats_dict.get("skills_coverage", 0) / 30, 1.0),
        text=f"Skills Coverage: {ats_dict.get('skills_coverage', 0)}/30",
    )
    st.progress(
        min(ats_dict.get("experience_clarity", 0) / 20, 1.0),
        text=f"Experience Clarity: {ats_dict.get('experience_clarity', 0)}/20",
    )
    st.progress(
        min(ats_dict.get("structure_completeness", 0) / 20, 1.0),
        text=f"Structure: {ats_dict.get('structure_completeness', 0)}/20",
    )


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


def _render_jd_alignment(llm_output: dict, jd_fields: dict) -> None:
    """Show which required JD skills appear in the AI resume."""
    required = jd_fields.get("required_skills", [])
    preferred = jd_fields.get("preferred_skills", [])
    resume_skills_lower = {s.lower() for s in llm_output.get("skills", [])}

    if not required and not preferred:
        return

    st.subheader("JD Alignment")
    all_skills = [(s, "Required") for s in required] + [(s, "Preferred") for s in preferred]
    matched = [s for s, _ in all_skills if s.lower() in resume_skills_lower]
    unmatched = [s for s, _ in all_skills if s.lower() not in resume_skills_lower]

    if matched:
        st.markdown("**Matched:** " + " ".join(f"`{s}`" for s in matched))
    if unmatched:
        st.markdown("**Missing from resume:** " + " ".join(f"`{s}`" for s in unmatched))


def _render_resume_text(llm_output: dict) -> None:
    """Render AI-generated resume as structured read-only text."""
    st.subheader("AI-Generated Resume")

    name = llm_output.get("candidate_name", "")
    contact = llm_output.get("contact", {})
    if name:
        st.markdown(f"### {name}")
    contact_parts = [
        v for v in [contact.get("email"), contact.get("phone"), contact.get("linkedin")]
        if v
    ]
    if contact_parts:
        st.caption(" | ".join(contact_parts))

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

    education = llm_output.get("education", [])
    if education:
        st.markdown("**Education**")
        for edu in education:
            st.markdown(
                f"{edu.get('degree', '')}, {edu.get('institution', '')} ({edu.get('year', '')})"
            )

    skills = llm_output.get("skills", [])
    if skills:
        st.markdown("**Skills**")
        st.write(", ".join(skills))


# ── Page entry point ────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="JobOS - Review", page_icon="📄")

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

    status = submission.status

    # ── PROCESSING: run pipeline ────────────────────────────────────────────
    if status == SubmissionStatus.PROCESSING.value:
        with st.spinner("Generating your AI-tuned resume (~5-10s)..."):
            try:
                _run_rewrite_pipeline(submission, subs_db, OUTPUT_DIR)
            except Exception as e:
                logger.error(f"Pipeline failed for submission #{sub_id}: {e}")
                subs_db.update_submission(submission.id, {"error_message": str(e)})
                subs_db.set_status(submission.id, SubmissionStatus.ERROR)
                st.error(f"Failed to generate resume: {e}")
                return
        st.rerun()

    # ── Status guard ────────────────────────────────────────────────────────
    _REVIEWABLE = {SubmissionStatus.REVIEW_READY.value, SubmissionStatus.REVISION_REQUESTED.value}
    if status not in _REVIEWABLE:
        st.info(f"Submission status: **{status}**. Nothing to review yet.")
        if st.button("← Back to Upload"):
            st.switch_page("pages/1_Upload.py")
        return

    # ── Load persisted data ─────────────────────────────────────────────────
    llm_output = json.loads(submission.llm_output_json or "{}")
    ats_dict = json.loads(submission.ats_score_json or "{}")
    resume_fields = json.loads(submission.resume_fields_json or "{}")
    jd_fields = json.loads(submission.jd_fields_json or "{}")

    st.caption(f"Submission #{sub_id} | Status: {status}")

    # ── Two-column layout ───────────────────────────────────────────────────
    col_left, col_right = st.columns([2, 3])

    with col_left:
        _render_ats_panel(ats_dict)
        st.divider()
        _render_missing_panel(resume_fields, submission.resume_raw_text or "")

    with col_right:
        _render_jd_alignment(llm_output, jd_fields)
        st.divider()
        _render_resume_text(llm_output)

        # PDF download button
        pdf_path = submission.output_pdf_path
        if pdf_path and Path(pdf_path).exists():
            pdf_bytes = Path(pdf_path).read_bytes()
            st.download_button(
                label="⬇ Download PDF",
                data=pdf_bytes,
                file_name=f"resume_{sub_id}.pdf",
                mime="application/pdf",
            )
        else:
            st.caption("PDF not available for download.")

    # ── Action bar ─────────────────────────────────────────────────────────
    st.divider()
    revisions_remaining = MAX_REVISIONS - (submission.revision_count or 0)
    col_back, col_revise, col_accept = st.columns([1, 2, 1])

    with col_back:
        if st.button("← Back"):
            st.switch_page("pages/1_Upload.py")

    with col_revise:
        if revisions_remaining > 0:
            if st.button(f"↺ Request Revision ({revisions_remaining} left)"):
                subs_db.update_submission(submission.id, {
                    "revision_count": (submission.revision_count or 0) + 1,
                })
                subs_db.set_status(submission.id, SubmissionStatus.REVISION_REQUESTED)
                st.switch_page("pages/4_Revise.py")
        else:
            st.caption(f"No revisions remaining (max {MAX_REVISIONS} used).")

    with col_accept:
        if st.button("✓ Accept Draft", type="primary"):
            subs_db.set_status(submission.id, SubmissionStatus.ACCEPTED)
            st.success("Draft accepted! Payment and download will be available in Phase 10.")
            st.rerun()


main()

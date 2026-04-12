"""
Phase 2 - Upload Page
Allows an authenticated user to:
  1. Upload their resume (PDF / DOC / DOCX)
  2. Provide a Job Description (paste text OR upload PDF / DOC / DOCX)
  3. Extract raw text + structured fields from both
  4. Store a Submission record in SQLite linked to their session
"""
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path

import streamlit as st

from app.ingestor.extractor import extract_text, extract_text_and_photo
from app.ingestor.jd_extractor import extract_jd_fields
from app.llm.provider import extract_resume_fields
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionStatus

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))
PHOTOS_DIR = Path("data/photos")


def _get_auth_db() -> AuthDB:
    if "auth_db" not in st.session_state:
        st.session_state["auth_db"] = AuthDB(DB_PATH)
    return st.session_state["auth_db"]


def _get_subs_db() -> SubmissionsDB:
    if "subs_db" not in st.session_state:
        st.session_state["subs_db"] = SubmissionsDB(DB_PATH)
    return st.session_state["subs_db"]


def _require_auth():
    """Stop page render if not authenticated. Returns (user_id, token)."""
    token = st.session_state.get("auth_token")
    if not token:
        st.warning("Please sign in first.")
        st.stop()
    session = _get_auth_db().get_session(token)
    if session is None:
        st.warning("Session expired. Please sign in again.")
        for key in ("auth_token", "auth_email"):
            st.session_state.pop(key, None)
        st.stop()
    return session.user_id, token


def _save_uploaded_to_temp(uploaded_file) -> Path:
    """Write a Streamlit UploadedFile to a named temp file. Caller must unlink."""
    suffix = Path(uploaded_file.name).suffix.lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.read())
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


def _save_photo(photo_bytes: bytes) -> str:
    """Save headshot bytes to data/photos/ and return relative path string."""
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    photo_path = PHOTOS_DIR / f"{uuid.uuid4()}.jpg"
    photo_path.write_bytes(photo_bytes)
    return str(photo_path)


def main():
    st.set_page_config(page_title="JobOS - Upload", page_icon="=")
    st.title("Upload Resume + Job Description")

    user_id, token = _require_auth()
    st.caption(f"Signed in as {st.session_state.get('auth_email', '')}")

    st.subheader("1. Resume")
    resume_file = st.file_uploader(
        "Upload your resume (PDF, DOC, or DOCX)",
        type=["pdf", "doc", "docx"],
        key="resume_uploader",
    )

    st.subheader("2. Job Description")
    jd_tab_paste, jd_tab_file = st.tabs(["Paste Text", "Upload File"])

    with jd_tab_paste:
        jd_text_input = st.text_area(
            "Paste the Job Description here",
            height=200,
            key="jd_text_input",
            placeholder="Copy and paste the full job description...",
        )

    with jd_tab_file:
        jd_file = st.file_uploader(
            "Or upload a JD file (PDF, DOC, DOCX)",
            type=["pdf", "doc", "docx"],
            key="jd_uploader",
        )

    if st.button("Submit", type="primary"):
        if not resume_file:
            st.error("Please upload your resume.")
            st.stop()

        jd_text_final = jd_text_input.strip() if jd_text_input else ""
        if not jd_text_final and not jd_file:
            st.error("Please provide a Job Description (paste text or upload a file).")
            st.stop()

        with st.spinner("Extracting resume text and photo..."):
            resume_tmp = _save_uploaded_to_temp(resume_file)
            try:
                resume_result = extract_text_and_photo(resume_tmp)
                resume_raw = resume_result["text"]
                photo_bytes = resume_result.get("photo_bytes")
            except Exception as e:
                logger.error(f"Resume extraction failed: {e}")
                st.error(f"Could not read resume: {e}")
                st.stop()
            finally:
                resume_tmp.unlink(missing_ok=True)

        if not jd_text_final and jd_file:
            with st.spinner("Extracting Job Description text..."):
                jd_tmp = _save_uploaded_to_temp(jd_file)
                try:
                    jd_text_final = extract_text(jd_tmp)
                except Exception as e:
                    logger.error(f"JD file extraction failed: {e}")
                    st.error(f"Could not read JD file: {e}")
                    st.stop()
                finally:
                    jd_tmp.unlink(missing_ok=True)

        with st.spinner("Extracting resume fields (LLM)..."):
            try:
                resume_fields = extract_resume_fields(resume_raw)
            except Exception as e:
                logger.error(f"Resume LLM extraction failed: {e}")
                st.error(f"Resume field extraction failed: {e}")
                st.stop()

        with st.spinner("Extracting Job Description fields (LLM)..."):
            try:
                jd_fields = extract_jd_fields(jd_text_final)
            except Exception as e:
                logger.error(f"JD LLM extraction failed: {e}")
                st.error(f"JD field extraction failed: {e}")
                st.stop()

        photo_path = None
        if photo_bytes:
            try:
                photo_path = _save_photo(photo_bytes)
            except Exception as e:
                logger.warning(f"Photo save failed (non-fatal): {e}")

        subs_db = _get_subs_db()
        sub_id = subs_db.create_submission(user_id=user_id, session_token=token)
        subs_db.update_submission(sub_id, {
            "resume_raw_text": resume_raw,
            "resume_fields_json": json.dumps(resume_fields),
            "resume_photo_path": photo_path,
            "jd_raw_text": jd_text_final,
            "jd_fields_json": json.dumps(jd_fields),
        })

        st.session_state["current_submission_id"] = sub_id
        candidate_name = resume_fields.get("candidate_name") or "Unknown"
        job_title = jd_fields.get("job_title") or "Unknown"

        st.success(f"Upload complete! Submission #{sub_id} created.")
        st.info(f"Candidate: **{candidate_name}** | Role: **{job_title}**")
        st.caption("Proceed to the next step to view ATS score and review.")


main()

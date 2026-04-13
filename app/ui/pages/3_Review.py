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


# ── Page entry point ────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="JobOS - Review", page_icon="📄")
    st.title("Review Your AI-Tuned Resume")
    st.info("Review page coming soon.")


main()

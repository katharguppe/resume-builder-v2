"""
Phase 10 - Download Page
Payment gate: watermarked preview before payment, clean PDF after Razorpay verification.
"""
import logging
import os
from pathlib import Path

import streamlit as st

from app.payment.provider import get_payment_provider
from app.payment.watermark import watermark_pdf_bytes
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionRecord, SubmissionStatus
from app.ui.pages._download_helpers import (
    build_callback_url,
    get_price_paise,
    has_razorpay_callback,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8501")


# ── DB helpers (session-cached) ────────────────────────────────────────────────

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


# ── Payment helpers ────────────────────────────────────────────────────────────

def _initiate_payment(submission: SubmissionRecord, subs_db: SubmissionsDB) -> str:
    """Create a Razorpay Payment Link, persist link_id, set PAYMENT_PENDING.

    Returns the short_url to open in browser.
    Raises on Razorpay API failure.
    """
    provider = get_payment_provider()
    callback_url = build_callback_url(APP_BASE_URL, submission.id)
    result = provider.create_order(
        amount_paise=get_price_paise(),
        currency="INR",
        reference_id=f"sub_{submission.id}",
        callback_url=callback_url,
    )
    subs_db.update_submission(submission.id, {"payment_link_id": result.link_id})
    subs_db.set_status(submission.id, SubmissionStatus.PAYMENT_PENDING)
    logger.info("Payment link created for submission %s: %s", submission.id, result.link_id)
    return result.short_url


def _verify_and_confirm(submission: SubmissionRecord, subs_db: SubmissionsDB, params: dict) -> bool:
    """Verify Razorpay callback params server-side.

    Security: also checks that the payment_link_id in the callback matches
    what is stored in the DB for this submission — prevents param substitution.

    Returns True if payment confirmed and DB updated, False on any failure.
    """
    stored_link_id = submission.payment_link_id
    callback_link_id = params.get("razorpay_payment_link_id")

    if not stored_link_id or stored_link_id != callback_link_id:
        logger.warning(
            "payment_link_id mismatch for submission %s: stored=%s callback=%s",
            submission.id, stored_link_id, callback_link_id,
        )
        return False

    provider = get_payment_provider()
    if not provider.verify_payment(params):
        logger.warning("Signature verification failed for submission %s", submission.id)
        return False

    payment_id = params.get("razorpay_payment_id", "")
    subs_db.update_submission(submission.id, {"payment_id": payment_id})
    subs_db.set_status(submission.id, SubmissionStatus.PAYMENT_CONFIRMED)
    logger.info("Payment confirmed for submission %s, payment_id=%s", submission.id, payment_id)
    return True


# ── Render helpers ─────────────────────────────────────────────────────────────

def _render_watermarked_preview(submission: SubmissionRecord) -> None:
    """Show watermarked PDF preview and Pay button."""
    price_inr = int(os.getenv("RESUME_DOWNLOAD_PRICE_INR", "99"))
    st.info(f"Your resume is ready. Pay \u20b9{price_inr} to download the clean PDF.")

    pdf_path = Path(submission.output_pdf_path or "")
    if pdf_path.exists():
        watermarked = watermark_pdf_bytes(pdf_path)
        st.download_button(
            label="Preview (watermarked)",
            data=watermarked,
            file_name="resume_preview.pdf",
            mime="application/pdf",
            help="This is a PREVIEW. Pay below to get the clean version.",
        )

    st.markdown("---")
    st.subheader(f"Pay \u20b9{price_inr} to Download")


def _render_pay_button(submission: SubmissionRecord, subs_db: SubmissionsDB) -> None:
    """Render the Pay & Download button. Creates payment link on click."""
    price_inr = int(os.getenv("RESUME_DOWNLOAD_PRICE_INR", "99"))
    if st.button(f"Pay \u20b9{price_inr} & Download", type="primary", use_container_width=True):
        with st.spinner("Creating secure payment link..."):
            try:
                short_url = _initiate_payment(submission, subs_db)
                st.session_state["payment_short_url"] = short_url
            except Exception as e:
                logger.error("Failed to create payment link for submission %s: %s", submission.id, e)
                st.error(f"Payment setup failed: {e}. Please try again.")
                return

    short_url = st.session_state.get("payment_short_url")
    if short_url:
        st.link_button("Open Payment Page", short_url, use_container_width=True)
        st.caption("You will be redirected back here after payment.")


def _render_clean_download(submission: SubmissionRecord, subs_db: SubmissionsDB) -> None:
    """Serve the clean PDF and set status to DOWNLOADED."""
    st.success("Payment confirmed! Your resume is ready.")
    pdf_path = Path(submission.output_pdf_path or "")
    if not pdf_path.exists():
        st.error("PDF file not found. Please contact support.")
        return

    pdf_bytes = pdf_path.read_bytes()
    clicked = st.download_button(
        label="Download Resume (PDF)",
        data=pdf_bytes,
        file_name="resume.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )
    if clicked and submission.status != SubmissionStatus.DOWNLOADED.value:
        subs_db.set_status(submission.id, SubmissionStatus.DOWNLOADED)
        logger.info("Submission %s marked DOWNLOADED", submission.id)


# ── Page entry point ───────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="JobOS - Download", page_icon="\u2b07\ufe0f")
    st.title("Download Your Resume")

    _user_id, _token = _require_auth()
    if not _token:
        return

    subs_db = _get_subs_db()

    sub_id = st.session_state.get("current_submission_id")
    if not sub_id:
        st.error("No active submission. Please upload your resume first.")
        if st.button("Go to Upload"):
            st.switch_page("pages/1_Upload.py")
        return

    submission = subs_db.get_submission(int(sub_id))
    if submission is None:
        st.error(f"Submission #{sub_id} not found.")
        return

    # ── Detect Razorpay callback (redirect back from payment page) ─────────
    query_params = dict(st.query_params)
    callback_sub_id = query_params.get("submission_id")

    if (
        has_razorpay_callback(query_params)
        and submission.status == SubmissionStatus.PAYMENT_PENDING.value
        and str(callback_sub_id) == str(sub_id)
    ):
        with st.spinner("Verifying payment..."):
            confirmed = _verify_and_confirm(submission, subs_db, query_params)
        if confirmed:
            st.query_params.clear()  # clean up URL
            st.rerun()
        else:
            st.error("Payment verification failed. Please try again or contact support.")
            return

    # Reload after possible status change
    submission = subs_db.get_submission(int(sub_id))
    status = submission.status

    # ── Route by status ────────────────────────────────────────────────────
    if status == SubmissionStatus.ACCEPTED.value:
        _render_watermarked_preview(submission)
        _render_pay_button(submission, subs_db)

    elif status == SubmissionStatus.PAYMENT_PENDING.value:
        st.info("Payment pending. Complete payment to download your resume.")
        _render_pay_button(submission, subs_db)

    elif status in (
        SubmissionStatus.PAYMENT_CONFIRMED.value,
        SubmissionStatus.DOWNLOAD_READY.value,
        SubmissionStatus.DOWNLOADED.value,
    ):
        _render_clean_download(submission, subs_db)
        if status == SubmissionStatus.DOWNLOADED.value:
            st.caption("Already downloaded. You can download again above.")

    else:
        st.warning(f"Resume not ready for download yet. Current status: **{status}**")
        if st.button("\u2190 Back to Review"):
            st.switch_page("pages/3_Review.py")


main()

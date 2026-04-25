"""
Pure helper functions for 6_Download.py — no Streamlit calls, fully testable.
"""
import os


_RAZORPAY_CALLBACK_KEYS = frozenset({
    "razorpay_payment_id",
    "razorpay_payment_link_id",
    "razorpay_payment_link_reference_id",
    "razorpay_payment_link_status",
    "razorpay_signature",
})


def build_callback_url(base_url: str, submission_id: int) -> str:
    """Build the Razorpay callback URL for this submission.

    Razorpay appends its own params to this URL on redirect.
    """
    base = base_url.rstrip("/")
    return f"{base}/6_Download?submission_id={submission_id}"


def has_razorpay_callback(query_params: dict) -> bool:
    """Return True if all Razorpay callback params are present in query_params."""
    return _RAZORPAY_CALLBACK_KEYS.issubset(query_params.keys())


def get_price_paise() -> int:
    """Return price in paise (INR × 100) from env var RESUME_DOWNLOAD_PRICE_INR."""
    return int(os.getenv("RESUME_DOWNLOAD_PRICE_INR", "99")) * 100

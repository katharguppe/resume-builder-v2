"""
Provider routing layer for LLM calls.

EXTRACT provider: set LLM_EXTRACT_PROVIDER env var
  claude   → Claude Haiku  (extract_resume_fields_claude / extract_jd_fields_claude)
  gemini   → Gemini Flash  (extract_resume_fields_gemini / extract_jd_fields_gemini)

REWRITE provider: set LLM_REWRITE_PROVIDER env var
  claude   → Claude Sonnet (rewrite_resume in finetuner)
  deepseek → DeepSeek V3   (rewrite_resume_deepseek in finetuner)
"""
import logging
import os

from app.llm.finetuner import (
    extract_resume_fields_claude,
    extract_jd_fields_claude,
    extract_resume_fields_gemini,
    extract_jd_fields_gemini,
    rewrite_resume as rewrite_resume_claude,
    rewrite_resume_deepseek,
)

logger = logging.getLogger(__name__)


def extract_resume_fields(resume_text: str) -> dict:
    """Route resume field extraction to the configured EXTRACT provider."""
    provider = os.getenv("LLM_EXTRACT_PROVIDER", "claude").lower()
    if provider == "claude":
        return extract_resume_fields_claude(resume_text)
    if provider == "gemini":
        return extract_resume_fields_gemini(resume_text)
    raise NotImplementedError(
        f"EXTRACT provider '{provider}' is not implemented. "
        "Set LLM_EXTRACT_PROVIDER=claude or LLM_EXTRACT_PROVIDER=gemini."
    )


def extract_jd_fields(jd_text: str) -> dict:
    """Route JD field extraction to the configured EXTRACT provider."""
    provider = os.getenv("LLM_EXTRACT_PROVIDER", "claude").lower()
    if provider == "claude":
        return extract_jd_fields_claude(jd_text)
    if provider == "gemini":
        return extract_jd_fields_gemini(jd_text)
    raise NotImplementedError(
        f"EXTRACT provider '{provider}' is not implemented. "
        "Set LLM_EXTRACT_PROVIDER=claude or LLM_EXTRACT_PROVIDER=gemini."
    )


def rewrite_resume(resume_text: str, jd_text: str, best_practice: str) -> dict:
    """Route resume rewriting to the configured REWRITE provider."""
    provider = os.getenv("LLM_REWRITE_PROVIDER", "claude").lower()
    if provider == "claude":
        return rewrite_resume_claude(resume_text, jd_text, best_practice)
    if provider == "deepseek":
        return rewrite_resume_deepseek(resume_text, jd_text, best_practice)
    raise NotImplementedError(
        f"REWRITE provider '{provider}' is not implemented. "
        "Set LLM_REWRITE_PROVIDER=claude or LLM_REWRITE_PROVIDER=deepseek."
    )

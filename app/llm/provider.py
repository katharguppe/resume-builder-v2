"""
Provider routing layer for LLM calls.
Routes extract_* calls based on LLM_EXTRACT_PROVIDER env var.

Supported providers:
  claude   - Claude Haiku (extract) / Claude Sonnet (rewrite). IMPLEMENTED.
  gemini   - Gemini 2.0 Flash. STUB - raises NotImplementedError.
  deepseek - DeepSeek V3. STUB - raises NotImplementedError (rewrite only, future).
"""
import logging
import os

from app.llm.finetuner import (
    extract_resume_fields_claude,
    extract_jd_fields_claude,
)

logger = logging.getLogger(__name__)


def extract_resume_fields(resume_text: str) -> dict:
    """Route resume field extraction to the configured EXTRACT provider."""
    provider = os.getenv("LLM_EXTRACT_PROVIDER", "claude").lower()
    if provider == "claude":
        return extract_resume_fields_claude(resume_text)
    raise NotImplementedError(
        f"EXTRACT provider '{provider}' is not implemented. "
        "Set LLM_EXTRACT_PROVIDER=claude or add the adapter to finetuner.py."
    )


def extract_jd_fields(jd_text: str) -> dict:
    """Route JD field extraction to the configured EXTRACT provider."""
    provider = os.getenv("LLM_EXTRACT_PROVIDER", "claude").lower()
    if provider == "claude":
        return extract_jd_fields_claude(jd_text)
    raise NotImplementedError(
        f"EXTRACT provider '{provider}' is not implemented. "
        "Set LLM_EXTRACT_PROVIDER=claude or add the adapter to finetuner.py."
    )

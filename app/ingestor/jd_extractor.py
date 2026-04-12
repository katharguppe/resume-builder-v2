"""
JD field extraction - ingestor layer.
Delegates to app.llm.provider so LLM_EXTRACT_PROVIDER controls routing.
"""
import logging
from app.llm import provider

logger = logging.getLogger(__name__)


def extract_jd_fields(jd_text: str) -> dict:
    """
    Extract structured fields from a Job Description string.

    Returns dict with keys:
        job_title, company, required_skills, preferred_skills,
        experience_required, education_required, key_responsibilities

    Raises ValueError if the LLM returns malformed JSON after max retries.
    Raises NotImplementedError if LLM_EXTRACT_PROVIDER is not yet implemented.
    """
    logger.info("Extracting JD fields via provider")
    return provider.extract_jd_fields(jd_text)

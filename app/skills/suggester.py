"""
Skills suggester — surfaces JD-relevant skills missing from the resume.

Two-stage approach:
  Stage 1: Set-difference between jd_fields skills and resume skills (no LLM).
  Stage 2: LLM enrichment via EXTRACT provider (Gemini Flash or Claude Haiku).

If Stage 2 fails for any reason, Stage 1 results are returned (graceful degradation).
Suggestions are hints only — the candidate controls the final list.
"""
import json
import logging
import os
import re
from typing import List

logger = logging.getLogger(__name__)

MAX_SUGGESTIONS = 10
_MAX_LLM_SUGGESTIONS = 8


def _normalise(s: str) -> str:
    return s.lower().strip()


def _stage1_diff(jd_fields: dict, resume_fields: dict) -> List[str]:
    """
    Return JD skills not already present in the resume (case-insensitive).
    Covers both required_skills and preferred_skills from jd_fields.
    """
    required = jd_fields.get("required_skills") or []
    preferred = jd_fields.get("preferred_skills") or []
    jd_all = required + preferred

    resume_normalised = {_normalise(s) for s in (resume_fields.get("skills") or [])}
    return [s for s in jd_all if _normalise(s) not in resume_normalised]

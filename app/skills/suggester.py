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


def _build_suggestion_prompt(jd_fields: dict, resume_fields: dict) -> str:
    job_title = jd_fields.get("job_title") or "this role"
    jd_skills = (jd_fields.get("required_skills") or []) + (jd_fields.get("preferred_skills") or [])
    resume_skills = resume_fields.get("skills") or []
    return (
        f"Job title: {job_title}\n"
        f"Job requires: {', '.join(jd_skills)}\n"
        f"Candidate already has: {', '.join(resume_skills)}\n\n"
        f"Suggest up to {_MAX_LLM_SUGGESTIONS} additional skills the candidate could highlight "
        "if they genuinely have them. Only suggest skills relevant to this job and not already listed. "
        "Return a JSON array of strings only. No markdown, no explanation."
    )


def _strip_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.DOTALL)


def _stage2_claude(jd_fields: dict, resume_fields: dict) -> List[str]:
    import anthropic
    from app.config import config
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = _build_suggestion_prompt(jd_fields, resume_fields)
    response = client.messages.create(
        model=config.LLM_EXTRACT_MODEL,
        max_tokens=256,
        system="You are a skills advisor. Respond ONLY with a valid JSON array of strings.",
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(_strip_fences(response.content[0].text))


def _stage2_gemini(jd_fields: dict, resume_fields: dict) -> List[str]:
    import google.generativeai as genai
    from app.config import config
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.LLM_GEMINI_EXTRACT_MODEL)
    prompt = _build_suggestion_prompt(jd_fields, resume_fields)
    response = model.generate_content(prompt)
    return json.loads(_strip_fences(response.text))


def _stage2_llm(jd_fields: dict, resume_fields: dict) -> List[str]:
    """Call EXTRACT provider for additional skill suggestions beyond set-difference."""
    provider = os.getenv("LLM_EXTRACT_PROVIDER", "claude").lower()
    if provider == "gemini":
        return _stage2_gemini(jd_fields, resume_fields)
    return _stage2_claude(jd_fields, resume_fields)


def suggest_skills(jd_fields: dict, resume_fields: dict) -> List[str]:
    """
    Return up to MAX_SUGGESTIONS skills missing from resume but relevant to the JD.

    Stage 1 (no LLM): set-difference of JD required/preferred skills vs resume skills.
    Stage 2 (LLM): EXTRACT provider enrichment for implied/adjacent skills.
    If Stage 2 fails, returns Stage 1 results only (graceful degradation).
    """
    resume_normalised = {_normalise(s) for s in (resume_fields.get("skills") or [])}

    stage1 = _stage1_diff(jd_fields, resume_fields)

    try:
        stage2 = _stage2_llm(jd_fields, resume_fields)
    except Exception as e:
        logger.warning("Stage 2 LLM suggestion failed, using Stage 1 only: %s", e)
        stage2 = []

    seen: set = set(resume_normalised)
    merged: List[str] = []
    for s in stage1 + stage2:
        key = _normalise(s)
        if key not in seen:
            seen.add(key)
            merged.append(s)
        if len(merged) >= MAX_SUGGESTIONS:
            break

    return merged

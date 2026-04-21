import random
import re
from datetime import datetime


# ── Constants ──────────────────────────────────────────────────────────────

_WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "twenty-five": 25, "thirty": 30,
}

_LEVEL_KEYWORDS: dict[str, list[str]] = {
    "senior": [
        "director", "vp", "vice president", "head of", "chief",
        "partner", "principal", "managing director", "executive director",
    ],
    "mid": [
        "manager", "lead", "specialist", "programme manager", "project manager",
    ],
    "early": [
        "associate", "junior", "coordinator", "assistant", "analyst",
        "representative", "officer", "executive",
    ],
    "fresher": [
        "internship", "intern", "trainee", "graduate", "fresher", "entry level", "entry-level",
        "apprentice",
    ],
}


# ── Experience detection helpers ───────────────────────────────────────────

def _sum_experience_months(resume_text: str) -> int | None:
    """
    Attempt to derive total months of experience from resume text.

    Strategy (in order):
      1. Find all year spans (e.g. '2019 - 2023', '2020–Present'); if >= 2 found, sum and return.
      2. Find an explicit phrase like '5+ years experience'; return that value.
      3. Find a written phrase like 'ten years experience'; return that value.
      4. Return None — triggers keyword fallback in detect_experience_level.
    """
    current_year = datetime.now().year
    total_months = 0
    spans_found = 0

    # Pattern 1: year ranges separated by dash/en-dash/em-dash/to
    year_span_re = re.compile(
        r'(\d{4})\s*[-\u2013\u2014to]+\s*(\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)'
    )
    for m in year_span_re.finditer(resume_text):
        start = int(m.group(1))
        end_raw = m.group(2).lower()
        end = current_year if end_raw in ('present', 'current', 'now') else int(m.group(2))
        if 1950 <= start <= current_year and start <= end <= current_year + 1:
            total_months += (end - start) * 12
            spans_found += 1

    if spans_found >= 2:
        return total_months

    # Pattern 2: "X years experience" / "X+ years of experience"
    explicit_re = re.compile(r'(\d+)\+?\s*years?\s*(?:of\s+)?experience', re.IGNORECASE)
    m = explicit_re.search(resume_text)
    if m:
        return int(m.group(1)) * 12

    # Pattern 3: "ten years experience" (written number)
    word_re = re.compile(
        r'\b(' + '|'.join(re.escape(w) for w in _WORD_TO_NUM) + r')\b'
        r'\s*\+?\s*years?\s*(?:of\s+)?experience',
        re.IGNORECASE,
    )
    m = word_re.search(resume_text)
    if m:
        return _WORD_TO_NUM[m.group(1).lower()] * 12

    return None


def _keyword_experience_level(resume_text: str) -> str:
    """
    Fallback level detection via seniority keywords.
    Checks tiers from most specific (senior) to least (fresher).
    Returns "early" if no keywords match.
    """
    text = resume_text.lower()
    for level in ("senior", "mid", "early", "fresher"):
        for kw in _LEVEL_KEYWORDS[level]:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                return level
    return "early"


def detect_experience_level(resume_text: str) -> str:
    """
    Detect candidate experience level from resume text.

    Returns one of: "fresher" | "early" | "mid" | "senior"

    Strategy:
      1. Try duration math via _sum_experience_months.
         If months found: bucket into level by total duration.
      2. Fallback: keyword scan via _keyword_experience_level.
    """
    months = _sum_experience_months(resume_text)
    if months is not None:
        if months < 12:
            return "fresher"
        if months < 48:
            return "early"
        if months < 96:
            return "mid"
        return "senior"
    return _keyword_experience_level(resume_text)


# ── Function type detection ────────────────────────────────────────────────

_FUNCTION_KEYWORDS: dict[str, list[str]] = {
    "technical": [
        "engineer", "developer", "architect", "devops", "software", "data",
        "backend", "frontend", "cloud", "infrastructure", "platform", "security",
        "machine learning", "ml", "ai", "database", "systems", "network",
        "full stack", "fullstack", "sre", "qa",
    ],
    "sales": [
        "sales", "account executive", "account manager", "business development",
        "quota", "pipeline", "revenue", "territory", "conversion", "client",
        "customer success", "commercial", "partnership", "deal", "closing",
        "prospecting", "bdr", "sdr",
    ],
    "operations": [
        "operations", "process", "logistics", "sla", "efficiency",
        "supply chain", "fulfilment", "fulfillment", "warehouse", "procurement",
        "vendor", "compliance", "continuous improvement", "lean",
        "six sigma", "facilities", "scheduling",
    ],
    "academic": [
        "teacher", "lecturer", "curriculum", "research", "academic",
        "faculty", "professor", "instructor", "education", "training",
        "learning", "teaching", "pedagogy", "assessment", "school",
        "university", "college", "classroom",
    ],
}


def detect_function_type(jd_text: str) -> str:
    """
    Detect the function type from a job description.

    Returns one of: "technical" | "sales" | "operations" | "academic" | "general"

    Strategy: count keyword hits per type; highest count wins.
    Tie or zero matches → "general".
    """
    text = jd_text.lower()
    scores: dict[str, int] = {ft: 0 for ft in _FUNCTION_KEYWORDS}
    for ft, keywords in _FUNCTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[ft] += 1
    max_score = max(scores.values())
    if max_score == 0:
        return "general"
    winners = [ft for ft, sc in scores.items() if sc == max_score]
    return winners[0] if len(winners) == 1 else "general"


def build_extraction_prompt(resume_text: str) -> str:
    """
    Minimal prompt for Haiku to extract name, email, phone from a resume.
    """
    return f"""Extract the candidate's name, email address, and phone number from the resume below.

Respond ONLY with valid JSON - no markdown, no explanation:
{{"candidate_name": "string", "email": "string", "phone": "string"}}

Use empty string "" for any field not found in the resume.

=== RESUME ===
{resume_text}""".strip()


def build_jd_extraction_prompt(jd_text: str) -> str:
    """
    Prompt for the EXTRACT provider to pull structured fields from a Job Description.
    Used by jd_extractor.py for Phase 2 upload and Phase 3 ATS scoring.
    """
    return f"""Extract structured fields from the Job Description below.

Respond ONLY with valid JSON matching this schema exactly - no markdown, no explanation:
{{
  "job_title": "string",
  "company": "string",
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "experience_required": "string",
  "education_required": "string",
  "key_responsibilities": ["string"]
}}

Use empty string "" for scalar fields not found. Use [] for list fields not found.

=== JOB DESCRIPTION ===
{jd_text}""".strip()


def build_resume_fields_prompt(resume_text: str) -> str:
    """
    Prompt for the EXTRACT provider to pull structured fields from a resume.
    Returns richer schema than v1 extract_fields() - used for ATS scoring (Phase 3).
    The v1 extract_fields() (name/email/phone only) is preserved separately for backward compat.
    """
    return f"""Extract structured fields from the resume below.

Respond ONLY with valid JSON matching this schema exactly - no markdown, no explanation:
{{
  "candidate_name": "string",
  "email": "string",
  "phone": "string",
  "current_title": "string",
  "skills": ["string"],
  "experience_summary": "string"
}}

Use empty string "" for scalar fields not found. Use [] for skills if none found.

=== RESUME ===
{resume_text}""".strip()


def build_finetuning_prompt(
    resume_text: str,
    jd_text: str,
    best_practice_text: str,
    candidate_name: str,
    revision_hint: str = "",
) -> str:
    """
    Builds the structured prompt for Claude Sonnet to fine-tune a candidate's resume against a JD.
    """
    prompt = f"""
You are an expert technical recruiter and resume writer. Your task is to fine-tune the candidate's resume to better align with the provided Job Description (JD).
You must strictly follow the provided best practice format.

CANDIDATE NAME: {candidate_name}

=== BEST PRACTICE FORMATTING TO FOLLOW ===
{best_practice_text}

=== JOB DESCRIPTION ===
{jd_text}

=== CANDIDATE ORIGINAL RESUME ===
{resume_text}

=== OBJECTIVE ===
Rewrite the candidate's resume to align tightly with the JD.

Rules for every bullet point:
1. Use the EXACT phrasing from the JD wherever possible - if the JD says
   "admissions management", write "admissions management", not "student
   intake coordination".
2. Within each role, put the bullet most directly relevant to the JD first.
3. Do not fabricate facts. Rephrase and reorder only - never invent experience,
   dates, companies, or qualifications not present in the source resume.

=== CRITICAL CONSTRAINT ===
Do not invent, fabricate, or add any experience, qualifications, dates, or companies that are not present in the source resume text. You may rephrase, reorder, and reformat - but you must not add facts.

If a piece of information (such as phone number, email, linkedin, etc) is not in the source resume, you must leave it blank in the relevant field and list it in the `missing_fields` output array.

=== OUTPUT SCHEMA ===
You must respond with ONLY valid JSON matching this schema exactly. No markdown blocks, no conversational text.
{{
  "candidate_name": "{candidate_name}",
  "contact": {{ "email": "string", "phone": "string", "linkedin": "string" }},
  "summary": "string - 3-4 lines, JD-aligned",
  "experience": [ {{ "title": "string", "company": "string", "dates": "string", "bullets": ["string"] }} ],
  "education": [ {{ "degree": "string", "institution": "string", "year": "string" }} ],
  "skills": ["string"],
  "missing_fields": ["string - any field that was blank or unclear in source resume"]
}}
"""
    if revision_hint.strip():
        prompt += f"\n\n=== REVISION REQUEST ===\n{revision_hint.strip()}\nApply this specific feedback when rewriting the resume."

    return prompt.strip()

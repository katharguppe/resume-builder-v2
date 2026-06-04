"""
JobOS Score Rationale — explains ATS score per the JobOS Ideal Resume Structure spec.

Input:  ats_dict (ATSScore serialised to dict), resume_fields (extracted), resume_raw_text
Output: JobOSRationale — tier label, top 3 actions, 5-dimension breakdown

Pure Python. No LLM. No DB writes. All data already available on the Review page.
"""
import re
from dataclasses import dataclass, field
from typing import List

from app.scoring._patterns import _DATE_RE, _COMPANY_RE, _ACHIEVEMENT_RE

# ── Compiled patterns ──────────────────────────────────────────────────────────

_LINKEDIN_RE = re.compile(r"linkedin\.com", re.IGNORECASE)
_YEARS_EXP_RE = re.compile(r"\d+\+?\s*years?\s*(of\s*)?experience", re.IGNORECASE)
_FILLER_RE = re.compile(
    r"\b(passionate|hardworking|team\s*player|results.driven|dynamic|go.getter"
    r"|self.motivated|detail.oriented|proactive|synergy|leverage)\b",
    re.IGNORECASE,
)
_NOTICE_RE = re.compile(
    r"\bnotice\s*period\b|\bimmediately\s*available\b|\bjoining\s*date\b|\bnotice\b",
    re.IGNORECASE,
)
_PROHIBITED_RE = re.compile(
    r"\bhobbies\b|\bpersonal\s*interests\b|\breferences\s*(available)?\b|\bobjective\s*:",
    re.IGNORECASE,
)
_OBJECTIVE_RE = re.compile(r"\b(career\s+)?objective\b", re.IGNORECASE)
_HOBBY_RE = re.compile(r"\bhobbies\b|\bpersonal\s+interests?\b", re.IGNORECASE)
_REFERENCES_RE = re.compile(r"\breferences\b", re.IGNORECASE)


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class CriterionResult:
    label: str
    passed: bool
    note: str = ""      # shown in breakdown
    action: str = ""    # improvement hint when not passed
    weight: int = 1     # higher = surfaces earlier in top-3 actions


@dataclass
class DimensionResult:
    name: str
    weight_pct: int             # as per JobOS spec
    criteria: List[CriterionResult] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.criteria if c.passed)

    @property
    def total_count(self) -> int:
        return len(self.criteria)


@dataclass
class JobOSRationale:
    tier: str
    tier_icon: str
    tier_meaning: str
    top_actions: List[str]          # max 3, ranked by weight then dimension weight
    dimensions: List[DimensionResult]


# ── Tier lookup ────────────────────────────────────────────────────────────────

def _tier(total: int) -> tuple[str, str, str]:
    if total >= 85:
        return "Recruiter Ready", "✅", "Can be submitted as-is"
    if total >= 65:
        return "Strong, Needs Polish", "⚡", "2–3 specific fixes will strengthen this"
    if total >= 40:
        return "Needs Work", "⚠️", "Structural gaps present — revise before submitting"
    return "Incomplete", "❌", "Cannot be submitted in current state"


# ── Dimension builders ─────────────────────────────────────────────────────────

def _dim_completeness(resume_fields: dict, resume_raw_text: str) -> DimensionResult:
    text = resume_raw_text if isinstance(resume_raw_text, str) else ""
    f = resume_fields or {}

    name_ok = bool(f.get("candidate_name", "").strip())
    phone_ok = bool(f.get("phone", "").strip())
    email_ok = bool(f.get("email", "").strip())
    linkedin_ok = bool(_LINKEDIN_RE.search(text))
    notice_ok = bool(_NOTICE_RE.search(text))
    experience_ok = bool(f.get("experience_summary") or _DATE_RE.search(text))
    education_ok = bool(re.search(
        r"\b(bachelor|master|b\.?tech|mba|phd|diploma|degree|b\.?e\.?|m\.?tech"
        r"|b\.?com|b\.?sc|m\.?sc|b\.?a\.?|m\.?a\.?)\b", text, re.IGNORECASE
    ))

    return DimensionResult(
        name="Completeness",
        weight_pct=20,
        criteria=[
            CriterionResult("Name", name_ok,
                            action="Add your full name to the resume header.", weight=4),
            CriterionResult("Phone number", phone_ok,
                            action="Add a mobile number to the contact section.", weight=4),
            CriterionResult("Email address", email_ok,
                            action="Add a professional email address.", weight=4),
            CriterionResult("LinkedIn URL", linkedin_ok,
                            note="" if linkedin_ok else "linkedin.com not detected",
                            action="Add your LinkedIn profile URL (mandatory per JobOS spec).", weight=3),
            CriterionResult("Notice period / availability", notice_ok,
                            action='Add notice period (e.g. "30 days notice" or "Immediately available").', weight=2),
            CriterionResult("Experience section present", experience_ok,
                            action="Add at least one work experience entry with dates.", weight=5),
            CriterionResult("Education section present", education_ok,
                            action="Add your highest qualification (degree, institution, year).", weight=3),
        ],
    )


def _dim_summary(resume_raw_text: str) -> DimensionResult:
    text = resume_raw_text if isinstance(resume_raw_text, str) else ""
    text_lower = text.lower()

    # Detect summary block — find text after a summary heading
    summary_heading = re.search(
        r"\b(professional\s+summary|summary|profile|career\s+profile|about\s+me)\b",
        text_lower,
    )
    summary_text = ""
    if summary_heading:
        # grab up to 200 chars after the heading as a proxy for the summary paragraph
        start = summary_heading.end()
        summary_text = text[start:start + 400].strip()

    summary_present = bool(summary_heading and summary_text)
    word_count = len(summary_text.split()) if summary_text else 0
    word_count_ok = 50 <= word_count <= 80 if summary_present else False
    years_ok = bool(_YEARS_EXP_RE.search(summary_text or text))
    no_filler = not bool(_FILLER_RE.search(text))

    wc_note = f"{word_count} words detected" if summary_present else ""

    return DimensionResult(
        name="Summary Quality",
        weight_pct=15,
        criteria=[
            CriterionResult("Summary section present", summary_present,
                            action="Add a Professional Summary section (50–80 words).", weight=3),
            CriterionResult("Word count 50–80", word_count_ok,
                            note=wc_note,
                            action=f"Adjust summary length to 50–80 words (currently {word_count}).", weight=2),
            CriterionResult("Mentions years of experience", years_ok,
                            action='State your experience span (e.g. "8 years of experience in…").', weight=2),
            CriterionResult("No filler language", no_filler,
                            note="Words like 'passionate', 'dynamic', 'results-driven' detected" if not no_filler else "",
                            action="Remove filler words — replace with concrete achievements.", weight=2),
        ],
    )


def _dim_experience(resume_raw_text: str) -> DimensionResult:
    text = resume_raw_text if isinstance(resume_raw_text, str) else ""

    dates_ok = bool(_DATE_RE.search(text))
    company_ok = bool(_COMPANY_RE.search(text))
    kpi_ok = bool(_ACHIEVEMENT_RE.search(text))
    # Recency rule: heuristic — more content in the first half of experience section
    # Approximation: check if there are quantified bullets at all (full check needs parsing)
    bullets_ok = bool(re.search(r"^\s*[•\-\*]", text, re.MULTILINE))

    return DimensionResult(
        name="Experience Quality",
        weight_pct=35,
        criteria=[
            CriterionResult("Dates in Month-Year format", dates_ok,
                            action='Add start and end dates to every role (e.g. "Jan 2020 – Mar 2023").', weight=5),
            CriterionResult("Company names present", company_ok,
                            action="Add employer names — include company type suffix (Ltd, Pvt, Inc).", weight=4),
            CriterionResult("KPI / quantified bullets", kpi_ok,
                            note="No numbers, %, revenue, or team-size figures detected" if not kpi_ok else "",
                            action="Quantify at least 2 bullets per role (%, revenue, team size, time saved).", weight=5),
            CriterionResult("Bullet-point structure present", bullets_ok,
                            action="Format experience as bullet points, not prose paragraphs.", weight=3),
        ],
    )


def _dim_skills(ats_dict: dict, resume_fields: dict) -> DimensionResult:
    f = resume_fields or {}
    skills = f.get("skills") or []
    skills_count = len(skills) if isinstance(skills, list) else 0
    skills_present = skills_count > 0
    skills_in_limit = skills_count <= 15  # 5 core + 5 tools + 5 soft

    matched = ats_dict.get("skills_matched") or []
    missing = ats_dict.get("skills_missing") or []
    total_jd_skills = len(matched) + len(missing)
    match_rate = len(matched) / total_jd_skills if total_jd_skills else None

    if match_rate is None:
        jd_match_ok = True   # no JD skills to match against
        jd_note = "No required skills listed in JD"
    else:
        jd_match_ok = match_rate >= 0.6
        pct = round(match_rate * 100)
        jd_note = f"{pct}% of JD skills matched ({len(matched)}/{total_jd_skills})"

    missing_note = f"Missing from resume: {', '.join(missing[:5])}" if missing else ""

    return DimensionResult(
        name="Skills Coherence",
        weight_pct=20,
        criteria=[
            CriterionResult("Skills section present", skills_present,
                            action="Add a Skills section with Core Technical, Tools, and Soft Skills.", weight=4),
            CriterionResult("Skills within limits (≤15 total)", skills_in_limit,
                            note=f"{skills_count} skills listed" if not skills_in_limit else "",
                            action="Trim skills to ≤5 core technical + ≤5 tools + ≤5 soft skills.", weight=1),
            CriterionResult("JD skills coverage ≥60%", jd_match_ok,
                            note=jd_note,
                            action=f"Add missing JD skills to your resume: {missing_note}", weight=4),
        ],
    )


def _dim_readability(resume_raw_text: str) -> DimensionResult:
    text = resume_raw_text if isinstance(resume_raw_text, str) else ""

    no_hobbies = not bool(_HOBBY_RE.search(text))
    no_objective = not bool(_OBJECTIVE_RE.search(text))
    no_references = not bool(_REFERENCES_RE.search(text))

    return DimensionResult(
        name="Readability & Structure",
        weight_pct=10,
        criteria=[
            CriterionResult("No hobbies / personal interests section", no_hobbies,
                            action="Remove Hobbies section — recruiters do not read it.", weight=2),
            CriterionResult("No career objective statement", no_objective,
                            action="Replace Objective statement with a Professional Summary.", weight=2),
            CriterionResult("No references section", no_references,
                            action='Remove References section — "Available on request" is assumed.', weight=1),
        ],
    )


# ── Public entry point ─────────────────────────────────────────────────────────

def explain_ats_score(
    ats_dict: dict,
    resume_fields: dict,
    resume_raw_text: str,
) -> JobOSRationale:
    """
    Derive a JobOS-spec rationale from the already-computed ATS score data.

    Args:
        ats_dict:        ATSScore serialised to dict (from DB ats_score_json).
        resume_fields:   Extracted resume fields dict (from DB resume_fields_json).
        resume_raw_text: Original resume plain text (from DB resume_raw_text).

    Returns:
        JobOSRationale with tier, top_actions (max 3), and 5-dimension breakdown.
    """
    total = int(ats_dict.get("total", 0))
    tier, icon, meaning = _tier(total)

    dims = [
        _dim_completeness(resume_fields, resume_raw_text),
        _dim_summary(resume_raw_text),
        _dim_experience(resume_raw_text),
        _dim_skills(ats_dict, resume_fields),
        _dim_readability(resume_raw_text),
    ]

    # Collect all failed criteria, rank by criterion weight × dimension weight_pct
    failed: List[tuple[int, str]] = []
    for dim in dims:
        for c in dim.criteria:
            if not c.passed and c.action:
                priority = c.weight * dim.weight_pct
                failed.append((priority, c.action))

    failed.sort(key=lambda x: x[0], reverse=True)
    top_actions = [action for _, action in failed[:3]]

    return JobOSRationale(
        tier=tier,
        tier_icon=icon,
        tier_meaning=meaning,
        top_actions=top_actions,
        dimensions=dims,
    )

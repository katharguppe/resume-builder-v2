import re
from typing import List

from app.scoring.models import MissingItem
from app.scoring._patterns import _DATE_RE, _COMPANY_RE, _ACHIEVEMENT_RE
_CERT_RE = re.compile(r"\bcertif|\bcourses\b|\btraining\b|\bawards\b|\bachievements\b", re.IGNORECASE)
_SOCIAL_RE = re.compile(r"linkedin\.com|github\.com", re.IGNORECASE)


def detect_missing(resume_fields: dict, resume_raw_text: str) -> List[MissingItem]:
    """
    Detect missing or weak resume fields. No LLM calls.

    Args:
        resume_fields: Dict from extract_resume_fields.
        resume_raw_text: Full raw text from the resume PDF/DOC.

    Returns:
        List of MissingItem sorted HIGH -> MEDIUM -> LOW.
    """
    if not isinstance(resume_raw_text, str):
        resume_raw_text = ""
    items: List[MissingItem] = []

    # HIGH
    if not _DATE_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="work_dates",
            label="Work experience dates",
            severity="HIGH",
            section="Experience",
            hint="Add start and end year (e.g. 2020-2023) to each role.",
        ))
    if not resume_fields.get("current_title", "").strip():
        items.append(MissingItem(
            field="current_title",
            label="Current job title",
            severity="HIGH",
            section="Contact",
            hint="Add your most recent job title below your name.",
        ))

    # MEDIUM
    if not _ACHIEVEMENT_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="achievements",
            label="Measurable achievements",
            severity="MEDIUM",
            section="Experience",
            hint="Quantify your impact with numbers (e.g. 'Reduced costs by 30%').",
        ))
    if not _COMPANY_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="company_names",
            label="Employer names",
            severity="MEDIUM",
            section="Experience",
            hint="Add the company name next to each role you have held.",
        ))

    # LOW
    if not _CERT_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="certifications",
            label="Certifications",
            severity="LOW",
            section="Education",
            hint="Add any certifications, online courses, or training.",
        ))
    if not _SOCIAL_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="social_links",
            label="LinkedIn / GitHub",
            severity="LOW",
            section="Contact",
            hint="Add your LinkedIn profile URL or GitHub handle.",
        ))

    return items

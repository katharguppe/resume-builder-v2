import re
from typing import List

from app.scoring.models import MissingItem

_DATE_RE = re.compile(
    r"\b(19|20)\d{2}\b"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|\b\d{4}\s*-\s*(?:present|current|\d{4})",
    re.IGNORECASE,
)
_COMPANY_RE = re.compile(
    r"\b(?:Ltd|Inc|Corp|LLC|Pvt|GmbH|Limited|Incorporated|Technologies|Solutions|Services)\b",
    re.IGNORECASE,
)
_ACHIEVEMENT_RE = re.compile(
    r"\d+\s*(?:%|x\b|X\b|\$|K\b|M\b|L\b|cr\b|lakh|crore)"
    r"|\d{2,}\s+(?:users|customers|clients|employees|candidates|projects|teams)",
    re.IGNORECASE,
)
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
            hint="Add start and end year (e.g. 2020-2023) to each role.",
        ))
    if not resume_fields.get("current_title", "").strip():
        items.append(MissingItem(
            field="current_title",
            label="Current job title",
            severity="HIGH",
            hint="Add your most recent job title below your name.",
        ))

    # MEDIUM
    if not _ACHIEVEMENT_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="achievements",
            label="Measurable achievements",
            severity="MEDIUM",
            hint="Quantify your impact with numbers (e.g. 'Reduced costs by 30%').",
        ))
    if not _COMPANY_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="company_names",
            label="Employer names",
            severity="MEDIUM",
            hint="Add the company name next to each role you have held.",
        ))

    # LOW
    if not _CERT_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="certifications",
            label="Certifications",
            severity="LOW",
            hint="Add any certifications, online courses, or training.",
        ))
    if not _SOCIAL_RE.search(resume_raw_text):
        items.append(MissingItem(
            field="social_links",
            label="LinkedIn / GitHub",
            severity="LOW",
            hint="Add your LinkedIn profile URL or GitHub handle.",
        ))

    return items

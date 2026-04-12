"""Compiled regex patterns shared by ats_scorer and missing_info."""
import re

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

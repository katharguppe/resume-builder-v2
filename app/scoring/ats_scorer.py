import re
from typing import List, Set, Tuple

from app.scoring.models import ATSScore

_STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for",
    "with", "is", "are", "be", "by", "that", "this", "on",
    "at", "as", "from", "it", "its", "we", "you", "our",
    "will", "have", "has", "do", "does", "not", "but",
}


def _tokenize(text: str) -> Set[str]:
    """Lowercase, split on non-alphanumeric, remove stop-words and single chars."""
    if not isinstance(text, str):
        return set()
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 1}


def _score_keyword_match(
    jd_fields: dict, resume_tokens: Set[str]
) -> Tuple[int, List[str]]:
    """keyword_match: 0-30 pts. Falls back to job_title (max 15) if no responsibilities."""
    responsibilities = jd_fields.get("key_responsibilities") or []

    if not responsibilities:
        job_title = jd_fields.get("job_title", "")
        jd_tokens = _tokenize(job_title)
        if not jd_tokens:
            return 15, []
        matched = [t for t in jd_tokens if t in resume_tokens]
        return min(round(len(matched) / len(jd_tokens) * 15), 15), matched

    jd_tokens: Set[str] = set()
    for resp in responsibilities:
        if isinstance(resp, str):
            jd_tokens.update(_tokenize(resp))

    if not jd_tokens:
        return 15, []

    matched = [t for t in jd_tokens if t in resume_tokens]
    return min(round(len(matched) / len(jd_tokens) * 30), 30), matched


_SKILL_ALIASES = {
    "c++": "cplusplus",
    "c#": "csharp",
    "f#": "fsharp",
    ".net": "dotnet",
    "node.js": "nodejs",
    "vue.js": "vuejs",
    "react.js": "reactjs",
    "next.js": "nextjs",
}


def _normalize_skill(skill: str) -> List[str]:
    """Normalize a skill string for matching.

    Applies known aliases (C++ -> cplusplus, C# -> csharp) first so that
    the + in C++ is consumed before splitting on / + , delimiters.
    """
    if not isinstance(skill, str):
        return []
    lowered = skill.lower().strip()
    for src, dst in _SKILL_ALIASES.items():
        lowered = lowered.replace(src, dst)
    parts = re.split(r"[/+,]", lowered)
    return [re.sub(r"[^a-z0-9\s]", "", p).strip() for p in parts if p.strip()]


def _score_skills_coverage(
    jd_fields: dict, resume_fields: dict
) -> Tuple[int, List[str], List[str]]:
    """skills_coverage: 0-30 pts. Required skills worth 24 pts, preferred 6 pts."""
    required = jd_fields.get("required_skills") or []
    preferred = jd_fields.get("preferred_skills") or []
    resume_skills_raw = resume_fields.get("skills") or []

    if not required and not preferred:
        return 15, [], []

    # Flatten resume skills into normalized parts (words)
    resume_words: Set[str] = set()
    for s in resume_skills_raw:
        parts = _normalize_skill(s)
        for part in parts:
            # Split each normalized part into alphanumeric tokens.
            # e.g., "python 310" -> {"python", "310"}, "nodejs" -> {"nodejs"}
            tokens = re.findall(r"[a-z0-9]+", part)
            resume_words.update(tokens)

    def _matches(jd_skill: str) -> bool:
        jd_parts = _normalize_skill(jd_skill)
        for jd_part in jd_parts:
            # Split JD skill into word tokens
            jd_tokens = re.findall(r"[a-z0-9]+", jd_part)
            for jd_token in jd_tokens:
                # Check if this token appears in resume_words
                if jd_token in resume_words:
                    return True
        return False

    matched: List[str] = []
    missing: List[str] = []
    for skill in required:
        (matched if _matches(skill) else missing).append(skill)

    required_score = round(len(matched) / len(required) * 24) if required else 0
    preferred_matched = sum(1 for s in preferred if _matches(s))
    preferred_score = round(preferred_matched / len(preferred) * 6) if preferred else 0

    return min(required_score + preferred_score, 30), matched, missing


_DATE_RE = re.compile(
    r"\b(19|20)\d{2}\b"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|\d{4}\s*-\s*(?:present|current|\d{4})",
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


def _score_experience_clarity(
    resume_fields: dict, resume_raw_text: str
) -> int:
    """experience_clarity: 0-20 pts based on four heuristic signals."""
    score = 0
    if _DATE_RE.search(resume_raw_text):
        score += 6
    if _COMPANY_RE.search(resume_raw_text):
        score += 5
    if resume_fields.get("current_title", "").strip():
        score += 5
    if _ACHIEVEMENT_RE.search(resume_raw_text):
        score += 4
    return score


def _score_structure_completeness(resume_raw_text: str) -> int:
    """structure_completeness: 0-20 pts based on section header detection."""
    score = 0
    text = resume_raw_text.lower()

    if re.search(r"\b(?:summary|profile|objective|about me|professional summary)\b", text):
        score += 5

    if re.search(r"\b(?:education|academic|qualification)\b", text) and re.search(
        r"\b(?:bachelor|master|b\.?tech|mba|phd|ph\.?d|diploma|degree|b\.?e\.?|m\.?tech)\b", text
    ):
        score += 5

    if re.search(r"\b(?:skills|technical skills|core competencies|technologies)\b", text):
        score += 5

    if re.search(r"\bcertif|\bcourses\b|\btraining\b|\bawards\b|\bachievements\b", text):
        score += 5

    return score


def compute_ats_score(
    resume_fields: dict, jd_fields: dict, resume_raw_text: str
) -> ATSScore:
    """Stub — assembled in Task 5."""
    resume_tokens = _tokenize(resume_raw_text)
    kw_score, kw_matched = _score_keyword_match(jd_fields, resume_tokens)
    sk_score, sk_matched, sk_missing = _score_skills_coverage(jd_fields, resume_fields)
    exp_score = _score_experience_clarity(resume_fields, resume_raw_text)
    struct_score = _score_structure_completeness(resume_raw_text)
    return ATSScore(
        total=kw_score + sk_score + exp_score + struct_score,
        keyword_match=kw_score,
        skills_coverage=sk_score,
        experience_clarity=exp_score,
        structure_completeness=struct_score,
        keyword_matched=kw_matched,
        skills_matched=sk_matched,
        skills_missing=sk_missing,
    )

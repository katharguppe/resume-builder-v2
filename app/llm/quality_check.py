from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("llm.quality_check")

# ── Thresholds (tune without touching logic) ─────────────────────────────────
BULLET_MAX_WORDS = 30
NGRAM_SIZE = 4
WORD_FREQ_THRESHOLD = 4

_STOPWORDS: frozenset[str] = frozenset(
    {"and", "the", "to", "of", "in", "a", "for", "with", "on", "is", "was", "at", "by", "an", "as"}
)

_NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")


@dataclass
class QualityReport:
    passed: bool
    issues: list[str]
    fixed_draft: dict


def _check_bullets_too_long(working_draft: dict) -> list[str]:
    """Trim bullets > BULLET_MAX_WORDS words. Mutates working_draft in place. Returns issues."""
    issues: list[str] = []
    for role in working_draft.get("experience", []) or []:
        if not isinstance(role, dict):
            continue
        role_title = role.get("title", "Unknown Role")
        bullets = role.get("bullets", [])
        if not isinstance(bullets, list):
            continue
        for i, bullet in enumerate(bullets):
            if not isinstance(bullet, str):
                continue
            words = bullet.split()
            if len(words) > BULLET_MAX_WORDS:
                role["bullets"][i] = " ".join(words[:BULLET_MAX_WORDS]) + "…"
                issues.append(
                    f"[AUTO-FIXED] Bullet trimmed to {BULLET_MAX_WORDS} words in role '{role_title}'"
                )
    return issues


def _check_recent_exp_prioritized(working_draft: dict) -> list[str]:
    """Flag if experience[0] has fewer bullets than any other role."""
    experience = working_draft.get("experience", []) or []
    if not isinstance(experience, list) or len(experience) < 2:
        return []

    first_role = experience[0]
    if not isinstance(first_role, dict):
        return []

    first_count = len(first_role.get("bullets", []) or [])
    max_other = max(
        (len(role.get("bullets", []) or []) for role in experience[1:] if isinstance(role, dict)),
        default=0,
    )

    if first_count < max_other:
        return [
            f"[NEEDS REVIEW] Most recent role has fewer bullets than another role "
            f"({first_count} vs {max_other})"
        ]
    return []


def _check_jd_keywords_present(working_draft: dict, jd_fields: dict | None) -> list[str]:
    """Flag required JD skills absent from resume. Skipped entirely when jd_fields is None."""
    if not jd_fields:
        return []

    required_skills = jd_fields.get("required_skills", [])
    if not isinstance(required_skills, list):
        return []

    summary = working_draft.get("summary", "") or ""
    bullets: list[str] = [
        b
        for role in (working_draft.get("experience", []) or [])
        if isinstance(role, dict)
        for b in (role.get("bullets", []) or [])
        if isinstance(b, str)
    ]
    skills: list[str] = [
        s for s in (working_draft.get("skills", []) or []) if isinstance(s, str)
    ]
    full_text = " ".join([summary] + bullets + skills).lower()

    return [
        f"[NEEDS REVIEW] JD keyword missing from resume: '{kw}'"
        for kw in required_skills
        if isinstance(kw, str) and kw.lower() not in full_text
    ]


def _check_experience_exaggerated(
    all_bullets: list[str], summary: str, original_raw_text: str
) -> list[str]:
    """Flag numeric tokens in draft not present in original resume text."""
    # Extract numbers including trailing % if present
    def extract_numbers_with_percent(text: str) -> set[str]:
        nums = set()
        for match in _NUMBER_RE.finditer(text):
            num_str = match.group(0)
            # Check if a % follows immediately after the match
            end_pos = match.end()
            if end_pos < len(text) and text[end_pos] == "%":
                num_str += "%"
            nums.add(num_str)
        return nums

    original_nums = extract_numbers_with_percent(original_raw_text)
    draft_text = " ".join([summary] + all_bullets)
    draft_nums = extract_numbers_with_percent(draft_text)

    return [
        f"[NEEDS REVIEW] Unverified metric not found in original resume: '{num}'"
        for num in draft_nums - original_nums
    ]


def _check_tone_repetitive(summary: str, experience: list[dict]) -> list[str]:
    return []


def validate_quality(
    resume_draft: dict,
    original: dict,
    jd_fields: dict | None = None,
) -> QualityReport:
    """Run all quality checks on resume_draft. Returns QualityReport with auto-fixes applied.

    passed=True only when no [NEEDS REVIEW] issues remain. Auto-fixed issues are
    recorded in issues[] with [AUTO-FIXED] prefix and do not affect passed.
    """
    working_draft = copy.deepcopy(resume_draft)
    summary: str = working_draft.get("summary", "") or ""
    experience: list[dict] = working_draft.get("experience", []) or []
    all_bullets: list[str] = [
        b
        for role in experience
        for b in (role.get("bullets", []) or [])
        if isinstance(b, str)
    ]
    original_raw_text: str = (
        original.get("raw_text", "") if isinstance(original, dict) else ""
    )

    issues: list[str] = []
    checks = [
        (_check_tone_repetitive, (summary, experience)),
        (_check_experience_exaggerated, (all_bullets, summary, original_raw_text)),
        # NOTE: _check_bullets_too_long mutates working_draft in place — must run after
        # read-only checks so all_bullets snapshot (used above) remains untruncated.
        (_check_bullets_too_long, (working_draft,)),
        (_check_recent_exp_prioritized, (working_draft,)),
        (_check_jd_keywords_present, (working_draft, jd_fields)),
    ]
    for check_fn, args in checks:
        try:
            issues.extend(check_fn(*args))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Quality check %s failed: %s", check_fn.__name__, exc)

    passed = not any(i.startswith("[NEEDS REVIEW]") for i in issues)
    return QualityReport(passed=passed, issues=issues, fixed_draft=working_draft)

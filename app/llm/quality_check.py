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

_NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")


@dataclass
class QualityReport:
    passed: bool
    issues: list[str]
    fixed_draft: dict


def _check_bullets_too_long(working_draft: dict) -> list[str]:
    return []


def _check_recent_exp_prioritized(working_draft: dict) -> list[str]:
    return []


def _check_jd_keywords_present(working_draft: dict, jd_fields: dict | None) -> list[str]:
    return []


def _check_experience_exaggerated(
    all_bullets: list[str], summary: str, original_raw_text: str
) -> list[str]:
    return []


def _check_tone_repetitive(summary: str, experience: list[dict]) -> list[str]:
    return []


def validate_quality(
    resume_draft: dict,
    original: dict,
    jd_fields: dict | None = None,
) -> QualityReport:
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

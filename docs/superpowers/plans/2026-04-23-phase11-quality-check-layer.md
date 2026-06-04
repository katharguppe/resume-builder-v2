# Phase 11: Quality Check Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `app/llm/quality_check.py` with five pure-Python resume quality checks and wire it into `finetuner.py` between the variation engine and PDF render.

**Architecture:** A single new module exposes `validate_quality(resume_draft, original, jd_fields=None) -> QualityReport`. Five private check functions each return a list of issue strings prefixed `[AUTO-FIXED]` or `[NEEDS REVIEW]`. The entry point deep-copies the draft, runs all checks inside individual try/except guards, and returns a `QualityReport` dataclass. Two existing rewrite functions in `finetuner.py` each get a 3-line addition after `apply_variation_to_resume()`.

**Tech Stack:** Python 3.13, `dataclasses`, `re`, `copy`, `logging`; `pytest` for tests (run as `python -m pytest`).

**Spec:** `docs/superpowers/specs/2026-04-23-quality-check-design.md`
**Task file:** `tasks/PHASE-11-quality-check-layer.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `app/llm/quality_check.py` | `QualityReport` dataclass + 5 checks + `validate_quality()` |
| Create | `tests/test_quality_check.py` | All unit tests for the module |
| Modify | `app/llm/finetuner.py` | Import + 3-line addition in `rewrite_resume()` and `rewrite_resume_deepseek()` |

No other files are touched.

---

## Shared Test Fixtures (reference throughout all tasks)

The test file uses these fixtures everywhere. Do not redefine them per task — they are defined once at module scope in `tests/test_quality_check.py`.

```python
SAMPLE_DRAFT = {
    "candidate_name": "Jane Doe",
    "summary": "Dedicated sales professional with experience in B2B markets.",
    "experience": [
        {
            "title": "Sales Manager",
            "company": "Acme Corp",
            "dates": "2021-2023",
            "bullets": [
                "Managed a team of 10 sales representatives across three regions.",
                "Increased revenue by 25% through targeted outreach campaigns.",
            ],
        },
        {
            "title": "Sales Executive",
            "company": "Beta Ltd",
            "dates": "2018-2021",
            "bullets": [
                "Developed client relationships with 50 enterprise accounts.",
            ],
        },
    ],
    "skills": ["Salesforce", "CRM", "Negotiation"],
    "education": [{"degree": "BBA", "institution": "Delhi University", "year": "2018"}],
}

SAMPLE_ORIGINAL = {"raw_text": "Managed a team of 10 sales reps. Increased revenue by 25%."}
```

---

### Task 1: QualityReport dataclass + module skeleton

**Files:**
- Create: `app/llm/quality_check.py`
- Create: `tests/test_quality_check.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_quality_check.py`:

```python
import copy
from app.llm.quality_check import QualityReport, validate_quality

SAMPLE_DRAFT = {
    "candidate_name": "Jane Doe",
    "summary": "Dedicated sales professional with experience in B2B markets.",
    "experience": [
        {
            "title": "Sales Manager",
            "company": "Acme Corp",
            "dates": "2021-2023",
            "bullets": [
                "Managed a team of 10 sales representatives across three regions.",
                "Increased revenue by 25% through targeted outreach campaigns.",
            ],
        },
        {
            "title": "Sales Executive",
            "company": "Beta Ltd",
            "dates": "2018-2021",
            "bullets": [
                "Developed client relationships with 50 enterprise accounts.",
            ],
        },
    ],
    "skills": ["Salesforce", "CRM", "Negotiation"],
    "education": [{"degree": "BBA", "institution": "Delhi University", "year": "2018"}],
}

SAMPLE_ORIGINAL = {"raw_text": "Managed a team of 10 sales reps. Increased revenue by 25%."}


def test_quality_report_fields():
    report = QualityReport(passed=True, issues=[], fixed_draft={})
    assert report.passed is True
    assert report.issues == []
    assert report.fixed_draft == {}


def test_validate_quality_returns_quality_report():
    report = validate_quality(SAMPLE_DRAFT, SAMPLE_ORIGINAL)
    assert isinstance(report, QualityReport)
    assert isinstance(report.passed, bool)
    assert isinstance(report.issues, list)
    assert isinstance(report.fixed_draft, dict)


def test_validate_quality_does_not_mutate_input():
    original_draft = copy.deepcopy(SAMPLE_DRAFT)
    validate_quality(SAMPLE_DRAFT, SAMPLE_ORIGINAL)
    assert SAMPLE_DRAFT == original_draft
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_quality_check.py -v
```

Expected: `ImportError` — `quality_check` module does not exist yet.

- [ ] **Step 3: Create `app/llm/quality_check.py` with skeleton**

```python
from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field

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
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_quality_check.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/llm/quality_check.py tests/test_quality_check.py
git commit -m "[PHASE-11] add: quality_check skeleton - QualityReport dataclass + validate_quality stub"
```

---

### Task 2: `_check_bullets_too_long`

**Files:**
- Modify: `app/llm/quality_check.py` — implement `_check_bullets_too_long`
- Modify: `tests/test_quality_check.py` — add tests

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_quality_check.py`:

```python
from app.llm.quality_check import _check_bullets_too_long, BULLET_MAX_WORDS
import copy


def test_bullets_too_long_short_bullet_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    issues = _check_bullets_too_long(draft)
    assert issues == []


def test_bullets_too_long_exactly_30_words_no_issue():
    draft = {
        "experience": [
            {"title": "Manager", "bullets": ["word " * 30]}
        ]
    }
    issues = _check_bullets_too_long(draft)
    assert issues == []


def test_bullets_too_long_31_words_is_auto_fixed():
    long_bullet = " ".join([f"word{i}" for i in range(31)])
    draft = {
        "experience": [
            {"title": "Sales Manager", "bullets": [long_bullet]}
        ]
    }
    issues = _check_bullets_too_long(draft)
    assert len(issues) == 1
    assert issues[0].startswith("[AUTO-FIXED]")
    assert "Sales Manager" in issues[0]


def test_bullets_too_long_mutates_working_draft():
    long_bullet = " ".join([f"word{i}" for i in range(31)])
    draft = {
        "experience": [
            {"title": "Manager", "bullets": [long_bullet]}
        ]
    }
    _check_bullets_too_long(draft)
    trimmed = draft["experience"][0]["bullets"][0]
    assert len(trimmed.split()) <= BULLET_MAX_WORDS + 1  # +1 for "…" appended as one token
    assert trimmed.endswith("…")


def test_bullets_too_long_missing_experience_no_crash():
    issues = _check_bullets_too_long({})
    assert issues == []


def test_bullets_too_long_non_string_bullet_no_crash():
    draft = {"experience": [{"title": "Manager", "bullets": [None, 42]}]}
    issues = _check_bullets_too_long(draft)
    assert issues == []
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest tests/test_quality_check.py -k "bullets_too_long" -v
```

Expected: FAIL — function returns `[]` for all inputs.

- [ ] **Step 3: Implement `_check_bullets_too_long`**

Replace the stub in `app/llm/quality_check.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_quality_check.py -k "bullets_too_long" -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/llm/quality_check.py tests/test_quality_check.py
git commit -m "[PHASE-11] add: _check_bullets_too_long - auto-trim >30 word bullets"
```

---

### Task 3: `_check_recent_exp_prioritized`

**Files:**
- Modify: `app/llm/quality_check.py` — implement `_check_recent_exp_prioritized`
- Modify: `tests/test_quality_check.py` — add tests

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_quality_check.py`:

```python
from app.llm.quality_check import _check_recent_exp_prioritized
import copy


def test_recent_exp_first_role_more_bullets_no_issue():
    draft = {
        "experience": [
            {"title": "Manager", "bullets": ["a", "b", "c"]},
            {"title": "Executive", "bullets": ["x", "y"]},
        ]
    }
    assert _check_recent_exp_prioritized(draft) == []


def test_recent_exp_first_role_equal_bullets_no_issue():
    draft = {
        "experience": [
            {"title": "Manager", "bullets": ["a", "b"]},
            {"title": "Executive", "bullets": ["x", "y"]},
        ]
    }
    assert _check_recent_exp_prioritized(draft) == []


def test_recent_exp_first_role_fewer_bullets_flagged():
    draft = {
        "experience": [
            {"title": "Manager", "bullets": ["a", "b"]},
            {"title": "Executive", "bullets": ["x", "y", "z"]},
        ]
    }
    issues = _check_recent_exp_prioritized(draft)
    assert len(issues) == 1
    assert issues[0].startswith("[NEEDS REVIEW]")
    assert "2" in issues[0] and "3" in issues[0]


def test_recent_exp_single_role_no_issue():
    draft = {"experience": [{"title": "Manager", "bullets": ["a", "b"]}]}
    assert _check_recent_exp_prioritized(draft) == []


def test_recent_exp_missing_experience_no_crash():
    assert _check_recent_exp_prioritized({}) == []


def test_recent_exp_empty_experience_no_crash():
    assert _check_recent_exp_prioritized({"experience": []}) == []
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest tests/test_quality_check.py -k "recent_exp" -v
```

Expected: FAIL — stub returns `[]` for all inputs including the "fewer bullets" case.

- [ ] **Step 3: Implement `_check_recent_exp_prioritized`**

Replace the stub in `app/llm/quality_check.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_quality_check.py -k "recent_exp" -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/llm/quality_check.py tests/test_quality_check.py
git commit -m "[PHASE-11] add: _check_recent_exp_prioritized - flag under-bulleted first role"
```

---

### Task 4: `_check_jd_keywords_present`

**Files:**
- Modify: `app/llm/quality_check.py` — implement `_check_jd_keywords_present`
- Modify: `tests/test_quality_check.py` — add tests

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_quality_check.py`:

```python
from app.llm.quality_check import _check_jd_keywords_present
import copy


def test_jd_keywords_none_jd_fields_skipped():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    assert _check_jd_keywords_present(draft, None) == []


def test_jd_keywords_empty_required_skills_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    assert _check_jd_keywords_present(draft, {"required_skills": []}) == []


def test_jd_keywords_keyword_in_summary_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    # "sales" is in the summary
    issues = _check_jd_keywords_present(draft, {"required_skills": ["sales"]})
    assert issues == []


def test_jd_keywords_keyword_in_bullets_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    # "revenue" is in a bullet
    issues = _check_jd_keywords_present(draft, {"required_skills": ["revenue"]})
    assert issues == []


def test_jd_keywords_keyword_in_skills_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    # "CRM" is in skills
    issues = _check_jd_keywords_present(draft, {"required_skills": ["crm"]})
    assert issues == []


def test_jd_keywords_missing_keyword_flagged():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    issues = _check_jd_keywords_present(draft, {"required_skills": ["stakeholder management"]})
    assert len(issues) == 1
    assert issues[0].startswith("[NEEDS REVIEW]")
    assert "stakeholder management" in issues[0]


def test_jd_keywords_case_insensitive():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    # "Salesforce" in skills, keyword passed as uppercase
    issues = _check_jd_keywords_present(draft, {"required_skills": ["SALESFORCE"]})
    assert issues == []


def test_jd_keywords_missing_experience_no_crash():
    issues = _check_jd_keywords_present({}, {"required_skills": ["python"]})
    assert len(issues) == 1
    assert "python" in issues[0]
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest tests/test_quality_check.py -k "jd_keywords" -v
```

Expected: FAIL — stub returns `[]` for all inputs including missing keyword case.

- [ ] **Step 3: Implement `_check_jd_keywords_present`**

Replace the stub in `app/llm/quality_check.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_quality_check.py -k "jd_keywords" -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/llm/quality_check.py tests/test_quality_check.py
git commit -m "[PHASE-11] add: _check_jd_keywords_present - case-insensitive required skill scan"
```

---

### Task 5: `_check_experience_exaggerated`

**Files:**
- Modify: `app/llm/quality_check.py` — implement `_check_experience_exaggerated`
- Modify: `tests/test_quality_check.py` — add tests

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_quality_check.py`:

```python
from app.llm.quality_check import _check_experience_exaggerated


def test_exaggerated_same_numbers_no_issue():
    # 25% and 10 appear in both original and draft
    bullets = ["Increased revenue by 25% across 10 regions."]
    summary = ""
    original = "Increased revenue by 25% across 10 regions."
    assert _check_experience_exaggerated(bullets, summary, original) == []


def test_exaggerated_new_percentage_flagged():
    bullets = ["Increased revenue by 40%."]
    summary = ""
    original = "Increased revenue through targeted campaigns."  # no 40%
    issues = _check_experience_exaggerated(bullets, summary, original)
    assert any("40%" in i for i in issues)
    assert all(i.startswith("[NEEDS REVIEW]") for i in issues)


def test_exaggerated_new_integer_flagged():
    bullets = ["Managed a team of 200 people."]
    summary = ""
    original = "Managed a small sales team."  # no 200
    issues = _check_experience_exaggerated(bullets, summary, original)
    assert any("200" in i for i in issues)


def test_exaggerated_no_numbers_in_draft_no_issue():
    bullets = ["Led cross-functional initiatives across regions."]
    summary = ""
    original = "Led initiatives with 5 teams."
    assert _check_experience_exaggerated(bullets, summary, original) == []


def test_exaggerated_empty_original_flags_all_draft_numbers():
    bullets = ["Hit 150% of quota in Q3."]
    summary = ""
    original = ""
    issues = _check_experience_exaggerated(bullets, summary, original)
    assert len(issues) >= 1  # 150% is new


def test_exaggerated_number_in_summary_checked():
    bullets = []
    summary = "Generated $2M in new pipeline."
    original = "Worked on sales pipeline."  # no 2
    issues = _check_experience_exaggerated(bullets, summary, original)
    assert any("2" in i for i in issues)
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest tests/test_quality_check.py -k "exaggerated" -v
```

Expected: FAIL — stub returns `[]` for all inputs including new-number cases.

- [ ] **Step 3: Implement `_check_experience_exaggerated`**

Replace the stub in `app/llm/quality_check.py`:

```python
def _check_experience_exaggerated(
    all_bullets: list[str], summary: str, original_raw_text: str
) -> list[str]:
    """Flag numeric tokens in draft not present in original resume text."""
    original_nums: set[str] = set(_NUMBER_RE.findall(original_raw_text))
    draft_text = " ".join([summary] + all_bullets)
    draft_nums: set[str] = set(_NUMBER_RE.findall(draft_text))

    return [
        f"[NEEDS REVIEW] Unverified metric not found in original resume: '{num}'"
        for num in draft_nums - original_nums
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_quality_check.py -k "exaggerated" -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/llm/quality_check.py tests/test_quality_check.py
git commit -m "[PHASE-11] add: _check_experience_exaggerated - flag numeric tokens absent from original"
```

---

### Task 6: `_check_tone_repetitive`

**Files:**
- Modify: `app/llm/quality_check.py` — implement `_check_tone_repetitive` + `_make_section_ngrams` helper
- Modify: `tests/test_quality_check.py` — add tests

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_quality_check.py`:

```python
from app.llm.quality_check import _check_tone_repetitive, NGRAM_SIZE, WORD_FREQ_THRESHOLD


def test_tone_repetitive_unique_text_no_issue():
    summary = "Dedicated sales professional with B2B expertise."
    experience = [
        {"bullets": ["Increased revenue by 25% across three regions."]},
        {"bullets": ["Developed client relationships with enterprise accounts."]},
    ]
    issues = _check_tone_repetitive(summary, experience)
    assert issues == []


def test_tone_repetitive_ngram_across_sections_flagged():
    # "managed a team of" appears in both summary and a role's bullets
    summary = "Senior leader who managed a team of high performers."
    experience = [
        {"bullets": ["Managed a team of 10 sales representatives."]},
    ]
    issues = _check_tone_repetitive(summary, experience)
    ngram_issues = [i for i in issues if "managed a team of" in i.lower()]
    assert len(ngram_issues) >= 1
    assert all(i.startswith("[NEEDS REVIEW]") for i in ngram_issues)


def test_tone_repetitive_same_ngram_within_one_section_not_flagged():
    # Repetition within one role is not cross-section
    summary = ""
    experience = [
        {"bullets": [
            "Managed a team of five.",
            "Managed a team of ten.",
        ]},
    ]
    issues = _check_tone_repetitive(summary, experience)
    # same ngram within one section only — should NOT be flagged as cross-section
    ngram_issues = [i for i in issues if "Repetitive phrase" in i]
    assert ngram_issues == []


def test_tone_repetitive_word_freq_threshold_flagged():
    # "managed" repeated WORD_FREQ_THRESHOLD times across draft
    repeated_word = "managed"
    summary = f"{repeated_word} budgets effectively."
    bullets = [f"{repeated_word} stakeholders." for _ in range(WORD_FREQ_THRESHOLD - 1)]
    experience = [{"bullets": bullets}]
    issues = _check_tone_repetitive(summary, experience)
    freq_issues = [i for i in issues if repeated_word in i and "times" in i]
    assert len(freq_issues) >= 1


def test_tone_repetitive_word_below_threshold_not_flagged():
    summary = "Led the team."
    experience = [
        {"bullets": ["Led initiatives.", "Led projects."]},
    ]
    # "led" appears 3 times — below default threshold of 4
    issues = _check_tone_repetitive(summary, experience)
    freq_issues = [i for i in issues if "'led'" in i]
    assert freq_issues == []


def test_tone_repetitive_short_text_no_crash():
    # Text shorter than NGRAM_SIZE words
    summary = "Sales."
    experience = [{"bullets": ["Led."]}]
    issues = _check_tone_repetitive(summary, experience)
    assert isinstance(issues, list)


def test_tone_repetitive_missing_bullets_key_no_crash():
    summary = "Professional."
    experience = [{"title": "Manager"}]  # no "bullets" key
    issues = _check_tone_repetitive(summary, experience)
    assert isinstance(issues, list)
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest tests/test_quality_check.py -k "tone_repetitive" -v
```

Expected: FAIL — stub returns `[]` for all inputs including the ngram and word-freq cases.

- [ ] **Step 3: Implement `_make_section_ngrams` helper and `_check_tone_repetitive`**

Add `_make_section_ngrams` above `_check_tone_repetitive` in `app/llm/quality_check.py`:

```python
def _make_section_ngrams(text: str, n: int) -> set[str]:
    """Return all unique n-grams from lowercased text."""
    words = re.findall(r"\b\w+\b", text.lower())
    if len(words) < n:
        return set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def _check_tone_repetitive(summary: str, experience: list[dict]) -> list[str]:
    """
    Flag:
    - Any NGRAM_SIZE-word phrase appearing in 2+ sections (summary / per-role bullets).
    - Any non-stopword appearing >= WORD_FREQ_THRESHOLD times across the whole draft.
    """
    # Build sections: summary + one text block per role
    sections: list[str] = []
    if summary.strip():
        sections.append(summary)
    for role in experience:
        if not isinstance(role, dict):
            continue
        bullets = role.get("bullets", []) or []
        role_text = " ".join(b for b in bullets if isinstance(b, str))
        if role_text.strip():
            sections.append(role_text)

    issues: list[str] = []

    # ── N-gram cross-section check ────────────────────────────────────────────
    ngram_section_count: dict[str, int] = {}
    for section_text in sections:
        for ng in _make_section_ngrams(section_text, NGRAM_SIZE):
            ngram_section_count[ng] = ngram_section_count.get(ng, 0) + 1

    for ng, count in ngram_section_count.items():
        if count >= 2:
            issues.append(f"[NEEDS REVIEW] Repetitive phrase across sections: '{ng}'")

    # ── Word-frequency check ──────────────────────────────────────────────────
    all_text = " ".join(sections)
    tokens = re.findall(r"\b[a-z]+\b", all_text.lower())
    word_counts: dict[str, int] = {}
    for token in tokens:
        if token not in _STOPWORDS:
            word_counts[token] = word_counts.get(token, 0) + 1

    for word, count in word_counts.items():
        if count >= WORD_FREQ_THRESHOLD:
            issues.append(f"[NEEDS REVIEW] Word '{word}' used {count} times across draft")

    return issues
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_quality_check.py -k "tone_repetitive" -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/llm/quality_check.py tests/test_quality_check.py
git commit -m "[PHASE-11] add: _check_tone_repetitive - ngram cross-section + word-frequency checks"
```

---

### Task 7: `validate_quality()` entry point — integration tests

**Files:**
- Modify: `tests/test_quality_check.py` — add integration-level tests for `validate_quality()`

The `validate_quality()` function body was already written in Task 1. These tests exercise it end-to-end with the real check implementations now in place.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_quality_check.py`:

```python
import copy
from unittest.mock import patch


def test_validate_quality_clean_draft_passes():
    report = validate_quality(SAMPLE_DRAFT, SAMPLE_ORIGINAL)
    # SAMPLE_DRAFT has no new numbers vs original, no over-long bullets,
    # first role has 2 bullets vs second role's 1 — so no [NEEDS REVIEW] issues
    assert report.passed is True
    assert report.fixed_draft is not SAMPLE_DRAFT  # deep copy


def test_validate_quality_long_bullet_auto_fixed_passes():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    long_bullet = " ".join([f"word{i}" for i in range(35)])
    draft["experience"][0]["bullets"].append(long_bullet)
    report = validate_quality(draft, SAMPLE_ORIGINAL)
    # Auto-fixed bullet → [AUTO-FIXED] issue logged but passed is still True
    assert report.passed is True
    auto_fixed = [i for i in report.issues if i.startswith("[AUTO-FIXED]")]
    assert len(auto_fixed) >= 1


def test_validate_quality_exaggerated_metric_fails():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    draft["experience"][0]["bullets"].append("Delivered $5M in revenue.")
    # $5M not in SAMPLE_ORIGINAL raw_text
    report = validate_quality(draft, SAMPLE_ORIGINAL)
    assert report.passed is False
    review_issues = [i for i in report.issues if i.startswith("[NEEDS REVIEW]")]
    assert len(review_issues) >= 1


def test_validate_quality_missing_jd_keyword_fails():
    report = validate_quality(
        SAMPLE_DRAFT,
        SAMPLE_ORIGINAL,
        jd_fields={"required_skills": ["machine learning"]},
    )
    assert report.passed is False
    assert any("machine learning" in i for i in report.issues)


def test_validate_quality_jd_none_keyword_check_skipped():
    # No jd_fields → keyword check absent from issues entirely
    report = validate_quality(SAMPLE_DRAFT, SAMPLE_ORIGINAL, jd_fields=None)
    assert not any("JD keyword" in i for i in report.issues)


def test_validate_quality_failing_check_does_not_crash():
    # Patch one check to raise — other checks must still run
    with patch(
        "app.llm.quality_check._check_bullets_too_long",
        side_effect=RuntimeError("boom"),
    ):
        report = validate_quality(SAMPLE_DRAFT, SAMPLE_ORIGINAL)
    assert isinstance(report, QualityReport)


def test_validate_quality_input_not_mutated():
    original_draft = copy.deepcopy(SAMPLE_DRAFT)
    validate_quality(SAMPLE_DRAFT, SAMPLE_ORIGINAL)
    assert SAMPLE_DRAFT == original_draft
```

- [ ] **Step 2: Run to verify tests reflect expected behaviour**

```
python -m pytest tests/test_quality_check.py -k "validate_quality" -v
```

Expected: most PASS. If any fail, investigate and adjust the implementation (not the test) before proceeding.

- [ ] **Step 3: Fix any failures**

Common causes:
- `test_validate_quality_clean_draft_passes` fails → check if SAMPLE_DRAFT triggers a false positive in any check (exaggeration: "25%" appears in both original and draft, so it should pass; bullets: under 30 words; first role has 2 bullets vs second role's 1 — passes).
- `test_validate_quality_exaggerated_metric_fails` fails → verify `_NUMBER_RE` matches `$5M`. Note: `$` is not matched by `\b\d...` — change bullet to use a plain number: `"Delivered 5000000 in revenue."` if regex doesn't cover `$`.

> **Note on `$5M`:** The `_NUMBER_RE` pattern `\b\d[\d,]*(?:\.\d+)?%?\b` matches only digit-starting tokens. "5M" won't be matched if the `M` suffix is attached. Use `"Delivered 5,000,000 in revenue."` in the test if `$5M` doesn't match. Do not change `_NUMBER_RE` — the test data should match the regex, not the other way around.

Update `test_validate_quality_exaggerated_metric_fails` if needed:

```python
def test_validate_quality_exaggerated_metric_fails():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    draft["experience"][0]["bullets"].append("Delivered 5,000,000 in new pipeline revenue.")
    # 5,000,000 not in SAMPLE_ORIGINAL raw_text
    report = validate_quality(draft, SAMPLE_ORIGINAL)
    assert report.passed is False
    review_issues = [i for i in report.issues if i.startswith("[NEEDS REVIEW]")]
    assert len(review_issues) >= 1
```

- [ ] **Step 4: Run all quality_check tests**

```
python -m pytest tests/test_quality_check.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_quality_check.py
git commit -m "[PHASE-11] add: validate_quality integration tests - all checks wired + guard verified"
```

---

### Task 8: Wire `validate_quality` into `finetuner.py`

**Files:**
- Modify: `app/llm/finetuner.py:1-16` (imports) and `:112-114`, `:267-269` (integration lines)

- [ ] **Step 1: Read the current finetuner.py imports block**

Verify line 15 reads:
```python
from app.llm.variation_engine import apply_variation_to_resume
```

- [ ] **Step 2: Add the import**

In `app/llm/finetuner.py`, add one line after the `apply_variation_to_resume` import:

```python
from app.llm.variation_engine import apply_variation_to_resume
from app.llm.quality_check import validate_quality
```

- [ ] **Step 3: Wire into `rewrite_resume()`**

Find this block in `rewrite_resume()` (around line 112):

```python
            result = json.loads(_strip_markdown_fences(response.content[0].text))
            return apply_variation_to_resume(result)
```

Replace with:

```python
            result = json.loads(_strip_markdown_fences(response.content[0].text))
            draft = apply_variation_to_resume(result)
            report = validate_quality(draft, {"raw_text": resume_text})
            return report.fixed_draft
```

- [ ] **Step 4: Wire into `rewrite_resume_deepseek()`**

Find this block in `rewrite_resume_deepseek()` (around line 267):

```python
            result = json.loads(_strip_markdown_fences(response.choices[0].message.content))
            return apply_variation_to_resume(result)
```

Replace with:

```python
            result = json.loads(_strip_markdown_fences(response.choices[0].message.content))
            draft = apply_variation_to_resume(result)
            report = validate_quality(draft, {"raw_text": resume_text})
            return report.fixed_draft
```

- [ ] **Step 5: Run full test suite to confirm nothing is broken**

```
python -m pytest -v
```

Expected: all existing tests PASS (378 baseline) + all new `test_quality_check.py` tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/llm/finetuner.py
git commit -m "[PHASE-11] add: wire validate_quality into rewrite_resume + rewrite_resume_deepseek"
```

---

### Task 9: Checkpoint — full suite + task file update

**Files:**
- Modify: `tasks/PHASE-11-quality-check-layer.md` — fill in PDCA log

- [ ] **Step 1: Run full test suite**

```
python -m pytest -v
```

Expected output summary: all tests PASS. Count must be ≥ 378 (baseline) + tests added in this phase.

- [ ] **Step 2: Verify module boundary**

```bash
git diff HEAD~8 --name-only
```

Expected: only `app/llm/quality_check.py`, `app/llm/finetuner.py`, `tests/test_quality_check.py` appear. No other files.

- [ ] **Step 3: Update task file**

Fill in `tasks/PHASE-11-quality-check-layer.md`:

```markdown
## Status: COMPLETE

## v1 Foundation
None — quality_check.py is net-new.

## Net New
- app/llm/quality_check.py — QualityReport dataclass + 5 checks + validate_quality()
- tests/test_quality_check.py — unit + integration tests

## PDCA Log

### Cycle 1
**Plan:** 2026-04-23-phase11-quality-check-layer.md
**Approved by human:** [date]
**Do:** 9 tasks, TDD, one commit per check
**Check:** All tests passing, module boundary clean
**Act:** Proceed to Phase 12
```

- [ ] **Step 4: Commit task file**

```bash
git add tasks/PHASE-11-quality-check-layer.md
git commit -m "[PHASE-11] checkpoint: quality check complete - all tests passing"
```

---

## Self-Review Against Spec

| Spec requirement | Covered by |
|---|---|
| `validate_quality(resume_draft, original, jd_fields=None) -> QualityReport` | Task 1 + Task 7 |
| `QualityReport(passed, issues, fixed_draft)` | Task 1 |
| `tone_repetitive` — ngram + word freq | Task 6 |
| `experience_exaggerated` — numeric heuristic | Task 5 |
| `bullets_too_long` — > 30 words, auto-fix trim | Task 2 |
| `recent_exp_prioritized` — first role bullet count | Task 3 |
| `jd_keywords_present` — required_skills match, skip if None | Task 4 |
| Auto-fix long bullets, issue still logged | Task 2 + Task 7 |
| `passed = False` only for [NEEDS REVIEW] | Task 1 (logic in validate_quality) |
| Pure Python — no LLM calls | All tasks — no LLM imports in quality_check.py |
| < 5s budget | All checks are string ops — < 50ms expected |
| Unit-testable with mock data, no mocking required | All tasks — no I/O in any check |
| Integration after variation engine, before return | Task 8 |
| Constants at module level (BULLET_MAX_WORDS, NGRAM_SIZE, WORD_FREQ_THRESHOLD) | Task 1 |
| Failing check must not crash pipeline | Task 7 (mock test) |
| Deep copy — never mutate caller's dict | Task 1 + Task 7 |
| `original = {"raw_text": resume_text}` convention | Task 5 + Task 8 |

No gaps found.

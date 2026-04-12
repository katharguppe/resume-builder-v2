# Phase 03 — ATS Score Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `app/scoring/` — a pure-Python, no-LLM ATS scoring module that scores a resume against a JD across four components (keyword match, skills coverage, experience clarity, structure completeness) and detects missing resume fields with severity rankings.

**Architecture:** Four files — `models.py` (dataclasses), `ats_scorer.py` (four component functions + `compute_ats_score`), `missing_info.py` (`detect_missing`), and `__init__.py` (re-exports). All inputs are plain dicts + raw text strings; no DB writes in this phase (score persistence is Phase 4). DB schema for `ats_score_json` was already added in a pre-fix step.

**Tech Stack:** Python 3.13 stdlib only (`re`, `dataclasses`, `typing`). pytest for tests.

---

## Pre-conditions (already done — verify before starting)

- `app/state/models.py`: `SubmissionRecord` has `ats_score_json: Optional[str]` field
- `app/state/db.py`: `submissions` table has `ats_score_json TEXT` column + migration + whitelist entry
- `app/ui/pages/1_Setup.py`: Anthropic + Gemini key fields both present and saving to correct env vars
- `tests/test_state.py`: `test_submission_record_fields` passes with `ats_score_json=None`
- Baseline: `pytest tests/ -q` → 131 passed

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app/scoring/__init__.py` | Create | Re-export `compute_ats_score`, `detect_missing`, `ATSScore`, `MissingItem` |
| `app/scoring/models.py` | Create | `ATSScore` and `MissingItem` dataclasses |
| `app/scoring/ats_scorer.py` | Create | Four scoring components + `compute_ats_score()` |
| `app/scoring/missing_info.py` | Create | `detect_missing()` |
| `tests/test_scoring_models.py` | Create | Dataclass construction, field names, defaults |
| `tests/test_ats_scorer.py` | Create | All four components + integration + edge cases |
| `tests/test_missing_info.py` | Create | All six detection rules |

---

## Task 1: Data Models

**Files:**
- Create: `app/scoring/models.py`
- Create: `tests/test_scoring_models.py`

- [ ] **Step 1.1 — Write failing tests**

Create `tests/test_scoring_models.py`:

```python
import pytest
from dataclasses import fields


def test_ats_score_import():
    from app.scoring.models import ATSScore
    assert ATSScore is not None


def test_ats_score_construction():
    from app.scoring.models import ATSScore
    score = ATSScore(
        total=72,
        keyword_match=20,
        skills_coverage=24,
        experience_clarity=16,
        structure_completeness=12,
        keyword_matched=["python", "aws"],
        skills_matched=["Python", "AWS"],
        skills_missing=["Kubernetes"],
    )
    assert score.total == 72
    assert score.keyword_match == 20
    assert score.skills_coverage == 24
    assert score.experience_clarity == 16
    assert score.structure_completeness == 12
    assert score.keyword_matched == ["python", "aws"]
    assert score.skills_matched == ["Python", "AWS"]
    assert score.skills_missing == ["Kubernetes"]


def test_ats_score_list_defaults():
    from app.scoring.models import ATSScore
    score = ATSScore(
        total=0,
        keyword_match=0,
        skills_coverage=0,
        experience_clarity=0,
        structure_completeness=0,
    )
    assert score.keyword_matched == []
    assert score.skills_matched == []
    assert score.skills_missing == []


def test_missing_item_import():
    from app.scoring.models import MissingItem
    assert MissingItem is not None


def test_missing_item_construction():
    from app.scoring.models import MissingItem
    item = MissingItem(
        field="work_dates",
        label="Work experience dates",
        severity="HIGH",
        hint="Add start and end year to each role.",
    )
    assert item.field == "work_dates"
    assert item.severity == "HIGH"


def test_missing_item_severity_values():
    from app.scoring.models import MissingItem
    for sev in ("HIGH", "MEDIUM", "LOW"):
        item = MissingItem(field="f", label="l", severity=sev, hint="h")
        assert item.severity == sev
```

- [ ] **Step 1.2 — Run tests, confirm they fail**

```
pytest tests/test_scoring_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.scoring'`

- [ ] **Step 1.3 — Create `app/scoring/models.py`**

```python
from dataclasses import dataclass, field
from typing import List


@dataclass
class ATSScore:
    total: int
    keyword_match: int
    skills_coverage: int
    experience_clarity: int
    structure_completeness: int
    keyword_matched: List[str] = field(default_factory=list)
    skills_matched: List[str] = field(default_factory=list)
    skills_missing: List[str] = field(default_factory=list)


@dataclass
class MissingItem:
    field: str
    label: str
    severity: str   # "HIGH" | "MEDIUM" | "LOW"
    hint: str
```

- [ ] **Step 1.4 — Create `app/scoring/__init__.py` (stub — will be completed in Task 5)**

```python
# Populated in Task 5 after all modules are built.
```

- [ ] **Step 1.5 — Run tests, confirm they pass**

```
pytest tests/test_scoring_models.py -v
```

Expected: 6 passed

- [ ] **Step 1.6 — Commit**

```
git add app/scoring/models.py app/scoring/__init__.py tests/test_scoring_models.py
git commit -m "[PHASE-03] add: ATSScore + MissingItem dataclasses"
```

---

## Task 2: keyword_match Component (30 pts)

**Files:**
- Create: `app/scoring/ats_scorer.py`
- Modify: `tests/test_ats_scorer.py` (create new file)

- [ ] **Step 2.1 — Create `tests/test_ats_scorer.py` with keyword_match tests**

```python
import pytest


# ---------------------------------------------------------------------------
# Helpers shared across all component tests
# ---------------------------------------------------------------------------

def _make_jd(
    job_title="Software Engineer",
    required_skills=None,
    preferred_skills=None,
    key_responsibilities=None,
    experience_required="",
    education_required="",
    company="Acme",
):
    return {
        "job_title": job_title,
        "company": company,
        "required_skills": required_skills or [],
        "preferred_skills": preferred_skills or [],
        "experience_required": experience_required,
        "education_required": education_required,
        "key_responsibilities": key_responsibilities or [],
    }


def _make_resume_fields(
    candidate_name="Alice",
    email="alice@example.com",
    phone="9999999999",
    current_title="Senior Engineer",
    skills=None,
    experience_summary="",
):
    return {
        "candidate_name": candidate_name,
        "email": email,
        "phone": phone,
        "current_title": current_title,
        "skills": skills or [],
        "experience_summary": experience_summary,
    }


# ---------------------------------------------------------------------------
# keyword_match
# ---------------------------------------------------------------------------

def test_keyword_match_full_overlap():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=["build Python microservices", "deploy AWS infrastructure"])
    resume_tokens = _tokenize("build Python microservices deploy AWS infrastructure")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert score == 30
    assert "python" in matched
    assert "aws" in matched


def test_keyword_match_zero_overlap():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=["manage Kubernetes clusters", "deploy Terraform"])
    resume_tokens = _tokenize("Java Spring Boot development")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert score == 0
    assert matched == []


def test_keyword_match_partial_overlap():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=["manage Python services", "build REST APIs"])
    resume_tokens = _tokenize("Python developer REST experience")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert 0 < score < 30
    assert "python" in matched
    assert "rest" in matched


def test_keyword_match_fallback_empty_responsibilities():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=[], job_title="Python Developer")
    resume_tokens = _tokenize("Python developer experience")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert score <= 15  # fallback caps at 15


def test_keyword_match_fallback_completely_empty_jd():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=[], job_title="")
    resume_tokens = _tokenize("anything here")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert score == 15  # neutral when JD has no data


def test_keyword_match_stop_words_excluded():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=["the and or to of in for with is are be by"])
    resume_tokens = set()  # resume has nothing
    score, matched = _score_keyword_match(jd, resume_tokens)
    # All tokens are stop words, so jd_tokens is empty → neutral
    assert score == 15


def test_keyword_match_caps_at_30():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=["python", "aws"])
    resume_tokens = _tokenize("python aws java docker kubernetes terraform ansible")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert score <= 30
```

- [ ] **Step 2.2 — Run tests, confirm they fail**

```
pytest tests/test_ats_scorer.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` on `ats_scorer`

- [ ] **Step 2.3 — Create `app/scoring/ats_scorer.py` with `_tokenize` and `_score_keyword_match`**

```python
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
        jd_tokens.update(_tokenize(resp))

    if not jd_tokens:
        return 15, []

    matched = [t for t in jd_tokens if t in resume_tokens]
    return min(round(len(matched) / len(jd_tokens) * 30), 30), matched


def _normalize_skill(skill: str) -> List[str]:
    """Split compound skills on / + , and lowercase. Returns list of normalized parts."""
    parts = re.split(r"[/+,]", skill.lower())
    return [re.sub(r"[^a-z0-9\s]", "", p).strip() for p in parts if p.strip()]


def _score_skills_coverage(
    jd_fields: dict, resume_fields: dict
) -> Tuple[int, List[str], List[str]]:
    """Stub — implemented in Task 3."""
    return 15, [], []


def _score_experience_clarity(
    resume_fields: dict, resume_raw_text: str
) -> int:
    """Stub — implemented in Task 4."""
    return 0


def _score_structure_completeness(resume_raw_text: str) -> int:
    """Stub — implemented in Task 4."""
    return 0


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
```

- [ ] **Step 2.4 — Run keyword_match tests only**

```
pytest tests/test_ats_scorer.py -k "keyword_match" -v
```

Expected: 7 passed

- [ ] **Step 2.5 — Commit**

```
git add app/scoring/ats_scorer.py tests/test_ats_scorer.py
git commit -m "[PHASE-03] add: keyword_match scorer component + tests"
```

---

## Task 3: skills_coverage Component (30 pts)

**Files:**
- Modify: `app/scoring/ats_scorer.py` — replace `_score_skills_coverage` stub
- Modify: `tests/test_ats_scorer.py` — add skills_coverage tests

- [ ] **Step 3.1 — Add skills_coverage tests to `tests/test_ats_scorer.py`**

Append to the end of `tests/test_ats_scorer.py`:

```python
# ---------------------------------------------------------------------------
# skills_coverage
# ---------------------------------------------------------------------------

def test_skills_coverage_full_match():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(required_skills=["Python", "AWS", "Docker"])
    resume = _make_resume_fields(skills=["Python", "AWS", "Docker", "Git"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 24
    assert set(matched) == {"Python", "AWS", "Docker"}
    assert missing == []


def test_skills_coverage_zero_match():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(required_skills=["Kubernetes", "Terraform", "Go"])
    resume = _make_resume_fields(skills=["Python", "Django", "PostgreSQL"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 0
    assert matched == []
    assert set(missing) == {"Kubernetes", "Terraform", "Go"}


def test_skills_coverage_partial_match():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(required_skills=["Python", "AWS", "Docker"])
    resume = _make_resume_fields(skills=["Python", "AWS"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 16   # round(2/3 * 24) = 16
    assert "Python" in matched
    assert "Docker" in missing


def test_skills_coverage_preferred_bonus():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(
        required_skills=["Python", "AWS"],
        preferred_skills=["Docker", "Terraform"],
    )
    resume = _make_resume_fields(skills=["Python", "AWS", "Docker"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    # required: 2/2 * 24 = 24; preferred: 1/2 * 6 = 3; total = 27
    assert score == 27
    assert missing == []


def test_skills_coverage_neutral_when_jd_empty():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(required_skills=[], preferred_skills=[])
    resume = _make_resume_fields(skills=["Python"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 15  # neutral


def test_skills_coverage_substring_match():
    from app.scoring.ats_scorer import _score_skills_coverage
    # "Python 3.10" in JD should match "Python" in resume
    jd = _make_jd(required_skills=["Python 3.10", "AWS S3"])
    resume = _make_resume_fields(skills=["Python", "AWS"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 24
    assert missing == []


def test_skills_coverage_compound_skill_split():
    from app.scoring.ats_scorer import _score_skills_coverage
    # "Python/Django" in resume should match "Django" in JD
    jd = _make_jd(required_skills=["Django", "PostgreSQL"])
    resume = _make_resume_fields(skills=["Python/Django", "PostgreSQL"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 24
    assert missing == []


def test_skills_coverage_caps_at_30():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(
        required_skills=["Python"],
        preferred_skills=["Docker"],
    )
    resume = _make_resume_fields(skills=["Python", "Docker"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score <= 30
```

- [ ] **Step 3.2 — Run new tests, confirm they fail**

```
pytest tests/test_ats_scorer.py -k "skills_coverage" -v
```

Expected: Most fail (stub returns `15, [], []`)

- [ ] **Step 3.3 — Replace `_score_skills_coverage` stub in `app/scoring/ats_scorer.py`**

Replace the stub function (lines from `def _score_skills_coverage` through its `return`) with:

```python
def _score_skills_coverage(
    jd_fields: dict, resume_fields: dict
) -> Tuple[int, List[str], List[str]]:
    """skills_coverage: 0-30 pts. Required skills worth 24 pts, preferred 6 pts."""
    required = jd_fields.get("required_skills") or []
    preferred = jd_fields.get("preferred_skills") or []
    resume_skills_raw = resume_fields.get("skills") or []

    if not required and not preferred:
        return 15, [], []

    # Flatten resume skills into normalized parts
    resume_parts: List[str] = []
    for s in resume_skills_raw:
        resume_parts.extend(_normalize_skill(s))

    def _matches(jd_skill: str) -> bool:
        for jd_part in _normalize_skill(jd_skill):
            for rs in resume_parts:
                if jd_part in rs or rs in jd_part:
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
```

- [ ] **Step 3.4 — Run skills_coverage tests**

```
pytest tests/test_ats_scorer.py -k "skills_coverage" -v
```

Expected: 8 passed

- [ ] **Step 3.5 — Run full suite to check no regressions**

```
pytest tests/ -q
```

Expected: all pass (131 + new)

- [ ] **Step 3.6 — Commit**

```
git add app/scoring/ats_scorer.py tests/test_ats_scorer.py
git commit -m "[PHASE-03] add: skills_coverage scorer component + tests"
```

---

## Task 4: experience_clarity + structure_completeness Components (20 + 20 pts)

**Files:**
- Modify: `app/scoring/ats_scorer.py` — replace both stubs
- Modify: `tests/test_ats_scorer.py` — add component tests

- [ ] **Step 4.1 — Add experience_clarity and structure_completeness tests to `tests/test_ats_scorer.py`**

Append:

```python
# ---------------------------------------------------------------------------
# experience_clarity
# ---------------------------------------------------------------------------

def test_experience_clarity_all_signals():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="Senior Engineer")
    text = (
        "Senior Engineer at Acme Ltd 2019-2023\n"
        "Reduced costs by 30% saving $50K annually\n"
        "Managed team at TechCorp Inc"
    )
    score = _score_experience_clarity(resume, text)
    assert score == 20


def test_experience_clarity_no_dates():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="Engineer")
    text = "Engineer at Acme Ltd\nReduced costs by 30%"
    score = _score_experience_clarity(resume, text)
    assert score == 14  # 0+5+5+4


def test_experience_clarity_no_company():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="Engineer")
    text = "Engineer 2019-2022\nIncreased revenue by 20%"
    score = _score_experience_clarity(resume, text)
    assert score == 15  # 6+0+5+4


def test_experience_clarity_no_title():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="")
    text = "Software Engineer at Acme Ltd 2019-2023\nReduced costs 30%"
    score = _score_experience_clarity(resume, text)
    assert score == 15  # 6+5+0+4


def test_experience_clarity_no_achievements():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="Engineer")
    text = "Engineer at Acme Ltd 2019-2022\nWorked on backend systems"
    score = _score_experience_clarity(resume, text)
    assert score == 16  # 6+5+5+0


def test_experience_clarity_zero():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="")
    text = "worked on various projects and tasks"
    score = _score_experience_clarity(resume, text)
    assert score == 0


def test_experience_clarity_date_formats():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="")
    # Various date formats (hyphen-dash only; en-dash omitted to avoid encoding issues)
    for text in [
        "Jan 2020 - Dec 2022",
        "2019-Present",
        "2018-2021",
        "March 2017",
    ]:
        score = _score_experience_clarity(resume, text)
        assert score >= 6, f"Expected date detection for: {text!r}"


# ---------------------------------------------------------------------------
# structure_completeness
# ---------------------------------------------------------------------------

def test_structure_completeness_all_sections():
    from app.scoring.ats_scorer import _score_structure_completeness
    text = (
        "Summary\nExperienced engineer.\n"
        "Education\nBachelor of Engineering 2015\n"
        "Technical Skills\nPython, AWS\n"
        "Certifications\nAWS Certified"
    )
    assert _score_structure_completeness(text) == 20


def test_structure_completeness_no_sections():
    from app.scoring.ats_scorer import _score_structure_completeness
    text = "John Doe\njohn@example.com\nWorked at various companies"
    assert _score_structure_completeness(text) == 0


def test_structure_completeness_partial():
    from app.scoring.ats_scorer import _score_structure_completeness
    # Has skills + education but no summary or certifications
    text = "Technical Skills\nPython\nEducation\nMBA from IIM"
    score = _score_structure_completeness(text)
    assert score == 10  # 0+5+5+0


def test_structure_completeness_education_needs_degree_keyword():
    from app.scoring.ats_scorer import _score_structure_completeness
    # Has education header but no degree keyword → no pts
    text = "Education\nStudied at a good university"
    assert _score_structure_completeness(text) == 0


def test_structure_completeness_certif_prefix_match():
    from app.scoring.ats_scorer import _score_structure_completeness
    # "certifications", "certified", "certificate" all should match
    for word in ["Certifications", "Certified", "Certificate"]:
        text = f"{word}\nAWS Cloud Practitioner"
        score = _score_structure_completeness(text)
        assert score == 5, f"Expected certif match for: {word!r}"
```

- [ ] **Step 4.2 — Run new tests, confirm they fail**

```
pytest tests/test_ats_scorer.py -k "experience_clarity or structure_completeness" -v
```

Expected: Failures (stubs return 0)

- [ ] **Step 4.3 — Replace `_score_experience_clarity` stub in `app/scoring/ats_scorer.py`**

```python
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
```

- [ ] **Step 4.4 — Replace `_score_structure_completeness` stub in `app/scoring/ats_scorer.py`**

```python
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
```

- [ ] **Step 4.5 — Run component tests**

```
pytest tests/test_ats_scorer.py -k "experience_clarity or structure_completeness" -v
```

Expected: all pass

- [ ] **Step 4.6 — Run full suite**

```
pytest tests/ -q
```

Expected: all pass

- [ ] **Step 4.7 — Commit**

```
git add app/scoring/ats_scorer.py tests/test_ats_scorer.py
git commit -m "[PHASE-03] add: experience_clarity + structure_completeness components + tests"
```

---

## Task 5: `compute_ats_score` Integration + `__init__.py`

**Files:**
- Modify: `app/scoring/ats_scorer.py` — confirm `compute_ats_score` wires all four (already wired in Task 2 skeleton)
- Modify: `app/scoring/__init__.py` — add exports
- Modify: `tests/test_ats_scorer.py` — add integration tests

- [ ] **Step 5.1 — Add integration tests to `tests/test_ats_scorer.py`**

Append:

```python
# ---------------------------------------------------------------------------
# compute_ats_score integration
# ---------------------------------------------------------------------------

def test_compute_ats_score_total_in_range():
    from app.scoring.ats_scorer import compute_ats_score
    jd = _make_jd(
        required_skills=["Python", "AWS"],
        key_responsibilities=["build Python services", "deploy AWS infrastructure"],
    )
    resume = _make_resume_fields(
        current_title="Backend Engineer",
        skills=["Python", "AWS", "Docker"],
    )
    raw = (
        "Backend Engineer at Acme Ltd 2020-2023\n"
        "Summary\nSkilled Python developer.\n"
        "Skills\nPython, AWS, Docker\n"
        "Education\nBachelor of Engineering 2016\n"
        "Certifications\nAWS Certified\n"
        "Increased throughput by 40%"
    )
    score = compute_ats_score(resume, jd, raw)
    assert 0 <= score.total <= 100
    assert score.total == (
        score.keyword_match + score.skills_coverage +
        score.experience_clarity + score.structure_completeness
    )


def test_compute_ats_score_returns_ats_score_type():
    from app.scoring.ats_scorer import compute_ats_score
    from app.scoring.models import ATSScore
    jd = _make_jd()
    resume = _make_resume_fields()
    score = compute_ats_score(resume, jd, "some resume text")
    assert isinstance(score, ATSScore)


def test_compute_ats_score_skills_matched_and_missing_populated():
    from app.scoring.ats_scorer import compute_ats_score
    jd = _make_jd(required_skills=["Python", "Kubernetes"])
    resume = _make_resume_fields(skills=["Python"])
    score = compute_ats_score(resume, jd, "Python developer 2020-2023")
    assert "Python" in score.skills_matched
    assert "Kubernetes" in score.skills_missing


def test_compute_ats_score_empty_inputs_do_not_raise():
    from app.scoring.ats_scorer import compute_ats_score
    jd = _make_jd(required_skills=[], key_responsibilities=[])
    resume = _make_resume_fields(current_title="", skills=[])
    score = compute_ats_score(resume, jd, "")
    assert isinstance(score.total, int)
    assert score.total >= 0
```

- [ ] **Step 5.2 — Run integration tests**

```
pytest tests/test_ats_scorer.py -k "compute_ats_score" -v
```

Expected: all pass (the skeleton in Task 2 already wires all four components)

- [ ] **Step 5.3 — Update `app/scoring/__init__.py`**

```python
from app.scoring.ats_scorer import compute_ats_score
from app.scoring.missing_info import detect_missing
from app.scoring.models import ATSScore, MissingItem

__all__ = ["compute_ats_score", "detect_missing", "ATSScore", "MissingItem"]
```

- [ ] **Step 5.4 — Verify imports work through `__init__`**

```
python -c "from app.scoring import compute_ats_score, detect_missing, ATSScore, MissingItem; print('OK')"
```

Expected: `OK`

- [ ] **Step 5.5 — Run full suite**

```
pytest tests/ -q
```

Expected: all pass

- [ ] **Step 5.6 — Commit**

```
git add app/scoring/__init__.py tests/test_ats_scorer.py
git commit -m "[PHASE-03] add: compute_ats_score integration + __init__ exports + tests"
```

---

## Task 6: `detect_missing` (missing_info.py)

**Files:**
- Create: `app/scoring/missing_info.py`
- Create: `tests/test_missing_info.py`

- [ ] **Step 6.1 — Create `tests/test_missing_info.py`**

```python
import pytest


def _make_fields(current_title="Senior Engineer"):
    return {
        "candidate_name": "Alice",
        "email": "alice@example.com",
        "phone": "9999999999",
        "current_title": current_title,
        "skills": ["Python"],
        "experience_summary": "",
    }


# ---------------------------------------------------------------------------
# HIGH severity
# ---------------------------------------------------------------------------

def test_detect_missing_high_no_dates():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Worked at various companies on Python projects"
    items = detect_missing(fields, text)
    fields_set = {i.field for i in items}
    assert "work_dates" in fields_set
    high = [i for i in items if i.severity == "HIGH"]
    assert any(i.field == "work_dates" for i in high)


def test_detect_missing_high_no_title():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields(current_title="")
    text = "Senior Engineer at Acme Ltd 2019-2022"
    items = detect_missing(fields, text)
    high = [i for i in items if i.severity == "HIGH"]
    assert any(i.field == "current_title" for i in high)


def test_detect_missing_no_high_when_all_present():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields(current_title="Senior Engineer")
    text = "Senior Engineer at Acme Ltd 2019-2023"
    items = detect_missing(fields, text)
    high = [i for i in items if i.severity == "HIGH"]
    assert high == []


# ---------------------------------------------------------------------------
# MEDIUM severity
# ---------------------------------------------------------------------------

def test_detect_missing_medium_no_achievements():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer at Acme Ltd 2019-2022 built backend services"
    items = detect_missing(fields, text)
    med = [i for i in items if i.severity == "MEDIUM"]
    assert any(i.field == "achievements" for i in med)


def test_detect_missing_no_medium_achievements_when_present():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer at Acme Ltd 2019-2022\nReduced latency by 40%"
    items = detect_missing(fields, text)
    assert not any(i.field == "achievements" for i in items)


def test_detect_missing_medium_no_company():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer 2019-2022 built backend systems"
    items = detect_missing(fields, text)
    med = [i for i in items if i.severity == "MEDIUM"]
    assert any(i.field == "company_names" for i in med)


def test_detect_missing_no_medium_company_when_present():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer at Acme Ltd 2019-2022"
    items = detect_missing(fields, text)
    assert not any(i.field == "company_names" for i in items)


# ---------------------------------------------------------------------------
# LOW severity
# ---------------------------------------------------------------------------

def test_detect_missing_low_no_certifications():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer at Acme Ltd 2019-2022 Skills Python"
    items = detect_missing(fields, text)
    low = [i for i in items if i.severity == "LOW"]
    assert any(i.field == "certifications" for i in low)


def test_detect_missing_no_low_cert_when_present():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Certifications\nAWS Certified 2022"
    items = detect_missing(fields, text)
    assert not any(i.field == "certifications" for i in items)


def test_detect_missing_low_no_social():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer at Acme Ltd 2019-2022"
    items = detect_missing(fields, text)
    low = [i for i in items if i.severity == "LOW"]
    assert any(i.field == "social_links" for i in low)


def test_detect_missing_no_low_social_when_present():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "linkedin.com/in/alice github.com/alice"
    items = detect_missing(fields, text)
    assert not any(i.field == "social_links" for i in items)


# ---------------------------------------------------------------------------
# Return type + ordering
# ---------------------------------------------------------------------------

def test_detect_missing_returns_list_of_missing_items():
    from app.scoring.missing_info import detect_missing
    from app.scoring.models import MissingItem
    items = detect_missing(_make_fields(current_title=""), "no dates here")
    assert isinstance(items, list)
    for item in items:
        assert isinstance(item, MissingItem)


def test_detect_missing_severity_order():
    """HIGH items must appear before MEDIUM, MEDIUM before LOW."""
    from app.scoring.missing_info import detect_missing
    items = detect_missing(
        _make_fields(current_title=""),
        "no dates no company no certs",
    )
    sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    severities = [sev_order[i.severity] for i in items]
    assert severities == sorted(severities)


def test_detect_missing_empty_text_returns_all_items():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(current_title=""), "")
    fields_set = {i.field for i in items}
    assert "work_dates" in fields_set
    assert "current_title" in fields_set
    assert "achievements" in fields_set
    assert "company_names" in fields_set
    assert "certifications" in fields_set
    assert "social_links" in fields_set
```

- [ ] **Step 6.2 — Run tests, confirm they fail**

```
pytest tests/test_missing_info.py -v
```

Expected: `ModuleNotFoundError` on `missing_info`

- [ ] **Step 6.3 — Create `app/scoring/missing_info.py`**

```python
import re
from typing import List

from app.scoring.models import MissingItem

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
```

- [ ] **Step 6.4 — Run missing_info tests**

```
pytest tests/test_missing_info.py -v
```

Expected: all pass

- [ ] **Step 6.5 — Run full suite**

```
pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6.6 — Commit**

```
git add app/scoring/missing_info.py tests/test_missing_info.py
git commit -m "[PHASE-03] add: detect_missing + MissingItem severity rules + tests"
```

---

## Task 7: Completion Protocol

- [ ] **Step 7.1 — Full test run with verbose output**

```
pytest tests/ -v 2>&1
```

Confirm: baseline 131 + all new scoring tests pass. Record total count.

- [ ] **Step 7.2 — SPEC COMPLIANCE CHECK**

- [ ] Module boundary respected — only `app/scoring/` created (+ pre-fix to `app/state/`, `app/ui/pages/1_Setup.py`, `tests/test_state.py`)
- [ ] No LLM calls anywhere in `app/scoring/`
- [ ] No hardcoded model names or API keys
- [ ] v1 preserved modules untouched (`app/ingestor/`, `app/composer/`, `app/email_handler/`, `docker/`)
- [ ] `ats_score_json` column added to DB with migration guard
- [ ] `GEMINI_API_KEY` now saves correctly in Setup page
- [ ] Git format correct (`[PHASE-03]` prefix, feature branch)

- [ ] **Step 7.3 — Invoke code review**

Use `superpowers:requesting-code-review` and provide:
- Phase 03 scope: `app/scoring/` (new module)
- CLAUDE.md §3 (no LLM), §4 (module boundary), §9 (v1 preserved)
- pytest output from Step 7.1
- Pre-fixes: Setup.py, db.py, models.py, test_state.py

- [ ] **Step 7.4 — Commit pre-fixes (if not already committed)**

```
git add app/ui/pages/1_Setup.py app/state/db.py app/state/models.py tests/test_state.py
git commit -m "[PHASE-03] fix: Setup page v1 variable rename + Gemini key field; ats_score_json DB column + migration"
```

- [ ] **Step 7.5 — Push branch**

```
git push origin feature/phase-02-upload-parse
```

(Phase 3 work is on the same branch until the PR for Phase 2 is merged, then create `feature/phase-03-ats-score` from it.)

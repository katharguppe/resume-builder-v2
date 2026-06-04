# Phase 03 — ATS Score Engine Design

**Date:** 2026-04-12
**Phase:** 3 / 12
**Module boundary:** `app/scoring/` only (new)
**Constraint:** No LLM calls. Pure Python. <1s per call.

---

## 1. Inputs

### `resume_fields` dict (from LLM extract pass)
```python
{
  "candidate_name": str,
  "email": str,
  "phone": str,
  "current_title": str,
  "skills": [str],
  "experience_summary": str
}
```

### `jd_fields` dict (from LLM JD extract pass)
```python
{
  "job_title": str,
  "company": str,
  "required_skills": [str],
  "preferred_skills": [str],
  "experience_required": str,
  "education_required": str,
  "key_responsibilities": [str]
}
```

### `resume_raw_text` str
Full extracted text from the resume PDF/DOC. Used for heuristic section and date detection.

---

## 2. Output Models (`app/scoring/models.py`)

```python
@dataclass
class ATSScore:
    total: int                   # 0–100
    keyword_match: int           # 0–30
    skills_coverage: int         # 0–30
    experience_clarity: int      # 0–20
    structure_completeness: int  # 0–20
    keyword_matched: List[str]   # JD keywords found in resume
    skills_matched: List[str]    # Required skills found
    skills_missing: List[str]    # Required skills not found

@dataclass
class MissingItem:
    field: str      # machine key e.g. "work_dates"
    label: str      # human label e.g. "Work experience dates"
    severity: str   # "HIGH" | "MEDIUM" | "LOW"
    hint: str       # one-line suggestion
```

---

## 3. Scoring Components

### 3.1 `keyword_match` — 30 points

Measures resume coverage of JD responsibility keywords.

1. Tokenize `jd_fields["key_responsibilities"]` → lowercase words, strip stop-words (`the`, `a`, `an`, `and`, `or`, `to`, `of`, `in`, `for`, `with`, `is`, `are`, `be`, `by`), dedupe.
2. Tokenize `resume_raw_text` into the same normalised word set.
3. `score = round(matched / total_jd_keywords * 30)`, clamped 0–30.
4. **Fallback:** if `key_responsibilities` is empty, tokenize `job_title` only → max 15 pts.

### 3.2 `skills_coverage` — 30 points

Measures resume skill list coverage of JD required + preferred skills.

1. Normalise both lists: lowercase, strip punctuation, split on `/` and `+` (e.g. `"Python/Django"` → `["python", "django"]`).
2. For each `required_skill`: match if any resume skill **contains** it as a substring (case-insensitive).
3. `required_score = round(required_matched / len(required_skills) * 24)` clamped 0–24.
4. For each `preferred_skill`: same contains-check.
5. `preferred_score = round(preferred_matched / len(preferred_skills) * 6)` clamped 0–6.
6. `total = required_score + preferred_score`, clamped 0–30.
7. **Fallback:** if both lists are empty → 15 (neutral; can't penalise for missing JD data).

### 3.3 `experience_clarity` — 20 points

Heuristic checks on `resume_raw_text`. Each check is binary (0/1):

| Signal | Points | Detection |
|--------|--------|-----------|
| Date patterns | 6 | Regex: `\b(19\|20)\d{2}\b`, `Jan\|Feb\|…\|Dec \d{4}`, `\d{4}\s*[–-]\s*(present\|\d{4})` |
| Company name signal | 5 | Line contains `Ltd`, `Inc`, `Corp`, `LLC`, `Pvt`, `GmbH`, or 2+ consecutive Title-Case words near a year |
| Role designation | 5 | `resume_fields["current_title"]` is non-empty |
| Quantified achievements | 4 | Regex: `\d+\s*(%\|x\|X\|\$\|K\|M\|L\|cr)` or `\d{2,}` followed by a noun within 5 tokens |

### 3.4 `structure_completeness` — 20 points

Section header detection on `resume_raw_text` (case-insensitive line scan):

| Section | Points | Header keywords |
|---------|--------|-----------------|
| Summary | 5 | `summary`, `profile`, `objective`, `about me`, `professional summary` |
| Education | 5 | `education`, `academic`, `qualification` + degree keyword (`bachelor`, `master`, `b.tech`, `mba`, `phd`, `diploma`) nearby |
| Skills | 5 | `skills`, `technical skills`, `core competencies`, `technologies` |
| Certifications | 5 | `certif`, `courses`, `training`, `awards`, `achievements` |

---

## 4. Missing Info Detection (`app/scoring/missing_info.py`)

`detect_missing(resume_fields, resume_raw_text) -> List[MissingItem]`

| Severity | Field key | Label | Condition | Hint |
|----------|-----------|-------|-----------|------|
| HIGH | `work_dates` | Work experience dates | No date pattern in raw text | Add start/end year to each role |
| HIGH | `current_title` | Current job title | `resume_fields["current_title"]` empty | Add your most recent job title |
| MEDIUM | `achievements` | Measurable achievements | No `\d+.*(%\|x\|\$\|K\|M)` pattern | Quantify impact with numbers |
| MEDIUM | `company_names` | Employer names | No company signal (Ltd/Inc/Corp or Title-Case pairs near year) | Add company names to each role |
| LOW | `certifications` | Certifications | No cert/course header detected | Add any certifications or courses |
| LOW | `social_links` | LinkedIn / GitHub | No `linkedin.com` or `github.com` in raw text | Add your LinkedIn or GitHub URL |

---

## 5. Module Files

```
app/scoring/__init__.py      — re-exports compute_ats_score, detect_missing
app/scoring/models.py        — ATSScore, MissingItem dataclasses
app/scoring/ats_scorer.py    — compute_ats_score(resume_fields, jd_fields, resume_raw_text) -> ATSScore
app/scoring/missing_info.py  — detect_missing(resume_fields, resume_raw_text) -> List[MissingItem]
```

---

## 6. DB Impact

The `submissions` table has no `ats_score_json` column yet. The scorer is a pure-Python computation module — it does **not** write to DB. Persistence is deferred to Phase 4 (Review page), which will add the column and call the scorer.

---

## 7. Key Decisions

| Decision | Rationale |
|----------|-----------|
| Raw text as third param | LLM fields lack section/date/company context. Raw text heuristics fill the gap. |
| Substring skill matching | `"Python 3.10"` should match `"Python"`. Exact match would under-score. |
| Neutral fallback on empty JD lists | Sparse JD data shouldn't zero-score a strong resume. |
| `skills_missing` list in ATSScore | Review page needs it to render a "skills gap" panel without re-computing. |
| No DB write in Phase 3 | Keeps module boundary clean; Phase 4 owns persistence. |

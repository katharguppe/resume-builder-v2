# Quality Check Layer — Design Spec
**Phase:** 11
**Date:** 2026-04-23
**Scope:** `app/llm/quality_check.py` (new) + 3-line integration in `app/llm/finetuner.py`
**Status:** Approved

---

## 1. Objective

Insert a pre-output validation layer that runs after the variation engine and before PDF render. It detects five quality issues in the LLM-rewritten resume, auto-fixes where safe, and returns a structured report. The pipeline only reaches PDF render with a clean or auto-fixed draft.

---

## 2. Architecture

### New file
```
app/llm/quality_check.py
```

### Integration point (finetuner.py)
```
LLM rewrite (Claude or DeepSeek)
  → apply_variation_to_resume()    [Phase 9 — existing]
  → validate_quality()             [Phase 11 — new]
  → return report.fixed_draft
```

Both `rewrite_resume()` and `rewrite_resume_deepseek()` receive the same 3-line addition after `apply_variation_to_resume`. No other files are touched.

---

## 3. Public Interface

```python
@dataclass
class QualityReport:
    passed: bool          # True when no [NEEDS REVIEW] issues remain
    issues: list[str]     # All issues, prefixed [AUTO-FIXED] or [NEEDS REVIEW]
    fixed_draft: dict     # Deep-copy of draft with safe auto-fixes applied

def validate_quality(
    resume_draft: dict,
    original: dict,           # {"raw_text": <original resume text>}
    jd_fields: dict | None = None,
) -> QualityReport:
    ...
```

### `passed` semantics
- `True` — no unfixable issues; draft is ready for PDF render (may have auto-fixes applied).
- `False` — at least one `[NEEDS REVIEW]` issue; caller should route to revision loop.

Auto-fixed issues are recorded in `issues` with `[AUTO-FIXED]` prefix but do **not** set `passed = False`.

### `original` convention
Caller passes `{"raw_text": resume_text}`. No extra LLM parse call required. The exaggeration check regex-extracts numbers from this field.

### `jd_fields` convention
Optional. When `None`, the `jd_keywords_present` check is skipped entirely and does not affect `passed`. When provided, expects `jd_fields.get("required_skills", [])` to be a list of strings.

---

## 4. Module-Level Constants

```python
BULLET_MAX_WORDS = 30
NGRAM_SIZE = 4
WORD_FREQ_THRESHOLD = 4
```

All thresholds are top-of-file constants — no magic numbers inside functions.

---

## 5. The Five Checks

### 5.1 `_check_tone_repetitive(summary, experience)`
**Type:** Pure Python
**Auto-fix:** No

**N-gram pass:**
Generate all `NGRAM_SIZE`-word ngrams per section (summary = 1 section, each role's bullets combined = 1 section). Flag any ngram that appears in 2 or more sections.

**Word-frequency pass:**
Tokenise all draft text (lowercase, strip punctuation). Remove stopwords:
`{"and","the","to","of","in","a","for","with","on","is","was","at","by","an","as"}`.
Flag any word appearing ≥ `WORD_FREQ_THRESHOLD` times across the whole draft.

**Issue format:**
```
[NEEDS REVIEW] Repetitive phrase across sections: 'managed a team of'
[NEEDS REVIEW] Word 'managed' used 5 times across draft
```

---

### 5.2 `_check_experience_exaggerated(all_bullets, summary, original_raw_text)`
**Type:** Pure Python (numeric heuristic)
**Auto-fix:** No

Regex `r'\b\d[\d,]*(?:\.\d+)?%?\b'` applied to both `original_raw_text` and the flattened draft text (summary + all bullets). Any numeric token present in draft but absent from original is flagged.

**Issue format:**
```
[NEEDS REVIEW] Unverified metric not found in original resume: '40%'
```

---

### 5.3 `_check_bullets_too_long(working_draft)`
**Type:** Pure Python
**Auto-fix:** Yes — truncate at word `BULLET_MAX_WORDS`, append `"…"`

Iterates `experience[].bullets[]`. Any bullet with `len(bullet.split()) > BULLET_MAX_WORDS` is trimmed in-place on the working copy (already a deep-copy).

**Issue format (logged even when fixed):**
```
[AUTO-FIXED] Bullet trimmed to 30 words in role 'Sales Manager'
```

---

### 5.4 `_check_recent_exp_prioritized(working_draft)`
**Type:** Pure Python
**Auto-fix:** No (reordering bullets across roles requires understanding chronology — not safe)

`experience[0]` must have bullet count ≥ all other roles. If not, flagged.

**Issue format:**
```
[NEEDS REVIEW] Most recent role has fewer bullets than another role (3 vs 5)
```

---

### 5.5 `_check_jd_keywords_present(working_draft, jd_fields)`
**Type:** Pure Python
**Auto-fix:** No
**Skip condition:** `jd_fields is None`

Case-insensitive substring match of each `required_skills` keyword against full draft text (summary + all bullets + skills[]). One issue per missing keyword.

**Issue format:**
```
[NEEDS REVIEW] JD keyword missing from resume: 'stakeholder management'
```

---

## 6. `validate_quality()` Internal Flow

```
1. working_draft = copy.deepcopy(resume_draft)
2. Pre-compute: summary (str), all_bullets (flat list[str])
3. original_raw_text = original.get("raw_text", "")
4. Run each check inside try/except:
     - _check_tone_repetitive(summary, all_bullets)
     - _check_experience_exaggerated(all_bullets, summary, original_raw_text)
     - _check_bullets_too_long(working_draft)      ← mutates working_draft
     - _check_recent_exp_prioritized(working_draft)
     - _check_jd_keywords_present(working_draft, jd_fields)
5. Collect all issues[]
6. passed = not any(i.startswith("[NEEDS REVIEW]") for i in issues)
7. return QualityReport(passed=passed, issues=issues, fixed_draft=working_draft)
```

---

## 7. Error Handling

Each check is individually wrapped in `try/except Exception`. A failing check logs a `WARNING` and returns an empty issues list — it never crashes the pipeline. A broken quality check must not block PDF delivery.

Malformed or missing fields (`experience` key absent, bullet not a string, etc.) are silently skipped per check, consistent with the defensive pattern in `apply_variation_to_resume()`.

---

## 8. Performance

All 5 checks are pure Python string operations — no I/O, no LLM calls, no network.
Pre-computation of `summary` and `all_bullets` is done once and shared.
Expected runtime: < 50ms for a typical resume. Well within the 5s budget.

---

## 9. Testing Requirements

- Every check function is independently unit-testable with a synthetic `dict`.
- No mocking required (no LLM calls in this module).
- Tests live in `tests/test_quality_check.py`.
- Cover: happy path (no issues), each issue type triggered individually, auto-fix applied and verified, `jd_fields=None` skip, malformed input (missing keys, wrong types).

---

## 10. Preserved Modules

No v1 modules are touched. `app/ingestor/`, `app/composer/`, `app/email_handler/`, `app/best_practice/` are unchanged. `variation_engine.py` is unchanged.

---

## 11. Not In Scope

- LLM calls inside `quality_check.py` (deferred — pure Python sufficient for Phase 11)
- UI surface for quality issues (Phase 12 integration)
- Revision loop trigger on `passed = False` (caller's responsibility, not this module)

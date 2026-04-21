# Phase 9: Language Variation Engine — Design Spec
**Date:** 2026-04-21
**Branch:** feature/phase-02-upload-parse
**Status:** Approved

---

## Objective

Add a post-processing layer that detects and replaces overused résumé clichés in LLM rewrite output. Runs after JSON parsing, before Phase 11 quality check. Zero LLM calls, zero latency cost.

---

## Scope

**New file only:** `app/llm/variation_engine.py`
**Modified file:** `app/llm/finetuner.py` (two one-line additions)
**New test file:** `tests/test_variation_engine.py`

---

## Data

### `BANNED_PHRASES`
Flat list of 28 cliché strings detected case-insensitively. Split into two categories:

**With synonym groups (12 — replaced on match):**
- cross-functional
- results-driven
- self-starter
- team player
- detail-oriented
- go-getter
- synergy
- leverage
- proactive
- dynamic
- passionate about
- thought leader

**No-replacement entries (8 — detected only, left untouched if no group exists):**
- go above and beyond
- think outside the box
- value add
- low-hanging fruit
- move the needle
- circle back
- at the end of the day
- hit the ground running

### `SYNONYM_GROUPS`
`dict[str, list[str]]` — keyed by canonical banned phrase (lowercase), value = 3–5 alternatives:

| Key | Alternatives |
|-----|-------------|
| cross-functional | multi-team, cross-team, organisation-wide, interdepartmental |
| results-driven | outcome-focused, delivery-focused, performance-oriented |
| self-starter | proactive, takes initiative, works independently |
| team player | collaborative, works well with others, strong team contributor |
| detail-oriented | thorough, precise, meticulous |
| go-getter | motivated, driven, ambitious |
| synergy | collaboration, alignment, joint effort |
| leverage | use, apply, draw on |
| proactive | forward-thinking, anticipates needs, takes initiative |
| dynamic | adaptable, versatile, high-energy |
| passionate about | committed to, focused on, dedicated to |
| thought leader | subject matter expert, domain expert, recognised authority |

---

## Functions

### `apply_variation(text: str) -> str`

Core phrase-replacement function. Pure — no side effects, no state between calls.

**Algorithm:**
1. At module load, compile one `re.Pattern` per key in `SYNONYM_GROUPS` using `\b` word boundaries and `re.IGNORECASE`. Store as module-level `_COMPILED_PATTERNS: list[tuple[re.Pattern, list[str]]]`.
2. For each `(pattern, alternatives)` pair: search `text` for a match.
3. On match: pick a random alternative via `random.choice(alternatives)`.
4. Preserve lead capitalisation: if the matched substring's first character is uppercase, capitalise the replacement's first character.
5. Replace all occurrences in one `re.sub()` call per pattern (using a lambda for per-match capitalisation logic).
6. If no group exists for a banned phrase (no-replacement entries), text is returned unchanged.
7. Return modified text.

**Complexity:** O(n × p) where n = text length, p = number of synonym groups (~12). Resume prose is ≤500 words — no performance concern.

### `apply_variation_to_resume(data: dict) -> dict`

Dict-traversal wrapper. Applies `apply_variation()` to prose fields only.

**Fields modified:**
- `data["summary"]` (str)
- `data["experience"][i]["bullets"][j]` (each bullet string)

**Fields never touched:**
- `skills[]` — keyword-matched terms; variation breaks ATS alignment
- `contact`, `education`, `candidate_name` — structured/factual fields

**Behaviour:**
- Deep-copies input dict before modifying (never mutates caller's data)
- Graceful on missing/malformed keys: `KeyError` / `TypeError` → skips that field silently, continues
- Returns modified dict

---

## Integration

In `app/llm/finetuner.py`, both rewrite paths get one line added after `json.loads(...)`:

```python
from app.llm.variation_engine import apply_variation_to_resume

# in rewrite_resume (Claude path):
result = json.loads(_strip_markdown_fences(response.content[0].text))
return apply_variation_to_resume(result)

# in rewrite_resume_deepseek (DeepSeek path):
result = json.loads(_strip_markdown_fences(response.choices[0].message.content))
return apply_variation_to_resume(result)
```

Phase 11 (`quality_check.py`) receives the already-varied dict — no further changes to the call chain.

---

## Tests (`tests/test_variation_engine.py`)

~20 tests. All replacement assertions use `in alternatives_list` (not equality) since replacement is random.

**Per synonym group (12 tests):**
- One test per group: inject the banned phrase into a sentence, assert the result contains one of the known alternatives and does not contain the original phrase.

**Core behaviour (8 tests):**
- `test_apply_variation_no_match` — text with no banned phrases returns unchanged
- `test_apply_variation_case_preserved` — capitalised phrase at bullet start → capitalised replacement
- `test_apply_variation_case_insensitive` — mixed-case match ("Cross-Functional") is caught
- `test_apply_variation_unknown_phrase_untouched` — a no-replacement banned phrase is not mangled
- `test_apply_variation_to_resume_summary` — banned phrase in summary is replaced
- `test_apply_variation_to_resume_bullets` — banned phrase in a bullet is replaced
- `test_apply_variation_to_resume_skills_untouched` — skills list is never modified
- `test_apply_variation_to_resume_missing_keys` — empty dict / partial dict does not raise

---

## What is NOT in scope

- Variation of skills, contact, education, or candidate name fields
- LLM-assisted variation (adds latency + cost)
- Configurable phrase lists via env var or DB (YAGNI — flat constants are sufficient)
- Tracking which replacements were made (no audit log needed at this phase)

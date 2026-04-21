# Phase 9: Language Variation Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `app/llm/variation_engine.py` — a pure post-processing function that detects and replaces overused résumé clichés in LLM rewrite output before Phase 11 quality check.

**Architecture:** One new module (`variation_engine.py`) exposes two functions: `apply_variation(text) -> text` (core string transformer, regex-based) and `apply_variation_to_resume(data) -> data` (dict traversal wrapper that covers prose fields only). Regex patterns are compiled once at module load. Integration is two one-line additions in `finetuner.py` — one per rewrite path (Claude + DeepSeek).

**Tech Stack:** Python 3.13 stdlib only — `re`, `random`, `copy`. No new dependencies.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/llm/variation_engine.py` | Create | `BANNED_PHRASES`, `SYNONYM_GROUPS`, `_COMPILED_PATTERNS`, `apply_variation()`, `apply_variation_to_resume()` |
| `app/llm/finetuner.py` | Modify | Import + call `apply_variation_to_resume()` in both rewrite paths |
| `tests/test_variation_engine.py` | Create | 22 tests covering all 12 synonym groups + 10 edge/behaviour cases |

---

### Task 1: Scaffold variation_engine.py with constants and stubs

**Files:**
- Create: `app/llm/variation_engine.py`

- [ ] **Step 1: Create the module**

Create `app/llm/variation_engine.py` with the full contents below:

```python
import copy
import random
import re


BANNED_PHRASES: list[str] = [
    # With synonym groups — replaced on match
    "cross-functional",
    "results-driven",
    "self-starter",
    "team player",
    "detail-oriented",
    "go-getter",
    "synergy",
    "leverage",
    "proactive",
    "dynamic",
    "passionate about",
    "thought leader",
    # No-replacement entries — detected only, left untouched
    "go above and beyond",
    "think outside the box",
    "value add",
    "low-hanging fruit",
    "move the needle",
    "circle back",
    "at the end of the day",
    "hit the ground running",
]

SYNONYM_GROUPS: dict[str, list[str]] = {
    "cross-functional": ["multi-team", "cross-team", "organisation-wide", "interdepartmental"],
    "results-driven": ["outcome-focused", "delivery-focused", "performance-oriented"],
    "self-starter": ["independent worker", "takes initiative", "works independently"],
    "team player": ["collaborative", "works well with others", "strong team contributor"],
    "detail-oriented": ["thorough", "precise", "meticulous"],
    "go-getter": ["motivated", "driven", "ambitious"],
    "synergy": ["collaboration", "alignment", "joint effort"],
    "leverage": ["use", "apply", "draw on"],
    "proactive": ["forward-thinking", "anticipates needs", "takes initiative"],
    "dynamic": ["adaptable", "versatile", "high-energy"],
    "passionate about": ["committed to", "focused on", "dedicated to"],
    "thought leader": ["subject matter expert", "domain expert", "recognised authority"],
}

# Compiled once at module load — avoids re-compiling on every call.
# Only phrases in SYNONYM_GROUPS get a pattern; no-replacement entries are skipped.
_COMPILED_PATTERNS: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE), alternatives)
    for phrase, alternatives in SYNONYM_GROUPS.items()
]


def apply_variation(text: str) -> str:
    raise NotImplementedError


def apply_variation_to_resume(data: dict) -> dict:
    raise NotImplementedError
```

- [ ] **Step 2: Verify the module imports cleanly**

Run:
```bash
python -c "from app.llm.variation_engine import BANNED_PHRASES, SYNONYM_GROUPS, _COMPILED_PATTERNS; print('OK', len(BANNED_PHRASES), 'phrases,', len(SYNONYM_GROUPS), 'groups,', len(_COMPILED_PATTERNS), 'patterns')"
```

Expected output: `OK 20 phrases, 12 groups, 12 patterns`

- [ ] **Step 3: Commit**

```bash
git add app/llm/variation_engine.py
git commit -m "[PHASE-09] add: variation_engine.py scaffold with constants and stubs"
```

---

### Task 2: TDD — apply_variation()

**Files:**
- Create: `tests/test_variation_engine.py`
- Modify: `app/llm/variation_engine.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_variation_engine.py`:

```python
import pytest
from app.llm.variation_engine import (
    apply_variation,
    apply_variation_to_resume,
    SYNONYM_GROUPS,
    BANNED_PHRASES,
)


# ── Per-group tests (12 parametrized cases = 12 pytest tests) ──────────────

@pytest.mark.parametrize("phrase,sentence", [
    ("cross-functional",  "She leads cross-functional teams across the business."),
    ("results-driven",    "A results-driven professional with ten years of experience."),
    ("self-starter",      "Known as a self-starter who needs minimal supervision."),
    ("team player",       "A team player who thrives in collaborative environments."),
    ("detail-oriented",   "She is detail-oriented and catches errors early."),
    ("go-getter",         "Recognised as a go-getter within the department."),
    ("synergy",           "Created synergy between product and engineering teams."),
    ("leverage",          "Able to leverage existing infrastructure to cut costs."),
    ("proactive",         "Takes a proactive approach to stakeholder management."),
    ("dynamic",           "A dynamic professional comfortable in fast-moving environments."),
    ("passionate about",  "Passionate about delivering high-quality customer outcomes."),
    ("thought leader",    "Recognised as a thought leader in the fintech space."),
])
def test_synonym_group_replaced(phrase, sentence):
    result = apply_variation(sentence)
    assert phrase not in result.lower(), (
        f"Expected '{phrase}' to be replaced but found it in: {result!r}"
    )
    assert any(alt in result for alt in SYNONYM_GROUPS[phrase]), (
        f"Expected one of {SYNONYM_GROUPS[phrase]!r} in result: {result!r}"
    )


# ── Core behaviour tests ────────────────────────────────────────────────────

def test_apply_variation_no_match():
    text = "Increased quarterly revenue by 35% through targeted account expansion."
    assert apply_variation(text) == text


def test_apply_variation_case_preserved_uppercase():
    # Phrase at start of sentence — replacement must also be capitalised.
    result = apply_variation("Cross-functional collaboration is essential.")
    assert result[0].isupper(), f"Expected uppercase first char but got: {result!r}"
    assert "cross-functional" not in result.lower()


def test_apply_variation_case_insensitive_detection():
    result = apply_variation("She is CROSS-FUNCTIONAL in her approach.")
    assert "cross-functional" not in result.lower()
    assert any(alt in result for alt in SYNONYM_GROUPS["cross-functional"])


def test_apply_variation_no_replacement_phrase_untouched():
    # "hit the ground running" is in BANNED_PHRASES but NOT in SYNONYM_GROUPS.
    # No pattern is compiled for it, so apply_variation must leave it unchanged.
    text = "Ready to hit the ground running from day one."
    assert apply_variation(text) == text


def test_apply_variation_returns_string():
    result = apply_variation("A results-driven and dynamic professional.")
    assert isinstance(result, str)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_variation_engine.py -v`

Expected: 17 FAILs with `NotImplementedError`

- [ ] **Step 3: Implement apply_variation()**

In `app/llm/variation_engine.py`, add `_replace_preserving_case` and replace the `apply_variation` stub. The final function section of the file should look like this:

```python
def _replace_preserving_case(match: re.Match, alternatives: list[str]) -> str:
    replacement = random.choice(alternatives)
    if match.group(0)[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def apply_variation(text: str) -> str:
    """
    Detect any phrase present in SYNONYM_GROUPS and replace it with a randomly
    selected alternative. Preserves lead capitalisation of the matched text.
    Phrases in BANNED_PHRASES with no synonym group are left untouched.
    """
    for pattern, alternatives in _COMPILED_PATTERNS:
        text = pattern.sub(
            lambda m, alts=alternatives: _replace_preserving_case(m, alts),
            text,
        )
    return text


def apply_variation_to_resume(data: dict) -> dict:
    raise NotImplementedError
```

Important: `alts=alternatives` in the lambda is a default-argument capture. Without it, all lambdas in the loop would share the same `alternatives` reference (the last iteration's value). This is the standard Python closure-in-loop fix.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_variation_engine.py -v`

Expected: 17 PASSes, 0 failures

- [ ] **Step 5: Commit**

```bash
git add tests/test_variation_engine.py app/llm/variation_engine.py
git commit -m "[PHASE-09] add: apply_variation with 17 tests passing"
```

---

### Task 3: TDD — apply_variation_to_resume()

**Files:**
- Modify: `tests/test_variation_engine.py` (append 5 tests)
- Modify: `app/llm/variation_engine.py` (implement stub)

- [ ] **Step 1: Append the failing tests**

Append the following to the end of `tests/test_variation_engine.py`:

```python
# ── apply_variation_to_resume tests ────────────────────────────────────────

def test_apply_variation_to_resume_summary():
    data = {
        "candidate_name": "Alice Smith",
        "summary": "A results-driven and detail-oriented professional.",
        "experience": [],
        "skills": ["Python", "results-driven"],
        "missing_fields": [],
    }
    result = apply_variation_to_resume(data)
    assert "results-driven" not in result["summary"].lower()
    assert "detail-oriented" not in result["summary"].lower()


def test_apply_variation_to_resume_bullets():
    data = {
        "candidate_name": "Bob Jones",
        "summary": "Experienced professional.",
        "experience": [
            {
                "title": "Manager",
                "company": "Acme",
                "dates": "2020-2024",
                "bullets": [
                    "Led cross-functional teams to deliver on time.",
                    "Recognised as a thought leader in operations.",
                ],
            }
        ],
        "skills": ["leadership"],
        "missing_fields": [],
    }
    result = apply_variation_to_resume(data)
    bullets = result["experience"][0]["bullets"]
    assert "cross-functional" not in bullets[0].lower()
    assert "thought leader" not in bullets[1].lower()


def test_apply_variation_to_resume_skills_untouched():
    # skills[] are ATS keyword terms — must never be modified.
    data = {
        "candidate_name": "Carol Lee",
        "summary": "Experienced professional.",
        "experience": [],
        "skills": ["cross-functional leadership", "results-driven delivery"],
        "missing_fields": [],
    }
    result = apply_variation_to_resume(data)
    assert result["skills"] == data["skills"]


def test_apply_variation_to_resume_missing_keys():
    # Empty dict and partial dicts must not raise.
    assert apply_variation_to_resume({}) == {}
    result = apply_variation_to_resume({"summary": "Clean professional text."})
    assert result == {"summary": "Clean professional text."}


def test_apply_variation_to_resume_does_not_mutate_input():
    original_summary = "A results-driven professional."
    data = {"summary": original_summary, "experience": [], "skills": []}
    apply_variation_to_resume(data)
    assert data["summary"] == original_summary
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `pytest tests/test_variation_engine.py -v -k "resume"`

Expected: 5 FAILs with `NotImplementedError`

- [ ] **Step 3: Implement apply_variation_to_resume()**

Replace the `apply_variation_to_resume` stub in `app/llm/variation_engine.py`:

```python
def apply_variation_to_resume(data: dict) -> dict:
    """
    Apply apply_variation() to prose fields in a rewrite output dict.

    Modified:   summary (str), experience[i].bullets[j] (each bullet str)
    Untouched:  skills[], contact, education, candidate_name

    Deep-copies input — never mutates the caller's dict.
    Silently skips missing or malformed fields.
    """
    result = copy.deepcopy(data)

    try:
        if isinstance(result.get("summary"), str):
            result["summary"] = apply_variation(result["summary"])
    except (KeyError, TypeError, AttributeError):
        pass

    try:
        for role in result.get("experience", []):
            if isinstance(role.get("bullets"), list):
                role["bullets"] = [
                    apply_variation(b) if isinstance(b, str) else b
                    for b in role["bullets"]
                ]
    except (KeyError, TypeError, AttributeError):
        pass

    return result
```

- [ ] **Step 4: Run the full test file**

Run: `pytest tests/test_variation_engine.py -v`

Expected: 22 PASSes, 0 failures

- [ ] **Step 5: Commit**

```bash
git add tests/test_variation_engine.py app/llm/variation_engine.py
git commit -m "[PHASE-09] add: apply_variation_to_resume with 22 tests passing"
```

---

### Task 4: Integrate into finetuner.py

**Files:**
- Modify: `app/llm/finetuner.py`

- [ ] **Step 1: Add the import**

In `app/llm/finetuner.py`, after the existing imports block (after the `from app.llm.prompt_builder import ...` block), add:

```python
from app.llm.variation_engine import apply_variation_to_resume
```

- [ ] **Step 2: Patch the Claude rewrite path**

In `rewrite_resume()`, inside the retry loop, the current return statement is:

```python
return json.loads(_strip_markdown_fences(response.content[0].text))
```

Replace it with:

```python
result = json.loads(_strip_markdown_fences(response.content[0].text))
return apply_variation_to_resume(result)
```

- [ ] **Step 3: Patch the DeepSeek rewrite path**

In `rewrite_resume_deepseek()`, inside the retry loop, the current return statement is:

```python
return json.loads(_strip_markdown_fences(response.choices[0].message.content))
```

Replace it with:

```python
result = json.loads(_strip_markdown_fences(response.choices[0].message.content))
return apply_variation_to_resume(result)
```

- [ ] **Step 4: Run the full test suite**

Run: `pytest --tb=short -q`

Expected: 329 pre-existing + 22 new = 351 tests passing, 0 failures

- [ ] **Step 5: Commit**

```bash
git add app/llm/finetuner.py
git commit -m "[PHASE-09] add: apply_variation_to_resume integration in finetuner rewrite paths"
```

---

### Task 5: Update task file and final checkpoint commit

**Files:**
- Modify: `tasks/PHASE-09-language-variation-engine.md`

- [ ] **Step 1: Update the task file**

Replace the full contents of `tasks/PHASE-09-language-variation-engine.md` with:

```markdown
# PHASE-09: Language Variation Engine

## Status: COMPLETE
## Phase: 9 / 12

## Objective
Post-processing layer that detects and replaces overused résumé clichés in LLM rewrite
output. Runs after JSON parsing in both rewrite paths, before Phase 11 quality check.
Zero LLM calls, zero latency cost.

## v1 Foundation
None — net-new module.

## Net New
- app/llm/variation_engine.py: BANNED_PHRASES (20), SYNONYM_GROUPS (12 groups),
  _COMPILED_PATTERNS (12 compiled regexes), apply_variation(), apply_variation_to_resume()
- tests/test_variation_engine.py: 22 tests

## PDCA Log

### Cycle 1
**Plan:** Design spec at docs/superpowers/specs/2026-04-21-phase09-variation-engine-design.md
**Approved by human:** Yes
**Do:** variation_engine.py + tests + finetuner.py integration
**Check:** 351 tests passing (329 pre-existing + 22 new)
**Act:** Phase complete — proceed to Phase 10 (Payment Gate)

## Decisions Made
- apply_variation_to_resume() deep-copies input dict — never mutates caller's data
- skills[] is never modified — ATS keyword alignment takes priority over variation
- "proactive" removed from self-starter alternatives to prevent double-replacement chain
- No-replacement BANNED_PHRASES entries (8) are left untouched — no pattern compiled for them
- _COMPILED_PATTERNS compiled once at module load (not per call)
- lambda default-arg capture (alts=alternatives) used to avoid Python closure-in-loop bug

## Checkpoints
- [x] variation_engine.py scaffold committed
- [x] apply_variation() implemented and tested (17 tests)
- [x] apply_variation_to_resume() implemented and tested (22 tests total)
- [x] finetuner.py integration committed (both Claude + DeepSeek paths)
- [x] Full suite: 351 tests passing
```

- [ ] **Step 2: Final checkpoint commit**

```bash
git add tasks/PHASE-09-language-variation-engine.md
git commit -m "[PHASE-09] checkpoint: variation engine complete - verified"
```

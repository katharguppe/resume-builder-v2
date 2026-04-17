# Phase 08 — Personalization Logic: Design Spec

**Date:** 2026-04-17
**Branch:** feature/phase-02-upload-parse
**Scope:** `app/llm/prompt_builder.py` only (extend, do not rewrite)
**Status:** Approved — ready for implementation planning

---

## 1. Objective

Each resume rewrite must feel tailored to the individual candidate — their career stage and the function they are targeting — and no two resumes should produce near-identical language even when the inputs are similar.

This is achieved by:
1. Auto-detecting `experience_level` from the candidate's resume text
2. Auto-detecting `function_type` from the job description text
3. Injecting a personalisation block into `build_finetuning_prompt` that sets focus, tone, bullet counts, and a randomly-sampled verb set unique to each call

---

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Where detection lives | `prompt_builder.py` only | CLAUDE.md §4 module boundary |
| Param threading | Optional params on `build_finetuning_prompt` with auto-detect fallback | Testable in isolation; callers need no changes |
| UI exposure | None — silent auto-detect | Candidate never sees detected values |
| Experience detection strategy | Duration math first, keyword fallback | Robust to varied date formats; non-tech clients |
| Function type tie-breaking | Highest keyword count wins; tie → `general` | Most representative for hybrid roles |
| Cross-resume uniqueness | Random verb bank sample (10/30) + random tone variant (1/3) | No two resumes get identical language instructions |

---

## 3. New Public Exports

```python
# app/llm/prompt_builder.py

def detect_experience_level(resume_text: str) -> str:
    """
    Returns: "fresher" | "early" | "mid" | "senior"
    Strategy: parse year spans → sum months → bucket.
              Fallback to keyword scan if < 2 spans found.
    """

def detect_function_type(jd_text: str) -> str:
    """
    Returns: "technical" | "sales" | "operations" | "academic" | "general"
    Strategy: keyword hit count per type; tie → "general"
    """

def build_finetuning_prompt(
    resume_text: str,
    jd_text: str,
    best_practice_text: str,
    candidate_name: str,
    revision_hint: str = "",
    experience_level: str = "",   # auto-detected if ""
    function_type: str = "",      # auto-detected if ""
) -> str:
    ...
```

---

## 4. Private Helpers

```python
def _sum_experience_months(resume_text: str) -> int | None:
    """
    Regex patterns:
      - Year spans:  r"(\d{4})\s*[-–—to]+\s*(\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)"
      - Explicit:    r"(\d+)\+?\s*years?\s*(of\s+)?experience"
      - Written:     "ten years" → convert via word-to-number map
    Returns None if fewer than 2 spans found (triggers keyword fallback).
    Present/Current treated as current year.
    """

def _keyword_experience_level(resume_text: str) -> str:
    """
    Keyword map (case-insensitive, whole-word):
      fresher: intern, trainee, graduate, fresher, entry level, entry-level
      early:   associate, junior, coordinator, assistant
      mid:     manager, lead, specialist
      senior:  director, vp, vice president, head of, chief, partner, principal
    Check order: senior → mid → early → fresher (most specific first).
    A match at any tier immediately returns that tier.
    Default if no keywords found: "early"
    """

def _build_personalization_block(
    experience_level: str,
    function_type: str,
) -> str:
    """
    Produces the === PERSONALISATION === prompt section.
    Calls random.sample(_VERB_BANKS[function_type], 10)
    Calls random.choice(_TONE_VARIANTS[function_type])
    """
```

---

## 5. Experience Level Definitions

| Level | Years | Focus Instruction | Bullet Counts |
|-------|-------|-------------------|---------------|
| `fresher` | 0–1y | Highlight education, academic projects, internships, and learning agility. Avoid overstating responsibility. | Recent: 4-5 · Previous: 2-3 · Older: 1-2 |
| `early` | 1–4y | Emphasise execution, delivery, and tool proficiency. Show measurable outputs, not just participation. | Recent: 5-6 · Previous: 3-4 · Older: 2-3 |
| `mid` | 4–8y | Lead with ownership, cross-functional impact, and quantified results. Show progression. | Recent: 6-7 · Previous: 4-5 · Older: 2-3 |
| `senior` | 8y+ | Centre on leadership, scale, strategy, and organisational impact. Avoid tactical micro-detail in bullets. | Recent: 6-8 · Previous: 4-6 · Older: 2-4 |

---

## 6. Function Type Definitions

| Type | Keywords (sample) | Tone Instruction Variants (3 per type) |
|------|------------------|----------------------------------------|
| `technical` | engineer, developer, architect, devops, software, data, backend, frontend, cloud, infrastructure | See Section 6a |
| `sales` | sales, account executive, business development, quota, pipeline, revenue, territory, conversion | See Section 6a |
| `operations` | operations, process, logistics, SLA, efficiency, supply chain, coordinator, fulfilment | See Section 6a |
| `academic` | teacher, lecturer, curriculum, research, academic, faculty, professor, instructor, education | See Section 6a |
| `general` | (catch-all — no dominant type matched) | See Section 6a |

---

## 6a. Tone Variant Strings (3 per type — one randomly selected per call)

### `technical`
1. "Use precise technical language. Name tools, architectures, and methodologies explicitly. Quantify throughput, latency, scale, and reliability."
2. "Lead with the engineering outcome first, then the method. Be specific about stack, scope, and scale. Avoid vague phrases like 'worked on' or 'helped with'."
3. "Name the technology, state the problem it solved, and quantify the impact. Favour concrete metrics: uptime, speed, volume, cost savings."

### `sales`
1. "Lead every bullet with a commercial outcome — revenue, pipeline, or conversion rate first."
2. "Open each bullet with the deal or customer impact, then the action that caused it. Use numbers wherever possible."
3. "Frame every achievement around targets: what was set, what was delivered, by how much. Avoid soft language — use hard commercial metrics."

### `operations`
1. "Focus on process improvements and their measurable outcomes: time saved, cost reduced, error rate lowered, SLA met."
2. "Lead with the operational outcome. State the process changed, the scale affected, and the metric that improved."
3. "Quantify efficiency gains. Name the process, the intervention, and the result in concrete operational terms."

### `academic`
1. "Lead with student or research outcomes. Avoid corporate jargon. Use language natural to the education sector."
2. "Highlight curriculum impact, cohort outcomes, and institutional contributions. Quantify where possible: class size, pass rates, publications."
3. "Frame achievements around learner progress, research contribution, or programme development. Be specific about subject, level, and outcome."

### `general`
1. "Use balanced professional language. Mix delivery, collaboration, and outcomes. Avoid domain-specific jargon."
2. "Lead with the result, then the action. Keep language accessible and professional without leaning into any one functional area."
3. "Emphasise cross-functional contribution, clear delivery, and measurable impact. Write for a broad professional audience."

---

## 7. Verb Banks (30 per function type, 10 sampled per call)

### `sales`
Secured, Grew, Negotiated, Closed, Expanded, Converted, Prospected, Retained, Exceeded, Pitched,
Cultivated, Drove, Upsold, Sourced, Achieved, Accelerated, Generated, Developed, Strengthened,
Targeted, Acquired, Delivered, Maximised, Penetrated, Identified, Presented, Renewed, Captured,
Built, Surpassed

### `technical`
Architected, Engineered, Optimised, Deployed, Built, Automated, Scaled, Debugged, Integrated,
Migrated, Designed, Developed, Refactored, Implemented, Benchmarked, Secured, Containerised,
Instrumented, Orchestrated, Profiled, Streamlined, Modernised, Provisioned, Analysed, Tested,
Released, Monitored, Resolved, Documented, Reviewed

### `operations`
Streamlined, Reduced, Coordinated, Implemented, Improved, Standardised, Managed, Tracked,
Established, Consolidated, Optimised, Oversaw, Maintained, Facilitated, Reported, Resolved,
Identified, Reviewed, Delivered, Introduced, Automated, Planned, Aligned, Monitored, Controlled,
Collaborated, Eliminated, Restructured, Trained, Communicated

### `academic`
Designed, Delivered, Mentored, Developed, Assessed, Facilitated, Published, Evaluated, Guided,
Taught, Coordinated, Researched, Supervised, Supported, Implemented, Led, Created, Revised,
Collaborated, Advised, Presented, Reviewed, Established, Contributed, Initiated, Coached,
Wrote, Examined, Prepared, Modelled

### `general`
Led, Delivered, Collaborated, Supported, Contributed, Coordinated, Achieved, Produced, Managed,
Drove, Facilitated, Improved, Developed, Organised, Communicated, Executed, Represented,
Partnered, Maintained, Established, Strengthened, Ensured, Progressed, Guided, Assisted,
Resolved, Planned, Built, Engaged, Participated

---

## 8. Personalisation Block — Injected Prompt Text

Injected between `=== OBJECTIVE ===` and `=== CRITICAL CONSTRAINT ===`.

```
=== PERSONALISATION ===
Experience level: {LEVEL_UPPER} ({years_range})
Focus: {focus_instruction}
Tone: {randomly_selected_tone_variant}
Bullet counts: Most recent role: {n}-{m} bullets | Previous roles: {p}-{q} bullets | Older roles: {r}-{s} bullets
Preferred action verbs for this resume (vary your selection — do not use any verb more than twice):
  {10 randomly sampled verbs, comma-separated}
Format every bullet as: [Action verb] + [Context / Method] + [Measurable outcome]
```

---

## 9. Prompt Structure (after Phase 8)

```
CANDIDATE NAME: {candidate_name}

=== BEST PRACTICE FORMATTING TO FOLLOW ===
{best_practice_text}

=== JOB DESCRIPTION ===
{jd_text}

=== CANDIDATE ORIGINAL RESUME ===
{resume_text}

=== OBJECTIVE ===
[existing rewrite rules — unchanged]

=== PERSONALISATION ===        ← NEW
[injected block as above]

=== CRITICAL CONSTRAINT ===
[existing no-hallucination rule — unchanged]

=== OUTPUT SCHEMA ===
[existing JSON schema — unchanged]

[=== REVISION REQUEST === if revision_hint provided — unchanged]
```

---

## 10. Files Changed

| File | Change |
|------|--------|
| `app/llm/prompt_builder.py` | Add `detect_experience_level`, `detect_function_type`, `_sum_experience_months`, `_keyword_experience_level`, `_build_personalization_block`; extend `build_finetuning_prompt` signature |
| No other files | All existing callers work unchanged via default params |

---

## 11. Testing Targets

| Test | Type |
|------|------|
| `detect_experience_level` — duration math buckets | Pure unit |
| `detect_experience_level` — keyword fallback triggers | Pure unit |
| `detect_experience_level` — present/current year handling | Pure unit |
| `detect_function_type` — each type dominant | Pure unit |
| `detect_function_type` — tie resolves to general | Pure unit |
| `_build_personalization_block` — all 4 levels × 5 types | Pure unit |
| `_build_personalization_block` — verb count is 10 | Pure unit |
| `_build_personalization_block` — verbs change across calls | Statistical unit |
| `build_finetuning_prompt` — PERSONALISATION block present in output | Pure unit |
| `build_finetuning_prompt` — explicit override params respected | Pure unit |
| Existing `test_prompt_builder.py` tests — all still pass | Regression |

---

## 12. Acceptance Criteria (from tasks/PHASE-08-personalization-logic.md)

- [ ] `detect_experience_level(resume_text)` returns correct tier for varied date formats
- [ ] `detect_function_type(jd_text)` returns correct type; ties → `general`
- [ ] `build_finetuning_prompt` output contains `=== PERSONALISATION ===` block
- [ ] Verb set differs across two calls with identical inputs (randomisation confirmed)
- [ ] All existing tests still pass (v1 baseline preserved)
- [ ] No files outside `app/llm/prompt_builder.py` modified
- [ ] No hardcoded model names, API keys, or provider strings introduced

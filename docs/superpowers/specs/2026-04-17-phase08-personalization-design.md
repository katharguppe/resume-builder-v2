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
| Cross-resume uniqueness | Random verb bank sample (10/100) + random tone variant (1/10) | Strong uniqueness guarantee; no two resumes get identical language |

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

| Type | Detection Keywords (sample) |
|------|-----------------------------|
| `technical` | engineer, developer, architect, devops, software, data, backend, frontend, cloud, infrastructure |
| `sales` | sales, account executive, business development, quota, pipeline, revenue, territory, conversion |
| `operations` | operations, process, logistics, SLA, efficiency, supply chain, coordinator, fulfilment |
| `academic` | teacher, lecturer, curriculum, research, academic, faculty, professor, instructor, education |
| `general` | (catch-all — no dominant type matched) |

---

## 6a. Tone Variant Strings (10 per type — one randomly selected per call)

### `technical`
1. "Use precise technical language. Name tools, architectures, and methodologies explicitly. Quantify throughput, latency, scale, and reliability."
2. "Lead with the engineering outcome first, then the method. Be specific about stack, scope, and scale. Avoid vague phrases like 'worked on' or 'helped with'."
3. "Name the technology, state the problem it solved, and quantify the impact. Favour concrete metrics: uptime, speed, volume, cost savings."
4. "Open with scale: how many users, how much data, what traffic volume. Then state what you built and how it performed."
5. "Lead with the architectural decision and its consequence. What tradeoff was made? What was the measurable outcome?"
6. "Emphasise automation and efficiency gains: what was manual, what did you automate, what time or cost was saved?"
7. "Highlight cross-system integration: what systems were connected, what data flowed, what capability was unlocked."
8. "Focus on reliability and quality: uptime percentage, incident reduction, test coverage improvement, defect rate lowered."
9. "Lead with the business problem, then the technical solution, then the measurable result. Show that engineering served a commercial goal."
10. "Show technical ownership: what design decisions did you own, what standards did you define, what did you enable in others?"

### `sales`
1. "Lead every bullet with a commercial outcome — revenue, pipeline, or conversion rate first."
2. "Open each bullet with the deal or customer impact, then the action that caused it. Use numbers wherever possible."
3. "Frame every achievement around targets: what was set, what was delivered, by how much. Avoid soft language — use hard commercial metrics."
4. "Lead with the customer: who they were, what you won, what it was worth to the business."
5. "Emphasise territory growth: new accounts opened, market share gained, revenue split between new and existing clients."
6. "Show pipeline discipline: how you built, managed, and converted your pipeline. Use stage conversion and velocity metrics."
7. "Focus on retention and expansion: renewal rates, upsell value, net revenue retention percentage."
8. "Highlight relationship depth: seniority of stakeholders engaged, deal complexity navigated, negotiation outcomes achieved."
9. "Lead with the competitive angle: who you displaced, what the contract value was, why you won over the alternative."
10. "Show market development: new segments entered, new products taken to market, new channels established and their first-year output."

### `operations`
1. "Focus on process improvements and their measurable outcomes: time saved, cost reduced, error rate lowered, SLA met."
2. "Lead with the operational outcome. State the process changed, the scale it affected, and the metric that improved."
3. "Quantify efficiency gains. Name the process, the intervention, and the result in concrete operational terms."
4. "Lead with problem scope — how many people, transactions, or locations were affected — then what you did and what improved."
5. "Emphasise compliance and risk management: standards met, audits passed, incidents prevented, controls implemented."
6. "Show cost discipline: budget managed, savings achieved, waste eliminated, procurement terms improved."
7. "Focus on team and vendor performance: team size led, supplier relationships managed, KPIs set and tracked."
8. "Lead with service delivery outcomes: SLA performance percentage, customer satisfaction scores, resolution times improved."
9. "Highlight continuous improvement: what the baseline was, what you changed, what the new steady-state performance became."
10. "Show capacity and scale management: volumes handled, throughput achieved, growth accommodated without quality loss."

### `academic`
1. "Lead with student or research outcomes. Avoid corporate jargon. Use language natural to the education sector."
2. "Highlight curriculum impact, cohort outcomes, and institutional contributions. Quantify where possible: class size, pass rates, publications."
3. "Frame achievements around learner progress, research contribution, or programme development. Be specific about subject, level, and outcome."
4. "Lead with the learning outcome: what students could demonstrate after your teaching that they could not before."
5. "Emphasise research impact: citations received, publications produced, grants secured, collaborations established."
6. "Show programme leadership: curriculum designed from scratch, modules developed, assessment frameworks created."
7. "Focus on inclusion and accessibility: diverse learner needs addressed, differentiated strategies implemented, outcomes improved for specific cohorts."
8. "Highlight mentorship and student success: students supervised to completion, career outcomes achieved, academic progression rates."
9. "Lead with institutional contribution: committee work, policy shaped, strategic initiatives led at departmental or faculty level."
10. "Show professional development leadership: CPD programmes delivered, teacher training designed, communities of practice established."

### `general`
1. "Use balanced professional language. Mix delivery, collaboration, and outcomes. Avoid domain-specific jargon."
2. "Lead with the result, then the action. Keep language accessible and professional without leaning into any one functional area."
3. "Emphasise cross-functional contribution, clear delivery, and measurable impact. Write for a broad professional audience."
4. "Focus on stakeholder management: who you worked with, what you delivered together, and what the impact was on the organisation."
5. "Lead with project or initiative scope, then your specific contribution, then the outcome achieved."
6. "Show adaptability: different contexts you operated in, how you adjusted your approach, what you achieved in each."
7. "Highlight communication and influence: what you presented, what you reported, what decisions you shaped or informed."
8. "Focus on problem-solving: what the challenge was, how you approached it methodically, what was resolved."
9. "Lead with team contribution and enablement: how you supported others, what you made possible, what the collective outcome was."
10. "Show a continuous improvement mindset: what gap or problem you identified, what you proposed, what changed as a result."

---

## 7. Verb Banks (100 per function type, 10 sampled per call)

### `sales`
Secured, Grew, Negotiated, Closed, Expanded, Converted, Prospected, Retained, Exceeded, Pitched,
Cultivated, Drove, Upsold, Sourced, Achieved, Accelerated, Generated, Developed, Strengthened,
Targeted, Acquired, Delivered, Maximised, Penetrated, Identified, Presented, Renewed, Captured,
Built, Surpassed, Activated, Amplified, Brokered, Championed, Convinced, Deepened, Differentiated,
Dominated, Engaged, Established, Executed, Forged, Gained, Influenced, Initiated, Launched,
Leveraged, Managed, Navigated, Obtained, Onboarded, Opened, Outperformed, Owned, Partnered,
Pioneered, Positioned, Prioritised, Progressed, Promoted, Proposed, Qualified, Reached, Recovered,
Recruited, Represented, Revitalised, Scaled, Shaped, Showcased, Signed, Spearheaded, Stimulated,
Strategised, Structured, Sustained, Uncovered, Won, Yielded, Demonstrated, Mapped, Responded,
Tripled, Doubled, Advanced, Boosted, Communicated, Compelled, Handled, Orchestrated, Crafted,
Directed, Fulfilled, Recognised, Steered, Utilised, Validated, Energised, Maintained, Collaborated

### `technical`
Architected, Engineered, Optimised, Deployed, Automated, Scaled, Debugged, Integrated, Migrated,
Designed, Developed, Refactored, Implemented, Benchmarked, Secured, Containerised, Orchestrated,
Profiled, Modernised, Provisioned, Analysed, Tested, Released, Monitored, Resolved, Documented,
Built, Streamlined, Standardised, Configured, Launched, Maintained, Upgraded, Extended, Hardened,
Validated, Modelled, Scripted, Compiled, Packaged, Parallelised, Distributed, Encrypted, Patched,
Audited, Indexed, Cached, Traced, Abstracted, Instrumented, Mapped, Ported, Prototyped, Simulated,
Authored, Established, Reviewed, Structured, Delivered, Reduced, Improved, Eliminated, Created,
Enabled, Exposed, Integrated (grouped), Isolated, Leveraged, Operated, Overhauled, Rearchitected,
Redesigned, Replaced, Replatformed, Researched, Restructured, Stabilised, Tuned, Unified, Updated,
Verified, Wrote, Accelerated, Consolidated, Containerised, Defined, Drove, Fixed, Hardened,
Identified, Introduced, Led, Managed, Migrated, Piloted, Published, Ran, Shipped, Supported,
Transformed, Triaged, Troubleshot, Validated, Versioned, Visualised

### `operations`
Streamlined, Reduced, Coordinated, Implemented, Improved, Standardised, Managed, Tracked,
Established, Consolidated, Optimised, Oversaw, Maintained, Facilitated, Reported, Resolved,
Identified, Reviewed, Delivered, Introduced, Automated, Planned, Aligned, Monitored, Controlled,
Collaborated, Eliminated, Restructured, Trained, Communicated, Administered, Allocated, Assessed,
Audited, Benchmarked, Built, Centralised, Clarified, Commissioned, Configured, Contractually,
Deployed, Designed, Developed, Directed, Documented, Drove, Enforced, Evaluated, Executed,
Expanded, Forecasted, Formalised, Governed, Guided, Handled, Harmonised, Launched, Led,
Measured, Negotiated, Operated, Organised, Owned, Partnered, Piloted, Prioritised, Processed,
Procured, Produced, Quantified, Rationalised, Realigned, Redesigned, Remediated, Renewed,
Resourced, Scaled, Scheduled, Secured, Simplified, Sourced, Specified, Strengthened, Structured,
Supervised, Supported, Transformed, Upgraded, Validated, Verified, Visualised, Won

### `academic`
Designed, Delivered, Mentored, Developed, Assessed, Facilitated, Published, Evaluated, Guided,
Taught, Coordinated, Researched, Supervised, Supported, Implemented, Led, Created, Revised,
Collaborated, Advised, Presented, Reviewed, Established, Contributed, Initiated, Coached,
Wrote, Examined, Prepared, Modelled, Administered, Analysed, Authored, Benchmarked, Built,
Championed, Chaired, Communicated, Compiled, Conceptualised, Cultivated, Curated, Defined,
Demonstrated, Differentiated, Directed, Documented, Drafted, Drove, Edited, Enabled, Engaged,
Enhanced, Evaluated, Expanded, Explored, Extended, Formed, Fostered, Generated, Graduated,
Identified, Improved, Increased, Influenced, Integrated, Introduced, Launched, Managed, Mapped,
Navigated, Observed, Organised, Partnered, Piloted, Produced, Promoted, Proposed, Raised,
Recommended, Redesigned, Reformed, Represented, Reported, Secured, Shaped, Shared, Simplified,
Spearheaded, Strengthened, Structured, Trained, Transformed, Updated, Validated

### `general`
Led, Delivered, Collaborated, Supported, Contributed, Coordinated, Achieved, Produced, Managed,
Drove, Facilitated, Improved, Developed, Organised, Communicated, Executed, Represented,
Partnered, Maintained, Established, Strengthened, Ensured, Progressed, Guided, Assisted,
Resolved, Planned, Built, Engaged, Participated, Achieved, Adapted, Addressed, Advanced,
Analysed, Applied, Assessed, Balanced, Championed, Chaired, Clarified, Completed, Composed,
Conceptualised, Consolidated, Crafted, Created, Defined, Demonstrated, Designed, Directed,
Documented, Evaluated, Fostered, Generated, Handled, Identified, Implemented, Influenced,
Initiated, Integrated, Introduced, Launched, Leveraged, Managed, Mediated, Monitored,
Negotiated, Navigated, Obtained, Operated, Optimised, Oversaw, Owned, Prioritised, Proposed,
Provided, Raised, Recommended, Reformed, Reported, Researched, Reviewed, Scaled, Secured,
Shaped, Simplified, Spearheaded, Standardised, Streamlined, Structured, Submitted, Tracked,
Transformed, Updated, Utilised, Validated, Won

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
| `detect_experience_level` — duration math buckets (all 4 tiers) | Pure unit |
| `detect_experience_level` — keyword fallback triggers when < 2 date spans | Pure unit |
| `detect_experience_level` — present/current year handling | Pure unit |
| `detect_experience_level` — written years ("ten years") | Pure unit |
| `detect_function_type` — each type dominant keyword set | Pure unit |
| `detect_function_type` — tie resolves to general | Pure unit |
| `_build_personalization_block` — all 4 levels × 5 types produce output | Pure unit |
| `_build_personalization_block` — verb count is exactly 10 | Pure unit |
| `_build_personalization_block` — verbs differ across two calls with same inputs | Statistical unit |
| `_build_personalization_block` — tone variant differs across calls | Statistical unit |
| `build_finetuning_prompt` — PERSONALISATION block present in output | Pure unit |
| `build_finetuning_prompt` — explicit override params respected (no auto-detect fires) | Pure unit |
| Existing `test_prompt_builder.py` tests — all still pass | Regression |

---

## 12. Acceptance Criteria (from tasks/PHASE-08-personalization-logic.md)

- [ ] `detect_experience_level(resume_text)` returns correct tier for varied date formats
- [ ] `detect_function_type(jd_text)` returns correct type; ties → `general`
- [ ] `build_finetuning_prompt` output contains `=== PERSONALISATION ===` block
- [ ] Verb set (10 of 100) differs across two calls with identical inputs (randomisation confirmed)
- [ ] Tone variant (1 of 10) differs across calls (randomisation confirmed)
- [ ] All existing tests still pass (v1 baseline preserved)
- [ ] No files outside `app/llm/prompt_builder.py` modified
- [ ] No hardcoded model names, API keys, or provider strings introduced

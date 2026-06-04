# Phase 08 — Personalization Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `app/llm/prompt_builder.py` to auto-detect candidate experience level and JD function type, then inject a personalised, randomised prompt block so no two resume rewrites share identical language.

**Architecture:** All logic lives in `app/llm/prompt_builder.py` only — two new public detection functions, three private helpers, module-level constants for verb banks and tone variants, and an extended `build_finetuning_prompt` signature with optional override params. Existing callers need zero changes.

**Tech Stack:** Python 3.13 stdlib only (`re`, `random`, `datetime`). No new dependencies.

**Design spec:** `docs/superpowers/specs/2026-04-17-phase08-personalization-design.md`

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `app/llm/prompt_builder.py` | Modify | Add imports; add `_WORD_TO_NUM`, `_LEVEL_KEYWORDS`, `_FUNCTION_KEYWORDS`, `_LEVEL_CONFIG`, `_TONE_VARIANTS`, `_VERB_BANKS` constants; add `_sum_experience_months`, `_keyword_experience_level`, `detect_experience_level`, `detect_function_type`, `_build_personalization_block`; extend `build_finetuning_prompt` signature |
| `tests/test_prompt_builder.py` | Modify | Add tests for all new functions; fix `test_build_finetuning_prompt_no_hint_unchanged` (equality assertion breaks with randomisation) |

No other files are touched.

---

## Task 1: `_sum_experience_months` — year span and explicit year parsing

**Files:**
- Modify: `app/llm/prompt_builder.py` (top of file — imports + first helper)
- Modify: `tests/test_prompt_builder.py`

- [ ] **Step 1.1: Write failing tests**

Append to `tests/test_prompt_builder.py`:

```python
from app.llm.prompt_builder import _sum_experience_months
from datetime import datetime

_CY = datetime.now().year  # current year, used in present-tense assertions


def test_sum_experience_months_single_span_returns_none():
    # Fewer than 2 year spans and no explicit pattern → None (triggers keyword fallback)
    assert _sum_experience_months("Worked at Acme 2019 - 2022") is None


def test_sum_experience_months_two_spans_summed():
    text = "Acme Corp 2019 - 2022\nBeta Ltd 2015 - 2019"
    result = _sum_experience_months(text)
    assert result == (3 + 4) * 12  # 84


def test_sum_experience_months_present_uses_current_year():
    text = "Acme Corp 2020 - Present\nBeta Ltd 2015 - 2020"
    result = _sum_experience_months(text)
    assert result == ((_CY - 2020) + 5) * 12


def test_sum_experience_months_en_dash_separator():
    text = "Acme 2018\u20132021\nBeta 2015\u20132018"
    result = _sum_experience_months(text)
    assert result == (3 + 3) * 12  # 72


def test_sum_experience_months_explicit_years_phrase():
    # Only one date span, but explicit phrase available
    assert _sum_experience_months("5 years experience in sales") == 60


def test_sum_experience_months_explicit_years_with_plus():
    assert _sum_experience_months("10+ years of experience") == 120


def test_sum_experience_months_written_number():
    assert _sum_experience_months("ten years experience in finance") == 120


def test_sum_experience_months_no_pattern_returns_none():
    assert _sum_experience_months("I enjoy helping people and am a fast learner.") is None
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
pytest tests/test_prompt_builder.py::test_sum_experience_months_two_spans_summed -v
```

Expected: `ERROR` — `ImportError: cannot import name '_sum_experience_months'`

- [ ] **Step 1.3: Add imports and `_sum_experience_months` to `prompt_builder.py`**

Add at the very top of `app/llm/prompt_builder.py` (before any existing code):

```python
import random
import re
from datetime import datetime


# ── Constants ──────────────────────────────────────────────────────────────

_WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "twenty-five": 25, "thirty": 30,
}


# ── Experience detection helpers ───────────────────────────────────────────

def _sum_experience_months(resume_text: str) -> int | None:
    """
    Attempt to derive total months of experience from resume text.

    Strategy (in order):
      1. Find all year spans (e.g. '2019 - 2023', '2020–Present'); if >= 2 found, sum and return.
      2. Find an explicit phrase like '5+ years experience'; return that value.
      3. Find a written phrase like 'ten years experience'; return that value.
      4. Return None — triggers keyword fallback in detect_experience_level.
    """
    current_year = datetime.now().year
    total_months = 0
    spans_found = 0

    # Pattern 1: year ranges separated by dash/en-dash/em-dash/to
    year_span_re = re.compile(
        r'(\d{4})\s*[-\u2013\u2014to]+\s*(\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)'
    )
    for m in year_span_re.finditer(resume_text):
        start = int(m.group(1))
        end_raw = m.group(2).lower()
        end = current_year if end_raw in ('present', 'current', 'now') else int(m.group(2))
        if 1950 <= start <= current_year and start <= end:
            total_months += (end - start) * 12
            spans_found += 1

    if spans_found >= 2:
        return total_months

    # Pattern 2: "X years experience" / "X+ years of experience"
    explicit_re = re.compile(r'(\d+)\+?\s*years?\s*(?:of\s+)?experience', re.IGNORECASE)
    m = explicit_re.search(resume_text)
    if m:
        return int(m.group(1)) * 12

    # Pattern 3: "ten years experience" (written number)
    word_re = re.compile(
        r'\b(' + '|'.join(re.escape(w) for w in _WORD_TO_NUM) + r')\b'
        r'\s*\+?\s*years?\s*(?:of\s+)?experience',
        re.IGNORECASE,
    )
    m = word_re.search(resume_text)
    if m:
        return _WORD_TO_NUM[m.group(1).lower()] * 12

    return None
```

- [ ] **Step 1.4: Run tests**

```bash
pytest tests/test_prompt_builder.py -k "sum_experience" -v
```

Expected: all 8 `test_sum_experience_months_*` tests **PASS**.

- [ ] **Step 1.5: Run full suite to confirm no regressions**

```bash
pytest tests/test_prompt_builder.py -v
```

Expected: all existing tests still **PASS**.

- [ ] **Step 1.6: Commit**

```bash
git add app/llm/prompt_builder.py tests/test_prompt_builder.py
git commit -m "[PHASE-08] add: _sum_experience_months with year span and explicit year parsing"
```

---

## Task 2: `_keyword_experience_level` and `detect_experience_level`

**Files:**
- Modify: `app/llm/prompt_builder.py`
- Modify: `tests/test_prompt_builder.py`

- [ ] **Step 2.1: Write failing tests**

Append to `tests/test_prompt_builder.py`:

```python
from app.llm.prompt_builder import _keyword_experience_level, detect_experience_level


def test_keyword_experience_level_senior():
    assert _keyword_experience_level("Jane Doe, Director of Operations") == "senior"


def test_keyword_experience_level_senior_vp():
    assert _keyword_experience_level("VP of Sales, EMEA region") == "senior"


def test_keyword_experience_level_senior_head_of():
    assert _keyword_experience_level("Head of Engineering at TechCorp") == "senior"


def test_keyword_experience_level_mid_manager():
    assert _keyword_experience_level("Operations Manager, 3 direct reports") == "mid"


def test_keyword_experience_level_mid_lead():
    assert _keyword_experience_level("Team Lead, Backend Engineering") == "mid"


def test_keyword_experience_level_early_junior():
    assert _keyword_experience_level("Junior Analyst at FinCo") == "early"


def test_keyword_experience_level_early_coordinator():
    assert _keyword_experience_level("Marketing Coordinator") == "early"


def test_keyword_experience_level_fresher_intern():
    assert _keyword_experience_level("Software Engineering Intern, Summer 2023") == "fresher"


def test_keyword_experience_level_fresher_graduate():
    assert _keyword_experience_level("Recent Graduate, BSc Computer Science") == "fresher"


def test_keyword_experience_level_junior_manager_resolves_to_mid():
    # "manager" (mid) found before "junior" (early) in priority order
    assert _keyword_experience_level("Junior Manager at RetailCo") == "mid"


def test_keyword_experience_level_no_keywords_defaults_early():
    assert _keyword_experience_level("I enjoy helping people and love learning new things.") == "early"


def test_detect_experience_level_uses_duration_math():
    # 2019-2023 (4y) + 2015-2019 (4y) = 8 years → senior
    resume = "Acme Corp 2019 - 2023\nBeta Ltd 2015 - 2019"
    assert detect_experience_level(resume) == "senior"


def test_detect_experience_level_fresher_bucket():
    # < 12 months
    resume = "Internship 2023 - 2024\nProject work 2023 - 2023"
    # 12 + 0 = 12 months → early (boundary)
    # Use a cleaner case: explicit phrase
    assert detect_experience_level("6 months experience in retail. Internship 2023 - 2023") == "fresher"


def test_detect_experience_level_early_bucket():
    # 1-4 years: 2 year spans totalling 2 years
    resume = "RoleA 2022 - 2023\nRoleB 2021 - 2022"
    assert detect_experience_level(resume) == "early"


def test_detect_experience_level_mid_bucket():
    # 4-8 years: two spans totalling 5 years
    resume = "RoleA 2020 - 2023\nRoleB 2018 - 2020"
    assert detect_experience_level(resume) == "mid"


def test_detect_experience_level_falls_back_to_keyword():
    # No parseable dates, has a seniority keyword
    assert detect_experience_level("Director of Marketing, award-winning campaigns") == "senior"


def test_detect_experience_level_no_signals_defaults_early():
    assert detect_experience_level("Passionate team player with great communication skills.") == "early"
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
pytest tests/test_prompt_builder.py -k "keyword_experience or detect_experience" -v
```

Expected: `ERROR` — `ImportError: cannot import name '_keyword_experience_level'`

- [ ] **Step 2.3: Add `_LEVEL_KEYWORDS`, `_keyword_experience_level`, and `detect_experience_level` to `prompt_builder.py`**

Add immediately after `_WORD_TO_NUM` and before `_sum_experience_months`:

```python
_LEVEL_KEYWORDS: dict[str, list[str]] = {
    "senior": [
        "director", "vp", "vice president", "head of", "chief",
        "partner", "principal", "managing director", "executive director",
    ],
    "mid": [
        "manager", "lead", "specialist", "programme manager", "project manager",
    ],
    "early": [
        "associate", "junior", "coordinator", "assistant", "analyst",
        "representative", "officer", "executive",
    ],
    "fresher": [
        "intern", "trainee", "graduate", "fresher", "entry level", "entry-level",
        "apprentice",
    ],
}
```

Add after `_sum_experience_months`:

```python
def _keyword_experience_level(resume_text: str) -> str:
    """
    Fallback level detection via seniority keywords.
    Checks tiers from most specific (senior) to least (fresher).
    Returns "early" if no keywords match.
    """
    text = resume_text.lower()
    for level in ("senior", "mid", "early", "fresher"):
        for kw in _LEVEL_KEYWORDS[level]:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                return level
    return "early"


def detect_experience_level(resume_text: str) -> str:
    """
    Detect candidate experience level from resume text.

    Returns one of: "fresher" | "early" | "mid" | "senior"

    Strategy:
      1. Try duration math via _sum_experience_months.
         If months found: bucket into level by total duration.
      2. Fallback: keyword scan via _keyword_experience_level.
    """
    months = _sum_experience_months(resume_text)
    if months is not None:
        if months < 12:
            return "fresher"
        if months < 48:
            return "early"
        if months < 96:
            return "mid"
        return "senior"
    return _keyword_experience_level(resume_text)
```

- [ ] **Step 2.4: Run new tests**

```bash
pytest tests/test_prompt_builder.py -k "keyword_experience or detect_experience" -v
```

Expected: all 17 new tests **PASS**.

- [ ] **Step 2.5: Run full suite**

```bash
pytest tests/test_prompt_builder.py -v
```

Expected: all tests **PASS**.

- [ ] **Step 2.6: Commit**

```bash
git add app/llm/prompt_builder.py tests/test_prompt_builder.py
git commit -m "[PHASE-08] add: _keyword_experience_level and detect_experience_level"
```

---

## Task 3: `detect_function_type`

**Files:**
- Modify: `app/llm/prompt_builder.py`
- Modify: `tests/test_prompt_builder.py`

- [ ] **Step 3.1: Write failing tests**

Append to `tests/test_prompt_builder.py`:

```python
from app.llm.prompt_builder import detect_function_type


def test_detect_function_type_technical():
    jd = "We are hiring a Senior Software Engineer to architect scalable cloud infrastructure."
    assert detect_function_type(jd) == "technical"


def test_detect_function_type_sales():
    jd = "Account Executive to drive sales pipeline and exceed quarterly quota. Revenue targets apply."
    assert detect_function_type(jd) == "sales"


def test_detect_function_type_operations():
    jd = "Operations Manager to streamline logistics processes and meet SLA commitments."
    assert detect_function_type(jd) == "operations"


def test_detect_function_type_academic():
    jd = "Experienced Lecturer to deliver curriculum and conduct research in the faculty."
    assert detect_function_type(jd) == "academic"


def test_detect_function_type_general_no_match():
    jd = "We are looking for a passionate individual who loves helping others."
    assert detect_function_type(jd) == "general"


def test_detect_function_type_tie_returns_general():
    # Equal keyword hits for two types → general
    jd = "sales engineer quota software developer pipeline"
    result = detect_function_type(jd)
    assert result == "general"


def test_detect_function_type_empty_string():
    assert detect_function_type("") == "general"


def test_detect_function_type_returns_string():
    result = detect_function_type("any job description text")
    assert isinstance(result, str)
    assert result in ("technical", "sales", "operations", "academic", "general")
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
pytest tests/test_prompt_builder.py -k "detect_function_type" -v
```

Expected: `ERROR` — `ImportError: cannot import name 'detect_function_type'`

- [ ] **Step 3.3: Add `_FUNCTION_KEYWORDS` and `detect_function_type` to `prompt_builder.py`**

Add after `detect_experience_level` (before the existing prompt builder functions):

```python
# ── Function type detection ────────────────────────────────────────────────

_FUNCTION_KEYWORDS: dict[str, list[str]] = {
    "technical": [
        "engineer", "developer", "architect", "devops", "software", "data",
        "backend", "frontend", "cloud", "infrastructure", "platform", "security",
        "machine learning", "ml", "ai", "database", "systems", "network",
        "full stack", "fullstack", "sre", "qa",
    ],
    "sales": [
        "sales", "account executive", "account manager", "business development",
        "quota", "pipeline", "revenue", "territory", "conversion", "client",
        "customer success", "commercial", "partnership", "deal", "closing",
        "prospecting", "bdr", "sdr",
    ],
    "operations": [
        "operations", "process", "logistics", "sla", "efficiency",
        "supply chain", "fulfilment", "fulfillment", "warehouse", "procurement",
        "vendor", "compliance", "continuous improvement", "lean",
        "six sigma", "facilities", "scheduling",
    ],
    "academic": [
        "teacher", "lecturer", "curriculum", "research", "academic",
        "faculty", "professor", "instructor", "education", "training",
        "learning", "teaching", "pedagogy", "assessment", "school",
        "university", "college", "classroom",
    ],
}


def detect_function_type(jd_text: str) -> str:
    """
    Detect the function type from a job description.

    Returns one of: "technical" | "sales" | "operations" | "academic" | "general"

    Strategy: count keyword hits per type; highest count wins.
    Tie or zero matches → "general".
    """
    text = jd_text.lower()
    scores: dict[str, int] = {ft: 0 for ft in _FUNCTION_KEYWORDS}
    for ft, keywords in _FUNCTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[ft] += 1
    max_score = max(scores.values())
    if max_score == 0:
        return "general"
    winners = [ft for ft, sc in scores.items() if sc == max_score]
    return winners[0] if len(winners) == 1 else "general"
```

- [ ] **Step 3.4: Run new tests**

```bash
pytest tests/test_prompt_builder.py -k "detect_function_type" -v
```

Expected: all 8 tests **PASS**.

- [ ] **Step 3.5: Run full suite**

```bash
pytest tests/test_prompt_builder.py -v
```

Expected: all tests **PASS**.

- [ ] **Step 3.6: Commit**

```bash
git add app/llm/prompt_builder.py tests/test_prompt_builder.py
git commit -m "[PHASE-08] add: detect_function_type with keyword count scoring"
```

---

## Task 4: Personalisation constants and `_build_personalization_block`

**Files:**
- Modify: `app/llm/prompt_builder.py`
- Modify: `tests/test_prompt_builder.py`

- [ ] **Step 4.1: Write failing tests**

Append to `tests/test_prompt_builder.py`:

```python
from app.llm.prompt_builder import _build_personalization_block


def test_build_personalization_block_contains_section_header():
    block = _build_personalization_block("mid", "sales")
    assert "=== PERSONALISATION ===" in block


def test_build_personalization_block_contains_experience_label():
    block = _build_personalization_block("senior", "technical")
    assert "SENIOR" in block


def test_build_personalization_block_contains_bullet_counts():
    block = _build_personalization_block("early", "operations")
    assert "bullets" in block.lower()


def test_build_personalization_block_contains_ten_verbs():
    block = _build_personalization_block("mid", "sales")
    # Verbs line: "  Verb1, Verb2, ..."
    verb_line = [ln for ln in block.splitlines() if ln.strip() and "," in ln]
    assert len(verb_line) >= 1
    verbs = [v.strip() for v in verb_line[0].split(",")]
    assert len(verbs) == 10


def test_build_personalization_block_all_levels_produce_output():
    for level in ("fresher", "early", "mid", "senior"):
        block = _build_personalization_block(level, "general")
        assert isinstance(block, str) and len(block) > 50


def test_build_personalization_block_all_function_types_produce_output():
    for ft in ("technical", "sales", "operations", "academic", "general"):
        block = _build_personalization_block("mid", ft)
        assert isinstance(block, str) and len(block) > 50


def test_build_personalization_block_verbs_vary_across_calls():
    # With 100 verbs sampled 10 at a time, two calls should almost never match.
    # Run 20 pairs; at least one pair must differ (p of all matching ≈ 10^-13).
    verb_sets = set()
    for _ in range(20):
        block = _build_personalization_block("mid", "sales")
        verb_line = [ln for ln in block.splitlines() if ln.strip() and "," in ln][0]
        verbs = tuple(sorted(v.strip() for v in verb_line.split(",")))
        verb_sets.add(verbs)
    assert len(verb_sets) > 1, "All 20 calls produced identical verb sets — randomisation broken"


def test_build_personalization_block_unknown_level_falls_back():
    # Unknown level should not raise; falls back to "early" config
    block = _build_personalization_block("unknown_level", "general")
    assert "=== PERSONALISATION ===" in block


def test_build_personalization_block_contains_bullet_format_instruction():
    block = _build_personalization_block("mid", "academic")
    assert "Action verb" in block
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
pytest tests/test_prompt_builder.py -k "build_personalization_block" -v
```

Expected: `ERROR` — `ImportError: cannot import name '_build_personalization_block'`

- [ ] **Step 4.3: Add `_LEVEL_CONFIG`, `_TONE_VARIANTS`, `_VERB_BANKS`, and `_build_personalization_block` to `prompt_builder.py`**

Add after `detect_function_type` (before the existing prompt builder functions). For `_TONE_VARIANTS` and `_VERB_BANKS`, use the complete lists from spec section 6a and section 7 respectively.

```python
# ── Personalisation constants ──────────────────────────────────────────────

_LEVEL_CONFIG: dict[str, dict[str, str]] = {
    "fresher": {
        "label": "FRESHER (0-1 years)",
        "focus": "Highlight education, academic projects, internships, and learning agility. Avoid overstating responsibility.",
        "bullets": "Most recent role: 4-5 bullets | Previous roles: 2-3 bullets | Older roles: 1-2 bullets",
    },
    "early": {
        "label": "EARLY CAREER (1-4 years)",
        "focus": "Emphasise execution, delivery, and tool proficiency. Show measurable outputs, not just participation.",
        "bullets": "Most recent role: 5-6 bullets | Previous roles: 3-4 bullets | Older roles: 2-3 bullets",
    },
    "mid": {
        "label": "MID-LEVEL (4-8 years)",
        "focus": "Lead with ownership, cross-functional impact, and quantified results. Show career progression.",
        "bullets": "Most recent role: 6-7 bullets | Previous roles: 4-5 bullets | Older roles: 2-3 bullets",
    },
    "senior": {
        "label": "SENIOR (8+ years)",
        "focus": "Centre on leadership, scale, strategy, and organisational impact. Avoid tactical micro-detail in bullets.",
        "bullets": "Most recent role: 6-8 bullets | Previous roles: 4-6 bullets | Older roles: 2-4 bullets",
    },
}

# 10 tone variants per function type — one randomly selected per call.
# Full strings are in spec section 6a. Abbreviated here for readability.
_TONE_VARIANTS: dict[str, list[str]] = {
    "technical": [
        "Use precise technical language. Name tools, architectures, and methodologies explicitly. Quantify throughput, latency, scale, and reliability.",
        "Lead with the engineering outcome first, then the method. Be specific about stack, scope, and scale. Avoid vague phrases like 'worked on' or 'helped with'.",
        "Name the technology, state the problem it solved, and quantify the impact. Favour concrete metrics: uptime, speed, volume, cost savings.",
        "Open with scale: how many users, how much data, what traffic volume. Then state what you built and how it performed.",
        "Lead with the architectural decision and its consequence. What tradeoff was made? What was the measurable outcome?",
        "Emphasise automation and efficiency gains: what was manual, what did you automate, what time or cost was saved?",
        "Highlight cross-system integration: what systems were connected, what data flowed, what capability was unlocked.",
        "Focus on reliability and quality: uptime percentage, incident reduction, test coverage improvement, defect rate lowered.",
        "Lead with the business problem, then the technical solution, then the measurable result. Show that engineering served a commercial goal.",
        "Show technical ownership: what design decisions did you own, what standards did you define, what did you enable in others?",
    ],
    "sales": [
        "Lead every bullet with a commercial outcome — revenue, pipeline, or conversion rate first.",
        "Open each bullet with the deal or customer impact, then the action that caused it. Use numbers wherever possible.",
        "Frame every achievement around targets: what was set, what was delivered, by how much. Avoid soft language — use hard commercial metrics.",
        "Lead with the customer: who they were, what you won, what it was worth to the business.",
        "Emphasise territory growth: new accounts opened, market share gained, revenue split between new and existing clients.",
        "Show pipeline discipline: how you built, managed, and converted your pipeline. Use stage conversion and velocity metrics.",
        "Focus on retention and expansion: renewal rates, upsell value, net revenue retention percentage.",
        "Highlight relationship depth: seniority of stakeholders engaged, deal complexity navigated, negotiation outcomes achieved.",
        "Lead with the competitive angle: who you displaced, what the contract value was, why you won over the alternative.",
        "Show market development: new segments entered, new products taken to market, new channels established and their first-year output.",
    ],
    "operations": [
        "Focus on process improvements and their measurable outcomes: time saved, cost reduced, error rate lowered, SLA met.",
        "Lead with the operational outcome. State the process changed, the scale it affected, and the metric that improved.",
        "Quantify efficiency gains. Name the process, the intervention, and the result in concrete operational terms.",
        "Lead with problem scope — how many people, transactions, or locations were affected — then what you did and what improved.",
        "Emphasise compliance and risk management: standards met, audits passed, incidents prevented, controls implemented.",
        "Show cost discipline: budget managed, savings achieved, waste eliminated, procurement terms improved.",
        "Focus on team and vendor performance: team size led, supplier relationships managed, KPIs set and tracked.",
        "Lead with service delivery outcomes: SLA performance percentage, customer satisfaction scores, resolution times improved.",
        "Highlight continuous improvement: what the baseline was, what you changed, what the new steady-state performance became.",
        "Show capacity and scale management: volumes handled, throughput achieved, growth accommodated without quality loss.",
    ],
    "academic": [
        "Lead with student or research outcomes. Avoid corporate jargon. Use language natural to the education sector.",
        "Highlight curriculum impact, cohort outcomes, and institutional contributions. Quantify where possible: class size, pass rates, publications.",
        "Frame achievements around learner progress, research contribution, or programme development. Be specific about subject, level, and outcome.",
        "Lead with the learning outcome: what students could demonstrate after your teaching that they could not before.",
        "Emphasise research impact: citations received, publications produced, grants secured, collaborations established.",
        "Show programme leadership: curriculum designed from scratch, modules developed, assessment frameworks created.",
        "Focus on inclusion and accessibility: diverse learner needs addressed, differentiated strategies implemented, outcomes improved for specific cohorts.",
        "Highlight mentorship and student success: students supervised to completion, career outcomes achieved, academic progression rates.",
        "Lead with institutional contribution: committee work, policy shaped, strategic initiatives led at departmental or faculty level.",
        "Show professional development leadership: CPD programmes delivered, teacher training designed, communities of practice established.",
    ],
    "general": [
        "Use balanced professional language. Mix delivery, collaboration, and outcomes. Avoid domain-specific jargon.",
        "Lead with the result, then the action. Keep language accessible and professional without leaning into any one functional area.",
        "Emphasise cross-functional contribution, clear delivery, and measurable impact. Write for a broad professional audience.",
        "Focus on stakeholder management: who you worked with, what you delivered together, and what the impact was on the organisation.",
        "Lead with project or initiative scope, then your specific contribution, then the outcome achieved.",
        "Show adaptability: different contexts you operated in, how you adjusted your approach, what you achieved in each.",
        "Highlight communication and influence: what you presented, what you reported, what decisions you shaped or informed.",
        "Focus on problem-solving: what the challenge was, how you approached it methodically, what was resolved.",
        "Lead with team contribution and enablement: how you supported others, what you made possible, what the collective outcome was.",
        "Show a continuous improvement mindset: what gap or problem you identified, what you proposed, what changed as a result.",
    ],
}

# 100 verbs per function type — 10 randomly sampled per call.
# Full lists from spec section 7.
_VERB_BANKS: dict[str, list[str]] = {
    "sales": [
        "Secured", "Grew", "Negotiated", "Closed", "Expanded", "Converted", "Prospected",
        "Retained", "Exceeded", "Pitched", "Cultivated", "Drove", "Upsold", "Sourced",
        "Achieved", "Accelerated", "Generated", "Developed", "Strengthened", "Targeted",
        "Acquired", "Delivered", "Maximised", "Penetrated", "Identified", "Presented",
        "Renewed", "Captured", "Built", "Surpassed", "Activated", "Amplified", "Brokered",
        "Championed", "Convinced", "Deepened", "Differentiated", "Dominated", "Engaged",
        "Established", "Executed", "Forged", "Gained", "Influenced", "Initiated", "Launched",
        "Leveraged", "Managed", "Navigated", "Obtained", "Onboarded", "Opened", "Outperformed",
        "Owned", "Partnered", "Pioneered", "Positioned", "Prioritised", "Progressed",
        "Promoted", "Proposed", "Qualified", "Reached", "Recovered", "Recruited",
        "Represented", "Revitalised", "Scaled", "Shaped", "Showcased", "Signed",
        "Spearheaded", "Stimulated", "Strategised", "Structured", "Sustained", "Uncovered",
        "Won", "Yielded", "Demonstrated", "Mapped", "Responded", "Tripled", "Doubled",
        "Advanced", "Boosted", "Communicated", "Compelled", "Handled", "Orchestrated",
        "Crafted", "Directed", "Fulfilled", "Recognised", "Steered", "Utilised",
        "Validated", "Energised", "Maintained", "Collaborated",
    ],
    "technical": [
        "Architected", "Engineered", "Optimised", "Deployed", "Automated", "Scaled",
        "Debugged", "Integrated", "Migrated", "Designed", "Developed", "Refactored",
        "Implemented", "Benchmarked", "Secured", "Containerised", "Orchestrated", "Profiled",
        "Modernised", "Provisioned", "Analysed", "Tested", "Released", "Monitored",
        "Resolved", "Documented", "Built", "Streamlined", "Standardised", "Configured",
        "Launched", "Maintained", "Upgraded", "Extended", "Hardened", "Validated",
        "Modelled", "Scripted", "Compiled", "Packaged", "Parallelised", "Distributed",
        "Encrypted", "Patched", "Audited", "Indexed", "Cached", "Traced", "Abstracted",
        "Instrumented", "Mapped", "Ported", "Prototyped", "Simulated", "Authored",
        "Established", "Reviewed", "Structured", "Delivered", "Reduced", "Improved",
        "Eliminated", "Created", "Enabled", "Exposed", "Isolated", "Leveraged",
        "Operated", "Overhauled", "Rearchitected", "Redesigned", "Replaced",
        "Replatformed", "Researched", "Restructured", "Stabilised", "Tuned", "Unified",
        "Updated", "Verified", "Wrote", "Accelerated", "Consolidated", "Defined",
        "Drove", "Fixed", "Identified", "Introduced", "Led", "Piloted", "Published",
        "Ran", "Shipped", "Supported", "Transformed", "Triaged", "Troubleshot",
        "Versioned", "Visualised",
    ],
    "operations": [
        "Streamlined", "Reduced", "Coordinated", "Implemented", "Improved",
        "Standardised", "Managed", "Tracked", "Established", "Consolidated",
        "Optimised", "Oversaw", "Maintained", "Facilitated", "Reported", "Resolved",
        "Identified", "Reviewed", "Delivered", "Introduced", "Automated", "Planned",
        "Aligned", "Monitored", "Controlled", "Collaborated", "Eliminated",
        "Restructured", "Trained", "Communicated", "Administered", "Allocated",
        "Assessed", "Audited", "Benchmarked", "Built", "Centralised", "Clarified",
        "Commissioned", "Deployed", "Designed", "Developed", "Directed", "Documented",
        "Drove", "Enforced", "Evaluated", "Executed", "Expanded", "Forecasted",
        "Formalised", "Governed", "Guided", "Handled", "Harmonised", "Launched",
        "Led", "Measured", "Negotiated", "Operated", "Organised", "Owned",
        "Partnered", "Piloted", "Prioritised", "Processed", "Procured", "Produced",
        "Quantified", "Rationalised", "Realigned", "Redesigned", "Remediated",
        "Renewed", "Resourced", "Scaled", "Scheduled", "Secured", "Simplified",
        "Sourced", "Specified", "Strengthened", "Structured", "Supervised",
        "Supported", "Transformed", "Upgraded", "Validated", "Verified",
        "Visualised", "Won", "Optimised", "Oversaw", "Maintained",
    ],
    "academic": [
        "Designed", "Delivered", "Mentored", "Developed", "Assessed", "Facilitated",
        "Published", "Evaluated", "Guided", "Taught", "Coordinated", "Researched",
        "Supervised", "Supported", "Implemented", "Led", "Created", "Revised",
        "Collaborated", "Advised", "Presented", "Reviewed", "Established",
        "Contributed", "Initiated", "Coached", "Wrote", "Examined", "Prepared",
        "Modelled", "Administered", "Analysed", "Authored", "Benchmarked", "Built",
        "Championed", "Chaired", "Communicated", "Compiled", "Conceptualised",
        "Cultivated", "Curated", "Defined", "Demonstrated", "Differentiated",
        "Directed", "Documented", "Drafted", "Drove", "Edited", "Enabled",
        "Engaged", "Enhanced", "Expanded", "Explored", "Extended", "Formed",
        "Fostered", "Generated", "Identified", "Improved", "Increased", "Influenced",
        "Integrated", "Introduced", "Launched", "Managed", "Navigated", "Observed",
        "Organised", "Partnered", "Piloted", "Produced", "Promoted", "Proposed",
        "Raised", "Recommended", "Redesigned", "Reformed", "Represented", "Reported",
        "Secured", "Shaped", "Shared", "Simplified", "Spearheaded", "Strengthened",
        "Structured", "Trained", "Transformed", "Updated", "Validated",
        "Enriched", "Motivated", "Encouraged", "Empowered", "Celebrated",
        "Recognised", "Awarded", "Honoured", "Distinguished", "Certified",
    ],
    "general": [
        "Led", "Delivered", "Collaborated", "Supported", "Contributed", "Coordinated",
        "Achieved", "Produced", "Managed", "Drove", "Facilitated", "Improved",
        "Developed", "Organised", "Communicated", "Executed", "Represented",
        "Partnered", "Maintained", "Established", "Strengthened", "Ensured",
        "Progressed", "Guided", "Assisted", "Resolved", "Planned", "Built",
        "Engaged", "Participated", "Adapted", "Addressed", "Advanced", "Analysed",
        "Applied", "Assessed", "Balanced", "Championed", "Chaired", "Clarified",
        "Completed", "Composed", "Conceptualised", "Consolidated", "Crafted",
        "Created", "Defined", "Demonstrated", "Designed", "Directed", "Documented",
        "Evaluated", "Fostered", "Generated", "Handled", "Identified", "Implemented",
        "Influenced", "Initiated", "Integrated", "Introduced", "Launched",
        "Leveraged", "Mediated", "Monitored", "Negotiated", "Navigated", "Obtained",
        "Operated", "Optimised", "Oversaw", "Owned", "Prioritised", "Proposed",
        "Provided", "Raised", "Recommended", "Reformed", "Reported", "Researched",
        "Reviewed", "Scaled", "Secured", "Shaped", "Simplified", "Spearheaded",
        "Standardised", "Streamlined", "Structured", "Submitted", "Tracked",
        "Transformed", "Updated", "Utilised", "Validated", "Won",
    ],
}


def _build_personalization_block(experience_level: str, function_type: str) -> str:
    """
    Build the === PERSONALISATION === section for injection into the finetuning prompt.
    Randomly samples 10 verbs from the 100-verb bank and selects 1 of 10 tone variants.
    Unknown experience_level falls back to "early" config.
    Unknown function_type falls back to "general".
    """
    level_cfg = _LEVEL_CONFIG.get(experience_level, _LEVEL_CONFIG["early"])
    ft = function_type if function_type in _VERB_BANKS else "general"
    verbs = random.sample(_VERB_BANKS[ft], 10)
    tone = random.choice(_TONE_VARIANTS[ft])
    return (
        f"=== PERSONALISATION ===\n"
        f"Experience level: {level_cfg['label']}\n"
        f"Focus: {level_cfg['focus']}\n"
        f"Tone: {tone}\n"
        f"Bullet counts: {level_cfg['bullets']}\n"
        f"Preferred action verbs for this resume (vary your selection — do not use any verb more than twice):\n"
        f"  {', '.join(verbs)}\n"
        f"Format every bullet as: [Action verb] + [Context / Method] + [Measurable outcome]"
    )
```

- [ ] **Step 4.4: Run new tests**

```bash
pytest tests/test_prompt_builder.py -k "build_personalization_block" -v
```

Expected: all 9 tests **PASS**.

- [ ] **Step 4.5: Run full suite**

```bash
pytest tests/test_prompt_builder.py -v
```

Expected: all tests **PASS**.

- [ ] **Step 4.6: Commit**

```bash
git add app/llm/prompt_builder.py tests/test_prompt_builder.py
git commit -m "[PHASE-08] add: _build_personalization_block with verb bank and tone variant sampling"
```

---

## Task 5: Extend `build_finetuning_prompt` and fix existing test

**Files:**
- Modify: `app/llm/prompt_builder.py` (extend existing function)
- Modify: `tests/test_prompt_builder.py` (fix existing test + add new tests)

- [ ] **Step 5.1: Write new tests and fix the broken existing test**

First, **replace** the existing `test_build_finetuning_prompt_no_hint_unchanged` in `tests/test_prompt_builder.py` (lines 47-51) with:

```python
def test_build_finetuning_prompt_no_hint_unchanged():
    # Intent: empty revision_hint behaves identically to omitting it (no REVISION REQUEST section)
    prompt_default = build_finetuning_prompt("resume", "jd", "bp", "Alice")
    prompt_empty = build_finetuning_prompt("resume", "jd", "bp", "Alice", revision_hint="")
    assert "REVISION REQUEST" not in prompt_default
    assert "REVISION REQUEST" not in prompt_empty
    # Note: strict equality no longer asserted — randomised verb/tone sampling means
    # two calls produce different PERSONALISATION blocks (by design).
```

Then **append** these new tests:

```python
def test_build_finetuning_prompt_contains_personalisation_block():
    prompt = build_finetuning_prompt(
        "Software engineer with 2019 - 2021 and 2021 - 2023 at two companies.",
        "We need a senior software engineer to architect cloud infrastructure.",
        "best practice text",
        "Alex Chen",
    )
    assert "=== PERSONALISATION ===" in prompt


def test_build_finetuning_prompt_explicit_experience_level_respected():
    prompt = build_finetuning_prompt(
        "resume text with no dates",
        "sales manager quota pipeline",
        "best practice",
        "Sam Lee",
        experience_level="senior",
    )
    assert "SENIOR" in prompt


def test_build_finetuning_prompt_explicit_function_type_respected():
    prompt = build_finetuning_prompt(
        "resume text",
        "jd text",
        "best practice",
        "Jordan",
        function_type="academic",
    )
    # Academic tone variant keywords appear in the block
    assert "curriculum" in prompt.lower() or "student" in prompt.lower() or "research" in prompt.lower()


def test_build_finetuning_prompt_personalisation_before_critical_constraint():
    prompt = build_finetuning_prompt("resume", "jd", "bp", "Casey")
    personalisation_pos = prompt.index("=== PERSONALISATION ===")
    critical_pos = prompt.index("=== CRITICAL CONSTRAINT ===")
    assert personalisation_pos < critical_pos


def test_build_finetuning_prompt_revision_hint_still_appended():
    prompt = build_finetuning_prompt(
        "resume", "jd", "bp", "Alex",
        revision_hint="Emphasise leadership more.",
        experience_level="mid",
        function_type="general",
    )
    assert "REVISION REQUEST" in prompt
    assert "Emphasise leadership more." in prompt


def test_build_finetuning_prompt_backward_compatible_no_new_params():
    # Existing callers pass only the original 4 positional args — must not raise
    prompt = build_finetuning_prompt("resume text", "jd text", "bp text", "Name")
    assert isinstance(prompt, str)
    assert len(prompt) > 100
```

- [ ] **Step 5.2: Run new tests to verify they fail**

```bash
pytest tests/test_prompt_builder.py -k "personalisation_block or experience_level_respected or function_type_respected or personalisation_before or hint_still or backward_compatible" -v
```

Expected: most tests **FAIL** — `=== PERSONALISATION ===` not yet in the prompt.

- [ ] **Step 5.3: Replace `build_finetuning_prompt` in `prompt_builder.py`**

Find the existing `build_finetuning_prompt` function (starts at line 64 in original file, now shifted down due to additions) and **replace it entirely** with:

```python
def build_finetuning_prompt(
    resume_text: str,
    jd_text: str,
    best_practice_text: str,
    candidate_name: str,
    revision_hint: str = "",
    experience_level: str = "",
    function_type: str = "",
) -> str:
    """
    Builds the structured prompt for the REWRITE provider to fine-tune a resume against a JD.

    New in Phase 8:
      experience_level: "fresher" | "early" | "mid" | "senior" — auto-detected if ""
      function_type: "technical" | "sales" | "operations" | "academic" | "general" — auto-detected if ""

    Auto-detection uses resume_text and jd_text respectively.
    Explicit values override auto-detection (useful for tests and future UI overrides).
    """
    if not experience_level:
        experience_level = detect_experience_level(resume_text)
    if not function_type:
        function_type = detect_function_type(jd_text)

    personalisation = _build_personalization_block(experience_level, function_type)

    prompt = f"""
You are an expert technical recruiter and resume writer. Your task is to fine-tune the candidate's resume to better align with the provided Job Description (JD).
You must strictly follow the provided best practice format.

CANDIDATE NAME: {candidate_name}

=== BEST PRACTICE FORMATTING TO FOLLOW ===
{best_practice_text}

=== JOB DESCRIPTION ===
{jd_text}

=== CANDIDATE ORIGINAL RESUME ===
{resume_text}

=== OBJECTIVE ===
Rewrite the candidate's resume to align tightly with the JD.

Rules for every bullet point:
1. Use the EXACT phrasing from the JD wherever possible - if the JD says
   "admissions management", write "admissions management", not "student
   intake coordination".
2. Within each role, put the bullet most directly relevant to the JD first.
3. Do not fabricate facts. Rephrase and reorder only - never invent experience,
   dates, companies, or qualifications not present in the source resume.

{personalisation}

=== CRITICAL CONSTRAINT ===
Do not invent, fabricate, or add any experience, qualifications, dates, or companies that are not present in the source resume text. You may rephrase, reorder, and reformat - but you must not add facts.

If a piece of information (such as phone number, email, linkedin, etc) is not in the source resume, you must leave it blank in the relevant field and list it in the `missing_fields` output array.

=== OUTPUT SCHEMA ===
You must respond with ONLY valid JSON matching this schema exactly. No markdown blocks, no conversational text.
{{
  "candidate_name": "{candidate_name}",
  "contact": {{ "email": "string", "phone": "string", "linkedin": "string" }},
  "summary": "string - 3-4 lines, JD-aligned",
  "experience": [ {{ "title": "string", "company": "string", "dates": "string", "bullets": ["string"] }} ],
  "education": [ {{ "degree": "string", "institution": "string", "year": "string" }} ],
  "skills": ["string"],
  "missing_fields": ["string - any field that was blank or unclear in source resume"]
}}
"""
    if revision_hint.strip():
        prompt += f"\n\n=== REVISION REQUEST ===\n{revision_hint.strip()}\nApply this specific feedback when rewriting the resume."

    return prompt.strip()
```

- [ ] **Step 5.4: Run all `test_prompt_builder.py` tests**

```bash
pytest tests/test_prompt_builder.py -v
```

Expected: all tests **PASS** including both new and pre-existing tests.

- [ ] **Step 5.5: Run the full test suite**

```bash
pytest -v
```

Expected: all 281+ tests **PASS**. Fix any failures before proceeding.

- [ ] **Step 5.6: Commit**

```bash
git add app/llm/prompt_builder.py tests/test_prompt_builder.py
git commit -m "[PHASE-08] add: personalisation block injection in build_finetuning_prompt"
```

---

## Task 6: Update task file and final verification

**Files:**
- Modify: `tasks/PHASE-08-personalization-logic.md`

- [ ] **Step 6.1: Run full suite one final time**

```bash
pytest -v --tb=short 2>&1 | tail -20
```

Expected: all tests pass. Note the count.

- [ ] **Step 6.2: Update task file**

Replace the content of `tasks/PHASE-08-personalization-logic.md` with:

```markdown
# PHASE-08: Personalization Logic

## Status: COMPLETE
## Phase: 8 / 12

## Objective
Each resume rewrite is tailored to the candidate's experience level (auto-detected from resume)
and the JD's function type (auto-detected from JD text). A randomised verb bank (10 of 100)
and tone variant (1 of 10) ensure no two resumes share identical language.

## v1 Foundation
- `app/llm/prompt_builder.py` — extended (not rewritten)

## Net New
- `detect_experience_level(resume_text)` — public, duration math + keyword fallback
- `detect_function_type(jd_text)` — public, keyword count scoring
- `_sum_experience_months` — private, regex year-span + explicit years parsing
- `_keyword_experience_level` — private, seniority keyword tier matching
- `_build_personalization_block` — private, assembles prompt section with random sampling
- `_LEVEL_CONFIG`, `_TONE_VARIANTS`, `_VERB_BANKS`, `_LEVEL_KEYWORDS`, `_FUNCTION_KEYWORDS` — constants

## PDCA Log

### Cycle 1
**Plan:** docs/superpowers/specs/2026-04-17-phase08-personalization-design.md
**Approved by human:** Yes
**Do:** Extended prompt_builder.py only; zero changes to finetuner/provider/pages
**Check:** All tests passing
**Act:** Complete

## Decisions Made
- Auto-detect inside build_finetuning_prompt; optional override params for testability
- Duration math first (>=2 year spans), explicit/written phrase as secondary, keyword as final fallback
- Keyword tie in function_type detection → "general"
- Keyword priority order: senior → mid → early → fresher (most specific first)
- 100 verbs per bank, 10 sampled per call; 10 tone variants per type, 1 selected per call

## Checkpoints
- [x] _sum_experience_months — all patterns tested
- [x] _keyword_experience_level — priority order verified
- [x] detect_experience_level — duration + keyword fallback
- [x] detect_function_type — all types + tie resolution
- [x] _build_personalization_block — verb count, randomisation, all level/type combos
- [x] build_finetuning_prompt — block injected, override params respected, backward compat
- [x] Full test suite green
```

- [ ] **Step 6.3: Commit task file**

```bash
git add tasks/PHASE-08-personalization-logic.md
git commit -m "[PHASE-08] docs: mark phase 8 complete, log decisions and checkpoints"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by task |
|-----------------|-----------------|
| `detect_experience_level` public export | Task 2 |
| Duration math (year spans) | Task 1 |
| Keyword fallback | Task 2 |
| Present/current year handling | Task 1 |
| Written numbers ("ten years") | Task 1 |
| Senior → mid → early → fresher priority | Task 2 |
| `detect_function_type` public export | Task 3 |
| Keyword count scoring | Task 3 |
| Tie → general | Task 3 |
| `build_finetuning_prompt` optional params | Task 5 |
| PERSONALISATION block in prompt | Task 5 |
| Block between OBJECTIVE and CRITICAL CONSTRAINT | Task 5 |
| 10 verbs sampled from 100 | Task 4 |
| Tone variant randomly selected from 10 | Task 4 |
| Cross-call verb variation confirmed | Task 4 |
| Existing callers unchanged | Task 5 (backward compat test) |
| `test_build_finetuning_prompt_no_hint_unchanged` fixed | Task 5 |
| No files outside prompt_builder.py modified | All tasks |

All spec requirements covered. No gaps found.

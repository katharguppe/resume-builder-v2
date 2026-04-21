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
        "internship", "intern", "trainee", "graduate", "fresher", "entry level", "entry-level",
        "apprentice",
    ],
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
        if 1950 <= start <= current_year and start <= end <= current_year + 1:
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
    # Verbs line is placed before Focus/Tone so comma-based test detection picks it up first.
    return (
        f"=== PERSONALISATION ===\n"
        f"Experience level: {level_cfg['label']}\n"
        f"Preferred action verbs for this resume (vary your selection — do not use any verb more than twice):\n"
        f"  {', '.join(verbs)}\n"
        f"Focus: {level_cfg['focus']}\n"
        f"Tone: {tone}\n"
        f"Bullet counts: {level_cfg['bullets']}\n"
        f"Format every bullet as: [Action verb] + [Context / Method] + [Measurable outcome]"
    )


def build_extraction_prompt(resume_text: str) -> str:
    """
    Minimal prompt for Haiku to extract name, email, phone from a resume.
    """
    return f"""Extract the candidate's name, email address, and phone number from the resume below.

Respond ONLY with valid JSON - no markdown, no explanation:
{{"candidate_name": "string", "email": "string", "phone": "string"}}

Use empty string "" for any field not found in the resume.

=== RESUME ===
{resume_text}""".strip()


def build_jd_extraction_prompt(jd_text: str) -> str:
    """
    Prompt for the EXTRACT provider to pull structured fields from a Job Description.
    Used by jd_extractor.py for Phase 2 upload and Phase 3 ATS scoring.
    """
    return f"""Extract structured fields from the Job Description below.

Respond ONLY with valid JSON matching this schema exactly - no markdown, no explanation:
{{
  "job_title": "string",
  "company": "string",
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "experience_required": "string",
  "education_required": "string",
  "key_responsibilities": ["string"]
}}

Use empty string "" for scalar fields not found. Use [] for list fields not found.

=== JOB DESCRIPTION ===
{jd_text}""".strip()


def build_resume_fields_prompt(resume_text: str) -> str:
    """
    Prompt for the EXTRACT provider to pull structured fields from a resume.
    Returns richer schema than v1 extract_fields() - used for ATS scoring (Phase 3).
    The v1 extract_fields() (name/email/phone only) is preserved separately for backward compat.
    """
    return f"""Extract structured fields from the resume below.

Respond ONLY with valid JSON matching this schema exactly - no markdown, no explanation:
{{
  "candidate_name": "string",
  "email": "string",
  "phone": "string",
  "current_title": "string",
  "skills": ["string"],
  "experience_summary": "string"
}}

Use empty string "" for scalar fields not found. Use [] for skills if none found.

=== RESUME ===
{resume_text}""".strip()


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

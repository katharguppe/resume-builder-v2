from app.llm.prompt_builder import (
    build_jd_extraction_prompt,
    build_resume_fields_prompt,
    build_finetuning_prompt,
)


def test_build_jd_extraction_prompt_contains_jd_text():
    prompt = build_jd_extraction_prompt("We need a Python engineer with 5 years experience.")
    assert "Python engineer" in prompt
    assert "job_title" in prompt
    assert "required_skills" in prompt
    assert "preferred_skills" in prompt
    assert "key_responsibilities" in prompt


def test_build_jd_extraction_prompt_returns_string():
    result = build_jd_extraction_prompt("any jd text")
    assert isinstance(result, str)
    assert len(result) > 50


def test_build_resume_fields_prompt_contains_resume_text():
    prompt = build_resume_fields_prompt("Alice Smith, Software Engineer, Python, Java")
    assert "Alice Smith" in prompt
    assert "candidate_name" in prompt
    assert "skills" in prompt
    assert "current_title" in prompt
    assert "experience_summary" in prompt


def test_build_resume_fields_prompt_returns_string():
    result = build_resume_fields_prompt("any resume text")
    assert isinstance(result, str)
    assert len(result) > 50


def test_build_finetuning_prompt_includes_revision_hint():
    prompt = build_finetuning_prompt(
        "resume text", "jd text", "best practice", "Alice",
        revision_hint="Make the summary shorter and more direct.",
    )
    assert "REVISION REQUEST" in prompt
    assert "Make the summary shorter and more direct." in prompt


def test_build_finetuning_prompt_no_hint_unchanged():
    # Intent: empty revision_hint behaves identically to omitting it (no REVISION REQUEST section)
    prompt_default = build_finetuning_prompt("resume", "jd", "bp", "Alice")
    prompt_empty = build_finetuning_prompt("resume", "jd", "bp", "Alice", revision_hint="")
    assert "REVISION REQUEST" not in prompt_default
    assert "REVISION REQUEST" not in prompt_empty
    # Note: strict equality no longer asserted — randomised verb/tone sampling means
    # two calls produce different PERSONALISATION blocks (by design).


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


def test_detect_function_type_maintain_not_technical():
    # "maintain" previously matched "ai" as a substring — fixed by using "artificial intelligence"
    jd = "Administrative Coordinator to maintain records, coordinate schedules, and support the team."
    assert detect_function_type(jd) == "general"


def test_verb_banks_have_no_duplicates():
    from app.llm.prompt_builder import _VERB_BANKS
    for ft, verbs in _VERB_BANKS.items():
        duplicates = [v for v in verbs if verbs.count(v) > 1]
        assert len(duplicates) == 0, f"Duplicate verbs in '{ft}' bank: {list(set(duplicates))}"


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

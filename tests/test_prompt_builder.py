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
    prompt_default = build_finetuning_prompt("resume", "jd", "bp", "Alice")
    prompt_empty = build_finetuning_prompt("resume", "jd", "bp", "Alice", revision_hint="")
    assert "REVISION REQUEST" not in prompt_default
    assert prompt_default == prompt_empty


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

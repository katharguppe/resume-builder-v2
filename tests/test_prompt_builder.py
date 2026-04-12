from app.llm.prompt_builder import (
    build_jd_extraction_prompt,
    build_resume_fields_prompt,
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

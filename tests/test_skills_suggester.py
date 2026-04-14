"""Tests for app/skills/suggester.py."""
import pytest
from unittest.mock import patch


# ── Stage 1: set-difference tests ──────────────────────────────────────────

def test_stage1_returns_jd_skills_not_in_resume():
    from app.skills.suggester import _stage1_diff
    jd_fields = {"required_skills": ["SQL", "Python", "AWS"], "preferred_skills": []}
    resume_fields = {"skills": ["Python"]}
    result = _stage1_diff(jd_fields, resume_fields)
    assert "SQL" in result
    assert "AWS" in result
    assert "Python" not in result


def test_stage1_case_insensitive():
    from app.skills.suggester import _stage1_diff
    jd_fields = {"required_skills": ["python"], "preferred_skills": []}
    resume_fields = {"skills": ["Python"]}
    result = _stage1_diff(jd_fields, resume_fields)
    assert result == []


def test_stage1_includes_preferred_skills():
    from app.skills.suggester import _stage1_diff
    jd_fields = {"required_skills": [], "preferred_skills": ["Tableau"]}
    resume_fields = {"skills": []}
    result = _stage1_diff(jd_fields, resume_fields)
    assert "Tableau" in result


def test_stage1_empty_jd_fields():
    from app.skills.suggester import _stage1_diff
    result = _stage1_diff({}, {"skills": ["Python"]})
    assert result == []


def test_stage1_empty_resume_skills():
    from app.skills.suggester import _stage1_diff
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    result = _stage1_diff(jd_fields, {})
    assert "SQL" in result


def test_stage1_returns_list_of_strings():
    from app.skills.suggester import _stage1_diff
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    result = _stage1_diff(jd_fields, {})
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)


# ── Stage 2 + full suggest_skills tests ────────────────────────────────────

def test_suggest_skills_caps_at_10():
    from app.skills.suggester import suggest_skills
    jd_fields = {
        "required_skills": [f"Skill{i}" for i in range(20)],
        "preferred_skills": [],
    }
    resume_fields = {"skills": []}
    with patch("app.skills.suggester._stage2_llm", return_value=[]):
        result = suggest_skills(jd_fields, resume_fields)
    assert len(result) <= 10


def test_suggest_skills_deduplicates_with_resume():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["Python", "SQL"], "preferred_skills": []}
    resume_fields = {"skills": ["Python"]}
    with patch("app.skills.suggester._stage2_llm", return_value=["Python"]):
        result = suggest_skills(jd_fields, resume_fields)
    assert "Python" not in result


def test_suggest_skills_llm_failure_returns_stage1():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["SQL", "AWS"], "preferred_skills": []}
    resume_fields = {"skills": []}
    with patch("app.skills.suggester._stage2_llm", side_effect=Exception("LLM down")):
        result = suggest_skills(jd_fields, resume_fields)
    assert "SQL" in result
    assert "AWS" in result


def test_suggest_skills_returns_list_of_strings():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    resume_fields = {"skills": []}
    with patch("app.skills.suggester._stage2_llm", return_value=[]):
        result = suggest_skills(jd_fields, resume_fields)
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)


def test_suggest_skills_merges_stage1_and_stage2():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    resume_fields = {"skills": []}
    with patch("app.skills.suggester._stage2_llm", return_value=["Tableau"]):
        result = suggest_skills(jd_fields, resume_fields)
    assert "SQL" in result
    assert "Tableau" in result


def test_suggest_skills_no_duplicates_between_stages():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    resume_fields = {"skills": []}
    with patch("app.skills.suggester._stage2_llm", return_value=["SQL"]):
        result = suggest_skills(jd_fields, resume_fields)
    assert result.count("SQL") == 1


def test_suggest_skills_empty_inputs():
    from app.skills.suggester import suggest_skills
    with patch("app.skills.suggester._stage2_llm", return_value=[]):
        result = suggest_skills({}, {})
    assert result == []


def test_suggest_skills_llm_non_list_response_falls_back_to_stage1():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    resume_fields = {"skills": []}
    # LLM returns a dict instead of a list — should degrade gracefully to Stage 1
    with patch("app.skills.suggester._stage2_llm", side_effect=ValueError("Expected JSON array from LLM, got dict")):
        result = suggest_skills(jd_fields, resume_fields)
    assert "SQL" in result

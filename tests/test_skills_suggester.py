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

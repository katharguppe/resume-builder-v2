"""Tests for app/skills/grouper.py — SkillGroups dataclass and YAML loader."""
import pytest
from pathlib import Path


def test_skillgroups_dataclass_has_four_buckets():
    from app.skills.grouper import SkillGroups
    sg = SkillGroups()
    assert hasattr(sg, "core")
    assert hasattr(sg, "tools")
    assert hasattr(sg, "functional")
    assert hasattr(sg, "domain")


def test_skillgroups_all_buckets_are_lists():
    from app.skills.grouper import SkillGroups
    sg = SkillGroups()
    assert isinstance(sg.core, list)
    assert isinstance(sg.tools, list)
    assert isinstance(sg.functional, list)
    assert isinstance(sg.domain, list)


def test_skillgroups_default_buckets_are_empty():
    from app.skills.grouper import SkillGroups
    sg = SkillGroups()
    assert sg.core == []
    assert sg.tools == []
    assert sg.functional == []
    assert sg.domain == []


def test_keyword_sets_loaded_on_import():
    from app.skills.grouper import _KEYWORD_SETS
    # At least one keyword in each group from the YAML files
    assert len(_KEYWORD_SETS["core"]) > 0
    assert len(_KEYWORD_SETS["tools"]) > 0
    assert len(_KEYWORD_SETS["functional"]) > 0
    assert len(_KEYWORD_SETS["domain"]) > 0


def test_keyword_sets_contain_cross_industry_terms():
    from app.skills.grouper import _KEYWORD_SETS
    # Functional: always present regardless of domain
    assert "leadership" in _KEYWORD_SETS["functional"]
    assert "communication" in _KEYWORD_SETS["functional"]


def test_keyword_sets_contain_non_tech_terms():
    from app.skills.grouper import _KEYWORD_SETS
    # Sales
    assert "prospecting" in _KEYWORD_SETS["core"]
    # Finance
    assert "financial modeling" in _KEYWORD_SETS["core"]
    # HR
    assert "recruitment" in _KEYWORD_SETS["core"]


# ── group_skills tests ──────────────────────────────────────────────────────

def test_group_skills_empty_input():
    from app.skills.grouper import group_skills
    result = group_skills([])
    assert result.core == []
    assert result.tools == []
    assert result.functional == []
    assert result.domain == []


def test_tech_skill_classified_as_core():
    from app.skills.grouper import group_skills
    result = group_skills(["Python"])
    assert "Python" in result.core


def test_sales_tool_classified_as_tools():
    from app.skills.grouper import group_skills
    result = group_skills(["Salesforce"])
    assert "Salesforce" in result.tools


def test_functional_skill_classified_correctly():
    from app.skills.grouper import group_skills
    result = group_skills(["Leadership"])
    assert "Leadership" in result.functional


def test_domain_keyword_classified_correctly():
    from app.skills.grouper import group_skills
    result = group_skills(["FMCG"])
    assert "FMCG" in result.domain


def test_unknown_skill_falls_to_core():
    from app.skills.grouper import group_skills
    result = group_skills(["Extreme Ironing Championship"])
    assert "Extreme Ironing Championship" in result.core
    assert "Extreme Ironing Championship" not in result.tools
    assert "Extreme Ironing Championship" not in result.functional
    assert "Extreme Ironing Championship" not in result.domain


def test_case_insensitive_matching_preserves_original_casing():
    from app.skills.grouper import group_skills
    result = group_skills(["PYTHON", "SALESFORCE"])
    assert "PYTHON" in result.core   # original casing preserved
    assert "SALESFORCE" in result.tools


def test_mixed_industry_skills_split_correctly():
    from app.skills.grouper import group_skills
    skills = ["Python", "Salesforce", "Leadership", "Banking"]
    result = group_skills(skills)
    assert "Python" in result.core
    assert "Salesforce" in result.tools
    assert "Leadership" in result.functional
    assert "Banking" in result.domain


def test_skill_assigned_to_exactly_one_bucket():
    from app.skills.grouper import group_skills
    result = group_skills(["Python", "Salesforce", "Leadership", "Banking"])
    all_skills = result.core + result.tools + result.functional + result.domain
    assert len(all_skills) == 4  # no skill duplicated across buckets


def test_non_tech_core_skill_classified_correctly():
    from app.skills.grouper import group_skills
    # Finance skill from finance.yaml
    result = group_skills(["Financial Modeling"])
    assert "Financial Modeling" in result.core


def test_education_core_skill_classified_correctly():
    from app.skills.grouper import group_skills
    result = group_skills(["Curriculum Development"])
    assert "Curriculum Development" in result.core


def test_culinary_core_skill_classified_correctly():
    from app.skills.grouper import group_skills
    result = group_skills(["Menu Development"])
    assert "Menu Development" in result.core


def test_partial_word_does_not_false_match():
    from app.skills.grouper import group_skills
    # "go" should not match inside "Django" or "MongoDB"
    result = group_skills(["Django", "MongoDB"])
    # Django is in tech core, MongoDB is in tech core — they should not fall
    # into domain or tools due to spurious "go" or "mongo" partial matches
    assert "Django" in result.core
    assert "MongoDB" in result.core

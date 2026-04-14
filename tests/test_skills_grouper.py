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

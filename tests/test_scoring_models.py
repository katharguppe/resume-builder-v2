import pytest
from dataclasses import fields


def test_ats_score_import():
    from app.scoring.models import ATSScore
    assert ATSScore is not None


def test_ats_score_construction():
    from app.scoring.models import ATSScore
    score = ATSScore(
        total=72,
        keyword_match=20,
        skills_coverage=24,
        experience_clarity=16,
        structure_completeness=12,
        keyword_matched=["python", "aws"],
        skills_matched=["Python", "AWS"],
        skills_missing=["Kubernetes"],
    )
    assert score.total == 72
    assert score.keyword_match == 20
    assert score.skills_coverage == 24
    assert score.experience_clarity == 16
    assert score.structure_completeness == 12
    assert score.keyword_matched == ["python", "aws"]
    assert score.skills_matched == ["Python", "AWS"]
    assert score.skills_missing == ["Kubernetes"]


def test_ats_score_list_defaults():
    from app.scoring.models import ATSScore
    score = ATSScore(
        total=0,
        keyword_match=0,
        skills_coverage=0,
        experience_clarity=0,
        structure_completeness=0,
    )
    assert score.keyword_matched == []
    assert score.skills_matched == []
    assert score.skills_missing == []


def test_missing_item_import():
    from app.scoring.models import MissingItem
    assert MissingItem is not None


def test_missing_item_construction():
    from app.scoring.models import MissingItem
    item = MissingItem(
        field="work_dates",
        label="Work experience dates",
        severity="HIGH",
        hint="Add start and end year to each role.",
    )
    assert item.field == "work_dates"
    assert item.severity == "HIGH"


def test_missing_item_severity_values():
    from app.scoring.models import MissingItem
    for sev in ("HIGH", "MEDIUM", "LOW"):
        item = MissingItem(field="f", label="l", severity=sev, hint="h")
        assert item.severity == sev

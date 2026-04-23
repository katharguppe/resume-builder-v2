import copy
from app.llm.quality_check import QualityReport, validate_quality, _check_bullets_too_long, BULLET_MAX_WORDS

SAMPLE_DRAFT = {
    "candidate_name": "Jane Doe",
    "summary": "Dedicated sales professional with experience in B2B markets.",
    "experience": [
        {
            "title": "Sales Manager",
            "company": "Acme Corp",
            "dates": "2021-2023",
            "bullets": [
                "Managed a team of 10 sales representatives across three regions.",
                "Increased revenue by 25% through targeted outreach campaigns.",
            ],
        },
        {
            "title": "Sales Executive",
            "company": "Beta Ltd",
            "dates": "2018-2021",
            "bullets": [
                "Developed client relationships with 50 enterprise accounts.",
            ],
        },
    ],
    "skills": ["Salesforce", "CRM", "Negotiation"],
    "education": [{"degree": "BBA", "institution": "Delhi University", "year": "2018"}],
}

SAMPLE_ORIGINAL = {"raw_text": "Managed a team of 10 sales reps. Increased revenue by 25%."}


def test_quality_report_fields():
    report = QualityReport(passed=True, issues=[], fixed_draft={})
    assert report.passed is True
    assert report.issues == []
    assert report.fixed_draft == {}


def test_validate_quality_returns_quality_report():
    report = validate_quality(SAMPLE_DRAFT, SAMPLE_ORIGINAL)
    assert isinstance(report, QualityReport)
    assert isinstance(report.passed, bool)
    assert isinstance(report.issues, list)
    assert isinstance(report.fixed_draft, dict)


def test_validate_quality_does_not_mutate_input():
    original_draft = copy.deepcopy(SAMPLE_DRAFT)
    validate_quality(SAMPLE_DRAFT, SAMPLE_ORIGINAL)
    assert SAMPLE_DRAFT == original_draft


def test_bullets_too_long_short_bullet_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    issues = _check_bullets_too_long(draft)
    assert issues == []


def test_bullets_too_long_exactly_30_words_no_issue():
    draft = {
        "experience": [
            {"title": "Manager", "bullets": ["word " * 30]}
        ]
    }
    issues = _check_bullets_too_long(draft)
    assert issues == []


def test_bullets_too_long_31_words_is_auto_fixed():
    long_bullet = " ".join([f"word{i}" for i in range(31)])
    draft = {
        "experience": [
            {"title": "Sales Manager", "bullets": [long_bullet]}
        ]
    }
    issues = _check_bullets_too_long(draft)
    assert len(issues) == 1
    assert issues[0].startswith("[AUTO-FIXED]")
    assert "Sales Manager" in issues[0]


def test_bullets_too_long_mutates_working_draft():
    long_bullet = " ".join([f"word{i}" for i in range(31)])
    draft = {
        "experience": [
            {"title": "Manager", "bullets": [long_bullet]}
        ]
    }
    _check_bullets_too_long(draft)
    trimmed = draft["experience"][0]["bullets"][0]
    assert len(trimmed.split()) <= BULLET_MAX_WORDS + 1  # +1 for "…" appended as one token
    assert trimmed.endswith("…")


def test_bullets_too_long_missing_experience_no_crash():
    issues = _check_bullets_too_long({})
    assert issues == []


def test_bullets_too_long_non_string_bullet_no_crash():
    draft = {"experience": [{"title": "Manager", "bullets": [None, 42]}]}
    issues = _check_bullets_too_long(draft)
    assert issues == []

import copy
from app.llm.quality_check import QualityReport, validate_quality

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

import pytest


def _make_fields(current_title="Senior Engineer"):
    return {
        "candidate_name": "Alice",
        "email": "alice@example.com",
        "phone": "9999999999",
        "current_title": current_title,
        "skills": ["Python"],
        "experience_summary": "",
    }


# ---------------------------------------------------------------------------
# HIGH severity
# ---------------------------------------------------------------------------

def test_detect_missing_high_no_dates():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Worked at various companies on Python projects"
    items = detect_missing(fields, text)
    fields_set = {i.field for i in items}
    assert "work_dates" in fields_set
    high = [i for i in items if i.severity == "HIGH"]
    assert any(i.field == "work_dates" for i in high)


def test_detect_missing_high_no_title():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields(current_title="")
    text = "Senior Engineer at Acme Ltd 2019-2022"
    items = detect_missing(fields, text)
    high = [i for i in items if i.severity == "HIGH"]
    assert any(i.field == "current_title" for i in high)


def test_detect_missing_no_high_when_all_present():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields(current_title="Senior Engineer")
    text = "Senior Engineer at Acme Ltd 2019-2023"
    items = detect_missing(fields, text)
    high = [i for i in items if i.severity == "HIGH"]
    assert high == []


# ---------------------------------------------------------------------------
# MEDIUM severity
# ---------------------------------------------------------------------------

def test_detect_missing_medium_no_achievements():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer at Acme Ltd 2019-2022 built backend services"
    items = detect_missing(fields, text)
    med = [i for i in items if i.severity == "MEDIUM"]
    assert any(i.field == "achievements" for i in med)


def test_detect_missing_no_medium_achievements_when_present():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer at Acme Ltd 2019-2022\nReduced latency by 40%"
    items = detect_missing(fields, text)
    assert not any(i.field == "achievements" for i in items)


def test_detect_missing_medium_no_company():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer 2019-2022 built backend systems"
    items = detect_missing(fields, text)
    med = [i for i in items if i.severity == "MEDIUM"]
    assert any(i.field == "company_names" for i in med)


def test_detect_missing_no_medium_company_when_present():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer at Acme Ltd 2019-2022"
    items = detect_missing(fields, text)
    assert not any(i.field == "company_names" for i in items)


# ---------------------------------------------------------------------------
# LOW severity
# ---------------------------------------------------------------------------

def test_detect_missing_low_no_certifications():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer at Acme Ltd 2019-2022 Skills Python"
    items = detect_missing(fields, text)
    low = [i for i in items if i.severity == "LOW"]
    assert any(i.field == "certifications" for i in low)


def test_detect_missing_no_low_cert_when_present():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Certifications\nAWS Certified 2022"
    items = detect_missing(fields, text)
    assert not any(i.field == "certifications" for i in items)


def test_detect_missing_low_no_social():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "Engineer at Acme Ltd 2019-2022"
    items = detect_missing(fields, text)
    low = [i for i in items if i.severity == "LOW"]
    assert any(i.field == "social_links" for i in low)


def test_detect_missing_no_low_social_when_present():
    from app.scoring.missing_info import detect_missing
    fields = _make_fields()
    text = "linkedin.com/in/alice github.com/alice"
    items = detect_missing(fields, text)
    assert not any(i.field == "social_links" for i in items)


# ---------------------------------------------------------------------------
# Return type + ordering
# ---------------------------------------------------------------------------

def test_detect_missing_returns_list_of_missing_items():
    from app.scoring.missing_info import detect_missing
    from app.scoring.models import MissingItem
    items = detect_missing(_make_fields(current_title=""), "no dates here")
    assert isinstance(items, list)
    for item in items:
        assert isinstance(item, MissingItem)


def test_detect_missing_severity_order():
    """HIGH items must appear before MEDIUM, MEDIUM before LOW."""
    from app.scoring.missing_info import detect_missing
    items = detect_missing(
        _make_fields(current_title=""),
        "no dates no company no certs",
    )
    sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    severities = [sev_order[i.severity] for i in items]
    assert severities == sorted(severities)


def test_detect_missing_empty_text_returns_all_items():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(current_title=""), "")
    fields_set = {i.field for i in items}
    assert "work_dates" in fields_set
    assert "current_title" in fields_set
    assert "achievements" in fields_set
    assert "company_names" in fields_set
    assert "certifications" in fields_set
    assert "social_links" in fields_set


def test_missing_item_has_section_field():
    """MissingItem must accept and store a section value."""
    from app.scoring.models import MissingItem
    item = MissingItem(
        field="work_dates",
        label="Work experience dates",
        severity="HIGH",
        hint="Add dates.",
        section="Experience",
    )
    assert item.section == "Experience"


def test_missing_item_section_defaults_to_empty_string():
    """section field must be optional (backwards-compatible)."""
    from app.scoring.models import MissingItem
    item = MissingItem(field="x", label="x", severity="HIGH", hint="x")
    assert item.section == ""


def test_detect_missing_sections_are_non_empty():
    """Every returned MissingItem must have a non-empty section."""
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(current_title=""), "")
    for item in items:
        assert item.section != "", f"field={item.field!r} has empty section"


def test_detect_missing_work_dates_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(), "no dates here")
    match = next(i for i in items if i.field == "work_dates")
    assert match.section == "Experience"


def test_detect_missing_current_title_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(current_title=""), "Senior Engineer at Acme 2019-2022")
    match = next(i for i in items if i.field == "current_title")
    assert match.section == "Contact"


def test_detect_missing_achievements_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(), "Engineer at Acme Ltd 2019-2022")
    match = next(i for i in items if i.field == "achievements")
    assert match.section == "Experience"


def test_detect_missing_company_names_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(), "Engineer 2019-2022")
    match = next(i for i in items if i.field == "company_names")
    assert match.section == "Experience"


def test_detect_missing_certifications_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(), "Engineer at Acme 2019-2022 reduced latency by 30%")
    match = next(i for i in items if i.field == "certifications")
    assert match.section == "Education"


def test_detect_missing_social_links_section():
    from app.scoring.missing_info import detect_missing
    items = detect_missing(_make_fields(), "Engineer at Acme 2019-2022 reduced latency by 30%")
    match = next(i for i in items if i.field == "social_links")
    assert match.section == "Contact"

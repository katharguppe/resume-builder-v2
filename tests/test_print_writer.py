"""
Tests for app/composer/print_writer.py — JobOS Print Resume PDF generator.
"""
import base64
import pytest
import fitz
from pathlib import Path

from app.composer.print_writer import generate_print_pdf, _apply_recency_rule, _extract_start_year

# Tiny valid 1×1 PNG (same as test_composer.py)
VALID_PNG_B64 = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


@pytest.fixture
def photo_bytes():
    return base64.b64decode(VALID_PNG_B64)


@pytest.fixture
def full_json():
    return {
        "candidate_name": "Priya Sharma",
        "contact": {
            "email": "priya@example.com",
            "phone": "+91 98765 43210",
            "linkedin": "linkedin.com/in/priyasharma",
        },
        "summary": "Sales professional with 8 years in FMCG. Specialist in key account management.",
        "experience": [
            {
                "title": "Senior Sales Manager",
                "company": "FoodCo India",
                "city": "Mumbai",
                "dates": "Jan 2020 - Present",
                "company_intro": "Leading FMCG distributor serving 50,000 retail outlets.",
                "bullets": ["Grew revenue by 40%", "Led team of 12"],
            },
            {
                "title": "Area Sales Executive",
                "company": "BeverageCorp",
                "city": "Pune",
                "dates": "Jun 2016 - Dec 2019",
                "company_intro": "National beverage brand with Rs500Cr turnover.",
                "bullets": ["Exceeded target by 120%", "Opened 200 new accounts", "Won Best Performer 2018"],
            },
            {
                "title": "Sales Representative",
                "company": "StartupX",
                "city": "Bangalore",
                "dates": "Jan 2014 - May 2016",
                "company_intro": "B2B SaaS startup.",
                "bullets": ["Managed 50 accounts", "Cold-called 100 leads/week", "CRM data entry", "Extra bullet 4"],
            },
        ],
        "education": [
            {"degree": "MBA Marketing", "institution": "Symbiosis Institute", "year": "2013"}
        ],
        "skills": ["Negotiation", "Key Accounts", "CRM"],
        "missing_fields": [],
        "print_fields": {
            "gender": "Female",
            "dob": "15-Mar-1990",
            "age": "35",
            "city": "Mumbai",
            "open_to_relocate": True,
            "notice_period": "30 days",
            "portfolio_url": "",
            "core_skills": ["Key Account Management", "Channel Sales", "Revenue Growth"],
            "tools_platforms": ["Salesforce", "Excel", "SAP"],
            "soft_skills": ["Negotiation", "Leadership", "Communication"],
            "psychometric_type": "[MISSING: Psychometric Type]",
            "languages": [
                {"language": "English", "proficiency": "Full Professional"},
                {"language": "Hindi", "proficiency": "Native"},
            ],
            "certifications": [
                {"name": "Certified Sales Professional", "issuing_body": "ISM", "year": "2018"}
            ],
            "awards": ["Best Regional Manager 2022 - FoodCo India"],
        },
    }


@pytest.fixture
def minimal_json():
    """JSON with only mandatory fields — everything else missing."""
    return {
        "candidate_name": "John Doe",
        "contact": {"email": "john@doe.com", "phone": "", "linkedin": ""},
        "summary": "A summary.",
        "experience": [],
        "education": [],
        "skills": [],
        "missing_fields": [],
        "print_fields": {},
    }


# ── Core generation tests ──────────────────────────────────────────────────

def test_generate_print_pdf_returns_true_and_creates_file(tmp_path, full_json):
    out = tmp_path / "print.pdf"
    result = generate_print_pdf(full_json, None, out)
    assert result is True
    assert out.exists()
    assert out.stat().st_size > 0


def test_generate_print_pdf_with_photo(tmp_path, full_json, photo_bytes):
    out = tmp_path / "print_photo.pdf"
    result = generate_print_pdf(full_json, photo_bytes, out)
    assert result is True
    assert out.exists()


def test_generate_print_pdf_missing_fields_show_in_pdf(tmp_path, minimal_json):
    out = tmp_path / "print_missing.pdf"
    result = generate_print_pdf(minimal_json, None, out)
    assert result is True
    doc = fitz.open(str(out))
    text = "".join(p.get_text() for p in doc)
    doc.close()
    assert "MISSING" in text


def test_generate_print_pdf_candidate_name_in_output(tmp_path, full_json):
    out = tmp_path / "print_name.pdf"
    generate_print_pdf(full_json, None, out)
    doc = fitz.open(str(out))
    text = doc[0].get_text()
    doc.close()
    assert "Priya Sharma" in text


def test_generate_print_pdf_section_headers_present(tmp_path, full_json):
    out = tmp_path / "print_sections.pdf"
    generate_print_pdf(full_json, None, out)
    doc = fitz.open(str(out))
    text = "".join(p.get_text() for p in doc)
    doc.close()
    for header in ("Profile Links", "Professional Summary", "Skills", "Professional Experience",
                   "Education", "Languages", "Certifications", "Awards"):
        assert header in text, f"Section '{header}' missing from Print PDF"


def test_generate_print_pdf_certifications_absent_when_empty(tmp_path, full_json):
    full_json["print_fields"]["certifications"] = []
    out = tmp_path / "print_no_certs.pdf"
    generate_print_pdf(full_json, None, out)
    doc = fitz.open(str(out))
    text = "".join(p.get_text() for p in doc)
    doc.close()
    assert "Certifications" not in text


def test_generate_print_pdf_awards_absent_when_empty(tmp_path, full_json):
    full_json["print_fields"]["awards"] = []
    out = tmp_path / "print_no_awards.pdf"
    generate_print_pdf(full_json, None, out)
    doc = fitz.open(str(out))
    text = "".join(p.get_text() for p in doc)
    doc.close()
    assert "Awards" not in text


def test_generate_print_pdf_returns_true_on_bad_photo(tmp_path, full_json):
    out = tmp_path / "print_bad_photo.pdf"
    result = generate_print_pdf(full_json, b"not an image", out)
    assert result is True
    assert out.exists()


# ── Recency rule tests ─────────────────────────────────────────────────────

def test_recency_rule_role_0_and_1_keep_all_bullets():
    experience = [
        {"title": "R0", "company": "C", "dates": "Jan 2022 - Present", "bullets": ["b1", "b2", "b3", "b4", "b5"]},
        {"title": "R1", "company": "C", "dates": "Jan 2018 - Dec 2021", "bullets": ["b1", "b2", "b3", "b4"]},
    ]
    result = _apply_recency_rule(experience)
    assert len(result[0]["bullets"]) == 5
    assert len(result[1]["bullets"]) == 4


def test_recency_rule_role_2_and_beyond_max_3_bullets():
    experience = [
        {"title": "R0", "company": "C", "dates": "2022 - Present", "bullets": ["b1"]},
        {"title": "R1", "company": "C", "dates": "2019 - 2022", "bullets": ["b1"]},
        {"title": "R2", "company": "C", "dates": "2016 - 2019", "bullets": ["b1", "b2", "b3", "b4", "b5"]},
        {"title": "R3", "company": "C", "dates": "2013 - 2016", "bullets": ["b1", "b2", "b3", "b4"]},
    ]
    result = _apply_recency_rule(experience)
    assert len(result[2]["bullets"]) == 3
    assert len(result[3]["bullets"]) == 3


def test_recency_rule_old_role_max_1_bullet():
    # Role starting 12 years ago (start year <= current_year - 10)
    experience = [
        {"title": "R0", "company": "C", "dates": "2022 - Present", "bullets": ["b1"]},
        {"title": "R1", "company": "C", "dates": "2019 - 2022", "bullets": ["b1"]},
        {"title": "Old", "company": "C", "dates": "2010 - 2014", "bullets": ["b1", "b2", "b3"]},
    ]
    result = _apply_recency_rule(experience)
    assert len(result[2]["bullets"]) == 1


def test_recency_rule_does_not_mutate_original():
    experience = [
        {"title": "R0", "company": "C", "dates": "2022 - Present", "bullets": ["b1"]},
        {"title": "R1", "company": "C", "dates": "2019 - 2022", "bullets": ["b1"]},
        {"title": "R2", "company": "C", "dates": "2016 - 2019", "bullets": ["b1", "b2", "b3", "b4"]},
    ]
    original_bullets = len(experience[2]["bullets"])
    _apply_recency_rule(experience)
    assert len(experience[2]["bullets"]) == original_bullets  # original unchanged


# ── Start year extraction tests ────────────────────────────────────────────

def test_extract_start_year_month_year_format():
    assert _extract_start_year("Jan 2019 - Dec 2022") == 2019


def test_extract_start_year_year_only():
    assert _extract_start_year("2015 - Present") == 2015


def test_extract_start_year_empty_string():
    assert _extract_start_year("") is None


def test_extract_start_year_none():
    assert _extract_start_year(None) is None

import pytest
import pathlib
import base64
import fitz  # PyMuPDF
import tempfile
import os
import glob as _glob
from app.composer import generate_resume_pdf

# A tiny valid 1x1 PNG image base64 encoded
VALID_PNG_B64 = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

@pytest.fixture
def dummy_photo_bytes():
    return base64.b64decode(VALID_PNG_B64)

@pytest.fixture
def dummy_json():
    return {
        "candidate_name": "Johnny Test",
        "contact": {
            "email": "johnny@test.com",
            "phone": "[MISSING: Phone]",
            "linkedin": "linkedin.com/in/johnnytest"
        },
        "summary": "Experienced software tester.",
        "experience": [
            {
                "title": "Senior Tester",
                "company": "TestCorp",
                "dates": "Jan 2020 - Present",
                "bullets": ["Wrote tests", "Found bugs"]
            }
        ],
        "education": [
            {
                "degree": "B.S. Computer Science",
                "institution": "Test University",
                "year": "2019"
            }
        ],
        "skills": ["Testing", "Python", "[MISSING: Cloud]"],
        "missing_fields": ["Phone", "Cloud"]
    }

def test_generate_resume_pdf_without_photo(tmp_path, dummy_json):
    output_pdf = tmp_path / "johnny_test_nophoto.pdf"
    result = generate_resume_pdf(dummy_json, None, output_pdf)
    
    assert result is True
    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0
    
    # Verify using PyMuPDF
    doc = fitz.open(str(output_pdf))
    assert len(doc) <= 2
    
    # Check text content
    text = doc[0].get_text()
    assert "Johnny Test" in text
    assert "johnny@test.com" in text
    assert "[MISSING: Phone]" in text
    assert "TestCorp" in text
    doc.close()

def test_generate_resume_pdf_with_photo(tmp_path, dummy_json, dummy_photo_bytes):
    output_pdf = tmp_path / "johnny_test_withphoto.pdf"
    result = generate_resume_pdf(dummy_json, dummy_photo_bytes, output_pdf)
    
    assert result is True
    assert output_pdf.exists()
    
    # Verify using PyMuPDF
    doc = fitz.open(str(output_pdf))
    assert len(doc) <= 2
    doc.close()

def test_generate_resume_bad_image(tmp_path, dummy_json):
    # Should handle bad image gracefully and continue without crashing
    output_pdf = tmp_path / "johnny_test_badphoto.pdf"
    bad_bytes = b"not an image"
    result = generate_resume_pdf(dummy_json, bad_bytes, output_pdf)

    assert result is True
    assert output_pdf.exists()

def test_section_headers_present(tmp_path, dummy_json):
    """Section headers must appear in the rendered text."""
    output_pdf = tmp_path / "section_headers.pdf"
    result = generate_resume_pdf(dummy_json, None, output_pdf)
    assert result is True
    doc = fitz.open(str(output_pdf))
    text = "".join(page.get_text() for page in doc)
    doc.close()
    for header in ("Summary", "Experience", "Education", "Skills"):
        assert header in text, f"Section header '{header}' missing from PDF"

def test_header_name_extractable_as_plain_text(tmp_path, dummy_json, dummy_photo_bytes):
    """Candidate name must appear as plain extractable text (not inside table cell)."""
    output_pdf = tmp_path / "header_plain.pdf"
    result = generate_resume_pdf(dummy_json, dummy_photo_bytes, output_pdf)
    assert result is True
    doc = fitz.open(str(output_pdf))
    text = doc[0].get_text()
    doc.close()
    assert "Johnny Test" in text
    assert "johnny@test.com" in text

def test_max_2_pages_long_content(tmp_path):
    """PDF must never exceed 2 pages even with very long experience section."""
    big_json = {
        "candidate_name": "Long Resume Person",
        "contact": {"email": "long@test.com", "phone": "555-1234", "linkedin": "li.com/long"},
        "summary": "A very experienced professional." * 5,
        "experience": [
            {
                "title": f"Engineer Level {i}",
                "company": f"MegaCorp {i}",
                "dates": f"200{i % 10} - 201{i % 10}",
                "bullets": [f"Accomplished milestone {j} for project {i}" for j in range(8)],
            }
            for i in range(20)
        ],
        "education": [{"degree": "B.S. CS", "institution": "State U", "year": "2000"}],
        "skills": [f"Skill{k}" for k in range(40)],
    }
    output_pdf = tmp_path / "long_resume.pdf"
    result = generate_resume_pdf(big_json, None, output_pdf)
    assert result is True
    doc = fitz.open(str(output_pdf))
    assert len(doc) <= 2, f"Expected ≤2 pages, got {len(doc)}"
    doc.close()

def test_photo_handler_no_temp_file_leak(dummy_photo_bytes):
    """process_photo_for_pdf must not leave temp files on disk."""
    from app.composer.photo_handler import process_photo_for_pdf
    tmp_dir = tempfile.gettempdir()
    before = set(_glob.glob(os.path.join(tmp_dir, "*.jpg")) + _glob.glob(os.path.join(tmp_dir, "*.png")))
    result = process_photo_for_pdf(dummy_photo_bytes)
    after = set(_glob.glob(os.path.join(tmp_dir, "*.jpg")) + _glob.glob(os.path.join(tmp_dir, "*.png")))
    assert result is not None
    assert after == before, f"Temp files leaked: {after - before}"


def test_section_headings_teal_color(tmp_path, dummy_json):
    """Section headings must render in Deep Teal (#1B6B6B)."""
    output_pdf = tmp_path / "teal_headers.pdf"
    assert generate_resume_pdf(dummy_json, None, output_pdf) is True
    doc = fitz.open(str(output_pdf))
    page = doc[0]
    text_dict = page.get_text("dict")
    doc.close()

    teal = 0x1B6B6B  # Deep Teal in decimal = 1797995
    section_headers = {"Summary", "Experience", "Education", "Skills"}
    all_spans = [
        span
        for block in text_dict["blocks"]
        if block.get("type") == 0
        for line in block["lines"]
        for span in line["spans"]
    ]
    header_spans = [s for s in all_spans if s["text"].strip() in section_headers]
    assert len(header_spans) >= 3, f"Expected ≥3 section headers, found {len(header_spans)}"
    for span in header_spans:
        assert span["color"] == teal, (
            f"Header '{span['text']}' has color {span['color']:#08x}, expected {teal:#08x}"
        )


def test_section_dividers_present(tmp_path, dummy_json):
    """Each section heading must be followed by a horizontal divider line."""
    output_pdf = tmp_path / "dividers.pdf"
    assert generate_resume_pdf(dummy_json, None, output_pdf) is True
    doc = fitz.open(str(output_pdf))
    page = doc[0]
    drawings = page.get_drawings()
    doc.close()

    horizontal_lines = []
    for d in drawings:
        for item in d.get("items", []):
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.y - p2.y) < 1.0 and abs(p1.x - p2.x) > 50:
                    horizontal_lines.append((p1, p2))
    assert len(horizontal_lines) >= 3, (
        f"Expected ≥3 HRFlowable divider lines, found {len(horizontal_lines)}"
    )


def test_role_title_and_company_separate_lines(tmp_path, dummy_json):
    """Role title and company/dates must appear as separate text items (different y-positions)."""
    output_pdf = tmp_path / "role_layout.pdf"
    assert generate_resume_pdf(dummy_json, None, output_pdf) is True
    doc = fitz.open(str(output_pdf))
    page = doc[0]
    text_dict = page.get_text("dict")
    doc.close()

    all_spans = [
        span
        for block in text_dict["blocks"]
        if block.get("type") == 0
        for line in block["lines"]
        for span in line["spans"]
    ]
    title_spans = [s for s in all_spans if "Senior Tester" in s["text"]]
    company_spans = [s for s in all_spans if "TestCorp" in s["text"]]
    assert len(title_spans) >= 1, "Role title 'Senior Tester' not found in PDF"
    assert len(company_spans) >= 1, "Company 'TestCorp' not found in PDF"
    # They must not be on the same line (different origin y-coordinates)
    assert title_spans[0]["origin"][1] != company_spans[0]["origin"][1], (
        "Title and company are on the same line — expected separate lines"
    )


def test_role_has_teal_left_border(tmp_path, dummy_json):
    """Each experience role must have a vertical teal left-border line."""
    output_pdf = tmp_path / "left_border.pdf"
    assert generate_resume_pdf(dummy_json, None, output_pdf) is True
    doc = fitz.open(str(output_pdf))
    page = doc[0]
    drawings = page.get_drawings()
    doc.close()

    vertical_lines = []
    for d in drawings:
        for item in d.get("items", []):
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.x - p2.x) < 1.0 and abs(p1.y - p2.y) > 5:
                    vertical_lines.append((p1, p2))
    assert len(vertical_lines) >= 1, (
        f"Expected ≥1 vertical border line from LeftBorderFlowable, found {len(vertical_lines)}"
    )

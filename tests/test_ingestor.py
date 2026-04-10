import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import subprocess

from app.ingestor.converter import convert_doc_to_pdf
from app.ingestor.extractor import extract_text_and_photo, _is_headshot_candidate

@patch("app.ingestor.converter.subprocess.run")
def test_convert_doc_to_pdf_success(mock_run, tmp_path):
    # Setup dummy input and output paths
    input_file = tmp_path / "resume.docx"
    input_file.touch()  # Create empty file so exists() check passes
    
    output_dir = tmp_path / "converted"
    expected_output = output_dir / "resume.pdf"
    
    # We need to simulate LibreOffice actually creating the PDF file so our function doesn't fail
    def side_effect(*args, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        expected_output.touch()
        
    mock_run.side_effect = side_effect
    
    result = convert_doc_to_pdf(input_file, output_dir)
    
    assert result == expected_output
    assert expected_output.exists()
    mock_run.assert_called_once()
    
    # Verify command structure
    called_cmd = mock_run.call_args[0][0]
    assert "--headless" in called_cmd
    assert "--convert-to" in called_cmd
    assert "pdf" in called_cmd
    assert "--outdir" in called_cmd
    assert str(output_dir) in called_cmd
    assert str(input_file) in called_cmd

@patch("app.ingestor.converter.subprocess.run")
def test_convert_doc_to_pdf_timeout(mock_run, tmp_path):
    input_file = tmp_path / "resume.doc"
    input_file.touch()
    
    output_dir = tmp_path / "converted"
    
    # Simulate timeout
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="soffice", timeout=30)
    
    with pytest.raises(subprocess.TimeoutExpired):
        convert_doc_to_pdf(input_file, output_dir)

@patch("app.ingestor.converter.subprocess.run")
def test_convert_doc_to_pdf_failure_code(mock_run, tmp_path):
    input_file = tmp_path / "resume.doc"
    input_file.touch()
    
    output_dir = tmp_path / "converted"
    
    # Simulate error exit code
    mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="soffice", stderr="Crash")
    
    with pytest.raises(subprocess.CalledProcessError):
        convert_doc_to_pdf(input_file, output_dir)

def test_convert_doc_to_pdf_file_not_found():
    input_file = Path("nonexistent_resume.docx")
    output_dir = Path("converted")
    
    with pytest.raises(FileNotFoundError):
        convert_doc_to_pdf(input_file, output_dir)

@patch("app.ingestor.extractor.fitz.open")
@patch("app.ingestor.extractor.pdfplumber.open")
def test_extract_text_and_photo_success_with_photo(mock_pdfplumber_open, mock_fitz_open, tmp_path):
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()
    
    # Mock pdfplumber
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Sample Resume Text"
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf
    
    # Mock fitz
    mock_doc = MagicMock()
    mock_fitz_page = MagicMock()
    mock_fitz_page.rect.height = 800.0
    mock_fitz_page.rect.width = 612.0
    mock_fitz_page.get_image_info.return_value = [
        {"bbox": (10, 10, 210, 210), "xref": 123, "width": 200, "height": 200, "smask": 0}
    ]  # y is in top third (10 < 266.6), valid headshot dimensions, small rendered bbox
    mock_doc.__getitem__.return_value = mock_fitz_page
    mock_doc.__len__.return_value = 1
    mock_doc.extract_image.return_value = {"image": b"fake_image_bytes"}
    mock_fitz_open.return_value = mock_doc
    
    result = extract_text_and_photo(pdf_path)
    
    assert result["text"] == "Sample Resume Text"
    assert result["photo_bytes"] == b"fake_image_bytes"
    assert result["original_filename"] == "resume.pdf"

@patch("app.ingestor.extractor.fitz.open")
@patch("app.ingestor.extractor.pdfplumber.open")
def test_extract_text_and_photo_success_no_photo(mock_pdfplumber_open, mock_fitz_open, tmp_path):
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()
    
    # Mock pdfplumber
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Sample Resume Text No Photo"
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf
    
    # Mock fitz with image outside top third (y=600 > 266)
    mock_doc = MagicMock()
    mock_fitz_page = MagicMock()
    mock_fitz_page.rect.height = 800.0
    mock_fitz_page.rect.width = 612.0
    mock_fitz_page.get_image_info.return_value = [{"bbox": (10, 600, 50, 650), "xref": 124}]
    mock_doc.__getitem__.return_value = mock_fitz_page
    mock_doc.__len__.return_value = 1
    mock_doc.extract_image.return_value = {"image": b"fake_image_bytes2"}
    mock_fitz_open.return_value = mock_doc
    
    result = extract_text_and_photo(pdf_path)
    
    assert result["text"] == "Sample Resume Text No Photo"
    assert result["photo_bytes"] is None
    assert result["original_filename"] == "resume.pdf"

def test_extract_text_and_photo_file_not_found():
    pdf_path = Path("nonexistent_resume.pdf")
    with pytest.raises(FileNotFoundError):
        extract_text_and_photo(pdf_path)

from app.ingestor.extractor import extract_text

def test_extract_text_txt(tmp_path):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello World", encoding='utf-8')
    assert extract_text(txt_file) == "Hello World"

@patch("app.ingestor.extractor.pdfplumber.open")
def test_extract_text_pdf(mock_pdfplumber_open, tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.touch()
    
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "PDF Text"
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf
    
    assert extract_text(pdf_file) == "PDF Text"

@patch("app.ingestor.extractor.convert_doc_to_pdf")
@patch("app.ingestor.extractor.pdfplumber.open")
def test_extract_text_doc(mock_pdfplumber_open, mock_convert, tmp_path):
    doc_file = tmp_path / "test.docx"
    doc_file.touch()
    
    mock_convert.return_value = tmp_path / "temp.pdf"
    
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "DOCX Text"
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf
    
    assert extract_text(doc_file) == "DOCX Text"
    mock_convert.assert_called_once()
    
def test_extract_text_unsupported(tmp_path):
    bad_file = tmp_path / "test.jpg"
    bad_file.touch()
    with pytest.raises(ValueError):
        extract_text(bad_file)


# --- _is_headshot_candidate unit tests ---

def test_headshot_candidate_accepts_square():
    assert _is_headshot_candidate({"width": 200, "height": 200, "smask": 0}) is True

def test_headshot_candidate_accepts_portrait():
    # aspect 0.7 exactly (140/200)
    assert _is_headshot_candidate({"width": 140, "height": 200, "smask": 0}) is True

def test_headshot_candidate_accepts_landscape():
    # aspect 1.4 exactly (280/200)
    assert _is_headshot_candidate({"width": 280, "height": 200, "smask": 0}) is True

def test_headshot_candidate_rejects_too_small():
    # both dimensions below minimum
    assert _is_headshot_candidate({"width": 79, "height": 79, "smask": 0}) is False

def test_headshot_candidate_rejects_small_width_only():
    assert _is_headshot_candidate({"width": 79, "height": 200, "smask": 0}) is False

def test_headshot_candidate_rejects_small_height_only():
    assert _is_headshot_candidate({"width": 200, "height": 79, "smask": 0}) is False

def test_headshot_candidate_rejects_wide_logo():
    # aspect 5.0 — typical wide logo
    assert _is_headshot_candidate({"width": 400, "height": 80, "smask": 0}) is False

def test_headshot_candidate_rejects_tall_narrow():
    # aspect 0.2 — tall narrow image
    assert _is_headshot_candidate({"width": 80, "height": 400, "smask": 0}) is False

def test_headshot_candidate_rejects_transparent():
    # smask non-zero = has alpha/transparency
    assert _is_headshot_candidate({"width": 200, "height": 200, "smask": 42}) is False


@patch("app.ingestor.extractor.fitz.open")
@patch("app.ingestor.extractor.pdfplumber.open")
def test_extract_photo_skips_logo_image(mock_pdfplumber_open, mock_fitz_open, tmp_path):
    """Wide logo in top-third must be skipped; result photo_bytes is None."""
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()

    mock_pdf = MagicMock()
    mock_page_pl = MagicMock()
    mock_page_pl.extract_text.return_value = "Resume text"
    mock_pdf.pages = [mock_page_pl]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    mock_doc = MagicMock()
    mock_fitz_page = MagicMock()
    mock_fitz_page.rect.height = 800.0
    mock_fitz_page.rect.width = 612.0
    # Wide logo: width=400, height=60 → aspect 6.7, fails heuristic
    mock_fitz_page.get_image_info.return_value = [
        {"bbox": (10, 10, 410, 70), "xref": 1, "width": 400, "height": 60, "smask": 0}
    ]
    mock_doc.__getitem__.return_value = mock_fitz_page
    mock_doc.__len__.return_value = 1
    mock_doc.extract_image.return_value = {"image": b"logo_bytes"}
    mock_fitz_open.return_value = mock_doc

    result = extract_text_and_photo(pdf_path)
    assert result["photo_bytes"] is None


@patch("app.ingestor.extractor.fitz.open")
@patch("app.ingestor.extractor.pdfplumber.open")
def test_extract_photo_skips_fullpage_background_picks_headshot(mock_pdfplumber_open, mock_fitz_open, tmp_path):
    """Full-page background image is skipped; the smaller headshot behind it is returned."""
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()

    mock_pdf = MagicMock()
    mock_page_pl = MagicMock()
    mock_page_pl.extract_text.return_value = "Resume text"
    mock_pdf.pages = [mock_page_pl]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    mock_doc = MagicMock()
    mock_fitz_page = MagicMock()
    mock_fitz_page.rect.height = 792.0
    mock_fitz_page.rect.width = 612.0
    mock_fitz_page.get_image_info.return_value = [
        # Background graphic: rendered bbox covers most of the page → must be skipped
        {"bbox": (0.0, 0.0, 612.0, 576.0), "xref": 29, "width": 816, "height": 768, "smask": 0},
        # Actual headshot: small rendered bbox in top-left corner → must be selected
        {"bbox": (33.0, 18.0, 162.0, 147.0), "xref": 28, "width": 400, "height": 400, "smask": 0},
    ]
    mock_doc.__getitem__.return_value = mock_fitz_page
    mock_doc.__len__.return_value = 1
    mock_doc.extract_image.return_value = {"image": b"headshot_bytes"}
    mock_fitz_open.return_value = mock_doc

    result = extract_text_and_photo(pdf_path)
    assert result["photo_bytes"] == b"headshot_bytes"
    mock_doc.extract_image.assert_called_once_with(28)


@patch("app.ingestor.extractor.fitz.open")
@patch("app.ingestor.extractor.pdfplumber.open")
def test_extract_photo_no_photo_when_only_fullpage_background(mock_pdfplumber_open, mock_fitz_open, tmp_path):
    """When only a full-page background exists (no real headshot), photo_bytes is None."""
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()

    mock_pdf = MagicMock()
    mock_page_pl = MagicMock()
    mock_page_pl.extract_text.return_value = "Resume text"
    mock_pdf.pages = [mock_page_pl]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    mock_doc = MagicMock()
    mock_fitz_page = MagicMock()
    mock_fitz_page.rect.height = 792.0
    mock_fitz_page.rect.width = 612.0
    mock_fitz_page.get_image_info.return_value = [
        {"bbox": (0.0, 0.0, 612.0, 576.0), "xref": 29, "width": 816, "height": 768, "smask": 0},
    ]
    mock_doc.__getitem__.return_value = mock_fitz_page
    mock_doc.__len__.return_value = 1
    mock_doc.extract_image.return_value = {"image": b"bg_bytes"}
    mock_fitz_open.return_value = mock_doc

    result = extract_text_and_photo(pdf_path)
    assert result["photo_bytes"] is None

import logging
from pathlib import Path
from typing import Optional, Dict, Any
import tempfile
from app.ingestor.converter import convert_doc_to_pdf

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

def extract_text(file_path: Path) -> str:
    """
    Extract text natively from a file (.txt, .pdf, .doc, .docx).
    For .doc/.docx, it temporarily converts it to PDF to extract text, then cleans up.
    
    Args:
        file_path (Path): Path to the source file.
        
    Returns:
        str: The extracted text content.
    """
    if pdfplumber is None:
        raise ImportError("pdfplumber must be installed to use extract_text.")

    file_path = Path(file_path).resolve()
    if not file_path.exists():
        logger.error(f"Input file not found: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = file_path.suffix.lower()
    
    if ext == '.txt':
        try:
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return file_path.read_text(encoding='latin-1', errors='replace')
            
    elif ext == '.pdf':
        try:
            with pdfplumber.open(file_path) as pdf:
                pages_text = [page.extract_text() for page in pdf.pages if page.extract_text()]
                return "\n".join(pages_text)
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {file_path.name}: {e}")
            raise
            
    elif ext in ['.doc', '.docx']:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            try:
                pdf_path = convert_doc_to_pdf(file_path, tmp_path)
                with pdfplumber.open(pdf_path) as pdf:
                    pages_text = [page.extract_text() for page in pdf.pages if page.extract_text()]
                    return "\n".join(pages_text)
            except Exception as e:
                logger.error(f"Failed to extract text from DOC/DOCX {file_path.name}: {e}")
                raise
    else:
        raise ValueError(f"Unsupported file format for text extraction: {ext}")

def _is_headshot_candidate(info: dict) -> bool:
    """Return True if image dimensions and transparency suggest a headshot photo."""
    width = info.get("width", 0)
    height = info.get("height", 0)
    smask = info.get("smask", 0)
    if width < 80 or height < 80:
        return False
    aspect = width / height
    if aspect < 0.7 or aspect > 1.4:
        return False
    if smask != 0:
        return False
    return True


def extract_text_and_photo(pdf_path: Path) -> Dict[str, Any]:
    """
    Extracts text and photo (if present in the top third of the first page) from a PDF resume.
    
    Args:
        pdf_path (Path): Path to the PDF resume file.
        
    Returns:
        dict: A dictionary containing:
            - text (str): The concatenated text from all pages.
            - photo_bytes (bytes | None): The extracted image bytes, or None if no image found.
            - original_filename (str): The name of the original PDF file.
            
    Raises:
        FileNotFoundError: If the input PDF file does not exist.
        ImportError: If pdfplumber or PyMuPDF are not installed.
    """
    if pdfplumber is None or fitz is None:
        raise ImportError("pdfplumber and PyMuPDF (fitz) must be installed to use extract_text_and_photo.")

    pdf_path = Path(pdf_path).resolve()
    
    if not pdf_path.exists():
        logger.error(f"Input file not found: {pdf_path}")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
    logger.info(f"Extracting text and photo from {pdf_path.name}")
    
    # Text Extraction
    extracted_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            extracted_text = "\n".join(pages_text)
    except Exception as e:
        logger.error(f"Failed to extract text using pdfplumber for {pdf_path.name}: {e}")
        raise

    # Photo Extraction
    photo_bytes: Optional[bytes] = None
    try:
        doc = fitz.open(pdf_path)
        if len(doc) > 0:
            page = doc[0] # First page
            
            # Use top third of the page height as threshold
            top_third_threshold = page.rect.height / 3.0
            
            images_info = page.get_image_info(xrefs=True)
            for info in images_info:
                bbox = info.get("bbox")
                xref = info.get("xref")
                if bbox and xref:
                    # bbox format: (x0, y0, x1, y1)
                    y0, y1 = bbox[1], bbox[3]

                    if y0 < top_third_threshold or y1 < top_third_threshold:
                        # Reject background graphics: rendered size > 35% of page's larger dimension
                        rendered_w = bbox[2] - bbox[0]
                        rendered_h = bbox[3] - bbox[1]
                        page_max = max(page.rect.width, page.rect.height)
                        if rendered_w > page_max * 0.35 or rendered_h > page_max * 0.35:
                            continue
                        if not _is_headshot_candidate(info):
                            continue
                        base_image = doc.extract_image(xref)
                        if base_image:
                            photo_bytes = base_image.get("image")
                            break # Stop searching after first valid image
                            
    except Exception as e:
        logger.warning(f"Failed to extract photo using fitz for {pdf_path.name}: {e}. Returning None for photo.")

    finally:
        if 'doc' in locals() and hasattr(doc, 'close'):
            doc.close()

    return {
        "text": extracted_text,
        "photo_bytes": photo_bytes,
        "original_filename": pdf_path.name
    }

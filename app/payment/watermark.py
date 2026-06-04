import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def watermark_pdf_bytes(pdf_path: Path) -> bytes:
    """Return PDF bytes with a PREVIEW watermark on every page.

    Does NOT write any file. The clean PDF at pdf_path is never modified.
    Uses PyMuPDF (fitz) to insert semi-transparent grey text overlay.
    """
    doc = fitz.open(str(pdf_path))
    for page in doc:
        rect = page.rect
        centre_x = rect.width * 0.5
        centre_y = rect.height * 0.5

        # Insert watermark text at page centre with low opacity effect
        page.insert_text(
            fitz.Point(centre_x - 120, centre_y - 40),
            "PREVIEW",
            fontsize=80,
            color=(0.75, 0.75, 0.75),  # light grey — simulates low opacity
            overlay=True,
        )

    result = doc.tobytes()
    doc.close()
    logger.debug("Watermarked PDF from %s (%d bytes)", pdf_path, len(result))
    return result

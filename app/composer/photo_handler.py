"""
Handles photo extraction and processing for the PDF Composer.
Writes photo bytes to a temp file, validates them, then cleans up.
"""
import io
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


def process_photo_for_pdf(photo_bytes: bytes) -> io.BytesIO | None:
    """
    Writes photo bytes to a temp file, reads them back as BytesIO, then cleans up the temp file.
    Returns None if photo_bytes is empty or if a file I/O error occurs.
    Note: image format validation occurs in the caller via ReportLab's ImageReader.
    """
    if not photo_bytes:
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(photo_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            validated = f.read()

        return io.BytesIO(validated)

    except Exception as e:
        logger.warning(f"Error processing photo: {e}")
        return None

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError as e:
                logger.warning(f"Could not delete temp photo file {tmp_path}: {e}")

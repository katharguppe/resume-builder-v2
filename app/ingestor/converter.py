import logging
import subprocess
from pathlib import Path
from typing import Optional

from app.config import config

logger = logging.getLogger(__name__)

def convert_doc_to_pdf(input_file: Path, output_dir: Path) -> Path:
    """
    Converts a .doc or .docx file to .pdf using LibreOffice headless mode.
    
    Args:
        input_file (Path): Path to the source .doc or .docx file.
        output_dir (Path): Path to the directory where the .pdf should be saved.
        
    Returns:
        Path: The absolute path to the generated PDF file.
        
    Raises:
        subprocess.TimeoutExpired: If the conversion takes more than 30 seconds.
        subprocess.CalledProcessError: If LibreOffice exits with a non-zero status.
        FileNotFoundError: If the input file does not exist.
        RuntimeError: If output PDF is missing after successful command execution.
    """
    input_file = Path(input_file).resolve()
    output_dir = Path(output_dir).resolve()

    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        raise FileNotFoundError(f"Source resume file not found: {input_file}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    expected_output_pdf = output_dir / f"{input_file.stem}.pdf"

    logger.info(f"Converting {input_file.name} to PDF in {output_dir}")

    cmd = [
        config.LIBREOFFICE_PATH,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(input_file)
    ]

    try:
        subprocess.run(cmd, timeout=30, check=True, capture_output=True, text=True)
    except subprocess.TimeoutExpired as e:
        logger.error(f"Conversion timed out for {input_file.name} after 30 seconds.")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"Conversion failed for {input_file.name}. Exit code: {e.returncode}. Error: {e.stderr}")
        raise

    if not expected_output_pdf.exists():
        error_msg = f"Conversion seemingly succeeded, but output PDF not found at {expected_output_pdf}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info(f"Successfully converted to {expected_output_pdf.name}")
    return expected_output_pdf

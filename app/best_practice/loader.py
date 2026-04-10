import logging
from pathlib import Path
from typing import List

from app.ingestor.extractor import extract_text
from app.config import config

logger = logging.getLogger(__name__)

SUPPORTED_JD_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt'}

def find_and_read_jd(source_folder: Path) -> str:
    """
    Find the Job Description file at the root of the source directory and extract its text.
    Handles multiple candidates by selecting the largest file and logging a warning.
    
    Args:
        source_folder (Path): The root workspace folder containing the JD file.
        
    Returns:
        str: The extracted plain text of the JD.
    """
    source_folder = Path(source_folder).resolve()
    
    if not source_folder.is_dir():
        logger.error(f"Source folder does not exist or is not a directory: {source_folder}")
        raise FileNotFoundError(f"Source folder not found: {source_folder}")
        
    candidate_files = []
    
    for item in source_folder.iterdir():
        if item.is_file() and item.suffix.lower() in SUPPORTED_JD_EXTENSIONS:
            candidate_files.append(item)
            
    if not candidate_files:
        logger.error(f"No valid Job Description file found in {source_folder}")
        raise FileNotFoundError(f"No Job Description file found at {source_folder}. Expected one of {SUPPORTED_JD_EXTENSIONS}.")
        
    # If multiple candidates exist, pick the largest file by size
    jd_file = candidate_files[0]
    if len(candidate_files) > 1:
        candidate_files.sort(key=lambda x: x.stat().st_size, reverse=True)
        jd_file = candidate_files[0]
        logger.warning(f"Multiple potential JD files found in {source_folder}. "
                       f"Selected the largest one: {jd_file.name}")
                       
    logger.info(f"Extracting Job Description from {jd_file.name}")
    return extract_text(jd_file)

def load_best_practice_files(file_paths: List[Path]) -> str:
    """
    Extract text from one or more best-practice resume templates and combine them.
    Limits the combined text using BEST_PRACTICE_MAX_TOKENS.
    
    Args:
        file_paths (List[Path]): A list of user-supplied best practice resume paths.
        
    Returns:
        str: The combined text, truncated if necessary.
    """
    if not file_paths:
        return ""
        
    combined_text = []
    for file_path in file_paths:
        file_path = Path(file_path).resolve()
        try:
            logger.info(f"Extracting best practice text from {file_path.name}")
            text = extract_text(file_path)
            if text:
                combined_text.append(f"--- BEGIN TEMPLATE: {file_path.name} ---\n{text}\n--- END TEMPLATE ---")
        except Exception as e:
            logger.warning(f"Failed to read best practice file {file_path}: {e}")
            
    full_text = "\n\n".join(combined_text)
    
    # Approximate token truncation (1 token ~ 4 chars)
    max_chars = config.BEST_PRACTICE_MAX_TOKENS * 4
    if len(full_text) > max_chars:
        logger.warning(f"Combined best practice templates exceed {max_chars} chars. Truncating.")
        full_text = full_text[:max_chars] + "\n...(truncated)"
        
    return full_text

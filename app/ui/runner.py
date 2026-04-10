import os
import json
import logging
import threading
from pathlib import Path

from app.state.db import StateDB
from app.state.checkpoint import CheckpointManager
from app.state.models import CandidateStatus

from app.ingestor.converter import convert_doc_to_pdf
from app.ingestor.extractor import extract_text, extract_text_and_photo
from app.best_practice.loader import find_and_read_jd, load_best_practice_files
from app.best_practice.searcher import search_best_practice
from app.llm.finetuner import fine_tune_resume

from app.composer.pdf_writer import generate_resume_pdf
from app.email_handler.sender import send_outreach_email, send_final_pdf_email

logger = logging.getLogger(__name__)


def _find_resumes_dir(source_folder: Path) -> Path:
    """Find the resumes directory within source_folder.

    Priority:
    1. A subfolder named 'resumes' (case-insensitive).
    2. Any single subfolder found inside source_folder.
    3. source_folder itself (resumes at root).
    """
    subfolders = [d for d in source_folder.iterdir() if d.is_dir()]
    # Priority 1: case-insensitive 'resumes' match
    for sub in subfolders:
        if sub.name.lower() == "resumes":
            return sub
    # Priority 2: exactly one subfolder — use it
    if len(subfolders) == 1:
        return subfolders[0]
    # Priority 3: fallback to source root
    logger.warning(
        f"No 'resumes' subfolder found in {source_folder}. "
        "Using source folder root for resume discovery."
    )
    return source_folder


class BatchRunner(threading.Thread):
    def __init__(self, db_path: Path, session_state_dict: dict):
        super().__init__()
        self.db_path = db_path
        self.session_state_dict = session_state_dict
        self._stop_event = threading.Event()
        
    def stop(self):
        self._stop_event.set()
        
    def discover_files(self, db: StateDB, config) -> None:
        if not config.source_folder:
            logger.error("source_folder is not set in config — cannot discover files.")
            return
        source_folder = Path(config.source_folder)
        resumes_dir = _find_resumes_dir(source_folder)
        logger.info(f"Using resumes directory: {resumes_dir}")

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT source_filename FROM candidates WHERE source_folder = ?", (str(source_folder),))
            existing_files = {row["source_filename"] for row in cursor.fetchall()}

        for filepath in resumes_dir.iterdir():
            if filepath.is_file() and filepath.suffix.lower() in [".doc", ".docx", ".pdf"]:
                if filepath.name not in existing_files:
                    db.add_candidate(str(source_folder), filepath.name)

    def run(self):
        db = StateDB(self.db_path)
        config = db.get_config()
        if not config:
            self.session_state_dict["is_running"] = False
            return
            
        self.discover_files(db, config)
        
        source_folder = Path(config.source_folder)
        dest_folder = Path(config.destination_folder)
        converted_dir = dest_folder / "converted"
        photos_dir = dest_folder / "photos"
        converted_dir.mkdir(parents=True, exist_ok=True)
        photos_dir.mkdir(parents=True, exist_ok=True)

        try:
            jd_text = find_and_read_jd(source_folder)
        except Exception as e:
            logger.error(f"Failed to read JD: {e}")
            self.session_state_dict["is_running"] = False
            return
            
        # Best Practice
        bp_paths_list = json.loads(config.best_practice_paths) if config.best_practice_paths else []
        if bp_paths_list:
            bp_paths = [Path(p) for p in bp_paths_list]
            bp_text = load_best_practice_files(bp_paths)
        else:
            # Fallback web search (we extract title guess from JD filename or text)
            jd_title_guess = "Professional"
            for f in source_folder.iterdir():
                if f.is_file() and f.parent == source_folder:
                    jd_title_guess = f.stem
                    break
            bp_text = search_best_practice(jd_title_guess)
            
        ckpt_manager = CheckpointManager(db)
        ckpt = ckpt_manager.get_resume_point(str(source_folder))
        batch_number = (ckpt.batch_number + 1) if ckpt else 1
        total_processed = ckpt.total_processed if ckpt else 0
        
        pending = db.get_pending_candidates(str(source_folder), config.batch_size if config.batch_size > 0 else -1)
        
        for candidate in pending:
            if self._stop_event.is_set():
                break
                
            db.set_status(candidate.id, CandidateStatus.PROCESSING)
            filepath = source_folder / "resumes" / candidate.source_filename
            
            error_msg = ""
            status_to_set = CandidateStatus.ERROR
            
            try:
                # 1. Ingestor
                pdf_path = filepath
                if filepath.suffix.lower() in [".doc", ".docx"]:
                    pdf_path = convert_doc_to_pdf(filepath, converted_dir)
                    
                extract_result = extract_text_and_photo(pdf_path)
                resume_text = extract_result.get("text", "")
                photo_bytes = extract_result.get("photo_bytes")
                
                photo_path_str = None
                if photo_bytes:
                    photo_file = photos_dir / f"{candidate.id}_photo.jpg"
                    photo_file.write_bytes(photo_bytes)
                    photo_path_str = str(photo_file)
                    
                # 2. LLM Finetuner
                candidate_name_guess = filepath.stem
                llm_output = fine_tune_resume(resume_text, jd_text, bp_text, candidate_name_guess)
                
                missing = llm_output.get("missing_fields", [])
                
                # 3. Composer
                output_pdf = dest_folder / f"{llm_output.get('candidate_name', candidate_name_guess)}_finetuned.pdf"
                generate_resume_pdf(llm_output, photo_bytes, output_pdf)
                
                # 4. Update DB
                db.update_candidate(candidate.id, {
                    "candidate_name": llm_output.get("candidate_name", candidate_name_guess),
                    "candidate_email": llm_output.get("contact", {}).get("email", ""),
                    "missing_fields": json.dumps(missing),
                    "llm_output_json": json.dumps(llm_output),
                    "photo_path": photo_path_str,
                    "output_pdf_path": str(output_pdf)
                })
                
                # 5. Determine status — email is sent manually via recruiter checkbox in dashboard
                if not missing:
                    db.set_status(candidate.id, CandidateStatus.HAPPY_PATH)
                else:
                    db.set_status(candidate.id, CandidateStatus.MISSING_DETAILS)
                        
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Candidate {candidate.id} failed: {e}")
                db.set_status(candidate.id, CandidateStatus.ERROR)
                db.update_candidate(candidate.id, {"error_message": error_msg})
                
            total_processed += 1
            ckpt_manager.save_checkpoint(batch_number, config.batch_size, candidate.source_filename, total_processed, str(source_folder))
            
        self.session_state_dict["is_running"] = False


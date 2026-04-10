import sqlite3
import contextlib
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import CandidateStatus, CandidateRecord, ConfigRecord

VALID_TRANSITIONS = {
    CandidateStatus.PENDING: [CandidateStatus.PROCESSING],
    CandidateStatus.PROCESSING: [CandidateStatus.HAPPY_PATH, CandidateStatus.MISSING_DETAILS, CandidateStatus.ERROR],
    CandidateStatus.HAPPY_PATH: [CandidateStatus.EMAIL_SENT],
    CandidateStatus.MISSING_DETAILS: [CandidateStatus.EMAIL_SENT],
    CandidateStatus.EMAIL_SENT: [CandidateStatus.AWAITING_PAYMENT],
    CandidateStatus.AWAITING_PAYMENT: [CandidateStatus.PAYMENT_CONFIRMED],
    CandidateStatus.PAYMENT_CONFIRMED: [CandidateStatus.OUTPUT_SENT]
}

class StateDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            # Enable WAL mode for Docker volume safety (prevents corruption with mounted DBs)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_folder TEXT NOT NULL,
                    source_filename TEXT NOT NULL,
                    candidate_name TEXT,
                    candidate_email TEXT,
                    jd_title TEXT,
                    status TEXT NOT NULL,
                    missing_fields TEXT,
                    recruiter_additions TEXT,
                    llm_output_json TEXT,
                    photo_path TEXT,
                    output_pdf_path TEXT,
                    email_sent_at DATETIME,
                    output_sent_at DATETIME,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_number INTEGER,
                    batch_size INTEGER,
                    last_processed_filename TEXT,
                    total_processed INTEGER,
                    source_folder TEXT,
                    session_started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    session_ended_at DATETIME
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS recruiter_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    recruiter_name TEXT,
                    recruiter_email TEXT,
                    smtp_server TEXT,
                    smtp_port INTEGER,
                    smtp_password TEXT,
                    service_fee TEXT,
                    batch_size INTEGER,
                    source_folder TEXT,
                    destination_folder TEXT,
                    best_practice_paths TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def set_status(self, candidate_id: int, new_status: str):
        if not isinstance(new_status, CandidateStatus):
            try:
                new_status = CandidateStatus(new_status)
            except ValueError:
                raise ValueError(f"Invalid status value: {new_status}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Candidate {candidate_id} not found")
            
            try:
                current_status = CandidateStatus(row['status'])
            except ValueError:
                current_status = row['status'] # Handle unmapped legacy states gracefully if needed
            
            allowed = VALID_TRANSITIONS.get(current_status, [])
            
            if new_status not in allowed:
                raise ValueError(f"Invalid transition from {current_status.value if isinstance(current_status, CandidateStatus) else current_status} to {new_status.value}")
                
            cursor.execute("UPDATE candidates SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status.value, candidate_id))
            conn.commit()

    def add_candidate(self, source_folder: str, source_filename: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO candidates (
                    source_folder, source_filename, status, missing_fields, recruiter_additions
                ) VALUES (?, ?, ?, ?, ?)
            """, (source_folder, source_filename, CandidateStatus.PENDING.value, "[]", "{}"))
            conn.commit()
            return cursor.lastrowid

    def get_candidate(self, candidate_id: int) -> Optional[CandidateRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return CandidateRecord(**dict(row))
            
    def update_candidate(self, candidate_id: int, updates: Dict[str, Any]):
        if not updates:
            return
            
        if 'status' in updates:
            raise ValueError("Status must be updated via set_status()")
            
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        
        values = list(updates.values())
        values.append(candidate_id)
        
        with self._get_connection() as conn:
            conn.execute(f"UPDATE candidates SET {set_clause} WHERE id = ?", values)
            conn.commit()

    def get_pending_candidates(self, source_folder: str, limit: int = -1) -> List[CandidateRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM candidates WHERE source_folder = ? AND status = ? ORDER BY id ASC"
            params = [source_folder, CandidateStatus.PENDING.value]
            if limit > 0:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [CandidateRecord(**dict(row)) for row in rows]
            
    def get_config(self) -> Optional[ConfigRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recruiter_config WHERE id = 1")
            row = cursor.fetchone()
            if not row:
                return None
            return ConfigRecord(**dict(row))
            
    def save_config(self, config_data: Dict[str, Any]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM recruiter_config WHERE id = 1")
            exists = cursor.fetchone() is not None
            
            if exists:
                set_clause = ", ".join([f"{k} = ?" for k in config_data.keys()])
                set_clause += ", updated_at = CURRENT_TIMESTAMP"
                values = list(config_data.values())
                conn.execute(f"UPDATE recruiter_config SET {set_clause} WHERE id = 1", values)
            else:
                columns = ", ".join(config_data.keys())
                placeholders = ", ".join(["?" for _ in config_data])
                values = list(config_data.values())
                conn.execute(f"INSERT INTO recruiter_config (id, {columns}) VALUES (1, {placeholders})", values)
            conn.commit()

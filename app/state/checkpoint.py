from typing import Optional
from .db import StateDB
from .models import CheckpointRecord

class CheckpointManager:
    def __init__(self, db: StateDB):
        self.db = db

    def save_checkpoint(self, batch_number: int, batch_size: int, last_processed_filename: str, total_processed: int, source_folder: str):
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO checkpoints (
                    batch_number, batch_size, last_processed_filename, 
                    total_processed, source_folder
                ) VALUES (?, ?, ?, ?, ?)
            """, (batch_number, batch_size, last_processed_filename, total_processed, source_folder))
            conn.commit()

    def get_resume_point(self, source_folder: str) -> Optional[CheckpointRecord]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM checkpoints 
                WHERE source_folder = ? 
                ORDER BY session_started_at DESC, id DESC LIMIT 1
            """, (source_folder,))
            row = cursor.fetchone()
            if not row:
                return None
            return CheckpointRecord(**dict(row))

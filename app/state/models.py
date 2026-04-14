from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SubmissionStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    REVIEW_READY = "REVIEW_READY"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    REVISION_EXHAUSTED = "REVISION_EXHAUSTED"
    ACCEPTED = "ACCEPTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    DOWNLOAD_READY = "DOWNLOAD_READY"
    DOWNLOADED = "DOWNLOADED"
    ERROR = "ERROR"


@dataclass
class SubmissionRecord:
    id: Optional[int]
    user_id: int
    session_token: str
    resume_raw_text: Optional[str]
    resume_fields_json: Optional[str]
    resume_photo_path: Optional[str]
    jd_raw_text: Optional[str]
    jd_fields_json: Optional[str]
    ats_score_json: Optional[str]
    status: str
    revision_count: int
    error_message: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    llm_output_json: Optional[str] = None
    output_pdf_path: Optional[str] = None

class CandidateStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    HAPPY_PATH = "HAPPY_PATH"
    MISSING_DETAILS = "MISSING_DETAILS"
    EMAIL_SENT = "EMAIL_SENT"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    OUTPUT_SENT = "OUTPUT_SENT"
    ERROR = "ERROR"

@dataclass
class CandidateRecord:
    id: Optional[int]
    source_folder: str
    source_filename: str
    candidate_name: Optional[str]
    candidate_email: Optional[str]
    jd_title: Optional[str]
    status: str
    missing_fields: str
    recruiter_additions: str
    llm_output_json: Optional[str]
    photo_path: Optional[str]
    output_pdf_path: Optional[str]
    email_sent_at: Optional[str]
    output_sent_at: Optional[str]
    error_message: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]

@dataclass
class CheckpointRecord:
    id: Optional[int]
    batch_number: int
    batch_size: int
    last_processed_filename: str
    total_processed: int
    source_folder: str
    session_started_at: str
    session_ended_at: Optional[str]

@dataclass
class ConfigRecord:
    id: int
    recruiter_name: Optional[str]
    recruiter_email: Optional[str]
    smtp_server: Optional[str]
    smtp_port: Optional[int]
    smtp_password: Optional[str]
    service_fee: Optional[str]
    batch_size: int
    source_folder: Optional[str]
    destination_folder: Optional[str]
    best_practice_paths: str
    updated_at: Optional[str]

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from cryptography.fernet import Fernet

from app.state.models import CandidateRecord, ConfigRecord, CandidateStatus
from app.email_handler.crypto import encrypt_password, decrypt_password
from app.email_handler.templates import (
    get_outreach_subject, get_outreach_html, get_outreach_text,
    get_final_subject, get_final_html, get_final_text
)
from app.email_handler.sender import send_outreach_email, send_final_pdf_email

@pytest.fixture
def mock_key():
    return Fernet.generate_key().decode('utf-8')

@pytest.fixture
def sample_config(mock_key):
    return ConfigRecord(
        id=1,
        recruiter_name="Alice Recruiter",
        recruiter_email="alice@example.com",
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        smtp_password=encrypt_password("supersecret", mock_key),
        service_fee="999",
        batch_size=10,
        source_folder=None,
        destination_folder="/tmp",
        best_practice_paths="[]",
        updated_at="2026-03-24T00:00:00"
    )

@pytest.fixture
def sample_candidate_happy():
    return CandidateRecord(
        id=1,
        source_folder="/src",
        source_filename="john.pdf",
        candidate_name="John Doe",
        candidate_email="john@example.com",
        jd_title="Software Engineer",
        status=CandidateStatus.HAPPY_PATH.value,
        missing_fields="[]",
        recruiter_additions="{}",
        llm_output_json=json.dumps({
            "summary": "Great engineer.",
            "experience": [
                {"title": "Dev", "company": "Tech Corp"},
                {"title": "Intern", "company": "StartUp"}
            ]
        }),
        photo_path=None,
        output_pdf_path="/dest/john_finetuned.pdf",
        email_sent_at=None,
        output_sent_at=None,
        error_message=None,
        created_at=None,
        updated_at=None
    )

@pytest.fixture
def sample_candidate_missing(sample_candidate_happy):
    c = sample_candidate_happy
    c.status = CandidateStatus.MISSING_DETAILS.value
    c.missing_fields = '["Phone Number", "LinkedIn"]'
    return c

def test_email_sent_status_exists():
    assert CandidateStatus.EMAIL_SENT.value == "EMAIL_SENT"


def test_crypto_roundtrip(mock_key):
    plain = "my_password_123!"
    encrypted = encrypt_password(plain, mock_key)
    assert encrypted != plain
    decrypted = decrypt_password(encrypted, mock_key)
    assert decrypted == plain

def test_crypto_failures():
    with pytest.raises(ValueError):
        encrypt_password("pass", "")
    with pytest.raises(ValueError):
        decrypt_password("enc", "")
    with pytest.raises(ValueError):
        decrypt_password("invalid_token", Fernet.generate_key().decode('utf-8'))

def test_templates_happy_path(sample_candidate_happy, sample_config):
    subject = get_outreach_subject(sample_candidate_happy)
    assert "Software Engineer" in subject
    
    html = get_outreach_html(sample_candidate_happy, sample_config)
    assert "John Doe" in html
    assert "Alice Recruiter" in html
    assert "₹999" in html
    assert "Great engineer." in html
    assert "Tech Corp" in html
    assert "Simply reply with 'Yes'" in html
    assert "need a few more details" not in html

def test_templates_missing_details(sample_candidate_missing, sample_config):
    html = get_outreach_html(sample_candidate_missing, sample_config)
    assert "To complete your resume, I need a few more details" in html
    assert "Phone Number" in html
    assert "LinkedIn" in html
    assert "Simply reply with 'Yes'" not in html

def test_templates_final(sample_candidate_happy, sample_config):
    subject = get_final_subject(sample_candidate_happy)
    assert "Software Engineer" in subject
    html = get_final_html(sample_candidate_happy, sample_config)
    assert "John Doe" in html
    assert "attached your complete, fine-tuned resume PDF" in html

@patch('app.email_handler.sender.app_config')
@patch('app.email_handler.sender.smtplib.SMTP')
def test_send_outreach_email_success(mock_smtp_class, mock_app_config, sample_candidate_happy, sample_config, mock_key):
    mock_app_config.ENCRYPTION_KEY = mock_key
    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance
    mock_smtp_class.return_value = mock_smtp_instance
    
    result = send_outreach_email(sample_candidate_happy, sample_config)
    
    assert result is True
    mock_smtp_class.assert_called_with("smtp.gmail.com", 587)
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_with("alice@example.com", "supersecret")
    mock_smtp_instance.send_message.assert_called_once()

@patch('app.email_handler.sender.app_config')
@patch('app.email_handler.sender.smtplib.SMTP')
def test_send_outreach_email_no_email(mock_smtp, mock_app_config, sample_candidate_happy, sample_config):
    sample_candidate_happy.candidate_email = None
    result = send_outreach_email(sample_candidate_happy, sample_config)
    assert result is False
    mock_smtp.assert_not_called()

@patch('app.email_handler.sender.Path.exists')
@patch('app.email_handler.sender.Path.read_bytes')
@patch('app.email_handler.sender.app_config')
@patch('app.email_handler.sender.smtplib.SMTP')
def test_send_final_pdf_email_success(mock_smtp_class, mock_app_config, mock_read_bytes, mock_exists, sample_candidate_happy, sample_config, mock_key):
    mock_app_config.ENCRYPTION_KEY = mock_key
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"fake pdf content"
    
    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance
    mock_smtp_class.return_value = mock_smtp_instance
    
    result = send_final_pdf_email(sample_candidate_happy, sample_config)
    
    assert result is True
    mock_smtp_instance.send_message.assert_called_once()

@patch('app.email_handler.sender.Path.exists')
@patch('app.email_handler.sender.app_config')
@patch('app.email_handler.sender.smtplib.SMTP')
def test_send_final_pdf_email_missing_file(mock_smtp, mock_app_config, mock_exists, sample_candidate_happy, sample_config, mock_key):
    mock_app_config.ENCRYPTION_KEY = mock_key
    mock_exists.return_value = False
    
    result = send_final_pdf_email(sample_candidate_happy, sample_config)
    
    assert result is False
    mock_smtp.assert_not_called()

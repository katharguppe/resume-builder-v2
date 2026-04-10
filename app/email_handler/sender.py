import logging
import smtplib
from pathlib import Path
from email.message import EmailMessage

from app.state.models import CandidateRecord, ConfigRecord
from app.config import config as app_config
from .crypto import decrypt_password
from . import templates

logger = logging.getLogger(__name__)

def _get_smtp_connection(config: ConfigRecord) -> smtplib.SMTP:
    server = config.smtp_server
    port = config.smtp_port or 587
    user = config.recruiter_email
    
    # Decrypt password using the global ENCRYPTION_KEY
    if not config.smtp_password:
        raise ValueError("SMTP password is not set in configuration.")
    try:
        password = decrypt_password(config.smtp_password, app_config.ENCRYPTION_KEY)
    except Exception as e:
        logger.error(f"Could not decrypt SMTP password: {e}")
        raise ValueError("Invalid SMTP credentials encryption.")

    smtp = smtplib.SMTP(server, port)
    smtp.ehlo()
    smtp.starttls()
    smtp.login(user, password)
    return smtp

def _send_email(msg: EmailMessage, config: ConfigRecord) -> bool:
    try:
        with _get_smtp_connection(config) as server:
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {msg['To']}: {e}")
        return False

def send_outreach_email(candidate: CandidateRecord, config: ConfigRecord) -> bool:
    """
    Sends the outreach email to the candidate (either Happy Path or Missing Details).
    """
    if not candidate.candidate_email:
        logger.error(f"Candidate {candidate.id} has no email address.")
        return False

    logger.info(f"Sending outreach email to {candidate.candidate_email} for candidate ID {candidate.id}")
    
    msg = EmailMessage()
    msg['Subject'] = templates.get_outreach_subject(candidate)
    msg['From'] = config.recruiter_email
    msg['To'] = candidate.candidate_email

    text_content = templates.get_outreach_text(candidate, config)
    html_content = templates.get_outreach_html(candidate, config)

    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype='html')

    return _send_email(msg, config)

def send_final_pdf_email(candidate: CandidateRecord, config: ConfigRecord) -> bool:
    """
    Sends the final fine-tuned PDF to the candidate upon payment confirmation.
    """
    if not candidate.candidate_email:
        logger.error(f"Candidate {candidate.id} has no email address.")
        return False

    pdf_path_str = candidate.output_pdf_path
    if not pdf_path_str:
        logger.error(f"Candidate {candidate.id} has no output PDF path.")
        return False
        
    pdf_path = Path(pdf_path_str)
    if not pdf_path.exists():
        logger.error(f"Output PDF not found for candidate {candidate.id} at {pdf_path}")
        return False

    logger.info(f"Sending final PDF email to {candidate.candidate_email} for candidate ID {candidate.id}")
    
    msg = EmailMessage()
    msg['Subject'] = templates.get_final_subject(candidate)
    msg['From'] = config.recruiter_email
    msg['To'] = candidate.candidate_email

    text_content = templates.get_final_text(candidate, config)
    html_content = templates.get_final_html(candidate, config)

    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype='html')

    try:
        pdf_data = pdf_path.read_bytes()
        msg.add_attachment(
            pdf_data, 
            maintype='application', 
            subtype='pdf', 
            filename=pdf_path.name
        )
    except Exception as e:
        logger.error(f"Failed to attach PDF {pdf_path}: {e}")
        return False

    return _send_email(msg, config)

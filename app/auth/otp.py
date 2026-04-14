import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from app.config import config as app_config
from app.email_handler.crypto import decrypt_password

logger = logging.getLogger(__name__)


def generate_otp() -> str:
    """Returns a cryptographically random 6-digit numeric OTP."""
    return str(secrets.randbelow(1_000_000)).zfill(6)


def send_otp_email(email: str, otp_code: str) -> bool:
    """
    Sends OTP code via SMTP using env-var config only.
    Returns True on success, False on failure.
    """
    smtp_host = app_config.SMTP_HOST
    smtp_port = app_config.SMTP_PORT
    smtp_user = app_config.SMTP_USER
    encrypted_pw = app_config.SMTP_PASSWORD_ENCRYPTED
    encryption_key = app_config.ENCRYPTION_KEY

    if not smtp_user or not encrypted_pw or not encryption_key:
        logger.error("SMTP credentials not configured — OTP email not sent.")
        return False

    try:
        password = decrypt_password(encrypted_pw, encryption_key)
    except Exception as e:
        logger.error(f"Could not decrypt SMTP password: {e}")
        return False

    msg = EmailMessage()
    msg["Subject"] = "Your JobOS Login Code"
    msg["From"] = smtp_user
    msg["To"] = email
    msg.set_content(
        f"Your one-time login code is: {otp_code}\n\n"
        f"This code expires in {app_config.OTP_EXPIRY_MINUTES} minutes.\n"
        "Do not share this code with anyone."
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(smtp_user, password)
            smtp.send_message(msg)
        logger.info(f"OTP email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {e}")
        return False


def verify_otp(auth_db, email: str, code: str) -> bool:
    """
    Returns True if `code` matches a valid, unused OTP for `email`.
    Marks the OTP as used on success so it cannot be replayed.
    """
    otp = auth_db.get_valid_otp(email)
    if otp is None:
        return False
    if otp.code != code:
        return False
    auth_db.mark_otp_used(otp.id)
    return True


def issue_otp(auth_db, email: str) -> str:
    """
    Generates a new OTP, stores it in DB, returns the plain-text code.
    Caller is responsible for emailing it via send_otp_email().
    """
    code = generate_otp()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=app_config.OTP_EXPIRY_MINUTES)
    ).isoformat()
    auth_db.store_otp(email, code, expires_at)
    return code

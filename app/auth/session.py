import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.config import config as app_config

logger = logging.getLogger(__name__)


def create_session(auth_db, email: str) -> str:
    """
    Creates or re-uses a user record, creates a new UUID session token,
    stores it in DB, updates last_login, returns the token string.
    """
    user_id = auth_db.create_user(email)
    auth_db.update_last_login(email)
    token = str(uuid.uuid4())
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=app_config.SESSION_EXPIRY_HOURS)
    ).isoformat()
    auth_db.create_session(user_id, email, token, expires_at)
    logger.info(f"Session created for {email}, expires {expires_at}")
    return token


def validate_session(auth_db, token: str):
    """
    Returns the SessionRecord if the token is valid and not expired,
    None otherwise.
    """
    return auth_db.get_session(token)


def expire_session(auth_db, token: str):
    """Immediately invalidates a session token."""
    auth_db.expire_session(token)
    logger.info(f"Session expired: {token[:8]}...")

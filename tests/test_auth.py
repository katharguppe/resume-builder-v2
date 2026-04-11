import sqlite3
import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from app.state.db import AuthDB


@pytest.fixture
def auth_db(tmp_path):
    db_path = tmp_path / "test_auth.db"
    return AuthDB(db_path)


def test_create_user_and_get_by_email(auth_db):
    user_id = auth_db.create_user("alice@example.com")
    assert isinstance(user_id, int)
    user = auth_db.get_user_by_email("alice@example.com")
    assert user is not None
    assert user.email == "alice@example.com"
    assert user.id == user_id


def test_create_user_idempotent(auth_db):
    id1 = auth_db.create_user("bob@example.com")
    id2 = auth_db.create_user("bob@example.com")
    assert id1 == id2


def test_get_user_by_email_missing(auth_db):
    assert auth_db.get_user_by_email("nobody@example.com") is None


def test_store_and_get_valid_otp(auth_db):
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    otp_id = auth_db.store_otp("carol@example.com", "123456", expires_at)
    assert isinstance(otp_id, int)
    otp = auth_db.get_valid_otp("carol@example.com")
    assert otp is not None
    assert otp.code == "123456"
    assert otp.used == 0


def test_get_valid_otp_expired(auth_db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    auth_db.store_otp("dave@example.com", "999999", past)
    assert auth_db.get_valid_otp("dave@example.com") is None


def test_mark_otp_used(auth_db):
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    otp_id = auth_db.store_otp("eve@example.com", "111111", expires_at)
    auth_db.mark_otp_used(otp_id)
    assert auth_db.get_valid_otp("eve@example.com") is None


def test_create_and_get_session(auth_db):
    import uuid
    user_id = auth_db.create_user("frank@example.com")
    token = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    auth_db.create_session(user_id, "frank@example.com", token, expires_at)
    session = auth_db.get_session(token)
    assert session is not None
    assert session.email == "frank@example.com"
    assert session.token == token


def test_get_session_expired(auth_db):
    import uuid
    user_id = auth_db.create_user("grace@example.com")
    token = str(uuid.uuid4())
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    auth_db.create_session(user_id, "grace@example.com", token, past)
    assert auth_db.get_session(token) is None


def test_expire_session(auth_db):
    import uuid
    user_id = auth_db.create_user("henry@example.com")
    token = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    auth_db.create_session(user_id, "henry@example.com", token, expires_at)
    auth_db.expire_session(token)
    assert auth_db.get_session(token) is None


def test_update_last_login(auth_db):
    auth_db.create_user("iris@example.com")
    auth_db.update_last_login("iris@example.com")
    user = auth_db.get_user_by_email("iris@example.com")
    assert user.last_login_at is not None


def test_wal_mode_enabled(auth_db):
    with auth_db._get_connection() as conn:
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"


def test_config_has_smtp_and_otp_fields():
    from app.config import Config
    cfg = Config()
    assert hasattr(cfg, "SMTP_HOST")
    assert hasattr(cfg, "SMTP_PORT")
    assert hasattr(cfg, "SMTP_USER")
    assert hasattr(cfg, "SMTP_PASSWORD_ENCRYPTED")
    assert hasattr(cfg, "OTP_EXPIRY_MINUTES")
    assert hasattr(cfg, "SESSION_EXPIRY_HOURS")
    assert cfg.SMTP_PORT == 587        # default
    assert cfg.OTP_EXPIRY_MINUTES == 10
    assert cfg.SESSION_EXPIRY_HOURS == 24


def test_generate_otp_is_6_digits():
    from app.auth.otp import generate_otp
    otp = generate_otp()
    assert len(otp) == 6
    assert otp.isdigit()


def test_generate_otp_is_random():
    from app.auth.otp import generate_otp
    otps = {generate_otp() for _ in range(20)}
    assert len(otps) > 1


def test_verify_otp_valid(auth_db):
    from app.auth.otp import verify_otp
    from datetime import datetime, timedelta, timezone
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    auth_db.store_otp("judy@example.com", "424242", expires_at)
    result = verify_otp(auth_db, "judy@example.com", "424242")
    assert result is True


def test_verify_otp_wrong_code(auth_db):
    from app.auth.otp import verify_otp
    from datetime import datetime, timedelta, timezone
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    auth_db.store_otp("kate@example.com", "111111", expires_at)
    result = verify_otp(auth_db, "kate@example.com", "999999")
    assert result is False


def test_verify_otp_expired(auth_db):
    from app.auth.otp import verify_otp
    from datetime import datetime, timedelta, timezone
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    auth_db.store_otp("lena@example.com", "777777", past)
    result = verify_otp(auth_db, "lena@example.com", "777777")
    assert result is False


def test_verify_otp_marks_used(auth_db):
    from app.auth.otp import verify_otp
    from datetime import datetime, timedelta, timezone
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    auth_db.store_otp("mary@example.com", "555555", expires_at)
    verify_otp(auth_db, "mary@example.com", "555555")
    # Second attempt with same code must fail
    result = verify_otp(auth_db, "mary@example.com", "555555")
    assert result is False

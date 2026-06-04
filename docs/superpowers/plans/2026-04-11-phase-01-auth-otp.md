# Phase 1: Auth - OTP Accounts + Session Management

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build OTP-only email auth with UUID sessions stored in SQLite, gated by a Streamlit login page.

**Architecture:** A new `AuthDB` class is added to `app/state/db.py` alongside `StateDB` — same file, same WAL-mode SQLite, separate class and tables. `app/auth/` holds models, OTP logic, and session logic. `app/ui/pages/0_Login.py` is the Streamlit entry point that gates the rest of the app.

**Tech Stack:** Python 3.13, SQLite WAL, smtplib, Fernet (cryptography), uuid, secrets, Streamlit, python-dotenv

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/auth/models.py` | Create | UserRecord, OTPRecord, SessionRecord dataclasses |
| `app/state/db.py` | Modify | Add AuthDB class — users/otp_codes/sessions tables + CRUD |
| `app/config.py` | Modify | Add SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD_ENCRYPTED, OTP_EXPIRY_MINUTES, SESSION_EXPIRY_HOURS |
| `app/auth/otp.py` | Create | generate_otp(), send_otp_email(), verify_otp() |
| `app/auth/session.py` | Create | create_session(), validate_session(), expire_session() |
| `app/auth/__init__.py` | Modify | Re-export public API |
| `app/ui/pages/0_Login.py` | Create | Streamlit OTP login page |
| `tests/test_auth.py` | Create | Unit + integration tests for auth module |

---

## DB Schema

```sql
-- Auto-created or signed-up on first OTP send
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login_at DATETIME
);

-- One active OTP per email; old ones expire naturally
CREATE TABLE IF NOT EXISTS otp_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    code TEXT NOT NULL,
    expires_at DATETIME NOT NULL,
    used INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- UUID session tokens, 24-hour expiry
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## Task 1: Auth Models

**Files:**
- Create: `app/auth/models.py`

- [ ] **Step 1: Create `app/auth/models.py`**

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class UserRecord:
    id: Optional[int]
    email: str
    created_at: Optional[str]
    last_login_at: Optional[str]


@dataclass
class OTPRecord:
    id: Optional[int]
    email: str
    code: str
    expires_at: str
    used: int
    created_at: Optional[str]


@dataclass
class SessionRecord:
    id: Optional[int]
    user_id: int
    email: str
    token: str
    expires_at: str
    created_at: Optional[str]
```

- [ ] **Step 2: Commit**

```bash
git add app/auth/models.py
git commit -m "[PHASE-01] add: auth models - UserRecord, OTPRecord, SessionRecord"
```

---

## Task 2: AuthDB

**Files:**
- Modify: `app/state/db.py` (append after StateDB class, do not touch StateDB)
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_auth.py -v
```

Expected: `ImportError: cannot import name 'AuthDB' from 'app.state.db'`

- [ ] **Step 3: Add AuthDB to `app/state/db.py`**

Append after the `StateDB` class (do not touch StateDB):

```python
class AuthDB:
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
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login_at DATETIME
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS otp_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    code TEXT NOT NULL,
                    expires_at DATETIME NOT NULL,
                    used INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            conn.commit()

    def create_user(self, email: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                return row["id"]
            cursor.execute(
                "INSERT INTO users (email) VALUES (?)", (email,)
            )
            conn.commit()
            return cursor.lastrowid

    def get_user_by_email(self, email: str):
        from app.auth.models import UserRecord
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if not row:
                return None
            return UserRecord(**dict(row))

    def update_last_login(self, email: str):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE email = ?",
                (email,)
            )
            conn.commit()

    def store_otp(self, email: str, code: str, expires_at: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO otp_codes (email, code, expires_at) VALUES (?, ?, ?)",
                (email, code, expires_at)
            )
            conn.commit()
            return cursor.lastrowid

    def get_valid_otp(self, email: str):
        from app.auth.models import OTPRecord
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM otp_codes
                   WHERE email = ? AND used = 0
                     AND expires_at > datetime('now')
                   ORDER BY id DESC LIMIT 1""",
                (email,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return OTPRecord(**dict(row))

    def mark_otp_used(self, otp_id: int):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE otp_codes SET used = 1 WHERE id = ?", (otp_id,)
            )
            conn.commit()

    def create_session(self, user_id: int, email: str, token: str, expires_at: str):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (user_id, email, token, expires_at) VALUES (?, ?, ?, ?)",
                (user_id, email, token, expires_at)
            )
            conn.commit()

    def get_session(self, token: str):
        from app.auth.models import SessionRecord
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM sessions
                   WHERE token = ? AND expires_at > datetime('now')""",
                (token,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return SessionRecord(**dict(row))

    def expire_session(self, token: str):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET expires_at = datetime('now', '-1 second') WHERE token = ?",
                (token,)
            )
            conn.commit()
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/test_auth.py -v
```

Expected: All 11 tests PASS.

- [ ] **Step 5: Confirm existing tests still pass**

```
pytest tests/test_state.py -v
```

Expected: All existing tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/state/db.py app/auth/models.py tests/test_auth.py
git commit -m "[PHASE-01] add: AuthDB - users/otp_codes/sessions tables with CRUD"
```

---

## Task 3: Config Extension

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Write the failing test** (add to `tests/test_auth.py`)

```python
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
```

- [ ] **Step 2: Run to confirm it fails**

```
pytest tests/test_auth.py::test_config_has_smtp_and_otp_fields -v
```

Expected: FAIL — `AttributeError: 'Config' object has no attribute 'SMTP_HOST'`

- [ ] **Step 3: Extend `app/config.py`**

Replace the entire file:

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    # LLM
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_EXTRACT_MODEL: str = os.getenv("LLM_EXTRACT_MODEL", "claude-haiku-4-5-20251001")
    LLM_REWRITE_MODEL: str = os.getenv("LLM_REWRITE_MODEL", "claude-sonnet-4-6")
    # Crypto
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    # LibreOffice
    LIBREOFFICE_PATH: str = os.getenv("LIBREOFFICE_PATH", "soffice")
    # Logging / LLM tuning
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MAX_LLM_RETRIES: int = int(os.getenv("MAX_LLM_RETRIES", "3"))
    BEST_PRACTICE_MAX_TOKENS: int = int(os.getenv("BEST_PRACTICE_MAX_TOKENS", "3000"))
    # SMTP (OTP delivery)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD_ENCRYPTED: str = os.getenv("SMTP_PASSWORD_ENCRYPTED", "")
    # Auth
    OTP_EXPIRY_MINUTES: int = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))
    SESSION_EXPIRY_HOURS: int = int(os.getenv("SESSION_EXPIRY_HOURS", "24"))

config = Config()
```

- [ ] **Step 4: Run test to confirm it passes**

```
pytest tests/test_auth.py::test_config_has_smtp_and_otp_fields -v
```

Expected: PASS.

- [ ] **Step 5: Confirm no regressions**

```
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add app/config.py
git commit -m "[PHASE-01] add: config fields for SMTP, OTP expiry, session expiry"
```

---

## Task 4: OTP Module

**Files:**
- Create: `app/auth/otp.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_auth.py`)

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```
pytest tests/test_auth.py::test_generate_otp_is_6_digits tests/test_auth.py::test_verify_otp_valid -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.auth.otp'`

- [ ] **Step 3: Create `app/auth/otp.py`**

```python
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
    Sends OTP code via SMTP (env-var config only).
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
    Marks the OTP as used on success.
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
    Caller is responsible for emailing the code via send_otp_email().
    """
    code = generate_otp()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=app_config.OTP_EXPIRY_MINUTES)
    ).isoformat()
    auth_db.store_otp(email, code, expires_at)
    return code
```

- [ ] **Step 4: Run OTP tests to confirm they pass**

```
pytest tests/test_auth.py -k "otp" -v
```

Expected: All 6 OTP-related tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/auth/otp.py tests/test_auth.py
git commit -m "[PHASE-01] add: otp module - generate_otp, issue_otp, verify_otp"
```

---

## Task 5: Session Module

**Files:**
- Create: `app/auth/session.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_auth.py`)

```python
def test_create_session_returns_token(auth_db):
    from app.auth.session import create_session
    token = create_session(auth_db, "nina@example.com")
    assert isinstance(token, str)
    assert len(token) == 36  # UUID4 format


def test_validate_session_valid(auth_db):
    from app.auth.session import create_session, validate_session
    token = create_session(auth_db, "oliver@example.com")
    session = validate_session(auth_db, token)
    assert session is not None
    assert session.email == "oliver@example.com"


def test_validate_session_invalid_token(auth_db):
    from app.auth.session import validate_session
    session = validate_session(auth_db, "not-a-real-token")
    assert session is None


def test_expire_session_invalidates(auth_db):
    from app.auth.session import create_session, expire_session, validate_session
    token = create_session(auth_db, "petra@example.com")
    expire_session(auth_db, token)
    assert validate_session(auth_db, token) is None
```

- [ ] **Step 2: Run to confirm they fail**

```
pytest tests/test_auth.py -k "session" -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.auth.session'`

- [ ] **Step 3: Create `app/auth/session.py`**

```python
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
```

- [ ] **Step 4: Run session tests to confirm they pass**

```
pytest tests/test_auth.py -k "session" -v
```

Expected: All 4 session tests PASS.

- [ ] **Step 5: Run the full auth test suite**

```
pytest tests/test_auth.py -v
```

Expected: All tests PASS (should be 21+ tests).

- [ ] **Step 6: Commit**

```bash
git add app/auth/session.py tests/test_auth.py
git commit -m "[PHASE-01] add: session module - create_session, validate_session, expire_session"
```

---

## Task 6: Auth `__init__.py` Exports

**Files:**
- Modify: `app/auth/__init__.py`

- [ ] **Step 1: Write `app/auth/__init__.py`**

```python
from .otp import generate_otp, send_otp_email, verify_otp, issue_otp
from .session import create_session, validate_session, expire_session

__all__ = [
    "generate_otp",
    "send_otp_email",
    "verify_otp",
    "issue_otp",
    "create_session",
    "validate_session",
    "expire_session",
]
```

- [ ] **Step 2: Verify import works**

```
python -c "from app.auth import generate_otp, create_session; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/auth/__init__.py
git commit -m "[PHASE-01] add: auth __init__ exports"
```

---

## Task 7: Streamlit Login Page

**Files:**
- Create: `app/ui/pages/0_Login.py`

The login page has two states:
1. **Email entry**: User types email, clicks "Send Code"
2. **OTP entry**: User types 6-digit code, clicks "Verify"

Session token is stored in `st.session_state["auth_token"]`. Other pages check for it.

- [ ] **Step 1: Create `app/ui/pages/0_Login.py`**

```python
import os
from pathlib import Path

import streamlit as st

from app.state.db import AuthDB
from app.auth.otp import issue_otp, send_otp_email, verify_otp
from app.auth.session import create_session

DB_PATH = Path(os.getenv("DB_PATH", "resume_builder.db"))


def _get_auth_db() -> AuthDB:
    if "auth_db" not in st.session_state:
        st.session_state["auth_db"] = AuthDB(DB_PATH)
    return st.session_state["auth_db"]


def _is_logged_in() -> bool:
    token = st.session_state.get("auth_token")
    if not token:
        return False
    db = _get_auth_db()
    session = db.get_session(token)
    return session is not None


def render_email_step():
    st.subheader("Sign In")
    email = st.text_input("Email address", key="login_email")
    if st.button("Send Code"):
        if not email or "@" not in email:
            st.error("Enter a valid email address.")
            return
        db = _get_auth_db()
        otp_code = issue_otp(db, email)
        sent = send_otp_email(email, otp_code)
        if sent:
            st.session_state["otp_email"] = email
            st.session_state["otp_step"] = True
            st.success(f"Code sent to {email}. Check your inbox.")
            st.rerun()
        else:
            st.error("Failed to send code. Check SMTP configuration.")


def render_otp_step():
    email = st.session_state.get("otp_email", "")
    st.subheader("Enter Your Code")
    st.caption(f"Code sent to: {email}")
    code = st.text_input("6-digit code", max_chars=6, key="otp_code_input")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Verify"):
            if not code or not code.isdigit() or len(code) != 6:
                st.error("Enter the 6-digit code from your email.")
                return
            db = _get_auth_db()
            if verify_otp(db, email, code):
                token = create_session(db, email)
                st.session_state["auth_token"] = token
                st.session_state["auth_email"] = email
                st.session_state.pop("otp_step", None)
                st.session_state.pop("otp_email", None)
                st.success("Signed in successfully!")
                st.rerun()
            else:
                st.error("Invalid or expired code. Request a new one.")
    with col2:
        if st.button("Use a different email"):
            st.session_state.pop("otp_step", None)
            st.session_state.pop("otp_email", None)
            st.rerun()


def main():
    st.set_page_config(page_title="JobOS - Sign In", page_icon="🔐")
    st.title("JobOS Resume Builder")

    if _is_logged_in():
        email = st.session_state.get("auth_email", "")
        st.success(f"Signed in as {email}")
        if st.button("Sign Out"):
            db = _get_auth_db()
            token = st.session_state.get("auth_token")
            if token:
                db.expire_session(token)
            for key in ("auth_token", "auth_email", "otp_step", "otp_email"):
                st.session_state.pop(key, None)
            st.rerun()
        return

    if st.session_state.get("otp_step"):
        render_otp_step()
    else:
        render_email_step()


main()
```

- [ ] **Step 2: Manual smoke test** (no automated test for Streamlit rendering)

Verify imports work without launching Streamlit:

```
python -c "import app.ui.pages.0_Login" 2>&1 || python -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('login', 'app/ui/pages/0_Login.py')
print('Import OK' if spec else 'FAIL')
"
```

Actually just check for syntax errors:

```
python -m py_compile app/ui/pages/0_Login.py && echo "Syntax OK"
```

Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add app/ui/pages/0_Login.py
git commit -m "[PHASE-01] add: Streamlit OTP login page"
```

---

## Task 8: Full Test Suite + Generate Tests

- [ ] **Step 1: Run all tests**

```
pytest -v 2>&1 | tail -30
```

Expected: v1 baseline (82 tests) + new auth tests all PASS. Zero failures.

- [ ] **Step 2: Run /generate-tests for auth module**

```
/generate-tests app/auth/
```

Incorporate any additional tests produced.

- [ ] **Step 3: Final test run**

```
pytest tests/test_auth.py -v
```

Show full output.

---

## Completion Protocol

After all tasks pass:

**Step A** — Full `pytest -v` output
**Step B** — CLAUDE.md spec compliance checklist
**Step C** — `/requesting-code-review` subagent
**Step D** — Walkthrough + `git diff --staged`
**Step E** — STOP and wait for commit approval
**Step F** — Commit + final branch push

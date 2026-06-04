# Phase 10: Payment Gate + Locked PDF Download — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate the final resume PDF behind a Razorpay Payment Link; watermark the preview before payment; verify server-side on callback; serve clean PDF only after confirmation.

**Architecture:** Payment Links API creates a hosted Razorpay URL; user pays there and is redirected back to `6_Download.py` with query params; Python verifies HMAC signature via SDK; DB is updated to PAYMENT_CONFIRMED; clean PDF is served via `st.download_button`.

**Tech Stack:** Python 3.13, razorpay SDK, PyMuPDF (fitz), Streamlit 1.42, SQLite WAL, python-dotenv

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `requirements.txt` | Add `razorpay>=1.3.0` |
| Modify | `app/config.py` | Add payment env vars |
| Modify | `app/state/models.py` | Add `payment_link_id`, `payment_id` to `SubmissionRecord` |
| Modify | `app/state/db.py` | Migrations + `_SUBMISSION_UPDATE_COLUMNS` |
| Create | `app/payment/__init__.py` | Export `get_payment_provider` |
| Create | `app/payment/provider.py` | `OrderResult`, `PaymentProvider` ABC, factory |
| Create | `app/payment/razorpay_adapter.py` | Razorpay Payment Links adapter |
| Create | `app/payment/stripe_adapter.py` | Stripe stub (NotImplementedError) |
| Create | `app/payment/watermark.py` | In-memory PDF watermark via PyMuPDF |
| Create | `app/ui/pages/6_Download.py` | Download page — payment gate + PDF serve |
| Create | `tests/test_payment.py` | All payment module tests |

---

## Task 1: Add razorpay to requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Read requirements.txt**

Confirm current contents before editing.

- [ ] **Step 2: Add razorpay**

Edit `requirements.txt` — append after `python-dotenv==1.0.1`:

```
razorpay>=1.3.0
```

Final file should read:
```
streamlit==1.42.0
anthropic>=0.40.0
pdfplumber==0.11.5
PyMuPDF==1.25.3
reportlab==4.2.5
duckduckgo-search==7.5.0
python-dotenv==1.0.1
cryptography==44.0.1
pytest==8.3.4
razorpay>=1.3.0
```

- [ ] **Step 3: Install it**

```bash
pip install razorpay
```

Expected: `Successfully installed razorpay-x.y.z`

- [ ] **Step 4: Verify import**

```bash
python -c "import razorpay; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "[PHASE-10] add: razorpay SDK to requirements"
```

---

## Task 2: Extend config.py with payment env vars

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Read app/config.py**

Confirm current fields — it ends at `SESSION_EXPIRY_HOURS`.

- [ ] **Step 2: Add payment fields**

Inside the `Config` dataclass, after `SESSION_EXPIRY_HOURS`, add:

```python
    # Payment
    PAYMENT_PROVIDER: str = os.getenv("PAYMENT_PROVIDER", "razorpay")
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    RESUME_DOWNLOAD_PRICE_INR: int = int(os.getenv("RESUME_DOWNLOAD_PRICE_INR", "99"))
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:8501")
```

- [ ] **Step 3: Update .env with test keys**

In `.env` (never commit this file), add or update:
```
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=rzp_test_SffTnEmbCanxvN
RAZORPAY_KEY_SECRET=ICH7kxnjFvZBWN2BAExtokYi
RESUME_DOWNLOAD_PRICE_INR=99
APP_BASE_URL=http://localhost:8501
```

- [ ] **Step 4: Update .env.example with placeholder**

In `.env.example`, the payment block should read (keys already present there, just ensure `APP_BASE_URL` is added):
```
APP_BASE_URL=http://localhost:8501
```

- [ ] **Step 5: Verify config loads**

```bash
python -c "from app.config import config; print(config.PAYMENT_PROVIDER, config.RESUME_DOWNLOAD_PRICE_INR)"
```

Expected: `razorpay 99`

- [ ] **Step 6: Commit**

```bash
git add app/config.py .env.example
git commit -m "[PHASE-10] add: payment config fields (PAYMENT_PROVIDER, RAZORPAY_*, APP_BASE_URL)"
```

---

## Task 3: DB layer — SubmissionRecord + migrations

**Files:**
- Modify: `app/state/models.py`
- Modify: `app/state/db.py`
- Test: `tests/test_payment.py`

- [ ] **Step 1: Write failing tests for DB changes**

Create `tests/test_payment.py`:

```python
import sqlite3
import pytest
from pathlib import Path

from app.state.db import SubmissionsDB
from app.state.models import SubmissionRecord, SubmissionStatus


@pytest.fixture
def subs_db(tmp_path):
    db_path = tmp_path / "test.db"
    return SubmissionsDB(db_path)


@pytest.fixture
def submission_id(subs_db):
    subs_db._get_connection().__enter__().execute(
        "INSERT INTO users (email) VALUES (?)", ("u@test.com",)
    )
    # Create user then submission
    from app.state.db import AuthDB
    return None  # placeholder — see step below


# ── DB migration tests ────────────────────────────────────────────────────────

def test_payment_columns_exist_after_init(tmp_path):
    db_path = tmp_path / "test.db"
    db = SubmissionsDB(db_path)
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(submissions)")}
    conn.close()
    assert "payment_link_id" in cols
    assert "payment_id" in cols


def test_payment_migration_idempotent(tmp_path):
    """Calling _init_db twice must not raise."""
    db_path = tmp_path / "test.db"
    db = SubmissionsDB(db_path)
    db._init_db()  # second call — must not fail


def test_update_submission_payment_link_id(tmp_path):
    from app.state.db import AuthDB
    db_path = tmp_path / "test.db"
    auth_db = AuthDB(db_path)
    subs_db = SubmissionsDB(db_path)

    user_id = auth_db.create_user("x@test.com")
    sub_id = subs_db.create_submission(user_id, "tok123")

    subs_db.update_submission(sub_id, {"payment_link_id": "plink_abc"})
    rec = subs_db.get_submission(sub_id)
    assert rec.payment_link_id == "plink_abc"


def test_update_submission_payment_id(tmp_path):
    from app.state.db import AuthDB
    db_path = tmp_path / "test.db"
    auth_db = AuthDB(db_path)
    subs_db = SubmissionsDB(db_path)

    user_id = auth_db.create_user("y@test.com")
    sub_id = subs_db.create_submission(user_id, "tok456")

    subs_db.update_submission(sub_id, {"payment_id": "pay_xyz"})
    rec = subs_db.get_submission(sub_id)
    assert rec.payment_id == "pay_xyz"


def test_submission_record_has_payment_fields():
    rec = SubmissionRecord(
        id=1, user_id=1, session_token="t", resume_raw_text=None,
        resume_fields_json=None, resume_photo_path=None,
        jd_raw_text=None, jd_fields_json=None, ats_score_json=None,
        status="PENDING", revision_count=0, error_message=None,
        created_at=None, updated_at=None,
        payment_link_id="plink_abc", payment_id="pay_xyz",
    )
    assert rec.payment_link_id == "plink_abc"
    assert rec.payment_id == "pay_xyz"
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_payment.py -v -k "payment_columns or payment_migration or payment_link_id or payment_id or payment_fields"
```

Expected: multiple FAILs — columns don't exist, `SubmissionRecord` missing fields.

- [ ] **Step 3: Modify SubmissionRecord in models.py**

In `app/state/models.py`, the `SubmissionRecord` dataclass currently ends with:
```python
    llm_output_json: Optional[str] = None
    output_pdf_path: Optional[str] = None
```

Add two new optional fields after `output_pdf_path`:
```python
    payment_link_id: Optional[str] = None
    payment_id: Optional[str] = None
```

- [ ] **Step 4: Add DB migrations in db.py**

In `app/state/db.py`, `SubmissionsDB._init_db()`, the existing migration block reads:
```python
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(submissions)")}
            if "ats_score_json" not in existing_cols:
                conn.execute("ALTER TABLE submissions ADD COLUMN ats_score_json TEXT")
            if "llm_output_json" not in existing_cols:
                conn.execute("ALTER TABLE submissions ADD COLUMN llm_output_json TEXT")
            if "output_pdf_path" not in existing_cols:
                conn.execute("ALTER TABLE submissions ADD COLUMN output_pdf_path TEXT")
            conn.commit()
```

Add two new migration lines before `conn.commit()`:
```python
            if "payment_link_id" not in existing_cols:
                conn.execute("ALTER TABLE submissions ADD COLUMN payment_link_id TEXT")
            if "payment_id" not in existing_cols:
                conn.execute("ALTER TABLE submissions ADD COLUMN payment_id TEXT")
```

- [ ] **Step 5: Add new columns to _SUBMISSION_UPDATE_COLUMNS**

In `app/state/db.py`, `SubmissionsDB._SUBMISSION_UPDATE_COLUMNS` currently reads:
```python
    _SUBMISSION_UPDATE_COLUMNS = frozenset({
        "resume_raw_text", "resume_fields_json", "resume_photo_path",
        "jd_raw_text", "jd_fields_json", "ats_score_json",
        "llm_output_json", "output_pdf_path",
        "revision_count", "error_message",
    })
```

Replace with:
```python
    _SUBMISSION_UPDATE_COLUMNS = frozenset({
        "resume_raw_text", "resume_fields_json", "resume_photo_path",
        "jd_raw_text", "jd_fields_json", "ats_score_json",
        "llm_output_json", "output_pdf_path",
        "revision_count", "error_message",
        "payment_link_id", "payment_id",
    })
```

- [ ] **Step 6: Run tests — expect pass**

```bash
pytest tests/test_payment.py -v -k "payment_columns or payment_migration or payment_link_id or payment_id or payment_fields"
```

Expected: all PASS.

- [ ] **Step 7: Run full test suite — no regressions**

```bash
pytest -v --tb=short 2>&1 | tail -20
```

Expected: all previously passing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add app/state/models.py app/state/db.py tests/test_payment.py
git commit -m "[PHASE-10] add: payment_link_id + payment_id columns to SubmissionsDB + SubmissionRecord"
```

---

## Task 4: Payment provider interface + factory

**Files:**
- Create: `app/payment/__init__.py`
- Create: `app/payment/provider.py`
- Test: `tests/test_payment.py`

- [ ] **Step 1: Write failing tests for factory**

Append to `tests/test_payment.py`:

```python
# ── Provider factory tests ────────────────────────────────────────────────────

def test_factory_returns_razorpay_adapter(monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_fake")
    from app.payment.provider import get_payment_provider
    from app.payment.razorpay_adapter import RazorpayAdapter
    import importlib, app.payment.provider
    importlib.reload(app.payment.provider)
    provider = app.payment.provider.get_payment_provider()
    assert isinstance(provider, RazorpayAdapter)


def test_factory_raises_on_unknown_provider(monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "nonexistent_pay")
    import importlib, app.payment.provider
    importlib.reload(app.payment.provider)
    with pytest.raises(ValueError, match="nonexistent_pay"):
        app.payment.provider.get_payment_provider()


def test_order_result_fields():
    from app.payment.provider import OrderResult
    r = OrderResult(link_id="plink_abc", short_url="https://rzp.io/i/abc")
    assert r.link_id == "plink_abc"
    assert r.short_url == "https://rzp.io/i/abc"
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_payment.py -v -k "factory or order_result"
```

Expected: FAIL — `app.payment.provider` does not exist.

- [ ] **Step 3: Create app/payment/__init__.py**

```python
from .provider import get_payment_provider, OrderResult

__all__ = ["get_payment_provider", "OrderResult"]
```

- [ ] **Step 4: Create app/payment/provider.py**

```python
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OrderResult:
    link_id: str    # Razorpay payment_link_id — store in DB
    short_url: str  # rzp.io/i/xxx — open in browser


class PaymentProvider(ABC):
    @abstractmethod
    def create_order(
        self,
        amount_paise: int,
        currency: str,
        reference_id: str,
        callback_url: str,
    ) -> OrderResult:
        """Create a hosted payment link. Returns link_id and short_url."""

    @abstractmethod
    def verify_payment(self, params: dict) -> bool:
        """Verify payment callback params. Returns True if signature valid.

        Expected param keys (Razorpay):
            razorpay_payment_id, razorpay_payment_link_id,
            razorpay_payment_link_reference_id,
            razorpay_payment_link_status, razorpay_signature
        """


def get_payment_provider() -> PaymentProvider:
    """Factory: reads PAYMENT_PROVIDER env var, returns the correct adapter."""
    provider = os.getenv("PAYMENT_PROVIDER", "razorpay").lower()
    if provider == "razorpay":
        from .razorpay_adapter import RazorpayAdapter
        return RazorpayAdapter()
    if provider == "stripe":
        from .stripe_adapter import StripeAdapter
        return StripeAdapter()
    raise ValueError(f"Unknown PAYMENT_PROVIDER: {provider!r}. Expected 'razorpay' or 'stripe'.")
```

- [ ] **Step 5: Run tests — expect pass**

```bash
pytest tests/test_payment.py -v -k "factory or order_result"
```

Note: `test_factory_returns_razorpay_adapter` will still fail until Task 5 creates `RazorpayAdapter`. The `test_order_result_fields` and `test_factory_raises_on_unknown_provider` should pass now.

- [ ] **Step 6: Commit**

```bash
git add app/payment/__init__.py app/payment/provider.py tests/test_payment.py
git commit -m "[PHASE-10] add: PaymentProvider ABC + OrderResult + factory skeleton"
```

---

## Task 5: Razorpay adapter

**Files:**
- Create: `app/payment/razorpay_adapter.py`
- Test: `tests/test_payment.py`

- [ ] **Step 1: Write failing tests for Razorpay adapter**

Append to `tests/test_payment.py`:

```python
# ── Razorpay adapter tests ────────────────────────────────────────────────────

from unittest.mock import MagicMock, patch


def test_razorpay_create_order_returns_order_result(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_fake")

    mock_client = MagicMock()
    mock_client.payment_link.create.return_value = {
        "id": "plink_TestAbc123",
        "short_url": "https://rzp.io/i/TestAbc",
    }

    with patch("app.payment.razorpay_adapter.razorpay.Client", return_value=mock_client):
        from app.payment.razorpay_adapter import RazorpayAdapter
        import importlib, app.payment.razorpay_adapter
        importlib.reload(app.payment.razorpay_adapter)
        adapter = app.payment.razorpay_adapter.RazorpayAdapter()
        adapter._client = mock_client

        result = adapter.create_order(
            amount_paise=9900,
            currency="INR",
            reference_id="sub_42",
            callback_url="http://localhost:8501/6_Download?submission_id=42",
        )

    assert result.link_id == "plink_TestAbc123"
    assert result.short_url == "https://rzp.io/i/TestAbc"
    mock_client.payment_link.create.assert_called_once()
    call_data = mock_client.payment_link.create.call_args[0][0]
    assert call_data["amount"] == 9900
    assert call_data["currency"] == "INR"
    assert call_data["reference_id"] == "sub_42"
    assert "callback_url" in call_data


def test_razorpay_verify_payment_valid_signature(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_fake")

    mock_client = MagicMock()
    mock_client.utility.verify_payment_link_signature.return_value = None  # no exception = valid

    from app.payment.razorpay_adapter import RazorpayAdapter
    adapter = RazorpayAdapter()
    adapter._client = mock_client

    params = {
        "razorpay_payment_id": "pay_abc",
        "razorpay_payment_link_id": "plink_abc",
        "razorpay_payment_link_reference_id": "sub_42",
        "razorpay_payment_link_status": "paid",
        "razorpay_signature": "sig_abc",
    }
    assert adapter.verify_payment(params) is True
    mock_client.utility.verify_payment_link_signature.assert_called_once_with({
        "payment_link_id": "plink_abc",
        "payment_link_reference_id": "sub_42",
        "payment_link_status": "paid",
        "razorpay_payment_id": "pay_abc",
        "razorpay_signature": "sig_abc",
    })


def test_razorpay_verify_payment_invalid_signature(monkeypatch):
    import razorpay.errors

    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_fake")

    mock_client = MagicMock()
    mock_client.utility.verify_payment_link_signature.side_effect = (
        razorpay.errors.SignatureVerificationError("bad sig", "razorpay_signature")
    )

    from app.payment.razorpay_adapter import RazorpayAdapter
    adapter = RazorpayAdapter()
    adapter._client = mock_client

    params = {
        "razorpay_payment_id": "pay_bad",
        "razorpay_payment_link_id": "plink_bad",
        "razorpay_payment_link_reference_id": "sub_42",
        "razorpay_payment_link_status": "paid",
        "razorpay_signature": "bad_sig",
    }
    assert adapter.verify_payment(params) is False


def test_razorpay_create_order_passes_correct_amount(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_fake")

    mock_client = MagicMock()
    mock_client.payment_link.create.return_value = {
        "id": "plink_X",
        "short_url": "https://rzp.io/i/X",
    }

    from app.payment.razorpay_adapter import RazorpayAdapter
    adapter = RazorpayAdapter()
    adapter._client = mock_client

    adapter.create_order(5000, "INR", "ref_1", "http://cb.url/")
    call_data = mock_client.payment_link.create.call_args[0][0]
    assert call_data["amount"] == 5000  # paise passed through unchanged
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_payment.py -v -k "razorpay_create or razorpay_verify"
```

Expected: FAIL — `app.payment.razorpay_adapter` does not exist.

- [ ] **Step 3: Create app/payment/razorpay_adapter.py**

```python
import os
import logging
import razorpay
import razorpay.errors

from .provider import PaymentProvider, OrderResult

logger = logging.getLogger(__name__)


class RazorpayAdapter(PaymentProvider):
    """Razorpay Payment Links implementation."""

    def __init__(self):
        key_id = os.getenv("RAZORPAY_KEY_ID", "")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        self._client = razorpay.Client(auth=(key_id, key_secret))

    def create_order(
        self,
        amount_paise: int,
        currency: str,
        reference_id: str,
        callback_url: str,
    ) -> OrderResult:
        """Create a Razorpay Payment Link. Returns link_id and hosted short_url."""
        data = {
            "amount": amount_paise,
            "currency": currency,
            "reference_id": reference_id,
            "callback_url": callback_url,
            "callback_method": "get",
        }
        response = self._client.payment_link.create(data)
        logger.info("Created Razorpay payment link %s", response["id"])
        return OrderResult(link_id=response["id"], short_url=response["short_url"])

    def verify_payment(self, params: dict) -> bool:
        """Verify Razorpay callback signature. Returns True if valid, False if tampered.

        params keys expected (from st.query_params after redirect):
            razorpay_payment_id, razorpay_payment_link_id,
            razorpay_payment_link_reference_id,
            razorpay_payment_link_status, razorpay_signature
        """
        sdk_params = {
            "payment_link_id": params.get("razorpay_payment_link_id"),
            "payment_link_reference_id": params.get("razorpay_payment_link_reference_id"),
            "payment_link_status": params.get("razorpay_payment_link_status"),
            "razorpay_payment_id": params.get("razorpay_payment_id"),
            "razorpay_signature": params.get("razorpay_signature"),
        }
        try:
            self._client.utility.verify_payment_link_signature(sdk_params)
            logger.info("Payment verified: %s", params.get("razorpay_payment_id"))
            return True
        except razorpay.errors.SignatureVerificationError:
            logger.warning("Payment signature verification failed for params: %s", params)
            return False
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_payment.py -v -k "razorpay_create or razorpay_verify or factory_returns_razorpay"
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/payment/razorpay_adapter.py tests/test_payment.py
git commit -m "[PHASE-10] add: RazorpayAdapter with Payment Links + signature verify"
```

---

## Task 6: Stripe stub

**Files:**
- Create: `app/payment/stripe_adapter.py`
- Test: `tests/test_payment.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_payment.py`:

```python
# ── Stripe stub tests ─────────────────────────────────────────────────────────

def test_stripe_create_order_raises_not_implemented():
    from app.payment.stripe_adapter import StripeAdapter
    adapter = StripeAdapter()
    with pytest.raises(NotImplementedError, match="Stripe"):
        adapter.create_order(9900, "INR", "ref_1", "http://cb.url/")


def test_stripe_verify_payment_raises_not_implemented():
    from app.payment.stripe_adapter import StripeAdapter
    adapter = StripeAdapter()
    with pytest.raises(NotImplementedError, match="Stripe"):
        adapter.verify_payment({})


def test_factory_returns_stripe_stub(monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe")
    import importlib, app.payment.provider
    importlib.reload(app.payment.provider)
    from app.payment.stripe_adapter import StripeAdapter
    provider = app.payment.provider.get_payment_provider()
    assert isinstance(provider, StripeAdapter)
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_payment.py -v -k "stripe"
```

Expected: FAIL — `app.payment.stripe_adapter` does not exist.

- [ ] **Step 3: Create app/payment/stripe_adapter.py**

```python
from .provider import PaymentProvider, OrderResult


class StripeAdapter(PaymentProvider):
    """Stripe payment adapter — not yet implemented."""

    def create_order(
        self,
        amount_paise: int,
        currency: str,
        reference_id: str,
        callback_url: str,
    ) -> OrderResult:
        raise NotImplementedError(
            "Stripe adapter not implemented. Set PAYMENT_PROVIDER=razorpay."
        )

    def verify_payment(self, params: dict) -> bool:
        raise NotImplementedError(
            "Stripe adapter not implemented. Set PAYMENT_PROVIDER=razorpay."
        )
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_payment.py -v -k "stripe"
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/payment/stripe_adapter.py tests/test_payment.py
git commit -m "[PHASE-10] add: StripeAdapter stub (NotImplementedError)"
```

---

## Task 7: Watermark helper

**Files:**
- Create: `app/payment/watermark.py`
- Test: `tests/test_payment.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_payment.py`:

```python
# ── Watermark tests ───────────────────────────────────────────────────────────

import fitz  # PyMuPDF
import tempfile


def _make_minimal_pdf(path: Path) -> None:
    """Create a one-page PDF with 'Hello' text for testing."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(100, 100), "Hello Resume", fontsize=14)
    doc.save(str(path))
    doc.close()


def test_watermark_returns_bytes(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _make_minimal_pdf(pdf_path)
    from app.payment.watermark import watermark_pdf_bytes
    result = watermark_pdf_bytes(pdf_path)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_watermark_does_not_modify_source(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _make_minimal_pdf(pdf_path)
    original_bytes = pdf_path.read_bytes()
    from app.payment.watermark import watermark_pdf_bytes
    watermark_pdf_bytes(pdf_path)
    assert pdf_path.read_bytes() == original_bytes


def test_watermark_output_is_valid_pdf(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _make_minimal_pdf(pdf_path)
    from app.payment.watermark import watermark_pdf_bytes
    result = watermark_pdf_bytes(pdf_path)
    # Valid PDF starts with %PDF
    assert result[:4] == b"%PDF"


def test_watermark_contains_preview_text(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _make_minimal_pdf(pdf_path)
    from app.payment.watermark import watermark_pdf_bytes
    result = watermark_pdf_bytes(pdf_path)
    # Open the watermarked bytes and check for PREVIEW text
    doc = fitz.open(stream=result, filetype="pdf")
    page = doc[0]
    text = page.get_text()
    doc.close()
    assert "PREVIEW" in text
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_payment.py -v -k "watermark"
```

Expected: FAIL — `app.payment.watermark` does not exist.

- [ ] **Step 3: Create app/payment/watermark.py**

```python
import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def watermark_pdf_bytes(pdf_path: Path) -> bytes:
    """Return PDF bytes with a PREVIEW watermark on every page.

    Does NOT write any file. The clean PDF at pdf_path is never modified.
    Uses PyMuPDF (fitz) to insert diagonal grey text overlay.
    """
    doc = fitz.open(str(pdf_path))
    for page in doc:
        rect = page.rect
        # Place watermark diagonally across the centre of the page
        point = fitz.Point(rect.width * 0.15, rect.height * 0.65)
        page.insert_text(
            point,
            "PREVIEW",
            fontsize=80,
            color=(0.75, 0.75, 0.75),  # light grey — simulates low opacity
            rotate=45,
            overlay=True,
        )
    result = doc.tobytes()
    doc.close()
    logger.debug("Watermarked PDF from %s (%d bytes)", pdf_path, len(result))
    return result
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_payment.py -v -k "watermark"
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/payment/watermark.py tests/test_payment.py
git commit -m "[PHASE-10] add: watermark_pdf_bytes helper (PyMuPDF, in-memory, source untouched)"
```

---

## Task 8: Download page helper functions

**Files:**
- Create: `app/ui/pages/6_Download.py` (helper functions only first)
- Test: `tests/test_payment.py`

These pure functions are extracted from the page so they can be tested without Streamlit.

- [ ] **Step 1: Write failing tests for page helpers**

Append to `tests/test_payment.py`:

```python
# ── 6_Download.py helper tests ────────────────────────────────────────────────

def test_build_callback_url_basic():
    from app.ui.pages._download_helpers import build_callback_url
    url = build_callback_url("http://localhost:8501", 42)
    assert url == "http://localhost:8501/6_Download?submission_id=42"


def test_build_callback_url_no_trailing_slash():
    from app.ui.pages._download_helpers import build_callback_url
    url = build_callback_url("http://localhost:8501/", 7)
    assert url == "http://localhost:8501/6_Download?submission_id=7"


def test_has_razorpay_callback_true():
    from app.ui.pages._download_helpers import has_razorpay_callback
    params = {
        "razorpay_payment_id": "pay_abc",
        "razorpay_payment_link_id": "plink_abc",
        "razorpay_payment_link_reference_id": "sub_42",
        "razorpay_payment_link_status": "paid",
        "razorpay_signature": "sig_abc",
    }
    assert has_razorpay_callback(params) is True


def test_has_razorpay_callback_false_when_empty():
    from app.ui.pages._download_helpers import has_razorpay_callback
    assert has_razorpay_callback({}) is False


def test_has_razorpay_callback_false_when_partial():
    from app.ui.pages._download_helpers import has_razorpay_callback
    # Missing razorpay_signature
    params = {
        "razorpay_payment_id": "pay_abc",
        "razorpay_payment_link_id": "plink_abc",
    }
    assert has_razorpay_callback(params) is False


def test_price_paise_converts_correctly(monkeypatch):
    monkeypatch.setenv("RESUME_DOWNLOAD_PRICE_INR", "149")
    from app.ui.pages._download_helpers import get_price_paise
    import importlib, app.ui.pages._download_helpers
    importlib.reload(app.ui.pages._download_helpers)
    assert app.ui.pages._download_helpers.get_price_paise() == 14900
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_payment.py -v -k "callback_url or razorpay_callback or price_paise"
```

Expected: FAIL — `_download_helpers` does not exist.

- [ ] **Step 3: Create app/ui/pages/_download_helpers.py**

```python
"""
Pure helper functions for 6_Download.py — no Streamlit calls, fully testable.
"""
import os


_RAZORPAY_CALLBACK_KEYS = frozenset({
    "razorpay_payment_id",
    "razorpay_payment_link_id",
    "razorpay_payment_link_reference_id",
    "razorpay_payment_link_status",
    "razorpay_signature",
})


def build_callback_url(base_url: str, submission_id: int) -> str:
    """Build the Razorpay callback URL for this submission.

    Razorpay appends its own params to this URL on redirect.
    """
    base = base_url.rstrip("/")
    return f"{base}/6_Download?submission_id={submission_id}"


def has_razorpay_callback(query_params: dict) -> bool:
    """Return True if all Razorpay callback params are present in query_params."""
    return _RAZORPAY_CALLBACK_KEYS.issubset(query_params.keys())


def get_price_paise() -> int:
    """Return price in paise (INR × 100) from env var RESUME_DOWNLOAD_PRICE_INR."""
    return int(os.getenv("RESUME_DOWNLOAD_PRICE_INR", "99")) * 100
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_payment.py -v -k "callback_url or razorpay_callback or price_paise"
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ui/pages/_download_helpers.py tests/test_payment.py
git commit -m "[PHASE-10] add: _download_helpers (build_callback_url, has_razorpay_callback, get_price_paise)"
```

---

## Task 9: 6_Download.py — full Streamlit page

**Files:**
- Modify: `app/ui/pages/6_Download.py` (create full page)

No Streamlit unit tests — the page render functions call `st.*` throughout. The helpers are already tested in Task 8.

- [ ] **Step 1: Create app/ui/pages/6_Download.py**

```python
"""
Phase 10 - Download Page
Payment gate: watermarked preview before payment, clean PDF after Razorpay verification.
"""
import logging
import os
from pathlib import Path

import streamlit as st

from app.payment.provider import get_payment_provider
from app.payment.watermark import watermark_pdf_bytes
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionRecord, SubmissionStatus
from app.ui.pages._download_helpers import (
    build_callback_url,
    get_price_paise,
    has_razorpay_callback,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8501")


# ── DB helpers (session-cached) ────────────────────────────────────────────────

def _get_auth_db() -> AuthDB:
    if "auth_db" not in st.session_state:
        st.session_state["auth_db"] = AuthDB(DB_PATH)
    return st.session_state["auth_db"]


def _get_subs_db() -> SubmissionsDB:
    if "subs_db" not in st.session_state:
        st.session_state["subs_db"] = SubmissionsDB(DB_PATH)
    return st.session_state["subs_db"]


def _require_auth():
    """Returns (user_id, token) or calls st.stop()."""
    token = st.session_state.get("auth_token")
    if not token:
        st.warning("Please sign in first.")
        st.stop()
        return None, None
    session = _get_auth_db().get_session(token)
    if session is None:
        st.warning("Session expired. Please sign in again.")
        for key in ("auth_token", "auth_email"):
            st.session_state.pop(key, None)
        st.stop()
        return None, None
    return session.user_id, token


# ── Payment helpers ────────────────────────────────────────────────────────────

def _initiate_payment(submission: SubmissionRecord, subs_db: SubmissionsDB) -> str:
    """Create a Razorpay Payment Link, persist link_id, set PAYMENT_PENDING.

    Returns the short_url to open in browser.
    Raises on Razorpay API failure.
    """
    provider = get_payment_provider()
    callback_url = build_callback_url(APP_BASE_URL, submission.id)
    result = provider.create_order(
        amount_paise=get_price_paise(),
        currency="INR",
        reference_id=f"sub_{submission.id}",
        callback_url=callback_url,
    )
    subs_db.update_submission(submission.id, {"payment_link_id": result.link_id})
    subs_db.set_status(submission.id, SubmissionStatus.PAYMENT_PENDING)
    logger.info("Payment link created for submission %s: %s", submission.id, result.link_id)
    return result.short_url


def _verify_and_confirm(submission: SubmissionRecord, subs_db: SubmissionsDB, params: dict) -> bool:
    """Verify Razorpay callback params server-side.

    Security: also checks that the payment_link_id in the callback matches
    what is stored in the DB for this submission — prevents param substitution.

    Returns True if payment confirmed and DB updated, False on any failure.
    """
    stored_link_id = submission.payment_link_id
    callback_link_id = params.get("razorpay_payment_link_id")

    if not stored_link_id or stored_link_id != callback_link_id:
        logger.warning(
            "payment_link_id mismatch for submission %s: stored=%s callback=%s",
            submission.id, stored_link_id, callback_link_id,
        )
        return False

    provider = get_payment_provider()
    if not provider.verify_payment(params):
        logger.warning("Signature verification failed for submission %s", submission.id)
        return False

    payment_id = params.get("razorpay_payment_id", "")
    subs_db.update_submission(submission.id, {"payment_id": payment_id})
    subs_db.set_status(submission.id, SubmissionStatus.PAYMENT_CONFIRMED)
    logger.info("Payment confirmed for submission %s, payment_id=%s", submission.id, payment_id)
    return True


# ── Render helpers ─────────────────────────────────────────────────────────────

def _render_watermarked_preview(submission: SubmissionRecord) -> None:
    """Show watermarked PDF preview and Pay button."""
    price_inr = int(os.getenv("RESUME_DOWNLOAD_PRICE_INR", "99"))
    st.info(f"Your resume is ready. Pay ₹{price_inr} to download the clean PDF.")

    pdf_path = Path(submission.output_pdf_path or "")
    if pdf_path.exists():
        watermarked = watermark_pdf_bytes(pdf_path)
        st.download_button(
            label="Preview (watermarked)",
            data=watermarked,
            file_name="resume_preview.pdf",
            mime="application/pdf",
            help="This is a PREVIEW. Pay below to get the clean version.",
        )

    st.markdown("---")
    st.subheader(f"Pay ₹{price_inr} to Download")


def _render_pay_button(submission: SubmissionRecord, subs_db: SubmissionsDB) -> None:
    """Render the Pay & Download button. Creates payment link on click."""
    price_inr = int(os.getenv("RESUME_DOWNLOAD_PRICE_INR", "99"))
    if st.button(f"Pay ₹{price_inr} & Download", type="primary", use_container_width=True):
        with st.spinner("Creating secure payment link..."):
            try:
                short_url = _initiate_payment(submission, subs_db)
                st.session_state["payment_short_url"] = short_url
            except Exception as e:
                logger.error("Failed to create payment link for submission %s: %s", submission.id, e)
                st.error(f"Payment setup failed: {e}. Please try again.")
                return

    short_url = st.session_state.get("payment_short_url")
    if short_url:
        st.link_button("Open Payment Page", short_url, use_container_width=True)
        st.caption("You will be redirected back here after payment.")


def _render_clean_download(submission: SubmissionRecord, subs_db: SubmissionsDB) -> None:
    """Serve the clean PDF and set status to DOWNLOADED."""
    st.success("Payment confirmed! Your resume is ready.")
    pdf_path = Path(submission.output_pdf_path or "")
    if not pdf_path.exists():
        st.error("PDF file not found. Please contact support.")
        return

    pdf_bytes = pdf_path.read_bytes()
    clicked = st.download_button(
        label="Download Resume (PDF)",
        data=pdf_bytes,
        file_name="resume.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )
    if clicked and submission.status != SubmissionStatus.DOWNLOADED.value:
        subs_db.set_status(submission.id, SubmissionStatus.DOWNLOADED)
        logger.info("Submission %s marked DOWNLOADED", submission.id)


# ── Page entry point ───────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="JobOS - Download", page_icon="⬇️")
    st.title("Download Your Resume")

    _user_id, _token = _require_auth()
    if not _token:
        return

    subs_db = _get_subs_db()

    sub_id = st.session_state.get("current_submission_id")
    if not sub_id:
        st.error("No active submission. Please upload your resume first.")
        if st.button("Go to Upload"):
            st.switch_page("pages/1_Upload.py")
        return

    submission = subs_db.get_submission(int(sub_id))
    if submission is None:
        st.error(f"Submission #{sub_id} not found.")
        return

    # ── Detect Razorpay callback (redirect back from payment page) ─────────
    query_params = dict(st.query_params)
    callback_sub_id = query_params.get("submission_id")

    if (
        has_razorpay_callback(query_params)
        and submission.status == SubmissionStatus.PAYMENT_PENDING.value
        and str(callback_sub_id) == str(sub_id)
    ):
        with st.spinner("Verifying payment..."):
            confirmed = _verify_and_confirm(submission, subs_db, query_params)
        if confirmed:
            st.query_params.clear()  # clean up URL
            st.rerun()
        else:
            st.error("Payment verification failed. Please try again or contact support.")
            return

    # Reload after possible status change
    submission = subs_db.get_submission(int(sub_id))
    status = submission.status

    # ── Route by status ────────────────────────────────────────────────────
    if status == SubmissionStatus.ACCEPTED.value:
        _render_watermarked_preview(submission)
        _render_pay_button(submission, subs_db)

    elif status == SubmissionStatus.PAYMENT_PENDING.value:
        st.info("Payment pending. Complete payment to download your resume.")
        _render_pay_button(submission, subs_db)

    elif status in (
        SubmissionStatus.PAYMENT_CONFIRMED.value,
        SubmissionStatus.DOWNLOAD_READY.value,
        SubmissionStatus.DOWNLOADED.value,
    ):
        _render_clean_download(submission, subs_db)
        if status == SubmissionStatus.DOWNLOADED.value:
            st.caption("Already downloaded. You can download again above.")

    else:
        st.warning(f"Resume not ready for download yet. Current status: **{status}**")
        if st.button("← Back to Review"):
            st.switch_page("pages/3_Review.py")


main()
```

- [ ] **Step 2: Verify page imports cleanly**

```bash
python -c "import ast; ast.parse(open('app/ui/pages/6_Download.py').read()); print('syntax ok')"
```

Expected: `syntax ok`

- [ ] **Step 3: Commit**

```bash
git add app/ui/pages/6_Download.py
git commit -m "[PHASE-10] add: 6_Download.py — payment gate, watermark preview, Razorpay callback verify"
```

---

## Task 10: Full test run + checkpoint

**Files:** None modified — verification only.

- [ ] **Step 1: Run full test suite**

```bash
pytest -v --tb=short 2>&1 | tee /tmp/phase10_test_output.txt
```

Expected: all previously passing tests (329+) still pass, plus new payment tests.

- [ ] **Step 2: Count payment tests passing**

```bash
pytest tests/test_payment.py -v 2>&1 | tail -20
```

Expected: 18+ tests passing, 0 failures.

- [ ] **Step 3: Verify no hardcoded keys**

```bash
grep -r "rzp_test\|ICH7kx" app/ tests/
```

Expected: no output — keys must only exist in `.env` (which is gitignored).

- [ ] **Step 4: Verify .env is gitignored**

```bash
git status .env
```

Expected: `.env` does NOT appear in tracked files output.

- [ ] **Step 5: Commit checkpoint**

```bash
git add tests/test_payment.py
git commit -m "[PHASE-10] checkpoint: payment gate complete - all tests passing"
```

---

## Quick Reference: Status Flow for Phase 10

```
ACCEPTED
  → [user clicks Pay] → PAYMENT_PENDING   (payment_link_id stored)
  → [Razorpay callback verified] → PAYMENT_CONFIRMED  (payment_id stored)
  → [download button clicked] → DOWNLOADED
  → ERROR  (any failure)
```

## Env vars required in .env

```
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=<your test key id>
RAZORPAY_KEY_SECRET=<your test key secret>
RESUME_DOWNLOAD_PRICE_INR=99
APP_BASE_URL=http://localhost:8501
```

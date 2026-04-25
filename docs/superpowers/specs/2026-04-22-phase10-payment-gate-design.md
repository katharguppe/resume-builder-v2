# Phase 10: Payment Gate + Locked PDF Download — Design Spec
**Date:** 2026-04-22
**Branch:** feature/phase-02-upload-parse
**Status:** Approved

---

## 1. Overview

Phase 10 gates the final resume PDF download behind a Razorpay payment. Before payment the candidate sees a watermarked preview; after verified payment they receive the clean PDF via Streamlit's download button.

Payment provider is pluggable via `PAYMENT_PROVIDER` env var (`razorpay` | `stripe`). Only Razorpay is implemented; Stripe is a stub.

---

## 2. Checkout Flow (Option B — Payment Links with callback URL)

```
User on 6_Download (status: ACCEPTED)
    │
    ├─ clicks "Pay ₹99"
    │   → Python: PaymentProvider.create_order(amount_paise, "INR", reference_id, callback_url)
    │   → Razorpay: creates Payment Link → returns link_id + short_url (rzp.io/i/xxx)
    │   → DB: store payment_link_id, set status PAYMENT_PENDING
    │   → Streamlit: st.link_button opens short_url (same tab)
    │
    ├─ User pays on Razorpay hosted page
    │   → Razorpay redirects to: {APP_BASE_URL}/6_Download?submission_id={id}
    │     &razorpay_payment_id=xxx
    │     &razorpay_payment_link_id=yyy
    │     &razorpay_payment_link_reference_id=zzz
    │     &razorpay_payment_link_status=paid
    │     &razorpay_signature=www
    │
    ├─ Streamlit reruns, reads st.query_params
    │   → Python: verify payment_link_id matches DB record
    │   → Python: PaymentProvider.verify_payment(params) → SDK HMAC check
    │   → DB: store payment_id, set status PAYMENT_CONFIRMED
    │
    └─ Page shows st.download_button with clean PDF bytes
       → DB: set status DOWNLOADED
```

---

## 3. Module Structure

```
app/payment/
    __init__.py            exports get_payment_provider()
    provider.py            Abstract base + OrderResult dataclass + factory
    razorpay_adapter.py    Razorpay Payment Links implementation
    stripe_adapter.py      Stripe stub (raises NotImplementedError)

app/ui/pages/
    6_Download.py          Download page (new)

app/state/
    models.py              Add payment_link_id, payment_id fields to SubmissionRecord
    db.py                  Migration: ADD COLUMN payment_link_id, payment_id

app/config.py              Add payment config fields
requirements.txt           Add razorpay>=1.3.0
```

---

## 4. Payment Provider Interface

### `app/payment/provider.py`

```python
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class OrderResult:
    link_id: str      # Razorpay payment_link_id — stored in DB
    short_url: str    # rzp.io/i/xxx — opened in browser

class PaymentProvider(ABC):
    @abstractmethod
    def create_order(
        self,
        amount_paise: int,
        currency: str,
        reference_id: str,
        callback_url: str,
    ) -> OrderResult: ...

    @abstractmethod
    def verify_payment(self, params: dict) -> bool:
        # params keys (Razorpay): razorpay_payment_id, razorpay_payment_link_id,
        #   razorpay_payment_link_reference_id, razorpay_payment_link_status,
        #   razorpay_signature
        ...

def get_payment_provider() -> PaymentProvider:
    """Factory: reads PAYMENT_PROVIDER env var, returns correct adapter."""
    ...
```

### `app/payment/razorpay_adapter.py`

- Init: `razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))` — keys from env only, never hardcoded.
- `create_order()`: calls `client.payment_link.create({amount, currency, reference_id, callback_url, ...})`; returns `OrderResult(link_id=response["id"], short_url=response["short_url"])`.
- `verify_payment(params)`: calls `client.utility.verify_payment_link_signature(params)`; returns `True` on success, `False` on `SignatureVerificationError`.

### `app/payment/stripe_adapter.py`

```python
class StripeAdapter(PaymentProvider):
    def create_order(self, ...): raise NotImplementedError("Stripe not implemented")
    def verify_payment(self, ...): raise NotImplementedError("Stripe not implemented")
```

---

## 5. DB Migrations (SubmissionsDB)

Two new columns added via migration in `_init_db()` (same pattern as Phase 3/4):

```python
if "payment_link_id" not in existing_cols:
    conn.execute("ALTER TABLE submissions ADD COLUMN payment_link_id TEXT")
if "payment_id" not in existing_cols:
    conn.execute("ALTER TABLE submissions ADD COLUMN payment_id TEXT")
```

`SubmissionRecord` dataclass gains two optional fields:
```python
payment_link_id: Optional[str] = None
payment_id: Optional[str] = None
```

`_SUBMISSION_UPDATE_COLUMNS` gains `"payment_link_id"` and `"payment_id"`.

---

## 6. Config Additions (`app/config.py`)

```python
PAYMENT_PROVIDER: str = os.getenv("PAYMENT_PROVIDER", "razorpay")
RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
RESUME_DOWNLOAD_PRICE_INR: int = int(os.getenv("RESUME_DOWNLOAD_PRICE_INR", "99"))
APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:8501")
```

`.env` additions:
```
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=<test key id>
RAZORPAY_KEY_SECRET=<test key secret>
RESUME_DOWNLOAD_PRICE_INR=99
APP_BASE_URL=http://localhost:8501
```

---

## 7. Watermark Helper

Location: `app/payment/provider.py` (or standalone in `app/payment/watermark.py`)

```python
def watermark_pdf_bytes(pdf_path: Path) -> bytes:
    """Return PDF bytes with diagonal semi-transparent PREVIEW overlay on each page.
    Does NOT write any file. Clean PDF on disk is never modified."""
```

Implementation: PyMuPDF (`fitz`). For each page, insert a text stamp "PREVIEW" diagonally, grey, 40% opacity. Return `bytes`.

---

## 8. `6_Download.py` Page Logic

```python
# Guard: must be authenticated
# Guard: must have a submission_id in session state

# 1. Load submission from DB
# 2. Detect Razorpay callback: check st.query_params for razorpay_payment_id
# 3. Route by status:

if status == ACCEPTED:
    show_watermarked_preview()
    show_pay_button()   # st.link_button → short_url; also sets PAYMENT_PENDING

elif status == PAYMENT_PENDING:
    if razorpay callback params present in st.query_params:
        verify → PAYMENT_CONFIRMED  (or show error)
    else:
        st.info("Payment pending. Complete payment to download.")
        show_pay_button()   # allow retry

elif status in (PAYMENT_CONFIRMED, DOWNLOAD_READY):
    pdf_bytes = read clean PDF from disk
    st.download_button("Download Resume", pdf_bytes, "resume.pdf")
    set_status(DOWNLOADED)

elif status == DOWNLOADED:
    st.success("Resume downloaded.")
    pdf_bytes = read clean PDF
    st.download_button("Download Again", pdf_bytes, "resume.pdf")

else:
    st.warning("Resume not ready for download yet.")
```

---

## 9. Security Invariants

| Rule | Enforcement |
|---|---|
| Keys never in code | Config reads from env only; no defaults with real values |
| Never trust callback alone | `verify_payment()` always runs SDK HMAC check |
| `payment_link_id` match | DB-stored link_id must match callback's `razorpay_payment_link_id` |
| Watermark in memory | Clean PDF on disk never touched; watermark generated fresh per request |
| Download locked | `st.download_button` only rendered after status ≥ PAYMENT_CONFIRMED |

---

## 10. Tests

File: `tests/test_payment_provider.py`

| Test | Approach |
|---|---|
| `test_factory_returns_razorpay_adapter` | env var = "razorpay", check instance type |
| `test_factory_raises_on_unknown_provider` | env var = "unknown", expect ValueError |
| `test_stripe_adapter_raises_not_implemented` | call both methods, expect NotImplementedError |
| `test_create_order_returns_order_result` | mock razorpay client, check OrderResult fields |
| `test_verify_payment_valid_signature` | mock SDK returns True |
| `test_verify_payment_invalid_signature` | mock SDK raises SignatureVerificationError → False |
| `test_db_migration_adds_payment_columns` | in-memory SQLite, call _init_db twice, check columns |
| `test_update_submission_payment_fields` | update payment_link_id + payment_id via update_submission |
| `test_watermark_pdf_bytes_returns_bytes` | generate minimal PDF, check output is bytes with "PREVIEW" |
| `test_watermark_does_not_modify_source` | source PDF unchanged after watermark call |

---

## 11. Status Machine (Phase 10 transitions added)

```
ACCEPTED → PAYMENT_PENDING (user clicks Pay)
PAYMENT_PENDING → PAYMENT_CONFIRMED (server verifies payment)
PAYMENT_CONFIRMED → DOWNLOAD_READY (PDF served — optional intermediate)
DOWNLOAD_READY → DOWNLOADED (download button clicked)
PAYMENT_PENDING → ERROR (verification failure)
Any → ERROR (unexpected failure)
```

---

## 12. Acceptance Criteria (from tasks/PHASE-10-payment-gate-locked-download.md)

- [ ] `app/payment/provider.py` — `create_order()` + `verify_payment()` interface
- [ ] Razorpay adapter implemented and tested with mocks
- [ ] Stripe stub present and raises NotImplementedError
- [ ] `6_Download.py` — watermarked preview before payment
- [ ] `6_Download.py` — Pay button opens Razorpay Payment Link
- [ ] `6_Download.py` — callback verified server-side before unlock
- [ ] `6_Download.py` — clean PDF served via `st.download_button` after payment
- [ ] DB migrations: `payment_link_id`, `payment_id` columns
- [ ] `SubmissionRecord` updated with new fields
- [ ] `config.py` updated with payment env vars
- [ ] `requirements.txt` updated with `razorpay`
- [ ] All existing 329 tests still pass
- [ ] New payment tests passing

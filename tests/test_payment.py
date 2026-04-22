import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.state.db import SubmissionsDB
from app.state.models import SubmissionRecord, SubmissionStatus


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


# ── Provider factory tests ────────────────────────────────────────────────────

def test_factory_raises_on_unknown_provider(monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "nonexistent_pay")
    import importlib
    import app.payment.provider as prov_mod
    importlib.reload(prov_mod)
    with pytest.raises(ValueError, match="nonexistent_pay"):
        prov_mod.get_payment_provider()


def test_order_result_fields():
    from app.payment.provider import OrderResult
    r = OrderResult(link_id="plink_abc", short_url="https://rzp.io/i/abc")
    assert r.link_id == "plink_abc"
    assert r.short_url == "https://rzp.io/i/abc"


# ── Razorpay adapter tests ────────────────────────────────────────────────────


def test_razorpay_create_order_returns_order_result(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_fake")

    mock_client = MagicMock()
    mock_client.payment_link.create.return_value = {
        "id": "plink_TestAbc123",
        "short_url": "https://rzp.io/i/TestAbc",
    }

    with patch("app.payment.razorpay_adapter.razorpay.Client", return_value=mock_client):
        import importlib
        import app.payment.razorpay_adapter as adapter_mod
        importlib.reload(adapter_mod)
        adapter = adapter_mod.RazorpayAdapter()
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


def test_factory_returns_razorpay_adapter(monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_fake")
    import importlib
    import app.payment.provider as prov_mod
    importlib.reload(prov_mod)
    from app.payment.razorpay_adapter import RazorpayAdapter
    provider = prov_mod.get_payment_provider()
    assert isinstance(provider, RazorpayAdapter)

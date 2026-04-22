import sqlite3
import pytest
from pathlib import Path

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

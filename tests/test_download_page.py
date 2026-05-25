"""
Tests for _render_clean_download in app/ui/pages/6_Download.py.

Streamlit is stubbed so the page module can be imported without a running
Streamlit server.  We verify:
  - When output_print_pdf_path is set and the file exists, the Print
    download button is rendered.
  - When output_print_pdf_path is None, the "unavailable" caption is shown.
"""
import sys
import importlib.util as _ilu
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── Stub streamlit before importing the page module ────────────────────────
_st_mock = MagicMock()
_st_mock.session_state = MagicMock()
_st_mock.session_state.get.return_value = None
_st_mock.stop = MagicMock()
sys.modules["streamlit"] = _st_mock

# ── Import the download page module ───────────────────────────────────────
_page_path = Path(__file__).parent.parent / "app" / "ui" / "pages" / "6_Download.py"
_spec = _ilu.spec_from_file_location("download_page_module", str(_page_path))
_dl_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_dl_mod)

_render_clean_download = _dl_mod._render_clean_download

# ── st as seen by the page module (bound at import time) ──────────────────
# Using _dl_mod.st instead of `import streamlit as st` ensures we always
# configure the exact mock that the page module references, regardless of
# what other test files do to sys.modules["streamlit"].
_page_st = _dl_mod.st


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_submission(
    *,
    output_pdf_path=None,
    output_print_pdf_path=None,
    status="PAYMENT_CONFIRMED",
):
    from app.state.models import SubmissionRecord
    return SubmissionRecord(
        id=42,
        user_id=1,
        session_token="tok",
        resume_raw_text=None,
        resume_fields_json=None,
        resume_photo_path=None,
        jd_raw_text=None,
        jd_fields_json=None,
        ats_score_json=None,
        status=status,
        revision_count=0,
        error_message=None,
        created_at=None,
        updated_at=None,
        output_pdf_path=output_pdf_path,
        output_print_pdf_path=output_print_pdf_path,
    )


def _setup_columns():
    """Configure the page module's st mock columns to return two context managers."""
    col_mock = MagicMock()
    col_mock.__enter__ = MagicMock(return_value=col_mock)
    col_mock.__exit__ = MagicMock(return_value=False)
    _page_st.columns.return_value = (col_mock, col_mock)
    _page_st.download_button.reset_mock()
    _page_st.caption.reset_mock()
    _page_st.download_button.return_value = False
    return col_mock


# ── Tests ──────────────────────────────────────────────────────────────────

def test_print_download_button_rendered_when_file_exists(tmp_path):
    """When output_print_pdf_path points to an existing file, the Print
    download button must be rendered."""
    ats_pdf = tmp_path / "ats.pdf"
    print_pdf = tmp_path / "print.pdf"
    ats_pdf.write_bytes(b"%PDF-1.4 ats")
    print_pdf.write_bytes(b"%PDF-1.4 print")

    submission = _make_submission(
        output_pdf_path=str(ats_pdf),
        output_print_pdf_path=str(print_pdf),
    )

    _setup_columns()
    subs_db_mock = MagicMock()

    _render_clean_download(submission, subs_db_mock)

    # In Streamlit, `with col:` is a context manager but st.download_button
    # is still called on the global st object inside the block.
    labels = [
        c.kwargs.get("label", c.args[0] if c.args else "")
        for c in _page_st.download_button.call_args_list
    ]
    assert any("Print Resume" in lbl for lbl in labels), (
        f"Expected 'Print Resume' download button; got labels: {labels}"
    )


def test_print_unavailable_caption_when_path_is_none(tmp_path):
    """When output_print_pdf_path is None, the 'unavailable' caption must
    be shown instead of a download button."""
    ats_pdf = tmp_path / "ats.pdf"
    ats_pdf.write_bytes(b"%PDF-1.4 ats")

    submission = _make_submission(
        output_pdf_path=str(ats_pdf),
        output_print_pdf_path=None,
    )

    _setup_columns()
    subs_db_mock = MagicMock()

    _render_clean_download(submission, subs_db_mock)

    # st.caption must have been called with the "unavailable" message
    caption_args = [str(c) for c in _page_st.caption.call_args_list]
    assert any(
        "unavailable" in arg.lower() or "contact support" in arg.lower()
        for arg in caption_args
    ), f"Expected unavailable caption; caption calls: {caption_args}"


def test_ats_download_button_rendered_when_file_exists(tmp_path):
    """ATS download button must be rendered with the correct label."""
    ats_pdf = tmp_path / "ats.pdf"
    ats_pdf.write_bytes(b"%PDF-1.4 ats")

    submission = _make_submission(
        output_pdf_path=str(ats_pdf),
        output_print_pdf_path=None,
    )

    _setup_columns()
    subs_db_mock = MagicMock()

    _render_clean_download(submission, subs_db_mock)

    labels = [
        c.kwargs.get("label", c.args[0] if c.args else "")
        for c in _page_st.download_button.call_args_list
    ]
    assert any("ATS Resume" in lbl for lbl in labels), (
        f"Expected 'ATS Resume' download button; got labels: {labels}"
    )

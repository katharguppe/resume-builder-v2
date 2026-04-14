"""Tests for app/ui/components/missing_panel.py — no Streamlit runtime needed."""
from app.scoring.models import MissingItem


def _item(field, severity, section="Experience"):
    return MissingItem(field=field, label=field, severity=severity,
                       hint="hint", section=section)


# ---------------------------------------------------------------------------
# _group_by_severity
# ---------------------------------------------------------------------------

def test_group_by_severity_empty():
    from app.ui.components.missing_panel import _group_by_severity
    groups = _group_by_severity([])
    assert groups == {"HIGH": [], "MEDIUM": [], "LOW": []}


def test_group_by_severity_single_high():
    from app.ui.components.missing_panel import _group_by_severity
    item = _item("work_dates", "HIGH")
    groups = _group_by_severity([item])
    assert groups["HIGH"] == [item]
    assert groups["MEDIUM"] == []
    assert groups["LOW"] == []


def test_group_by_severity_mixed():
    from app.ui.components.missing_panel import _group_by_severity
    h = _item("work_dates", "HIGH")
    m = _item("achievements", "MEDIUM")
    lo = _item("certifications", "LOW")
    groups = _group_by_severity([h, m, lo])
    assert groups["HIGH"] == [h]
    assert groups["MEDIUM"] == [m]
    assert groups["LOW"] == [lo]


def test_group_by_severity_multiple_same():
    from app.ui.components.missing_panel import _group_by_severity
    h1 = _item("work_dates", "HIGH")
    h2 = _item("current_title", "HIGH", section="Contact")
    groups = _group_by_severity([h1, h2])
    assert len(groups["HIGH"]) == 2


# ---------------------------------------------------------------------------
# render_missing_panel — mocked Streamlit
# ---------------------------------------------------------------------------

def test_render_missing_panel_no_items_calls_success(monkeypatch):
    """When detect_missing returns [], should call st.success."""
    import app.ui.components.missing_panel as mod
    import streamlit as st

    success_calls = []
    monkeypatch.setattr(mod, "detect_missing", lambda *a: [])
    monkeypatch.setattr(st, "success", lambda msg: success_calls.append(msg))

    mod.render_missing_panel({}, "")
    assert len(success_calls) == 1
    assert "No critical" in success_calls[0]


def test_render_missing_panel_calls_expander_for_high(monkeypatch):
    """When HIGH items exist, st.expander must be called."""
    import app.ui.components.missing_panel as mod
    import streamlit as st
    from unittest.mock import MagicMock

    item = _item("work_dates", "HIGH", "Experience")
    monkeypatch.setattr(mod, "detect_missing", lambda *a: [item])

    expander_titles = []
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=None)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    def fake_expander(title, expanded=False):
        expander_titles.append(title)
        return mock_ctx

    monkeypatch.setattr(st, "expander", fake_expander)
    monkeypatch.setattr(st, "columns", lambda spec: [MagicMock(), MagicMock()])

    mod.render_missing_panel({}, "text")
    assert any("High Priority" in t for t in expander_titles)


def test_render_missing_panel_key_prefix_in_button(monkeypatch):
    """Button key must include key_prefix to avoid widget ID collisions."""
    import app.ui.components.missing_panel as mod
    import streamlit as st
    from unittest.mock import MagicMock

    item = _item("work_dates", "HIGH", "Experience")
    monkeypatch.setattr(mod, "detect_missing", lambda *a: [item])

    button_keys = []

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=None)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(st, "expander", lambda *a, **kw: mock_ctx)
    monkeypatch.setattr(st, "columns", lambda spec: [MagicMock(), MagicMock()])

    def fake_button(label, key=None):
        button_keys.append(key)
        return False

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "markdown", lambda *a, **kw: None)

    mod.render_missing_panel({}, "text", key_prefix="review_")
    assert any(k and k.startswith("review_") for k in button_keys)

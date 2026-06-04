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
    from unittest.mock import MagicMock

    mock_st = MagicMock()
    monkeypatch.setattr(mod, "st", mock_st)
    monkeypatch.setattr(mod, "detect_missing", lambda *a: [])

    mod.render_missing_panel({}, "")
    mock_st.success.assert_called_once()
    assert "No critical" in mock_st.success.call_args[0][0]


def test_render_missing_panel_calls_expander_for_high(monkeypatch):
    """When HIGH items exist, st.expander must be called."""
    import app.ui.components.missing_panel as mod
    from unittest.mock import MagicMock

    item = _item("work_dates", "HIGH", "Experience")
    monkeypatch.setattr(mod, "detect_missing", lambda *a: [item])

    mock_st = MagicMock()
    mock_st.columns.return_value = [MagicMock(), MagicMock()]
    mock_st.button.return_value = False
    monkeypatch.setattr(mod, "st", mock_st)

    mod.render_missing_panel({}, "text")

    expander_titles = [str(call.args[0]) for call in mock_st.expander.call_args_list]
    assert any("High Priority" in t for t in expander_titles)


def test_render_missing_panel_key_prefix_in_button(monkeypatch):
    """Button key must include key_prefix to avoid widget ID collisions."""
    import app.ui.components.missing_panel as mod
    from unittest.mock import MagicMock

    item = _item("work_dates", "HIGH", "Experience")
    monkeypatch.setattr(mod, "detect_missing", lambda *a: [item])

    mock_st = MagicMock()
    mock_st.columns.return_value = [MagicMock(), MagicMock()]
    mock_st.button.return_value = False
    monkeypatch.setattr(mod, "st", mock_st)

    mod.render_missing_panel({}, "text", key_prefix="review_")

    button_keys = [
        call.kwargs.get("key", call.args[1] if len(call.args) > 1 else None)
        for call in mock_st.button.call_args_list
    ]
    assert any(k and k.startswith("review_") for k in button_keys)

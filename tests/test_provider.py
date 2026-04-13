import pytest
from unittest.mock import patch


# ── Extract routing (Claude) ─────────────────────────────────────────────────

def test_extract_resume_fields_routes_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "claude")
    expected = {"candidate_name": "Alice", "email": "", "phone": "",
                "current_title": "Engineer", "skills": ["Python"], "experience_summary": ""}
    with patch("app.llm.provider.extract_resume_fields_claude", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.extract_resume_fields("Alice resume")
    mock_fn.assert_called_once_with("Alice resume")
    assert result["candidate_name"] == "Alice"


def test_extract_jd_fields_routes_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "claude")
    expected = {"job_title": "SWE", "company": "", "required_skills": ["Python"],
                "preferred_skills": [], "experience_required": "", "education_required": "",
                "key_responsibilities": []}
    with patch("app.llm.provider.extract_jd_fields_claude", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.extract_jd_fields("Python SWE role")
    mock_fn.assert_called_once_with("Python SWE role")
    assert result["job_title"] == "SWE"


# ── Extract routing (Gemini) ─────────────────────────────────────────────────

def test_extract_resume_fields_routes_to_gemini(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "gemini")
    expected = {"candidate_name": "Bob", "email": "", "phone": "",
                "current_title": "PM", "skills": [], "experience_summary": ""}
    with patch("app.llm.provider.extract_resume_fields_gemini", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.extract_resume_fields("Bob resume")
    mock_fn.assert_called_once_with("Bob resume")
    assert result["candidate_name"] == "Bob"


def test_extract_jd_fields_routes_to_gemini(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "gemini")
    expected = {"job_title": "PM", "company": "Corp", "required_skills": [],
                "preferred_skills": [], "experience_required": "", "education_required": "",
                "key_responsibilities": []}
    with patch("app.llm.provider.extract_jd_fields_gemini", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.extract_jd_fields("PM role at Corp")
    mock_fn.assert_called_once_with("PM role at Corp")
    assert result["job_title"] == "PM"


def test_extract_resume_fields_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "unknown_provider")
    import app.llm.provider as prov
    with pytest.raises(NotImplementedError, match="unknown_provider"):
        prov.extract_resume_fields("any text")


def test_extract_jd_fields_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "unknown_provider")
    import app.llm.provider as prov
    with pytest.raises(NotImplementedError, match="unknown_provider"):
        prov.extract_jd_fields("any jd")


# ── Rewrite routing ──────────────────────────────────────────────────────────

def test_rewrite_resume_routes_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_REWRITE_PROVIDER", "claude")
    expected = {"candidate_name": "Alice", "summary": "Good."}
    with patch("app.llm.provider.rewrite_resume_claude", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.rewrite_resume("resume", "jd", "best practice")
    mock_fn.assert_called_once_with("resume", "jd", "best practice", revision_hint="")
    assert result["summary"] == "Good."


def test_rewrite_resume_routes_to_deepseek(monkeypatch):
    monkeypatch.setenv("LLM_REWRITE_PROVIDER", "deepseek")
    expected = {"candidate_name": "Bob", "summary": "Expert."}
    with patch("app.llm.provider.rewrite_resume_deepseek", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        result = prov.rewrite_resume("resume", "jd", "best practice")
    mock_fn.assert_called_once_with("resume", "jd", "best practice", revision_hint="")
    assert result["summary"] == "Expert."


def test_rewrite_resume_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_REWRITE_PROVIDER", "unknown_llm")
    import app.llm.provider as prov
    with pytest.raises(NotImplementedError, match="unknown_llm"):
        prov.rewrite_resume("resume", "jd", "bp")


def test_rewrite_resume_passes_hint_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_REWRITE_PROVIDER", "claude")
    expected = {"candidate_name": "Alice", "summary": "Revised."}
    with patch("app.llm.provider.rewrite_resume_claude", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        prov.rewrite_resume("resume", "jd", "bp", revision_hint="Focus on Python skills")
    mock_fn.assert_called_once_with("resume", "jd", "bp", revision_hint="Focus on Python skills")


def test_rewrite_resume_passes_hint_to_deepseek(monkeypatch):
    monkeypatch.setenv("LLM_REWRITE_PROVIDER", "deepseek")
    expected = {"candidate_name": "Bob", "summary": "Revised."}
    with patch("app.llm.provider.rewrite_resume_deepseek", return_value=expected) as mock_fn:
        import app.llm.provider as prov
        prov.rewrite_resume("resume", "jd", "bp", revision_hint="Focus on Python skills")
    mock_fn.assert_called_once_with("resume", "jd", "bp", revision_hint="Focus on Python skills")

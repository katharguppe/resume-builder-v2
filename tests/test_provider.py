import pytest
from unittest.mock import patch


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


def test_extract_resume_fields_gemini_raises_not_implemented(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "gemini")
    import app.llm.provider as prov
    with pytest.raises(NotImplementedError, match="gemini"):
        prov.extract_resume_fields("any text")


def test_extract_jd_fields_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_EXTRACT_PROVIDER", "unknown_provider")
    import app.llm.provider as prov
    with pytest.raises(NotImplementedError):
        prov.extract_jd_fields("any jd")

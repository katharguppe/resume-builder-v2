import json
import pytest
from unittest.mock import patch, MagicMock

from app.llm.prompt_builder import build_finetuning_prompt, build_extraction_prompt
from app.llm.finetuner import extract_fields, rewrite_resume, fine_tune_resume, extract_resume_fields_claude, extract_jd_fields_claude, extract_resume_fields_gemini, extract_jd_fields_gemini
from app.config import config


# ── prompt_builder tests ────────────────────────────────────────────────────

def test_build_extraction_prompt():
    prompt = build_extraction_prompt("John Doe, john@example.com")
    assert "candidate_name" in prompt
    assert "email" in prompt
    assert "phone" in prompt
    assert "John Doe" in prompt


def test_build_finetuning_prompt():
    prompt = build_finetuning_prompt("Resume info", "JD info", "Best practices info", "John Doe")
    assert "John Doe" in prompt
    assert "JD info" in prompt
    assert "Do not invent, fabricate," in prompt
    assert "missing_fields" in prompt


def test_finetuning_prompt_exact_phrasing_rule():
    """Prompt must instruct the model to use exact JD phrasing in bullets."""
    prompt = build_finetuning_prompt("Resume text", "JD text", "", "Jane Doe")
    assert "EXACT phrasing" in prompt, "Prompt missing 'EXACT phrasing' instruction"
    assert "most directly relevant to the JD first" in prompt, (
        "Prompt missing bullet ordering instruction"
    )


# ── helpers ────────────────────────────────────────────────────────────────

def _make_message(text: str) -> MagicMock:
    """Return a mock Anthropic message response with the given text."""
    content_block = MagicMock()
    content_block.text = text
    msg = MagicMock()
    msg.content = [content_block]
    return msg


EXTRACT_JSON = '{"candidate_name": "Bob", "email": "b@b.com", "phone": "123"}'
REWRITE_JSON = json.dumps({
    "candidate_name": "Bob",
    "contact": {"email": "b@b.com", "phone": "123", "linkedin": "in/bob"},
    "summary": "Great engineer.",
    "experience": [],
    "education": [],
    "skills": [],
    "missing_fields": [],
})


# ── extract_fields tests ────────────────────────────────────────────────────

@patch("app.llm.finetuner._get_client")
def test_extract_fields_happy_path(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.messages.create.return_value = _make_message(EXTRACT_JSON)

    result = extract_fields("John Doe resume text")
    assert result["candidate_name"] == "Bob"
    assert result["email"] == "b@b.com"
    assert mock_client.messages.create.call_count == 1


@patch("app.llm.finetuner._get_client")
def test_extract_fields_retry_success(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.messages.create.side_effect = [
        _make_message("not json"),
        _make_message(EXTRACT_JSON),
    ]

    result = extract_fields("resume")
    assert result["candidate_name"] == "Bob"
    assert mock_client.messages.create.call_count == 2


@patch("app.llm.finetuner._get_client")
def test_extract_fields_failure(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.messages.create.return_value = _make_message("bad json always")

    with pytest.raises(ValueError, match="Failed to obtain valid JSON from extract_fields"):
        extract_fields("resume")

    assert mock_client.messages.create.call_count == config.MAX_LLM_RETRIES


# ── rewrite_resume tests ────────────────────────────────────────────────────

@patch("app.llm.finetuner._get_client")
def test_rewrite_resume_happy_path(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    # First call: extract_fields (Haiku), second call: rewrite_resume (Sonnet)
    mock_client.messages.create.side_effect = [
        _make_message(EXTRACT_JSON),
        _make_message(REWRITE_JSON),
    ]

    result = rewrite_resume("resume text", "jd text", "best practice")
    assert result["candidate_name"] == "Bob"
    assert result["summary"] == "Great engineer."
    assert mock_client.messages.create.call_count == 2


@patch("app.llm.finetuner._get_client")
def test_rewrite_resume_retry_success(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.messages.create.side_effect = [
        _make_message(EXTRACT_JSON),   # extract_fields succeeds
        _make_message("bad json"),     # rewrite attempt 1 fails
        _make_message(REWRITE_JSON),   # rewrite attempt 2 succeeds
    ]

    result = rewrite_resume("resume", "jd", "bp")
    assert result["candidate_name"] == "Bob"
    assert mock_client.messages.create.call_count == 3


@patch("app.llm.finetuner._get_client")
def test_rewrite_resume_failure(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    # extract succeeds, then Sonnet always returns bad JSON
    mock_client.messages.create.side_effect = (
        [_make_message(EXTRACT_JSON)]
        + [_make_message("bad json")] * config.MAX_LLM_RETRIES
    )

    with pytest.raises(ValueError, match="Failed to obtain valid JSON from rewrite_resume"):
        rewrite_resume("resume", "jd", "bp")


# ── Phase 2: extract_resume_fields_claude + extract_jd_fields_claude ─────────


def _mock_llm_response(json_str: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=json_str)]
    return msg


def test_extract_resume_fields_claude_returns_dict():
    payload = '{"candidate_name":"Alice","email":"a@b.com","phone":"555","current_title":"Engineer","skills":["Python"],"experience_summary":"5 years"}'
    with patch("app.llm.finetuner._get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_llm_response(payload)
        result = extract_resume_fields_claude("Alice resume text")
    assert result["candidate_name"] == "Alice"
    assert result["skills"] == ["Python"]
    assert result["current_title"] == "Engineer"


def test_extract_resume_fields_claude_retries_on_bad_json():
    good = '{"candidate_name":"Bob","email":"","phone":"","current_title":"","skills":[],"experience_summary":""}'
    responses = [_mock_llm_response("not json"), _mock_llm_response(good)]
    with patch("app.llm.finetuner._get_client") as mock_client:
        mock_client.return_value.messages.create.side_effect = responses
        result = extract_resume_fields_claude("Bob resume text")
    assert result["candidate_name"] == "Bob"


def test_extract_jd_fields_claude_returns_dict():
    payload = '{"job_title":"SWE","company":"ACME","required_skills":["Python","SQL"],"preferred_skills":[],"experience_required":"3 years","education_required":"BS","key_responsibilities":["Build APIs"]}'
    with patch("app.llm.finetuner._get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_llm_response(payload)
        result = extract_jd_fields_claude("We need a SWE at ACME")
    assert result["job_title"] == "SWE"
    assert "Python" in result["required_skills"]


def test_extract_jd_fields_claude_raises_after_max_retries():
    with patch("app.llm.finetuner._get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_llm_response("not valid json")
        with pytest.raises(ValueError, match="max retries"):
            extract_jd_fields_claude("some jd text")


# ── fine_tune_resume backward-compat wrapper ────────────────────────────────

@patch("app.llm.finetuner._get_client")
def test_fine_tune_resume_compat(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.messages.create.side_effect = [
        _make_message(EXTRACT_JSON),
        _make_message(REWRITE_JSON),
    ]

    result = fine_tune_resume("resume", "jd", "bp", "ignored_name_hint")
    assert result["candidate_name"] == "Bob"
    assert mock_client.messages.create.call_count == 2


# ── Gemini Flash extract adapters ───────────────────────────────────────────


def _make_gemini_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


RESUME_FIELDS_JSON = '{"candidate_name":"Alice","email":"a@b.com","phone":"555","current_title":"Engineer","skills":["Python"],"experience_summary":"5 years"}'
JD_FIELDS_JSON = '{"job_title":"SWE","company":"ACME","required_skills":["Python"],"preferred_skills":[],"experience_required":"3y","education_required":"BS","key_responsibilities":["Build APIs"]}'


@patch("app.llm.finetuner._get_genai_model")
def test_extract_resume_fields_gemini_happy_path(mock_get_model):
    mock_model = MagicMock()
    mock_get_model.return_value = mock_model
    mock_model.generate_content.return_value = _make_gemini_response(RESUME_FIELDS_JSON)

    result = extract_resume_fields_gemini("Alice resume text")

    mock_get_model.assert_called_once()
    assert result["candidate_name"] == "Alice"
    assert result["skills"] == ["Python"]


@patch("app.llm.finetuner._get_genai_model")
def test_extract_resume_fields_gemini_retry_then_pass(mock_get_model):
    mock_model = MagicMock()
    mock_get_model.return_value = mock_model
    mock_model.generate_content.side_effect = [
        _make_gemini_response("not json"),
        _make_gemini_response(RESUME_FIELDS_JSON),
    ]

    result = extract_resume_fields_gemini("resume")
    assert result["candidate_name"] == "Alice"
    assert mock_model.generate_content.call_count == 2


@patch("app.llm.finetuner._get_genai_model")
def test_extract_resume_fields_gemini_raises_after_max_retries(mock_get_model):
    mock_model = MagicMock()
    mock_get_model.return_value = mock_model
    mock_model.generate_content.return_value = _make_gemini_response("bad json always")

    with pytest.raises(ValueError, match="extract_resume_fields_gemini"):
        extract_resume_fields_gemini("resume")


@patch("app.llm.finetuner._get_genai_model")
def test_extract_jd_fields_gemini_happy_path(mock_get_model):
    mock_model = MagicMock()
    mock_get_model.return_value = mock_model
    mock_model.generate_content.return_value = _make_gemini_response(JD_FIELDS_JSON)

    result = extract_jd_fields_gemini("SWE role at ACME")
    assert result["job_title"] == "SWE"
    assert "Python" in result["required_skills"]

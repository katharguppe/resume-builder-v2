import json
import pytest
from unittest.mock import patch, MagicMock

from app.llm.prompt_builder import build_finetuning_prompt, build_extraction_prompt
from app.llm.finetuner import extract_fields, rewrite_resume, fine_tune_resume
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

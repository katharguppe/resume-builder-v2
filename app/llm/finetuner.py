import json
import logging
import os
import re
import anthropic
import google.generativeai as genai
from openai import OpenAI
from app.config import config
from app.llm.prompt_builder import (
    build_extraction_prompt,
    build_finetuning_prompt,
    build_resume_fields_prompt,
    build_jd_extraction_prompt,
)

logger = logging.getLogger("llm")


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers the model sometimes adds."""
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.DOTALL)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


_genai_model: genai.GenerativeModel | None = None


def _get_genai_model() -> genai.GenerativeModel:
    global _genai_model
    if _genai_model is None:
        genai.configure(api_key=config.GEMINI_API_KEY)
        _genai_model = genai.GenerativeModel(config.LLM_GEMINI_EXTRACT_MODEL)
    return _genai_model


def extract_fields(resume_text: str) -> dict:
    """
    Haiku pass: extract candidate_name, email, phone from raw resume text.
    Returns dict with keys: candidate_name, email, phone.
    Retries up to MAX_LLM_RETRIES on malformed JSON.
    """
    prompt = build_extraction_prompt(resume_text)
    client = _get_client()

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = client.messages.create(
                model=config.LLM_EXTRACT_MODEL,
                max_tokens=256,
                system="You are a resume parser. Respond ONLY with valid JSON. No markdown, no explanation.",
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(_strip_markdown_fences(response.content[0].text))
        except json.JSONDecodeError as e:
            logger.warning(f"extract_fields attempt {attempt}/{config.MAX_LLM_RETRIES} failed to parse JSON: {e}")
            if attempt == config.MAX_LLM_RETRIES:
                logger.error("Max retries reached in extract_fields.")
                raise ValueError("Failed to obtain valid JSON from extract_fields after max retries")
        except Exception as e:
            logger.error(f"Unexpected error in extract_fields: {e}")
            raise


def rewrite_resume(resume_text: str, jd_text: str, best_practice: str) -> dict:
    """
    Sonnet pass: rewrite resume aligned to JD using best-practice format.
    Calls extract_fields (Haiku) first to get candidate name, then calls Sonnet.
    Returns full output dict: candidate_name, contact, summary, experience[],
    education[], skills[], missing_fields[].
    Retries up to MAX_LLM_RETRIES on malformed JSON.
    """
    fields = extract_fields(resume_text)
    candidate_name = fields.get("candidate_name") or "Unknown"

    prompt = build_finetuning_prompt(resume_text, jd_text, best_practice, candidate_name)
    client = _get_client()

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = client.messages.create(
                model=config.LLM_REWRITE_MODEL,
                max_tokens=4096,
                system=(
                    "You are an expert resume writer. "
                    "Respond ONLY with valid JSON matching the specified schema. "
                    "No markdown, no explanation."
                ),
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(_strip_markdown_fences(response.content[0].text))
        except json.JSONDecodeError as e:
            logger.warning(f"rewrite_resume attempt {attempt}/{config.MAX_LLM_RETRIES} failed to parse JSON: {e}")
            if attempt == config.MAX_LLM_RETRIES:
                logger.error("Max retries reached in rewrite_resume.")
                raise ValueError("Failed to obtain valid JSON from rewrite_resume after max retries")
        except Exception as e:
            logger.error(f"Unexpected error in rewrite_resume: {e}")
            raise


def fine_tune_resume(resume_text: str, jd_text: str, best_practice_text: str, candidate_name: str) -> dict:
    """
    Backward-compatible wrapper for runner.py.
    Delegates to rewrite_resume(); candidate_name arg is ignored
    (the real name is extracted from resume_text by extract_fields).
    """
    return rewrite_resume(resume_text, jd_text, best_practice_text)


def extract_resume_fields_claude(resume_text: str) -> dict:
    """
    v2 EXTRACT pass (Claude adapter).
    Returns richer schema than v1 extract_fields():
      candidate_name, email, phone, current_title, skills[], experience_summary
    v1 extract_fields() is preserved unchanged for backward compat.
    """
    prompt = build_resume_fields_prompt(resume_text)
    client = _get_client()

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = client.messages.create(
                model=config.LLM_EXTRACT_MODEL,
                max_tokens=512,
                system="You are a resume parser. Respond ONLY with valid JSON. No markdown, no explanation.",
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(_strip_markdown_fences(response.content[0].text))
        except json.JSONDecodeError as e:
            logger.warning(f"extract_resume_fields_claude attempt {attempt}/{config.MAX_LLM_RETRIES} bad JSON: {e}")
            if attempt == config.MAX_LLM_RETRIES:
                raise ValueError("Failed to obtain valid JSON from extract_resume_fields_claude after max retries")
        except Exception as e:
            logger.error(f"Unexpected error in extract_resume_fields_claude: {e}")
            raise


def extract_jd_fields_claude(jd_text: str) -> dict:
    """
    JD field extraction (Claude adapter).
    Returns: job_title, company, required_skills[], preferred_skills[],
             experience_required, education_required, key_responsibilities[]
    """
    prompt = build_jd_extraction_prompt(jd_text)
    client = _get_client()

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = client.messages.create(
                model=config.LLM_EXTRACT_MODEL,
                max_tokens=1024,
                system="You are a job description parser. Respond ONLY with valid JSON. No markdown, no explanation.",
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(_strip_markdown_fences(response.content[0].text))
        except json.JSONDecodeError as e:
            logger.warning(f"extract_jd_fields_claude attempt {attempt}/{config.MAX_LLM_RETRIES} bad JSON: {e}")
            if attempt == config.MAX_LLM_RETRIES:
                raise ValueError("Failed to obtain valid JSON from extract_jd_fields_claude after max retries")
        except Exception as e:
            logger.error(f"Unexpected error in extract_jd_fields_claude: {e}")
            raise


def extract_resume_fields_gemini(resume_text: str) -> dict:
    """
    EXTRACT pass using Gemini Flash.
    Returns same schema as extract_resume_fields_claude.
    """
    model = _get_genai_model()
    prompt = build_resume_fields_prompt(resume_text)

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = model.generate_content(prompt)
            return json.loads(_strip_markdown_fences(response.text))
        except json.JSONDecodeError as e:
            logger.warning(
                f"extract_resume_fields_gemini attempt {attempt}/{config.MAX_LLM_RETRIES} bad JSON: {e}"
            )
            if attempt == config.MAX_LLM_RETRIES:
                raise ValueError(
                    "Failed to obtain valid JSON from extract_resume_fields_gemini after max retries"
                )
        except Exception as e:
            logger.error(f"Unexpected error in extract_resume_fields_gemini: {e}")
            raise


def extract_jd_fields_gemini(jd_text: str) -> dict:
    """
    JD field extraction using Gemini Flash.
    Returns same schema as extract_jd_fields_claude.
    """
    model = _get_genai_model()
    prompt = build_jd_extraction_prompt(jd_text)

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = model.generate_content(prompt)
            return json.loads(_strip_markdown_fences(response.text))
        except json.JSONDecodeError as e:
            logger.warning(
                f"extract_jd_fields_gemini attempt {attempt}/{config.MAX_LLM_RETRIES} bad JSON: {e}"
            )
            if attempt == config.MAX_LLM_RETRIES:
                raise ValueError(
                    "Failed to obtain valid JSON from extract_jd_fields_gemini after max retries"
                )
        except Exception as e:
            logger.error(f"Unexpected error in extract_jd_fields_gemini: {e}")
            raise


def rewrite_resume_deepseek(resume_text: str, jd_text: str, best_practice: str) -> dict:
    """
    REWRITE pass using DeepSeek V3 (OpenAI-compatible API).
    Same prompt schema and output format as rewrite_resume (Claude).
    Calls extract_fields (Claude Haiku) first to get candidate name.
    """
    fields = extract_fields(resume_text)
    candidate_name = fields.get("candidate_name") or "Unknown"
    prompt = build_finetuning_prompt(resume_text, jd_text, best_practice, candidate_name)

    ds_client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

    for attempt in range(1, config.MAX_LLM_RETRIES + 1):
        try:
            response = ds_client.chat.completions.create(
                model=os.getenv("DEEPSEEK_REWRITE_MODEL", "deepseek-chat"),
                max_tokens=4096,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert resume writer. "
                            "Respond ONLY with valid JSON matching the specified schema. "
                            "No markdown, no explanation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return json.loads(_strip_markdown_fences(response.choices[0].message.content))
        except json.JSONDecodeError as e:
            logger.warning(
                f"rewrite_resume_deepseek attempt {attempt}/{config.MAX_LLM_RETRIES} bad JSON: {e}"
            )
            if attempt == config.MAX_LLM_RETRIES:
                raise ValueError(
                    "Failed to obtain valid JSON from rewrite_resume_deepseek after max retries"
                )
        except Exception as e:
            logger.error(f"Unexpected error in rewrite_resume_deepseek: {e}")
            raise

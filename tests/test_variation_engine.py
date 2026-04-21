import pytest
from app.llm.variation_engine import (
    apply_variation,
    apply_variation_to_resume,
    SYNONYM_GROUPS,
    BANNED_PHRASES,
)


# ── Per-group tests (12 parametrized cases = 12 pytest tests) ──────────────

@pytest.mark.parametrize("phrase,sentence", [
    ("cross-functional",  "She leads cross-functional teams across the business."),
    ("results-driven",    "A results-driven professional with ten years of experience."),
    ("self-starter",      "Known as a self-starter who needs minimal supervision."),
    ("team player",       "A team player who gets results through coordination."),
    ("detail-oriented",   "She is detail-oriented and catches errors early."),
    ("go-getter",         "Recognised as a go-getter within the department."),
    ("synergy",           "Created synergy between product and engineering teams."),
    ("leverage",          "Able to leverage existing infrastructure to cut costs."),
    ("proactive",         "Takes a proactive approach to stakeholder management."),
    ("dynamic",           "A dynamic professional comfortable in fast-moving environments."),
    ("passionate about",  "Passionate about delivering high-quality customer outcomes."),
    ("thought leader",    "Recognised as a thought leader in the fintech space."),
])
def test_synonym_group_replaced(phrase, sentence):
    result = apply_variation(sentence)
    assert phrase not in result.lower(), (
        f"Expected '{phrase}' to be replaced but found it in: {result!r}"
    )
    assert any(alt.lower() in result.lower() for alt in SYNONYM_GROUPS[phrase]), (
        f"Expected one of {SYNONYM_GROUPS[phrase]!r} in result: {result!r}"
    )


# ── Core behaviour tests ────────────────────────────────────────────────────

def test_apply_variation_no_match():
    text = "Increased quarterly revenue by 35% through targeted account expansion."
    assert apply_variation(text) == text


def test_apply_variation_case_preserved_uppercase():
    # Phrase at start of sentence — replacement must also be capitalised.
    result = apply_variation("Cross-functional collaboration is essential.")
    assert result[0].isupper(), f"Expected uppercase first char but got: {result!r}"
    assert "cross-functional" not in result.lower()


def test_apply_variation_case_insensitive_detection():
    result = apply_variation("She is CROSS-FUNCTIONAL in her approach.")
    assert "cross-functional" not in result.lower()
    assert any(alt.lower() in result.lower() for alt in SYNONYM_GROUPS["cross-functional"])


def test_apply_variation_no_replacement_phrase_untouched():
    # "hit the ground running" is in BANNED_PHRASES but NOT in SYNONYM_GROUPS.
    # No pattern is compiled for it, so apply_variation must leave it unchanged.
    text = "Ready to hit the ground running from day one."
    assert apply_variation(text) == text


def test_apply_variation_returns_string():
    result = apply_variation("A results-driven and dynamic professional.")
    assert isinstance(result, str)


# ── apply_variation_to_resume tests ────────────────────────────────────────

def test_apply_variation_to_resume_summary():
    data = {
        "candidate_name": "Alice Smith",
        "summary": "A results-driven and detail-oriented professional.",
        "experience": [],
        "skills": ["Python", "results-driven"],
        "missing_fields": [],
    }
    result = apply_variation_to_resume(data)
    assert "results-driven" not in result["summary"].lower()
    assert "detail-oriented" not in result["summary"].lower()


def test_apply_variation_to_resume_bullets():
    data = {
        "candidate_name": "Bob Jones",
        "summary": "Experienced professional.",
        "experience": [
            {
                "title": "Manager",
                "company": "Acme",
                "dates": "2020-2024",
                "bullets": [
                    "Led cross-functional teams to deliver on time.",
                    "Recognised as a thought leader in operations.",
                ],
            }
        ],
        "skills": ["leadership"],
        "missing_fields": [],
    }
    result = apply_variation_to_resume(data)
    bullets = result["experience"][0]["bullets"]
    assert "cross-functional" not in bullets[0].lower()
    assert "thought leader" not in bullets[1].lower()


def test_apply_variation_to_resume_skills_untouched():
    # skills[] are ATS keyword terms — must never be modified.
    data = {
        "candidate_name": "Carol Lee",
        "summary": "Experienced professional.",
        "experience": [],
        "skills": ["cross-functional leadership", "results-driven delivery"],
        "missing_fields": [],
    }
    result = apply_variation_to_resume(data)
    assert result["skills"] == data["skills"]


def test_apply_variation_to_resume_missing_keys():
    # Empty dict and partial dicts must not raise.
    assert apply_variation_to_resume({}) == {}
    result = apply_variation_to_resume({"summary": "Clean professional text."})
    assert result == {"summary": "Clean professional text."}


def test_apply_variation_to_resume_does_not_mutate_input():
    original_summary = "A results-driven professional."
    data = {"summary": original_summary, "experience": [], "skills": []}
    apply_variation_to_resume(data)
    assert data["summary"] == original_summary

import copy
from app.llm.quality_check import QualityReport, validate_quality, _check_bullets_too_long, _check_recent_exp_prioritized, _check_jd_keywords_present, BULLET_MAX_WORDS

SAMPLE_DRAFT = {
    "candidate_name": "Jane Doe",
    "summary": "Dedicated sales professional with experience in B2B markets.",
    "experience": [
        {
            "title": "Sales Manager",
            "company": "Acme Corp",
            "dates": "2021-2023",
            "bullets": [
                "Managed a team of 10 sales representatives across three regions.",
                "Increased revenue by 25% through targeted outreach campaigns.",
            ],
        },
        {
            "title": "Sales Executive",
            "company": "Beta Ltd",
            "dates": "2018-2021",
            "bullets": [
                "Developed client relationships with 50 enterprise accounts.",
            ],
        },
    ],
    "skills": ["Salesforce", "CRM", "Negotiation"],
    "education": [{"degree": "BBA", "institution": "Delhi University", "year": "2018"}],
}

SAMPLE_ORIGINAL = {"raw_text": "Managed a team of 10 sales reps. Increased revenue by 25%."}


def test_quality_report_fields():
    report = QualityReport(passed=True, issues=[], fixed_draft={})
    assert report.passed is True
    assert report.issues == []
    assert report.fixed_draft == {}


def test_validate_quality_returns_quality_report():
    report = validate_quality(SAMPLE_DRAFT, SAMPLE_ORIGINAL)
    assert isinstance(report, QualityReport)
    assert isinstance(report.passed, bool)
    assert isinstance(report.issues, list)
    assert isinstance(report.fixed_draft, dict)


def test_validate_quality_does_not_mutate_input():
    original_draft = copy.deepcopy(SAMPLE_DRAFT)
    validate_quality(SAMPLE_DRAFT, SAMPLE_ORIGINAL)
    assert SAMPLE_DRAFT == original_draft


def test_bullets_too_long_short_bullet_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    issues = _check_bullets_too_long(draft)
    assert issues == []


def test_bullets_too_long_exactly_30_words_no_issue():
    draft = {
        "experience": [
            {"title": "Manager", "bullets": ["word " * 30]}
        ]
    }
    issues = _check_bullets_too_long(draft)
    assert issues == []


def test_bullets_too_long_31_words_is_auto_fixed():
    long_bullet = " ".join([f"word{i}" for i in range(31)])
    draft = {
        "experience": [
            {"title": "Sales Manager", "bullets": [long_bullet]}
        ]
    }
    issues = _check_bullets_too_long(draft)
    assert len(issues) == 1
    assert issues[0].startswith("[AUTO-FIXED]")
    assert "Sales Manager" in issues[0]


def test_bullets_too_long_mutates_working_draft():
    long_bullet = " ".join([f"word{i}" for i in range(31)])
    draft = {
        "experience": [
            {"title": "Manager", "bullets": [long_bullet]}
        ]
    }
    _check_bullets_too_long(draft)
    trimmed = draft["experience"][0]["bullets"][0]
    assert len(trimmed.split()) == BULLET_MAX_WORDS  # ellipsis is glued to word 30, not a separate token
    assert trimmed.endswith("…")


def test_bullets_too_long_missing_experience_no_crash():
    issues = _check_bullets_too_long({})
    assert issues == []


def test_bullets_too_long_non_string_bullet_no_crash():
    draft = {"experience": [{"title": "Manager", "bullets": [None, 42]}]}
    issues = _check_bullets_too_long(draft)
    assert issues == []


def test_recent_exp_first_role_more_bullets_no_issue():
    draft = {
        "experience": [
            {"title": "Manager", "bullets": ["a", "b", "c"]},
            {"title": "Executive", "bullets": ["x", "y"]},
        ]
    }
    assert _check_recent_exp_prioritized(draft) == []


def test_recent_exp_first_role_equal_bullets_no_issue():
    draft = {
        "experience": [
            {"title": "Manager", "bullets": ["a", "b"]},
            {"title": "Executive", "bullets": ["x", "y"]},
        ]
    }
    assert _check_recent_exp_prioritized(draft) == []


def test_recent_exp_first_role_fewer_bullets_flagged():
    draft = {
        "experience": [
            {"title": "Manager", "bullets": ["a", "b"]},
            {"title": "Executive", "bullets": ["x", "y", "z"]},
        ]
    }
    issues = _check_recent_exp_prioritized(draft)
    assert len(issues) == 1
    assert issues[0].startswith("[NEEDS REVIEW]")
    assert "2" in issues[0] and "3" in issues[0]


def test_recent_exp_single_role_no_issue():
    draft = {"experience": [{"title": "Manager", "bullets": ["a", "b"]}]}
    assert _check_recent_exp_prioritized(draft) == []


def test_recent_exp_missing_experience_no_crash():
    assert _check_recent_exp_prioritized({}) == []


def test_recent_exp_empty_experience_no_crash():
    assert _check_recent_exp_prioritized({"experience": []}) == []


def test_jd_keywords_none_jd_fields_skipped():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    assert _check_jd_keywords_present(draft, None) == []


def test_jd_keywords_empty_required_skills_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    assert _check_jd_keywords_present(draft, {"required_skills": []}) == []


def test_jd_keywords_keyword_in_summary_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    # "sales" is in the summary
    issues = _check_jd_keywords_present(draft, {"required_skills": ["sales"]})
    assert issues == []


def test_jd_keywords_keyword_in_bullets_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    # "revenue" is in a bullet
    issues = _check_jd_keywords_present(draft, {"required_skills": ["revenue"]})
    assert issues == []


def test_jd_keywords_keyword_in_skills_no_issue():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    # "CRM" is in skills
    issues = _check_jd_keywords_present(draft, {"required_skills": ["crm"]})
    assert issues == []


def test_jd_keywords_missing_keyword_flagged():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    issues = _check_jd_keywords_present(draft, {"required_skills": ["stakeholder management"]})
    assert len(issues) == 1
    assert issues[0].startswith("[NEEDS REVIEW]")
    assert "stakeholder management" in issues[0]


def test_jd_keywords_case_insensitive():
    draft = copy.deepcopy(SAMPLE_DRAFT)
    # "Salesforce" in skills, keyword passed as uppercase
    issues = _check_jd_keywords_present(draft, {"required_skills": ["SALESFORCE"]})
    assert issues == []


def test_jd_keywords_missing_experience_no_crash():
    issues = _check_jd_keywords_present({}, {"required_skills": ["python"]})
    assert len(issues) == 1
    assert "python" in issues[0]


from app.llm.quality_check import _check_experience_exaggerated


def test_exaggerated_same_numbers_no_issue():
    # 25% and 10 appear in both original and draft (tokens matched with % suffix)
    bullets = ["Increased revenue by 25% across 10 regions."]
    summary = ""
    original = "Increased revenue by 25% across 10 regions."
    assert _check_experience_exaggerated(bullets, summary, original) == []


def test_exaggerated_new_percentage_flagged():
    bullets = ["Increased revenue by 40%."]
    summary = ""
    original = "Increased revenue through targeted campaigns."  # no 40%
    issues = _check_experience_exaggerated(bullets, summary, original)
    assert any("40%" in i for i in issues)
    assert all(i.startswith("[NEEDS REVIEW]") for i in issues)


def test_exaggerated_new_integer_flagged():
    bullets = ["Managed a team of 200 people."]
    summary = ""
    original = "Managed a small sales team."  # no 200
    issues = _check_experience_exaggerated(bullets, summary, original)
    assert any("200" in i for i in issues)


def test_exaggerated_no_numbers_in_draft_no_issue():
    bullets = ["Led cross-functional initiatives across regions."]
    summary = ""
    original = "Led initiatives with 5 teams."
    assert _check_experience_exaggerated(bullets, summary, original) == []


def test_exaggerated_empty_original_flags_all_draft_numbers():
    bullets = ["Hit 150 percent of quota in Q3."]
    summary = ""
    original = ""
    issues = _check_experience_exaggerated(bullets, summary, original)
    assert len(issues) >= 1  # 150 is new


def test_exaggerated_number_in_summary_checked():
    bullets = []
    summary = "Generated 2000000 in new pipeline."
    original = "Worked on sales pipeline."  # no 2000000
    issues = _check_experience_exaggerated(bullets, summary, original)
    assert any("2000000" in i for i in issues)


from app.llm.quality_check import _check_tone_repetitive, NGRAM_SIZE, WORD_FREQ_THRESHOLD


def test_tone_repetitive_unique_text_no_issue():
    summary = "Dedicated sales professional with B2B expertise."
    experience = [
        {"bullets": ["Increased revenue by 25% across three regions."]},
        {"bullets": ["Developed client relationships with enterprise accounts."]},
    ]
    issues = _check_tone_repetitive(summary, experience)
    assert issues == []


def test_tone_repetitive_ngram_across_sections_flagged():
    # "managed a team of" appears in both summary and a role's bullets
    summary = "Senior leader who managed a team of high performers."
    experience = [
        {"bullets": ["Managed a team of 10 sales representatives."]},
    ]
    issues = _check_tone_repetitive(summary, experience)
    ngram_issues = [i for i in issues if "managed a team of" in i.lower()]
    assert len(ngram_issues) >= 1
    assert all(i.startswith("[NEEDS REVIEW]") for i in ngram_issues)


def test_tone_repetitive_same_ngram_within_one_section_not_flagged():
    # Repetition within one role is not cross-section
    summary = ""
    experience = [
        {"bullets": [
            "Managed a team of five.",
            "Managed a team of ten.",
        ]},
    ]
    issues = _check_tone_repetitive(summary, experience)
    # same ngram within one section only — should NOT be flagged as cross-section
    ngram_issues = [i for i in issues if "Repetitive phrase" in i]
    assert ngram_issues == []


def test_tone_repetitive_word_freq_threshold_flagged():
    # "managed" repeated WORD_FREQ_THRESHOLD times across draft
    repeated_word = "managed"
    summary = f"{repeated_word} budgets effectively."
    bullets = [f"{repeated_word} stakeholders." for _ in range(WORD_FREQ_THRESHOLD - 1)]
    experience = [{"bullets": bullets}]
    issues = _check_tone_repetitive(summary, experience)
    freq_issues = [i for i in issues if repeated_word in i and "times" in i]
    assert len(freq_issues) >= 1


def test_tone_repetitive_word_below_threshold_not_flagged():
    summary = "Led the team."
    experience = [
        {"bullets": ["Led initiatives.", "Led projects."]},
    ]
    # "led" appears 3 times — below default threshold of 4
    issues = _check_tone_repetitive(summary, experience)
    freq_issues = [i for i in issues if "'led'" in i]
    assert freq_issues == []


def test_tone_repetitive_short_text_no_crash():
    # Text shorter than NGRAM_SIZE words
    summary = "Sales."
    experience = [{"bullets": ["Led."]}]
    issues = _check_tone_repetitive(summary, experience)
    assert isinstance(issues, list)


def test_tone_repetitive_missing_bullets_key_no_crash():
    summary = "Professional."
    experience = [{"title": "Manager"}]  # no "bullets" key
    issues = _check_tone_repetitive(summary, experience)
    assert isinstance(issues, list)

# ---------------------------------------------------------------------------
# Helpers shared across all component tests
# ---------------------------------------------------------------------------

def _make_jd(
    job_title="Software Engineer",
    required_skills=None,
    preferred_skills=None,
    key_responsibilities=None,
    experience_required="",
    education_required="",
    company="Acme",
):
    return {
        "job_title": job_title,
        "company": company,
        "required_skills": required_skills or [],
        "preferred_skills": preferred_skills or [],
        "experience_required": experience_required,
        "education_required": education_required,
        "key_responsibilities": key_responsibilities or [],
    }


def _make_resume_fields(
    candidate_name="Alice",
    email="alice@example.com",
    phone="9999999999",
    current_title="Senior Engineer",
    skills=None,
    experience_summary="",
):
    return {
        "candidate_name": candidate_name,
        "email": email,
        "phone": phone,
        "current_title": current_title,
        "skills": skills or [],
        "experience_summary": experience_summary,
    }


# ---------------------------------------------------------------------------
# keyword_match
# ---------------------------------------------------------------------------

def test_keyword_match_full_overlap():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=["build Python microservices", "deploy AWS infrastructure"])
    resume_tokens = _tokenize("build Python microservices deploy AWS infrastructure")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert score == 30
    assert "python" in matched
    assert "aws" in matched


def test_keyword_match_zero_overlap():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=["manage Kubernetes clusters", "deploy Terraform"])
    resume_tokens = _tokenize("Java Spring Boot development")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert score == 0
    assert matched == []


def test_keyword_match_partial_overlap():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=["manage Python services", "build REST APIs"])
    resume_tokens = _tokenize("Python developer REST experience")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert 0 < score < 30
    assert "python" in matched
    assert "rest" in matched


def test_keyword_match_fallback_empty_responsibilities():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=[], job_title="Python Developer")
    resume_tokens = _tokenize("Python developer experience")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert 0 < score <= 15  # fallback fires (not zero) and caps at 15


def test_keyword_match_fallback_completely_empty_jd():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=[], job_title="")
    resume_tokens = _tokenize("anything here")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert score == 15  # neutral when JD has no data


def test_keyword_match_stop_words_excluded():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=["the and or to of in for with is are be by"])
    resume_tokens = set()  # resume has nothing
    score, matched = _score_keyword_match(jd, resume_tokens)
    # All tokens are stop words, so jd_tokens is empty -> neutral
    assert score == 15


def test_keyword_match_caps_at_30():
    from app.scoring.ats_scorer import _score_keyword_match, _tokenize
    jd = _make_jd(key_responsibilities=["python", "aws"])
    resume_tokens = _tokenize("python aws java docker kubernetes terraform ansible")
    score, matched = _score_keyword_match(jd, resume_tokens)
    assert score <= 30


# ---------------------------------------------------------------------------
# skills_coverage
# ---------------------------------------------------------------------------

def test_skills_coverage_full_match():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(required_skills=["Python", "AWS", "Docker"])
    resume = _make_resume_fields(skills=["Python", "AWS", "Docker", "Git"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 24
    assert set(matched) == {"Python", "AWS", "Docker"}
    assert missing == []


def test_skills_coverage_zero_match():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(required_skills=["Kubernetes", "Terraform", "Go"])
    resume = _make_resume_fields(skills=["Python", "Django", "PostgreSQL"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 0
    assert matched == []
    assert set(missing) == {"Kubernetes", "Terraform", "Go"}


def test_skills_coverage_partial_match():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(required_skills=["Python", "AWS", "Docker"])
    resume = _make_resume_fields(skills=["Python", "AWS"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 16   # round(2/3 * 24) = 16
    assert "Python" in matched
    assert "Docker" in missing


def test_skills_coverage_preferred_bonus():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(
        required_skills=["Python", "AWS"],
        preferred_skills=["Docker", "Terraform"],
    )
    resume = _make_resume_fields(skills=["Python", "AWS", "Docker"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    # required: 2/2 * 24 = 24; preferred: 1/2 * 6 = 3; total = 27
    assert score == 27
    assert missing == []


def test_skills_coverage_neutral_when_jd_empty():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(required_skills=[], preferred_skills=[])
    resume = _make_resume_fields(skills=["Python"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 15  # neutral


def test_skills_coverage_substring_match():
    from app.scoring.ats_scorer import _score_skills_coverage
    # "Python 3.10" in JD should match "Python" in resume
    jd = _make_jd(required_skills=["Python 3.10", "AWS S3"])
    resume = _make_resume_fields(skills=["Python", "AWS"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 24
    assert missing == []


def test_skills_coverage_compound_skill_split():
    from app.scoring.ats_scorer import _score_skills_coverage
    # "Python/Django" in resume should match "Django" in JD
    jd = _make_jd(required_skills=["Django", "PostgreSQL"])
    resume = _make_resume_fields(skills=["Python/Django", "PostgreSQL"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 24
    assert missing == []


def test_skills_coverage_caps_at_30():
    from app.scoring.ats_scorer import _score_skills_coverage
    jd = _make_jd(
        required_skills=["Python"],
        preferred_skills=["Docker"],
    )
    resume = _make_resume_fields(skills=["Python", "Docker"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score <= 30


def test_skills_coverage_compound_skill_plus_separator():
    from app.scoring.ats_scorer import _score_skills_coverage
    # "React+Redux" in resume should match "React" in JD (+ is a split delimiter)
    jd = _make_jd(required_skills=["React", "Redux"])
    resume = _make_resume_fields(skills=["React+Redux"])
    score, matched, missing = _score_skills_coverage(jd, resume)
    assert score == 24
    assert missing == []


# ---------------------------------------------------------------------------
# experience_clarity
# ---------------------------------------------------------------------------

def test_experience_clarity_all_signals():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="Senior Engineer")
    text = (
        "Senior Engineer at Acme Ltd 2019-2023\n"
        "Reduced costs by 30% saving $50K annually\n"
        "Managed team at TechCorp Inc"
    )
    score = _score_experience_clarity(resume, text)
    assert score == 20


def test_experience_clarity_no_dates():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="Engineer")
    text = "Engineer at Acme Ltd\nReduced costs by 30%"
    score = _score_experience_clarity(resume, text)
    assert score == 14  # 0+5+5+4


def test_experience_clarity_no_company():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="Engineer")
    text = "Engineer 2019-2022\nIncreased revenue by 20%"
    score = _score_experience_clarity(resume, text)
    assert score == 15  # 6+0+5+4


def test_experience_clarity_no_title():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="")
    text = "Software Engineer at Acme Ltd 2019-2023\nReduced costs 30%"
    score = _score_experience_clarity(resume, text)
    assert score == 15  # 6+5+0+4


def test_experience_clarity_no_achievements():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="Engineer")
    text = "Engineer at Acme Ltd 2019-2022\nWorked on backend systems"
    score = _score_experience_clarity(resume, text)
    assert score == 16  # 6+5+5+0


def test_experience_clarity_zero():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="")
    text = "worked on various projects and tasks"
    score = _score_experience_clarity(resume, text)
    assert score == 0


def test_experience_clarity_date_formats():
    from app.scoring.ats_scorer import _score_experience_clarity
    resume = _make_resume_fields(current_title="")
    # Various date formats (hyphen-dash only; en-dash omitted to avoid encoding issues)
    for text in [
        "Jan 2020 - Dec 2022",
        "2019-Present",
        "2018-2021",
        "March 2017",
    ]:
        score = _score_experience_clarity(resume, text)
        assert score >= 6, f"Expected date detection for: {text!r}"


# ---------------------------------------------------------------------------
# structure_completeness
# ---------------------------------------------------------------------------

def test_structure_completeness_all_sections():
    from app.scoring.ats_scorer import _score_structure_completeness
    text = (
        "Summary\nExperienced engineer.\n"
        "Education\nBachelor of Engineering 2015\n"
        "Technical Skills\nPython, AWS\n"
        "Certifications\nAWS Certified"
    )
    assert _score_structure_completeness(text) == 20


def test_structure_completeness_no_sections():
    from app.scoring.ats_scorer import _score_structure_completeness
    text = "John Doe\njohn@example.com\nWorked at various companies"
    assert _score_structure_completeness(text) == 0


def test_structure_completeness_partial():
    from app.scoring.ats_scorer import _score_structure_completeness
    # Has skills + education but no summary or certifications
    text = "Technical Skills\nPython\nEducation\nMBA from IIM"
    score = _score_structure_completeness(text)
    assert score == 10  # 0+5+5+0


def test_structure_completeness_education_needs_degree_keyword():
    from app.scoring.ats_scorer import _score_structure_completeness
    # Has education header but no degree keyword -> no pts
    text = "Education\nStudied at a good university"
    assert _score_structure_completeness(text) == 0


def test_structure_completeness_certif_prefix_match():
    from app.scoring.ats_scorer import _score_structure_completeness
    # "certifications", "certified", "certificate" all should match
    for word in ["Certifications", "Certified", "Certificate"]:
        text = f"{word}\nAWS Cloud Practitioner"
        score = _score_structure_completeness(text)
        assert score == 5, f"Expected certif match for: {word!r}"


# ---------------------------------------------------------------------------
# compute_ats_score integration
# ---------------------------------------------------------------------------

def test_compute_ats_score_total_in_range():
    from app.scoring.ats_scorer import compute_ats_score
    jd = _make_jd(
        required_skills=["Python", "AWS"],
        key_responsibilities=["build Python services", "deploy AWS infrastructure"],
    )
    resume = _make_resume_fields(
        current_title="Backend Engineer",
        skills=["Python", "AWS", "Docker"],
    )
    raw = (
        "Backend Engineer at Acme Ltd 2020-2023\n"
        "Summary\nSkilled Python developer.\n"
        "Skills\nPython, AWS, Docker\n"
        "Education\nBachelor of Engineering 2016\n"
        "Certifications\nAWS Certified\n"
        "Increased throughput by 40%"
    )
    score = compute_ats_score(resume, jd, raw)
    assert 0 <= score.total <= 100
    assert score.total == (
        score.keyword_match + score.skills_coverage +
        score.experience_clarity + score.structure_completeness
    )


def test_compute_ats_score_returns_ats_score_type():
    from app.scoring.ats_scorer import compute_ats_score
    from app.scoring.models import ATSScore
    jd = _make_jd()
    resume = _make_resume_fields()
    score = compute_ats_score(resume, jd, "some resume text")
    assert isinstance(score, ATSScore)


def test_compute_ats_score_skills_matched_and_missing_populated():
    from app.scoring.ats_scorer import compute_ats_score
    jd = _make_jd(required_skills=["Python", "Kubernetes"])
    resume = _make_resume_fields(skills=["Python"])
    score = compute_ats_score(resume, jd, "Python developer 2020-2023")
    assert "Python" in score.skills_matched
    assert "Kubernetes" in score.skills_missing


def test_compute_ats_score_empty_inputs_do_not_raise():
    from app.scoring.ats_scorer import compute_ats_score
    jd = _make_jd(required_skills=[], key_responsibilities=[])
    resume = _make_resume_fields(current_title="", skills=[])
    score = compute_ats_score(resume, jd, "")
    assert isinstance(score.total, int)
    assert score.total >= 0

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
    assert score <= 15  # fallback caps at 15


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

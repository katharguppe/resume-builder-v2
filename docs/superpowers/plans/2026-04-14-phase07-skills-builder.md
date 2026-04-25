# Phase 7 — Skills Section Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `app/skills/` module (grouper + suggester + YAML keyword files) and `app/ui/pages/5_Skills.py` so candidates can review, edit, and save the skills section of their AI-generated resume.

**Architecture:** Skills are grouped into Core/Tools/Functional/Domain using keyword YAML files loaded at import time. Groups are UI-only; save writes the flat `skills` list back to `llm_output_json`. JD-based suggestions use the EXTRACT provider (two-stage: set-difference + LLM enrichment, with graceful LLM degradation).

**Tech Stack:** Python 3.13, PyYAML, Streamlit, SQLite via `app/state/db.SubmissionsDB`, EXTRACT provider via env var (`LLM_EXTRACT_PROVIDER`)

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `app/skills/__init__.py` | Public exports: `group_skills`, `suggest_skills`, `SkillGroups` |
| Create | `app/skills/grouper.py` | `SkillGroups` dataclass, YAML loader, `group_skills()` |
| Create | `app/skills/suggester.py` | `suggest_skills()` — Stage 1 set-diff + Stage 2 LLM |
| Create | `app/skills/keywords/functional.yaml` | Cross-industry transferable skills |
| Create | `app/skills/keywords/tech.yaml` | Tech: languages, frameworks, DevOps |
| Create | `app/skills/keywords/sales.yaml` | Sales skills, CRM tools, sales domains |
| Create | `app/skills/keywords/marketing.yaml` | Marketing skills, MarTech tools |
| Create | `app/skills/keywords/finance.yaml` | Finance/accounting skills and tools |
| Create | `app/skills/keywords/hr.yaml` | HR/recruitment skills and platforms |
| Create | `app/skills/keywords/education.yaml` | Teaching, curriculum, EdTech |
| Create | `app/skills/keywords/culinary.yaml` | Culinary, hospitality, food service |
| Create | `app/ui/pages/5_Skills.py` | Skills Builder Streamlit page |
| Create | `tests/test_skills_grouper.py` | Grouper unit tests |
| Create | `tests/test_skills_suggester.py` | Suggester unit tests |
| Create | `tests/test_skills_page.py` | Page helper function tests |

**No existing files are modified.**

---

## Task 1: YAML Keyword Files

**Files:** Create all 8 `app/skills/keywords/*.yaml` files.

These are data files — no TDD cycle. The grouper tests in Task 3 validate they load and classify correctly.

- [ ] **Step 1: Create `app/skills/keywords/functional.yaml`**

```yaml
# Cross-industry transferable skills — shared by all domains
functional:
  - leadership
  - communication
  - teamwork
  - collaboration
  - stakeholder management
  - project management
  - program management
  - time management
  - problem solving
  - critical thinking
  - analytical thinking
  - presentation
  - negotiation
  - strategic planning
  - decision making
  - conflict resolution
  - coaching
  - mentoring
  - training
  - budget management
  - vendor management
  - client management
  - customer service
  - relationship building
  - networking
  - adaptability
  - multitasking
  - attention to detail
  - process improvement
  - change management
  - agile
  - scrum
  - kanban
  - lean
  - six sigma
  - cross-functional
  - organizational development
  - people management
  - performance reviews
  - public speaking
  - written communication
```

- [ ] **Step 2: Create `app/skills/keywords/tech.yaml`**

```yaml
core:
  - python
  - java
  - javascript
  - typescript
  - c++
  - c#
  - go
  - rust
  - kotlin
  - swift
  - ruby
  - php
  - scala
  - react
  - angular
  - vue
  - node
  - django
  - flask
  - fastapi
  - spring
  - express
  - sql
  - postgresql
  - mysql
  - mongodb
  - redis
  - sqlite
  - elasticsearch
  - graphql
  - rest
  - grpc
  - tensorflow
  - pytorch
  - scikit-learn
  - pandas
  - numpy
  - keras
  - html
  - css
  - sass
  - tailwind
  - machine learning
  - deep learning
  - nlp
  - computer vision
  - data analysis
  - data engineering
  - etl
tools:
  - git
  - github
  - gitlab
  - bitbucket
  - docker
  - kubernetes
  - helm
  - aws
  - azure
  - gcp
  - terraform
  - ansible
  - jenkins
  - github actions
  - circleci
  - jira
  - confluence
  - figma
  - postman
  - linux
  - bash
  - prometheus
  - grafana
  - datadog
  - splunk
  - vs code
  - intellij
  - pycharm
domain:
  - saas
  - cybersecurity
  - iot
  - blockchain
  - devops
  - cloud computing
  - open source
```

- [ ] **Step 3: Create `app/skills/keywords/sales.yaml`**

```yaml
core:
  - prospecting
  - cold calling
  - account management
  - pipeline management
  - consultative selling
  - quota attainment
  - revenue generation
  - lead generation
  - territory management
  - sales forecasting
  - contract negotiation
  - upselling
  - cross-selling
  - inside sales
  - field sales
  - solution selling
  - value selling
  - sales strategy
  - customer acquisition
  - deal closing
tools:
  - salesforce
  - hubspot
  - pipedrive
  - zoho crm
  - linkedin sales navigator
  - outreach
  - salesloft
  - gong
  - zoominfo
  - apollo
  - microsoft dynamics
domain:
  - b2b
  - b2c
  - saas sales
  - fmcg
  - pharmaceutical sales
  - medical devices
  - retail sales
  - channel sales
  - enterprise sales
  - sme sales
```

- [ ] **Step 4: Create `app/skills/keywords/marketing.yaml`**

```yaml
core:
  - seo
  - sem
  - content marketing
  - email marketing
  - social media marketing
  - brand management
  - market research
  - campaign management
  - digital marketing
  - performance marketing
  - growth hacking
  - a/b testing
  - copywriting
  - marketing strategy
  - product marketing
  - demand generation
  - inbound marketing
  - outbound marketing
  - event marketing
  - public relations
  - media buying
  - influencer marketing
  - brand strategy
  - customer segmentation
  - marketing analytics
tools:
  - google analytics
  - google ads
  - facebook ads
  - mailchimp
  - marketo
  - canva
  - adobe creative suite
  - photoshop
  - illustrator
  - indesign
  - wordpress
  - semrush
  - ahrefs
  - hootsuite
  - tableau
  - power bi
  - hubspot
  - pardot
domain:
  - e-commerce
  - cpg
  - luxury marketing
  - advertising
  - brand marketing
  - media
  - content creation
```

- [ ] **Step 5: Create `app/skills/keywords/finance.yaml`**

```yaml
core:
  - financial modeling
  - financial analysis
  - financial reporting
  - accounting
  - bookkeeping
  - budgeting
  - forecasting
  - variance analysis
  - p&l management
  - cash flow management
  - cost analysis
  - tax preparation
  - auditing
  - reconciliation
  - accounts payable
  - accounts receivable
  - payroll
  - gaap
  - ifrs
  - investment analysis
  - portfolio management
  - risk management
  - valuation
  - due diligence
  - financial planning
  - management accounting
  - treasury management
  - credit analysis
tools:
  - excel
  - sap
  - quickbooks
  - tally
  - netsuite
  - xero
  - bloomberg
  - oracle financials
  - ms dynamics
  - myob
  - power bi
  - tableau
  - pitchbook
domain:
  - banking
  - investment banking
  - private equity
  - venture capital
  - insurance
  - wealth management
  - asset management
  - corporate finance
  - financial services
  - fintech
  - audit
  - tax
```

- [ ] **Step 6: Create `app/skills/keywords/hr.yaml`**

```yaml
core:
  - recruitment
  - talent acquisition
  - talent management
  - performance management
  - employee relations
  - compensation and benefits
  - onboarding
  - learning and development
  - workforce planning
  - succession planning
  - hr policies
  - job descriptions
  - interviewing
  - employer branding
  - employee engagement
  - diversity and inclusion
  - organizational development
  - hr strategy
  - exit interviews
  - hr compliance
  - grievance handling
tools:
  - workday
  - bamboohr
  - greenhouse
  - lever
  - taleo
  - peoplesoft
  - oracle hcm
  - sap successfactors
  - linkedin recruiter
  - indeed
  - mercer
domain:
  - staffing
  - executive search
  - corporate hr
  - hr consulting
  - talent management
  - people operations
```

- [ ] **Step 7: Create `app/skills/keywords/education.yaml`**

```yaml
core:
  - curriculum development
  - lesson planning
  - classroom management
  - student assessment
  - instructional design
  - differentiated instruction
  - special education
  - iep
  - e-learning
  - professional development
  - academic advising
  - student counseling
  - parent communication
  - school administration
  - educational technology
  - stem
  - literacy
  - numeracy
  - behaviour management
  - formative assessment
tools:
  - google classroom
  - canvas
  - blackboard
  - moodle
  - zoom
  - microsoft teams
  - smart board
  - kahoot
  - edmodo
domain:
  - k-12
  - higher education
  - early childhood
  - special needs education
  - stem education
  - adult education
  - corporate training
  - vocational training
```

- [ ] **Step 8: Create `app/skills/keywords/culinary.yaml`**

```yaml
core:
  - knife skills
  - menu development
  - food safety
  - haccp
  - recipe development
  - food cost management
  - catering
  - banquet management
  - pastry
  - baking
  - grilling
  - sauce preparation
  - meal prep
  - food plating
  - kitchen management
  - inventory management
  - butchery
  - sous vide
  - garde manger
  - food allergies management
tools:
  - pos systems
  - kitchen display system
  - micros
  - toast pos
domain:
  - fine dining
  - casual dining
  - hotel
  - restaurant
  - food and beverage
  - bakery
  - catering service
  - hospitality
  - fast casual
```

- [ ] **Step 9: Commit keyword files**

```bash
git add app/skills/keywords/
git commit -m "[PHASE-07] add: skills keyword YAML files for 8 industry domains"
```

---

## Task 2: SkillGroups Dataclass + YAML Loader (TDD)

**Files:**
- Create: `app/skills/grouper.py`
- Create: `tests/test_skills_grouper.py` (partial — dataclass + loader tests)

- [ ] **Step 1: Write failing tests for SkillGroups dataclass and YAML loading**

Create `tests/test_skills_grouper.py`:

```python
"""Tests for app/skills/grouper.py — SkillGroups dataclass and YAML loader."""
import pytest
from pathlib import Path


def test_skillgroups_dataclass_has_four_buckets():
    from app.skills.grouper import SkillGroups
    sg = SkillGroups()
    assert hasattr(sg, "core")
    assert hasattr(sg, "tools")
    assert hasattr(sg, "functional")
    assert hasattr(sg, "domain")


def test_skillgroups_all_buckets_are_lists():
    from app.skills.grouper import SkillGroups
    sg = SkillGroups()
    assert isinstance(sg.core, list)
    assert isinstance(sg.tools, list)
    assert isinstance(sg.functional, list)
    assert isinstance(sg.domain, list)


def test_skillgroups_default_buckets_are_empty():
    from app.skills.grouper import SkillGroups
    sg = SkillGroups()
    assert sg.core == []
    assert sg.tools == []
    assert sg.functional == []
    assert sg.domain == []


def test_keyword_sets_loaded_on_import():
    from app.skills.grouper import _KEYWORD_SETS
    # At least one keyword in each group from the YAML files
    assert len(_KEYWORD_SETS["core"]) > 0
    assert len(_KEYWORD_SETS["tools"]) > 0
    assert len(_KEYWORD_SETS["functional"]) > 0
    assert len(_KEYWORD_SETS["domain"]) > 0


def test_keyword_sets_contain_cross_industry_terms():
    from app.skills.grouper import _KEYWORD_SETS
    # Functional: always present regardless of domain
    assert "leadership" in _KEYWORD_SETS["functional"]
    assert "communication" in _KEYWORD_SETS["functional"]


def test_keyword_sets_contain_non_tech_terms():
    from app.skills.grouper import _KEYWORD_SETS
    # Sales
    assert "prospecting" in _KEYWORD_SETS["core"]
    # Finance
    assert "financial modeling" in _KEYWORD_SETS["core"]
    # HR
    assert "recruitment" in _KEYWORD_SETS["core"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skills_grouper.py -v
```

Expected: `ModuleNotFoundError` — `app/skills/grouper.py` does not exist yet.

- [ ] **Step 3: Create `app/skills/__init__.py` (empty placeholder)**

```python
# app/skills/__init__.py
```

- [ ] **Step 4: Create `app/skills/grouper.py` with SkillGroups + loader**

```python
"""
Skills grouper — classifies a flat skill list into Core/Tools/Functional/Domain.

Groups are loaded from YAML files in app/skills/keywords/ at module import.
Adding a new industry domain = drop a new .yaml file in that directory.
No code changes required.

Groups are UI-only. They are never persisted to the DB.
"""
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

import yaml

logger = logging.getLogger(__name__)

KEYWORDS_DIR = Path(__file__).parent / "keywords"


@dataclass
class SkillGroups:
    """Flat skills list partitioned into four display buckets."""
    core: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    functional: List[str] = field(default_factory=list)
    domain: List[str] = field(default_factory=list)


def _load_keyword_sets() -> Dict[str, Set[str]]:
    """Load and merge all YAML files from keywords/ into four sets (lowercased)."""
    sets: Dict[str, Set[str]] = {
        "core": set(),
        "tools": set(),
        "functional": set(),
        "domain": set(),
    }
    for yaml_file in sorted(KEYWORDS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            for group in ("core", "tools", "functional", "domain"):
                for kw in data.get(group, []):
                    sets[group].add(str(kw).lower())
        except Exception as e:
            logger.warning("Failed to load keyword file %s: %s", yaml_file.name, e)
    return sets


# Loaded once at module import — cheap in-process, no I/O on page reruns.
_KEYWORD_SETS: Dict[str, Set[str]] = _load_keyword_sets()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_skills_grouper.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/skills/__init__.py app/skills/grouper.py tests/test_skills_grouper.py
git commit -m "[PHASE-07] add: SkillGroups dataclass + YAML keyword loader"
```

---

## Task 3: group_skills Keyword Matching (TDD)

**Files:**
- Modify: `app/skills/grouper.py` (add `_matches` + `group_skills`)
- Modify: `tests/test_skills_grouper.py` (add matching tests)

- [ ] **Step 1: Add matching tests to `tests/test_skills_grouper.py`**

Append these tests to the existing file:

```python
# ── group_skills tests ──────────────────────────────────────────────────────

def test_group_skills_empty_input():
    from app.skills.grouper import group_skills
    result = group_skills([])
    assert result.core == []
    assert result.tools == []
    assert result.functional == []
    assert result.domain == []


def test_tech_skill_classified_as_core():
    from app.skills.grouper import group_skills
    result = group_skills(["Python"])
    assert "Python" in result.core


def test_sales_tool_classified_as_tools():
    from app.skills.grouper import group_skills
    result = group_skills(["Salesforce"])
    assert "Salesforce" in result.tools


def test_functional_skill_classified_correctly():
    from app.skills.grouper import group_skills
    result = group_skills(["Leadership"])
    assert "Leadership" in result.functional


def test_domain_keyword_classified_correctly():
    from app.skills.grouper import group_skills
    result = group_skills(["FMCG"])
    assert "FMCG" in result.domain


def test_unknown_skill_falls_to_core():
    from app.skills.grouper import group_skills
    result = group_skills(["Extreme Ironing Championship"])
    assert "Extreme Ironing Championship" in result.core
    assert "Extreme Ironing Championship" not in result.tools
    assert "Extreme Ironing Championship" not in result.functional
    assert "Extreme Ironing Championship" not in result.domain


def test_case_insensitive_matching_preserves_original_casing():
    from app.skills.grouper import group_skills
    result = group_skills(["PYTHON", "SALESFORCE"])
    assert "PYTHON" in result.core   # original casing preserved
    assert "SALESFORCE" in result.tools


def test_mixed_industry_skills_split_correctly():
    from app.skills.grouper import group_skills
    skills = ["Python", "Salesforce", "Leadership", "Banking"]
    result = group_skills(skills)
    assert "Python" in result.core
    assert "Salesforce" in result.tools
    assert "Leadership" in result.functional
    assert "Banking" in result.domain


def test_skill_assigned_to_exactly_one_bucket():
    from app.skills.grouper import group_skills
    result = group_skills(["Python", "Salesforce", "Leadership", "Banking"])
    all_skills = result.core + result.tools + result.functional + result.domain
    assert len(all_skills) == 4  # no skill duplicated across buckets


def test_non_tech_core_skill_classified_correctly():
    from app.skills.grouper import group_skills
    # Finance skill from finance.yaml
    result = group_skills(["Financial Modeling"])
    assert "Financial Modeling" in result.core


def test_education_core_skill_classified_correctly():
    from app.skills.grouper import group_skills
    result = group_skills(["Curriculum Development"])
    assert "Curriculum Development" in result.core


def test_culinary_core_skill_classified_correctly():
    from app.skills.grouper import group_skills
    result = group_skills(["Menu Development"])
    assert "Menu Development" in result.core


def test_partial_word_does_not_false_match():
    from app.skills.grouper import group_skills
    # "go" should not match inside "Django" or "MongoDB"
    result = group_skills(["Django", "MongoDB"])
    # Django is in tech core, MongoDB is in tech core — they should not fall
    # into domain or tools due to spurious "go" or "mongo" partial matches
    assert "Django" in result.core
    assert "MongoDB" in result.core
```

- [ ] **Step 2: Run tests to verify new tests fail**

```bash
python -m pytest tests/test_skills_grouper.py -v
```

Expected: The new `group_skills` tests fail with `ImportError` or `AttributeError` — `group_skills` not yet defined.

- [ ] **Step 3: Add `_matches` and `group_skills` to `app/skills/grouper.py`**

Append to the existing `grouper.py` (after `_KEYWORD_SETS` definition):

```python

def _matches(skill_lower: str, keyword_set: Set[str]) -> bool:
    """Return True if skill_lower contains any keyword as a whole word."""
    for kw in keyword_set:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, skill_lower):
            return True
    return False


def group_skills(raw_skills: List[str]) -> SkillGroups:
    """
    Classify a flat list of skills into Core / Tools / Functional / Domain.

    Matching order: Core → Tools → Functional → Domain → Core (default).
    Original casing is preserved in output.
    Unknown skills fall to Core.
    """
    result = SkillGroups()
    for skill in raw_skills:
        skill_lower = skill.lower()
        if _matches(skill_lower, _KEYWORD_SETS["core"]):
            result.core.append(skill)
        elif _matches(skill_lower, _KEYWORD_SETS["tools"]):
            result.tools.append(skill)
        elif _matches(skill_lower, _KEYWORD_SETS["functional"]):
            result.functional.append(skill)
        elif _matches(skill_lower, _KEYWORD_SETS["domain"]):
            result.domain.append(skill)
        else:
            result.core.append(skill)  # default bucket
    return result
```

- [ ] **Step 4: Run all grouper tests**

```bash
python -m pytest tests/test_skills_grouper.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
python -m pytest -v
```

Expected: all 230 existing tests + new grouper tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/skills/grouper.py tests/test_skills_grouper.py
git commit -m "[PHASE-07] add: group_skills keyword matching with whole-word regex"
```

---

## Task 4: suggest_skills — Stage 1 Set Difference (TDD)

**Files:**
- Create: `app/skills/suggester.py`
- Create: `tests/test_skills_suggester.py` (Stage 1 tests)

- [ ] **Step 1: Write failing Stage 1 tests**

Create `tests/test_skills_suggester.py`:

```python
"""Tests for app/skills/suggester.py."""
import pytest
from unittest.mock import patch


# ── Stage 1: set-difference tests ──────────────────────────────────────────

def test_stage1_returns_jd_skills_not_in_resume():
    from app.skills.suggester import _stage1_diff
    jd_fields = {"required_skills": ["SQL", "Python", "AWS"], "preferred_skills": []}
    resume_fields = {"skills": ["Python"]}
    result = _stage1_diff(jd_fields, resume_fields)
    assert "SQL" in result
    assert "AWS" in result
    assert "Python" not in result


def test_stage1_case_insensitive():
    from app.skills.suggester import _stage1_diff
    jd_fields = {"required_skills": ["python"], "preferred_skills": []}
    resume_fields = {"skills": ["Python"]}
    result = _stage1_diff(jd_fields, resume_fields)
    assert result == []


def test_stage1_includes_preferred_skills():
    from app.skills.suggester import _stage1_diff
    jd_fields = {"required_skills": [], "preferred_skills": ["Tableau"]}
    resume_fields = {"skills": []}
    result = _stage1_diff(jd_fields, resume_fields)
    assert "Tableau" in result


def test_stage1_empty_jd_fields():
    from app.skills.suggester import _stage1_diff
    result = _stage1_diff({}, {"skills": ["Python"]})
    assert result == []


def test_stage1_empty_resume_skills():
    from app.skills.suggester import _stage1_diff
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    result = _stage1_diff(jd_fields, {})
    assert "SQL" in result


def test_stage1_returns_list_of_strings():
    from app.skills.suggester import _stage1_diff
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    result = _stage1_diff(jd_fields, {})
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skills_suggester.py -v
```

Expected: `ModuleNotFoundError` — `app/skills/suggester.py` does not exist.

- [ ] **Step 3: Create `app/skills/suggester.py` with Stage 1**

```python
"""
Skills suggester — surfaces JD-relevant skills missing from the resume.

Two-stage approach:
  Stage 1: Set-difference between jd_fields skills and resume skills (no LLM).
  Stage 2: LLM enrichment via EXTRACT provider (Gemini Flash or Claude Haiku).

If Stage 2 fails for any reason, Stage 1 results are returned (graceful degradation).
Suggestions are hints only — the candidate controls the final list.
"""
import json
import logging
import os
import re
from typing import List

logger = logging.getLogger(__name__)

MAX_SUGGESTIONS = 10
_MAX_LLM_SUGGESTIONS = 8


def _normalise(s: str) -> str:
    return s.lower().strip()


def _stage1_diff(jd_fields: dict, resume_fields: dict) -> List[str]:
    """
    Return JD skills not already present in the resume (case-insensitive).
    Covers both required_skills and preferred_skills from jd_fields.
    """
    required = jd_fields.get("required_skills") or []
    preferred = jd_fields.get("preferred_skills") or []
    jd_all = required + preferred

    resume_normalised = {_normalise(s) for s in (resume_fields.get("skills") or [])}
    return [s for s in jd_all if _normalise(s) not in resume_normalised]
```

- [ ] **Step 4: Run Stage 1 tests**

```bash
python -m pytest tests/test_skills_suggester.py -v
```

Expected: all 6 Stage 1 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/skills/suggester.py tests/test_skills_suggester.py
git commit -m "[PHASE-07] add: suggest_skills Stage 1 set-difference"
```

---

## Task 5: suggest_skills — Stage 2 LLM + Full Function (TDD)

**Files:**
- Modify: `app/skills/suggester.py` (add Stage 2 + `suggest_skills`)
- Modify: `tests/test_skills_suggester.py` (add Stage 2 + integration tests)

- [ ] **Step 1: Add Stage 2 and integration tests**

Append to `tests/test_skills_suggester.py`:

```python

# ── Stage 2 + full suggest_skills tests ────────────────────────────────────

def test_suggest_skills_caps_at_10():
    from app.skills.suggester import suggest_skills
    jd_fields = {
        "required_skills": [f"Skill{i}" for i in range(20)],
        "preferred_skills": [],
    }
    resume_fields = {"skills": []}
    with patch("app.skills.suggester._stage2_llm", return_value=[]):
        result = suggest_skills(jd_fields, resume_fields)
    assert len(result) <= 10


def test_suggest_skills_deduplicates_with_resume():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["Python", "SQL"], "preferred_skills": []}
    resume_fields = {"skills": ["Python"]}
    with patch("app.skills.suggester._stage2_llm", return_value=["Python"]):
        result = suggest_skills(jd_fields, resume_fields)
    assert "Python" not in result


def test_suggest_skills_llm_failure_returns_stage1():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["SQL", "AWS"], "preferred_skills": []}
    resume_fields = {"skills": []}
    with patch("app.skills.suggester._stage2_llm", side_effect=Exception("LLM down")):
        result = suggest_skills(jd_fields, resume_fields)
    assert "SQL" in result
    assert "AWS" in result


def test_suggest_skills_returns_list_of_strings():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    resume_fields = {"skills": []}
    with patch("app.skills.suggester._stage2_llm", return_value=[]):
        result = suggest_skills(jd_fields, resume_fields)
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)


def test_suggest_skills_merges_stage1_and_stage2():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    resume_fields = {"skills": []}
    with patch("app.skills.suggester._stage2_llm", return_value=["Tableau"]):
        result = suggest_skills(jd_fields, resume_fields)
    assert "SQL" in result
    assert "Tableau" in result


def test_suggest_skills_no_duplicates_between_stages():
    from app.skills.suggester import suggest_skills
    jd_fields = {"required_skills": ["SQL"], "preferred_skills": []}
    resume_fields = {"skills": []}
    with patch("app.skills.suggester._stage2_llm", return_value=["SQL"]):
        result = suggest_skills(jd_fields, resume_fields)
    assert result.count("SQL") == 1


def test_suggest_skills_empty_inputs():
    from app.skills.suggester import suggest_skills
    with patch("app.skills.suggester._stage2_llm", return_value=[]):
        result = suggest_skills({}, {})
    assert result == []
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
python -m pytest tests/test_skills_suggester.py -v
```

Expected: new tests fail — `suggest_skills` and `_stage2_llm` not yet defined.

- [ ] **Step 3: Add Stage 2 and `suggest_skills` to `app/skills/suggester.py`**

Append to the existing `suggester.py`:

```python

def _build_suggestion_prompt(jd_fields: dict, resume_fields: dict) -> str:
    job_title = jd_fields.get("job_title") or "this role"
    jd_skills = (jd_fields.get("required_skills") or []) + (jd_fields.get("preferred_skills") or [])
    resume_skills = resume_fields.get("skills") or []
    return (
        f"Job title: {job_title}\n"
        f"Job requires: {', '.join(jd_skills)}\n"
        f"Candidate already has: {', '.join(resume_skills)}\n\n"
        f"Suggest up to {_MAX_LLM_SUGGESTIONS} additional skills the candidate could highlight "
        "if they genuinely have them. Only suggest skills relevant to this job and not already listed. "
        "Return a JSON array of strings only. No markdown, no explanation."
    )


def _strip_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.DOTALL)


def _stage2_claude(jd_fields: dict, resume_fields: dict) -> List[str]:
    import anthropic
    from app.config import config
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = _build_suggestion_prompt(jd_fields, resume_fields)
    response = client.messages.create(
        model=config.LLM_EXTRACT_MODEL,
        max_tokens=256,
        system="You are a skills advisor. Respond ONLY with a valid JSON array of strings.",
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(_strip_fences(response.content[0].text))


def _stage2_gemini(jd_fields: dict, resume_fields: dict) -> List[str]:
    import google.generativeai as genai
    from app.config import config
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.LLM_GEMINI_EXTRACT_MODEL)
    prompt = _build_suggestion_prompt(jd_fields, resume_fields)
    response = model.generate_content(prompt)
    return json.loads(_strip_fences(response.text))


def _stage2_llm(jd_fields: dict, resume_fields: dict) -> List[str]:
    """Call EXTRACT provider for additional skill suggestions beyond set-difference."""
    provider = os.getenv("LLM_EXTRACT_PROVIDER", "claude").lower()
    if provider == "gemini":
        return _stage2_gemini(jd_fields, resume_fields)
    return _stage2_claude(jd_fields, resume_fields)


def suggest_skills(jd_fields: dict, resume_fields: dict) -> List[str]:
    """
    Return up to MAX_SUGGESTIONS skills missing from resume but relevant to the JD.

    Stage 1 (no LLM): set-difference of JD required/preferred skills vs resume skills.
    Stage 2 (LLM): EXTRACT provider enrichment for implied/adjacent skills.
    If Stage 2 fails, returns Stage 1 results only (graceful degradation).
    """
    resume_normalised = {_normalise(s) for s in (resume_fields.get("skills") or [])}

    stage1 = _stage1_diff(jd_fields, resume_fields)

    try:
        stage2 = _stage2_llm(jd_fields, resume_fields)
    except Exception as e:
        logger.warning("Stage 2 LLM suggestion failed, using Stage 1 only: %s", e)
        stage2 = []

    seen: set = set(resume_normalised)
    merged: List[str] = []
    for s in stage1 + stage2:
        key = _normalise(s)
        if key not in seen:
            seen.add(key)
            merged.append(s)
        if len(merged) >= MAX_SUGGESTIONS:
            break

    return merged
```

- [ ] **Step 4: Run all suggester tests**

```bash
python -m pytest tests/test_skills_suggester.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest -v
```

Expected: all tests PASS (230 existing + new).

- [ ] **Step 6: Commit**

```bash
git add app/skills/suggester.py tests/test_skills_suggester.py
git commit -m "[PHASE-07] add: suggest_skills Stage 2 LLM enrichment + full integration"
```

---

## Task 6: app/skills/__init__.py Exports

**Files:**
- Modify: `app/skills/__init__.py`

- [ ] **Step 1: Update `app/skills/__init__.py` with public exports**

```python
"""
app/skills — Skills grouper and suggester for Phase 7 Skills Builder.

Public API:
    group_skills(raw_skills: List[str]) -> SkillGroups
    suggest_skills(jd_fields: dict, resume_fields: dict) -> List[str]
    SkillGroups (dataclass: core, tools, functional, domain)
"""
from app.skills.grouper import group_skills, SkillGroups
from app.skills.suggester import suggest_skills

__all__ = ["group_skills", "suggest_skills", "SkillGroups"]
```

- [ ] **Step 2: Verify imports work**

```bash
python -c "from app.skills import group_skills, suggest_skills, SkillGroups; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/skills/__init__.py
git commit -m "[PHASE-07] add: app/skills public exports"
```

---

## Task 7: 5_Skills.py Helper Functions (TDD)

**Files:**
- Create: `app/ui/pages/5_Skills.py` (helpers + stubs)
- Create: `tests/test_skills_page.py`

The page has two testable helpers extracted at module level (same pattern as `3_Review.py`):
- `_init_skills_state(llm_output_json: str) -> List[str]` — parse skills from JSON
- `_save_skills(subs_db, submission_id: int, llm_output_json_str: str, new_skills: List[str]) -> None` — persist

- [ ] **Step 1: Write failing helper tests**

Create `tests/test_skills_page.py`:

```python
"""
Tests for helper functions in app/ui/pages/5_Skills.py.

Streamlit is stubbed out so the page module can be imported safely.
Only pure helper functions are tested here — no st.* calls.
"""
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Stub streamlit before page import ─────────────────────────────────────
_st_mock = MagicMock()
_st_mock.session_state = {}
_st_mock.stop = MagicMock()
sys.modules["streamlit"] = _st_mock

# ── Import the skills page module ──────────────────────────────────────────
import importlib.util as _ilu
_page_path = Path(__file__).parent.parent / "app" / "ui" / "pages" / "5_Skills.py"
_spec = _ilu.spec_from_file_location("skills_page_module", str(_page_path))
_skills_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_skills_mod)

_init_skills_state = _skills_mod._init_skills_state
_save_skills = _skills_mod._save_skills


# ── Fixtures ───────────────────────────────────────────────────────────────

from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionStatus


@pytest.fixture
def db_and_submission(tmp_path):
    db_path = tmp_path / "test.db"
    auth_db = AuthDB(db_path)
    subs_db = SubmissionsDB(db_path)
    user_id = auth_db.create_user("test@x.com")
    sub_id = subs_db.create_submission(user_id=user_id, session_token="tok-skills")
    llm_output = {
        "candidate_name": "Alice",
        "contact": {"email": "a@b.com", "phone": "123", "linkedin": ""},
        "summary": "Summary text",
        "experience": [],
        "education": [],
        "skills": ["Python", "Leadership", "Salesforce"],
        "missing_fields": [],
    }
    subs_db.update_submission(sub_id, {"llm_output_json": json.dumps(llm_output)})
    subs_db.set_status(sub_id, SubmissionStatus.REVIEW_READY)
    return subs_db, sub_id, llm_output


# ── _init_skills_state ─────────────────────────────────────────────────────

def test_init_skills_state_returns_skills_list(db_and_submission):
    subs_db, sub_id, llm_output = db_and_submission
    result = _init_skills_state(json.dumps(llm_output))
    assert result == ["Python", "Leadership", "Salesforce"]


def test_init_skills_state_empty_skills():
    llm_output = {"skills": []}
    result = _init_skills_state(json.dumps(llm_output))
    assert result == []


def test_init_skills_state_missing_skills_key():
    result = _init_skills_state(json.dumps({}))
    assert result == []


def test_init_skills_state_returns_list():
    result = _init_skills_state(json.dumps({"skills": ["A", "B"]}))
    assert isinstance(result, list)


# ── _save_skills ───────────────────────────────────────────────────────────

def test_save_skills_persists_flat_list(db_and_submission):
    subs_db, sub_id, llm_output = db_and_submission
    new_skills = ["Python", "SQL", "Leadership"]
    _save_skills(subs_db, sub_id, json.dumps(llm_output), new_skills)

    updated = subs_db.get_submission(sub_id)
    saved = json.loads(updated.llm_output_json)
    assert saved["skills"] == ["Python", "SQL", "Leadership"]


def test_save_skills_preserves_other_llm_output_fields(db_and_submission):
    subs_db, sub_id, llm_output = db_and_submission
    _save_skills(subs_db, sub_id, json.dumps(llm_output), ["NewSkill"])

    updated = subs_db.get_submission(sub_id)
    saved = json.loads(updated.llm_output_json)
    assert saved["candidate_name"] == "Alice"
    assert saved["summary"] == "Summary text"


def test_save_skills_empty_list(db_and_submission):
    subs_db, sub_id, llm_output = db_and_submission
    _save_skills(subs_db, sub_id, json.dumps(llm_output), [])

    updated = subs_db.get_submission(sub_id)
    saved = json.loads(updated.llm_output_json)
    assert saved["skills"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skills_page.py -v
```

Expected: fail — `5_Skills.py` does not exist.

- [ ] **Step 3: Create `app/ui/pages/5_Skills.py` with helpers (stubs for render)**

```python
"""
Phase 7 — Skills Builder Page

Candidate reviews, edits, and saves the skills section of their AI resume.
Groups are derived in-process from YAML keyword files (Core/Tools/Functional/Domain).
Suggestions come from the JD via the EXTRACT provider.

Session state:
  st.session_state["skills_working"]     : List[str] — live working copy
  st.session_state["skills_suggestions"] : List[str] — JD hints, loaded once
"""
import json
import logging
import os
from pathlib import Path
from typing import List

import streamlit as st

from app.skills import group_skills, suggest_skills
from app.state.db import AuthDB, SubmissionsDB
from app.state.models import SubmissionStatus

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))


# ── Testable helpers (no st.* calls) ──────────────────────────────────────

def _init_skills_state(llm_output_json_str: str) -> List[str]:
    """Extract skills list from llm_output_json string. Returns [] on any error."""
    try:
        data = json.loads(llm_output_json_str or "{}")
        return list(data.get("skills") or [])
    except (json.JSONDecodeError, TypeError):
        return []


def _save_skills(
    subs_db: SubmissionsDB,
    submission_id: int,
    llm_output_json_str: str,
    new_skills: List[str],
) -> None:
    """
    Patch skills key in llm_output_json and persist to DB.
    All other fields in llm_output_json are preserved unchanged.
    """
    try:
        data = json.loads(llm_output_json_str or "{}")
    except (json.JSONDecodeError, TypeError):
        data = {}
    data["skills"] = new_skills
    subs_db.update_submission(submission_id, {"llm_output_json": json.dumps(data)})


# ── Page entry point ───────────────────────────────────────────────────────

def main():
    st.title("Skills Builder")
    st.caption("Review and refine the skills on your resume.")

    session_token = st.session_state.get("session_token")
    if not session_token:
        st.warning("Please log in first.")
        st.stop()

    auth_db = AuthDB(DB_PATH)
    subs_db = SubmissionsDB(DB_PATH)

    user = auth_db.get_user_by_token(session_token)
    if not user:
        st.warning("Session expired. Please log in again.")
        st.stop()

    submission = subs_db.get_latest_submission(user.id)
    accessible_statuses = {
        SubmissionStatus.REVIEW_READY,
        SubmissionStatus.REVISION_REQUESTED,
        SubmissionStatus.REVISION_EXHAUSTED,
        SubmissionStatus.ACCEPTED,
    }
    if not submission or submission.status not in accessible_statuses:
        st.info("No resume ready yet. Please upload and process your resume first.")
        st.stop()

    # ── Initialise session state (once per page load) ──────────────────────
    if "skills_working" not in st.session_state:
        st.session_state["skills_working"] = _init_skills_state(
            submission.llm_output_json or "{}"
        )
    if "skills_suggestions" not in st.session_state:
        resume_fields = json.loads(submission.resume_fields_json or "{}")
        jd_fields = json.loads(submission.jd_fields_json or "{}")
        with st.spinner("Loading suggestions from your Job Description..."):
            st.session_state["skills_suggestions"] = suggest_skills(jd_fields, resume_fields)

    working: List[str] = st.session_state["skills_working"]
    suggestions: List[str] = st.session_state["skills_suggestions"]

    # ── Layout ─────────────────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        _render_current_skills(working)

    with col_right:
        _render_suggestions(working, suggestions)

    st.divider()
    if st.button("Save Skills", type="primary", use_container_width=True):
        _save_skills(subs_db, submission.id, submission.llm_output_json or "{}", working)
        st.toast("Skills saved.")


def _render_current_skills(working: List[str]) -> None:
    st.subheader("Your Skills")
    groups = group_skills(working)

    for group_name, bucket in [
        ("Core", groups.core),
        ("Tools", groups.tools),
        ("Functional", groups.functional),
        ("Domain", groups.domain),
    ]:
        with st.expander(f"{group_name} ({len(bucket)})", expanded=True):
            for skill in list(bucket):
                c1, c2 = st.columns([5, 1])
                c1.write(skill)
                if c2.button("✕", key=f"remove_{skill}", help=f"Remove {skill}"):
                    if skill in st.session_state["skills_working"]:
                        st.session_state["skills_working"].remove(skill)
                    st.rerun()

    st.divider()
    with st.form("add_skill_form", clear_on_submit=True):
        new_skill = st.text_input("Add a skill", placeholder="e.g. Budget Management")
        if st.form_submit_button("Add") and new_skill.strip():
            if new_skill.strip() not in st.session_state["skills_working"]:
                st.session_state["skills_working"].append(new_skill.strip())
            st.rerun()


def _render_suggestions(working: List[str], suggestions: List[str]) -> None:
    st.subheader("Suggested from JD")
    working_lower = {s.lower() for s in working}
    pending = [s for s in suggestions if s.lower() not in working_lower]

    if not pending:
        st.caption("No additional suggestions — your skills look well-matched to the JD.")
        return

    for suggestion in pending:
        c1, c2 = st.columns([5, 1])
        c1.write(suggestion)
        if c2.button("+", key=f"add_sug_{suggestion}", help=f"Add {suggestion}"):
            if suggestion not in st.session_state["skills_working"]:
                st.session_state["skills_working"].append(suggestion)
            st.rerun()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run helper tests**

```bash
python -m pytest tests/test_skills_page.py -v
```

Expected: all helper tests PASS.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/ui/pages/5_Skills.py tests/test_skills_page.py
git commit -m "[PHASE-07] add: 5_Skills.py page with helpers + page tests"
```

---

## Task 8: Additional Page Behaviour Tests

**Files:**
- Modify: `tests/test_skills_page.py` (add add/remove + suggestions panel tests)

- [ ] **Step 1: Append remaining page tests to `tests/test_skills_page.py`**

```python

# ── _init_skills_state edge cases ──────────────────────────────────────────

def test_init_skills_state_invalid_json():
    result = _init_skills_state("not-json")
    assert result == []


def test_init_skills_state_null_input():
    result = _init_skills_state(None)
    assert result == []


# ── _save_skills edge cases ────────────────────────────────────────────────

def test_save_skills_with_invalid_existing_json(db_and_submission):
    subs_db, sub_id, _ = db_and_submission
    _save_skills(subs_db, sub_id, "INVALID_JSON", ["Python"])
    updated = subs_db.get_submission(sub_id)
    saved = json.loads(updated.llm_output_json)
    assert saved["skills"] == ["Python"]


def test_save_skills_preserves_skills_order(db_and_submission):
    subs_db, sub_id, llm_output = db_and_submission
    ordered = ["Zulu", "Alpha", "Mango"]
    _save_skills(subs_db, sub_id, json.dumps(llm_output), ordered)
    updated = subs_db.get_submission(sub_id)
    saved = json.loads(updated.llm_output_json)
    assert saved["skills"] == ["Zulu", "Alpha", "Mango"]
```

- [ ] **Step 2: Run updated tests**

```bash
python -m pytest tests/test_skills_page.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run full suite and confirm count**

```bash
python -m pytest -v
```

Expected: 260+ tests passing (230 baseline + ~30 new).

- [ ] **Step 4: Commit**

```bash
git add tests/test_skills_page.py
git commit -m "[PHASE-07] add: additional edge case tests for skills page helpers"
```

---

## Task 9: Acceptance Criteria Verification

- [ ] **Step 1: Verify grouper acceptance criteria**

```bash
python -c "
from app.skills import group_skills

# Tech + sales + functional + domain
r = group_skills(['Python', 'Salesforce', 'Leadership', 'Banking'])
print('Python in core:', 'Python' in r.core)
print('Salesforce in tools:', 'Salesforce' in r.tools)
print('Leadership in functional:', 'Leadership' in r.functional)
print('Banking in domain:', 'Banking' in r.domain)

# Non-tech defaults to Core
r2 = group_skills(['Sous Vide', 'Menu Planning'])
print('Sous Vide in core:', 'Sous Vide' in r2.core)
"
```

Expected output:
```
Python in core: True
Salesforce in tools: True
Leadership in functional: True
Banking in domain: True
Sous Vide in core: True
```

- [ ] **Step 2: Verify YAML extensibility — add chef.yaml without code change**

Create `app/skills/keywords/chef.yaml`:

```yaml
core:
  - butchery
  - charcuterie
  - fermentation
  - molecular gastronomy
domain:
  - michelin star
  - pop-up dining
```

Then verify:

```bash
python -c "
from app.skills import grouper
# Reload to pick up new file
import importlib; importlib.reload(grouper)
from app.skills.grouper import group_skills
r = group_skills(['Molecular Gastronomy', 'Fermentation'])
print('Molecular Gastronomy in core:', 'Molecular Gastronomy' in r.core)
print('Fermentation in core:', 'Fermentation' in r.core)
"
```

Expected:
```
Molecular Gastronomy in core: True
Fermentation in core: True
```

Remove `chef.yaml` after verification (it was only a smoke test for extensibility):

```bash
rm app/skills/keywords/chef.yaml
```

Note: In production, `chef.yaml` (and any new domain) should be a permanent addition checked into git. The test here just verifies the mechanism works.

- [ ] **Step 3: Run final full suite**

```bash
python -m pytest -v --tb=short 2>&1 | tail -20
```

Expected: all tests PASS, 260+ total.

- [ ] **Step 4: Final checkpoint commit**

```bash
git add app/skills/ app/ui/pages/5_Skills.py tests/test_skills_grouper.py tests/test_skills_suggester.py tests/test_skills_page.py
git commit -m "[PHASE-07] checkpoint: skills builder complete - tests passing"
```

---

## Completion Protocol

After all tasks are done, follow the COMPLETION PROTOCOL in the task file:

1. **STEP A** — Run `python -m pytest -v`, show full output
2. **STEP B** — Spec compliance checklist (CLAUDE.md §3, §4, §8, §9)
3. **STEP C** — Invoke `superpowers:requesting-code-review`
4. **STEP D** — Walkthrough + `git diff --staged`
5. **STEP E** — STOP, wait for commit approval
6. **STEP F** — Commit + push on approval

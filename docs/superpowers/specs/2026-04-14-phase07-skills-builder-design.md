# Phase 7 — Skills Section Builder: Design Spec
**Date:** 2026-04-14
**Branch:** feature/phase-02-upload-parse
**Status:** Approved

---

## 1. Objective

Give candidates a structured way to review, edit, and enrich the skills section of their AI-generated resume before download. Skills are grouped by category for clarity, JD-based suggestions are surfaced as hints, and the final save writes a flat list back to the submission record.

---

## 2. Scope

New files only. No existing files are touched.

```
app/skills/
  __init__.py
  grouper.py
  suggester.py
  keywords/
    tech.yaml
    sales.yaml
    marketing.yaml
    finance.yaml
    hr.yaml
    education.yaml
    culinary.yaml
    functional.yaml

app/ui/pages/
  5_Skills.py
```

Module boundary per CLAUDE.md §4: `app/skills/` and `app/ui/pages/5_Skills.py` only.

---

## 3. Key Constraints

- Groups are **UI-only** — never persisted. Re-derived on every page load from the flat skills list.
- Save writes only the flat `skills: List[str]` back into `llm_output_json`. No new DB columns.
- Suggestions are **hints** — candidate must explicitly click Add. No auto-additions.
- LLM called once on page load for suggestions. Not called again during editing.
- Suggester degrades gracefully: if LLM fails, return Stage 1 (set-difference) results only.
- Provider routing via `LLM_EXTRACT_PROVIDER` env var — no hardcoded model names.
- Keyword lists live in YAML files under `app/skills/keywords/`. Adding a new domain = add a YAML file, zero code changes.

---

## 4. Client Base Context

The majority of users are **non-tech professionals**: Sales, Marketing, Finance, HR, Education, Hospitality/Culinary, and others. All keyword lists, prompts, and UI copy must be industry-agnostic. Never assume a tech-first mental model.

---

## 5. Data Flow

```
DB: submission.llm_output_json → skills: ["Python", "Budgeting", ...]
          │
          ▼
    group_skills(skills) → SkillGroups(core, tools, functional, domain)
          │
          ▼
    UI: 4 collapsible buckets, each skill has [✕] remove button
          │
    suggest_skills(jd_fields, resume_fields) → List[str] (up to 10)
          │
          ▼
    UI: "Suggested from JD" panel, each suggestion has [+] add button
          │
    [Save Skills] clicked
          │
          ▼
    Flatten 4 buckets → List[str]
    Patch llm_output_json["skills"] = flattened list
    update_submission(id, {"llm_output_json": json.dumps(llm_output)})
    Show success toast
```

---

## 6. `app/skills/grouper.py`

### SkillGroups dataclass

```python
@dataclass
class SkillGroups:
    core: List[str]        # Primary/technical skills for the profession
    tools: List[str]       # Software, platforms, systems, equipment
    functional: List[str]  # Cross-industry transferable skills
    domain: List[str]      # Industry / sector specialisation
```

### group_skills(raw_skills: List[str]) -> SkillGroups

**Algorithm:**
1. At module import, load and merge all YAML files from `app/skills/keywords/` into four sets (core_set, tools_set, functional_set, domain_set).
2. For each skill in `raw_skills` (lowercased for matching):
   - Check `core_set` → match → assign Core
   - Check `tools_set` → match → assign Tools
   - Check `functional_set` → match → assign Functional
   - Check `domain_set` → match → assign Domain
   - No match → assign Core (default)
3. Preserve original casing in output.

**Match strategy:** whole-word substring match (`re.search(r'\b' + keyword + r'\b', skill_lower)`) to avoid false positives (e.g. "go" matching "Django").

### YAML keyword file schema

```yaml
# Example: sales.yaml
core:
  - prospecting
  - account management
  - pipeline management
  - consultative selling
  - quota attainment
  - B2B sales
  - lead generation
  - contract negotiation
tools:
  - Salesforce
  - HubSpot
  - Pipedrive
  - LinkedIn Sales Navigator
domain:
  - B2B
  - B2C
  - FMCG
  - enterprise sales
```

`functional.yaml` covers cross-industry transferable skills shared by all domains. Domain-specific YAML files omit `functional` (or leave it empty).

### Extensibility

Adding a new domain = create `app/skills/keywords/<domain>.yaml`. The grouper auto-discovers all YAML files in the directory on startup. No code changes required.

---

## 7. `app/skills/suggester.py`

### suggest_skills(jd_fields: dict, resume_fields: dict) -> List[str]

**Stage 1 — Set difference (no LLM, instant):**
- Pull `required_skills` + `preferred_skills` from `jd_fields`
- Subtract skills already in `resume_fields["skills"]` (case-insensitive)
- Direct keyword gaps identified without any LLM call

**Stage 2 — LLM enrichment (EXTRACT provider):**
- Build prompt: job title + required JD skills + current resume skills
- Ask: suggest up to 8 additional relevant skills the candidate could highlight, not already listed
- Provider routed via `LLM_EXTRACT_PROVIDER` env var (Gemini Flash default, Claude Haiku fallback)
- Merge with Stage 1, deduplicate, cap total at **10 suggestions**

**Failure handling:** If Stage 2 LLM call fails for any reason, log warning and return Stage 1 results only. Page must not crash.

**Prompt contract:** LLM returns a JSON array of strings only. No markdown, no explanation. Same `_strip_markdown_fences` + retry pattern as existing finetuner.py adapters.

---

## 8. `app/ui/pages/5_Skills.py`

### Access guard
Page is accessible when `submission.status` is `REVIEW_READY` or later. If no active submission or status is `PENDING`/`PROCESSING`, redirect to Upload page.

### Session state
- `st.session_state["skills_working"]` — `List[str]`, initialised from `llm_output_json["skills"]` on first load only. Survives reruns within the session.
- `st.session_state["skills_suggestions"]` — `List[str]`, loaded once on page load. Not reloaded on edit.

### Layout (two-column)

**Left column — Your Skills:**
- Four collapsible `st.expander` sections: Core / Tools / Functional / Domain
- Each skill rendered with a [✕] remove button
- [+ Add custom skill] text input + Add button at the bottom
- Skills re-grouped from `skills_working` on every render

**Right column — Suggested from JD:**
- Header: "Suggested from Job Description"
- List of suggestions not already in `skills_working`
- Each has a [+] Add button
- If no suggestions: "No additional suggestions — your skills look well-matched to the JD."

**Footer:**
- [Save Skills] button — full-width, primary style
- On click: flatten working list, patch `llm_output_json`, call `update_submission`, show `st.toast("Skills saved")`

### Reclassify UX
Reclassification (moving a skill between buckets) is not a separate explicit action. Candidate removes a skill from one bucket then adds it back — the grouper re-assigns on next render. This keeps the implementation simple with no drag-and-drop complexity.

---

## 9. Testing Plan

### `tests/test_skills_grouper.py`
- Tech skill classified as Core
- Sales tool (Salesforce) classified as Tools
- Functional skill (Leadership) classified as Functional
- Domain keyword (FMCG) classified as Domain
- Unknown skill falls to Core default
- Case-insensitive matching
- Empty input returns empty SkillGroups
- All four buckets populated correctly across a mixed list
- YAML file loading (at least one file loads without error)

### `tests/test_skills_suggester.py`
- Returns list of strings
- Caps at 10 suggestions
- Does not suggest skills already in resume (dedup)
- Stage 1 set-difference works with empty jd_fields
- Graceful degradation: LLM failure returns Stage 1 results
- Empty jd_fields returns empty list

### `tests/test_page_skills.py`
- Page renders without crashing (mock DB + session state)
- Save persists flat skills list to DB
- Adding a skill updates session state
- Removing a skill updates session state
- Suggestion not shown if already in working list

---

## 10. Acceptance Criteria

- [ ] `group_skills(["Python", "Salesforce", "Leadership", "FinTech"])` returns correct buckets
- [ ] `group_skills(["Sous Vide", "Menu Planning"])` → both in Core (no match, correct default)
- [ ] `suggest_skills` returns ≤10 items, none already in resume skills
- [ ] Suggester LLM failure does not crash — returns Stage 1 results
- [ ] Adding a new `keywords/chef.yaml` file causes `group_skills` to classify culinary skills correctly without any code changes
- [ ] [Save Skills] writes flat list to `llm_output_json["skills"]` in DB
- [ ] All existing 230 tests still pass
- [ ] New tests bring total to ~260+

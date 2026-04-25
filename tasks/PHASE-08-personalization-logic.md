# PHASE-08: Personalization Logic

## Status: COMPLETE
## Phase: 8 / 12

## Objective
Each resume rewrite is tailored to the candidate's experience level (auto-detected from resume)
and the JD's function type (auto-detected from JD text). A randomised verb bank (10 of 100)
and tone variant (1 of 10) ensure no two resumes share identical language.

## v1 Foundation
- `app/llm/prompt_builder.py` — extended (not rewritten)

## Net New
- `detect_experience_level(resume_text)` — public, duration math + keyword fallback
- `detect_function_type(jd_text)` — public, keyword count scoring
- `_sum_experience_months` — private, regex year-span + explicit years parsing
- `_keyword_experience_level` — private, seniority keyword tier matching
- `_build_personalization_block` — private, assembles prompt section with random sampling
- `_LEVEL_CONFIG`, `_TONE_VARIANTS`, `_VERB_BANKS`, `_LEVEL_KEYWORDS`, `_FUNCTION_KEYWORDS` — constants

## PDCA Log

### Cycle 1
**Plan:** docs/superpowers/specs/2026-04-17-phase08-personalization-design.md
**Approved by human:** Yes
**Do:** Extended prompt_builder.py only; zero changes to finetuner/provider/pages
**Check:** All tests passing (329 total)
**Act:** Complete

## Decisions Made
- Auto-detect inside build_finetuning_prompt; optional override params for testability
- Duration math first (>=2 year spans), explicit/written phrase as secondary, keyword as final fallback
- Keyword tie in function_type detection → "general"
- Keyword priority order: senior → mid → early → fresher (most specific first)
- 100 verbs per bank, 10 sampled per call; 10 tone variants per type, 1 selected per call
- Verbs line placed before Focus/Tone in block (both contain commas; verbs must be first comma-line for test detection)

## Checkpoints
- [x] _sum_experience_months — all patterns tested
- [x] _keyword_experience_level — priority order verified
- [x] detect_experience_level — duration + keyword fallback
- [x] detect_function_type — all types + tie resolution
- [x] _build_personalization_block — verb count, randomisation, all level/type combos
- [x] build_finetuning_prompt — block injected, override params respected, backward compat
- [x] Full test suite green (329 passed)

# PHASE-11: Quality Check Layer

## Status: COMPLETE
## Phase: 11 / 12

## Objective
Pre-output quality validation layer that runs after the variation engine and before PDF render.
Validates 5 checks on the rewritten resume draft, auto-fixes where safe, returns QualityReport.

## v1 Foundation
None — quality_check.py is net-new.

## Net New
- app/llm/quality_check.py — QualityReport dataclass + 5 checks + validate_quality()
- tests/test_quality_check.py — unit + integration tests

## PDCA Log

### Cycle 1
**Plan:** docs/superpowers/plans/2026-04-23-phase11-quality-check-layer.md
**Approved by human:** 2026-04-23
**Do:** 9 tasks, TDD, one commit per check function, subagent-driven execution
**Check:** All tests passing, module boundary clean (only 3 files changed in app/ and tests/)
**Act:** Proceed to Phase 12

## Decisions Made
- validate_quality signature: (resume_draft, original, jd_fields=None) — jd_fields optional
- original dict convention: {"raw_text": resume_text} — no extra LLM parse call
- experience_exaggerated: numeric heuristic only (no LLM) — numbers regex + set diff
- tone_repetitive: n-gram (4-word cross-section) + word-frequency (>=4 occurrences)
- passed=False only for [NEEDS REVIEW] issues; auto-fixed issues don't fail the report
- _NUMBER_RE: regex without %? (no-op removed); % captured manually via finditer post-match

## Checkpoints
- Task 1: QualityReport skeleton ✅
- Task 2: _check_bullets_too_long ✅
- Task 3: _check_recent_exp_prioritized ✅
- Task 4: _check_jd_keywords_present ✅
- Task 5: _check_experience_exaggerated ✅
- Task 6: _check_tone_repetitive ✅
- Task 7: validate_quality integration tests ✅
- Task 8: finetuner.py wiring ✅
- Task 9: checkpoint ✅

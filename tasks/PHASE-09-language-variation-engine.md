# PHASE-09: Language Variation Engine

## Status: COMPLETE
## Phase: 9 / 12

## Objective
Post-processing layer that detects and replaces overused résumé clichés in LLM rewrite
output. Runs after JSON parsing in both rewrite paths, before Phase 11 quality check.
Zero LLM calls, zero latency cost.

## v1 Foundation
None — net-new module.

## Net New
- app/llm/variation_engine.py: BANNED_PHRASES (20), SYNONYM_GROUPS (12 groups),
  _COMPILED_PATTERNS (12 compiled regexes), apply_variation(), apply_variation_to_resume()
- tests/test_variation_engine.py: 22 tests

## PDCA Log

### Cycle 1
**Plan:** Design spec at docs/superpowers/specs/2026-04-21-phase09-variation-engine-design.md
**Approved by human:** Yes
**Do:** variation_engine.py + tests + finetuner.py integration
**Check:** 353 tests passing (331 pre-existing + 22 new)
**Act:** Phase complete — proceed to Phase 10 (Payment Gate)

## Decisions Made
- apply_variation_to_resume() deep-copies input dict — never mutates caller's data
- skills[] is never modified — ATS keyword alignment takes priority over variation
- "takes initiative" removed from proactive alternatives to prevent semantic overlap with self-starter; replaced with "ahead of the curve"
- No-replacement BANNED_PHRASES entries (8) are left untouched — no pattern compiled for them
- _COMPILED_PATTERNS compiled once at module load (not per call)
- lambda default-arg capture (alts=alternatives) used to avoid Python closure-in-loop bug
- try/except in apply_variation_to_resume is defensive future-proofing; isinstance guards handle all documented cases

## Checkpoints
- [x] variation_engine.py scaffold committed
- [x] apply_variation() implemented and tested (17 tests)
- [x] apply_variation_to_resume() implemented and tested (22 tests total)
- [x] finetuner.py integration committed (both Claude + DeepSeek paths)
- [x] Full suite: 353 tests passing

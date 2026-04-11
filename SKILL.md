# SKILL.md
# Skill: PRD Executor
# Auto-activates when: user says "start phase", "next task", "build", or mentions a phase number
# ─────────────────────────────────────────────────────────────────────────────

## Skill Identity

You are a disciplined senior engineer executing the JobOS Resume Builder v2.0 PRD.
Your job is not to improvise - build exactly what CLAUDE.md specifies, phase by phase,
with full human approval at every gate.

## Activation Triggers

This skill activates when the user says:
- "Start Phase [N]"
- "Next phase" / "Next task"
- "Continue from Phase [N]"
- "Build [feature name]"

## Execution Protocol

When activated:

1. **Orient**
   - Read CLAUDE.md. State the current phase number and its scope.
   - Read tasks/PHASE-XX-*.md. State current status and any open questions.
   - Confirm: which v1 modules are being reused vs net-new.

2. **Plan**
   - Produce a written Implementation Plan:
     a. Files to create (with purpose)
     b. Files to modify (with what changes and why)
     c. Functions/classes to add or change
     d. Acceptance test: exactly how you will verify it works
     e. Risks: what could break in other modules as a side effect
   - Reference the exact CLAUDE.md section that governs this phase.

3. **Gate 1 - Plan Approval**
   - STOP. Present the plan. Wait for "proceed" or "approved".
   - Do NOT write a single line of code before approval.

4. **Execute**
   - Build only what is in the approved plan.
   - If you discover scope must expand: STOP, report, ask before continuing.
   - Follow code-style.md patterns throughout.

5. **Test**
   - Run: `pytest -v` - ALL tests must pass (v1 baseline + new).
   - If any v1 test breaks: fix it before proceeding. Do not suppress.
   - Run: `/generate-tests app/<module>/` to generate module test coverage.
   - Target: 80%+ function coverage for the new module.
   - Show full pytest output.

6. **Spec Compliance Check**
   Before invoking code review, verify against the spec yourself:
   - [ ] Does the implementation match CLAUDE.md §4 (module boundary for this phase)?
   - [ ] Does the status machine match CLAUDE.md §6 (if state was touched)?
   - [ ] Are all Critical Rules from CLAUDE.md §3 respected?
   - [ ] Does the git format follow CLAUDE.md §8 (branch + commit format)?
   - [ ] Are env vars used for all model/provider config (never hardcoded)?
   - [ ] Are the 82 v1 preserved modules (CLAUDE.md §9) untouched?
   - [ ] Does the task file (tasks/PHASE-XX-*.md) "Objective / Done" match what was built?
   If any check fails: fix before proceeding to code review.

7. **Code Review (subagent)**
   Invoke the `superpowers:requesting-code-review` skill.
   Provide it:
   - The phase number and scope
   - The relevant CLAUDE.md sections (§3 Critical Rules, §4 Module Boundary, §6 Status Machine)
   - The tasks/PHASE-XX-*.md acceptance criteria
   - The pytest output
   Wait for the code review report. Address any blocking issues before proceeding.

8. **Report**
   - Produce a Walkthrough: what was built, key decisions, anything deferred.
   - Run `git diff --staged` and show the output in full.

9. **Gate 2 - Commit Approval**
   - STOP. Wait for commit approval.
   - Never commit without explicit approval.

10. **Commit + Push**
    - Branch: `feature/phase-XX-short-slug`
    - Commit: `[PHASE-XX] checkpoint: <step> - verified`
    - Push to remote.

11. **Advance**
    - Update tasks/PHASE-XX-*.md: set Status to DONE, fill PDCA log.
    - Update CLAUDE.md Phase list: mark phase [DONE].
    - Ask: "Ready for Phase [N+1]?"

## Spec Compliance - What to Check Per Phase

| Phase | Key CLAUDE.md check |
|-------|---------------------|
| 1  Auth          | Users/sessions in DB, OTP expiry enforced, no passwords stored |
| 2  Upload/Parse  | v1 extractor.py untouched, JD fields stored in DB |
| 3  ATS Score     | No LLM call in scoring module, score < 1s |
| 4  Review Page   | Read-only, no editing, provider.py routes via env var |
| 5  Revision      | Hard cap at 3 enforced DB-side, revision_hint optional |
| 6  Missing Info  | Severity levels HIGH/MED/LOW, informational only |
| 7  Skills        | Suggestions are hints, candidate controls final list |
| 8  Personalization | No over-positioning, bullet format Action+Context+Outcome |
| 9  Variation     | No factual changes, leave original if no good replacement |
| 10 Payment       | Server-side signature verify, download locked until DB confirmed |
| 11 Quality Check | String checks pure Python, LLM only for semantic checks |
| 12 Tests         | All 82 v1 tests green, 120+ total, no real API/payment calls in tests |

## Failed Phase Protocol

If a phase fails after two attempts:
1. Stop trying.
2. Produce a Failure Report:
   - What was attempted
   - What error occurred
   - Root cause assessment
   - Two alternative approaches with trade-offs
3. Wait for a decision before any further action.

## What You Never Do

- Never start a new phase without finishing and committing the current one.
- Never modify files outside the approved module scope without asking first.
- Never skip the written plan, even for "simple" tasks.
- Never commit without showing the diff and waiting for approval.
- Never skip spec compliance check before invoking code review.
- Never skip code review before the commit gate.
- Never guess at a requirement - ask if unclear.
- Never swap LLM providers in code - env var only.
- Never break the 82 v1 tests - pytest must be green before every commit.
- Never hardcode API keys, model names, or payment credentials.

## References

- CLAUDE.md          - source of truth for all v2 requirements
- pdca-gate.md       - gate discipline (plan → wait → execute → walkthrough → wait → commit)
- git-discipline.md  - branch naming, pre-commit diff gate
- generate-tests.md  - /generate-tests workflow
- tasks/PHASE-XX-*.md - per-phase PDCA log and acceptance criteria
- session-workflow.md - master workflow from setup to go-live

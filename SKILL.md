# SKILL.md
# Skill: PRD Executor
# Auto-activates when: user says "start phase", "next task", "build", or mentions a phase number
# ─────────────────────────────────────────────────────────────────────────────

## Skill Identity

You are a disciplined senior engineer executing the JobOS Resume Builder v2.0 PRD.
Your job is not to improvise — build exactly what CLAUDE.md specifies, phase by phase,
with full human approval at every gate.

## Activation Triggers

This skill activates when the user says:
- "Start Phase [N]"
- "Next phase" / "Next task"
- "Continue from Phase [N]"
- "Build [feature name]"

## Execution Protocol

When activated:

1. **Orient**   — Read CLAUDE.md. State which phase and task you are on.
                  Read the relevant tasks/PHASE-XX-*.md file.
2. **Plan**     — Produce a written Implementation Plan for the current phase only.
                  (files to create, files to modify, functions to add, acceptance test, risks)
3. **Gate**     — STOP. Wait for "proceed" or "approved". Do not write code yet.
4. **Execute**  — Build only what is in the approved plan.
                  STOP if scope expands unexpectedly — report and ask.
5. **Verify**   — Run tests. Show results.
                  If tests fail: diagnose and fix within scope. Do not silently skip.
6. **Report**   — Produce a Walkthrough summary. Show `git diff --staged`.
7. **Gate**     — STOP. Wait for commit approval.
8. **Commit**   — Commit with `[PHASE-XX] checkpoint: step name - verified`
9. **Advance**  — Update tasks/PHASE-XX-*.md status to DONE.
                  Ask: "Ready for Phase [N+1]?"

## What You Never Do

- Never start a new phase without finishing and committing the current one.
- Never modify files outside the approved module scope without asking first.
- Never skip the written plan, even for "simple" tasks.
- Never commit without showing the diff and waiting for approval.
- Never guess at a requirement — ask if it is unclear.
- Never swap LLM providers in code — only via env var.
- Never break the 82 v1 tests — run pytest before every commit.

## References

- CLAUDE.md          — source of truth for all v2 requirements
- pdca-gate.md       — gate discipline rules
- git-discipline.md  — branch and commit rules
- generate-tests.md  — test generation workflow
- tasks/PHASE-XX-*.md — per-phase PDCA log

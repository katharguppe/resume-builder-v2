# git-discipline.md
# Workspace Rule: Git Hygiene
# Applies to every session in this workspace.
# ─────────────────────────────────────────────────────────────────────────────

## Branch Rules

- Never commit directly to `main` or `master`.
- Branch naming:
  - New feature:  `feature/phase-XX-short-slug`
  - Bug fix:      `fix/phase-XX-short-slug`
  - Config/infra: `chore/phase-XX-short-slug`

## Commit Rules

- Format: `[PHASE-XX] verb: what changed`
- Verbs: add, fix, update, remove, refactor, test, docs
- Examples:
  - `[PHASE-01] add: OTP generation and session table`
  - `[PHASE-03] fix: ATS keyword match edge case for short JDs`
  - `[PHASE-09] add: variation engine banned phrase list`
- One logical change per commit - do not bundle unrelated changes.
- Checkpoint commits: `[PHASE-XX] checkpoint: step name - verified`

## Pre-Commit Gate (ALWAYS)

Before any commit:
1. Run `git diff --staged` and show the output.
2. Wait for approval.
3. Only then commit.

NEVER auto-commit without showing the diff first.

## .gitignore Minimum

Always ensure these are in .gitignore:
- `.env`
- `__pycache__/`
- `*.pyc`
- `*.db` (except test fixtures)
- `.DS_Store`
- `*.log`
- `.venv/`

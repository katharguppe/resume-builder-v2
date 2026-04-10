# .agent/rules/code-style.md
# Workspace Rule: Code Style and Quality Standards
# Auto-loaded by Antigravity for every conversation in this workspace.
# ─────────────────────────────────────────────────────────────────────────────

## Language-Agnostic Rules

- Every function and class must have a docstring or JSDoc comment.
- No function longer than 50 lines — split into smaller functions.
- No magic numbers — use named constants.
- No hardcoded secrets, connection strings, or API keys — use env vars.
- No commented-out dead code in final commits.
- All error paths must be explicitly handled — no silent failures.

## Python Rules (apply when stack includes Python)

- Follow PEP 8 style guide.
- Use type hints on all function signatures.
- Use `pathlib` not `os.path` for file operations.
- Prefer dataclasses or Pydantic models over raw dicts for structured data.
- All tests use `pytest`. Naming: `test_<module>.py`, `test_<function_name>`.

## JavaScript / TypeScript Rules (apply when stack includes JS/TS)

- Prefer TypeScript over plain JavaScript.
- Use `const` by default; `let` only when reassignment is needed.
- No `any` type — use proper types or `unknown`.
- Async functions use `async/await`, not raw `.then()` chains.

## Docker Rules (apply when stack includes Docker)

- Every service must have a health check defined in docker-compose.yml.
- Never use `latest` tag for base images — pin to a specific version.
- Secrets go in `.env` file, never in Dockerfile or compose file.

## Database Rules

- Every schema change requires a migration file — no direct schema edits.
- All queries must be parameterised — no string interpolation in queries.
- Index any field that appears in a WHERE or filter clause.

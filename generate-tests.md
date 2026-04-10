# generate-tests.md
# Workflow: Generate Tests for a Module
# Trigger: /generate-tests <module>
# ─────────────────────────────────────────────────────────────────────────────
#
# WHAT THIS DOES:
#   Generates a full test suite for the module you specify.
#   Run this AFTER you are satisfied with the module's code.
#
# HOW TO USE:
#   Type: /generate-tests app/auth/
#   Type: /generate-tests app/scoring/
# ─────────────────────────────────────────────────────────────────────────────

Read every file in the module provided.

Generate a comprehensive test file for each source file in the module.

Rules:
- Test file naming: `tests/test_<source_filename>.py`
- Cover: happy path, edge cases, error/failure paths
- Use mocks for all external dependencies (DB, HTTP, file I/O, LLM calls)
- Mock pattern for LLM: patch the provider adapter, not the real API
- Mock pattern for payment: patch verify_payment() to return True/False
- Each test must have a descriptive name:
  `test_generate_otp_returns_6_digit_string`
  `test_verify_otp_returns_false_after_expiry`
  `test_ats_score_returns_zero_for_empty_resume`
- Minimum coverage: 80% of functions in the module

After generating tests:
1. Run: pytest tests/test_<module>.py -v
2. Show results.
3. Fix any failures before presenting output.
4. Confirm all pre-existing tests still pass: pytest -v

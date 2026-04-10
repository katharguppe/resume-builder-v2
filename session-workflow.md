# session-workflow.md
# Master Workflow: Every Session — Setup to Go-Live
# JobOS Resume Builder v2.0
# ─────────────────────────────────────────────────────────────────────────────
#
# Read this before every session. Follow every step in order.
# No step is optional. No gate is skippable.
# ─────────────────────────────────────────────────────────────────────────────

## Phase 0 — Pre-Session Checklist (run every time before opening Claude Code)

### 0.1 Environment
  [ ] cd D:\staging\resume-builder-v2
  [ ] git pull origin master          (get latest from remote)
  [ ] git status                       (confirm clean working tree)
  [ ] Check .env exists and is populated:
        GEMINI_API_KEY, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY
        SMTP credentials, ENCRYPTION_KEY
        PAYMENT_PROVIDER + keys (from Phase 10 onwards)

### 0.2 Fresh Clone / New Machine Only
  [ ] Copy .env.example to .env and fill all keys
  [ ] Run: .\setup-resume-builder-v2.ps1
        Creates: folders, .mcp.json, .env.example, task stubs, skill files
  [ ] Run: pip install -r requirements.txt
  [ ] Run: pytest -v   (confirm 82 v1 tests still pass before touching anything)

### 0.3 Identify Current Phase
  [ ] Open CLAUDE.md — check Phase list, find first [PENDING]
  [ ] Open tasks/PHASE-XX-*.md — read Status and open questions
  [ ] If previous session left unfinished work: finish that before starting new phase

---

## Phase 1 — Session Start

### 1.1 Create Feature Branch
  git checkout -b feature/phase-XX-short-slug
  (Never work on master directly — see git-discipline.md)

### 1.2 Launch Claude Code Session
  .\jobos-v2-sessions.ps1 -Session phase-X

### 1.3 Orient (Claude does this — verify it does)
  Claude should:
  [ ] Read CLAUDE.md and state the phase number + scope
  [ ] Read tasks/PHASE-XX-*.md and state current status
  [ ] Confirm which v1 modules are reused vs net-new
  If Claude skips this: type "orient first"

---

## Phase 2 — Plan Gate

### 2.1 Implementation Plan (Claude produces this)
  Claude must present:
  [ ] Files to create (with purpose)
  [ ] Files to modify (with what changes)
  [ ] Functions/classes to add
  [ ] Acceptance test (exactly how it will be verified)
  [ ] Risks to other modules

### 2.2 Human Review of Plan
  Review against:
  [ ] CLAUDE.md §4 Module Boundary — is scope correct?
  [ ] CLAUDE.md §9 Preserved — are v1 modules safe?
  [ ] tasks/PHASE-XX-*.md — does plan match the objective?
  [ ] pdca-gate.md — is the plan complete enough to approve?

### 2.3 Gate Decision
  [ ] APPROVED — type "proceed"
  [ ] NEEDS CHANGES — give specific feedback, wait for revised plan
  NEVER type "proceed" until the plan is fully satisfactory.

---

## Phase 3 — Execution

### 3.1 During Implementation
  Claude should stay within approved scope.
  If Claude reports scope expansion needed:
  [ ] Read the report
  [ ] Decide: approve expansion OR re-scope to stay within phase
  [ ] Give explicit answer before Claude continues

### 3.2 Scope Creep Warning Signs
  If Claude starts modifying files outside the stated phase scope without asking:
  [ ] Type "STOP — scope check" immediately
  [ ] Review what was changed
  [ ] Decide whether to keep or revert

---

## Phase 4 — Verification

### 4.1 Tests (Claude runs these — verify output)
  [ ] pytest -v — must show ALL passing (v1 + new)
  [ ] Zero failures. Zero errors. Zero skipped without explanation.
  [ ] New module coverage via /generate-tests app/<module>/
  [ ] Coverage >= 80% of new functions

### 4.2 If Tests Fail
  [ ] Read the failure message fully
  [ ] Claude diagnoses root cause — verify the diagnosis makes sense
  [ ] Claude fixes within approved scope
  [ ] Re-run pytest
  [ ] If still failing after 2 attempts: trigger Failed Phase Protocol (see SKILL.md)

---

## Phase 5 — Spec Compliance + Code Review

### 5.1 Spec Compliance (Claude self-checks — verify each item)
  [ ] Module boundary respected — no files touched outside phase scope
  [ ] Critical Rules respected — no hardcoded keys, WAL mode, manual-only email
  [ ] Status machine correct — if state was touched
  [ ] All providers via env var — no hardcoded model names
  [ ] v1 preserved modules untouched — ingestor, composer, email_handler, docker
  [ ] Git format correct — branch name and commit format per git-discipline.md
  [ ] Phase acceptance criteria met — matches tasks/PHASE-XX-*.md objective

### 5.2 Code Review Subagent
  Claude invokes: superpowers:requesting-code-review
  The subagent reviews against:
  [ ] CLAUDE.md spec for this phase
  [ ] code-style.md patterns
  [ ] Test coverage and quality

  Review outcomes:
  - BLOCKING issues:  Claude must fix before you approve commit
  - ADVISORY issues:  Note in tasks/PHASE-XX-*.md, do not block commit

### 5.3 Human Review of Code Review Report
  [ ] Read the code review output
  [ ] Confirm all blocking issues are resolved
  [ ] Accept or reject advisory notes

---

## Phase 6 — Commit Gate

### 6.1 Diff Review
  Claude shows: git diff --staged
  [ ] Review every changed file
  [ ] Confirm no .env, *.db, or credentials are staged
  [ ] Confirm no files outside approved scope are staged
  [ ] Confirm commit message format: [PHASE-XX] checkpoint: <name> - verified

### 6.2 Gate Decision
  [ ] APPROVED — type "commit"
  [ ] NEEDS CHANGES — give specific feedback
  NEVER approve a commit until the diff is reviewed.

### 6.3 After Commit
  Claude runs:
  [ ] git push origin feature/phase-XX-slug
  [ ] Updates tasks/PHASE-XX-*.md Status = DONE
  [ ] Updates CLAUDE.md Phase list: marks [DONE]

---

## Phase 7 — Post-Session

### 7.1 After Every Session
  [ ] Confirm git push succeeded (check GitHub)
  [ ] Note any deferred items in tasks/PHASE-XX-*.md Open Questions
  [ ] If a PR is needed: gh pr create (see git-discipline.md)
  [ ] Update CLAUDE.md current phase marker to next phase

### 7.2 Before Closing
  [ ] Run pytest -v one final time — confirm green
  [ ] git status — confirm clean working tree
  [ ] Close Claude Code

---

## Phase 8 — Go-Live Checklist (all 12 phases complete)

### 8.1 Full Test Suite
  [ ] pytest -v — 120+ tests, all passing, zero failures
  [ ] All 12 phase modules covered at 80%+
  [ ] E2E test: tests/test_e2e_v2.py — full candidate flow passes

### 8.2 Docker Build
  [ ] cd docker && docker-compose build --no-cache
  [ ] docker-compose up -d
  [ ] curl http://localhost:8501   (confirm Streamlit responds)
  [ ] Test OTP flow manually: register → receive OTP → login
  [ ] Test resume upload → ATS score → review → revise → download

### 8.3 Smoke Test Checklist
  [ ] OTP email delivered successfully
  [ ] Resume parsed (text + photo)
  [ ] JD parsed
  [ ] ATS score computed < 1s
  [ ] Missing info panel shows correctly
  [ ] AI rewrite generates (Gemini extract + DeepSeek rewrite)
  [ ] Variation engine removes clichés
  [ ] Quality check validates output
  [ ] Skills builder grouped correctly
  [ ] PDF preview rendered (watermarked)
  [ ] Payment flow initiates
  [ ] Payment verify server-side succeeds (test mode)
  [ ] PDF download unlocked after payment
  [ ] Revision limit enforced (3 max)

### 8.4 Final Code Review
  [ ] Invoke superpowers:requesting-code-review for full codebase
  [ ] All blocking issues resolved
  [ ] All 12 phase task files show Status = DONE

### 8.5 Release
  [ ] Merge feature branches to master (or confirm all work is on master)
  [ ] git tag v2.0.0
  [ ] git push origin v2.0.0
  [ ] Update CLAUDE.md: Current Phase = COMPLETE — v2.0.0 shipped
  [ ] Create GitHub Release: gh release create v2.0.0 --title "JobOS Resume Builder v2.0"

---

## Quick Reference — Files to Read Before Any Session

| File                  | Purpose                                      |
|-----------------------|----------------------------------------------|
| CLAUDE.md             | All v2 requirements, phase status, rules     |
| SKILL.md              | Full execution protocol                      |
| pdca-gate.md          | Plan → gate → execute → walkthrough → commit |
| git-discipline.md     | Branch naming, pre-commit diff gate          |
| generate-tests.md     | /generate-tests workflow                     |
| tasks/PHASE-XX-*.md   | Per-phase objective and PDCA log             |
| session-workflow.md   | This file                                    |

## Quick Reference — Commands Every Session

```powershell
# Pre-session
git pull origin master
git checkout -b feature/phase-XX-slug

# Run session
.\jobos-v2-sessions.ps1 -Session phase-X

# Test (run before every commit)
pytest -v

# Generate tests after implementation
# (say this inside Claude Code session)
/generate-tests app/<module>/

# Check diff before commit (Claude shows this — verify it)
git diff --staged

# Post-session
git push origin feature/phase-XX-slug
```

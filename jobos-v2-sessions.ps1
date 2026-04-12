# ==============================================================================
# jobos-v2-sessions.ps1
# Claude Code session launcher for JobOS Resume Builder v2.0
# Owner: Srinivas / Fidelitus Corp
# Usage: .\jobos-v2-sessions.ps1 -Session list
#        .\jobos-v2-sessions.ps1 -Session phase-1
# ==============================================================================

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet(
        "list",
        "phase-1","phase-2","phase-3","phase-4","phase-5","phase-6",
        "phase-7","phase-8","phase-9","phase-10","phase-11","phase-12",
        "debug"
    )]
    [string]$Session
)

$PROJECT_ROOT = "D:\staging\resume-builder-v2"
$SONNET       = "claude-sonnet-4-6"

# -- Completion Protocol (appended to every phase session, not debug) --------
# This enforces: test → spec compliance → code review → diff → commit gate
$completionProtocol = @'

════════════════════════════════════════════════════════════
COMPLETION PROTOCOL - run after implementation is done
════════════════════════════════════════════════════════════

STEP A - TEST
  Run: pytest -v
  All tests must pass - v1 baseline (82) + new tests.
  If any fail: fix before proceeding. Do not suppress or skip.
  Then run: /generate-tests app/<this-phase-module>/
  Show full pytest output.

STEP B - SPEC COMPLIANCE CHECK
  Check every item against CLAUDE.md before invoking code review:
  [ ] Module boundary respected (CLAUDE.md §4) - no files outside approved scope
  [ ] Critical Rules respected (CLAUDE.md §3) - no hardcoded keys, no auto-email, WAL mode
  [ ] Status machine correct (CLAUDE.md §6) - if state was touched
  [ ] LLM providers via env var only - never hardcoded model names
  [ ] v1 preserved modules untouched (CLAUDE.md §9) - ingestor, composer, email_handler
  [ ] Git format correct (CLAUDE.md §8) - branch feature/phase-XX-slug, commit [PHASE-XX]
  [ ] Phase task file acceptance criteria met (tasks/PHASE-XX-*.md)
  If any item fails: fix it now before code review.

STEP C - CODE REVIEW (subagent)
  Invoke: superpowers:requesting-code-review
  Provide the reviewer:
    - Phase number and scope
    - Relevant CLAUDE.md sections checked above
    - The pytest output from Step A
    - The tasks/PHASE-XX acceptance criteria
  Wait for review report. Fix any BLOCKING issues before proceeding.
  Advisory issues: note in the task file, do not block commit.

STEP D - REPORT + DIFF
  Produce a Walkthrough: what was built, key decisions, anything deferred.
  Run: git diff --staged
  Show the full diff output.

STEP E - GATE
  STOP. Present Steps A-D results. Wait for commit approval.
  Do NOT commit without explicit "approved" or "proceed".

STEP F - COMMIT + PUSH
  git add <specific files - never git add .>
  git commit -m "[PHASE-XX] checkpoint: <phase name> - verified"
  git push

STEP G - ADVANCE
  Update tasks/PHASE-XX-*.md: Status = DONE, fill PDCA log.
  Update CLAUDE.md Phase list: mark [DONE].
  Ask: "Ready for Phase [N+1]?"
════════════════════════════════════════════════════════════
'@

# -- Session definitions ---------------------------------------------------
$sessions = @{

    "phase-1" = @{
        model = $SONNET
        label = "Phase 1 - Auth: OTP accounts + session management"
        task  = "PHASE-01"
        prompt = @'
Stack: Python 3.13, Streamlit, SQLite WAL, smtplib, python-dotenv
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-01-auth-otp-accounts-session-management.md

PHASE 1: Auth - OTP accounts + session management

Scope: app/auth/ only. Do NOT touch other modules.

What to build:
  app/auth/__init__.py
  app/auth/models.py      - User + Session SQLAlchemy models (or raw SQLite)
  app/auth/otp.py         - generate_otp(), send_otp_email(), verify_otp()
  app/auth/session.py     - create_session(), validate_session(), expire_session()
  app/state/db.py         - extend with users + sessions tables (WAL mode)
  app/ui/pages/0_Login.py - Streamlit OTP login page

Rules:
  - OTP: 6-digit numeric, 10-minute expiry, one attempt per email per window
  - Sessions: UUID token, stored in DB, 24-hour expiry
  - Email delivery via smtplib (SMTP_* env vars) - same pattern as email_handler
  - No passwords stored - OTP-only auth
  - Fernet crypto already in app/email_handler/crypto.py - reuse it

Before writing any code:
  1. Read app/state/db.py fully
  2. Read app/email_handler/sender.py + crypto.py
  3. Present plan + schema
  4. Wait for approval
'@
    }

    "phase-2" = @{
        model = $SONNET
        label = "Phase 2 - Upload/Parse: resume + JD (port from v1)"
        task  = "PHASE-02"
        prompt = @'
Stack: Python 3.13, pdfplumber, PyMuPDF/fitz, LibreOffice (Docker), Streamlit
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-02-resume-jd-upload-parse.md

PHASE 2: Resume + JD upload + parse (port from v1, extend for multi-tenant)

Scope: app/ingestor/ + app/ui/pages/1_Upload.py

v1 foundation to reuse (DO NOT rewrite):
  app/ingestor/extractor.py  - text extraction + headshot photo filter (KEEP AS-IS)
  app/ingestor/converter.py  - LibreOffice DOC→PDF conversion (KEEP AS-IS)

New in v2:
  - Upload page associates files with authenticated user session
  - JD can be pasted (text) OR uploaded (PDF/DOC)
  - Store parsed resume_fields + jd_fields in DB linked to user session
  - app/ingestor/jd_extractor.py - extract JD fields using EXTRACT provider

Implementation plan already written - DO NOT re-plan.
Plan file: docs/superpowers/plans/2026-04-12-phase-02-upload-parse.md
Scope resolved: YES Phase 2 includes LLM extract_fields call.
Branch from: feature/phase-01-auth

Load the plan and execute it using superpowers:executing-plans.
'@
    }

    "phase-3" = @{
        model = $SONNET
        label = "Phase 3 - ATS Score Engine (batch, in-process)"
        task  = "PHASE-03"
        prompt = @'
Stack: Python 3.13, no LLM - pure Python scoring
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-03-ats-score-engine-batch.md

PHASE 3: ATS Score Engine - batch, in-process, no LLM

Scope: app/scoring/ only (new module)

What to build:
  app/scoring/__init__.py
  app/scoring/ats_scorer.py   - compute_ats_score(resume_fields, jd_fields) -> ATSScore
  app/scoring/missing_info.py - detect_missing(resume_fields) -> List[MissingItem]
  app/scoring/models.py       - ATSScore, MissingItem dataclasses

ATS score components (0-100):
  keyword_match        (30%) - resume keywords vs JD required keywords
  skills_coverage      (30%) - resume skills vs JD required skills
  experience_clarity   (20%) - presence of: dates, roles, company names, achievements
  structure_completeness(20%) - presence of: summary, education, certifications

Missing info severity:
  HIGH   - missing dates, missing current role designation
  MEDIUM - no measurable achievements, no company description
  LOW    - no certifications, no LinkedIn/GitHub

Rules:
  - NO LLM calls in this module - pure Python string matching + heuristics
  - Score must complete in <1s
  - Use skill: ats-scorer for each component

Before writing any code:
  1. Read app/ingestor/extractor.py (understand the field structure from v1)
  2. Present scoring algorithm design
  3. Wait for approval
'@
    }

    "phase-4" = @{
        model = $SONNET
        label = "Phase 4 - Resume Review Page (read-only)"
        task  = "PHASE-04"
        prompt = @'
Stack: Python 3.13, Streamlit, SQLite, reportlab
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-04-resume-review-page.md

PHASE 4: Resume review page - read-only output + accept/reject controls

Scope: app/ui/pages/3_Review.py + app/llm/ (trigger rewrite for first generation)

What to build:
  app/ui/pages/3_Review.py - candidate review page:
    - Show ATS score breakdown (from Phase 3)
    - Show missing info panel (severity ranked)
    - Show AI-generated resume (PDF preview or structured text)
    - Show JD alignment highlights
    - Controls: [Accept Draft] [Request Revision] [Back]

  app/llm/finetuner.py - extend to call REWRITE provider (DeepSeek or Claude)
  app/llm/provider.py  - NEW: provider routing by LLM_*_PROVIDER env var

v1 foundation to reuse:
  app/composer/pdf_writer.py  - PDF generation (KEEP AS-IS)
  app/composer/photo_handler.py - photo embed (KEEP AS-IS)
  app/llm/prompt_builder.py   - base prompts (extend, do not replace)

Rules:
  - No editing on this page - read-only
  - Revision button only shows if revisions_remaining > 0 (max 3)
  - Status machine: PROCESSING -> REVIEW_READY

Before writing any code:
  1. Read app/composer/pdf_writer.py + app/llm/finetuner.py fully
  2. Present provider.py design (Gemini Flash + DeepSeek V3 adapters)
  3. Wait for approval
'@
    }

    "phase-5" = @{
        model = $SONNET
        label = "Phase 5 - Revision Request (re-run LLM, up to 3x)"
        task  = "PHASE-05"
        prompt = @'
Stack: Python 3.13, Streamlit, SQLite, app/llm/
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-05-revision-request-up-to-3x.md

PHASE 5: Revision request - re-run LLM pipeline, max 3 revisions per session

Scope: app/ui/pages/4_Revise.py + app/state/ (revision counter)

What to build:
  app/ui/pages/4_Revise.py  - revision request page:
    - Show current draft
    - Text input: "What to improve?" (optional hint to LLM)
    - Show revisions_remaining count (e.g. "2 revisions left")
    - [Submit Revision Request] button
    - Status: REVISION_REQUESTED -> PROCESSING -> REVIEW_READY

  app/state/db.py  - add: revisions_used column, revisions_remaining computed
  app/state/models.py - add REVISION_REQUESTED, REVISION_EXHAUSTED to status enum
  app/llm/finetuner.py - accept optional revision_hint parameter

Rules:
  - Hard cap at 3 revisions (enforced DB-side, not just UI-side)
  - Revision hint is optional - LLM uses it only if provided
  - After 3rd revision: show [Accept Anyway] only, no more revision button
  - Status machine: REVIEW_READY -> REVISION_REQUESTED -> REVIEW_READY (up to 3x)
  -                 REVIEW_READY -> REVISION_EXHAUSTED (after 3rd)

Before writing any code:
  1. Read app/state/models.py + app/state/db.py
  2. Present revision counter schema + status transitions
  3. Wait for approval
'@
    }

    "phase-6" = @{
        model = $SONNET
        label = "Phase 6 - Missing Information Engine (severity panel)"
        task  = "PHASE-06"
        prompt = @'
Stack: Python 3.13, Streamlit, app/scoring/missing_info.py (Phase 3)
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-06-missing-information-engine.md

PHASE 6: Missing Information Engine - severity-ranked UI panel

Scope: app/scoring/missing_info.py (extend) + UI panel component

What to build/extend:
  app/scoring/missing_info.py - extend with:
    - importance_level: HIGH | MEDIUM | LOW
    - actionable message per missing item (e.g. "Add exact dates for each role")
    - group by section (Experience / Education / Skills / Summary)

  app/ui/components/missing_panel.py - Streamlit component:
    - Collapsible panel per severity level
    - Click-to-highlight which section needs fixing
    - Shown on Review page (left panel) and Revision page

Rules:
  - This is informational only - no auto-editing
  - v1 red fields in PDF are still preserved (existing composer behavior)
  - Missing panel is UI-layer on top of scoring output

Before writing any code:
  1. Read app/scoring/missing_info.py (Phase 3 output)
  2. Review PRD §5.7 missing info examples
  3. Present severity taxonomy
  4. Wait for approval
'@
    }

    "phase-7" = @{
        model = $SONNET
        label = "Phase 7 - Skills Section Builder"
        task  = "PHASE-07"
        prompt = @'
Stack: Python 3.13, Streamlit, app/llm/ (EXTRACT provider)
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-07-skills-section-builder.md

PHASE 7: Skills Section Builder - grouped suggest + edit

Scope: app/skills/ (new) + app/ui/pages/5_Skills.py

What to build:
  app/skills/__init__.py
  app/skills/grouper.py  - group_skills(raw_skills: List[str]) -> SkillGroups
                           Groups: Core | Tools | Functional | Domain
  app/skills/suggester.py - suggest_skills(jd_fields, resume_fields) -> suggestions
                            Uses EXTRACT provider (Gemini Flash) for JD-based suggestions

  app/ui/pages/5_Skills.py:
    - Show current skills grouped
    - Show JD-suggested missing skills (highlighted)
    - Candidate can: add / remove / reclassify skills
    - [Save Skills] updates session in DB

Rules:
  - Suggestions are hints, not auto-additions - candidate controls final list
  - Skills section in PDF composer is updated from DB, not re-run from scratch
  - Keep grouper logic simple: keyword matching to known group lists first, LLM fallback

Before writing any code:
  1. Read app/llm/finetuner.py (understand extract_fields output structure)
  2. Read app/composer/pdf_writer.py (skills section layout)
  3. Present grouper design
  4. Wait for approval
'@
    }

    "phase-8" = @{
        model = $SONNET
        label = "Phase 8 - Personalization Logic"
        task  = "PHASE-08"
        prompt = @'
Stack: Python 3.13, app/llm/prompt_builder.py (extend from v1)
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-08-personalization-logic.md

PHASE 8: Experience/function personalization logic

Scope: app/llm/prompt_builder.py only

Experience levels (detect from resume, pass to prompt):
  fresher  (0-1y)  -> focus: education, projects, learning agility
  early    (1-4y)  -> focus: execution, delivery, tools
  mid      (4-8y)  -> focus: ownership, results, cross-functional
  senior   (8y+)   -> focus: leadership, scale, strategy

Function types (detect from JD, pass to prompt):
  technical    -> precision, tools, architecture
  sales        -> targets, pipeline, conversion rates
  operations   -> process, efficiency, SLAs
  academic     -> curriculum, research, outcomes
  general      -> balanced across all areas

Rules from PRD §6:
  - No over-positioning - reflect actual level
  - Tone variation - no repeated cliche phrases across candidates
  - Bullet format: Action + Context + Outcome
  - Recent role: 6-8 bullets | Previous: 4-6 | Older: 2-4

Use skill: personalization for each level/function combination.

Before writing any code:
  1. Read current app/llm/prompt_builder.py fully
  2. Present which sections need extending vs replacing
  3. Wait for approval
'@
    }

    "phase-9" = @{
        model = $SONNET
        label = "Phase 9 - Language Variation Engine"
        task  = "PHASE-09"
        prompt = @'
Stack: Python 3.13, app/llm/ (post-processing layer)
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-09-language-variation-engine.md

PHASE 9: Language Variation Engine - anti-repetition phrase rotation

Scope: app/llm/variation_engine.py (new)

What to build:
  app/llm/variation_engine.py:
    BANNED_PHRASES    - list of cliche phrases to detect and replace
    SYNONYM_GROUPS    - dict of phrase -> list of alternatives
    apply_variation(text: str) -> str
      - Detect any BANNED_PHRASES in text
      - Replace with a randomly selected alternative from SYNONYM_GROUPS
      - Log replacements for auditability

  Integration: call apply_variation() on rewrite output BEFORE quality check

Banned phrase examples (from PRD §10.3):
  "cross-functional collaboration" -> rotate with alternatives
  "transforming vision into reality" -> rotate
  "mission-driven professional" -> rotate
  "results-oriented" -> rotate

Rules:
  - NEVER change factual content - only rephrase
  - Replacements must be grammatically correct in context
  - If no suitable replacement exists, leave original (do not force bad phrasing)
  - Unit-testable: each SYNONYM_GROUP must have a test

Use skill: variation-engine

Before writing any code:
  1. Present initial BANNED_PHRASES list (20+ entries)
  2. Present initial SYNONYM_GROUPS (10+ groups)
  3. Wait for approval
'@
    }

    "phase-10" = @{
        model = $SONNET
        label = "Phase 10 - Payment Gate + Locked Download"
        task  = "PHASE-10"
        prompt = @'
Stack: Python 3.13, Streamlit, Razorpay (default) or Stripe, SQLite
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-10-payment-gate-locked-download.md

PHASE 10: Payment gate + locked PDF download

Scope: app/payment/ (new) + app/ui/pages/6_Download.py

What to build:
  app/payment/__init__.py
  app/payment/provider.py  - PaymentProvider adapter
                             create_order(amount, currency) -> order_id
                             verify_payment(payment_id, order_id, signature) -> bool
                             Supports: PAYMENT_PROVIDER=razorpay | stripe

  app/ui/pages/6_Download.py:
    - Show resume preview (watermarked if unpaid)
    - Show price (RESUME_DOWNLOAD_PRICE_INR from .env)
    - [Pay & Download] button -> Razorpay/Stripe checkout
    - On payment_confirmed: unlock and serve PDF
    - On failure: show error, allow retry

  app/state/db.py - add: payment_status, payment_id, payment_order_id columns
  app/state/models.py - add PAYMENT_PENDING, PAYMENT_CONFIRMED, DOWNLOAD_READY, DOWNLOADED

Rules:
  - Download is LOCKED until payment_confirmed = true in DB
  - Verify payment server-side (signature check) - never trust client
  - Watermark PDF before payment: semi-transparent "PREVIEW" overlay
  - After payment: serve clean PDF, log DOWNLOADED status

Before writing any code:
  1. Present payment provider adapter design
  2. Confirm: Razorpay for India market (default)?
  3. Wait for approval
'@
    }

    "phase-11" = @{
        model = $SONNET
        label = "Phase 11 - Quality Check Layer"
        task  = "PHASE-11"
        prompt = @'
Stack: Python 3.13, app/llm/ (REWRITE provider)
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-11-quality-check-layer.md

PHASE 11: Quality Check Layer - pre-output validation before candidate sees resume

Scope: app/llm/quality_check.py (new)

What to build:
  app/llm/quality_check.py:
    validate_quality(resume_draft: dict, original: dict) -> QualityReport
      Checks (from PRD §10.10):
        1. tone_repetitive      - same phrases across sections?
        2. experience_exaggerated - claims beyond original?
        3. bullets_too_long     - bullets > 30 words?
        4. recent_exp_prioritized - latest role has most bullets?
        5. jd_keywords_present  - required JD keywords in resume?
      Returns: QualityReport(passed: bool, issues: List[str], fixed_draft: dict)

    If issues found: auto-fix where safe (trim long bullets, reorder sections)
    If cannot auto-fix: return issues list for revision loop

  Integration: call validate_quality() AFTER variation engine, BEFORE PDF render

Rules:
  - Use REWRITE provider (DeepSeek or Claude) for semantic checks only
  - String-based checks (bullet length, section order) are pure Python - no LLM
  - Must complete in < 5s total
  - All checks must be unit-testable with mock resume data

Before writing any code:
  1. Read app/llm/variation_engine.py (Phase 9 output)
  2. Present quality check algorithm design
  3. Wait for approval
'@
    }

    "phase-12" = @{
        model = $SONNET
        label = "Phase 12 - Integration + E2E Tests"
        task  = "PHASE-12"
        prompt = @'
Stack: Python 3.13, pytest, all app modules
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task file: tasks/PHASE-12-integration-e2e-tests.md

PHASE 12: Integration + E2E tests - extend v1 test suite, verify all phases

Scope: tests/ only

v1 tests to preserve (all must still pass):
  tests/test_ingestor.py   - text + photo extraction
  tests/test_composer.py   - PDF layout
  tests/test_best_practice.py
  tests/test_email_handler.py
  tests/test_state.py
  tests/test_e2e.py

New tests to add:
  tests/test_auth.py       - OTP generate/verify, session create/expire
  tests/test_scoring.py    - ATS score engine, missing info detection
  tests/test_skills.py     - grouper, suggester
  tests/test_payment.py    - payment adapter (mocked)
  tests/test_variation.py  - phrase rotation, banned phrase detection
  tests/test_quality.py    - quality check layer
  tests/test_e2e_v2.py     - full candidate flow: upload -> score -> review -> pay -> download

Rules:
  - All 82 v1 tests must remain green
  - New tests follow existing conftest.py patterns
  - E2E v2 test uses test fixtures (no real API calls, no real payment)
  - Target: 120+ total tests passing

Before writing any code:
  1. Run: pytest -v to confirm v1 baseline
  2. Present test plan per module
  3. Wait for approval
'@
    }

    "debug" = @{
        model = $SONNET
        label = "Debug - one error, one file, one session"
        task  = "DEBUG"
        prompt = @'
Stack: Python 3.13, Streamlit, Gemini Flash, DeepSeek V3, Claude fallback
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Task: Debugging - one error, one file, one session.

RULES:
  - Do NOT paste multiple files at once.
  - Paste: (1) full traceback, (2) ONLY the function that threw it.
  - State which module: auth / ingestor / scoring / skills / payment / llm / composer / email / state / ui

Known gotchas for this stack:
  - Gemini SDK: genai.Client(api_key=...) - not google-generativeai legacy pattern
  - DeepSeek: uses OpenAI-compatible SDK (openai.OpenAI(base_url=..., api_key=...))
  - anthropic SDK: client = anthropic.Anthropic(api_key=...) - fallback only
  - PyMuPDF: import fitz - not import pymupdf
  - LibreOffice in Docker: path is /usr/bin/soffice not Windows path
  - SQLite in Docker volume: must use WAL mode
  - Streamlit: no st.form submit inside st.columns
  - Fernet key: must be generated once and stored in .env - never regenerate
  - OTP: check expiry in DB, not in memory

Paste traceback and function below:
'@
    }

}

# -- List mode -----------------------------------------------------------------
if ($Session -eq "list") {
    Write-Host ""
    Write-Host "JobOS Resume Builder v2.0 - Session Launcher" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  STARTUP ORDER (every session):" -ForegroundColor Yellow
    Write-Host "    1. .\setup-resume-builder-v2.ps1     <- run first on fresh clone / new machine" -ForegroundColor DarkGray
    Write-Host "    2. .\jobos-v2-sessions.ps1 -Session list" -ForegroundColor DarkGray
    Write-Host "    3. .\jobos-v2-sessions.ps1 -Session phase-N" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  AVAILABLE SESSIONS:" -ForegroundColor Yellow
    foreach ($key in ($sessions.Keys | Sort-Object)) {
        $s = $sessions[$key]
        Write-Host "  $($key.PadRight(12)) : $($s.label)" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "  PROCESS FILES (read before every phase):" -ForegroundColor Yellow
    Write-Host "    SKILL.md          - full execution protocol" -ForegroundColor DarkGray
    Write-Host "    pdca-gate.md      - plan/gate/execute/walkthrough discipline" -ForegroundColor DarkGray
    Write-Host "    git-discipline.md - branch naming + pre-commit diff gate" -ForegroundColor DarkGray
    Write-Host "    generate-tests.md - /generate-tests workflow" -ForegroundColor DarkGray
    Write-Host "    session-workflow.md - master workflow setup to go-live" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Usage: .\jobos-v2-sessions.ps1 -Session phase-1" -ForegroundColor Green
    Write-Host ""
    exit 0
}

# -- Launch session -------------------------------------------------------------
$s = $sessions[$Session]
if (-not $s) {
    Write-Host "Unknown session: $Session" -ForegroundColor Red
    exit 1
}

Set-Location $PROJECT_ROOT

Write-Host ""
Write-Host "Launching: $($s.label)" -ForegroundColor Cyan
Write-Host "Model    : $($s.model)" -ForegroundColor DarkGray
Write-Host "Task     : $($s.task)" -ForegroundColor DarkGray
Write-Host ""

# Write prompt to temp file - append completion protocol for all phase sessions
$tmpPrompt = "$env:TEMP\jobos_v2_session_prompt.txt"
if ($Session -ne "debug") {
    ($s.prompt + $completionProtocol) | Set-Content $tmpPrompt -Encoding UTF8
} else {
    $s.prompt | Set-Content $tmpPrompt -Encoding UTF8
}

claude --model $s.model "$(Get-Content $tmpPrompt -Raw)"

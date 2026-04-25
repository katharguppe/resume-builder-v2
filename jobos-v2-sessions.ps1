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
        label = "Phase 3 - ATS Score Engine (batch, in-process) - RESUME from Task 3"
        task  = "PHASE-03"
        prompt = @'
Stack: Python 3.13, no LLM - pure Python scoring
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Branch: feature/phase-02-upload-parse (144 tests passing)
Plan file: docs/superpowers/plans/2026-04-12-phase-03-ats-score-engine.md

PHASE 3 RESUME SESSION - Tasks 1 and 2 are COMPLETE. Do NOT redo them.

════════════════════════════════════════════════
ALREADY DONE (do not re-implement):
════════════════════════════════════════════════
Pre-fixes committed (9d67daa):
  - app/ui/pages/1_Setup.py: anthropic_api_key renamed + GEMINI_API_KEY field added
  - app/state/models.py: ats_score_json: Optional[str] added to SubmissionRecord
  - app/state/db.py: ats_score_json TEXT column + ALTER TABLE migration + whitelist
  - tests/test_state.py: ats_score_json=None added to fixture

Task 1 committed (a30fd9f):
  - app/scoring/models.py: ATSScore + MissingItem dataclasses
  - app/scoring/__init__.py: stub
  - tests/test_scoring_models.py: 6 tests

Task 2 committed (e811327):
  - app/scoring/ats_scorer.py: _tokenize, _score_keyword_match, _normalize_skill (REAL)
    _score_skills_coverage, _score_experience_clarity, _score_structure_completeness,
    compute_ats_score are STUBS (return 15/0 - to be replaced in Tasks 3-4)
  - tests/test_ats_scorer.py: _make_jd + _make_resume_fields helpers + 7 keyword_match tests

════════════════════════════════════════════════
STEP 1 - APPLY THESE 4 FIXES FIRST (from code review of Task 2):
════════════════════════════════════════════════
In app/scoring/ats_scorer.py:

Fix 1 - non-string guard at top of _tokenize:
  if not isinstance(text, str):
      return set()

Fix 2 - non-string guard in _score_keyword_match responsibilities loop:
  for resp in responsibilities:
      if isinstance(resp, str):
          jd_tokens.update(_tokenize(resp))

Fix 3 - replace _normalize_skill with alias-aware version (C++ -> cplusplus, split on /,  NOT +):
  _SKILL_ALIASES = {
      "c++": "cplusplus", "c#": "csharp", "f#": "fsharp",
      ".net": "dotnet", "node.js": "nodejs", "vue.js": "vuejs",
      "react.js": "reactjs", "next.js": "nextjs",
  }
  def _normalize_skill(skill: str) -> List[str]:
      lowered = skill.lower().strip()
      for src, dst in _SKILL_ALIASES.items():
          lowered = lowered.replace(src, dst)
      parts = re.split(r"[/,]", lowered)
      return [re.sub(r"[^a-z0-9\s]", "", p).strip() for p in parts if p.strip()]

Fix 4 - tighten fallback test in tests/test_ats_scorer.py:
  test_keyword_match_fallback_empty_responsibilities:
    assert 0 < score <= 15  (was: assert score <= 15)

Run: python -m pytest tests/ -q   -> must still show 144 passed
Commit: [PHASE-03] fix: non-string guard in tokenize; C++ alias in normalize_skill; tighten fallback test

════════════════════════════════════════════════
STEP 2 - CONTINUE with Tasks 3-7 from the plan:
════════════════════════════════════════════════
Load plan: docs/superpowers/plans/2026-04-12-phase-03-ats-score-engine.md
Execute Tasks 3, 4, 5, 6, 7 using superpowers:subagent-driven-development.
Start at Task 3 (skills_coverage). Do NOT re-run Tasks 1 or 2.

Use python -m pytest (not bare pytest) for all test runs.
'@
    }

    "phase-4" = @{
        model = $SONNET
        label = "Phase 4 - Resume Review Page (read-only)"
        task  = "PHASE-04"
        prompt = @'
Stack: Python 3.13, Streamlit, SQLite, reportlab
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Branch: feature/phase-02-upload-parse (183 tests passing)

PHASE 3 IS COMPLETE. Do NOT redo it.
  app/scoring/ is fully built: ats_scorer, missing_info, models, _patterns, __init__
  compute_ats_score() and detect_missing() are live and tested.

PHASE 4: Resume review page - read-only output + accept/reject controls

Scope: app/ui/pages/3_Review.py + app/llm/ (trigger rewrite for first generation)

What to build:
  app/ui/pages/3_Review.py - candidate review page:
    - Show ATS score breakdown (from Phase 3 compute_ats_score)
    - Show missing info panel (from Phase 3 detect_missing, severity ranked)
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
  - Use python -m pytest (not bare pytest) for all test runs

Before writing any code:
  1. Read /memory to load Phase 3 context
  2. Read app/composer/pdf_writer.py + app/llm/finetuner.py fully
  3. Present provider.py design (Gemini Flash + DeepSeek V3 adapters)
  4. Wait for approval
'@
    }

    "phase-5" = @{
        model = $SONNET
        label = "Phase 5 - Revision Request (re-run LLM, up to 3x)"
        task  = "PHASE-05"
        prompt = @'
Stack: Python 3.13, Streamlit, SQLite, app/llm/
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Branch: feature/phase-02-upload-parse (204 tests passing)

PHASE 4 IS COMPLETE. Do NOT redo it.
  app/ui/pages/3_Review.py is fully built: auth guard, pipeline trigger,
    two-column layout (ATS score + missing info left, resume text + JD alignment right),
    action bar (Back / Request Revision / Accept Draft).
  _run_rewrite_pipeline() is live and tested (tests/test_review_pipeline.py, 5 tests).
  Provider routing is live: LLM_EXTRACT_PROVIDER (claude|gemini), LLM_REWRITE_PROVIDER (claude|deepseek).
  MAX_REVISIONS = 3 constant defined in 3_Review.py.
  Status machine in place: PROCESSING -> REVIEW_READY -> REVISION_REQUESTED / ACCEPTED.

PHASE 5: Revision request - re-run LLM pipeline, max 3 revisions per session

Scope: app/ui/pages/4_Revise.py + app/llm/ (revision_hint support)

What to build:
  app/ui/pages/4_Revise.py  - revision request page:
    - Auth guard (same pattern as 3_Review.py _require_auth)
    - Load submission (current_submission_id from session_state)
    - Guard: only show if status == REVISION_REQUESTED
    - Show current AI draft (read from llm_output_json)
    - Text area: "What would you like to improve?" (optional hint to LLM)
    - Show revisions_remaining = MAX_REVISIONS - revision_count
    - [Submit Revision] button:
        set status PROCESSING, re-run _run_rewrite_pipeline (with hint), st.rerun()
    - After re-run: redirect to 3_Review.py

  app/llm/provider.py + finetuner.py:
    - rewrite_resume() and adapters accept optional revision_hint: str = ""
    - If hint provided: append to prompt ("Candidate feedback: {hint}")
    - Claude and DeepSeek adapters both updated

  REVISION_EXHAUSTED status:
    - If revision_count >= MAX_REVISIONS after re-run: set REVISION_EXHAUSTED
    - 4_Revise.py shows [Accept Anyway] only when REVISION_EXHAUSTED

  MAX_REVISIONS = 3 is already defined in app/ui/pages/3_Review.py.
  Import or redefine it in 4_Revise.py (do NOT create a shared constants file
  unless the plan calls for it).

Rules:
  - revision_count is already in SubmissionRecord and DB (from Phase 2/4)
  - Do NOT add a revisions_used column - revision_count is already tracking this
  - REVISION_REQUESTED and REVISION_EXHAUSTED are already in SubmissionStatus enum
    (verify before adding - check app/state/models.py)
  - Hard cap enforced: button hidden + status set to REVISION_EXHAUSTED at limit
  - Revision hint is optional - LLM uses it only if non-empty
  - Use python -m pytest (not bare pytest) for all test runs

Before writing any code:
  1. Read /memory to load Phase 4 context
  2. Read app/state/models.py (check SubmissionStatus enum values)
  3. Read app/ui/pages/3_Review.py (understand _require_auth, _run_rewrite_pipeline patterns to reuse)
  4. Read app/llm/finetuner.py + provider.py (understand current rewrite_resume signature)
  5. Present plan for revision_hint threading + 4_Revise.py page structure
  6. Wait for approval
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
    - actionable message per missing item (e.g. 'Add exact dates for each role')
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
Branch: feature/phase-02-upload-parse (230 tests passing)
Task file: tasks/PHASE-07-skills-section-builder.md

PHASE 6 IS COMPLETE. Do NOT redo it.
  app/scoring/missing_info.py: section field added, 6 items with sections assigned.
  app/ui/components/missing_panel.py: severity-ranked collapsible panel, Focus button,
    highlight_section session state, key_prefix support.
  3_Review.py: panel wired in, _render_section_highlight callouts on all 5 sections.
  4_Revise.py: missing panel shown above revision form.
  230 tests passing (baseline was 214 + 16 new).

PHASE 7: Skills Section Builder - grouped suggest + edit

Scope: app/skills/ (new) + app/ui/pages/5_Skills.py

What to build:
  app/skills/__init__.py
  app/skills/grouper.py  - group_skills(raw_skills: List[str]) -> SkillGroups
                           Groups: Core | Tools | Functional | Domain
  app/skills/suggester.py - suggest_skills(jd_fields, resume_fields) -> List[str]
                            Uses EXTRACT provider (Gemini Flash) for JD-based suggestions

  app/ui/pages/5_Skills.py:
    - Show current skills grouped (from llm_output_json skills list)
    - Show JD-suggested missing skills (highlighted, from suggester)
    - Candidate can: add / remove / reclassify skills
    - [Save Skills] persists updated skills list to submission in DB

Rules:
  - Suggestions are hints, not auto-additions - candidate controls final list
  - Skills update stored in submission record (llm_output_json skills key)
  - Keep grouper logic simple: keyword matching to known group lists first, LLM fallback
  - Use python -m pytest (not bare pytest) for all test runs

Before writing any code:
  1. Read app/llm/finetuner.py (understand extract_fields output structure)
  2. Read app/composer/pdf_writer.py (skills section layout)
  3. Present grouper design + group keyword lists
  4. Wait for approval
'@
    }

    "phase-8" = @{
        model = $SONNET
        label = "Phase 8 - Personalization Logic [DONE - 329 tests]"
        task  = "PHASE-08"
        prompt = @'
Stack: Python 3.13, app/llm/prompt_builder.py
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Branch: feature/phase-02-upload-parse

PHASE 8 IS COMPLETE. Do NOT re-implement anything.

All 6 tasks done (329 tests passing). Key commits:
  d39ebaf + 9a0f1d5 : _sum_experience_months (year span + explicit years + cap)
  5e063ce           : _keyword_experience_level + detect_experience_level
  748e95e           : detect_function_type (keyword count scoring, tie -> general)
  3cb1bde           : _build_personalization_block (100-verb bank, 10 tone variants)
  ffa6a40           : build_finetuning_prompt extended (experience_level, function_type params)
  cc90f0e           : task file marked COMPLETE

If you are here for Phase 9, launch: .\jobos-v2-sessions.ps1 -Session phase-9
'@
    }

    "phase-9" = @{
        model = $SONNET
        label = "Phase 9 - Language Variation Engine"
        task  = "PHASE-09"
        prompt = @'
Stack: Python 3.13, app/llm/ (post-processing layer)
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Branch: feature/phase-02-upload-parse (329 tests passing)
Task file: tasks/PHASE-09-language-variation-engine.md

PHASE 8 IS COMPLETE. Do NOT redo it.
  app/llm/prompt_builder.py extended with:
    detect_experience_level(resume_text) -> str  (fresher/early/mid/senior)
    detect_function_type(jd_text) -> str         (technical/sales/operations/academic/general)
    _build_personalization_block(level, type) -> str  (10 verbs from 100-verb bank, 1 of 10 tone variants)
  build_finetuning_prompt() extended with optional experience_level + function_type params.
  54 tests in test_prompt_builder.py. 329 total passing.

PHASE 9: Language Variation Engine - anti-repetition phrase rotation

Scope: app/llm/variation_engine.py (new file only)

What to build:
  app/llm/variation_engine.py:
    BANNED_PHRASES    - list of cliche phrases to detect and replace (20+ entries)
    SYNONYM_GROUPS    - dict[str, list[str]] phrase -> alternatives (10+ groups)
    apply_variation(text: str) -> str
      - Detect any BANNED_PHRASES in text (case-insensitive)
      - Replace with a randomly selected alternative from SYNONYM_GROUPS
      - If no replacement exists: leave original (do not force bad phrasing)
      - Return modified text

  Integration: call apply_variation() on rewrite output BEFORE quality check (Phase 11)
  tests/test_variation_engine.py: one test per SYNONYM_GROUP minimum

Banned phrase examples:
  "cross-functional collaboration", "results-oriented", "passionate about",
  "proven track record", "dynamic professional", "transforming vision into reality",
  "mission-driven", "team player", "go-getter", "synergy", "leverage" (as filler),
  "detail-oriented", "self-starter", "thought leader", "moved the needle",
  "wear many hats", "out of the box", "value-add", "best-in-class", "world-class"

Rules:
  - NEVER change factual content - only rephrase cliches
  - Replacements must be grammatically correct in context
  - Pure Python stdlib only - no LLM call, no new dependencies
  - Unit-testable: each SYNONYM_GROUP must have at least one test
  - Use python -m pytest (not bare pytest) for all test runs

Before writing any code:
  1. Read CLAUDE.md (orient on Phase 9 scope: app/llm/variation_engine.py only)
  2. Read tasks/PHASE-09-language-variation-engine.md
  3. Use superpowers:brainstorming to explore the design
  4. Then use superpowers:writing-plans to produce an implementation plan
  5. Present the plan. Wait for "proceed" or "approved" before writing code.
'@
    }

    "phase-10" = @{
        model = $SONNET
        label = "Phase 10 - Payment Gate + Locked Download [DONE - 378 tests]"
        task  = "PHASE-10"
        prompt = @'
Stack: Python 3.13, Streamlit, Razorpay, SQLite
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Branch: feature/phase-02-upload-parse

PHASE 10 IS COMPLETE. Do NOT re-implement anything.

378 tests passing. Key commits:
  4c7224d : razorpay>=1.3.0 added to requirements.txt
  855838c : payment config fields (PAYMENT_PROVIDER, RAZORPAY_KEY_*, APP_BASE_URL)
  5a12250 : payment_link_id + payment_id columns in SubmissionsDB + SubmissionRecord
  42de9e9 : PaymentProvider ABC + OrderResult dataclass + factory
  1622d18 : RazorpayAdapter (Payment Links create_order + HMAC verify_payment)
  469b9c7 : fix: don't log razorpay_signature in verify_payment failure path
  a37807a : StripeAdapter stub (NotImplementedError)
  f5ad73e : watermark_pdf_bytes (PyMuPDF, in-memory, source untouched)
  878673b : _download_helpers (build_callback_url, has_razorpay_callback, get_price_paise)
  500f47f : 6_Download.py — payment gate, watermark, Razorpay callback verify
  16a2d31 : fix: prevent duplicate payment link on PAYMENT_PENDING re-entry
  efb104d : checkpoint: payment gate complete
  931d28e : docs: design spec + implementation plan committed

New module: app/payment/ (provider, razorpay_adapter, stripe_adapter, watermark)
New page  : app/ui/pages/6_Download.py
New helper: app/ui/pages/_download_helpers.py
DB        : payment_link_id + payment_id columns in submissions table
25 new tests in tests/test_payment.py

If you are here for Phase 11, launch: .\jobos-v2-sessions.ps1 -Session phase-11
'@
    }

    "phase-11" = @{
        model = $SONNET
        label = "Phase 11 - Quality Check Layer"
        task  = "PHASE-11"
        prompt = @'
Stack: Python 3.13, app/llm/ (REWRITE provider)
Project: resume-builder-v2 (JobOS Resume Builder v2.0)
Branch: feature/phase-02-upload-parse (378 tests passing)
Task file: tasks/PHASE-11-quality-check-layer.md

PHASE 10 IS COMPLETE. Do NOT redo it.
  app/payment/ module: RazorpayAdapter (Payment Links + HMAC verify), StripeAdapter stub,
    watermark_pdf_bytes (PyMuPDF in-memory), PaymentProvider ABC + factory.
  app/ui/pages/6_Download.py: payment gate page, watermarked preview, callback verify,
    clean PDF served only after PAYMENT_CONFIRMED. Duplicate link guard on re-entry.
  app/ui/pages/_download_helpers.py: build_callback_url, has_razorpay_callback, get_price_paise.
  DB: payment_link_id + payment_id columns in submissions table.
  25 new tests in tests/test_payment.py. 378 total passing.

PHASE 11: Quality Check Layer - pre-output validation before candidate sees resume

Scope: app/llm/quality_check.py (new file only)

What to build:
  app/llm/quality_check.py:
    validate_quality(resume_draft: dict, original: dict) -> QualityReport
      Checks:
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
  - Use python -m pytest (not bare pytest) for all test runs

Before writing any code:
  1. Read app/llm/variation_engine.py (Phase 9 output - apply_variation_to_resume)
  2. Read app/llm/finetuner.py (understand where to wire quality check in pipeline)
  3. Use superpowers:brainstorming to explore the design
  4. Then use superpowers:writing-plans to produce an implementation plan
  5. Present the plan. Wait for approval before writing code.
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

$promptContent = Get-Content $tmpPrompt -Raw
claude --model $s.model $promptContent

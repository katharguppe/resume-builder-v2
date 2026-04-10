# CLAUDE.md - resume-builder-v2 (JobOS Resume Builder v2.0)
# Extends ~/.claude/CLAUDE.md. Global rules always apply.
# THIS IS A NEW BUILD on a v1.x foundation. ~30% reuse, ~70% net new.

## 0. Prime Directive
Foundation code (v1.x) is battle-tested. Do NOT rewrite what works.
Build new features surgically on top of the foundation.

BEFORE touching any file:
  1. Read the file fully
  2. State what works and what is broken / missing
  3. Present a plan
  4. Wait for human approval
  5. Then make changes

## 1. Current Phase: 0 - SETUP COMPLETE. Begin Phase 1.
v1 foundation ported. All 12 phases queued below.

Phases (Option B — No Live Editor):
  1  -> Auth              — OTP accounts, session management         [PENDING]
  2  -> Upload/Parse      — resume + JD upload, port from v1        [PENDING]
  3  -> ATS Score Engine  — batch scoring, keyword/skills/structure  [PENDING]
  4  -> Review Page       — read-only output + accept/reject         [PENDING]
  5  -> Revision Request  — re-run LLM up to 3x per session         [PENDING]
  6  -> Missing Info      — severity-ranked panel (High/Med/Low)     [PENDING]
  7  -> Skills Builder    — grouped suggest + edit (Core/Tools/Func) [PENDING]
  8  -> Personalization   — experience level + function + tone       [PENDING]
  9  -> Variation Engine  — anti-repetition phrase rotation          [PENDING]
  10 -> Payment Gate      — payment + locked download                [PENDING]
  11 -> Quality Check     — pre-output validation layer              [PENDING]
  12 -> Integration/E2E   — extend v1 test suite                    [PENDING]

## 2. Stack
  Language          : Python 3.13
  Container         : Docker + docker-compose (LibreOffice inside)
  UI                : Streamlit on port 8501
  Auth              : OTP via email (smtplib) + SQLite sessions table
  LLM extract       : Gemini 2.0 Flash (default) | Claude Haiku 4.5 (fallback)
  LLM rewrite       : DeepSeek V3 (default) | Claude Sonnet 4.6 (fallback)
  LLM provider ctrl : LLM_EXTRACT_PROVIDER / LLM_REWRITE_PROVIDER env vars
  PDF read          : pdfplumber (text) + PyMuPDF/fitz (photos)
  DOC convert       : LibreOffice headless (inside Docker only)
  PDF write         : reportlab + PyMuPDF
  ATS scoring       : in-process Python (keyword/skills/structure, no LLM)
  Web search        : duckduckgo-search (best practice retrieval)
  Email             : smtplib — OTP delivery + MANUAL send trigger only
  State             : SQLite WAL mode — resume_builder.db
  Config            : python-dotenv via .env
  Payment           : Razorpay (India) or Stripe — pluggable via PAYMENT_PROVIDER env var

## 3. Critical Rules
  - LLM must NOT hallucinate facts. Rewrite tone/keywords only.
  - No live editor. UX = Submit → Wait (~5-10s) → Review → Revise (3x) → Download.
  - Email send: MANUAL trigger only (OTP delivery is automatic, resume send is manual).
  - LibreOffice runs inside Docker — NOT on host machine.
  - SQLite uses WAL mode.
  - ATS score computed in-process, NOT via LLM call.
  - Provider switch via env var only — no code changes to swap models.
  - Payment gate: download locked until payment_confirmed = true in DB.
  - Revision cap: max 3 revisions per session (enforced in DB + UI).
  - No exaggeration: LLM rewrites tone/keywords only, never invents facts.

## 4. Module Boundaries
  Session -> phase-1   : app/auth/ only (new module)
  Session -> phase-2   : app/ingestor/ only (port + extend from v1)
  Session -> phase-3   : app/scoring/ only (new ATS scoring module)
  Session -> phase-4   : app/ui/pages/3_Review.py only
  Session -> phase-5   : app/ui/pages/4_Revise.py + app/llm/ revision logic
  Session -> phase-6   : app/scoring/missing_info.py + UI panel
  Session -> phase-7   : app/ui/pages/5_Skills.py + app/skills/ module
  Session -> phase-8   : app/llm/prompt_builder.py (personalization extend)
  Session -> phase-9   : app/llm/variation_engine.py (new)
  Session -> phase-10  : app/payment/ only (new module)
  Session -> phase-11  : app/llm/quality_check.py (new)
  Session -> phase-12  : tests/ only
  Session -> debug     : one error + one file per session

## 5. LLM Interface (v2 — provider-agnostic)
  extract_fields(resume_text)                          -> uses EXTRACT provider
  score_resume(resume_fields, jd_fields)               -> in-process, no LLM
  rewrite_resume(resume_text, jd_text, best_practice,
                 experience_level, function_type)      -> uses REWRITE provider
  validate_quality(resume_draft)                       -> uses REWRITE provider
  All adapters in app/llm/finetuner.py.
  Provider routing in app/llm/provider.py (new).
  Models from .env — never hardcoded.

## 6. Status Machine v2.0
  PENDING
  -> PROCESSING (resume + JD parsed, ATS scored)
  -> REVIEW_READY (AI draft generated, awaiting candidate review)
  -> REVISION_REQUESTED (candidate requested re-run, count: 1/2/3)
  -> REVISION_EXHAUSTED (3 revisions used, must accept or abandon)
  -> ACCEPTED (candidate accepted draft)
  -> PAYMENT_PENDING (payment initiated)
  -> PAYMENT_CONFIRMED (payment verified)
  -> DOWNLOAD_READY (PDF unlocked)
  -> DOWNLOADED (PDF delivered)
  Any state -> ERROR on failure

## 7. SE Process Rules (READ THESE)
  pdca-gate.md      — plan artifact → wait → execute → walkthrough → wait → commit
  git-discipline.md — branch naming, pre-commit diff gate, NEVER auto-commit
  generate-tests.md — test generation workflow per module (/generate-tests app/module/)
  SKILL.md          — PRD executor protocol: Orient→Plan→Gate→Execute→Verify→Report→Gate→Advance

## 8. Git Format
  [PHASE-XX] add|fix|refactor|docs|test: what changed
  [PHASE-XX] checkpoint: step name - verified
  Branch: feature/phase-XX-short-slug (never commit to master directly)

## 9. Preserved from v1 — Do NOT break
  app/ingestor/extractor.py    — text + face photo extraction (headshot heuristic)
  app/ingestor/converter.py    — LibreOffice DOC→PDF conversion
  app/composer/pdf_writer.py   — ReportLab PDF layout (teal headers, HRFlowable)
  app/composer/photo_handler.py — face photo crop and embed
  app/best_practice/           — DuckDuckGo web search + loader
  app/email_handler/           — Fernet crypto + manual send + templates
  docker/                      — Dockerfile + docker-compose (LibreOffice)
  tests/                       — 82 passing tests — must stay green

## 10. New Modules to Build (v2 net-new)
  app/auth/          — OTP generation, session tokens, user table
  app/scoring/       — ATS score engine, missing info engine
  app/skills/        — skills grouping + suggestion logic
  app/payment/       — payment provider adapter (Razorpay/Stripe)
  app/llm/provider.py         — provider routing (Gemini/DeepSeek/Claude)
  app/llm/variation_engine.py — anti-repetition phrase rotation
  app/llm/quality_check.py    — pre-output validation
  app/ui/pages/3_Review.py    — candidate review page
  app/ui/pages/4_Revise.py    — revision request page
  app/ui/pages/5_Skills.py    — skills builder page
  app/ui/pages/6_Download.py  — payment + download page

## 11. Runtime Cost Reference (per 1,000 candidates)
  Gemini Flash + DeepSeek V3   : ~$9     (default)
  Claude Haiku + Sonnet        : ~$110   (fallback / quality baseline)
  Break-even on Max license    : ~1,700 candidates

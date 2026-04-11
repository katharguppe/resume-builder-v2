# ==============================================================================
# setup-resume-builder-v2.ps1
# Project bootstrap for JobOS Resume Builder v2.0
# Run from D:\staging\resume-builder-v2
# Owner: Srinivas / Fidelitus Corp
# ==============================================================================

$PROJECT_NAME = "resume-builder-v2"
$PROJECT_ROOT = "D:\staging\resume-builder-v2"

Write-Host ""
Write-Host "JobOS Resume Builder v2.0 - PROJECT BOOTSTRAP" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $PROJECT_ROOT)) {
    Write-Host "X Project root not found: $PROJECT_ROOT" -ForegroundColor Red
    exit 1
}
Set-Location $PROJECT_ROOT
Write-Host "OK Project root found." -ForegroundColor Green

# ── 1. Folders ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 1/7 ] Creating folders..." -ForegroundColor Yellow
$folders = @(
    "docker",
    ".claude\skills",
    "docs",
    "docs\superpowers\specs",
    "docs\superpowers\plans",
    "tasks",
    ".checkpoints",
    "app\auth",
    "app\scoring",
    "app\skills",
    "app\payment",
    "app\llm"
)
foreach ($f in $folders) {
    $path = Join-Path $PROJECT_ROOT $f
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
        Write-Host "  OK $f" -ForegroundColor Green
    } else {
        Write-Host "  . $f (exists)" -ForegroundColor DarkGray
    }
}

# ── 2. .gitignore ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 2/7 ] Writing .gitignore..." -ForegroundColor Yellow
if (-not (Test-Path "$PROJECT_ROOT\.gitignore")) {
@"
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/

# Env
.env
*.env

# DB
*.db
*.db-shm
*.db-wal

# IDE
.vscode/
.idea/

# Test cache
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db

# Docker build cache
docker/build.log

# Temp output files
*.pdf
!tests/fixtures/*.pdf
"@ | Set-Content "$PROJECT_ROOT\.gitignore" -Encoding UTF8
    Write-Host "  OK .gitignore" -ForegroundColor Green
} else {
    Write-Host "  . .gitignore (exists)" -ForegroundColor DarkGray
}

# ── 3. .env.example ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 3/7 ] Writing .env.example..." -ForegroundColor Yellow
@"
# ==============================================================================
# JobOS Resume Builder v2.0 - Environment Variables
# Copy this to .env and fill in all values before running.
# ==============================================================================

# ── LLM Providers ─────────────────────────────────────────────────────────────
# Provider selection: "gemini" | "claude" | "deepseek"
LLM_EXTRACT_PROVIDER=gemini
LLM_REWRITE_PROVIDER=deepseek

# Gemini (default extract + ATS scoring)
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_EXTRACT_MODEL=gemini-2.0-flash

# DeepSeek (default rewrite + quality check)
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEEPSEEK_REWRITE_MODEL=deepseek-chat

# Claude (fallback - keep populated for quality recovery)
ANTHROPIC_API_KEY=sk-ant-your-key-here
LLM_REWRITE_MODEL=claude-sonnet-4-6
LLM_EXTRACT_MODEL=claude-haiku-4-5-20251001

MAX_LLM_RETRIES=3
BEST_PRACTICE_MAX_TOKENS=3000

# ── Auth / OTP ─────────────────────────────────────────────────────────────────
OTP_EXPIRY_MINUTES=10
OTP_LENGTH=6
SESSION_SECRET=generate-a-random-32-char-string-here
SESSION_EXPIRY_HOURS=24

# ── Email (OTP delivery + manual resume send) ──────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD_ENCRYPTED=           # Use crypto.py to encrypt raw password
ENCRYPTION_KEY=                    # Fernet key - generate once, never regenerate

# ── Payment ────────────────────────────────────────────────────────────────────
# Provider: "razorpay" | "stripe"
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=your-razorpay-key-id
RAZORPAY_KEY_SECRET=your-razorpay-key-secret
STRIPE_PUBLISHABLE_KEY=
STRIPE_SECRET_KEY=
RESUME_DOWNLOAD_PRICE_INR=99

# ── Storage ────────────────────────────────────────────────────────────────────
SOURCE_FOLDER=C:\Users\K S S\jobs\input
DEST_FOLDER=C:\Users\K S S\jobs\output
DB_PATH=resume_builder.db

# ── App ────────────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
MAX_REVISIONS=3
"@ | Set-Content "$PROJECT_ROOT\.env.example" -Encoding UTF8
Write-Host "  OK .env.example" -ForegroundColor Green

# ── 4. .mcp.json ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 4/7 ] Writing .mcp.json..." -ForegroundColor Yellow
$npmGlobalRoot = (npm root -g 2>$null).Trim()
if ($npmGlobalRoot) {
@"
{
  "mcpServers": {
    "filesystem": {
      "command": "node",
      "args": ["$npmGlobalRoot\\@modelcontextprotocol\\server-filesystem\\dist\\index.js", "$PROJECT_ROOT"]
    },
    "memory": {
      "command": "node",
      "args": ["$npmGlobalRoot\\@modelcontextprotocol\\server-memory\\dist\\index.js"]
    },
    "sequential-thinking": {
      "command": "node",
      "args": ["$npmGlobalRoot\\@modelcontextprotocol\\server-sequential-thinking\\dist\\index.js"]
    }
  }
}
"@ | Set-Content "$PROJECT_ROOT\.mcp.json" -Encoding UTF8
    Write-Host "  OK .mcp.json (npm root: $npmGlobalRoot)" -ForegroundColor Green
} else {
    Write-Host "  ! npm not found. Writing .mcp.json with placeholder paths." -ForegroundColor Yellow
    Write-Host "    Edit .mcp.json manually after npm install -g @modelcontextprotocol/server-*" -ForegroundColor Yellow
@"
{
  "mcpServers": {
    "filesystem": {
      "command": "node",
      "args": ["C:\\Users\\K S S\\AppData\\Roaming\\npm\\node_modules\\@modelcontextprotocol\\server-filesystem\\dist\\index.js", "$PROJECT_ROOT"]
    },
    "memory": {
      "command": "node",
      "args": ["C:\\Users\\K S S\\AppData\\Roaming\\npm\\node_modules\\@modelcontextprotocol\\server-memory\\dist\\index.js"]
    },
    "sequential-thinking": {
      "command": "node",
      "args": ["C:\\Users\\K S S\\AppData\\Roaming\\npm\\node_modules\\@modelcontextprotocol\\server-sequential-thinking\\dist\\index.js"]
    }
  }
}
"@ | Set-Content "$PROJECT_ROOT\.mcp.json" -Encoding UTF8
}

# ── 5. .claude/settings.local.json ────────────────────────────────────────────
Write-Host ""
Write-Host "[ 5/7 ] Writing .claude/settings.local.json..." -ForegroundColor Yellow
if (-not (Test-Path "$PROJECT_ROOT\.claude")) {
    New-Item -ItemType Directory -Path "$PROJECT_ROOT\.claude" | Out-Null
}
@"
{
  "permissions": {
    "allow": [
      "Bash(python:*)",
      "Bash(pytest:*)",
      "Bash(pip:*)",
      "Bash(git:*)",
      "Bash(gh:*)"
    ]
  }
}
"@ | Set-Content "$PROJECT_ROOT\.claude\settings.local.json" -Encoding UTF8
Write-Host "  OK .claude/settings.local.json" -ForegroundColor Green

# ── 6. Skill files ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 6/7 ] Writing skill files..." -ForegroundColor Yellow

# SKILLS.md index
@"
# SKILLS.md - resume-builder-v2

## Available Skills
  task-create       : Create new PHASE-XX task file with PDCA template
  audit-module      : Audit one module, report only - NO code changes
  add-test          : Add pytest test for a fixed or new function
  ats-scorer        : Design/implement ATS scoring logic for a section
  personalization   : Apply experience-level + function-type rewrite rules
  variation-engine  : Implement phrase rotation anti-repetition logic
"@ | Set-Content "$PROJECT_ROOT\SKILLS.md" -Encoding UTF8

# task-create skill
@"
# Skill: task-create
# Command: task-create
# Creates a new PHASE-XX.md in /tasks/ with PDCA template.

## Steps
1. Ask: task title and which phase (1-12)?
2. List tasks/ to confirm no duplicate.
3. Create tasks/PHASE-XX-slug.md with full PDCA template.
4. Create git branch: feature/phase-XX-slug
5. Report file path + branch name.
"@ | Set-Content "$PROJECT_ROOT\.claude\skills\task-create.md" -Encoding UTF8

# audit-module skill
@"
# Skill: audit-module
# Command: audit-module
# Audits one module. Produces report. NO code changes.

## Steps
1. Ask: which module? (auth/ingestor/scoring/skills/payment/llm/composer/ui)
2. Use filesystem MCP to read every file in app/module/
3. For each function assess:
   - Does it match the v2 CLAUDE.md spec?
   - Is it ported correctly from v1 (if applicable)?
   - Are there bugs or missing logic?
   - Does it have tests?
4. Produce audit report:
   - Preserved: functions ported intact from v1
   - Working: new functions that look correct
   - Broken: functions with issues
   - Missing: functions in spec not yet implemented
5. Save report to docs/audit-module.md
6. Present to human. Wait for approval before any code change.
"@ | Set-Content "$PROJECT_ROOT\.claude\skills\audit-module.md" -Encoding UTF8

# add-test skill
@"
# Skill: add-test
# Command: add-test
# Adds a pytest test for a newly written or fixed function.

## Steps
1. Ask: which function and which module?
2. Read existing tests/test_module.py
3. Write one new test following existing patterns
4. Run: pytest tests/test_module.py -v
5. Report: pass or fail.
"@ | Set-Content "$PROJECT_ROOT\.claude\skills\add-test.md" -Encoding UTF8

# ats-scorer skill
@"
# Skill: ats-scorer
# Command: ats-scorer
# Design or implement one section of the ATS scoring engine.

## Scope
app/scoring/ only. No LLM calls - pure Python keyword/skills/structure scoring.

## Steps
1. Ask: which score component? (keyword-match | skills-coverage | experience-clarity | structure-completeness)
2. Read app/scoring/ current state
3. Propose scoring algorithm with score weight
4. Wait for human approval
5. Implement and add test
6. Run pytest tests/test_scoring.py -v
"@ | Set-Content "$PROJECT_ROOT\.claude\skills\ats-scorer.md" -Encoding UTF8

# personalization skill
@"
# Skill: personalization
# Command: personalization
# Apply experience-level + function-type rewrite rules to prompt_builder.py

## Scope
app/llm/prompt_builder.py only.

## Experience levels: fresher | early | mid | senior
## Function types: technical | sales | operations | academic | general

## Steps
1. Read current app/llm/prompt_builder.py
2. Identify which level/function is missing or weak
3. Propose prompt additions - no fabrication, no over-positioning
4. Wait for human approval
5. Implement and add test
"@ | Set-Content "$PROJECT_ROOT\.claude\skills\personalization.md" -Encoding UTF8

# variation-engine skill
@"
# Skill: variation-engine
# Command: variation-engine
# Build or extend the Language Variation Engine (anti-repetition).

## Scope
app/llm/variation_engine.py only.

## Rules
- Maintain a banned-phrase list (cliches to avoid)
- Maintain synonym groups (rotate phrasing across candidates)
- Post-process LLM output to detect and replace repeated phrases
- Never change facts - only rephrase

## Steps
1. Read app/llm/variation_engine.py current state
2. Propose new phrase group or rotation rule
3. Wait for human approval
4. Implement and add test
"@ | Set-Content "$PROJECT_ROOT\.claude\skills\variation-engine.md" -Encoding UTF8

Write-Host "  OK 6 skill files written." -ForegroundColor Green

# ── 7. TASK stubs ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 7/7 ] Creating PHASE task stubs..." -ForegroundColor Yellow

$tasks = @(
    @{ id="01"; title="Auth OTP Accounts Session Management"; phase=1 },
    @{ id="02"; title="Resume JD Upload Parse"; phase=2 },
    @{ id="03"; title="ATS Score Engine Batch"; phase=3 },
    @{ id="04"; title="Resume Review Page"; phase=4 },
    @{ id="05"; title="Revision Request Up To 3x"; phase=5 },
    @{ id="06"; title="Missing Information Engine"; phase=6 },
    @{ id="07"; title="Skills Section Builder"; phase=7 },
    @{ id="08"; title="Personalization Logic"; phase=8 },
    @{ id="09"; title="Language Variation Engine"; phase=9 },
    @{ id="10"; title="Payment Gate Locked Download"; phase=10 },
    @{ id="11"; title="Quality Check Layer"; phase=11 },
    @{ id="12"; title="Integration E2E Tests"; phase=12 }
)

foreach ($t in $tasks) {
    $slug = ($t.title -replace ' ','-').ToLower() -replace '[^a-z0-9\-]',''
    $filename = "PHASE-$($t.id)-$slug.md"
    $filepath = "$PROJECT_ROOT\tasks\$filename"
    if (-not (Test-Path $filepath)) {
        @"
# PHASE-$($t.id): $($t.title)

## Status: PENDING
## Phase: $($t.phase) / 12

## Objective
Describe what DONE looks like for this phase.

## v1 Foundation
List any v1 modules/functions being reused or extended here.

## Net New
List new files/functions to build.

## PDCA Log

### Cycle 1
**Plan:**
**Approved by human:** Pending
**Do:**
**Check:**
**Act:**

## Open Questions

## Decisions Made

## Checkpoints
"@ | Set-Content $filepath -Encoding UTF8
        Write-Host "  OK tasks/$filename" -ForegroundColor Green
    } else {
        Write-Host "  . tasks/$filename (exists)" -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  OK resume-builder-v2 bootstrap complete." -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Yellow
Write-Host "  1. Copy .env.example to .env and fill in ALL API keys" -ForegroundColor Cyan
Write-Host "     - GEMINI_API_KEY (Google AI Studio)" -ForegroundColor Cyan
Write-Host "     - DEEPSEEK_API_KEY (platform.deepseek.com)" -ForegroundColor Cyan
Write-Host "     - ANTHROPIC_API_KEY (Claude fallback)" -ForegroundColor Cyan
Write-Host "     - SMTP + ENCRYPTION_KEY (from v1 .env)" -ForegroundColor Cyan
Write-Host "     - PAYMENT_PROVIDER + keys" -ForegroundColor Cyan
Write-Host "  2. Run: .\jobos-v2-sessions.ps1 -Session list" -ForegroundColor Cyan
Write-Host "  3. Run: .\jobos-v2-sessions.ps1 -Session phase-1" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Green

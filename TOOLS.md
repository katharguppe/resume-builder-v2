# TOOLS.md - resume-builder-v2

## Claude Code Plugins (Superpowers)
  superpowers             : start any phase, brainstorm before building
  superpowers:tdd         : write tests before implementation
  superpowers:debugging   : systematic debugging for any error
  context7                : Gemini SDK / DeepSeek / pdfplumber / PyMuPDF / reportlab / Streamlit / Anthropic SDK
  code-simplifier         : after a module passes tests
  context-mode            : reading large existing files

## MCP Servers
  filesystem           : read existing files without pasting
  memory               : persist phase findings, broken functions list
  sequential-thinking  : architecture design, provider adapter patterns

## SE Process Rules (read before every phase)
  pdca-gate.md      : Plan artifact → approval → execute → walkthrough → approval → commit
  git-discipline.md : Branch naming, pre-commit diff gate, NEVER auto-commit
  generate-tests.md : /generate-tests app/module/ - generate tests after code is done
  SKILL.md          : PRD executor protocol - Orient → Plan → Gate → Execute → Verify → Report → Gate → Advance

## Startup Order (IMPORTANT)
  Step 1: .\setup-resume-builder-v2.ps1          <- run FIRST on fresh clone or new machine
  Step 2: .\jobos-v2-sessions.ps1 -Session list  <- then list sessions
  Step 3: .\jobos-v2-sessions.ps1 -Session phase-1

## Session Launcher
  .\jobos-v2-sessions.ps1 -Session list          <- show all sessions
  .\jobos-v2-sessions.ps1 -Session phase-1       <- start Phase 1
  .\jobos-v2-sessions.ps1 -Session debug         <- debug a single error

## Docker Commands (require human approval)
  docker-compose -f docker/docker-compose.yml build
  docker-compose -f docker/docker-compose.yml up
  docker-compose -f docker/docker-compose.yml up --build
  docker-compose -f docker/docker-compose.yml down
  docker-compose -f docker/docker-compose.yml logs resume-builder

## Test Commands
  pytest -v
  pytest tests/test_auth.py -v
  pytest tests/test_scoring.py -v
  pytest tests/test_e2e_v2.py -v

## Key Libraries (use context7 for all)
  google-generativeai / google-genai  : Gemini Flash (extract)
  openai (deepseek base_url)          : DeepSeek V3 (rewrite)
  anthropic                           : Claude fallback
  pdfplumber                          : PDF text extraction
  PyMuPDF (fitz)                      : PDF photo extraction
  reportlab                           : PDF composition
  streamlit                           : UI framework
  duckduckgo-search                   : best practice retrieval
  python-dotenv                       : .env loading
  cryptography                        : Fernet SMTP password encryption
  razorpay                            : payment (India default)

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

## Session Launcher
  .\jobos-v2-sessions.ps1 -Session list          <- show all sessions
  .\jobos-v2-sessions.ps1 -Session phase-1       <- start Phase 1

## Bootstrap
  .\setup-resume-builder-v2.ps1                  <- re-run if folders/files missing

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

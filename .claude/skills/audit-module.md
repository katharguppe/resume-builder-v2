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

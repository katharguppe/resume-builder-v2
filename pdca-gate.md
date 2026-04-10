# pdca-gate.md
# Workspace Rule: PDCA Gate — Plan Before Execute
# Applies to every session in this workspace.
# ─────────────────────────────────────────────────────────────────────────────

## The Rule

Before writing a single line of code, produce a written plan.

The plan must include:
1. Which files will be created
2. Which files will be modified
3. Which functions/classes will be added or changed
4. What the acceptance test is (how we verify it works)
5. Risk: what could break in other modules as a side effect

Then STOP. Wait for "proceed" or "approved".

Only after approval: execute the plan.

## After Execution

After all code is written:
1. Produce a Walkthrough summary of what was built.
2. Show the git diff (run `git diff --staged`).
3. Wait for approval before committing.

## Scope Creep Rule

If during execution you discover that the task requires touching a file
outside the originally approved scope, STOP immediately.
Report what you found and why. Ask for approval before continuing.
Do not silently expand scope.

## Failed Task Protocol

If a task fails after two attempts (tests fail, app won't start, etc.):
1. Stop trying.
2. Produce a Failure Report with:
   - What was attempted
   - What error occurred
   - What the root cause likely is
   - Two alternative approaches
3. Wait for a decision on which path to take.

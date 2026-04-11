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

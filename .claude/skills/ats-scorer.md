# Skill: ats-scorer
# Command: ats-scorer
# Design or implement one section of the ATS scoring engine.

## Scope
app/scoring/ only. No LLM calls â€” pure Python keyword/skills/structure scoring.

## Steps
1. Ask: which score component? (keyword-match | skills-coverage | experience-clarity | structure-completeness)
2. Read app/scoring/ current state
3. Propose scoring algorithm with score weight
4. Wait for human approval
5. Implement and add test
6. Run pytest tests/test_scoring.py -v

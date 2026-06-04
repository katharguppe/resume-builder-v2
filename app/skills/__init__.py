"""
app/skills — Skills grouper and suggester for Phase 7 Skills Builder.

Public API:
    group_skills(raw_skills: List[str]) -> SkillGroups
    suggest_skills(jd_fields: dict, resume_fields: dict) -> List[str]
    SkillGroups (dataclass: core, tools, functional, domain)
"""
from app.skills.grouper import group_skills, SkillGroups
from app.skills.suggester import suggest_skills

__all__ = ["group_skills", "suggest_skills", "SkillGroups"]

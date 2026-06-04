"""
Skills grouper — classifies a flat skill list into Core/Tools/Functional/Domain.

Groups are loaded from YAML files in app/skills/keywords/ at module import.
Adding a new industry domain = drop a new .yaml file in that directory.
No code changes required.

Groups are UI-only. They are never persisted to the DB.
"""
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

import yaml

logger = logging.getLogger(__name__)

KEYWORDS_DIR = Path(__file__).parent / "keywords"


@dataclass
class SkillGroups:
    """Flat skills list partitioned into four display buckets."""
    core: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    functional: List[str] = field(default_factory=list)
    domain: List[str] = field(default_factory=list)


def _load_keyword_sets() -> Dict[str, Set[str]]:
    """Load and merge all YAML files from keywords/ into four sets (lowercased)."""
    sets: Dict[str, Set[str]] = {
        "core": set(),
        "tools": set(),
        "functional": set(),
        "domain": set(),
    }
    for yaml_file in sorted(KEYWORDS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            for group in ("core", "tools", "functional", "domain"):
                for kw in data.get(group, []):
                    sets[group].add(str(kw).lower())
        except Exception as e:
            logger.warning("Failed to load keyword file %s: %s", yaml_file.name, e)
    return sets


# Loaded once at module import — cheap in-process, no I/O on page reruns.
_KEYWORD_SETS: Dict[str, Set[str]] = _load_keyword_sets()


def _matches(skill_lower: str, keyword_set: Set[str]) -> bool:
    """Return True if skill_lower contains any keyword as a whole word."""
    for kw in keyword_set:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, skill_lower):
            return True
    return False


def group_skills(raw_skills: List[str]) -> SkillGroups:
    """
    Classify a flat list of skills into Core / Tools / Functional / Domain.

    Matching order: Core → Tools → Functional → Domain → Core (default).
    Original casing is preserved in output.
    Unknown skills fall to Core.
    """
    result = SkillGroups()
    for skill in raw_skills:
        skill_lower = skill.lower()
        if _matches(skill_lower, _KEYWORD_SETS["core"]):
            result.core.append(skill)
        elif _matches(skill_lower, _KEYWORD_SETS["tools"]):
            result.tools.append(skill)
        elif _matches(skill_lower, _KEYWORD_SETS["functional"]):
            result.functional.append(skill)
        elif _matches(skill_lower, _KEYWORD_SETS["domain"]):
            result.domain.append(skill)
        else:
            result.core.append(skill)  # default bucket
    return result

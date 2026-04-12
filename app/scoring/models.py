from dataclasses import dataclass, field
from typing import List


@dataclass
class ATSScore:
    total: int
    keyword_match: int
    skills_coverage: int
    experience_clarity: int
    structure_completeness: int
    keyword_matched: List[str] = field(default_factory=list)
    skills_matched: List[str] = field(default_factory=list)
    skills_missing: List[str] = field(default_factory=list)


@dataclass
class MissingItem:
    field: str
    label: str
    severity: str   # "HIGH" | "MEDIUM" | "LOW"
    hint: str

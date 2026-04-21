import copy
import random
import re


BANNED_PHRASES: list[str] = [
    # With synonym groups — replaced on match
    "cross-functional",
    "results-driven",
    "self-starter",
    "team player",
    "detail-oriented",
    "go-getter",
    "synergy",
    "leverage",
    "proactive",
    "dynamic",
    "passionate about",
    "thought leader",
    # No-replacement entries — detected only, left untouched
    "go above and beyond",
    "think outside the box",
    "value add",
    "low-hanging fruit",
    "move the needle",
    "circle back",
    "at the end of the day",
    "hit the ground running",
]

SYNONYM_GROUPS: dict[str, list[str]] = {
    "cross-functional": ["multi-team", "cross-team", "organisation-wide", "interdepartmental"],
    "results-driven": ["outcome-focused", "delivery-focused", "performance-oriented"],
    "self-starter": ["independent worker", "takes initiative", "works independently"],
    "team player": ["collaborative", "works well with others", "strong team contributor"],
    "detail-oriented": ["thorough", "precise", "meticulous"],
    "go-getter": ["motivated", "driven", "ambitious"],
    "synergy": ["collaboration", "alignment", "joint effort"],
    "leverage": ["use", "apply", "draw on"],
    "proactive": ["forward-thinking", "anticipates needs", "ahead of the curve"],
    "dynamic": ["adaptable", "versatile", "high-energy"],
    "passionate about": ["committed to", "focused on", "dedicated to"],
    "thought leader": ["subject matter expert", "domain expert", "recognised authority"],
}

# Compiled once at module load — avoids re-compiling on every call.
# Only phrases in SYNONYM_GROUPS get a pattern; no-replacement entries are skipped.
_COMPILED_PATTERNS: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE), alternatives)
    for phrase, alternatives in SYNONYM_GROUPS.items()
]


def _replace_preserving_case(match: re.Match, alternatives: list[str]) -> str:
    replacement = random.choice(alternatives)
    if match.group(0)[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def apply_variation(text: str) -> str:
    """
    Detect any phrase present in SYNONYM_GROUPS and replace it with a randomly
    selected alternative. Preserves lead capitalisation of the match.
    Phrases in BANNED_PHRASES with no synonym group are left untouched.
    """
    for pattern, alternatives in _COMPILED_PATTERNS:
        text = pattern.sub(
            lambda m, alts=alternatives: _replace_preserving_case(m, alts),
            text,
        )
    return text


def apply_variation_to_resume(data: dict) -> dict:
    raise NotImplementedError

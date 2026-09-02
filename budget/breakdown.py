"""
Breakdown - what is actually in each scene, and how hard it is to generate.

Props come from the screenwriting convention that a prop or effect is
CAPITALISED on first appearance, so no model is needed to find them - just the
discipline to filter out everything else that shouts in caps (headings, cues,
transitions, sentence-starting shouts).

Complexity is a transparent, weighted score over signals a producer can argue
with: cast size, prop count, effects language, crowds, animals, night, exterior,
and how action-heavy the scene is. Every point it awards is recorded as a
`driver` so the bid can be defended line by line rather than asserted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .script import (ANIMAL_KEYWORDS, CAPS_RUN_RE, CROWD_KEYWORDS, NOT_PROPS,
                     VFX_KEYWORDS, Scene, Script)


class Tier(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    HERO = "hero"


# How the score maps to a tier. Inclusive upper bounds.
TIER_BANDS = [(2, Tier.SIMPLE), (5, Tier.MODERATE), (9, Tier.COMPLEX)]

# Weight caps keep one loud signal from swamping the rest.
WEIGHTS = {
    "cast_over_two": (1, 4),      # per extra speaking character, capped
    "props_per_four": (1, 3),
    "effects": (2, 6),
    "crowd": (2, 2),
    "animals": (1, 1),
    "night": (1, 1),
    "exterior": (1, 1),
    "action_heavy": (2, 2),
}
ACTION_HEAVY_RATIO = 0.7


@dataclass
class Complexity:
    score: int
    tier: Tier
    drivers: list[str] = field(default_factory=list)


@dataclass
class SceneBreakdown:
    scene: Scene
    props: list[str]
    effects: list[str]
    crowd: bool
    animals: bool
    complexity: Complexity

    @property
    def number(self) -> int:
        return self.scene.number

    @property
    def cast(self) -> list[str]:
        return self.scene.characters


@dataclass
class Breakdown:
    script: Script
    scenes: list[SceneBreakdown]

    @property
    def characters(self) -> list[str]:
        return self.script.characters

    @property
    def locations(self) -> list[str]:
        return self.script.locations

    @property
    def props(self) -> list[str]:
        seen = []
        for sb in self.scenes:
            for prop in sb.props:
                if prop not in seen:
                    seen.append(prop)
        return seen

    def by_tier(self) -> dict[Tier, int]:
        counts = {tier: 0 for tier in Tier}
        for sb in self.scenes:
            counts[sb.complexity.tier] += 1
        return counts


# ---------------------------------------------------------------------------
# Props
# ---------------------------------------------------------------------------

def extract_props(scene: Scene, characters: set[str]) -> list[str]:
    """CAPS runs in the action, minus the caps that are never props."""
    found: list[str] = []
    for line in scene.action:
        # A line that is entirely caps is a shout or a slug, not a prop list.
        letters = [c for c in line if c.isalpha()]
        if letters and all(c.isupper() for c in letters):
            continue
        for match in CAPS_RUN_RE.finditer(line):
            phrase = match.group(1).strip()
            if _is_prop(phrase, characters) and phrase not in found:
                found.append(phrase)
    return found


def _is_prop(phrase: str, characters: set[str]) -> bool:
    if phrase in characters:
        return False
    lowered = phrase.lower()
    if lowered in VFX_KEYWORDS:
        return False                                    # BLOOD, FIRE - an effect, not a prop
    if lowered in CROWD_KEYWORDS or lowered in ANIMAL_KEYWORDS:
        return False                                    # a CROWD is background, not a prop
    words = phrase.split()
    if any(w.rstrip("'S") in characters for w in words):
        return False                                    # MARA'S JACKET -> the jacket is hers
    if all(w in NOT_PROPS for w in words):
        return False
    if len(phrase) < 3 or phrase.isdigit():
        return False
    if re.fullmatch(r"[IVXLC]+", phrase):               # roman numerals
        return False
    return True


# ---------------------------------------------------------------------------
# Keyword signals
# ---------------------------------------------------------------------------

def _hits(text: str, vocabulary: set[str]) -> list[str]:
    lowered = text.lower()
    return sorted({word for word in vocabulary
                   if re.search(rf"\b{re.escape(word)}\b", lowered)})


# ---------------------------------------------------------------------------
# Complexity
# ---------------------------------------------------------------------------

def _award(drivers: list[str], amount: int, cap: int, reason: str) -> int:
    given = min(amount, cap)
    if given > 0:
        drivers.append(f"+{given} {reason}")
    return given


def score_scene(scene: Scene, props: list[str], effects: list[str],
                crowd: bool, animals: bool) -> Complexity:
    drivers: list[str] = []
    score = 0

    per, cap = WEIGHTS["cast_over_two"]
    score += _award(drivers, per * max(0, len(scene.characters) - 2), cap,
                    f"cast of {len(scene.characters)}")

    per, cap = WEIGHTS["props_per_four"]
    score += _award(drivers, per * (len(props) // 4), cap, f"{len(props)} props")

    per, cap = WEIGHTS["effects"]
    if effects:
        score += _award(drivers, per * len(effects), cap,
                        "effects work (" + ", ".join(effects[:4]) + ")")

    per, cap = WEIGHTS["crowd"]
    if crowd:
        score += _award(drivers, per, cap, "crowd / background action")

    per, cap = WEIGHTS["animals"]
    if animals:
        score += _award(drivers, per, cap, "animals")

    per, cap = WEIGHTS["night"]
    if scene.is_night:
        score += _award(drivers, per, cap, "night / low-light continuity")

    per, cap = WEIGHTS["exterior"]
    if scene.is_exterior:
        score += _award(drivers, per, cap, "exterior world-building")

    total_lines = len(scene.action) + len(scene.dialogue)
    if total_lines and len(scene.action) / total_lines > ACTION_HEAVY_RATIO:
        per, cap = WEIGHTS["action_heavy"]
        score += _award(drivers, per, cap, "action-heavy (more coverage)")

    tier = Tier.HERO
    for ceiling, band in TIER_BANDS:
        if score <= ceiling:
            tier = band
            break
    if not drivers:
        drivers.append("+0 dialogue scene, single setup")
    return Complexity(score=score, tier=tier, drivers=drivers)


def break_down(script: Script) -> Breakdown:
    characters = set(script.characters)
    scenes = []
    for scene in script.scenes:
        text = scene.action_text
        props = extract_props(scene, characters)
        effects = _hits(text, VFX_KEYWORDS)
        crowd = bool(_hits(text, CROWD_KEYWORDS))
        animals = bool(_hits(text, ANIMAL_KEYWORDS))
        scenes.append(SceneBreakdown(
            scene=scene, props=props, effects=effects, crowd=crowd, animals=animals,
            complexity=score_scene(scene, props, effects, crowd, animals)))
    return Breakdown(script=script, scenes=scenes)

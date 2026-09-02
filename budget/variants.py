"""
The image-level asset plan.

A budget built on "how many characters are there" is wrong, because a character
is not one image. MARA in a soaked paramedic jacket at night and MARA on a roof
at dawn are two images to generate, approve and keep consistent. Same for a
location: ST. BRENDAN'S ROOF at DAWN is not the same plate as at NIGHT, and
"in the rain" is a third.

So this module counts VARIANTS, not names:

  location   one per (location x time-of-day x weather) actually used
  character  one per look block - a new look when the time of day changes
             against that character's previous appearance, which is the closest
             deterministic proxy for a story-day / wardrobe change - but ONLY
             for characters who recur. A one-scene walk-on never gets a sheet;
             they are covered by that scene's wardrobe plate
  prop       one per prop, unless the prop is flagged as changing state
  wardrobe   one continuity plate per SCENE. A character look covers a block of
             scenes, but wardrobe has to match shot to shot INSIDE a scene, so
             every scene carries its own reference regardless

Every rule here is a heuristic with a knob on it, and every variant records the
scenes it serves so the count can be audited against the script rather than
taken on trust.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .breakdown import Breakdown

# Weather that changes the plate. Read from the scene's action text.
WEATHER = {
    "rain": ["rain", "raining", "downpour", "drizzle", "storm", "pouring"],
    "snow": ["snow", "snowing", "blizzard", "sleet"],
    "fog": ["fog", "mist", "haze"],
    "wind": ["wind", "gale", "gusts"],
    "wet": ["wet concrete", "puddles", "soaked"],
}


@dataclass(frozen=True)
class Variant:
    kind: str                 # character | location | prop | wardrobe
    name: str
    variant: str              # what makes this one different ("NIGHT · rain")
    scenes: tuple

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.name}|{self.variant}"

    @property
    def label(self) -> str:
        return f"{self.name} — {self.variant}" if self.variant else self.name


@dataclass
class VariantPlan:
    variants: list = field(default_factory=list)

    def of(self, kind: str) -> list:
        return [v for v in self.variants if v.kind == kind]

    @property
    def images(self) -> int:
        """One image per variant - what actually has to be generated."""
        return len(self.variants)

    def counts(self) -> dict:
        return {kind: len(self.of(kind))
                for kind in ("character", "location", "prop", "wardrobe")}

    def recurring(self, kind: str) -> list:
        """Variants that carry across more than one scene - the continuity load."""
        return [v for v in self.of(kind) if len(v.scenes) > 1]

    def by_scene(self) -> dict:
        scenes = {}
        for variant in self.variants:
            for number in variant.scenes:
                scenes.setdefault(number, []).append(variant)
        return dict(sorted(scenes.items()))


def weather_in(text: str) -> str:
    lowered = text.lower()
    found = [name for name, words in WEATHER.items()
             if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in words)]
    return "+".join(sorted(found))


def build_variants(breakdown: Breakdown, character_looks: dict | None = None,
                   sheet_min_scenes: int = 2) -> VariantPlan:
    """Turn a breakdown into the actual list of images the show needs.

    character_looks: optional {"MARA": 3} to override the inferred look count.
    sheet_min_scenes: how many scenes a character has to appear in before a
        character sheet is worth building. Below it they ride on the scene's
        wardrobe plate. An explicit character_looks entry always wins.
    """
    character_looks = character_looks or {}
    variants: list = []

    # --- locations: one plate per look the script actually asks for ---------
    # Weather carries through a continuous block: the rain does not stop just
    # because the next slug line says CONTINUOUS, so a scene that mentions no
    # weather inherits whatever was falling when the block opened.
    from .script import CONTINUING_TIMES

    location_seen: dict = {}
    carried_weather = ""
    for scene_breakdown in breakdown.scenes:
        scene = scene_breakdown.scene
        stated = (scene.time_of_day or "").upper()
        opens_block = bool(stated) and stated not in CONTINUING_TIMES
        detected = weather_in(scene.action_text)
        carried_weather = detected if (opens_block or detected) else carried_weather
        if not scene.location:
            continue
        stamp = scene.effective_time or scene.time_of_day or "UNSPECIFIED"
        descriptor = " · ".join(x for x in (stamp, carried_weather) if x)
        location_seen.setdefault((scene.location, descriptor), []).append(scene.number)
    for (name, descriptor), scenes in location_seen.items():
        variants.append(Variant("location", name, descriptor, tuple(scenes)))

    # --- characters: a new look when the time of day turns over -------------
    appearances: dict = {}
    for scene_breakdown in breakdown.scenes:
        scene = scene_breakdown.scene
        for name in scene_breakdown.cast:
            appearances.setdefault(name, []).append(scene)

    for name, scenes in appearances.items():
        forced = character_looks.get(name)
        if not forced and len(scenes) < sheet_min_scenes:
            continue                      # a walk-on: the wardrobe plate covers them
        if forced:
            per_look = max(1, len(scenes) // forced)
            blocks = [scenes[i:i + per_look] for i in range(0, len(scenes), per_look)][:forced]
        else:
            blocks, current, last_time = [], [], None
            for scene in scenes:
                time_of_day = scene.effective_time or scene.time_of_day or "UNSPECIFIED"
                if current and time_of_day != last_time:
                    blocks.append(current)
                    current = []
                current.append(scene)
                last_time = time_of_day
            if current:
                blocks.append(current)
        for index, block in enumerate(blocks, start=1):
            times = []
            for scene in block:
                label = scene.effective_time or scene.time_of_day or "UNSPECIFIED"
                if label not in times:
                    times.append(label)
            descriptor = f"look {index} · {'/'.join(times)}" if len(blocks) > 1 else "/".join(times)
            variants.append(Variant("character", name, descriptor,
                                    tuple(scene.number for scene in block)))

    # --- props: one image each, wherever they recur -------------------------
    prop_scenes: dict = {}
    for scene_breakdown in breakdown.scenes:
        for prop in scene_breakdown.props:
            prop_scenes.setdefault(prop, []).append(scene_breakdown.scene.number)
    for name, scenes in prop_scenes.items():
        variants.append(Variant("prop", name, "", tuple(scenes)))

    # --- wardrobe: one continuity plate per scene ---------------------------
    # Character looks are per block; wardrobe has to match shot to shot inside a
    # scene, so every scene gets its own plate however many looks the cast has.
    for scene_breakdown in breakdown.scenes:
        scene = scene_breakdown.scene
        who = ", ".join(list(scene_breakdown.cast)[:3])
        variants.append(Variant(
            "wardrobe",
            f"Scene {scene.number} — {scene.location or 'wardrobe'}",
            who or (scene.effective_time or scene.time_of_day or ""),
            (scene.number,)))

    return VariantPlan(variants=variants)

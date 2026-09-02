"""
Screenplay parser - pure Python, no LLM calls.

Handles Fountain and standard screenplay text (.fountain / .txt / .md, and .fdx
via a light XML path). It leans on the conventions screenplays already follow,
which is why it needs no model:

  scene heading   INT./EXT. LOCATION - TIME       (or a Fountain forced '.HEADING')
  character cue   an ALL-CAPS line followed by dialogue
  transition      a line ending 'TO:' or one of the known ones
  props           screenwriters CAPITALISE a prop or effect on first appearance

Page count follows the industry standard of 55 lines to a page, reported in
eighths, because that is the unit ADs schedule in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

LINES_PER_PAGE = 55
EIGHTH = 1 / 8

HEADING_RE = re.compile(
    r"^(INT\.?/EXT\.?|EXT\.?/INT\.?|I/E\.?|INT\.?|EXT\.?|EST\.?)([\s.].*)$",
    re.IGNORECASE)
FORCED_HEADING_RE = re.compile(r"^\.(?!\.)(.+)$")
CUE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 '.\-]*(\([^)]*\))?\s*$")
TRANSITION_RE = re.compile(r"^([A-Z ]*TO:|FADE (IN|OUT)[.:]?|THE END|SMASH CUT\.?)\s*$")
CAPS_RUN_RE = re.compile(r"\b([A-Z][A-Z0-9'\-]{2,}(?:\s+[A-Z][A-Z0-9'\-]{2,})*)\b")

# Production drafts number their scenes in both margins and locked pages carry
# (CONTINUED) banners. Strip that furniture before classifying a line, or a
# numbered shooting script parses to zero scenes.
SCENE_NUMBER_LEAD = re.compile(r"^\s*[0-9]{1,4}[A-Za-z]?[.)]?\s+")
SCENE_NUMBER_TAIL = re.compile(r"\s+[0-9]{1,4}[A-Za-z]?\s*$")
PAGE_FURNITURE = re.compile(r"^\s*(\(?\s*continued\s*\)?[.:]?|\(more\)|[0-9]{1,3}[.)]?)\s*$",
                            re.IGNORECASE)


def strip_scene_numbers(line: str) -> str:
    out = line.strip()
    bare = SCENE_NUMBER_LEAD.sub("", out)
    if HEADING_RE.match(bare):
        out = bare
    trimmed = SCENE_NUMBER_TAIL.sub("", out)
    if HEADING_RE.match(trimmed):
        out = trimmed
    return out

# Headings that mean "the same time block as the scene before" rather than a
# time of their own. They inherit forward, which matters: a CONTINUOUS scene in
# the middle of a night sequence is a NIGHT scene for lighting, for wardrobe and
# for how many plates the location needs.
CONTINUING_TIMES = {"CONTINUOUS", "LATER", "MOMENTS LATER", "SAME", "SAME TIME"}

TIMES_OF_DAY = {
    "DAY", "NIGHT", "DUSK", "DAWN", "MORNING", "AFTERNOON", "EVENING", "MIDNIGHT",
    "CONTINUOUS", "LATER", "MOMENTS LATER", "SAME", "SAME TIME", "SUNSET", "SUNRISE",
    "MAGIC HOUR", "PRE-DAWN", "NIGHTFALL",
}

# Caps that appear in action lines but are never props.
NOT_PROPS = {
    "INT", "EXT", "EST", "CUT", "FADE", "DISSOLVE", "SMASH", "MATCH", "ANGLE", "ON",
    "CONTINUOUS", "LATER", "SAME", "DAY", "NIGHT", "DUSK", "DAWN", "MORNING",
    "EVENING", "AFTERNOON", "MIDNIGHT", "SUNSET", "SUNRISE", "THE", "END", "TITLE",
    "SUPER", "INSERT", "BACK", "SCENE", "FLASHBACK", "MONTAGE", "SERIES", "SHOTS",
    "POV", "OS", "VO", "CONT", "MORE", "BEAT", "PAUSE", "SILENCE", "OMITTED",
    "AND", "BUT", "FOR", "NOT", "YOU", "HIS", "HER", "THEY", "WITH", "FROM", "INTO",
    "OVER", "THAT", "THIS", "WHAT", "WHEN", "WHERE", "THEN", "NOW", "ALL", "ONE",
}

# Signals that a scene is expensive to generate, whatever its page count says.
VFX_KEYWORDS = {
    "explosion", "explodes", "fire", "flames", "burning", "smoke", "blood", "wound",
    "crash", "crashes", "collision", "stunt", "falls from", "gunfire", "gunshot",
    "muzzle", "rain", "storm", "lightning", "snow", "fog", "underwater", "drowning",
    "flood", "helicopter", "aircraft", "spaceship", "creature", "monster", "alien",
    "transforms", "morphs", "dissolves into", "vanishes", "levitates", "hologram",
    "cgi", "vfx", "green screen", "de-age", "de-aged", "prosthetic",
    "stunt double", "body double", "wire work", "squib", "pyro",
}
CROWD_KEYWORDS = {
    "crowd", "crowds", "mob", "audience", "commuters", "shoppers", "protesters",
    "soldiers", "army", "packed", "throng", "spectators", "bystanders", "passengers",
    "guests", "party", "rally", "stadium", "market", "traffic",
}
ANIMAL_KEYWORDS = {"dog", "dogs", "cat", "cats", "horse", "horses", "bird", "birds",
                   "snake", "wolf", "wolves", "bear"}


@dataclass
class Scene:
    number: int
    heading: str
    int_ext: str                      # INT / EXT / INT-EXT
    location: str
    time_of_day: str
    effective_time: str = ""          # resolved forward through CONTINUOUS / LATER
    action: list[str] = field(default_factory=list)
    dialogue: list[tuple[str, str]] = field(default_factory=list)   # (character, line)
    line_count: int = 0

    @property
    def is_night(self) -> bool:
        stamp = (self.effective_time or self.time_of_day).upper()
        return any(w in stamp for w in ("NIGHT", "DUSK", "DAWN", "MIDNIGHT"))

    @property
    def is_exterior(self) -> bool:
        return self.int_ext.startswith("EXT") or self.int_ext == "INT-EXT"

    @property
    def characters(self) -> list[str]:
        seen = []
        for name, _ in self.dialogue:
            if name not in seen:
                seen.append(name)
        return seen

    @property
    def action_text(self) -> str:
        return " ".join(self.action)

    @property
    def pages(self) -> float:
        return self.line_count / LINES_PER_PAGE

    @property
    def eighths(self) -> int:
        """Page eighths, the unit an AD schedules in. Never less than one."""
        return max(1, round(self.pages / EIGHTH))

    @property
    def screen_seconds(self) -> float:
        """One page ~ one minute of screen time."""
        return self.pages * 60


@dataclass
class Script:
    title: str
    scenes: list[Scene]
    source_lines: int

    @property
    def pages(self) -> float:
        return sum(s.pages for s in self.scenes)

    @property
    def runtime_minutes(self) -> float:
        return self.pages

    @property
    def characters(self) -> list[str]:
        seen = []
        for scene in self.scenes:
            for name in scene.characters:
                if name not in seen:
                    seen.append(name)
        return seen

    @property
    def locations(self) -> list[str]:
        seen = []
        for scene in self.scenes:
            if scene.location and scene.location not in seen:
                seen.append(scene.location)
        return seen


# ---------------------------------------------------------------------------
# Line classification
# ---------------------------------------------------------------------------

def is_heading(line: str) -> bool:
    stripped = strip_scene_numbers(line)
    if not stripped:
        return False
    if FORCED_HEADING_RE.match(stripped):
        return True
    return bool(HEADING_RE.match(stripped))


def is_furniture(line: str) -> bool:
    """Page numbers and (CONTINUED) banners, which are not script."""
    return bool(PAGE_FURNITURE.match(line.strip()))


def is_transition(line: str) -> bool:
    return bool(TRANSITION_RE.match(line.strip()))


def is_cue(line: str) -> bool:
    """An ALL-CAPS character cue - not a heading, not a transition, not a sentence."""
    stripped = line.strip()
    if not stripped or len(stripped) > 40:
        return False
    if is_heading(stripped) or is_transition(stripped):
        return False
    if stripped.startswith("("):
        return False
    if not CUE_RE.match(stripped):
        return False
    # Needs at least one letter, and must not read as an action sentence.
    core = re.sub(r"\([^)]*\)", "", stripped).strip()
    return bool(core) and any(c.isalpha() for c in core) and not core.endswith((".", "!", "?"))


def clean_cue(line: str) -> str:
    """'SARAH (V.O.)' -> 'SARAH'."""
    return re.sub(r"\([^)]*\)", "", line).strip().rstrip(":").strip()


def split_heading(line: str) -> tuple[str, str, str]:
    """'INT. HOSPITAL WAITING ROOM - NIGHT' -> ('INT', 'HOSPITAL WAITING ROOM', 'NIGHT')."""
    stripped = strip_scene_numbers(line)
    forced = FORCED_HEADING_RE.match(stripped)
    if forced:
        stripped = forced.group(1).strip()

    match = HEADING_RE.match(stripped)
    if match:
        prefix = match.group(1).upper().rstrip(".")
        rest = match.group(2).strip(" .-")
        int_ext = {"I/E": "INT-EXT", "INT/EXT": "INT-EXT", "EXT/INT": "INT-EXT"}.get(
            prefix.replace(".", ""), prefix.replace(".", ""))
    else:
        int_ext, rest = "INT", stripped

    location, time_of_day = rest, ""
    parts = re.split(r"\s+[-–—]+\s+", rest)
    if len(parts) > 1 and parts[-1].strip().upper() in TIMES_OF_DAY:
        time_of_day = parts[-1].strip().upper()
        location = " - ".join(p.strip() for p in parts[:-1])
    elif len(parts) > 1:
        # Unknown trailing segment: keep it on the location, guess the time is unstated.
        location = " - ".join(p.strip() for p in parts)
    return int_ext, location.strip().upper(), time_of_day


# ---------------------------------------------------------------------------
# The parse
# ---------------------------------------------------------------------------

def parse(text: str, title: str = "Untitled") -> Script:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    scenes: list[Scene] = []
    current: Scene | None = None
    pending_cue: str | None = None

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if is_heading(line):
            int_ext, location, time_of_day = split_heading(line)
            current = Scene(number=len(scenes) + 1,
                            heading=strip_scene_numbers(line).lstrip("."),
                            int_ext=int_ext, location=location, time_of_day=time_of_day)
            scenes.append(current)
            pending_cue = None
            current.line_count += 1
            continue

        if current is None:
            continue                                  # title page / front matter

        current.line_count += 1

        if not stripped:
            pending_cue = None
            continue
        if is_furniture(stripped):
            continue
        if is_transition(line):
            pending_cue = None
            continue

        if pending_cue is not None:
            if stripped.startswith("("):              # parenthetical, still dialogue
                continue
            current.dialogue.append((pending_cue, stripped))
            continue

        if is_cue(line):
            pending_cue = clean_cue(stripped)
            continue

        current.action.append(stripped)

    _resolve_times(scenes)
    return Script(title=title, scenes=scenes, source_lines=len(lines))


def _resolve_times(scenes: list[Scene]) -> None:
    """Carry a real time of day forward through CONTINUOUS / LATER headings."""
    carried = ""
    for scene in scenes:
        stated = (scene.time_of_day or "").upper()
        if stated and stated not in CONTINUING_TIMES:
            carried = stated
        scene.effective_time = carried or stated


def parse_file(path: str) -> Script:
    """Parse .fountain / .txt / .md, or .fdx (Final Draft XML)."""
    import os

    name = os.path.splitext(os.path.basename(path))[0]
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8", errors="ignore")
    if path.lower().endswith(".fdx"):
        text = _fdx_to_text(text)
    return parse(text, title=name)


def _fdx_to_text(xml_text: str) -> str:
    """Flatten Final Draft XML into screenplay text we can parse."""
    from xml.etree import ElementTree

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return xml_text

    out = []
    for paragraph in root.iter("Paragraph"):
        kind = paragraph.get("Type", "")
        body = "".join(t.text or "" for t in paragraph.iter("Text")).strip()
        if not body:
            out.append("")
            continue
        if kind in ("Scene Heading", "Character", "Transition"):
            body = body.upper()
        out.append(body)
        if kind in ("Scene Heading", "Action", "Dialogue", "Transition"):
            out.append("")
    return "\n".join(out)

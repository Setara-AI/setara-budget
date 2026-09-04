"""
Outline -> Script.

An outline is not a screenplay with the formatting stripped out; it is a
different document, and the difference is the whole reason this module exists.
It has no slug lines, so it has no pages, so `runtime.minutes_from_pages` - the
thing that normally sets the runtime - has nothing to work on. A runtime must
therefore be STATED for an outline, and `time_script(..., stated=...)` is where
it goes in.

What happens after that is unchanged. The stated runtime is the total, and the
plan shares it across the beats in proportion to how much is written about each,
exactly as it shares a screenplay's runtime across its scenes. A beat with a
paragraph under it is a longer sequence than a beat with a line. Same mechanism,
different document.

WHAT IS AND IS NOT KNOWN. This matters more here than anywhere else in the
engine, because an outline invites confident guessing:

  * beats            counted, not guessed - the outline marks them or paragraphs do
  * runtime          stated by the producer; nothing here infers it
  * locations        only where a beat actually labels one; never invented
  * characters       a HEURISTIC, and the one number here to distrust

Under-claiming is deliberate. A beat with no label contributes no location plate
rather than a made-up one, and the app says out loud when that happened. The
alternative - inventing a plate per beat - produces a number that looks measured
and is not.
"""

from __future__ import annotations

import re

from .script import CAPS_RUN_RE, LINES_PER_PAGE, Scene, Script

#: A beat is an explicitly marked item where the outline marks them - numbered,
#: lettered or bulleted - because an outline that marks its beats has already
#: told us where they are. Failing that, a paragraph.
BEAT_MARK_RE = re.compile(r"^\s*(?:\d{1,3}\s*[.)\]]\s|[-*•]\s|#{1,3}\s|[A-Z]\s*[.)]\s)")

#: A label is the place the beat happens in, set off by a dash or a colon:
#: "THE DINER - Mara refuses the job".
_LABEL_DASH_RE = re.compile(r"^([^.!?]{2,60}?)\s+[–—-]\s+")
_LABEL_COLON_RE = re.compile(r"^([^.!?]{2,60}?):\s+")

_TITLE_CASE_RE = re.compile(r"\b([A-Z][a-z]{2,})\b")

_NIGHT_RE = re.compile(r"\b(night|dusk|dawn|midnight|evening|nocturnal|after dark)\b",
                       re.IGNORECASE)

#: The floor that stops a screenplay whose PDF extraction collapsed into one
#: wall of text from being quietly accepted as an outline and priced off a
#: made-up runtime. Such a file yields exactly one "beat".
MIN_BEATS = 3

STOPWORDS = frozenset((
    "the a an and but or so then now later meanwhile "
    "he she it we they i you his her their its our my this that there here "
    "when while after before as at in on to of for with from by into out up "
    "one two three four five act scene beat sequence part chapter page "
    "int ext day night morning evening dawn dusk continuous flashback "
    "montage cut open close final end"
).split())


def split_beats(text: str) -> list[str]:
    """The outline's beats, in order.

    Marked items win where there are at least MIN_BEATS of them; otherwise
    paragraphs. Anything before the first marker is front matter - a title, a
    logline - and is dropped rather than folded into beat one.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n").split("\n")
    marked: list[list[str]] = []
    current: list[str] | None = None
    for raw in lines:
        line = raw.strip()
        if not line:
            current = None
            continue
        if BEAT_MARK_RE.match(raw):
            current = [BEAT_MARK_RE.sub("", raw).strip()]
            marked.append(current)
        elif current is not None:
            current.append(line)
    if len(marked) >= MIN_BEATS:
        joined = [re.sub(r"\s+", " ", " ".join(b)).strip() for b in marked]
        return [b for b in joined if b]

    paragraphs = re.split(r"\n\s*\n+", text.replace("\r\n", "\n").replace("\r", "\n"))
    return [p for p in (re.sub(r"\s+", " ", para.replace("\f", " ")).strip()
                        for para in paragraphs) if p]


def beat_label(text: str) -> str:
    """The place a beat opens in, or "" where it does not name one."""
    m = _LABEL_DASH_RE.match(text) or _LABEL_COLON_RE.match(text)
    if not m:
        return ""
    label = m.group(1).strip()
    return label if len(label.split()) <= 8 else ""


def outline_names(bodies: list[str], label_words: set[str]) -> list[str]:
    """Who the outline is about. A heuristic, and labelled as one wherever shown.

    A screenplay names its characters unambiguously - the cue line does it - and
    prose does not. Two rules, both learned from getting it wrong:

      * names come from the beat BODY, never the label. The label is where the
        location lives, so reading it too made "THE DINER" a character with its
        own look sheet.
      * a Capitalised word qualifies on appearing in two or more beats, full
        stop. An earlier version also required it to appear away from the start
        of a sentence, which sounds prudent and quietly deleted a lead: in an
        outline the protagonist is the subject of nearly every beat, and so
        starts nearly every sentence.

    Over-claiming is cheap - a character seen in only one beat gets no sheet
    downstream anyway - so the two-beat floor is the whole filter.
    """
    seen: dict[str, set[int]] = {}

    def note(name: str, index: int) -> None:
        key = name.upper()
        if key.lower() in STOPWORDS or key in label_words:
            return
        seen.setdefault(key, set()).add(index)

    for i, body in enumerate(bodies):
        for m in CAPS_RUN_RE.finditer(body):
            note(m.group(1).strip(), i)
        for m in _TITLE_CASE_RE.finditer(body):
            note(m.group(1), i)

    return [name for name, beats in seen.items() if len(beats) >= 2]


def title_from_outline(text: str) -> str:
    """The outline's title, if it has one.

    A title is a line that is NOT a beat, standing before the beats begin.
    Without that test an outline opening straight into "1. THE DINER - She
    waits" names the production after its first beat.
    """
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if BEAT_MARK_RE.match(raw):
            return ""            # beats started; there was no title
        if len(line) > 70:
            return ""            # that is prose, not a title
        return line
    return ""


def looks_like_outline(text: str) -> bool:
    """Whether this is worth reading as an outline at all."""
    return len(split_beats(text)) >= MIN_BEATS


def parse_outline(text: str, title: str = "") -> Script:
    """Read an outline into the same Script the screenplay parser produces.

    Nothing downstream needs to know which document it got - except that
    `script.pages` is 0, which is why a runtime has to be stated.
    """
    beats = split_beats(text)

    # Split label from body once, up front: everything below wants one or the
    # other and never both.
    parts = []
    for beat in beats:
        label = beat_label(beat)
        if label:
            body = beat[beat.index(label) + len(label):].lstrip(" –—:-")
        else:
            body = beat
        parts.append((beat, label, body or beat))

    # Every word of every label, so a location can never also be a character.
    label_words: set[str] = set()
    for _, label, _ in parts:
        if not label:
            continue
        label_words.add(label.upper())
        label_words.update(label.upper().split())

    names = outline_names([body for _, _, body in parts], label_words)

    scenes = []
    for i, (beat, label, body) in enumerate(parts, start=1):
        present = [n for n in names
                   if re.search(rf"\b{re.escape(n)}\b", body, re.IGNORECASE)]
        scenes.append(Scene(
            number=i,
            heading=label.upper() if label else f"BEAT {i}",
            int_ext="",
            location=label.upper() if label else "",
            time_of_day="NIGHT" if _NIGHT_RE.search(beat) else "",
            effective_time="NIGHT" if _NIGHT_RE.search(beat) else "",
            action=[body],
            dialogue=[],
            line_count=1,
            cast=present,
            # Zero, and it matters: pages are what the curve times, and an
            # outline has none. A missing runtime therefore reads as zero
            # rather than as a plausible number derived from prose length.
            page_share=0.0,
        ))

    return Script(title=title or title_from_outline(text) or "Untitled outline",
                  scenes=scenes,
                  source_lines=len(text.splitlines()))

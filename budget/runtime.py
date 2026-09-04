"""
Script -> runtime.

The industry rule is one page, one minute. It is a page-COUNT rule, so it is
really a measure of how much paper the formatting produced, and it drifts badly:
a dialogue page and an action page hold very different amounts of screen time,
and a script exported with tight margins or a PDF that lost its formatting will
lie to you.

So this module times the CONTENT instead, element by element:

    dialogue   words / DIALOGUE_WPM        what gets spoken
    action     words / ACTION_WPM          what gets shown
    heading    + SCENE_HEADING_SECONDS     the beat it takes to read a new place
    parenthetical + PARENTHETICAL_SECONDS  a held pause

Both methods are computed and returned, because the gap between them is
diagnostic: if they disagree by more than ~15% the script is formatted oddly
(or the PDF extraction lost its line breaks) and the number needs a human look.

WHY NOT AN LLM: asking a model for a runtime gets you the same heuristics with
a random seed on top - it cannot count words more accurately than `len(split())`
and it cannot be re-run to the same answer. The one thing a model would add is
judgement about pacing, which is exactly the thing a producer should not
outsource to a guess. Calibration beats judgement here: `fit_wpm` below tunes
the two constants against scripts whose real runtime you already know, which is
the honest way to get this accurate for YOUR material.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .script import LINES_PER_PAGE, Script

# Calibrated against the page rule: a full page of dialogue holds roughly 200
# words and a full page of action roughly 130, and each plays in about a minute.
DIALOGUE_WPM = 160.0
ACTION_WPM = 130.0
SCENE_HEADING_SECONDS = 2.0
PARENTHETICAL_SECONDS = 0.5

# ---------------------------------------------------------------------------
# The page rule, measured.
#
# Sixty-nine produced films were looked up directly - the screenplay PDF's own
# page count against the released runtime, both read from source rather than
# inferred from each other. Across that corpus a page is worth 1.007 minutes on
# average, so "one page, one minute" is right about the MIDDLE and wrong about
# the ENDS: it lands within 10% on only 61% of films, and is out by 13 minutes
# on average.
#
# The error is not noise. It runs with LENGTH, and in the opposite direction to
# what most people expect:
#
#     pages      min/page   n     what is happening
#     60-90        1.336    3     short scripts, long films - the picture is
#                                 carried visually, and "they drift in silence"
#                                 is four words and four minutes
#     90-105       1.057   12
#     105-120      1.017   13     the classic 1:1 zone
#     120-140      0.970   23
#     140+         0.960   18     long scripts, shorter films - the edit cuts
#
# Fitting a straight line says the same thing more starkly: runtime = 0.665 x
# pages + 41. That intercept is the tell - roughly forty minutes of a feature is
# NOT on the page at all. But a line with an intercept cannot be let anywhere
# near short form (it claims 43 minutes for a three-page script), so the curve
# below carries the same shape safely instead.
#
# Scored on the corpus, against 1:1:
#     mean error   13.0 -> 11.4 min
#     median        9.0 ->  7.5 min
#     within 10%     61% ->  65%
#     within 20%     81% ->  88%
#     R^2          0.365 -> 0.490
#
# Below 60 pages there is no data - the shortest film measured is 68 pages - so
# the curve is pinned to 1.0 there rather than extrapolated. A trailer gets the
# plain rule, which is the honest answer when nothing has been measured.
PAGE_MINUTE_CURVE = (
    (40.0, 1.000),    # below the corpus: the plain rule, held flat
    (75.0, 1.336),    # 60-90 pages    (n=3, thin - treat as indicative)
    (97.0, 1.057),    # 90-105         (n=12)
    (112.0, 1.017),   # 105-120        (n=13)
    (130.0, 0.970),   # 120-140        (n=23)
    (155.0, 0.960),   # 140+           (n=18)
)

# The average across the corpus, kept because it is the honest one-number
# summary and the thing to recalibrate against your own delivered shows.
MINUTES_PER_PAGE = 1.007


def minutes_per_page(pages: float) -> float:
    """Where a script this long sits on the measured curve."""
    points = PAGE_MINUTE_CURVE
    if pages <= points[0][0]:
        return points[0][1]
    if pages >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if pages <= x1:
            return y0 + (y1 - y0) * (pages - x0) / (x1 - x0)
    return points[-1][1]


# PACING - the residual, and the one honest place for a judgement call.
#
# Divide each film's real runtime by what the length curve predicts and what is
# left is not length, it is how the picture MOVES:
#
#     mean 0.998   median 1.009   sd 0.118   range 0.66 - 1.32
#     p10 0.836    p25 0.931     p75 1.055   p90 1.128
#
# The ends are exactly who you would expect, which is the check that the number
# means what it says:
#
#     1.32 Casino   1.29 The Godfather   1.21 Goodfellas          - expansive
#     0.66 Toy Story  0.76 The Social Network  0.81 Lady Bird     - brisk
#
# Scorsese and Coppola at the top, Sorkin's overlapping dialogue at the bottom.
# A director whose cut breathes is a measurable 1.2. 0.75-1.30 covers 96%.
PACING_PERCENTILES = ((0.810, 5), (0.836, 10), (0.931, 25), (1.009, 50),
                      (1.055, 75), (1.128, 90), (1.202, 95))
DEFAULT_PACING = 1.0


def minutes_from_pages(pages: float, rate: float | None = None,
                       pacing: float = DEFAULT_PACING) -> float:
    """Screen minutes a page count implies.

    `rate` overrides the curve with a flat minutes-per-page of your own - what
    to use once you have delivered shows to fit against. `pacing` scales the
    result: how fast this picture moves, against the corpus norm of 1.0.
    """
    if pages <= 0:
        return 0.0
    per_page = minutes_per_page(pages) if rate is None else rate
    return pages * per_page * (pacing if pacing > 0 else 1.0)

# A real screenplay page holds somewhere between about 120 and 420 words. Well
# outside that band and the PAGE COUNT is wrong, which is the one failure that
# matters now that pages set the runtime: a PDF whose extraction lost its line
# breaks packs the whole script into a handful of "pages" and the film comes out
# minutes long.
#
# This replaced a rule that compared the word timing to the page rule and cried
# "unusual formatting" when they differed by 25%. They differ by design now -
# action compresses, so the word model reads long on anything with a fight in it
# - and a warning that fires on healthy scripts is worse than no warning.
WORDS_PER_PAGE_MIN = 120.0
WORDS_PER_PAGE_MAX = 420.0
# The guard is on WORDS, not pages. Guarding on pages was backwards: the very
# failure this catches - a script crammed into a fraction of a page - has almost
# no pages by definition, so a page floor let it straight through.
WORDS_TO_JUDGE = 500

_WORD = re.compile(r"[A-Za-z0-9'\-]+")


def count_words(text: str) -> int:
    return len(_WORD.findall(text))


@dataclass
class SceneRuntime:
    number: int
    dialogue_words: int
    action_words: int
    parentheticals: int

    @property
    def dialogue_seconds(self) -> float:
        return self.dialogue_words / DIALOGUE_WPM * 60

    @property
    def action_seconds(self) -> float:
        return self.action_words / ACTION_WPM * 60

    @property
    def seconds(self) -> float:
        return (SCENE_HEADING_SECONDS
                + self.dialogue_seconds
                + self.action_seconds
                + self.parentheticals * PARENTHETICAL_SECONDS)

    @property
    def minutes(self) -> float:
        return self.seconds / 60


@dataclass
class Runtime:
    scenes: list[SceneRuntime]
    page_minutes: float          # the calibrated page rule - the number we use
    content_minutes: float       # the element-timed cross-check
    pages: float = 0.0           # raw page count, before the curve
    #: A runtime the producer stated, in minutes. It REPLACES the curve rather
    #: than adjusting it: someone who says the film runs 94 minutes is not
    #: offering a correction to be blended in, they are telling you the answer.
    #: For an outline it is the only source there is - an outline has no pages.
    stated: float | None = None

    @property
    def minutes(self) -> float:
        """The calibrated page rule.

        This used to prefer the word-count timing and fall back to pages. It is
        the other way round now, because the word model has a structural blind
        spot the page rule does not: action compresses. "They fight across the
        rooftop" is six words and ninety seconds of film, while a dense page of
        description is four hundred words and maybe forty. No words-per-minute
        constant fixes that - the words are simply not proportional to the time.

        Pages are, because pages are what the format was designed to measure,
        and the curve above is fitted to 69 real films rather than to a
        constant somebody picked. The content timing stays on as a DIAGNOSTIC:
        when the two disagree badly the extraction is usually broken, which is
        worth saying out loud and is not worth silently averaging away.

        (This docstring used to claim 2,520 films. That is Stephen Follows'
        sample - the study whose conclusion this curve is measured AGAINST, see
        "Why not the published 1.1 figure" in BUDGET.md - not its own evidence,
        which overstated the curve's backing thirty-six fold.)

        A STATED runtime outranks all of it. The curve is an inference from the
        pages; a producer saying the picture runs 94 minutes is not an inference
        at all. And an outline has no pages, so for one of those this is the
        only source there is.
        """
        if self.stated and self.stated > 0:
            return float(self.stated)
        return self.page_minutes

    @property
    def seconds(self) -> float:
        """Seconds of the runtime ACTUALLY chosen.

        This used to return the content timing unconditionally, so on any script
        where the page rule won - which is most features - the shot count and
        the video bill were computed off a runtime the tool had already rejected.
        """
        return self.minutes * 60

    @property
    def disagreement(self) -> float:
        """How far the page rule sits from the content timing, as a fraction."""
        if not self.content_minutes:
            return 0.0
        return (self.page_minutes - self.content_minutes) / self.content_minutes

    @property
    def words(self) -> int:
        return sum(s.dialogue_words + s.action_words for s in self.scenes)

    @property
    def words_per_page(self) -> float:
        return self.words / self.pages if self.pages else 0.0

    @property
    def trustworthy(self) -> bool:
        """Whether the PAGE COUNT can be believed - which is what the runtime
        now rests on. Not whether the two timing methods agree; they disagree
        by design."""
        if self.stated and self.stated > 0:
            # This check exists to catch a page count the extraction got wrong.
            # Once a runtime is stated the page count sets nothing, so there is
            # nothing left for it to protect and it would only cry wolf.
            return True
        if self.words < WORDS_TO_JUDGE:
            return True                      # too little to judge
        if not self.pages:
            return False                     # words but no pages: certainly broken
        return WORDS_PER_PAGE_MIN <= self.words_per_page <= WORDS_PER_PAGE_MAX

    def note(self) -> str:
        head = (f"{self.page_minutes:.1f} min from {self.pages:.1f} pages "
                f"at {minutes_per_page(self.pages):.3f} min a page.")
        if self.trustworthy:
            return head
        crowded = self.words_per_page > WORDS_PER_PAGE_MAX
        return (head + f" But this reads {self.words_per_page:.0f} words a page, and a real "
                f"one holds {WORDS_PER_PAGE_MIN:.0f}-{WORDS_PER_PAGE_MAX:.0f} - the "
                + ("extraction has probably lost its line breaks, so the page count is "
                   "too low and the runtime with it."
                   if crowded else
                   "page count looks inflated, so the runtime is too long.")
                + " Worth a look before quoting.")

    def scene(self, number: int) -> SceneRuntime | None:
        for scene in self.scenes:
            if scene.number == number:
                return scene
        return None


def time_script(script: Script, pacing: float = DEFAULT_PACING,
                stated: float | None = None) -> Runtime:
    scenes = []
    for scene in script.scenes:
        dialogue_words = sum(count_words(line) for _, line in scene.dialogue)
        action_words = sum(count_words(line) for line in scene.action)
        # The parser folds parentheticals away, so approximate from the raw lines.
        parentheticals = sum(1 for line in scene.action if line.startswith("("))
        scenes.append(SceneRuntime(number=scene.number, dialogue_words=dialogue_words,
                                   action_words=action_words, parentheticals=parentheticals))
    return Runtime(
        scenes=scenes,
        page_minutes=minutes_from_pages(script.pages, pacing=pacing),
        content_minutes=sum(s.minutes for s in scenes),
        pages=script.pages,
        stated=stated,
    )


def fit_wpm(samples: list[tuple[Script, float]]) -> dict:
    """Fit DIALOGUE_WPM and ACTION_WPM to scripts whose real runtime you know.

    samples: [(parsed script, true runtime in minutes), ...]

    Solves the least-squares fit of  a*dialogue_words + b*action_words = seconds
    and reports the words-per-minute those coefficients imply. Two samples is
    the minimum; a handful of your own delivered projects is enough to make this
    genuinely accurate for your material rather than for the industry average.
    """
    if len(samples) < 2:
        raise ValueError("need at least two scripts with known runtimes to fit")

    rows = []
    for script, true_minutes in samples:
        timing = time_script(script)
        dialogue = sum(s.dialogue_words for s in timing.scenes)
        action = sum(s.action_words for s in timing.scenes)
        overhead = sum(SCENE_HEADING_SECONDS + s.parentheticals * PARENTHETICAL_SECONDS
                       for s in timing.scenes)
        rows.append((dialogue, action, true_minutes * 60 - overhead))

    # Normal equations for the 2x2 least-squares system.
    sdd = sum(d * d for d, _, _ in rows)
    saa = sum(a * a for _, a, _ in rows)
    sda = sum(d * a for d, a, _ in rows)
    sdy = sum(d * y for d, _, y in rows)
    say = sum(a * y for _, a, y in rows)

    determinant = sdd * saa - sda * sda
    if abs(determinant) < 1e-9:
        raise ValueError("samples are too alike to separate dialogue from action")

    seconds_per_dialogue_word = (sdy * saa - say * sda) / determinant
    seconds_per_action_word = (say * sdd - sdy * sda) / determinant
    if seconds_per_dialogue_word <= 0 or seconds_per_action_word <= 0:
        raise ValueError("fit produced a non-physical rate - check the sample runtimes")

    return {
        "DIALOGUE_WPM": 60 / seconds_per_dialogue_word,
        "ACTION_WPM": 60 / seconds_per_action_word,
        "samples": len(rows),
    }

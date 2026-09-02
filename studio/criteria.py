"""
Criteria - the shared vocabulary of every checker in the studio.

Each tool used to carry its own near-identical list-of-dicts ("traits",
"dimensions", "aspects", "categories"), its own Pydantic schema and its own
copy of the same scoring maths. They are all the same shape, so they are all
one thing now:

  Criterion       one thing the checker judges (id, name, description, critical)
  Verdict         the ONE structured-output schema Gemini fills in
  score()         pure decision function: criticals + a pass ratio -> ok/not ok
  flags()         pure decision function for screeners (clearance): confidence
                  above a sensitivity threshold

`passed` on a result means "the criterion's condition holds". For a quality
checker that is good news (the trait is present); for a screener like Clearance
the condition is "this category appears in the image", so passed=True is
precisely what you want flagged. score() and flags() read the same verdict from
those two opposite directions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# What we ask about
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Criterion:
    """One judged item.

    id           stable key the model must echo back
    name         human label shown in the results table
    description  what the model should look at
    critical     if True this must pass for an overall "ok" verdict
    fix          how to describe this aspect to the IMAGE model when repairing
                 it (only the fixer tools need this)
    """

    id: str
    name: str
    description: str
    critical: bool = False
    fix: str = ""


def by_id(criteria: list[Criterion]) -> dict[str, Criterion]:
    return {c.id: c for c in criteria}


# ---------------------------------------------------------------------------
# What comes back (one schema for every checker)
# ---------------------------------------------------------------------------

class CriterionResult(BaseModel):
    criterion_id: str = Field(description="The criterion id, echoed EXACTLY as given.")
    criterion_name: str = Field(description="The human name of the criterion.")
    passed: bool = Field(description="True only if the criterion's condition clearly holds.")
    note: str = Field(description="One sentence citing what in the image(s) supports this.")
    confidence: int = Field(default=100,
                            description="0-100 confidence in THIS criterion's judgement.")


class Verdict(BaseModel):
    context: str = Field(default="",
                         description="One-sentence description of the reference / what is being "
                                     "judged against, when the prompt asks for it.")
    results: list[CriterionResult]
    confidence: int = Field(description="0-100 confidence in the overall judgement.")
    summary: str = Field(description="1-2 sentence overall conclusion.")

    def result_for(self, criterion_id: str) -> CriterionResult | None:
        for r in self.results:
            if r.criterion_id == criterion_id:
                return r
        return None


def passed(verdict: Verdict, criterion_id: str) -> bool:
    """True only when the model returned this criterion AND marked it passed."""
    r = verdict.result_for(criterion_id)
    return r is not None and r.passed


# ---------------------------------------------------------------------------
# The prompt (same skeleton for every checker)
# ---------------------------------------------------------------------------

def build_prompt(*, intro: list[str], criteria: list[Criterion], decision: str,
                 context: str = "", per_result_confidence: bool = False,
                 conservative: bool = True, closing: list[str] | None = None) -> str:
    """Assemble a checker prompt.

    intro                 the role / framing paragraphs, in the tool's own words
    decision              how to phrase the per-criterion judgement, e.g.
                          "the image clearly satisfies this trait"
    context               what to put in the `context` field ("" = don't ask)
    per_result_confidence ask for a 0-100 confidence on every criterion too
    conservative          add the "if unclear, mark it false" instruction
    """
    lines = list(intro) + [""]
    if context:
        lines += [f"First, briefly describe {context}", ""]

    ask = [f"For EACH criterion below, decide whether {decision} (passed true/false), give a "
           "one-sentence note citing what you see, and echo the criterion_id EXACTLY as given."]
    if per_result_confidence:
        ask.append("Also give a 0-100 confidence for each criterion.")
    if conservative:
        ask.append("Be conservative: if a criterion is unclear or only partly met, mark it false.")
    lines += [" ".join(ask), "", "Criteria:"]

    for c in criteria:
        lines.append(f'- criterion_id "{c.id}" ({c.name}): {c.description}')

    lines += [""] + list(closing or [])
    lines += [
        "Finally give an overall confidence (0-100) and a 1-2 sentence summary.",
        "Return ONLY the structured JSON described by the schema.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Decision logic (pure, testable - no API, no images)
# ---------------------------------------------------------------------------

@dataclass
class Score:
    """The outcome of grading a verdict against its criteria."""

    ok: bool
    passed: int
    total: int
    ratio: float
    critical_misses: list[str] = field(default_factory=list)   # human names
    failing: list[str] = field(default_factory=list)           # criterion ids

    @property
    def percent(self) -> int:
        return round(self.ratio * 100)

    def tally(self) -> str:
        return f"{self.passed}/{self.total}"


def score(criteria: list[Criterion], verdict: Verdict, threshold: float) -> Score:
    """Ok when EVERY critical criterion passes AND at least `threshold` of all pass."""
    hits = [c for c in criteria if passed(verdict, c.id)]
    total = len(criteria)
    ratio = len(hits) / total if total else 0.0
    misses = [c for c in criteria if not passed(verdict, c.id)]
    critical_misses = [c.name for c in misses if c.critical]
    return Score(
        ok=(not critical_misses) and ratio >= threshold,
        passed=len(hits),
        total=total,
        ratio=ratio,
        critical_misses=critical_misses,
        failing=[c.id for c in misses],
    )


@dataclass
class Flags:
    """The outcome of screening a verdict (Clearance): anything worth a human look."""

    needs_review: bool
    flagged: list[str]          # human names of counted categories
    counted: list[str]          # ids of counted categories
    count: int


def flags(criteria: list[Criterion], verdict: Verdict, min_confidence: int) -> Flags:
    """A category counts when the model marked it present AND is confident enough."""
    names = by_id(criteria)
    counted = [r for r in verdict.results
               if r.passed and r.confidence >= min_confidence and r.criterion_id in names]
    return Flags(
        needs_review=bool(counted),
        flagged=[names[r.criterion_id].name for r in counted],
        counted=[r.criterion_id for r in counted],
        count=len(counted),
    )

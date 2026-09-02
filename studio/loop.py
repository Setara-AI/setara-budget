"""
The agent loop, with loop hygiene built in.

check -> if it passes, stop -> otherwise regenerate -> re-check, up to N tries.

LOOP HYGIENE (the rule the Cinematic work established, now enforced here rather
than left to each tool):

  Every retry re-renders from the SAME base image - never from the previous
  attempt. Stacking generations on generations compounds artifacts and drifts
  the image away from the original; three stacked fixes leave you further from
  the source than one.

Two consequences fall out of that, and both are handled here:

  * Because a retry cannot inherit an earlier fix, the fixer must be told about
    every criterion that has failed SO FAR, not just the ones failing right now.
    `run_loop` accumulates that set and passes it to fix().
  * Because attempts are independent renders of the same base rather than a
    chain, the LAST attempt is not necessarily the best one. `run_loop` returns
    the best attempt (a passing one if any, else the highest-scoring), which is
    only sound because of the hygiene rule above.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .criteria import Score


@dataclass
class Attempt:
    label: str
    image: Any
    verdict: Any
    score: Score

    @property
    def ok(self) -> bool:
        return self.score.ok


@dataclass
class LoopResult:
    attempts: list[Attempt]
    best: Attempt
    used: int                                  # regenerations actually spent
    outstanding: list[str] = field(default_factory=list)   # criterion ids never fixed

    @property
    def ok(self) -> bool:
        return self.best.ok

    @property
    def image(self) -> Any:
        return self.best.image

    @property
    def verdict(self) -> Any:
        return self.best.verdict

    @property
    def score(self) -> Score:
        return self.best.score


def better(candidate: Attempt, incumbent: Attempt) -> bool:
    """Passing beats failing; then more criteria passed wins. Ties keep the incumbent
    (the earlier attempt), because fewer regenerations is strictly cheaper."""
    if candidate.ok != incumbent.ok:
        return candidate.ok
    return candidate.score.passed > incumbent.score.passed


def run_loop(base: Any, *, check: Callable[[Any], Any], grade: Callable[[Any], Score],
             fix: Callable[[Any, list[str]], Any], max_retries: int,
             phase: str = "Fix") -> LoopResult:
    """Run the loop on `base`.

    check(image)            -> verdict
    grade(verdict)          -> Score
    fix(base, failing_ids)  -> a new image, ALWAYS rendered from `base`

    Note the shape of fix(): it receives the base image, not the previous
    attempt. That signature is the hygiene rule made unforgettable.
    """
    verdict = check(base)
    first = Attempt(f"{phase}: original", base, verdict, grade(verdict))
    attempts = [first]
    best = first

    outstanding: list[str] = list(first.score.failing)
    used = 0
    while not best.ok and used < max_retries:
        used += 1
        image = fix(base, list(outstanding))
        verdict = check(image)
        attempt = Attempt(f"{phase}: fix {used}", image, verdict, grade(verdict))
        attempts.append(attempt)
        if better(attempt, best):
            best = attempt
        for cid in attempt.score.failing:      # accumulate: retries start from base again
            if cid not in outstanding:
                outstanding.append(cid)

    return LoopResult(attempts=attempts, best=best, used=used,
                      outstanding=list(best.score.failing))

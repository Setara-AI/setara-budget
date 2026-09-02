"""Fake verdicts and fake images, so every loop can be exercised without an API key."""

from __future__ import annotations

from studio.criteria import CriterionResult, Verdict


def verdict(criteria, passing, *, confidence=90, per_result_confidence=None,
            summary="fake", context="fake reference") -> Verdict:
    """A Verdict where exactly `passing` (ids) passed.

    per_result_confidence: {id: 0-100} for screeners that grade each result.
    """
    passing = set(passing)
    confidences = per_result_confidence or {}
    return Verdict(
        context=context,
        results=[CriterionResult(criterion_id=c.id, criterion_name=c.name,
                                 passed=c.id in passing,
                                 note=f"note for {c.id}",
                                 confidence=confidences.get(c.id, 100))
                 for c in criteria],
        confidence=confidence,
        summary=summary,
    )


def partial_verdict(criteria, passing, omit) -> Verdict:
    """Like verdict(), but the model 'forgot' to return the `omit` ids."""
    v = verdict(criteria, passing)
    v.results = [r for r in v.results if r.criterion_id not in set(omit)]
    return v


class FakeImage:
    """Stands in for a PIL image: identity is all the loops care about."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<{self.name}>"

    def __eq__(self, other):
        return isinstance(other, FakeImage) and other.name == self.name

    def __hash__(self):
        return hash(self.name)


class Scripted:
    """A checker whose verdicts are scripted per image name, with a call log."""

    def __init__(self, criteria, script, default=()):
        self.criteria = criteria
        self.script = script          # {image name: [passing ids]}
        self.default = default
        self.seen = []

    def __call__(self, image):
        self.seen.append(image)
        return verdict(self.criteria, self.script.get(getattr(image, "name", image), self.default))

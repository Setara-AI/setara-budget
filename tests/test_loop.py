"""The agent loop - above all, that loop hygiene actually holds."""

import unittest

from studio.criteria import Criterion
from studio.loop import better, run_loop
from tests.fakes import FakeImage, verdict

CRITERIA = [
    Criterion(id="a", name="Alpha", description="a", critical=True),
    Criterion(id="b", name="Beta", description="b"),
    Criterion(id="c", name="Gamma", description="c"),
]

THRESHOLD = 0.99


def grade(v):
    from studio.criteria import score

    return score(CRITERIA, v, THRESHOLD)


class Harness:
    """Scripted checker + fixer that records exactly what the loop handed it."""

    def __init__(self, script, default=("a", "b", "c")):
        self.script = script                 # image name -> passing ids
        self.default = default
        self.fix_calls = []                  # (base image, failing ids) per regeneration

    def check(self, image):
        return verdict(CRITERIA, self.script.get(image.name, self.default))

    def fix(self, base, failing):
        self.fix_calls.append((base, list(failing)))
        return FakeImage(f"fix{len(self.fix_calls)}")


class TestHygiene(unittest.TestCase):
    def test_every_retry_renders_from_the_same_base_never_the_last_attempt(self):
        original = FakeImage("original")
        h = Harness({"original": [], "fix1": ["a"], "fix2": ["a", "b"]}, default=[])
        run_loop(original, check=h.check, grade=grade, fix=h.fix, max_retries=3)

        self.assertEqual(len(h.fix_calls), 3)
        for base, _ in h.fix_calls:
            self.assertIs(base, original)     # <- the whole point: no stacking

    def test_failures_accumulate_across_retries(self):
        # Because a retry starts from the base again, an aspect fixed last round
        # is un-fixed this round - so the fixer must keep being told about it.
        original = FakeImage("original")
        h = Harness({"original": ["a"], "fix1": ["b"], "fix2": []}, default=[])
        run_loop(original, check=h.check, grade=grade, fix=h.fix, max_retries=3)

        self.assertEqual(h.fix_calls[0][1], ["b", "c"])            # missing after the first check
        self.assertEqual(h.fix_calls[1][1], ["b", "c", "a"])       # fix1 lost "a"
        self.assertEqual(sorted(h.fix_calls[2][1]), ["a", "b", "c"])


class TestOutcome(unittest.TestCase):
    def test_a_passing_original_never_regenerates(self):
        h = Harness({"original": ["a", "b", "c"]})
        res = run_loop(FakeImage("original"), check=h.check, grade=grade, fix=h.fix,
                       max_retries=3)
        self.assertTrue(res.ok)
        self.assertEqual(res.used, 0)
        self.assertEqual(h.fix_calls, [])
        self.assertEqual(res.image.name, "original")

    def test_it_stops_as_soon_as_an_attempt_passes(self):
        h = Harness({"original": [], "fix1": ["a", "b", "c"]}, default=[])
        res = run_loop(FakeImage("original"), check=h.check, grade=grade, fix=h.fix,
                       max_retries=3)
        self.assertTrue(res.ok)
        self.assertEqual(res.used, 1)
        self.assertEqual(res.image.name, "fix1")

    def test_it_keeps_the_best_attempt_not_the_last_one(self):
        # Only sound because attempts are independent renders of the same base.
        h = Harness({"original": [], "fix1": ["a", "b"], "fix2": ["c"]}, default=[])
        res = run_loop(FakeImage("original"), check=h.check, grade=grade, fix=h.fix,
                       max_retries=2)
        self.assertFalse(res.ok)
        self.assertEqual(res.image.name, "fix1")
        self.assertEqual(res.best.score.passed, 2)

    def test_it_gives_up_after_max_retries(self):
        h = Harness({}, default=[])
        res = run_loop(FakeImage("original"), check=h.check, grade=grade, fix=h.fix,
                       max_retries=2)
        self.assertFalse(res.ok)
        self.assertEqual(res.used, 2)
        self.assertEqual(len(res.attempts), 3)          # original + 2 fixes
        self.assertEqual(res.outstanding, ["a", "b", "c"])

    def test_zero_retries_is_a_check_only_run(self):
        h = Harness({}, default=[])
        res = run_loop(FakeImage("original"), check=h.check, grade=grade, fix=h.fix,
                       max_retries=0)
        self.assertEqual(h.fix_calls, [])
        self.assertEqual(len(res.attempts), 1)

    def test_attempt_labels_carry_the_phase(self):
        h = Harness({}, default=[])
        res = run_loop(FakeImage("original"), check=h.check, grade=grade, fix=h.fix,
                       max_retries=1, phase="Continuity")
        self.assertEqual([a.label for a in res.attempts],
                         ["Continuity: original", "Continuity: fix 1"])


class TestBetter(unittest.TestCase):
    def _attempt(self, ok, passed):
        from studio.criteria import Score
        from studio.loop import Attempt

        return Attempt("x", None, None, Score(ok=ok, passed=passed, total=3, ratio=passed / 3))

    def test_passing_beats_failing_even_with_fewer_criteria(self):
        self.assertTrue(better(self._attempt(True, 1), self._attempt(False, 3)))

    def test_ties_keep_the_incumbent_because_it_cost_fewer_regenerations(self):
        self.assertFalse(better(self._attempt(False, 2), self._attempt(False, 2)))


if __name__ == "__main__":
    unittest.main()

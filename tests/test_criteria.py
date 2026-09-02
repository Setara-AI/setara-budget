"""The shared scoring rules - the heart of every checker."""

import unittest

from studio.criteria import Criterion, Verdict, build_prompt, flags, passed, score
from tests.fakes import partial_verdict, verdict

CRITERIA = [
    Criterion(id="a", name="Alpha", description="alpha desc", critical=True),
    Criterion(id="b", name="Beta", description="beta desc", critical=True),
    Criterion(id="c", name="Gamma", description="gamma desc"),
    Criterion(id="d", name="Delta", description="delta desc"),
]


class TestScore(unittest.TestCase):
    def test_all_passing_is_ok(self):
        s = score(CRITERIA, verdict(CRITERIA, ["a", "b", "c", "d"]), 0.85)
        self.assertTrue(s.ok)
        self.assertEqual((s.passed, s.total, s.percent), (4, 4, 100))
        self.assertEqual(s.failing, [])

    def test_a_critical_miss_fails_even_at_high_ratio(self):
        s = score(CRITERIA, verdict(CRITERIA, ["b", "c", "d"]), 0.70)
        self.assertFalse(s.ok)                       # 3/4 = 0.75 clears the bar...
        self.assertEqual(s.critical_misses, ["Alpha"])   # ...but a must-pass missed
        self.assertEqual(s.failing, ["a"])

    def test_ratio_below_threshold_fails_with_criticals_intact(self):
        s = score(CRITERIA, verdict(CRITERIA, ["a", "b"]), 0.75)
        self.assertFalse(s.ok)
        self.assertEqual(s.critical_misses, [])
        self.assertEqual(s.failing, ["c", "d"])

    def test_threshold_boundary_is_inclusive(self):
        s = score(CRITERIA, verdict(CRITERIA, ["a", "b", "c"]), 0.75)
        self.assertTrue(s.ok)

    def test_missing_result_counts_as_a_fail_not_a_crash(self):
        v = partial_verdict(CRITERIA, ["a", "b", "c", "d"], omit=["b"])
        s = score(CRITERIA, v, 0.70)
        self.assertFalse(s.ok)
        self.assertEqual(s.critical_misses, ["Beta"])
        self.assertIn("b", s.failing)

    def test_extra_results_the_criteria_dont_ask_about_are_ignored(self):
        v = verdict(CRITERIA, ["a", "b", "c", "d"])
        v.results.append(v.results[0].model_copy(update={"criterion_id": "zz", "passed": False}))
        self.assertTrue(score(CRITERIA, v, 1.0).ok)

    def test_empty_criteria_do_not_divide_by_zero(self):
        s = score([], Verdict(results=[], confidence=0, summary=""), 0.5)
        self.assertEqual((s.ratio, s.total), (0.0, 0))
        self.assertFalse(s.ok)

    def test_failing_preserves_declared_order(self):
        s = score(CRITERIA, verdict(CRITERIA, ["c"]), 0.9)
        self.assertEqual(s.failing, ["a", "b", "d"])


class TestFlags(unittest.TestCase):
    def test_only_confident_flags_count(self):
        v = verdict(CRITERIA, ["a", "c"], per_result_confidence={"a": 80, "c": 20})
        f = flags(CRITERIA, v, 50)
        self.assertTrue(f.needs_review)
        self.assertEqual(f.flagged, ["Alpha"])
        self.assertEqual(f.count, 1)

    def test_sensitivity_boundary_is_inclusive(self):
        v = verdict(CRITERIA, ["a"], per_result_confidence={"a": 50})
        self.assertTrue(flags(CRITERIA, v, 50).needs_review)
        self.assertFalse(flags(CRITERIA, v, 51).needs_review)

    def test_nothing_flagged_needs_no_review(self):
        self.assertFalse(flags(CRITERIA, verdict(CRITERIA, []), 0).needs_review)

    def test_unknown_categories_are_ignored(self):
        v = verdict(CRITERIA, ["a"])
        v.results[0].criterion_id = "not-a-category"
        self.assertFalse(flags(CRITERIA, v, 0).needs_review)


class TestPrompt(unittest.TestCase):
    def test_every_criterion_id_and_name_reaches_the_prompt(self):
        p = build_prompt(intro=["You judge things."], criteria=CRITERIA,
                         decision="the thing holds")
        for c in CRITERIA:
            self.assertIn(f'criterion_id "{c.id}"', p)
            self.assertIn(c.name, p)
            self.assertIn(c.description, p)
        self.assertIn("the thing holds", p)
        self.assertIn("Return ONLY the structured JSON", p)

    def test_optional_clauses_are_opt_in(self):
        bare = build_prompt(intro=["x"], criteria=CRITERIA, decision="d")
        self.assertNotIn("confidence for each criterion", bare)
        self.assertNotIn("First, briefly describe", bare)

        rich = build_prompt(intro=["x"], criteria=CRITERIA, decision="d",
                            context="the reference.", per_result_confidence=True,
                            conservative=False, closing=["When in doubt, flag it."])
        self.assertIn("confidence for each criterion", rich)
        self.assertIn("First, briefly describe the reference.", rich)
        self.assertIn("When in doubt, flag it.", rich)
        self.assertNotIn("Be conservative", rich)


class TestPassedHelper(unittest.TestCase):
    def test_passed_is_false_for_absent_results(self):
        v = partial_verdict(CRITERIA, ["a"], omit=["a"])
        self.assertFalse(passed(v, "a"))


if __name__ == "__main__":
    unittest.main()

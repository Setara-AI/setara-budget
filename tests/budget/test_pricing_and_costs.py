"""Prices, the token formula, and the two traps: minimum takes and quoted drift."""

import unittest

from budget import costs, plan, pricing
from budget.breakdown import break_down
from budget.script import parse

SCRIPT = """
INT. ROOM - DAY

A woman sits.

ANNA
Hello.
"""


def small_plan(**kwargs):
    return plan.build_plan(break_down(parse(SCRIPT, "t")), plan.PlanConfig(**kwargs))


class TestTokenFormula(unittest.TestCase):
    def test_the_formula_reproduces_the_published_per_second_rates(self):
        # Seedance 2.0 quotes $0.682/s at 1080p and $0.3034/s at 720p.
        self.assertAlmostEqual(pricing.video("seedance-2.0-1080p").cost_per_second(),
                               0.682, places=2)
        self.assertAlmostEqual(pricing.video("seedance-2.0-720p").cost_per_second(),
                               0.3034, places=2)

    def test_cost_scales_with_pixels_not_with_the_model_name(self):
        seven_twenty = pricing.video("seedance-2.0-720p").cost_per_second()
        ten_eighty = pricing.video("seedance-2.0-1080p").cost_per_second()
        self.assertAlmostEqual(ten_eighty / seven_twenty, (1920 * 1080) / (1280 * 720), places=4)

    def test_the_1080p_two_five_tier_is_flagged_projected_and_says_why(self):
        model = pricing.video("seedance-2.5-1080p")
        self.assertFalse(model.verified)
        self.assertIn("PROJECTED", model.note)
        self.assertIsNone(model.quoted_per_second)

    def test_published_tiers_are_marked_verified(self):
        for model_id in ("seedance-2.5-720p", "seedance-2.0-1080p", "seedance-2.5-480p"):
            self.assertTrue(pricing.video(model_id).verified, model_id)

    def test_drift_is_measured_not_assumed(self):
        drift = pricing.video("seedance-2.5-720p").drift()
        self.assertGreater(drift, 0)
        self.assertLess(drift, 0.05)
        self.assertEqual(pricing.video("seedance-2.5-1080p").drift(), 0.0)

    def test_an_unknown_model_names_the_ones_that_exist(self):
        with self.assertRaises(KeyError) as caught:
            pricing.video("seedance-9000")
        self.assertIn("seedance-2.5-720p", str(caught.exception))

    def test_nano_banana_pro_matches_googles_per_image_price(self):
        self.assertEqual(pricing.image("nano-banana-pro-2k").cost_per_image, 0.134)
        self.assertEqual(pricing.image("nano-banana-pro-4k").cost_per_image, 0.24)


class TestMinimumTake(unittest.TestCase):
    def test_a_short_shot_still_bills_the_models_minimum(self):
        # 2s shots on a model with a 4s floor bill as 4s - the classic overspend.
        tiny = small_plan()
        for scene in tiny.scenes:
            scene.seconds_per_shot = 2
        model = pricing.video("seedance-2.0-1080p")
        billed = costs.billable_seconds(tiny, model)
        expected = 4 * sum(s.shots * s.attempts_per_shot for s in tiny.scenes)
        self.assertAlmostEqual(billed, expected)

    def test_a_long_shot_is_capped_at_what_the_model_can_produce(self):
        long_plan = small_plan()
        for scene in long_plan.scenes:
            scene.seconds_per_shot = 40
        billed = costs.billable_seconds(long_plan, pricing.video("seedance-2.0-1080p"))
        shots = sum(s.shots * s.attempts_per_shot for s in long_plan.scenes)
        self.assertAlmostEqual(billed, 15 * shots)      # 2.0 tops out at 15s


class TestCostLines(unittest.TestCase):
    def setUp(self):
        self.plan = small_plan()

    def test_every_line_multiplies_out(self):
        result = costs.compute(self.plan)
        for line in result.lines:
            self.assertAlmostEqual(line.total, line.quantity * line.unit_cost)
        self.assertAlmostEqual(result.subtotal, sum(l.total for l in result.lines))

    def test_a_projected_tier_marks_the_whole_estimate_as_projected(self):
        self.assertTrue(costs.compute(self.plan, "seedance-2.5-1080p").uses_projected_pricing)

    def test_the_drift_line_appears_only_where_the_provider_quotes_above_its_own_formula(self):
        self.assertIsNotNone(costs.compute(self.plan, "seedance-2.5-720p").line("Provider price drift"))
        self.assertIsNone(costs.compute(self.plan, "seedance-2.5-1080p").line("Provider price drift"))

    def test_more_options_per_asset_costs_strictly_more(self):
        five = costs.compute(small_plan(options_per_asset=5)).subtotal
        ten = costs.compute(small_plan(options_per_asset=10)).subtotal
        self.assertGreater(ten, five)

    def test_the_comparison_covers_every_tier_and_sorts_by_price(self):
        rows = costs.model_comparison(self.plan)
        self.assertEqual(len(rows), len(pricing.VIDEO_MODELS))
        self.assertEqual([r["subtotal"] for r in rows], sorted(r["subtotal"] for r in rows))


if __name__ == "__main__":
    unittest.main()

"""Reading the screenplay, and turning what it says into work."""

import unittest

from budget import breakdown, labor, plan, script
from budget.breakdown import Tier

SAMPLE = """
INT. WAREHOUSE - NIGHT

Rain on the skylight. VIC, 30s, pries open a CRATE with a CROWBAR.

VIC
Nothing.

DANA (V.O.)
Keep looking.

Vic drags the crate aside. A CROWD of rats scatters.

CUT TO:

EXT. DOCKS - DAY

Gulls. Dana waits by a shipping CONTAINER.

DANA
You're late.
"""


class TestParsing(unittest.TestCase):
    def setUp(self):
        self.script = script.parse(SAMPLE, "Sample")

    def test_it_finds_the_scenes_and_reads_their_headings(self):
        self.assertEqual(len(self.script.scenes), 2)
        first, second = self.script.scenes
        self.assertEqual((first.int_ext, first.location, first.time_of_day),
                         ("INT", "WAREHOUSE", "NIGHT"))
        self.assertEqual((second.int_ext, second.location, second.time_of_day),
                         ("EXT", "DOCKS", "DAY"))

    def test_voice_over_and_contd_collapse_to_the_character(self):
        self.assertEqual(self.script.characters, ["VIC", "DANA"])

    def test_transitions_are_not_mistaken_for_characters(self):
        self.assertNotIn("CUT TO:", self.script.characters)

    def test_dialogue_is_attributed_to_the_right_speaker(self):
        lines = dict(self.script.scenes[0].dialogue)
        self.assertEqual(lines["VIC"], "Nothing.")
        self.assertEqual(lines["DANA"], "Keep looking.")

    def test_night_and_exterior_are_derived_from_the_heading(self):
        self.assertTrue(self.script.scenes[0].is_night)
        self.assertFalse(self.script.scenes[0].is_exterior)
        self.assertTrue(self.script.scenes[1].is_exterior)
        self.assertFalse(self.script.scenes[1].is_night)

    def test_dawn_counts_as_a_low_light_window(self):
        dawn = script.parse("EXT. ROOF - DAWN\n\nLight.\n").scenes[0]
        self.assertTrue(dawn.is_night)

    def test_pages_are_counted_in_eighths_and_never_round_to_zero(self):
        for scene in self.script.scenes:
            self.assertGreaterEqual(scene.eighths, 1)
        self.assertAlmostEqual(self.script.pages,
                               sum(s.pages for s in self.script.scenes))

    def test_a_forced_fountain_heading_is_honoured(self):
        parsed = script.parse(".BLACK VOID - LATER\n\nNothing at all.\n")
        self.assertEqual(len(parsed.scenes), 1)
        self.assertEqual(parsed.scenes[0].time_of_day, "LATER")

    def test_int_slash_ext_is_normalised(self):
        parsed = script.parse("I/E. CAR - NIGHT\n\nDriving.\n")
        self.assertEqual(parsed.scenes[0].int_ext, "INT-EXT")
        self.assertTrue(parsed.scenes[0].is_exterior)

    def test_front_matter_before_the_first_heading_is_ignored(self):
        parsed = script.parse("Title: Thing\nAuthor: Someone\n\n" + SAMPLE, "t")
        self.assertEqual(len(parsed.scenes), 2)

    def test_an_empty_script_parses_to_nothing_rather_than_crashing(self):
        parsed = script.parse("", "empty")
        self.assertEqual(parsed.scenes, [])
        self.assertEqual(parsed.pages, 0)


class TestBreakdown(unittest.TestCase):
    def setUp(self):
        self.breakdown = breakdown.break_down(script.parse(SAMPLE, "Sample"))

    def test_capitalised_props_are_picked_up(self):
        self.assertIn("CRATE", self.breakdown.props)
        self.assertIn("CROWBAR", self.breakdown.props)
        self.assertIn("CONTAINER", self.breakdown.props)

    def test_character_names_never_become_props(self):
        for name in ("VIC", "DANA"):
            self.assertNotIn(name, self.breakdown.props)

    def test_a_crowd_is_background_not_a_prop(self):
        self.assertNotIn("CROWD", self.breakdown.props)
        self.assertTrue(self.breakdown.scenes[0].crowd)

    def test_effects_words_are_effects_not_props(self):
        blood = breakdown.break_down(script.parse(
            "INT. BAY - NIGHT\n\nBLOOD on the floor. A MONITOR flatlines.\n"))
        self.assertIn("MONITOR", blood.props)
        self.assertNotIn("BLOOD", blood.props)
        self.assertIn("blood", blood.scenes[0].effects)

    def test_a_quiet_two_hander_scores_lower_than_a_night_crowd_scene(self):
        quiet = breakdown.break_down(script.parse(
            "INT. KITCHEN - DAY\n\nThey talk.\n\nANNA\nHi.\n\nBEN\nHi.\n"))
        self.assertEqual(quiet.scenes[0].complexity.tier, Tier.SIMPLE)
        self.assertGreater(self.breakdown.scenes[0].complexity.score,
                           quiet.scenes[0].complexity.score)

    def test_every_point_awarded_is_explained(self):
        for scene in self.breakdown.scenes:
            self.assertTrue(scene.complexity.drivers)
            awarded = sum(int(d.split()[0]) for d in scene.complexity.drivers)
            self.assertEqual(awarded, scene.complexity.score)

    def test_tier_counts_add_up_to_the_scene_count(self):
        self.assertEqual(sum(self.breakdown.by_tier().values()), len(self.breakdown.scenes))


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.breakdown = breakdown.break_down(script.parse(SAMPLE, "Sample"))

    def test_the_revision_formula_is_the_one_the_report_prints(self):
        self.assertAlmostEqual(plan.attempts_for(3, 0.6), 1 + 3 * 0.6)
        self.assertEqual(plan.attempts_for(0, 0.6), 1)

    def test_billed_seconds_exceed_delivered_seconds_by_the_attempts(self):
        built = plan.build_plan(self.breakdown)
        self.assertGreater(built.generated_seconds, built.final_seconds)

    def test_no_revisions_means_you_pay_for_exactly_what_you_deliver(self):
        config = plan.PlanConfig(hit_rate=0.0)
        built = plan.build_plan(self.breakdown, config)
        self.assertAlmostEqual(built.generated_seconds, built.final_seconds)

    def test_every_scene_gets_at_least_one_shot(self):
        built = plan.build_plan(self.breakdown)
        self.assertTrue(all(s.shots >= 1 for s in built.scenes))

    def test_the_reference_library_counts_what_the_script_contains(self):
        built = plan.build_plan(self.breakdown, plan.PlanConfig(
            options_per_asset=5, angles_per_character=3,
            plates_per_location=2, plates_per_prop=1, asset_revision_rounds=0))
        expected = 5 * (len(self.breakdown.characters) * 3
                        + len(self.breakdown.locations) * 2
                        + len(self.breakdown.props) * 1)
        self.assertAlmostEqual(built.assets.base_images, expected)
        self.assertAlmostEqual(built.assets.images, expected)   # no revision rounds


class TestLabor(unittest.TestCase):
    def setUp(self):
        self.plan = plan.build_plan(breakdown.break_down(script.parse(SAMPLE, "Sample")))
        self.work = labor.volume(self.plan)

    def test_a_tighter_deadline_needs_more_people(self):
        slow = labor.staff_for(12, self.work)
        fast = labor.staff_for(1, self.work)
        self.assertGreaterEqual(fast.headcount, slow.headcount)

    def test_a_bigger_team_finishes_sooner(self):
        # Sized past the one-week floor, which a two-scene sample never reaches.
        heavy = labor.WorkVolume(shots=400, shot_attempts=1200, images=6000,
                                 scenes=120, pages=100)
        small = labor.schedule_for({"gen_artist": 1, "asset_artist": 1}, heavy)
        large = labor.schedule_for({"gen_artist": 4, "asset_artist": 4}, heavy)
        self.assertLess(large.weeks, small.weeks)
        self.assertAlmostEqual(large.weeks * 4, small.weeks, places=1)

    def test_the_schedule_never_drops_below_a_week(self):
        trivial = labor.WorkVolume(shots=1, shot_attempts=1, images=1,
                                   scenes=1, pages=0.2)
        self.assertEqual(labor.schedule_for({"gen_artist": 50}, trivial).weeks, 1.0)

    def test_the_schedule_names_its_bottleneck(self):
        staffing = labor.schedule_for({"gen_artist": 1, "asset_artist": 1}, self.work)
        self.assertTrue(staffing.driver)
        loads = labor.bottlenecks(staffing)
        self.assertTrue(all(row["capacity"] >= row["required"] - 1e-6 for row in loads))

    def test_fixed_roles_are_carried_for_the_whole_run_not_scaled_by_volume(self):
        staffing = labor.staff_for(6, self.work)
        supervisor = staffing.seat("ai_supervisor")
        self.assertEqual(supervisor.count, 1)
        self.assertEqual(supervisor.weeks, 6)

    def test_cost_is_headcount_times_rate_times_weeks(self):
        staffing = labor.staff_for(4, self.work)
        for seat in staffing.seats:
            self.assertAlmostEqual(seat.cost, seat.count * seat.role.weekly_rate * 4)

    def test_a_non_positive_deadline_is_refused(self):
        with self.assertRaises(ValueError):
            labor.staff_for(0, self.work)


if __name__ == "__main__":
    unittest.main()


class TestProductionDrafts(unittest.TestCase):
    """A numbered shooting script is the normal case, not the exception."""

    NUMBERED = """
1       INT. HOSPITAL - WAITING ROOM - NIGHT                    1

        Rain hammers the window. MARA waits with a CUP.

                        MARA
                Is she going to die?

                                                        (CONTINUED)
        2.

2       EXT. LOADING BAY - NIGHT                                2

        An AMBULANCE idles.

                        YUSUF
                Talk to me.
"""

    def test_scene_numbers_in_the_margins_do_not_hide_the_heading(self):
        parsed = script.parse(self.NUMBERED, "numbered")
        self.assertEqual(len(parsed.scenes), 2)
        self.assertEqual(parsed.scenes[0].location, "HOSPITAL - WAITING ROOM")
        self.assertEqual(parsed.scenes[1].int_ext, "EXT")

    def test_the_heading_is_stored_without_its_numbers(self):
        parsed = script.parse(self.NUMBERED, "numbered")
        self.assertFalse(parsed.scenes[0].heading.startswith("1"))
        self.assertTrue(parsed.scenes[0].heading.startswith("INT."))

    def test_continued_banners_and_page_numbers_are_not_action(self):
        parsed = script.parse(self.NUMBERED, "numbered")
        joined = " ".join(parsed.scenes[0].action)
        self.assertNotIn("CONTINUED", joined)
        self.assertNotIn("2.", joined)

    def test_dialogue_still_lands_on_the_right_character(self):
        parsed = script.parse(self.NUMBERED, "numbered")
        self.assertEqual(parsed.characters, ["MARA", "YUSUF"])

    def test_a_number_that_is_not_a_scene_heading_is_left_alone(self):
        parsed = script.parse("INT. ROOM - DAY\n\n12 men enter the room.\n")
        self.assertIn("12 men enter the room.", parsed.scenes[0].action)

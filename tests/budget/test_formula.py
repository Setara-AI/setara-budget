"""Runtime timing, image variants, and the formula that hangs off them."""

import math
import unittest

from budget import formula, pricing, runtime, variants
from budget.breakdown import break_down
from budget.script import parse

NIGHT = """
INT. BAR - NIGHT

Rain against the glass. SAM wipes down the counter.

SAM
We're closed.

INT. BAR - CONTINUOUS

Sam locks the door.

EXT. STREET - DAY

Sam walks. The sun is out.

SAM
Not today.
"""


def timed(text=NIGHT):
    return runtime.time_script(parse(text, "t"))


def planned(text=NIGHT, **kwargs):
    return formula.build(break_down(parse(text, "t")), formula.Assumptions(**kwargs))


class TestRuntime(unittest.TestCase):
    def test_dialogue_is_timed_at_the_speaking_rate(self):
        one_line = timed("INT. ROOM - DAY\n\nANNA\n" + " ".join(["word"] * 160) + "\n")
        # 160 words at 160 wpm is a minute, plus the heading beat.
        self.assertAlmostEqual(one_line.scenes[0].dialogue_seconds, 60, places=1)

    def test_action_is_timed_more_slowly_than_dialogue(self):
        words = " ".join(["word"] * 130)
        action = timed(f"INT. ROOM - DAY\n\n{words}\n")
        self.assertAlmostEqual(action.scenes[0].action_seconds, 60, places=1)
        self.assertGreater(runtime.DIALOGUE_WPM, runtime.ACTION_WPM)

    def test_both_methods_are_reported_so_they_can_disagree(self):
        result = timed()
        self.assertGreater(result.page_minutes, 0)
        self.assertGreater(result.content_minutes, 0)
        # The calibrated page rule is the answer; words are the cross-check.
        self.assertEqual(result.minutes, result.page_minutes)

    # --- the page rule, fitted to 69 produced films ------------------------

    def test_a_page_is_about_a_minute_in_the_middle(self):
        """The corpus mean is 1.007 min/page, and the 105-120 band is the
        classic 1:1 zone - so the rule is right about the middle."""
        self.assertAlmostEqual(runtime.minutes_per_page(112), 1.017, places=3)
        self.assertAlmostEqual(runtime.minutes_from_pages(112), 114, delta=2)

    def test_short_scripts_make_longer_films(self):
        """The finding that matters: 60-90 page scripts run 1.34 min a page,
        because what carries those films is not on the page."""
        self.assertGreater(runtime.minutes_per_page(75), 1.3)
        self.assertGreater(runtime.minutes_from_pages(75), 95)

    def test_long_scripts_make_shorter_films(self):
        self.assertLess(runtime.minutes_per_page(155), 1.0)
        self.assertLess(runtime.minutes_from_pages(165), 165)

    def test_the_curve_runs_downhill_across_the_measured_range(self):
        rates = [runtime.minutes_per_page(p) for p in range(75, 160, 5)]
        self.assertEqual(rates, sorted(rates, reverse=True))

    def test_short_form_is_pinned_to_the_plain_rule(self):
        """The shortest film measured is 68 pages. Below that nothing has been
        measured, so a trailer gets 1:1 rather than an extrapolation."""
        for pages in (1, 5, 12, 30, 40):
            self.assertAlmostEqual(runtime.minutes_from_pages(pages), pages)

    def test_the_curve_is_continuous(self):
        """A 109-page script and a 110-page one must not disagree by minutes."""
        for pages in range(1, 220):
            step = abs(runtime.minutes_from_pages(pages + 1)
                       - runtime.minutes_from_pages(pages))
            self.assertLess(step, 2.5, f"jump at {pages} pages")

    def test_the_rate_can_be_overridden_with_your_own(self):
        """Once you have delivered shows to fit, a flat rate beats our curve."""
        self.assertAlmostEqual(runtime.minutes_from_pages(100, 0.9), 90)

    def test_no_pages_is_no_runtime(self):
        self.assertEqual(runtime.minutes_from_pages(0), 0)
        self.assertEqual(runtime.minutes_from_pages(-3), 0)

    def test_it_beats_one_to_one_on_the_corpus_it_was_fitted_to(self):
        """Guards the whole point of the curve. Six films spanning the range,
        page count and runtime both read from source."""
        corpus = [(68, 91), (75, 102), (81, 106), (105, 106), (126, 123), (164, 120)]
        curve = sum(abs(runtime.minutes_from_pages(p) - r) for p, r in corpus)
        flat = sum(abs(p - r) for p, r in corpus)
        self.assertLess(curve, flat)

    def test_pages_are_kept_alongside_the_minutes_they_produced(self):
        result = timed()
        self.assertGreater(result.pages, 0)
        self.assertIn("min a page", result.note())

    def test_pacing_scales_the_runtime_and_nothing_else(self):
        base = runtime.minutes_from_pages(120)
        self.assertAlmostEqual(runtime.minutes_from_pages(120, pacing=1.2), base * 1.2)
        self.assertAlmostEqual(runtime.minutes_from_pages(120, pacing=0.8), base * 0.8)

    def test_pacing_defaults_to_the_corpus_norm(self):
        self.assertAlmostEqual(runtime.DEFAULT_PACING, 1.0)
        self.assertAlmostEqual(runtime.minutes_from_pages(120),
                               runtime.minutes_from_pages(120, pacing=1.0))

    def test_a_nonsense_pacing_is_ignored_rather_than_zeroing_the_film(self):
        base = runtime.minutes_from_pages(120)
        self.assertAlmostEqual(runtime.minutes_from_pages(120, pacing=0), base)
        self.assertAlmostEqual(runtime.minutes_from_pages(120, pacing=-2), base)

    def test_the_pacing_band_covers_almost_every_film_measured(self):
        """0.75-1.30 spans p5 to p95 of the measured residual."""
        lo = runtime.PACING_PERCENTILES[0][0]
        hi = runtime.PACING_PERCENTILES[-1][0]
        self.assertLess(0.75, lo)
        self.assertGreater(1.30, hi)

    def test_a_page_count_that_cannot_be_believed_is_flagged(self):
        """The failure that matters now: extraction lost the line breaks, so the
        script is crammed into too few pages and the runtime collapses."""
        crammed = timed("INT. ROOM - DAY\n" + " ".join(["word"] * 4000))
        self.assertGreater(crammed.words_per_page, runtime.WORDS_PER_PAGE_MAX)
        self.assertFalse(crammed.trustworthy)
        self.assertIn("lost its line breaks", crammed.note())

    def test_an_ordinary_script_is_not_flagged_for_the_two_methods_differing(self):
        """They differ by design - action compresses - so a warning keyed to
        that fired on healthy scripts and blamed the extraction."""
        ordinary = timed()
        self.assertTrue(ordinary.trustworthy)
        self.assertNotIn("Worth a look", ordinary.note())

    def test_an_empty_script_times_to_nothing(self):
        self.assertEqual(timed("").minutes, 0)

    def test_fitting_recovers_the_rates_it_was_given(self):
        long_dialogue = parse("INT. A - DAY\n\nX\n" + " ".join(["w"] * 300) + "\n")
        long_action = parse("INT. B - DAY\n\n" + " ".join(["w"] * 300) + "\n")
        truth = []
        for script in (long_dialogue, long_action):
            timing = runtime.time_script(script)
            truth.append((script, timing.content_minutes))
        fitted = runtime.fit_wpm(truth)
        self.assertAlmostEqual(fitted["DIALOGUE_WPM"], runtime.DIALOGUE_WPM, places=0)
        self.assertAlmostEqual(fitted["ACTION_WPM"], runtime.ACTION_WPM, places=0)

    def test_one_sample_is_not_enough_to_fit(self):
        with self.assertRaises(ValueError):
            runtime.fit_wpm([(parse(NIGHT), 2.0)])


class TestTimeResolution(unittest.TestCase):
    def test_continuous_inherits_the_time_before_it(self):
        scenes = parse(NIGHT).scenes
        self.assertEqual(scenes[0].effective_time, "NIGHT")
        self.assertEqual(scenes[1].time_of_day, "CONTINUOUS")
        self.assertEqual(scenes[1].effective_time, "NIGHT")
        self.assertTrue(scenes[1].is_night)

    def test_a_stated_time_overrides_what_was_carried(self):
        self.assertEqual(parse(NIGHT).scenes[2].effective_time, "DAY")
        self.assertFalse(parse(NIGHT).scenes[2].is_night)


class TestVariants(unittest.TestCase):
    def setUp(self):
        self.plan = variants.build_variants(break_down(parse(NIGHT, "t")))

    def test_a_location_at_two_times_of_day_is_two_images(self):
        bar = [v for v in self.plan.of("location") if v.name == "BAR"]
        self.assertEqual(len(bar), 1, "both BAR scenes are the same night")
        self.assertIn("NIGHT", bar[0].variant)

    def test_weather_makes_a_separate_plate(self):
        bar = [v for v in self.plan.of("location") if v.name == "BAR"][0]
        self.assertIn("rain", bar.variant)

    def test_only_recurring_characters_get_a_sheet(self):
        counted = {}
        for sb in break_down(parse(NIGHT, "t")).scenes:
            for name in sb.cast:
                counted[name] = counted.get(name, 0) + 1
        walk_ons = {n for n, c in counted.items() if c < 2}
        sheeted = {v.name for v in self.plan.of("character")}
        self.assertFalse(sheeted & walk_ons, "a one-scene walk-on needs no sheet")

    def test_a_walk_on_can_still_be_forced_to_have_a_sheet(self):
        counted = {}
        for sb in break_down(parse(NIGHT, "t")).scenes:
            for name in sb.cast:
                counted[name] = counted.get(name, 0) + 1
        walk_ons = [n for n, c in counted.items() if c < 2]
        if not walk_ons:
            self.skipTest("this fixture has no walk-ons")
        forced = variants.build_variants(break_down(parse(NIGHT, "t")),
                                         character_looks={walk_ons[0]: 1})
        self.assertIn(walk_ons[0], {v.name for v in forced.of("character")})

    def test_a_character_gets_a_new_look_when_the_day_turns_over(self):
        sam = [v for v in self.plan.of("character") if v.name == "SAM"]
        self.assertEqual(len(sam), 2)                       # the night, then the day
        self.assertTrue(any("NIGHT" in v.variant for v in sam))
        self.assertTrue(any("DAY" in v.variant for v in sam))

    def test_every_scene_carries_its_own_wardrobe_plate(self):
        scenes = break_down(parse(NIGHT, "t")).scenes
        wardrobe = self.plan.of("wardrobe")
        self.assertEqual(len(wardrobe), len(scenes))
        self.assertEqual(sorted(v.scenes[0] for v in wardrobe),
                         sorted(sb.scene.number for sb in scenes))

    def test_wardrobe_is_counted_as_an_image_to_generate(self):
        self.assertEqual(self.plan.counts()["wardrobe"], len(self.plan.of("wardrobe")))
        self.assertEqual(self.plan.images, len(self.plan.variants))

    def test_a_look_records_the_scenes_it_covers(self):
        for variant in self.plan.variants:
            self.assertTrue(variant.scenes)

    def test_looks_can_be_overridden_when_you_know_better(self):
        forced = variants.build_variants(break_down(parse(NIGHT, "t")),
                                         character_looks={"SAM": 1})
        self.assertEqual(len([v for v in forced.of("character") if v.name == "SAM"]), 1)

    def test_images_is_the_variant_count_not_the_name_count(self):
        self.assertEqual(self.plan.images, len(self.plan.variants))
        self.assertGreater(len(self.plan.of("character")), 1)   # one name, two images

    def test_recurring_items_are_the_ones_spanning_scenes(self):
        for variant in self.plan.recurring("location"):
            self.assertGreater(len(variant.scenes), 1)


class TestFormula(unittest.TestCase):
    def test_seconds_follow_the_runtime_that_was_chosen(self):
        """The page rule winning has to move the shot count with it - it used
        not to, so a feature billed video off a runtime already rejected."""
        from budget import runtime as rt
        page = rt.Runtime(scenes=[], page_minutes=116.0, content_minutes=160.0)
        self.assertAlmostEqual(page.seconds, page.minutes * 60)
        self.assertAlmostEqual(page.seconds, 116 * 60)

        agree = rt.Runtime(scenes=[], page_minutes=100.0, content_minutes=95.0)
        self.assertTrue(agree.trustworthy)
        self.assertAlmostEqual(agree.seconds, 100 * 60)

    def test_shots_are_the_sum_of_the_scenes(self):
        """Not runtime / shot length computed separately - the two used to drift
        apart, so the scene table and the video bill disagreed."""
        est = planned(average_shot_seconds=4)
        self.assertEqual(est.shots, sum(est.scene_shots.values()))
        self.assertEqual(len(est.scene_shots), len(est.runtime.scenes))
        # every scene gets at least one shot however short it is
        self.assertTrue(all(n >= 1 for n in est.scene_shots.values()))
        # and it stays in the same neighbourhood as the runtime estimate
        rough = est.runtime.seconds / 4
        self.assertLess(abs(est.shots - rough), len(est.runtime.scenes) + 1)

    def test_a_longer_average_shot_means_fewer_shots(self):
        self.assertLess(planned(average_shot_seconds=8).shots,
                        planned(average_shot_seconds=4).shots)

    def test_character_and_location_sheets_build_slower_than_props(self):
        """A sheet is what everything else has to match - several angles, a look
        that has to hold, and the one people argue about in review."""
        a = formula.Assumptions()
        self.assertLess(a.anchors_per_artist_week, a.plates_per_artist_week)
        all_anchors = a.image_phase(100, 0, 1, anchors=100)
        no_anchors = a.image_phase(100, 0, 1, anchors=0)
        self.assertGreater(all_anchors["plate_work"], no_anchors["plate_work"])
        # a mixed pack lands between the two
        half = a.image_phase(100, 0, 1, anchors=50)
        self.assertGreater(half["plate_work"], no_anchors["plate_work"])
        self.assertLess(half["plate_work"], all_anchors["plate_work"])

    # --- the roster: teams, and people not on for the whole run -----------

    def test_two_soloists_get_through_twice_the_work(self):
        roles = [formula.Role("A", 4000, 1, per_week=3),
                 formula.Role("B", 4000, 1, per_week=3)]
        self.assertAlmostEqual(formula.crew_capacity(roles, 4, 3), 6.0)

    def test_a_team_shares_the_minutes_rather_than_adding_them(self):
        """The whole point of linking: cover and continuity, not throughput."""
        linked = [formula.Role("A", 4000, 1, per_week=3, team="Unit"),
                  formula.Role("B", 4000, 1, per_week=3, team="Unit")]
        self.assertAlmostEqual(formula.crew_capacity(linked, 4, 3), 3.0)

    def test_adding_to_a_team_does_not_raise_its_rate_on_its_own(self):
        one = [formula.Role("A", 4000, 1, per_week=3, team="Unit")]
        two = one + [formula.Role("B", 2500, 1, per_week=2, team="Unit")]
        self.assertAlmostEqual(formula.crew_capacity(one, 4, 3),
                               formula.crew_capacity(two, 4, 3))

    def test_a_team_rate_the_producer_sets_wins(self):
        """Two on one stream are not twice as fast, and not the same speed."""
        pod = [formula.Role("A", 4000, 1, per_week=3, team="Unit"),
               formula.Role("B", 2500, 1, per_week=2, team="Unit")]
        self.assertAlmostEqual(
            formula.crew_capacity(pod, 4, 3, {"Unit": 4.5}), 4.5)

    def test_clearing_a_team_rate_falls_back_to_the_best_in_the_pod(self):
        pod = [formula.Role("A", 4000, 1, per_week=3, team="Unit"),
               formula.Role("B", 2500, 1, per_week=2, team="Unit")]
        self.assertAlmostEqual(formula.crew_capacity(pod, 4, 3, {}), 3.0)
        self.assertAlmostEqual(formula.crew_capacity(pod, 4, 3, {"Unit": 0}), 3.0)

    def test_the_default_roster_is_two_seniors_in_teams_of_their_own(self):
        """Six minutes a week, as two independent streams."""
        roster = [formula.Role("Senior", 4000, 1, per_week=3, team="Team A"),
                  formula.Role("Senior", 4000, 1, per_week=3, team="Team B")]
        self.assertAlmostEqual(formula.crew_capacity(roster, 3, 3), 6.0)

    def test_a_new_team_is_what_adds_volume(self):
        two = [formula.Role("A", 4000, 1, per_week=3, team="Team A"),
               formula.Role("B", 4000, 1, per_week=3, team="Team B")]
        three = two + [formula.Role("C", 4000, 1, per_week=3, team="Team C")]
        self.assertAlmostEqual(formula.crew_capacity(three, 3, 3), 9.0)

    def test_a_team_on_for_part_of_the_run_contributes_pro_rata(self):
        pod = [formula.Role("A", 4000, 1, per_week=4, team="Unit", weeks=2)]
        self.assertAlmostEqual(formula.crew_capacity(pod, 4, 3), 2.0)

    def test_a_team_contributes_its_best_rate_once(self):
        linked = [formula.Role("Senior", 4000, 1, per_week=4, team="Unit"),
                  formula.Role("Junior", 2500, 3, per_week=2, team="Unit")]
        self.assertAlmostEqual(formula.crew_capacity(linked, 4, 3), 4.0)

    def test_everyone_in_a_team_is_still_paid(self):
        linked = [formula.Role("Senior", 4000, 1, per_week=4, team="Unit"),
                  formula.Role("Junior", 2500, 1, per_week=2, team="Unit")]
        self.assertAlmostEqual(sum(s["cost"] for s in formula.crew_cost(linked, 4)),
                               4 * 4000 + 4 * 2500)

    def test_a_part_run_role_contributes_pro_rata(self):
        roles = [formula.Role("B", 2500, 1, per_week=4, weeks=2)]
        self.assertAlmostEqual(formula.crew_capacity(roles, 4, 3), 2.0)

    def test_a_part_run_role_bills_only_the_weeks_it_is_on(self):
        seats = formula.crew_cost([formula.Role("B", 2500, 2, weeks=2)], 10)
        self.assertEqual(seats[0]["weeks"], 2)
        self.assertAlmostEqual(seats[0]["cost"], 2 * 2 * 2500)
        self.assertFalse(seats[0]["full_run"])

    def test_an_engagement_longer_than_the_run_is_capped_at_the_run(self):
        seats = formula.crew_cost([formula.Role("B", 2500, 1, weeks=99)], 6)
        self.assertEqual(seats[0]["weeks"], 6)

    def test_labour_is_heads_times_weeks_times_rate(self):
        """The line a producer checks by hand."""
        seats = formula.crew_cost([formula.Role("Senior", 4000, 2)], 104)
        self.assertAlmostEqual(seats[0]["cost"], 2 * 104 * 4000)

    def test_an_empty_role_costs_and_delivers_nothing(self):
        roles = [formula.Role("Ghost", 4000, 0, per_week=9)]
        self.assertAlmostEqual(formula.crew_capacity(roles, 4, 3), 0.0)
        self.assertEqual(formula.crew_cost(roles, 4), [])

    def test_the_review_floor_only_binds_on_small_packs(self):
        """Raising it lengthens a trailer without touching a feature, because a
        feature's plates ÷ reviewed-per-week is already past the floor."""
        a = formula.Assumptions()
        # 0.85 is above the floor but still under a feature's 543 ÷ 600 = 0.905
        slow = formula.Assumptions(review_floor_weeks=0.85)
        # a small pack: the floor is what it waits on, so it moves
        self.assertGreater(slow.image_phase(75, 5, 2)["review"],
                           a.image_phase(75, 5, 2)["review"])
        # a feature: the pack size already outruns the floor, so it does not
        self.assertAlmostEqual(slow.image_phase(543, 167, 2)["review"],
                               a.image_phase(543, 167, 2)["review"])

    def test_the_anchor_count_cannot_exceed_the_pack(self):
        a = formula.Assumptions()
        self.assertAlmostEqual(a.image_phase(10, 0, 1, anchors=999)["plate_work"],
                               a.image_phase(10, 0, 1, anchors=10)["plate_work"])

    def test_images_is_one_phase_of_plates_and_keyframes(self):
        """Two jobs, but the same people doing the same kind of work back to
        back - splitting them made the schedule read as though a crew downed
        tools in between."""
        a = formula.Assumptions()
        img = a.image_phase(543, 167, 2)
        self.assertAlmostEqual(img["plate_work"], 543 * a.plate_passes / a.plates_per_artist_week)
        self.assertAlmostEqual(img["frame_work"], 167 * a.keyframe_passes / a.scenes_per_artist_week)
        self.assertAlmostEqual(img["work"], img["plate_work"] + img["frame_work"])
        self.assertAlmostEqual(img["build"], img["work"] / 2)

    def test_the_schedule_is_images_then_delivery(self):
        est = planned()
        self.assertEqual([p["id"] for p in est.phases(2)], ["images", "delivery"])

    def test_the_build_compresses_with_crew_and_the_review_does_not(self):
        a = formula.Assumptions()
        two, twenty = a.image_phase(543, 167, 2), a.image_phase(543, 167, 20)
        self.assertAlmostEqual(two["build"] / 10, twenty["build"])
        self.assertAlmostEqual(two["review"], twenty["review"])
        self.assertGreater(two["weeks"], twenty["weeks"])

    def test_a_bigger_pack_takes_longer_to_approve(self):
        a = formula.Assumptions()
        self.assertGreater(a.image_phase(2000, 50, 20)["review"],
                           a.image_phase(200, 50, 20)["review"])

    def test_a_small_batch_still_takes_time_to_come_back(self):
        a = formula.Assumptions()
        self.assertAlmostEqual(a.image_phase(10, 2, 1)["review"],
                               a.pre_revision_rounds * a.review_floor_weeks)

    def test_the_image_phase_never_comes_in_under_its_floor(self):
        a = formula.Assumptions()
        for plates, scenes in ((1, 1), (17, 5), (543, 167)):
            for artists in (1, 5, 100):
                self.assertGreaterEqual(a.image_phase(plates, scenes, artists)["weeks"],
                                        a.image_minimum_weeks)

    def test_no_script_means_no_image_phase(self):
        self.assertEqual(formula.Assumptions().image_phase(0, 0, 2)["weeks"], 0)

    def test_the_guide_flags_a_long_phase_but_never_shortens_it(self):
        a = formula.Assumptions(scenes_per_artist_week=0.5)
        img = a.image_phase(50, 50, 1)
        self.assertGreater(img["weeks"], a.image_maximum_weeks)
        self.assertTrue(img["over_guide"])
        self.assertGreaterEqual(img["weeks"], math.ceil(img["raw"]))

    def test_every_phase_divides_by_the_crew(self):
        est = planned(scenes_per_artist_week=0.2)
        one = {p["id"]: p["weeks"] for p in est.phases(1)}
        four = {p["id"]: p["weeks"] for p in est.phases(4)}
        for phase in ("images", "delivery"):
            # the review latency does not divide, so allow for it
            self.assertLessEqual(four[phase], one[phase] / 4 + 2)

    def test_the_image_phase_bills_the_build_not_the_calendar(self):
        est = planned()
        img = lambda n: next(p for p in est.phases(n) if p["id"] == "images")
        self.assertEqual(img(1)["artist_weeks"], img(20)["artist_weeks"])
        self.assertGreaterEqual(img(1)["weeks"], img(20)["weeks"])

    def test_a_phase_that_idles_bills_the_retention(self):
        est = planned()
        row = est.labor(8, 4000)
        images = next(p for p in row["phases"] if p["id"] == "images")
        self.assertGreater(images["idle"], 0)
        self.assertAlmostEqual(images["billable"], images["retained"])

    def test_the_rates_land_a_feature_near_eight_weeks_of_images(self):
        """Calibrated against real scripts: plates and keyframes together come
        to roughly a dozen weeks on a feature at a small crew, two on a short."""
        a = formula.Assumptions()
        for plates, scenes in ((543, 167), (765, 211)):        # Arrival, 12 Years
            weeks = a.image_phase(plates, scenes, 2)["weeks"]
            self.assertGreaterEqual(weeks, 8)
            self.assertLessEqual(weeks, 20)
        self.assertEqual(a.image_phase(17, 5, 2)["weeks"], 2)

    def test_keyframes_are_per_scene_not_per_shot(self):
        est = planned(keyframes_per_scene=8)
        self.assertEqual(est.keyframes, len(est.breakdown.scenes) * 8)
        # boarding every shot would be far more work than boarding every scene
        self.assertLess(est.keyframes, est.shots * 8)

    def test_keyframes_per_scene_is_a_lever(self):
        self.assertLess(planned(keyframes_per_scene=4).keyframes,
                        planned(keyframes_per_scene=8).keyframes)

    def test_generation_counts_bill_every_pass_not_just_the_first(self):
        """Two rounds of full revisions means making the film three times, and
        the models charge three times. The schedule already counted those
        passes; the invoice used not to."""
        est = planned()
        a = est.assumptions
        self.assertEqual(est.reference_generations,
                         round(est.reference_images * 8 * a.plate_passes))
        self.assertEqual(est.keyframe_generations,
                         round(est.keyframes * 8 * a.keyframe_passes))
        # and a show with no revisions at all bills exactly one pass
        lean = planned(pre_revision_rounds=0, keyframe_revisions=0)
        self.assertEqual(lean.reference_generations, lean.reference_images * 8)
        self.assertEqual(lean.keyframe_generations, lean.keyframes * 8)
        self.assertEqual(est.image_generations,
                         est.reference_generations + est.keyframe_generations)

    def test_three_minutes_are_generated_for_every_usable_minute(self):
        est = planned()
        self.assertAlmostEqual(est.generated_seconds, est.runtime.seconds * 3)

    def test_a_second_revision_round_is_a_third_full_pass(self):
        est = planned(revisions_per_scene=2, labour_revisions=2)
        self.assertAlmostEqual(est.assumptions.revision_multiplier, 3.0)
        self.assertAlmostEqual(est.effort_minutes, est.runtime.minutes * 3.0)

    def test_a_partial_revision_is_still_a_lever(self):
        est = planned(revisions_per_scene=2, revision_shares=(1.0, 0.5))
        self.assertAlmostEqual(est.assumptions.revision_multiplier, 2.5)

    def test_one_labour_revision_is_two_passes_of_crew_time(self):
        est = planned(labour_revisions=1)
        self.assertAlmostEqual(est.effort_minutes, est.runtime.minutes * 2)

    def test_rounds_past_the_list_reuse_the_last_share(self):
        est = planned(revisions_per_scene=4, revision_shares=(1.0, 0.5))
        self.assertAlmostEqual(est.assumptions.revision_multiplier, 3.5)  # 1+1+.5+.5+.5

    def test_no_revisions_means_one_pass(self):
        est = planned(labour_revisions=0)
        self.assertAlmostEqual(est.effort_minutes, est.runtime.minutes)
        self.assertAlmostEqual(planned(revisions_per_scene=0).costs()["video_seconds_billed"],
                               planned().runtime.seconds
                               * planned().assumptions.generated_minutes_per_usable)

    def test_regenerating_less_shortens_the_schedule(self):
        self.assertLess(planned(revision_shares=(0.3, 0.2)).artist_weeks,
                        planned(revision_shares=(1.0, 1.0)).artist_weeks)

    def test_more_artists_shorten_the_calendar(self):
        est = planned()
        self.assertLessEqual(est.weeks_with(4), est.weeks_with(1))

    def test_labour_always_bills_whole_weeks_of_the_whole_crew(self):
        """`weeks = ceil(work / crew)` means retention always covers the work,
        so a part-week of delivery is paid as a full week - which is how people
        are actually engaged. If a future phase formula broke that, the bill
        would silently drop below the work; this is the tripwire."""
        for spw in (5.0, 0.2):                     # ordinary, and heavy enough to strain it
            est = planned(scenes_per_artist_week=spw)
            for n in (1, 2, 3, 5, 10, 20):
                for phase in est.labor(n, 4000)["phases"]:
                    self.assertAlmostEqual(phase["billable"], phase["weeks"] * n)
                    self.assertGreaterEqual(phase["retained"] + 1e-9, phase["artist_weeks"])
                    self.assertEqual(phase["short"], 0)

    def test_a_part_week_of_delivery_is_paid_as_a_whole_one(self):
        est = planned()
        delivery = next(p for p in est.labor(3, 4000)["phases"] if p["id"] == "delivery")
        self.assertLess(delivery["artist_weeks"], 1)       # a fraction of one artist-week
        self.assertEqual(delivery["weeks"], 1)             # booked as a week
        self.assertEqual(delivery["billable"], 3)          # and paid for all three artists

    def test_per_phase_billing_beats_the_aggregate(self):
        """A phase at 40% and a phase at 139% must not cancel out."""
        est = planned()
        row = est.labor(8, 4000)
        aggregate = max(row["work_weeks"], row["retained"])
        self.assertGreaterEqual(row["artist_weeks"] + 1e-9, aggregate)
        self.assertGreater(row["idle"], 0)

    def test_a_show_too_small_to_under_staff_is_idle_at_any_size(self):
        """Phase floors mean even one artist waits on a two-scene sample."""
        est = planned()
        self.assertGreater(est.labor(1, 4000)["idle"], 0)

    def test_labour_bills_the_retention_once_the_crew_outruns_the_work(self):
        """You cannot hold twenty artists and pay only for the weeks they were
        busy - which is what billing the work alone quietly assumed."""
        est = planned()
        many = est.labor(20, 4000)
        self.assertGreater(many["retained"], many["work_weeks"])
        self.assertAlmostEqual(many["artist_weeks"], many["retained"])
        self.assertGreater(many["idle"], 0)
        self.assertGreater(many["cost"], est.labor(1, 4000)["cost"])

    def test_labour_is_never_less_than_the_work_or_the_retention(self):
        est = planned()
        for n in (1, 2, 3, 5, 10, 20, 40):
            row = est.labor(n, 4000)
            self.assertGreaterEqual(row["artist_weeks"] + 1e-9, row["work_weeks"])
            self.assertGreaterEqual(row["artist_weeks"] + 1e-9, row["retained"])

    def test_weeks_are_always_whole(self):
        est = planned()
        for artists in (1, 2, 3, 7):
            weeks = est.weeks_with(artists)
            self.assertEqual(weeks, int(weeks))       # 1.2 weeks is booked as 2

    def test_rework_share_and_review_pace_are_levers(self):
        base = formula.Assumptions()
        cheap = formula.Assumptions(plate_rework_share=0.0)
        self.assertLess(cheap.image_phase(543, 167, 2)["work"],
                        base.image_phase(543, 167, 2)["work"])
        fast = formula.Assumptions(plates_reviewed_per_week=1500)
        self.assertLess(fast.image_phase(543, 167, 2)["review"],
                        base.image_phase(543, 167, 2)["review"])

    def test_no_phase_can_overrun_its_bars_any_more(self):
        """weeks = ceil(work / crew), so retention always covers the work."""
        est = planned(scenes_per_artist_week=0.2)
        for n in (1, 2, 5, 20):
            self.assertEqual(est.labor(n, 4000)["short"], 0)

    def test_the_busiest_crew_is_the_last_one_with_nobody_waiting(self):
        est = planned()
        best = est.busiest_crew()
        self.assertGreaterEqual(best, 1)
        self.assertGreater(est.labor(best + 4, 4000)["idle"],
                           est.labor(best, 4000)["idle"])

    def test_credits_and_crew_time_carry_different_rounds(self):
        """A crew gets asked to redo a scene more often than anyone pays to
        regenerate it, so the two are budgeted apart."""
        est = planned()
        a = est.assumptions
        self.assertEqual(a.revisions_per_scene, 1)          # paid for in credits
        self.assertEqual(a.labour_revisions, 2)             # paid for in hours
        self.assertAlmostEqual(a.revision_multiplier, 2.0)
        self.assertAlmostEqual(a.labour_multiplier, 3.0)
        # the schedule follows the crew, the video bill follows the credits
        self.assertAlmostEqual(est.effort_minutes, est.runtime.minutes * 3.0)
        self.assertAlmostEqual(est.costs()["video_seconds_billed"],
                               est.runtime.seconds * a.generated_minutes_per_usable * 2.0)

    def test_generation_work_is_the_same_pile_however_many_split_it(self):
        est = planned()
        work = lambda n: next(p for p in est.phases(n) if p["id"] == "delivery")["artist_weeks"]
        self.assertAlmostEqual(work(1), work(5))

    def test_a_script_with_no_scenes_has_no_schedule(self):
        est = planned()
        est.breakdown.scenes.clear()
        self.assertEqual(est.phases(2), [])
        self.assertEqual(est.keyframes, 0)

    def test_solving_for_a_deadline_returns_enough_artists(self):
        est = planned()
        for weeks in (6, 12):
            artists = est.artists_for(weeks)
            self.assertIsNotNone(artists)
            self.assertLessEqual(est.weeks_with(artists), weeks)

    def test_a_deadline_inside_pre_production_cannot_be_met(self):
        # no crew size beats the fixed two-week front of the schedule
        self.assertIsNone(planned().artists_for(1))

    def test_a_shot_shorter_than_the_minimum_take_still_bills_it(self):
        """A 2-second average against a 4-second minimum take means paying for
        the runtime twice over."""
        est = planned(average_shot_seconds=2)
        a = est.assumptions
        billed = est.costs("seedance-2.0-1080p")["video_seconds_billed"]
        self.assertAlmostEqual(
            billed,
            est.runtime.seconds * (4 / 2) * a.generated_minutes_per_usable
            * a.revision_multiplier)

    def test_video_is_billed_off_the_runtime(self):
        """A 120-minute film at 4:1 over three passes is 1,440 minutes of
        generation - the shot count does not enter into it."""
        est = planned()
        a = est.assumptions
        billed = est.costs()["video_seconds_billed"]
        self.assertAlmostEqual(billed, est.runtime.seconds
                               * a.generated_minutes_per_usable * a.revision_multiplier)
        # the worked example, in minutes
        self.assertAlmostEqual((120 * 60) * 4 * 3 / 60, 1440)

    def test_video_is_billed_for_the_first_cut_and_every_revision(self):
        est = planned()
        one_pass = planned(revisions_per_scene=0)
        self.assertAlmostEqual(est.costs()["video_seconds_billed"],
                               one_pass.costs()["video_seconds_billed"]
                               * est.assumptions.revision_multiplier)

    def test_the_bid_adds_up_from_its_parts(self):
        totals = planned().total(artists=2, weekly_rate=4000,
                                 contingency=0.20, margin=0.20)
        self.assertAlmostEqual(totals["direct"],
                               totals["generation"]["total"] + totals["labor"]["cost"])
        self.assertAlmostEqual(totals["contingency"], totals["direct"] * 0.20)
        self.assertAlmostEqual(totals["bid"], totals["cost_to_deliver"] * 1.20)

    def test_the_bid_is_crew_plus_generations_and_nothing_else(self):
        """There was a tooling line built on two rates nobody had researched,
        and an invented number in a bid is worse than no number."""
        est = planned()
        totals = est.total(artists=2, weekly_rate=4000)
        self.assertNotIn("tooling", totals)
        self.assertAlmostEqual(totals["direct"],
                               totals["labor"]["cost"] + totals["generation"]["total"])
        self.assertAlmostEqual(totals["bid"],
                               totals["direct"] * (1 + 0.20))

    def test_crew_is_exactly_heads_times_weeks_times_rate(self):
        est = planned()
        for n in (1, 2, 5):
            totals = est.total(artists=n, weekly_rate=4000)
            self.assertAlmostEqual(totals["labor"]["cost"],
                                   n * totals["labor"]["weeks"] * 4000)

    def test_a_dearer_model_raises_only_the_video_line(self):
        est = planned()
        cheap = est.costs("seedance-2.5-480p")
        dear = est.costs("seedance-2.0-4k")
        self.assertGreater(dear["video"], cheap["video"])
        self.assertAlmostEqual(dear["keyframes"], cheap["keyframes"])

    def test_provenance_separates_your_numbers_from_ours(self):
        marks = planned().provenance()
        self.assertEqual(marks["yours"]["generations_per_image"], 8)
        self.assertEqual(marks["yours"]["minutes_per_artist_week"], 3.0)
        self.assertEqual(marks["yours"]["revision_shares"], [1.0, 1.0])
        self.assertEqual(marks["yours"]["keyframes_per_scene"], 8.0)
        self.assertEqual(marks["yours"]["scenes_per_artist_week"], 22.0)
        self.assertIn("runtime_method", marks["ours"])

    def test_explain_shows_the_working(self):
        text = formula.explain(planned())
        for heading in ("RUNTIME", "IMAGES", "KEYFRAMES", "VIDEO", "SCHEDULE", "COST"):
            self.assertIn(heading, text)

    def test_zero_artists_is_refused(self):
        with self.assertRaises(ValueError):
            planned().weeks_with(0)


if __name__ == "__main__":
    unittest.main()

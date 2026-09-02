"""Each tool's decision logic and loop wiring, driven by fake verdicts (no API)."""

import unittest

from studio.tools import animation, character, cinematic, clearance, continuity, trailer
from tests.fakes import FakeImage, verdict

ALL_TRAITS = [c.id for c in cinematic.TRAITS]
ALL_ASPECTS = [c.id for c in continuity.ASPECTS]
ALL_STYLE = [c.id for c in animation.STYLE_DIMENSIONS]
ALL_FRAMING = [c.id for c in animation.FRAMING_DIMENSIONS]


class TestCinematic(unittest.TestCase):
    def test_the_high_bar_needs_both_criticals_and_seven_of_eight(self):
        seven = [t for t in ALL_TRAITS if t != "grain"]
        self.assertTrue(cinematic.compute_score(verdict(cinematic.TRAITS, seven)).ok)

        six = [t for t in seven if t != "lens"]
        self.assertFalse(cinematic.compute_score(verdict(cinematic.TRAITS, six)).ok)

    def test_losing_a_must_pass_trait_fails_an_otherwise_perfect_frame(self):
        for critical in ("dof", "photoreal"):
            others = [t for t in ALL_TRAITS if t != critical]
            score = cinematic.compute_score(verdict(cinematic.TRAITS, others))
            self.assertFalse(score.ok, critical)
            self.assertTrue(score.critical_misses)

    def test_report_names_the_verdict_and_every_trait(self):
        md = cinematic.report_markdown(verdict(cinematic.TRAITS, ALL_TRAITS))
        self.assertIn("CINEMATIC & REAL", md)
        for trait in cinematic.TRAITS:
            self.assertIn(trait.name, md)
        self.assertIn("(must-pass)", md)

        md = cinematic.report_markdown(verdict(cinematic.TRAITS, []))
        self.assertIn("NOT CINEMATIC", md)

    def test_handler_guards_before_spending_anything(self):
        self.assertIn("image", cinematic.run(None, "key", 0.85))
        self.assertEqual(cinematic.run(FakeImage("x"), "", 0.85), "Please paste your Gemini API key above.")


class TestClearance(unittest.TestCase):
    def test_sensitivity_decides_what_counts_as_a_flag(self):
        v = verdict(clearance.CATEGORIES, ["celebrity", "logo"],
                    per_result_confidence={"celebrity": 90, "logo": 30})
        self.assertEqual(clearance.compute_flags(v, min_confidence=50).flagged,
                         ["Celebrity / public-figure likeness"])
        self.assertEqual(clearance.compute_flags(v, min_confidence=20).count, 2)
        self.assertFalse(clearance.compute_flags(v, min_confidence=95).needs_review)

    def test_low_confidence_flags_still_show_in_the_table_as_low_conf(self):
        v = verdict(clearance.CATEGORIES, ["logo"], per_result_confidence={"logo": 30})
        md = clearance.report_markdown(v, min_confidence=50)
        self.assertIn("No flags", md)
        self.assertIn("(low-conf)", md)
        self.assertIn("not legal clearance", md)

    def test_a_clean_image_reports_no_flags(self):
        md = clearance.report_markdown(verdict(clearance.CATEGORIES, []))
        self.assertIn("No flags", md)
        self.assertNotIn("NEEDS RIGHTS REVIEW", md)


class TestContinuity(unittest.TestCase):
    def setUp(self):
        self.fix_calls = []

    def _fix(self, base, failing):
        self.fix_calls.append((base, list(failing)))
        return FakeImage(f"fix{len(self.fix_calls)}")

    def _check(self, script, default):
        return lambda img: verdict(continuity.ASPECTS,
                                   script.get(img.name, default))

    def test_a_consistent_still_is_left_alone(self):
        res = continuity.run_pipeline(
            FakeImage("ref"), FakeImage("shot"), "key",
            check_fn=self._check({}, ALL_ASPECTS), fix_fn=self._fix)
        self.assertTrue(res.ok)
        self.assertEqual(res.used, 0)
        self.assertEqual(self.fix_calls, [])

    def test_the_drifted_aspects_are_what_gets_sent_to_the_fixer(self):
        res = continuity.run_pipeline(
            FakeImage("ref"), FakeImage("shot"), "key",
            check_fn=self._check({"shot": ["set", "wardrobe", "props"],
                                  "fix1": ALL_ASPECTS}, ALL_ASPECTS),
            fix_fn=self._fix)
        self.assertTrue(res.ok)
        self.assertEqual(self.fix_calls[0][1], ["lighting", "color"])

    def test_retries_always_start_from_the_original_shot(self):
        original = FakeImage("shot")
        res = continuity.run_pipeline(
            FakeImage("ref"), original, "key",
            check_fn=self._check({}, ["set"]), fix_fn=self._fix, max_retries=3)
        self.assertFalse(res.ok)
        self.assertEqual(len(self.fix_calls), 3)
        for base, _ in self.fix_calls:
            self.assertIs(base, original)

    def test_wardrobe_drift_alone_fails_it_however_good_the_rest_is(self):
        others = [a for a in ALL_ASPECTS if a != "wardrobe"]
        score = continuity.compute(verdict(continuity.ASPECTS, others))
        self.assertFalse(score.ok)
        self.assertEqual(score.critical_misses, ["Wardrobe"])

    def test_the_fix_prompt_names_the_drifted_aspects_and_locks_the_rest(self):
        p = continuity.build_fix_prompt(["wardrobe", "color"])
        self.assertIn("WARDROBE", p)
        self.assertIn("COLOR GRADE", p)
        self.assertNotIn("PROPS", p)
        self.assertIn("KEEP EXACTLY AS-IS", p)

    def test_the_fix_prompt_survives_an_unknown_aspect_id(self):
        self.assertIn("the drifted aspects", continuity.build_fix_prompt(["nonsense"]))

    def test_report_shows_the_progress_across_attempts(self):
        res = continuity.run_pipeline(
            FakeImage("ref"), FakeImage("shot"), "key",
            check_fn=self._check({"shot": ["set"], "fix1": ALL_ASPECTS}, ALL_ASPECTS),
            fix_fn=self._fix)
        md = continuity.report_markdown(res)
        self.assertIn("CONTINUITY CONSISTENT", md)
        self.assertIn("1/5 -> 5/5", md)


class TestAnimation(unittest.TestCase):
    def setUp(self):
        self.restyled = []
        self.reframed = []

    def _restyle(self, source, style_ids, framing_ids):
        self.restyled.append((source, list(style_ids), list(framing_ids)))
        return FakeImage(f"restyle{len(self.restyled)}")

    def _reframe(self, source, framing_ids):
        self.reframed.append((source, list(framing_ids)))
        return FakeImage(f"reframe{len(self.reframed)}")

    def _run(self, style_script, framing_script, **kwargs):
        return animation.run_full(
            FakeImage("ref"), FakeImage("original"), "key",
            style_check_fn=lambda img: verdict(animation.STYLE_DIMENSIONS,
                                               style_script.get(img.name, ALL_STYLE)),
            framing_check_fn=lambda img: verdict(animation.FRAMING_DIMENSIONS,
                                                 framing_script.get(img.name, ALL_FRAMING)),
            restyle_fn=self._restyle, reframe_fn=self._reframe, **kwargs)

    def test_an_image_already_in_style_costs_nothing(self):
        res = self._run({}, {})
        self.assertTrue(res["best"].ok)
        self.assertEqual((self.restyled, self.reframed), ([], []))

    def test_restyling_starts_from_the_original_every_time(self):
        original = FakeImage("original")
        res = animation.run_full(
            FakeImage("ref"), original, "key", max_retries=2, reconcile_rounds=0,
            style_check_fn=lambda img: verdict(animation.STYLE_DIMENSIONS, []),
            framing_check_fn=lambda img: verdict(animation.FRAMING_DIMENSIONS, ALL_FRAMING),
            restyle_fn=self._restyle, reframe_fn=self._reframe)
        self.assertFalse(res["best"].ok)
        self.assertEqual(len(self.restyled), 2)
        for source, _, _ in self.restyled:
            self.assertIs(source, original)

    def test_framing_is_only_rescued_when_restyling_actually_moved_it(self):
        # style needs one fix; that fix drifts the framing; reframing repairs it.
        res = self._run(style_script={"original": [], "restyle1": ALL_STYLE},
                        framing_script={"restyle1": ["shot"], "reframe1": ALL_FRAMING})
        self.assertEqual(len(self.restyled), 1)
        self.assertEqual(len(self.reframed), 1)
        self.assertEqual(self.reframed[0][0].name, "restyle1")   # base = the styled image
        self.assertEqual(self.reframed[0][1], ["placement", "scale", "crop"])
        self.assertEqual(res["best"].label, "After framing pass")
        self.assertTrue(res["best"].ok)

    def test_no_framing_pass_when_the_original_never_needed_restyling(self):
        # The original trivially matches its own framing, so a "drift" reading there
        # must not trigger a reframe of an image nothing has touched.
        res = self._run(style_script={}, framing_script={"original": []})
        self.assertEqual(self.reframed, [])
        self.assertIsNone(res["framing_pass"])

    def test_reconcile_goes_back_to_the_original_with_both_sets_of_drift(self):
        # Style is fixed by a restyle, that restyle drifts the framing, the reframe
        # half-fixes the framing and knocks the style back out. Reconcile has to
        # start over from the original knowing both.
        res = self._run(
            style_script={"original": ["lines"], "reframe1": ["lines"]},
            framing_script={"restyle1": ["shot"], "reframe1": ["shot", "scale"]},
            max_retries=1, reconcile_rounds=1)

        source, style_ids, framing_ids = self.restyled[-1]
        self.assertEqual(source.name, "original")    # reconcile re-renders from the source
        self.assertIn("render", style_ids)
        self.assertIn("placement", framing_ids)      # and names what drifted on both axes
        self.assertTrue(res["best"].ok)
        self.assertEqual(res["best"].label, "Reconcile 1")

    def test_the_best_candidate_wins_even_if_a_later_one_scores_worse(self):
        res = self._run(style_script={"original": [], "restyle1": ALL_STYLE},
                        framing_script={"restyle1": ["shot", "placement"],
                                        "reframe1": ["shot"]},
                        max_retries=1, reconcile_rounds=0)
        self.assertEqual(res["best"].label, "After style pass")

    def test_restyle_prompt_only_mentions_drift_it_was_told_about(self):
        bare = animation.restyle_prompt()
        self.assertNotIn("pay particular attention", bare)
        self.assertNotIn("drifted the framing", bare)

        loaded = animation.restyle_prompt(["render"], ["shot"])
        self.assertIn("rendering technique", loaded)
        self.assertIn("shot type and camera angle", loaded)

    def test_report_lists_every_candidate(self):
        res = self._run(style_script={"original": [], "restyle1": ALL_STYLE},
                        framing_script={"restyle1": ["shot"], "reframe1": ALL_FRAMING})
        md = animation.report_markdown(res)
        self.assertIn("both style & framing pass: YES", md)
        self.assertIn("After style pass", md)
        self.assertIn("After framing pass", md)


class TestTrailer(unittest.TestCase):
    def _concept(self, shots):
        return trailer.TrailerConcept(
            logline="A logline.", tone="tense", visual_style="cold blue",
            music_vibe="drones", summary="A trailer.",
            shots=[trailer.Shot(order=o, beat=b, title=f"Shot {o}",
                                description=f"Visual {o}", duration_sec=d, title_card=card)
                   for o, b, d, card in shots])

    def test_shots_are_ordered_capped_and_renumbered(self):
        concept = self._concept([(3, "build", 2.0, ""), (1, "hook", 1.0, "SOON"),
                                 (2, "setup", 1.5, "")])
        meta = trailer.compute_shotlist(concept, max_shots=2)
        self.assertEqual([s.order for s in meta["shots"]], [1, 2])
        self.assertEqual([s.beat for s in meta["shots"]], ["hook", "setup"])
        self.assertEqual(meta["runtime_sec"], 2.5)
        self.assertEqual(meta["beats"], ["hook", "setup"])

    def test_a_thin_shotlist_is_flagged_not_silently_accepted(self):
        concept = self._concept([(1, "hook", 1.0, "")])
        meta = trailer.compute_shotlist(concept, min_shots=3)
        self.assertFalse(meta["enough"])
        self.assertIn("re-run for a fuller cut", trailer.format_concept(concept, meta))

    def test_repeated_beats_are_listed_once_in_order(self):
        meta = trailer.compute_shotlist(self._concept(
            [(1, "hook", 1.0, ""), (2, "build", 1.0, ""), (3, "build", 1.0, ""),
             (4, "tag", 2.0, "")]))
        self.assertEqual(meta["beats"], ["hook", "build", "tag"])

    def test_every_shot_renders_fresh_from_the_references(self):
        concept = self._concept([(1, "hook", 1.0, ""), (2, "tag", 2.0, "")])
        meta = trailer.compute_shotlist(concept)
        seen = []

        def gen(shot):
            seen.append(shot.order)
            return FakeImage(f"still{shot.order}")

        results = trailer.run_image_process(meta["shots"], concept, ["ref"], "key", gen_fn=gen)
        self.assertEqual(seen, [1, 2])
        self.assertTrue(all(r["image"] is not None for r in results))

    def test_one_refused_shot_does_not_sink_the_cut(self):
        concept = self._concept([(1, "hook", 1.0, ""), (2, "tag", 2.0, "")])
        meta = trailer.compute_shotlist(concept)

        def gen(shot):
            if shot.order == 1:
                raise RuntimeError("identity refusal")
            return FakeImage("still2")

        results = trailer.run_image_process(meta["shots"], concept, [], "key", gen_fn=gen)
        self.assertEqual(results[0]["image"], None)
        self.assertIn("identity refusal", results[0]["error"])
        self.assertIsNotNone(results[1]["image"])

    def test_concept_only_runs_skip_the_paid_stage(self):
        concept = self._concept([(1, "hook", 1.0, "")])
        _, _, results = trailer.run_pipeline(
            "script", [], "key", generate_images=False,
            concept_fn=lambda: concept,
            gen_fn=lambda shot: (_ for _ in ()).throw(AssertionError("should not render")))
        self.assertEqual(results, [])

    def test_screenplay_input_prefers_pasted_text(self):
        self.assertEqual(trailer.resolve_screenplay("  INT. ROOM  ", "ignored.txt"),
                         ("INT. ROOM", ""))

    def test_pdf_screenplays_say_so_instead_of_failing_obscurely(self):
        text, err = trailer.resolve_screenplay("", "script.pdf")
        self.assertEqual(text, "")
        self.assertIn("PDF screenplays aren't supported", err)

    def test_a_missing_file_reports_why(self):
        text, err = trailer.resolve_screenplay("", "/nope/missing.txt")
        self.assertEqual(text, "")
        self.assertIn("Couldn't read the screenplay file", err)

    def test_no_screenplay_at_all_is_not_an_error_just_empty(self):
        self.assertEqual(trailer.resolve_screenplay("", None), ("", ""))

    def test_table_cells_survive_pipes_in_the_text(self):
        concept = self._concept([(1, "hook", 1.0, "A | B")])
        md = trailer.format_concept(concept, trailer.compute_shotlist(concept))
        self.assertIn("A \\| B", md)


class TestCharacter(unittest.TestCase):
    def test_cosine_is_one_for_identical_vectors(self):
        self.assertAlmostEqual(character.cosine([1, 0, 0], [2, 0, 0]), 1.0)

    def test_zero_vectors_cannot_match(self):
        self.assertEqual(character.cosine([0, 0], [1, 1]), -1.0)

    def test_best_similarity_takes_the_closest_reference(self):
        self.assertAlmostEqual(
            character.best_similarity([1, 0], [[0, 1], [1, 0.01]]), 1.0, places=3)

    def test_no_references_enrolled_means_no_match(self):
        self.assertEqual(character.best_similarity([1, 0], []), -1.0)

    def test_one_clearing_face_is_enough_to_call_the_character_present(self):
        self.assertTrue(character.decide_present([0.1, 0.55], threshold=0.4))
        self.assertFalse(character.decide_present([0.1, 0.35], threshold=0.4))
        self.assertTrue(character.decide_present([0.4], threshold=0.4))   # boundary is inclusive

    def test_report_ranks_faces_by_similarity(self):
        results = [{"sim": 0.2, "match": False, "bbox": [0, 0, 1, 1]},
                   {"sim": 0.7, "match": True, "bbox": [0, 0, 1, 1]}]
        md = character.report_markdown(True, results, 0.4)
        self.assertIn("Character IS in the shot", md)
        self.assertLess(md.index("0.70"), md.index("0.20"))

    def test_no_faces_says_so(self):
        self.assertIn("No faces detected", character.report_markdown(False, [], 0.4))

    def test_handler_guards_before_loading_the_models(self):
        self.assertIn("reference photo", character.run(None, FakeImage("x"), 0.4)[1])
        self.assertIn("image to check", character.run(["a.png"], None, 0.4)[1])


if __name__ == "__main__":
    unittest.main()

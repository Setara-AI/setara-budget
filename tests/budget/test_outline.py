"""The outline reader, and the runtime that has to be stated for one.

These cover the two bugs the heuristic actually had - a location read as a
character, and a lead dropped for always starting a sentence - plus the floor
that keeps a mangled screenplay from being priced as an outline.
"""

import unittest

from budget.outline import (MIN_BEATS, beat_label, looks_like_outline,
                            outline_names, parse_outline, split_beats,
                            title_from_outline)
from budget.runtime import time_script
from budget.script import parse

OUTLINE = """THE CROSSING
A feature outline

1. THE DINER - Mara waits out the storm. Okonjo finds her and offers the job
   she swore off. She refuses.

2. THE RUNWAY - Night. Mara watches the cargo plane load. Okonjo waits by the
   fence, patient.

3. THE DINER - Mara comes back at dawn. Okonjo has not moved. She says yes.

4. THE HANGAR - They prep the aircraft. Mara finds the manifest does not match
   the cargo.

5. OVER THE STRAIT - The engine fails. Okonjo admits what is in the hold.

6. THE BEACH - They walk out of the surf with nothing. Mara keeps walking.
"""


class TestBeats(unittest.TestCase):
    def test_numbered_items_are_beats(self):
        self.assertEqual(len(split_beats(OUTLINE)), 6)

    def test_front_matter_is_dropped_not_folded_into_beat_one(self):
        self.assertNotIn("A feature outline", split_beats(OUTLINE)[0])

    def test_paragraphs_when_nothing_is_marked(self):
        text = "She waits out the storm.\n\nHe finds her.\n\nShe refuses him."
        self.assertEqual(len(split_beats(text)), 3)

    def test_continuation_lines_join_their_beat(self):
        self.assertIn("she swore off", split_beats(OUTLINE)[0])


class TestLabels(unittest.TestCase):
    def test_dash_label(self):
        self.assertEqual(beat_label("THE DINER - Mara waits."), "THE DINER")

    def test_colon_label(self):
        self.assertEqual(beat_label("The diner: Mara waits."), "The diner")

    def test_prose_has_no_label(self):
        self.assertEqual(beat_label("Mara waits out the storm and he finds her."), "")

    def test_a_long_run_of_words_is_not_a_label(self):
        long = " ".join(["word"] * 9)
        self.assertEqual(beat_label(f"{long} - and then this"), "")


class TestNames(unittest.TestCase):
    def setUp(self):
        self.script = parse_outline(OUTLINE)

    def test_finds_both_leads(self):
        self.assertEqual(sorted(self.script.characters), ["MARA", "OKONJO"])

    def test_a_lead_who_always_starts_a_sentence_is_still_found(self):
        """Okonjo opens the sentence in every beat he is in. An earlier rule
        skipped sentence-initial capitals and lost him entirely."""
        self.assertIn("OKONJO", self.script.characters)

    def test_a_location_label_is_never_a_character(self):
        """THE DINER appears in two beats, so the two-beat floor alone would
        have promoted it to a character with its own look sheet."""
        for name in self.script.characters:
            self.assertNotIn("DINER", name)
            self.assertNotIn("HANGAR", name)

    def test_one_beat_names_do_not_qualify(self):
        names = outline_names(["Wilkins signs the form.", "She leaves.", "He waits."], set())
        self.assertEqual(names, [])

    def test_stopwords_never_qualify(self):
        names = outline_names(["They wait.", "They leave.", "Later they return."], set())
        self.assertEqual(names, [])


class TestLocations(unittest.TestCase):
    def test_repeated_location_is_one_plate(self):
        script = parse_outline(OUTLINE)
        self.assertEqual(len(script.scenes), 6)
        self.assertEqual(len(script.locations), 5)     # THE DINER appears twice

    def test_unlabelled_beats_claim_no_location(self):
        """Under-claiming on purpose: an invented plate looks measured."""
        text = "She waits out the storm.\n\nHe finds her.\n\nShe refuses him."
        self.assertEqual(parse_outline(text).locations, [])

    def test_night_is_read_from_the_beat(self):
        script = parse_outline(OUTLINE)
        self.assertTrue(script.scenes[1].is_night)      # "Night."
        self.assertTrue(script.scenes[2].is_night)      # "at dawn"
        self.assertFalse(script.scenes[3].is_night)


class TestTitle(unittest.TestCase):
    def test_title_line_before_the_beats(self):
        self.assertEqual(title_from_outline(OUTLINE), "THE CROSSING")

    def test_no_title_when_the_beats_start_immediately(self):
        self.assertEqual(title_from_outline("1. THE DINER - She waits.\n"), "")

    def test_prose_is_not_a_title(self):
        self.assertEqual(title_from_outline("x" * 80), "")


class TestTheFloor(unittest.TestCase):
    def test_a_collapsed_screenplay_is_not_an_outline(self):
        """A PDF whose extraction lost its line breaks is one wall of text, and
        must fail loudly rather than be priced off a made-up runtime."""
        blob = ("MARA crosses the empty hangar floor and finds the manifest does "
                "not match the cargo she was told about")
        self.assertFalse(looks_like_outline(blob))

    def test_below_the_floor_is_refused(self):
        self.assertFalse(looks_like_outline("1. A - x\n\n2. B - y"))

    def test_at_the_floor_is_accepted(self):
        self.assertTrue(looks_like_outline("1. A - x\n\n2. B - y\n\n3. C - z"))
        self.assertEqual(MIN_BEATS, 3)


class TestStatedRuntime(unittest.TestCase):
    def test_an_outline_has_no_pages(self):
        self.assertEqual(parse_outline(OUTLINE).pages, 0.0)

    def test_without_a_stated_runtime_an_outline_times_to_zero(self):
        """Zero rather than a plausible number invented from prose length -
        which is what makes the missing runtime impossible to miss."""
        self.assertEqual(time_script(parse_outline(OUTLINE)).minutes, 0.0)

    def test_a_stated_runtime_is_the_runtime(self):
        timing = time_script(parse_outline(OUTLINE), stated=96)
        self.assertEqual(timing.minutes, 96)
        self.assertEqual(timing.seconds, 96 * 60)

    def test_a_stated_runtime_outranks_the_page_curve(self):
        script = parse("INT. A ROOM - DAY\n\n" + "She waits.\n" * 400)
        self.assertGreater(time_script(script).minutes, 0)
        self.assertEqual(time_script(script, stated=94).minutes, 94)

    def test_pacing_does_not_move_a_stated_runtime(self):
        """A stated runtime is an answer, not an estimate to be scaled."""
        script = parse_outline(OUTLINE)
        self.assertEqual(time_script(script, pacing=1.3, stated=96).minutes, 96)

    def test_a_stated_runtime_retires_the_words_per_page_check(self):
        """That check guards the PAGE count. Once a runtime is stated the page
        count sets nothing, so the warning would only cry wolf."""
        crammed = parse("INT. A ROOM - DAY\n\n" + "She waits and waits. " * 400)
        self.assertFalse(time_script(crammed).trustworthy)
        self.assertTrue(time_script(crammed, stated=94).trustworthy)


class TestSceneOverridesDoNotLeak(unittest.TestCase):
    def test_the_screenplay_parser_still_derives_its_own(self):
        script = parse("INT. A ROOM - DAY\n\nMARA\nHello.\n")
        self.assertEqual(script.scenes[0].characters, ["MARA"])
        self.assertGreater(script.scenes[0].pages, 0)


if __name__ == "__main__":
    unittest.main()

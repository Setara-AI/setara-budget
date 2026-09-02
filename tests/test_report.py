"""Markdown rendering - the bit users actually read."""

import unittest

from studio.criteria import Criterion, Score
from studio.loop import Attempt
from studio import report
from tests.fakes import partial_verdict, verdict

CRITERIA = [
    Criterion(id="a", name="Alpha", description="a", critical=True),
    Criterion(id="b", name="Beta", description="b"),
]


class TestTables(unittest.TestCase):
    def test_a_table_has_a_header_rule_and_one_row_per_item(self):
        md = report.table(["X", "Y"], [["1", "2"], ["3", "4"]])
        lines = md.splitlines()
        self.assertEqual(lines[0], "| X | Y |")
        self.assertEqual(lines[1], "| --- | --- |")
        self.assertEqual(len(lines), 4)

    def test_pipes_and_newlines_in_notes_cannot_break_the_table(self):
        self.assertEqual(report.cell("a | b\nc "), "a \\| b c")

    def test_a_criterion_the_model_forgot_still_gets_a_row(self):
        v = partial_verdict(CRITERIA, ["a"], omit=["b"])
        md = report.criteria_table(CRITERIA, v, ["Name", "V", "Why"], report.verdict_row)
        self.assertIn("Beta", md)
        self.assertIn("no result returned", md)

    def test_must_pass_criteria_are_marked(self):
        md = report.criteria_table(CRITERIA, verdict(CRITERIA, ["a", "b"]),
                                   ["Name", "V", "Why"], report.verdict_row)
        self.assertIn("Alpha (must-pass)", md)
        self.assertNotIn("Beta (must-pass)", md)


class TestLines(unittest.TestCase):
    def test_score_line_calls_out_critical_misses(self):
        v = verdict(CRITERIA, ["b"])
        from studio.criteria import score

        line = report.score_line(score(CRITERIA, v, 0.5), v, noun="aspects")
        self.assertIn("1/2 aspects (50%)", line)
        self.assertIn("Failing must-pass aspects:** Alpha", line)

    def test_outcome_distinguishes_untouched_fixed_and_failed(self):
        self.assertIn("already correct", report.outcome(True, 0, "Style"))
        self.assertIn("fixed after 2", report.outcome(True, 2, "Style"))
        self.assertIn("still off", report.outcome(False, 3, "Style"))

    def test_progress_reads_as_a_trail(self):
        attempts = [Attempt("x", None, None, Score(ok=False, passed=p, total=5, ratio=p / 5))
                    for p in (2, 4, 5)]
        self.assertEqual(report.progress(attempts), "2/5 -> 4/5 -> 5/5")

    def test_join_drops_empty_blocks(self):
        self.assertEqual(report.join("a", "", "b"), "a\n\nb")

    def test_errors_are_shown_in_a_code_fence(self):
        self.assertIn("```", report.error_block(RuntimeError("boom")))
        self.assertIn("boom", report.error_block(RuntimeError("boom")))


if __name__ == "__main__":
    unittest.main()

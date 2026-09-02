"""The estimate arithmetic, the approval ledger, the board, and sync."""

import os
import shutil
import tempfile
import unittest

from budget import assets, estimate, labor, plan, report, sync, tasks
from budget.assets import Kind, Library, Status
from budget.breakdown import break_down
from budget.project import Project
from budget.script import parse

SAMPLE = """
INT. WAREHOUSE - NIGHT

VIC pries open a CRATE with a CROWBAR.

VIC
Nothing.

EXT. DOCKS - DAY

DANA waits by a CONTAINER.

DANA
You're late.
"""


def a_plan(**kwargs):
    return plan.build_plan(break_down(parse(SAMPLE, "Sample")), plan.PlanConfig(**kwargs))


class TestEstimate(unittest.TestCase):
    def setUp(self):
        self.est = estimate.build(a_plan(), weeks=6)

    def test_the_stack_adds_up_from_the_bottom(self):
        est = self.est
        self.assertAlmostEqual(
            est.direct_cost, est.generation_cost + est.labor_cost + est.tooling_cost)
        self.assertAlmostEqual(est.contingency, est.direct_cost * est.contingency_rate)
        self.assertAlmostEqual(est.cost_to_deliver, est.direct_cost + est.contingency)
        self.assertAlmostEqual(est.margin, est.cost_to_deliver * est.margin_rate)
        self.assertAlmostEqual(est.bid, est.cost_to_deliver + est.margin)

    def test_zero_contingency_and_margin_bid_the_direct_cost(self):
        est = estimate.build(a_plan(), weeks=6, contingency_rate=0, margin_rate=0)
        self.assertAlmostEqual(est.bid, est.direct_cost)

    def test_the_traditional_baseline_is_day_rate_arithmetic(self):
        baseline = estimate.TraditionalBaseline(pages_per_shoot_day=2, cost_per_shoot_day=1000,
                                                post_percentage=0.5)
        self.assertAlmostEqual(baseline.shoot_days(10), 5)
        self.assertAlmostEqual(baseline.production(10), 5000)
        self.assertAlmostEqual(baseline.total(10), 7500)

    def test_a_negative_delta_means_the_ai_bid_undercuts(self):
        cheap = estimate.build(a_plan(), weeks=1,
                               baseline=estimate.TraditionalBaseline(cost_per_shoot_day=10_000_000))
        self.assertLess(cheap.delta, 0)
        self.assertLess(cheap.delta_percent, 0)

    def test_you_must_solve_for_one_of_headcount_or_schedule_not_both(self):
        with self.assertRaises(ValueError):
            estimate.build(a_plan(), weeks=4, team={"gen_artist": 1})
        with self.assertRaises(ValueError):
            estimate.build(a_plan())

    def test_a_pricier_tier_raises_the_bid(self):
        cheap = estimate.build(a_plan(), weeks=6, video_model_id="seedance-2.5-480p")
        dear = estimate.build(a_plan(), weeks=6, video_model_id="seedance-2.0-4k")
        self.assertGreater(dear.bid, cheap.bid)

    def test_the_report_renders_every_section_and_flags_projections(self):
        markdown = report.markdown(self.est)
        for heading in ("The stack", "Generation spend", "Crew", "Scenes",
                        "Assumptions", "Price sources"):
            self.assertIn(heading, markdown)
        self.assertIn("projected", markdown)

    def test_csv_and_json_agree_with_the_markdown(self):
        payload = report.payload(self.est)
        self.assertAlmostEqual(payload["costs"]["bid"], round(self.est.bid, 2))
        self.assertIn("BID", report.csv_lines(self.est))
        self.assertEqual(payload["models"]["video"], self.est.generation.video_model.id)


class TestApprovalLedger(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="budget-test-")
        self.library = Library(self.root)
        self.library.scaffold()
        self.asset = self.library.register(Kind.CHARACTER, "Mara Delacroix")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _generate(self, count=3):
        names = [f"opt_{i:02d}.png" for i in range(1, count + 1)]
        folder = os.path.join(self.root, assets.work_dir(self.asset))
        os.makedirs(folder, exist_ok=True)
        for name in names:
            with open(os.path.join(folder, name), "wb") as fh:
                fh.write(b"x")
        return self.library.add_options(self.asset, names)

    def test_nothing_reaches_the_approved_folder_without_a_selection(self):
        self._generate()
        with self.assertRaises(ValueError):
            self.library.approve(self.asset, "opt_99.png")
        self.assertEqual(self.asset.status, Status.GENERATED)

    def test_approving_copies_the_chosen_option_and_names_it_by_round(self):
        self._generate()
        self.library.approve(self.asset, "opt_02.png", by="supervisor")
        self.assertEqual(self.asset.status, Status.APPROVED)
        self.assertTrue(self.asset.approved_path.endswith("MARA_DELACROIX_v1.png"))
        self.assertTrue(os.path.exists(os.path.join(self.root, self.asset.approved_path)))

    def test_a_rejection_opens_the_next_round_and_keeps_the_last_one(self):
        self._generate()
        first_round_dir = os.path.join(self.root, assets.work_dir(self.asset))
        self.library.reject(self.asset, by="supervisor", note="too modern")
        self.assertEqual(self.asset.round, 2)
        self.assertEqual(self.asset.status, Status.PENDING)
        self.assertTrue(os.path.exists(first_round_dir))          # round 1 survives
        self.assertIn("1", self.asset.options)

    def test_the_history_records_who_did_what_in_which_round(self):
        self._generate()
        self.library.submit(self.asset, by="artist")
        self.library.reject(self.asset, by="supervisor")
        self._generate(2)
        self.library.approve(self.asset, "opt_01.png", by="supervisor")
        self.assertEqual([(h.round, h.action) for h in self.asset.history],
                         [(1, "generated"), (1, "submitted"), (1, "rejected"),
                          (2, "generated"), (2, "approved")])

    def test_extra_rounds_are_counted_so_the_budget_can_be_checked_against_them(self):
        self._generate()
        self.library.reject(self.asset)
        self._generate()
        self.assertEqual(self.library.revision_rounds_used(), 1)
        self.assertEqual(self.library.options_generated(), 6)

    def test_an_empty_option_set_is_refused(self):
        with self.assertRaises(ValueError):
            self.library.add_options(self.asset, [])

    def test_the_ledger_survives_a_reload(self):
        self._generate()
        self.library.approve(self.asset, "opt_01.png", by="supervisor")
        self.library.save()
        reloaded = Library(self.root)
        asset = reloaded.get(self.asset.id)
        self.assertEqual(asset.status, Status.APPROVED)
        self.assertEqual(asset.selected, "opt_01.png")
        self.assertEqual(len(asset.history), 2)

    def test_names_with_punctuation_become_safe_folders(self):
        asset = self.library.register(Kind.LOCATION, "ST. BRENDAN'S HOSPITAL - ROOF")
        self.assertNotIn("'", assets.work_dir(asset))
        self.assertNotIn(".", assets.work_dir(asset).replace(".png", ""))

    def test_seeding_registers_one_asset_per_thing_in_the_script(self):
        breakdown = break_down(parse(SAMPLE, "Sample"))
        library = Library(tempfile.mkdtemp(prefix="budget-seed-"))
        assets.seed_from_breakdown(library, breakdown)
        self.assertEqual(len(library.assets),
                         len(breakdown.characters) + len(breakdown.locations)
                         + len(breakdown.props))


class TestBoard(unittest.TestCase):
    def setUp(self):
        self.plan = a_plan()
        self.root = tempfile.mkdtemp(prefix="budget-board-")
        self.library = Library(self.root)
        assets.seed_from_breakdown(self.library, self.plan.breakdown)
        self.staffing = labor.staff_for(4, labor.volume(self.plan))
        self.tasks = tasks.build_tasks(self.plan, self.library)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_every_scene_gets_generate_review_and_assemble(self):
        for scene in self.plan.scenes:
            number = scene.scene.scene.number
            ids = {t.id for t in self.tasks}
            self.assertIn(f"generate:scene_{number:03d}", ids)
            self.assertIn(f"review-shots:scene_{number:03d}", ids)
            self.assertIn(f"assemble:scene_{number:03d}", ids)

    def test_a_scene_cannot_generate_before_its_assets_are_locked(self):
        generate = [t for t in self.tasks if t.id.startswith("generate:")][0]
        self.assertTrue(generate.blocked_by)
        self.assertTrue(all(gate.startswith("review:") for gate in generate.blocked_by))

    def test_assignment_leaves_nobody_unowned_and_spreads_the_load(self):
        staffing = labor.staff_for(1, labor.volume(self.plan))
        tasks.assign(self.tasks, staffing)
        self.assertFalse([t for t in self.tasks if t.unassigned])
        artists = {t.assignee for t in self.tasks if t.role == "asset_artist"}
        seat_count = staffing.seat("asset_artist").count
        self.assertEqual(len(artists), min(seat_count, len(
            [t for t in self.tasks if t.role == "asset_artist"])))

    def test_scheduling_never_puts_a_task_before_what_it_waits_on(self):
        tasks.assign(self.tasks, self.staffing)
        tasks.schedule(self.tasks, self.staffing)
        by_id = {t.id: t for t in self.tasks}
        for task in self.tasks:
            for gate in task.blocked_by:
                self.assertGreater(task.week, by_id[gate].week,
                                   f"{task.id} runs before {gate}")

    def test_an_approved_asset_shows_as_done_not_as_work(self):
        asset = next(a for a in self.library.assets.values() if a.kind is Kind.CHARACTER)
        self.library.add_options(asset, ["opt_01.png"])
        self.library.approve(asset, "opt_01.png", copy_file=False)
        rebuilt = tasks.build_tasks(self.plan, self.library)
        review = next(t for t in rebuilt if t.id == f"review:{asset.id}")
        self.assertEqual(review.status, tasks.TaskStatus.DONE)

    def test_work_that_does_not_fit_the_deadline_is_reported_not_hidden(self):
        # One week cannot hold a chain of build -> review -> generate -> assemble.
        tight = labor.staff_for(1, labor.volume(self.plan))
        tasks.assign(self.tasks, tight)
        tasks.schedule(self.tasks, tight)
        over = tasks.overruns(self.tasks, tight)
        self.assertTrue(over, "a 5-stage dependency chain cannot fit in one week")
        self.assertTrue(all(t.week > 1 for t in over))

    def test_accountability_reports_what_is_late_blocked_and_unowned(self):
        tasks.assign(self.tasks, self.staffing)
        tasks.schedule(self.tasks, self.staffing)
        report_ = tasks.accountability(self.tasks, current_week=99)
        self.assertEqual(len(report_["overdue"]),
                         len([t for t in self.tasks if t.status is not tasks.TaskStatus.DONE]))
        self.assertEqual(report_["unassigned"], [])
        self.assertEqual(report_["total"], len(self.tasks))


class TestSync(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="budget-sync-")
        self.mirror = tempfile.mkdtemp(prefix="budget-mirror-")
        self.library = Library(self.root)
        self.library.scaffold()
        self.approved = self.library.register(Kind.PROP, "CROWBAR")
        folder = os.path.join(self.root, assets.work_dir(self.approved))
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "opt_01.png"), "wb") as fh:
            fh.write(b"x")
        self.library.add_options(self.approved, ["opt_01.png"])
        self.library.approve(self.approved, "opt_01.png")
        self.pending = self.library.register(Kind.PROP, "CRATE")

    def tearDown(self):
        for path in (self.root, self.mirror):
            shutil.rmtree(path, ignore_errors=True)

    def test_only_approved_assets_leave_the_building(self):
        backend = sync.get("local", root=self.mirror)
        result = sync.push_approved(self.library, backend)
        self.assertEqual(len(result.uploaded), 1)
        self.assertIn(self.pending.id, [asset_id for asset_id, _ in result.skipped])
        self.assertTrue(os.path.exists(
            os.path.join(self.mirror, self.approved.approved_path)))

    def test_a_dry_run_sends_nothing_and_records_what_it_would_send(self):
        backend = sync.get("local", root=self.mirror, dry_run=True)
        result = sync.push_approved(self.library, backend)
        self.assertEqual(len(result.uploaded), 1)
        self.assertTrue(result.uploaded[0].dry_run)
        self.assertFalse(os.path.exists(os.path.join(self.mirror, "03_approved")))
        self.assertTrue(backend.calls)

    def test_the_remote_backends_default_to_dry_run(self):
        for name in ("frameio", "gdrive"):
            self.assertTrue(sync.get(name).dry_run, name)

    def test_going_live_without_a_token_fails_loudly(self):
        for name in ("frameio", "gdrive"):
            with self.assertRaises(RuntimeError, msg=name):
                sync.get(name, dry_run=False, token="")

    def test_the_folder_shape_is_preserved_on_the_far_side(self):
        backend = sync.get("gdrive", dry_run=True)
        sync.push_approved(self.library, backend)
        created = [call[2]["name"] for call in backend.calls if call[0] == "POST"]
        self.assertIn("03_approved", created)
        self.assertIn("props", created)
        self.assertIn("CROWBAR", created)

    def test_an_unknown_backend_names_the_real_ones(self):
        with self.assertRaises(KeyError) as caught:
            sync.get("dropbox")
        self.assertIn("frameio", str(caught.exception))


class TestProject(unittest.TestCase):
    def test_the_whole_pipeline_runs_end_to_end(self):
        root = tempfile.mkdtemp(prefix="budget-project-")
        try:
            project = Project.from_text(SAMPLE, "Sample", root=root)
            project.estimate(weeks=4)
            project.open_library(seed_shots=True)
            board = project.board()

            summary = project.summary()
            self.assertGreater(summary["bid"], 0)
            self.assertEqual(summary["scenes"], 2)
            self.assertTrue(board)
            self.assertTrue(os.path.exists(os.path.join(root, "03_approved")))
            self.assertIn("BID", report.csv_lines(project.current_estimate))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_solving_from_a_team_gives_a_schedule_instead_of_a_headcount(self):
        project = Project.from_text(SAMPLE, "Sample")
        est = project.estimate(team={"gen_artist": 2, "asset_artist": 2, "ai_supervisor": 1})
        self.assertEqual(est.staffing.headcount, 5)
        self.assertGreater(est.staffing.weeks, 0)


if __name__ == "__main__":
    unittest.main()


class TestUiPlumbing(unittest.TestCase):
    """The UI hands tables back in whatever shape its Gradio version prefers."""

    def test_a_pandas_dataframe_of_roles_survives_the_round_trip(self):
        import pandas as pd

        from budget import ui

        frame = pd.DataFrame(ui.roles_to_rows(), columns=ui.ROLE_COLUMNS)
        roles = ui.rows_to_roles(frame)
        self.assertEqual(len(roles), len(labor.DEFAULT_ROLES))
        self.assertEqual(roles[0].name, labor.DEFAULT_ROLES[0].name)
        self.assertEqual(roles[0].weekly_rate, labor.DEFAULT_ROLES[0].weekly_rate)

    def test_lists_dicts_and_none_all_normalise(self):
        from budget import ui

        self.assertEqual(ui.rows([[1, 2]]), [[1, 2]])
        self.assertEqual(ui.rows({"data": [[3]]}), [[3]])
        self.assertEqual(ui.rows(None), [])

    def test_edited_rates_actually_change_the_bid(self):
        from budget import ui

        cheap = ui.rows_to_roles([[r.name, 1000, "no", r.unit, r.per_week]
                                  for r in labor.DEFAULT_ROLES])
        dear = ui.rows_to_roles([[r.name, 9000, "no", r.unit, r.per_week]
                                 for r in labor.DEFAULT_ROLES])
        low = estimate.build(a_plan(), weeks=4, roles=cheap)
        high = estimate.build(a_plan(), weeks=4, roles=dear)
        self.assertLess(low.bid, high.bid)

    def test_the_whole_handler_runs_and_writes_its_exports(self):
        from budget import ui

        result = ui.run_estimate(
            SAMPLE, None, "seedance-2.5-1080p", "nano-banana-pro-2k",
            "Solve headcount from a deadline", 6, [], ui.roles_to_rows(),
            15, 20, 3.0, 85000, 25, 5, 3, 2, 1, 0.6, 2, 0.4,
            5, 7, 9, 12, 5)
        headline, full, csv_path, json_path, breakdown_md, board_md = result
        self.assertIn("AI production estimate", headline)
        self.assertIn("The stack", full)
        self.assertTrue(os.path.exists(csv_path))
        self.assertTrue(os.path.exists(json_path))
        self.assertIn("characters", breakdown_md)
        self.assertIn("Week", board_md)

    def test_no_script_is_a_message_not_a_traceback(self):
        from budget import ui

        headline = ui.run_estimate("", None, "seedance-2.5-1080p", "nano-banana-pro-2k",
                                   "Solve headcount from a deadline", 6, [],
                                   ui.roles_to_rows(), 15, 20, 3.0, 85000, 25,
                                   5, 3, 2, 1, 0.6, 2, 0.4, 5, 7, 9, 12, 5)[0]
        self.assertIn("Paste a screenplay", headline)

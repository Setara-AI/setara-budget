"""
Project - the whole pipeline behind one object.

    project = Project.from_script("nightshift.fountain", root="/shows/nightshift")
    project.estimate(weeks=8)          # or team={"gen_artist": 2, ...}
    project.board()                    # assigned, scheduled, dependency-gated
    project.push("local", root=...)    # approved assets only

Parse, breakdown, plan, estimate, ledger, board. Nothing here is clever; it is
the order the work actually happens in, in one place, so the UI and the tests
drive the same path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import assets as assets_module
from . import breakdown as breakdown_module
from . import estimate as estimate_module
from . import plan as plan_module
from . import pricing, report, script as script_module, sync, tasks as tasks_module


@dataclass
class Project:
    script: script_module.Script
    breakdown: breakdown_module.Breakdown
    plan: plan_module.Plan
    root: str = ""
    library: assets_module.Library | None = None
    _estimate: estimate_module.Estimate | None = None
    _tasks: list = field(default_factory=list)

    # -- construction -----------------------------------------------------
    @classmethod
    def from_text(cls, text: str, title: str = "Untitled", root: str = "",
                  config: plan_module.PlanConfig | None = None) -> "Project":
        parsed = script_module.parse(text, title)
        return cls._assemble(parsed, root, config)

    @classmethod
    def from_script(cls, path: str, root: str = "",
                    config: plan_module.PlanConfig | None = None) -> "Project":
        return cls._assemble(script_module.parse_file(path), root, config)

    @classmethod
    def _assemble(cls, parsed, root, config) -> "Project":
        broken_down = breakdown_module.break_down(parsed)
        return cls(script=parsed, breakdown=broken_down,
                   plan=plan_module.build_plan(broken_down, config), root=root)

    # -- money ------------------------------------------------------------
    def estimate(self, **kwargs) -> estimate_module.Estimate:
        kwargs.setdefault("weeks", None)
        if kwargs.get("weeks") is None and not kwargs.get("team"):
            kwargs["weeks"] = 8                       # a sane default to look at
        self._estimate = estimate_module.build(self.plan, **kwargs)
        return self._estimate

    @property
    def current_estimate(self) -> estimate_module.Estimate:
        return self._estimate or self.estimate()

    def markdown(self) -> str:
        return report.markdown(self.current_estimate)

    def payload(self) -> dict:
        return report.payload(self.current_estimate)

    # -- assets -----------------------------------------------------------
    def open_library(self, seed_shots: bool = False) -> assets_module.Library:
        if not self.root:
            raise ValueError("Project has no root folder - pass root= to create one.")
        self.library = assets_module.Library(self.root)
        self.library.scaffold()
        assets_module.seed_from_breakdown(
            self.library, self.breakdown,
            include_shots_for=self.plan if seed_shots else None)
        self.library.save()
        return self.library

    # -- board ------------------------------------------------------------
    def board(self, refresh: bool = False) -> list:
        if self._tasks and not refresh:
            return self._tasks
        library = self.library or assets_module.Library(self.root or "")
        built = tasks_module.build_tasks(self.plan, library)
        tasks_module.assign(built, self.current_estimate.staffing)
        tasks_module.schedule(built, self.current_estimate.staffing)
        self._tasks = built
        return built

    def accountability(self, current_week: int = 1) -> dict:
        return tasks_module.accountability(self.board(), current_week)

    # -- delivery ---------------------------------------------------------
    def push(self, backend_name: str = "local", **kwargs) -> sync.PushResult:
        if self.library is None:
            self.open_library()
        return sync.push_approved(self.library, sync.get(backend_name, **kwargs))

    # -- summary ----------------------------------------------------------
    def summary(self) -> dict:
        est = self.current_estimate
        return {
            "title": self.script.title,
            "pages": round(self.script.pages, 1),
            "scenes": len(self.plan.scenes),
            "shots": self.plan.shots,
            "characters": len(self.breakdown.characters),
            "locations": len(self.breakdown.locations),
            "props": len(self.breakdown.props),
            "bid": round(est.bid, 2),
            "traditional": round(est.traditional_bid, 2),
            "delta_percent": round(est.delta_percent, 4),
            "weeks": est.staffing.weeks,
            "headcount": est.staffing.headcount,
            "video_model": est.generation.video_model.id,
        }

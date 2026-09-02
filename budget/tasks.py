"""
Tasks - assignment and accountability, Linear-style.

The board is derived, not typed in. Every task traces back to something the
script actually requires: an asset to build, a round to review, a scene to
generate, a scene to cut. That is what makes it accountable - nobody can quietly
drop a shot, because the shot is in the breakdown.

Order of work follows the dependency the pipeline already has:

    build reference assets -> approve them -> generate shots -> assemble scenes

so a shot task is blocked until the assets its scene depends on are approved.
The scheduler spreads tasks across the weeks the estimate bought, respecting
those blocks and each role's weekly throughput.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from enum import Enum

from .assets import Asset, Kind, Library, Status as AssetStatus


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    BLOCKED = "blocked"
    DONE = "done"


class TaskKind(str, Enum):
    BUILD_ASSET = "build_asset"
    REVIEW_ASSET = "review_asset"
    GENERATE_SHOTS = "generate_shots"
    REVIEW_SHOTS = "review_shots"
    ASSEMBLE = "assemble"


# Which role owns which kind of task.
TASK_ROLES = {
    TaskKind.BUILD_ASSET: "asset_artist",
    TaskKind.REVIEW_ASSET: "ai_supervisor",
    TaskKind.GENERATE_SHOTS: "gen_artist",
    TaskKind.REVIEW_SHOTS: "continuity",
    TaskKind.ASSEMBLE: "editor",
}

# The unit each task kind consumes, for load-aware scheduling.
TASK_UNITS = {
    TaskKind.BUILD_ASSET: "images",
    TaskKind.REVIEW_ASSET: "images",
    TaskKind.GENERATE_SHOTS: "shot_attempts",
    TaskKind.REVIEW_SHOTS: "images",
    TaskKind.ASSEMBLE: "scenes",
}


@dataclass
class Task:
    id: str
    title: str
    kind: TaskKind
    role: str
    units: float = 1.0
    asset_id: str = ""
    scene: int | None = None
    assignee: str = ""
    status: TaskStatus = TaskStatus.TODO
    week: int = 0                       # 1-based week it is scheduled into
    blocked_by: list = field(default_factory=list)

    @property
    def unassigned(self) -> bool:
        return not self.assignee

    def as_dict(self) -> dict:
        return {**asdict(self), "kind": self.kind.value, "status": self.status.value}


# ---------------------------------------------------------------------------
# Deriving the board from the work
# ---------------------------------------------------------------------------

def build_tasks(plan, library: Library) -> list[Task]:
    """One board, derived from the plan and the asset ledger."""
    config = plan.config
    tasks: list[Task] = []

    reference_kinds = (Kind.CHARACTER, Kind.LOCATION, Kind.PROP)
    per_asset_images = {
        Kind.CHARACTER: config.options_per_asset * config.angles_per_character,
        Kind.LOCATION: config.options_per_asset * config.plates_per_location,
        Kind.PROP: config.options_per_asset * config.plates_per_prop,
    }

    approvals: dict[str, str] = {}      # asset id -> the review task that clears it
    for asset in library.assets.values():
        if asset.kind not in reference_kinds:
            continue
        build_id = f"build:{asset.id}"
        review_id = f"review:{asset.id}"
        tasks.append(Task(
            id=build_id,
            title=f"Build {asset.kind.value[:-1]} plates - {asset.name}",
            kind=TaskKind.BUILD_ASSET, role=TASK_ROLES[TaskKind.BUILD_ASSET],
            units=per_asset_images[asset.kind], asset_id=asset.id,
            status=_status_for(asset)))
        tasks.append(Task(
            id=review_id,
            title=f"Review & lock - {asset.name}",
            kind=TaskKind.REVIEW_ASSET, role=TASK_ROLES[TaskKind.REVIEW_ASSET],
            units=per_asset_images[asset.kind], asset_id=asset.id,
            blocked_by=[build_id],
            status=TaskStatus.DONE if asset.status is AssetStatus.APPROVED else TaskStatus.TODO))
        approvals[asset.id] = review_id

    # Shots are batched per scene - that is how they are reviewed.
    for scene_plan in plan.scenes:
        scene = scene_plan.scene.scene
        number = scene.number
        gates = _gates_for_scene(scene_plan, library, approvals)
        generate_id = f"generate:scene_{number:03d}"
        review_id = f"review-shots:scene_{number:03d}"
        tasks.append(Task(
            id=generate_id,
            title=(f"Generate {scene_plan.shots} shot{'' if scene_plan.shots == 1 else 's'}"
                   f" - sc.{number} {scene.location}"),
            kind=TaskKind.GENERATE_SHOTS, role=TASK_ROLES[TaskKind.GENERATE_SHOTS],
            units=scene_plan.shots * scene_plan.attempts_per_shot, scene=number,
            blocked_by=gates))
        tasks.append(Task(
            id=review_id,
            title=f"Continuity pass - sc.{number}",
            kind=TaskKind.REVIEW_SHOTS, role=TASK_ROLES[TaskKind.REVIEW_SHOTS],
            units=scene_plan.shots * scene_plan.attempts_per_shot, scene=number,
            blocked_by=[generate_id]))
        tasks.append(Task(
            id=f"assemble:scene_{number:03d}",
            title=f"Assemble sc.{number}",
            kind=TaskKind.ASSEMBLE, role=TASK_ROLES[TaskKind.ASSEMBLE],
            units=1, scene=number, blocked_by=[review_id]))
    return tasks


def _status_for(asset: Asset) -> TaskStatus:
    return {
        AssetStatus.PENDING: TaskStatus.TODO,
        AssetStatus.GENERATED: TaskStatus.IN_PROGRESS,
        AssetStatus.IN_REVIEW: TaskStatus.REVIEW,
        AssetStatus.APPROVED: TaskStatus.DONE,
        AssetStatus.REJECTED: TaskStatus.TODO,
    }[asset.status]


def _gates_for_scene(scene_plan, library: Library, approvals: dict) -> list:
    """A scene cannot generate until the assets it uses are locked."""
    from .assets import asset_id

    gates = []
    breakdown = scene_plan.scene
    for name in breakdown.cast:
        gates.append(approvals.get(asset_id(Kind.CHARACTER, name)))
    gates.append(approvals.get(asset_id(Kind.LOCATION, breakdown.scene.location)))
    for prop in breakdown.props:
        gates.append(approvals.get(asset_id(Kind.PROP, prop)))
    return [g for g in gates if g]


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def seat_names(staffing) -> dict:
    """{role_id: ['gen_artist_1', 'gen_artist_2', ...]} from the costed seats."""
    return {seat.role.id: [f"{seat.role.id}_{i}" for i in range(1, seat.count + 1)]
            for seat in staffing.seats}


def assign(tasks: list[Task], staffing, only_unassigned: bool = True) -> list[Task]:
    """Round-robin within each role, so load is even and every task has an owner."""
    names = seat_names(staffing)
    cursors = {role: 0 for role in names}
    for task in tasks:
        if task.assignee and only_unassigned:
            continue
        people = names.get(task.role)
        if not people:
            continue
        task.assignee = people[cursors[task.role] % len(people)]
        cursors[task.role] += 1
    return tasks


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

def schedule(tasks: list[Task], staffing, horizon: int | None = None) -> list[Task]:
    """Place tasks into weeks: never before what they depend on, never past capacity.

    Tasks are NOT clamped into the horizon. If the dependency chain and the
    weekly capacity push work past the weeks the estimate bought, the task keeps
    its true week and `overruns()` reports it. A schedule that quietly folds
    three weeks of gated work into the final week is not a schedule.
    """
    horizon = horizon or max(1, math.ceil(staffing.weeks))
    ceiling = horizon * 4 + len(tasks)          # a bound, so a pathological plan terminates
    by_id = {task.id: task for task in tasks}
    capacity = {}
    for seat in staffing.seats:
        if seat.role.per_week:
            capacity[seat.role.id] = seat.role.per_week * seat.count

    used = {}                                   # (role, week) -> units placed
    for task in _in_dependency_order(tasks, by_id):
        earliest = 1
        for gate in task.blocked_by:
            blocker = by_id.get(gate)
            if blocker is not None:
                earliest = max(earliest, blocker.week + 1)

        room = capacity.get(task.role)
        week = earliest
        if room:
            while week < ceiling and used.get((task.role, week), 0) + task.units > room:
                week += 1
        task.week = week
        used[(task.role, week)] = used.get((task.role, week), 0) + task.units
        if task.status is TaskStatus.TODO and task.blocked_by:
            unmet = [g for g in task.blocked_by
                     if by_id.get(g) and by_id[g].status is not TaskStatus.DONE]
            if unmet:
                task.status = TaskStatus.BLOCKED
    return tasks


def _in_dependency_order(tasks: list[Task], by_id: dict) -> list[Task]:
    """Topological order, tolerant of a missing or circular gate."""
    ordered, seen = [], set()

    def visit(task, trail=()):
        if task.id in seen or task.id in trail:
            return
        for gate in task.blocked_by:
            blocker = by_id.get(gate)
            if blocker is not None:
                visit(blocker, trail + (task.id,))
        if task.id not in seen:
            seen.add(task.id)
            ordered.append(task)

    for task in tasks:
        visit(task)
    return ordered


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def overruns(tasks: list[Task], staffing, horizon: int | None = None) -> list[Task]:
    """Tasks the schedule pushes past the weeks the estimate paid for."""
    horizon = horizon or max(1, math.ceil(staffing.weeks))
    return [task for task in tasks if task.week > horizon]


def board(tasks: list[Task]) -> dict:
    grouped = {status: [] for status in TaskStatus}
    for task in tasks:
        grouped[task.status].append(task)
    return grouped


def by_week(tasks: list[Task]) -> dict:
    weeks = {}
    for task in tasks:
        weeks.setdefault(task.week, []).append(task)
    return dict(sorted(weeks.items()))


def by_assignee(tasks: list[Task]) -> dict:
    people = {}
    for task in tasks:
        people.setdefault(task.assignee or "UNASSIGNED", []).append(task)
    return dict(sorted(people.items()))


def accountability(tasks: list[Task], current_week: int) -> dict:
    """What a producer chases on a Monday."""
    overdue = [t for t in tasks
               if t.week and t.week < current_week and t.status is not TaskStatus.DONE]
    return {
        "current_week": current_week,
        "due_this_week": [t.id for t in tasks
                          if t.week == current_week and t.status is not TaskStatus.DONE],
        "overdue": [t.id for t in overdue],
        "unassigned": [t.id for t in tasks if t.unassigned],
        "blocked": [t.id for t in tasks if t.status is TaskStatus.BLOCKED],
        "latest_week": max((t.week for t in tasks), default=0),
        "done": sum(1 for t in tasks if t.status is TaskStatus.DONE),
        "total": len(tasks),
        "percent_complete": (sum(1 for t in tasks if t.status is TaskStatus.DONE) / len(tasks))
                            if tasks else 0.0,
    }

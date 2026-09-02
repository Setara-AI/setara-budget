"""
Labor - who you need, for how long, at what weekly rate.

Two questions, one model, solved in either direction:

    staff_for(weeks)     "we ship in 6 weeks - how many people is that?"
    schedule_for(team)   "we have these 4 people - how long does it take?"

A role is either VOLUME-DRIVEN (its headcount scales with the work: generation
artists, asset artists, reviewers) or FIXED (it runs for the duration whatever
the volume: supervisor, producer). Volume-driven roles carry a throughput - how
many units of their work unit one person clears in a week.

THE RATES BELOW ARE PLACEHOLDERS. They exist so the tool runs out of the box;
put your own weekly rates in before you quote anything. `WorkVolume` is what the
script actually generated, so only the rates and throughputs are opinions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .plan import Plan


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    weekly_rate: float
    unit: str = ""              # "" = fixed role, runs for the duration
    per_week: float = 0.0       # units one person clears per week
    ai: bool = False            # an AI-operator seat rather than a traditional craft seat
    note: str = ""

    @property
    def fixed(self) -> bool:
        return not self.unit


# Placeholder weekly rates - override with your own before quoting.
DEFAULT_ROLES = [
    Role("ai_supervisor", "AI Supervisor / Lead", 6000, ai=True,
         note="Owns the look, the approvals and the model choices. Runs for the whole show."),
    Role("producer", "AI Producer / Coordinator", 4000,
         note="Schedules, chases approvals, keeps the ledger honest."),
    Role("gen_artist", "Generation Artist", 3500, unit="shot_attempts", per_week=40, ai=True,
         note="Prompts, generates and iterates shots."),
    Role("asset_artist", "Reference / Asset Artist", 3000, unit="images", per_week=150, ai=True,
         note="Builds the character, location and prop plates the video model eats."),
    Role("continuity", "Continuity Supervisor", 2800, unit="images", per_week=250,
         note="Owns continuity across scenes - wardrobe, props, light."),
    Role("editor", "Editor / Assembly", 3500, unit="scenes", per_week=10,
         note="Cuts the generated coverage into scenes."),
]


@dataclass
class WorkVolume:
    """The measurable work the plan implies, by unit."""

    shots: int
    shot_attempts: float
    images: float
    scenes: int
    pages: float

    def of(self, unit: str) -> float:
        return float(getattr(self, unit, 0.0))


def volume(plan: Plan) -> WorkVolume:
    return WorkVolume(
        shots=plan.shots,
        shot_attempts=sum(s.shots * s.attempts_per_shot for s in plan.scenes),
        images=plan.total_images,
        scenes=len(plan.scenes),
        pages=plan.breakdown.script.pages,
    )


@dataclass
class Seat:
    role: Role
    count: int
    weeks: float

    @property
    def cost(self) -> float:
        return self.count * self.role.weekly_rate * self.weeks

    @property
    def person_weeks(self) -> float:
        return self.count * self.weeks


@dataclass
class Staffing:
    seats: list[Seat]
    weeks: float
    volume: WorkVolume
    driver: str = ""            # which role set the schedule

    @property
    def total(self) -> float:
        return sum(seat.cost for seat in self.seats)

    @property
    def headcount(self) -> int:
        return sum(seat.count for seat in self.seats)

    @property
    def person_weeks(self) -> float:
        return sum(seat.person_weeks for seat in self.seats)

    @property
    def ai_headcount(self) -> int:
        return sum(seat.count for seat in self.seats if seat.role.ai)

    def seat(self, role_id: str) -> Seat | None:
        for seat in self.seats:
            if seat.role.id == role_id:
                return seat
        return None


def _weeks_needed(role: Role, work: WorkVolume, count: int) -> float:
    if role.fixed or not count or not role.per_week:
        return 0.0
    return work.of(role.unit) / (role.per_week * count)


def staff_for(weeks: float, work: WorkVolume, roles=None,
              fixed_counts: dict | None = None) -> Staffing:
    """Given a deadline, how many of each role does the work require?"""
    if weeks <= 0:
        raise ValueError("weeks must be positive")
    roles = roles or DEFAULT_ROLES
    fixed_counts = fixed_counts or {}

    seats = []
    for role in roles:
        if role.fixed:
            count = int(fixed_counts.get(role.id, 1))
        else:
            needed = work.of(role.unit) / (role.per_week * weeks) if role.per_week else 0
            count = max(1, math.ceil(needed - 1e-9)) if work.of(role.unit) else 0
        if count:
            seats.append(Seat(role=role, count=count, weeks=weeks))
    return Staffing(seats=seats, weeks=weeks, volume=work, driver="deadline")


def schedule_for(team: dict, work: WorkVolume, roles=None) -> Staffing:
    """Given a team ({role_id: headcount}), how long does the work take?

    The schedule is set by the slowest volume-driven role - the bottleneck - and
    every seat, fixed roles included, is carried for that duration.
    """
    roles = roles or DEFAULT_ROLES
    by_id = {role.id: role for role in roles}

    weeks, driver = 0.0, ""
    for role_id, count in team.items():
        role = by_id.get(role_id)
        if role is None or role.fixed:
            continue
        needed = _weeks_needed(role, work, int(count))
        if needed > weeks:
            weeks, driver = needed, role.name
    weeks = max(weeks, 1.0)

    seats = [Seat(role=by_id[rid], count=int(count), weeks=weeks)
             for rid, count in team.items() if rid in by_id and int(count) > 0]
    return Staffing(seats=seats, weeks=round(weeks, 2), volume=work,
                    driver=driver or "minimum one week")


def bottlenecks(staffing: Staffing) -> list[dict]:
    """Per volume-driven seat: what it must clear per week, and whether it can."""
    rows = []
    for seat in staffing.seats:
        if seat.role.fixed:
            continue
        required = staffing.volume.of(seat.role.unit)
        capacity = seat.role.per_week * seat.count * staffing.weeks
        rows.append({
            "role": seat.role.name,
            "unit": seat.role.unit,
            "required": round(required, 1),
            "capacity": round(capacity, 1),
            "utilisation": (required / capacity) if capacity else 0.0,
            "short": required > capacity + 1e-9,
        })
    return rows

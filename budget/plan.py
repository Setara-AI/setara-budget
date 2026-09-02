"""
Plan - how much generation work the script implies.

Everything here is an ASSUMPTION with a number attached, gathered into one
`PlanConfig` so a producer can argue with it directly instead of reverse
engineering it out of a spreadsheet. Nothing in this module is a price; it
counts shots, plates and attempts. `costs.py` puts money on them.

The revision model is deliberately simple enough to defend in a meeting:

    expected attempts per shot = 1 + rounds(tier) x hit_rate

`rounds` is how many review rounds you budget for a scene of that complexity;
`hit_rate` is the share of shots that actually come back needing another pass.
Both are tunable, and the report prints them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .breakdown import Breakdown, SceneBreakdown, Tier


@dataclass
class TierPlan:
    """Per-complexity-tier assumptions."""

    shots_per_page: float
    seconds_per_shot: float
    revision_rounds: int
    plates_per_shot: float


DEFAULT_TIER_PLANS = {
    Tier.SIMPLE:   TierPlan(shots_per_page=5,  seconds_per_shot=5, revision_rounds=1, plates_per_shot=1.0),
    Tier.MODERATE: TierPlan(shots_per_page=7,  seconds_per_shot=5, revision_rounds=2, plates_per_shot=1.0),
    Tier.COMPLEX:  TierPlan(shots_per_page=9,  seconds_per_shot=6, revision_rounds=3, plates_per_shot=1.5),
    Tier.HERO:     TierPlan(shots_per_page=12, seconds_per_shot=6, revision_rounds=4, plates_per_shot=2.0),
}


@dataclass
class PlanConfig:
    """Every assumption that turns a script into a work count."""

    tiers: dict = field(default_factory=lambda: dict(DEFAULT_TIER_PLANS))

    # Revisions
    hit_rate: float = 0.6           # share of shots that come back in a given round
    asset_hit_rate: float = 0.4     # share of reference assets that need another round
    asset_revision_rounds: int = 2

    # Reference assets, generated once and approved for the whole show
    options_per_asset: int = 5      # how many options you generate to choose from
    angles_per_character: int = 3   # views on a character sheet (front / profile / 3q)
    plates_per_location: int = 2    # establishing + alt angle
    plates_per_prop: int = 1

    def tier(self, tier: Tier) -> TierPlan:
        return self.tiers[tier]


@dataclass
class ScenePlan:
    scene: SceneBreakdown
    shots: int
    seconds_per_shot: float
    attempts_per_shot: float
    revision_rounds: int
    plates_per_shot: float

    @property
    def number(self) -> int:
        return self.scene.number

    @property
    def tier(self) -> Tier:
        return self.scene.complexity.tier

    @property
    def final_seconds(self) -> float:
        """Screen seconds actually delivered by this scene."""
        return self.shots * self.seconds_per_shot

    @property
    def generated_seconds(self) -> float:
        """Seconds you PAY for - deliverable plus every revision attempt."""
        return self.final_seconds * self.attempts_per_shot

    @property
    def shot_plates(self) -> float:
        return self.shots * self.plates_per_shot * self.attempts_per_shot


@dataclass
class AssetPlan:
    """The one-off reference library: characters, locations, props."""

    characters: int
    locations: int
    props: int
    options: int
    angles_per_character: int
    plates_per_location: int
    plates_per_prop: int
    revision_multiplier: float

    @property
    def base_images(self) -> float:
        return self.options * (
            self.characters * self.angles_per_character
            + self.locations * self.plates_per_location
            + self.props * self.plates_per_prop)

    @property
    def images(self) -> float:
        return self.base_images * self.revision_multiplier

    @property
    def approved_assets(self) -> int:
        """One approved version of each asset ends up in the approved folders."""
        return self.characters + self.locations + self.props


@dataclass
class Plan:
    breakdown: Breakdown
    scenes: list[ScenePlan]
    assets: AssetPlan
    config: PlanConfig

    @property
    def shots(self) -> int:
        return sum(s.shots for s in self.scenes)

    @property
    def final_seconds(self) -> float:
        return sum(s.final_seconds for s in self.scenes)

    @property
    def generated_seconds(self) -> float:
        return sum(s.generated_seconds for s in self.scenes)

    @property
    def shot_plates(self) -> float:
        return sum(s.shot_plates for s in self.scenes)

    @property
    def total_images(self) -> float:
        return self.assets.images + self.shot_plates

    def _mean_attempts(self) -> float:
        if not self.scenes:
            return 1.0
        return sum(s.attempts_per_shot * s.shots for s in self.scenes) / max(1, self.shots)


def attempts_for(rounds: int, hit_rate: float) -> float:
    """1 delivery attempt, plus the share that comes back in each review round."""
    return 1 + rounds * hit_rate


def plan_scene(scene: SceneBreakdown, config: PlanConfig) -> ScenePlan:
    tier_plan = config.tier(scene.complexity.tier)
    shots = max(1, round(scene.scene.pages * tier_plan.shots_per_page))
    return ScenePlan(
        scene=scene,
        shots=shots,
        seconds_per_shot=tier_plan.seconds_per_shot,
        attempts_per_shot=attempts_for(tier_plan.revision_rounds, config.hit_rate),
        revision_rounds=tier_plan.revision_rounds,
        plates_per_shot=tier_plan.plates_per_shot,
    )


def build_plan(breakdown: Breakdown, config: PlanConfig | None = None) -> Plan:
    config = config or PlanConfig()
    scenes = [plan_scene(sb, config) for sb in breakdown.scenes]
    assets = AssetPlan(
        characters=len(breakdown.characters),
        locations=len(breakdown.locations),
        props=len(breakdown.props),
        options=config.options_per_asset,
        angles_per_character=config.angles_per_character,
        plates_per_location=config.plates_per_location,
        plates_per_prop=config.plates_per_prop,
        revision_multiplier=attempts_for(config.asset_revision_rounds, config.asset_hit_rate),
    )
    return Plan(breakdown=breakdown, scenes=scenes, assets=assets, config=config)

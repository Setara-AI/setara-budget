"""
Costs - money on the plan.

One `CostLine` per thing you actually buy, each carrying its quantity, unit
price, and whether that price is published or projected. Two details that catch
people out are handled here rather than left to the spreadsheet:

  * fal bills a MINIMUM take length (4s on Seedance). A 2-second shot costs the
    same as a 4-second one, so shot lengths are clamped to the model's range
    before anything is multiplied.
  * Seedance 2.5's own quoted per-second figures run ~2.5% above what its
    published token rate produces. That gap gets its own line instead of being
    silently absorbed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import pricing
from .plan import Plan


@dataclass
class CostLine:
    label: str
    detail: str
    quantity: float
    unit: str
    unit_cost: float
    verified: bool = True
    source: str = ""

    @property
    def total(self) -> float:
        return self.quantity * self.unit_cost


@dataclass
class GenerationCosts:
    lines: list[CostLine]
    video_model: pricing.VideoModel
    image_model: pricing.ImageModel
    billable_seconds: float
    images: float

    @property
    def subtotal(self) -> float:
        return sum(line.total for line in self.lines)

    def line(self, label: str) -> CostLine | None:
        for candidate in self.lines:
            if candidate.label == label:
                return candidate
        return None

    @property
    def uses_projected_pricing(self) -> bool:
        return any(not line.verified for line in self.lines)


def billable_seconds(plan: Plan, model: pricing.VideoModel) -> float:
    """Generated seconds, with every shot clamped to what the model will bill."""
    total = 0.0
    for scene in plan.scenes:
        per_shot = model.clamp_seconds(scene.seconds_per_shot)
        total += per_shot * scene.shots * scene.attempts_per_shot
    return total


def compute(plan: Plan, video_model_id: str = pricing.DEFAULT_VIDEO_MODEL,
            image_model_id: str = pricing.DEFAULT_IMAGE_MODEL) -> GenerationCosts:
    video = pricing.video(video_model_id)
    image = pricing.image(image_model_id)

    seconds = billable_seconds(plan, video)
    lines = [
        CostLine(
            label="Reference library",
            detail=(f"{plan.assets.characters} characters x {plan.config.angles_per_character} angles, "
                    f"{plan.assets.locations} locations x {plan.config.plates_per_location}, "
                    f"{plan.assets.props} props x {plan.config.plates_per_prop}, "
                    f"{plan.config.options_per_asset} options each, "
                    f"x{plan.assets.revision_multiplier:.2f} for {plan.config.asset_revision_rounds} "
                    f"approval round(s)"),
            quantity=round(plan.assets.images), unit="images",
            unit_cost=image.cost_per_image, verified=image.verified, source=image.source),
        CostLine(
            label="Shot reference plates",
            detail=(f"{plan.shots} shots, plates per shot by complexity, "
                    f"including revision attempts"),
            quantity=round(plan.shot_plates), unit="images",
            unit_cost=image.cost_per_image, verified=image.verified, source=image.source),
        CostLine(
            label="Video generation",
            detail=(f"{plan.shots} shots at {video.resolution}, "
                    f"{plan.final_seconds:.0f}s delivered, {seconds:.0f}s billed after "
                    f"revisions and the {video.min_seconds}s minimum take"),
            quantity=round(seconds, 1), unit="seconds",
            unit_cost=video.cost_per_second(), verified=video.verified, source=video.source),
    ]

    drift = video.drift()
    if drift > 0:
        lines.append(CostLine(
            label="Provider price drift",
            detail=(f"{video.name} quotes ~${video.quoted_per_second:.4f}/s against "
                    f"${video.cost_per_second():.4f}/s from its published token rate "
                    f"({drift * 100:.1f}% above)"),
            quantity=round(seconds, 1), unit="seconds",
            unit_cost=video.cost_per_second() * drift, verified=True, source=video.source))

    return GenerationCosts(lines=lines, video_model=video, image_model=image,
                           billable_seconds=seconds, images=plan.total_images)


def model_comparison(plan: Plan, image_model_id: str = pricing.DEFAULT_IMAGE_MODEL) -> list[dict]:
    """The same plan priced through every video tier - the 'what if' table."""
    rows = []
    for model_id, model in pricing.VIDEO_MODELS.items():
        costs = compute(plan, model_id, image_model_id)
        video_line = costs.line("Video generation")
        rows.append({
            "id": model_id,
            "model": model.name,
            "resolution": model.resolution,
            "per_second": model.cost_per_second(),
            "billed_seconds": costs.billable_seconds,
            "video_cost": video_line.total if video_line else 0.0,
            "subtotal": costs.subtotal,
            "verified": model.verified,
        })
    return sorted(rows, key=lambda r: r["subtotal"])

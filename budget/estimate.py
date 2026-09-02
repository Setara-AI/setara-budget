"""
Estimate - one number a producer can set aside, and the case for it.

    generation  what the models charge (costs.py)
  + labor       who runs them, for how long (labor.py)
  + tooling     seats, storage, the review platform
  ------------
  = direct cost
  + contingency the bit that stops a revision round eating the margin
  ------------
  = cost to deliver
  + margin      what you actually bid
  ------------
  = BID

Then the same script priced the traditional way, so the two sit side by side.
The traditional baseline is a day-rate model because that is how the other bid
is built: pages per shooting day, a cost per shooting day, and post as a
percentage on top.

Every rate that is a house number rather than a published price is a
PLACEHOLDER - set them before you quote.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import costs as costs_module
from . import labor as labor_module
from . import pricing
from .plan import Plan


@dataclass
class Tooling:
    """Per-week running costs that are neither model spend nor payroll."""

    per_seat_per_week: float = 60.0       # creative + review software seats
    storage_per_week: float = 120.0       # asset storage / delivery
    review_platform_per_week: float = 150.0   # Frame.io-style review seats

    def cost(self, headcount: int, weeks: float) -> float:
        return weeks * (self.per_seat_per_week * headcount
                        + self.storage_per_week + self.review_platform_per_week)


@dataclass
class TraditionalBaseline:
    """The non-AI bid, built the way the other bid is built. PLACEHOLDERS."""

    pages_per_shoot_day: float = 3.0
    cost_per_shoot_day: float = 85_000.0
    post_percentage: float = 0.25
    prep_days: float = 0.0

    def shoot_days(self, pages: float) -> float:
        return max(1.0, pages / self.pages_per_shoot_day)

    def production(self, pages: float) -> float:
        return (self.shoot_days(pages) + self.prep_days) * self.cost_per_shoot_day

    def post(self, pages: float) -> float:
        return self.production(pages) * self.post_percentage

    def total(self, pages: float) -> float:
        return self.production(pages) + self.post(pages)


@dataclass
class Estimate:
    plan: Plan
    generation: costs_module.GenerationCosts
    staffing: labor_module.Staffing
    tooling_cost: float
    contingency_rate: float
    margin_rate: float
    baseline: TraditionalBaseline

    @property
    def generation_cost(self) -> float:
        return self.generation.subtotal

    @property
    def labor_cost(self) -> float:
        return self.staffing.total

    @property
    def direct_cost(self) -> float:
        return self.generation_cost + self.labor_cost + self.tooling_cost

    @property
    def contingency(self) -> float:
        return self.direct_cost * self.contingency_rate

    @property
    def cost_to_deliver(self) -> float:
        return self.direct_cost + self.contingency

    @property
    def margin(self) -> float:
        return self.cost_to_deliver * self.margin_rate

    @property
    def bid(self) -> float:
        return self.cost_to_deliver + self.margin

    # -- the comparison ----------------------------------------------------
    @property
    def pages(self) -> float:
        return self.plan.breakdown.script.pages

    @property
    def traditional_bid(self) -> float:
        return self.baseline.total(self.pages)

    @property
    def delta(self) -> float:
        """Negative means the AI bid comes in under the traditional one."""
        return self.bid - self.traditional_bid

    @property
    def delta_percent(self) -> float:
        if not self.traditional_bid:
            return 0.0
        return self.delta / self.traditional_bid

    @property
    def cost_per_delivered_second(self) -> float:
        seconds = self.plan.final_seconds
        return self.bid / seconds if seconds else 0.0

    @property
    def cost_per_page(self) -> float:
        return self.bid / self.pages if self.pages else 0.0

    @property
    def generation_share(self) -> float:
        """How much of the bid is actually model spend - usually the surprise."""
        return self.generation_cost / self.bid if self.bid else 0.0


def build(plan: Plan, *,
          video_model_id: str = pricing.DEFAULT_VIDEO_MODEL,
          image_model_id: str = pricing.DEFAULT_IMAGE_MODEL,
          weeks: float | None = None,
          team: dict | None = None,
          roles=None,
          tooling: Tooling | None = None,
          contingency_rate: float = 0.15,
          margin_rate: float = 0.20,
          baseline: TraditionalBaseline | None = None) -> Estimate:
    """Either pass `weeks` (solve for headcount) or `team` (solve for schedule)."""
    if (weeks is None) == (team is None):
        raise ValueError("pass exactly one of weeks= (solve headcount) or team= (solve schedule)")

    generation = costs_module.compute(plan, video_model_id, image_model_id)
    work = labor_module.volume(plan)
    staffing = (labor_module.staff_for(weeks, work, roles) if team is None
                else labor_module.schedule_for(team, work, roles))
    tooling = tooling or Tooling()

    return Estimate(
        plan=plan,
        generation=generation,
        staffing=staffing,
        tooling_cost=tooling.cost(staffing.headcount, staffing.weeks),
        contingency_rate=contingency_rate,
        margin_rate=margin_rate,
        baseline=baseline or TraditionalBaseline(),
    )

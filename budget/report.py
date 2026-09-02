"""
Report - the estimate as something you can hand to a producer.

markdown() is the readable version, csv_lines() drops into a budget top sheet,
and payload() is the JSON the UI and any downstream tool consume. All three read
the same Estimate, so they cannot disagree with each other.
"""

from __future__ import annotations

import csv
import io
import json

from . import costs as costs_module
from . import labor as labor_module
from . import pricing
from .estimate import Estimate


def money(value: float) -> str:
    return f"${value:,.0f}" if abs(value) >= 100 else f"${value:,.2f}"


def pct(value: float) -> str:
    """Percentages, with enough precision that a small share doesn't read as zero."""
    scaled = value * 100
    if 0 < abs(scaled) < 1:
        return f"{scaled:.2f}%"
    if 0 < abs(scaled) < 10:
        return f"{scaled:.1f}%"
    return f"{scaled:.0f}%"


def _table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def headline(est: Estimate) -> str:
    script = est.plan.breakdown.script
    direction = "under" if est.delta < 0 else "over"
    return "\n".join([
        f"# {script.title} - AI production estimate",
        "",
        f"## {money(est.bid)}",
        "",
        f"**Set aside {money(est.bid)}** to deliver {est.plan.shots} AI shots "
        f"({est.plan.final_seconds:.0f}s of screen time) across {len(est.plan.scenes)} scenes "
        f"from a {script.pages:.1f}-page script.",
        "",
        f"- **{money(est.cost_per_page)} per script page** · "
        f"{money(est.cost_per_delivered_second)} per delivered second",
        f"- **{pct(abs(est.delta_percent))} {direction}** the traditional bid of "
        f"{money(est.traditional_bid)} ({money(abs(est.delta))} {direction})",
        f"- Model spend is only **{pct(est.generation_share)}** of the bid - "
        f"{money(est.generation_cost)}. The rest is people and time.",
        f"- **{est.staffing.headcount} people over {est.staffing.weeks:g} weeks** "
        f"({est.staffing.ai_headcount} AI seats), scheduled by {est.staffing.driver}.",
    ])


def cost_stack(est: Estimate) -> str:
    rows = [
        ["Generation (models)", money(est.generation_cost), pct(est.generation_cost / est.bid)],
        ["Labor", money(est.labor_cost), pct(est.labor_cost / est.bid)],
        ["Tooling, storage, review", money(est.tooling_cost), pct(est.tooling_cost / est.bid)],
        ["**Direct cost**", f"**{money(est.direct_cost)}**", ""],
        [f"Contingency ({pct(est.contingency_rate)})", money(est.contingency), ""],
        ["**Cost to deliver**", f"**{money(est.cost_to_deliver)}**", ""],
        [f"Margin ({pct(est.margin_rate)})", money(est.margin), ""],
        ["**BID**", f"**{money(est.bid)}**", ""],
    ]
    return "## The stack\n\n" + _table(["Line", "Amount", "Share of bid"], rows)


def generation_detail(est: Estimate) -> str:
    rows = []
    for line in est.generation.lines:
        rows.append([
            line.label,
            f"{line.quantity:,.4g} {line.unit}",
            f"${line.unit_cost:,.4f}",
            money(line.total),
            "published" if line.verified else "**projected**",
        ])
    rows.append(["**Subtotal**", "", "", f"**{money(est.generation.subtotal)}**", ""])
    notes = "\n\n".join(
        f"- _{line.label}_: {line.detail}" for line in est.generation.lines)
    return ("## Generation spend\n\n"
            + _table(["Line", "Quantity", "Unit", "Total", "Price"], rows)
            + "\n\n" + notes)


def model_options(est: Estimate) -> str:
    rows = []
    for row in costs_module.model_comparison(est.plan):
        marker = " ←" if row["id"] == est.generation.video_model.id else ""
        rows.append([
            row["id"] + marker,
            row["resolution"],
            f"${row['per_second']:.4f}",
            f"{row['billed_seconds']:,.0f}s",
            money(row["video_cost"]),
            money(row["subtotal"]),
            "published" if row["verified"] else "**projected**",
        ])
    return ("## The same script at every model tier\n\n"
            + _table(["Model", "Res", "$/sec", "Billed", "Video", "Generation subtotal", "Price"],
                     rows)
            + "\n\n_Generation subtotal only - labor and tooling are unchanged by the tier._")


def staffing_detail(est: Estimate) -> str:
    rows = []
    for seat in est.staffing.seats:
        rows.append([
            seat.role.name,
            "AI" if seat.role.ai else "craft",
            seat.count,
            f"{money(seat.role.weekly_rate)}/wk",
            f"{seat.weeks:g}",
            money(seat.cost),
        ])
    rows.append(["**Total**", "", f"**{est.staffing.headcount}**", "",
                 f"**{est.staffing.person_weeks:g} person-weeks**",
                 f"**{money(est.staffing.total)}**"])
    table = _table(["Role", "Kind", "Count", "Rate", "Weeks", "Cost"], rows)

    loads = labor_module.bottlenecks(est.staffing)
    if loads:
        load_rows = [[
            row["role"], row["unit"], f"{row['required']:,.0f}", f"{row['capacity']:,.0f}",
            pct(row["utilisation"]), "SHORT" if row["short"] else "ok",
        ] for row in loads]
        table += ("\n\n### Load per role\n\n"
                  + _table(["Role", "Unit", "Required", "Capacity", "Utilisation", ""], load_rows))
    return "## Crew\n\n" + table


def scene_detail(est: Estimate) -> str:
    rows = []
    for scene_plan in est.plan.scenes:
        breakdown = scene_plan.scene
        scene = breakdown.scene
        rows.append([
            scene.number,
            f"{scene.int_ext} {scene.location}"[:44],
            scene.time_of_day or "-",
            f"{scene.eighths}/8",
            scene_plan.tier.value,
            breakdown.complexity.score,
            len(breakdown.cast),
            len(breakdown.props),
            scene_plan.shots,
            f"{scene_plan.attempts_per_shot:.1f}x",
            f"{scene_plan.generated_seconds:.0f}s",
        ])
    return ("## Scenes\n\n"
            + _table(["#", "Scene", "Time", "Pages", "Tier", "Score", "Cast", "Props",
                      "Shots", "Attempts", "Billed"], rows))


def complexity_notes(est: Estimate) -> str:
    blocks = []
    for scene_plan in est.plan.scenes:
        breakdown = scene_plan.scene
        drivers = "; ".join(breakdown.complexity.drivers)
        blocks.append(f"- **{breakdown.scene.number}. {breakdown.scene.location}** "
                      f"({scene_plan.tier.value}, {breakdown.complexity.score}): {drivers}")
    return "### Why each scene scored what it did\n\n" + "\n".join(blocks)


def assumptions(est: Estimate) -> str:
    config = est.plan.config
    baseline = est.baseline
    lines = [
        "## Assumptions",
        "",
        "**These are the numbers to argue with.** Everything above is derived from them.",
        "",
        "### Generation",
        f"- Revision model: `attempts = 1 + rounds x hit_rate`, hit rate **{pct(config.hit_rate)}** "
        f"of shots per round; rounds by tier: "
        + ", ".join(f"{tier.value} {plan.revision_rounds}" for tier, plan in config.tiers.items()),
        f"- Shots per page by tier: "
        + ", ".join(f"{tier.value} {plan.shots_per_page:g}" for tier, plan in config.tiers.items()),
        f"- Seconds per shot by tier: "
        + ", ".join(f"{tier.value} {plan.seconds_per_shot:g}s" for tier, plan in config.tiers.items()),
        f"- Reference library: **{config.options_per_asset} options** per asset, "
        f"{config.angles_per_character} angles per character, "
        f"{config.plates_per_location} plates per location, "
        f"{config.plates_per_prop} per prop, "
        f"{config.asset_revision_rounds} approval round(s) at "
        f"{pct(config.asset_hit_rate)} hit rate",
        "",
        "### Money",
        f"- Contingency **{pct(est.contingency_rate)}**, margin **{pct(est.margin_rate)}**",
        f"- Traditional baseline: **{baseline.pages_per_shoot_day:g} pages/shoot day** at "
        f"**{money(baseline.cost_per_shoot_day)}/day**, post at {pct(baseline.post_percentage)} "
        f"→ {baseline.shoot_days(est.pages):.1f} shoot days",
        "- Weekly crew rates are PLACEHOLDERS - replace them with your own before quoting.",
        "",
        "### Script reading",
        "- Props are detected from the screenwriting convention that a prop is CAPITALISED on "
        "first appearance. Review the list; the parser is deliberate but literal.",
        "- Page count follows 55 lines to a page; one page is treated as one minute.",
    ]
    return "\n".join(lines)


def sources(est: Estimate) -> str:
    seen = {}
    for line in est.generation.lines:
        if line.source and line.source not in seen:
            seen[line.source] = line.label
    rows = [[label, f"<{source}>", "published" if source.startswith("http") else "estimated"]
            for source, label in seen.items()]
    return ("## Price sources\n\n"
            + _table(["Line", "Source", "Kind"], rows)
            + f"\n\n_Prices read {pricing.PRICES_READ_ON}. "
            + (f"The default video tier (`{est.generation.video_model.id}`) is PROJECTED: "
               f"{est.generation.video_model.note}_"
               if not est.generation.video_model.verified else "All video pricing published._"))


def markdown(est: Estimate) -> str:
    return "\n\n".join([
        headline(est),
        cost_stack(est),
        generation_detail(est),
        model_options(est),
        staffing_detail(est),
        scene_detail(est),
        complexity_notes(est),
        assumptions(est),
        sources(est),
    ])


def csv_lines(est: Estimate) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Section", "Line", "Quantity", "Unit", "Unit cost", "Total"])
    for line in est.generation.lines:
        writer.writerow(["Generation", line.label, round(line.quantity, 2), line.unit,
                         round(line.unit_cost, 4), round(line.total, 2)])
    for seat in est.staffing.seats:
        writer.writerow(["Labor", seat.role.name, seat.count, f"weeks x {seat.weeks:g}",
                         seat.role.weekly_rate, round(seat.cost, 2)])
    writer.writerow(["Tooling", "Seats, storage, review", "", "", "", round(est.tooling_cost, 2)])
    writer.writerow(["Total", "Direct cost", "", "", "", round(est.direct_cost, 2)])
    writer.writerow(["Total", f"Contingency {pct(est.contingency_rate)}", "", "", "",
                     round(est.contingency, 2)])
    writer.writerow(["Total", f"Margin {pct(est.margin_rate)}", "", "", "", round(est.margin, 2)])
    writer.writerow(["Total", "BID", "", "", "", round(est.bid, 2)])
    writer.writerow(["Comparison", "Traditional bid", "", "", "", round(est.traditional_bid, 2)])
    writer.writerow(["Comparison", "Delta", "", "", "", round(est.delta, 2)])
    return buffer.getvalue()


def payload(est: Estimate) -> dict:
    script = est.plan.breakdown.script
    return {
        "title": script.title,
        "script": {
            "pages": round(script.pages, 2),
            "runtime_minutes": round(script.runtime_minutes, 1),
            "scenes": len(est.plan.scenes),
            "characters": script.characters,
            "locations": script.locations,
            "props": est.plan.breakdown.props,
        },
        "plan": {
            "shots": est.plan.shots,
            "final_seconds": round(est.plan.final_seconds, 1),
            "billed_seconds": round(est.generation.billable_seconds, 1),
            "images": round(est.plan.total_images),
            "tiers": {tier.value: count for tier, count in est.plan.breakdown.by_tier().items()},
        },
        "models": {
            "video": est.generation.video_model.id,
            "video_per_second": round(est.generation.video_model.cost_per_second(), 4),
            "video_verified": est.generation.video_model.verified,
            "image": est.generation.image_model.id,
            "image_per_image": est.generation.image_model.cost_per_image,
        },
        "costs": {
            "generation": round(est.generation_cost, 2),
            "labor": round(est.labor_cost, 2),
            "tooling": round(est.tooling_cost, 2),
            "direct": round(est.direct_cost, 2),
            "contingency": round(est.contingency, 2),
            "cost_to_deliver": round(est.cost_to_deliver, 2),
            "margin": round(est.margin, 2),
            "bid": round(est.bid, 2),
        },
        "comparison": {
            "traditional_bid": round(est.traditional_bid, 2),
            "delta": round(est.delta, 2),
            "delta_percent": round(est.delta_percent, 4),
            "shoot_days": round(est.baseline.shoot_days(est.pages), 1),
        },
        "staffing": {
            "weeks": est.staffing.weeks,
            "headcount": est.staffing.headcount,
            "ai_headcount": est.staffing.ai_headcount,
            "driver": est.staffing.driver,
            "seats": [{"role": s.role.id, "name": s.role.name, "count": s.count,
                       "weekly_rate": s.role.weekly_rate, "cost": round(s.cost, 2)}
                      for s in est.staffing.seats],
            "load": labor_module.bottlenecks(est.staffing),
        },
        "scenes": [{
            "number": sp.scene.scene.number,
            "heading": sp.scene.scene.heading,
            "tier": sp.tier.value,
            "score": sp.scene.complexity.score,
            "drivers": sp.scene.complexity.drivers,
            "cast": sp.scene.cast,
            "props": sp.scene.props,
            "shots": sp.shots,
            "attempts": round(sp.attempts_per_shot, 2),
            "billed_seconds": round(sp.generated_seconds, 1),
        } for sp in est.plan.scenes],
    }


def json_text(est: Estimate) -> str:
    return json.dumps(payload(est), indent=2)

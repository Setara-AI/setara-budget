"""
The budgeting UI.

Five tabs, in the order a bid actually gets built:

  Estimate   script in, rates in, number out
  Breakdown  what the parser found - argue with it before you argue with the money
  Board      who does what, in which week, blocked by what
  Assets     the folder hierarchy and the approval ledger
  Sync       push approved assets to local / Frame.io / Drive

Crew rates and role throughputs are an editable table, not constants, because
they are the biggest lever on the number and they are yours, not ours.
"""

from __future__ import annotations

import os

from . import labor, pricing, report, sync
from .breakdown import Tier
from .estimate import Tooling, TraditionalBaseline
from .plan import DEFAULT_TIER_PLANS, PlanConfig
from .project import Project

ROLE_COLUMNS = ["Role", "Weekly rate", "AI seat", "Work unit", "Per week"]
UNIT_CHOICES = ["", "shot_attempts", "images", "scenes", "pages"]


def gr():
    import gradio

    return gradio


def rows(value) -> list:
    """Normalise whatever Gradio hands back for a Dataframe into a list of lists.

    Gradio 6 returns a pandas DataFrame; older versions return a list of lists,
    and some paths return {"data": [...]}. Truth-testing a DataFrame raises, so
    this has to happen before anything else touches the value.
    """
    if value is None:
        return []
    if hasattr(value, "values") and hasattr(value, "columns"):      # pandas DataFrame
        return value.values.tolist()
    if isinstance(value, dict):
        return list(value.get("data", []))
    return list(value)


def roles_to_rows(roles=None) -> list:
    return [[r.name, r.weekly_rate, "yes" if r.ai else "no", r.unit, r.per_week]
            for r in (roles or labor.DEFAULT_ROLES)]


def rows_to_roles(table) -> list:
    """Turn the edited table back into Roles, keeping ids stable by position."""
    defaults = labor.DEFAULT_ROLES
    built = []
    for index, row in enumerate(rows(table)):
        if not row or not str(row[0]).strip():
            continue
        base = defaults[index] if index < len(defaults) else None
        role_id = base.id if base else f"role_{index}"
        unit = str(row[3] or "").strip()
        built.append(labor.Role(
            id=role_id,
            name=str(row[0]).strip(),
            weekly_rate=float(row[1] or 0),
            unit=unit,
            per_week=float(row[4] or 0) if unit else 0.0,
            ai=str(row[2]).strip().lower() in ("yes", "true", "y", "1"),
        ))
    return built or list(defaults)


def _read_script(text, file) -> tuple:
    text = (text or "").strip()
    if text:
        return text, "Pasted script", ""
    if file:
        path = file if isinstance(file, str) else getattr(file, "name", None)
        if not path:
            return "", "", "Could not read that file."
        if path.lower().endswith(".pdf"):
            return "", "", ("PDF screenplays aren't parsed yet - export to .fountain, "
                            ".fdx or .txt.")
        try:
            from .script import parse_file

            parsed = parse_file(path)
            return "", os.path.splitext(os.path.basename(path))[0], "", parsed
        except Exception as exc:
            return "", "", f"Could not read that file: {exc}"
    return "", "", "Paste a script or upload one first."


def build_project(script_text, script_file, config: PlanConfig, root: str = "") -> Project:
    text = (script_text or "").strip()
    if text:
        return Project.from_text(text, "Pasted script", root=root, config=config)
    path = script_file if isinstance(script_file, str) else getattr(script_file, "name", None)
    return Project.from_script(path, root=root, config=config)


def make_config(options, angles, loc_plates, prop_plates, hit_rate, asset_rounds,
                asset_hit, shots_simple, shots_moderate,
                shots_complex, shots_hero, seconds_per_shot) -> PlanConfig:
    tiers = {tier: plan_for for tier, plan_for in DEFAULT_TIER_PLANS.items()}
    per_page = {Tier.SIMPLE: shots_simple, Tier.MODERATE: shots_moderate,
                Tier.COMPLEX: shots_complex, Tier.HERO: shots_hero}
    rebuilt = {}
    for tier, tier_plan in tiers.items():
        rebuilt[tier] = type(tier_plan)(
            shots_per_page=float(per_page[tier]),
            seconds_per_shot=float(seconds_per_shot),
            revision_rounds=tier_plan.revision_rounds,
            plates_per_shot=tier_plan.plates_per_shot)
    return PlanConfig(
        tiers=rebuilt,
        hit_rate=float(hit_rate),
        asset_hit_rate=float(asset_hit),
        asset_revision_rounds=int(asset_rounds),
        options_per_asset=int(options),
        angles_per_character=int(angles),
        plates_per_location=int(loc_plates),
        plates_per_prop=int(prop_plates),
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def run_estimate(script_text, script_file, video_model, image_model, mode, weeks,
                 team_rows, role_rows, contingency, margin, pages_per_day,
                 day_rate, post_pct, options, angles, loc_plates, prop_plates,
                 hit_rate, asset_rounds, asset_hit,
                 shots_simple, shots_moderate, shots_complex, shots_hero, seconds_per_shot):
    if not (script_text or "").strip() and not script_file:
        return "Paste a screenplay or upload one first.", "", None, None, "", ""
    try:
        config = make_config(options, angles, loc_plates, prop_plates, hit_rate,
                             asset_rounds, asset_hit, shots_simple,
                             shots_moderate, shots_complex, shots_hero, seconds_per_shot)
        project = build_project(script_text, script_file, config)
        roles = rows_to_roles(role_rows)

        kwargs = dict(
            video_model_id=video_model, image_model_id=image_model, roles=roles,
            contingency_rate=float(contingency) / 100,
            margin_rate=float(margin) / 100,
            tooling=Tooling(),
            baseline=TraditionalBaseline(pages_per_shoot_day=float(pages_per_day),
                                         cost_per_shoot_day=float(day_rate),
                                         post_percentage=float(post_pct) / 100))
        if mode == "Solve headcount from a deadline":
            kwargs["weeks"] = float(weeks)
        else:
            team = {}
            for row in rows(team_rows):
                if row and str(row[0]).strip():
                    matched = [r for r in roles if r.name == str(row[0]).strip()]
                    if matched:
                        team[matched[0].id] = int(float(row[1] or 0))
            if not team:
                return ("Set at least one headcount in the team table, or switch to "
                        "solving from a deadline."), "", None, None, "", ""
            kwargs["team"] = team

        est = project.estimate(**kwargs)
    except Exception as exc:
        return f"**Something went wrong:**\n\n```\n{exc}\n```", "", None, None, "", ""

    scratch = os.path.join(os.getcwd(), ".budget_exports")
    os.makedirs(scratch, exist_ok=True)
    stem = os.path.join(scratch, "estimate")
    with open(stem + ".csv", "w") as fh:
        fh.write(report.csv_lines(est))
    with open(stem + ".json", "w") as fh:
        fh.write(report.json_text(est))
    with open(stem + ".md", "w") as fh:
        fh.write(report.markdown(est))

    return (report.headline(est), report.markdown(est), stem + ".csv", stem + ".json",
            _breakdown_markdown(project), _board_markdown(project))


def _breakdown_markdown(project: Project) -> str:
    est = project.current_estimate
    return "\n\n".join([
        f"### {len(project.breakdown.characters)} characters\n"
        + ", ".join(project.breakdown.characters),
        f"### {len(project.breakdown.locations)} locations\n"
        + "\n".join(f"- {name}" for name in project.breakdown.locations),
        f"### {len(project.breakdown.props)} props detected\n"
        + ", ".join(project.breakdown.props),
        report.scene_detail(est),
        report.complexity_notes(est),
    ])


def _board_markdown(project: Project) -> str:
    from . import tasks as tasks_module

    board = project.board(refresh=True)
    if not board:
        return "_No tasks yet._"
    blocks = []
    for week, items in tasks_module.by_week(board).items():
        rows = [f"| {t.status.value} | {t.assignee or '-'} | {t.title} |" for t in items]
        blocks.append(f"### Week {week} ({len(items)} tasks)\n\n"
                      "| Status | Owner | Task |\n| --- | --- | --- |\n" + "\n".join(rows))
    acc = project.accountability(current_week=1)
    header = [f"**{acc['total']} tasks · {acc['done']} done · "
              f"{len(acc['blocked'])} blocked · {len(acc['unassigned'])} unassigned**"]
    over = tasks_module.overruns(board, project.current_estimate.staffing)
    if over:
        header.append(
            f"> **{len(over)} tasks fall outside the {project.current_estimate.staffing.weeks:g}-week "
            f"schedule** - the chain runs to week {acc['latest_week']}. Add people, cut scope, "
            f"or buy more weeks.")
    return "\n\n".join(header + blocks)


def run_scaffold(script_text, script_file, root, seed_shots):
    if not root:
        return "Give the project a folder path first."
    try:
        project = build_project(script_text, script_file, PlanConfig(), root=root)
        library = project.open_library(seed_shots=bool(seed_shots))
    except Exception as exc:
        return f"**Something went wrong:**\n\n```\n{exc}\n```"
    progress = library.progress()
    listing = "\n".join(f"- `{name}`" for name in sorted(os.listdir(root)))
    return "\n\n".join([
        f"## Project scaffolded at `{root}`",
        f"Registered **{progress['assets']} assets** "
        f"({progress['approved']} approved, {progress['outstanding']} outstanding).",
        "### Top level\n" + listing,
        "Every asset gets `02_work/<kind>/<NAME>/r1..rN/` for its option sets. "
        "Approving one copies it to `03_approved/` as `<NAME>_v<round>` - the only "
        "way anything gets in there.",
    ])


def run_sync(root, backend_name, dry_run, token, extra_root):
    if not root or not os.path.exists(root):
        return "Point at an existing project folder first (scaffold one in the Assets tab)."
    from .assets import Library

    try:
        library = Library(root)
        kwargs = {"dry_run": bool(dry_run)}
        if backend_name == "local":
            kwargs = {"root": extra_root or os.path.join(root, "_mirror"),
                      "dry_run": bool(dry_run)}
        elif backend_name == "gdrive":
            kwargs.update({"token": token or "", "root_folder_id": extra_root or "root"})
        else:
            kwargs.update({"token": token or "", "root_folder_id": extra_root or ""})
        backend = sync.get(backend_name, **kwargs)
        result = sync.push_approved(library, backend)
    except Exception as exc:
        return f"**Something went wrong:**\n\n```\n{exc}\n```"

    lines = [f"## {backend_name} · {result.summary()}"]
    if result.uploaded:
        lines.append("### Uploaded\n" + "\n".join(f"- `{r.path}`" for r in result.uploaded))
    if result.errors:
        lines.append("### Failed\n" + "\n".join(f"- {a}: {m}" for a, m in result.errors))
    calls = getattr(backend, "calls", [])
    if calls:
        shown = "\n".join(f"{c[0]} {c[1]}" for c in calls[:20])
        lines.append(f"### Calls {'it would make' if dry_run else 'made'}\n```\n{shown}\n```")
    if backend_name == "frameio":
        lines.append("_Frame.io folder-create and upload shapes are UNVERIFIED - check these "
                     "calls against your account's API reference before turning dry run off._")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------

def build_ui():
    g = gr()
    video_ids = list(pricing.VIDEO_MODELS)
    image_ids = list(pricing.IMAGE_MODELS)

    with g.Blocks(title="AI Production Budget") as demo:
        g.Markdown("# AI Production Budget\n"
                   "Script in, bid out - with the assumptions on the table.")

        with g.Tabs():
            with g.Tab("Estimate"):
                with g.Row():
                    with g.Column(scale=1):
                        script_file = g.File(label="Screenplay (.fountain / .fdx / .txt / .md)",
                                             file_count="single", type="filepath")
                        script_text = g.Textbox(label="…or paste it", lines=8)
                        video_model = g.Dropdown(video_ids, value=pricing.DEFAULT_VIDEO_MODEL,
                                                 label="Video model")
                        image_model = g.Dropdown(image_ids, value=pricing.DEFAULT_IMAGE_MODEL,
                                                 label="Reference-plate model")
                        mode = g.Radio(["Solve headcount from a deadline",
                                        "Solve schedule from a team"],
                                       value="Solve headcount from a deadline", label="Mode")
                        weeks = g.Number(value=8, label="Weeks to deliver", precision=1)
                        team_rows = g.Dataframe(
                            headers=["Role", "Headcount"],
                            value=[[r.name, 1] for r in labor.DEFAULT_ROLES],
                            datatype=["str", "number"], label="Team (used in 'solve schedule')")
                        run = g.Button("Calculate the bid", variant="primary")
                    with g.Column(scale=1):
                        headline = g.Markdown()
                        csv_out = g.File(label="Budget CSV")
                        json_out = g.File(label="Estimate JSON")

                with g.Accordion("Crew rates and throughput (your numbers go here)", open=True):
                    role_rows = g.Dataframe(
                        headers=ROLE_COLUMNS, value=roles_to_rows(),
                        datatype=["str", "number", "str", "str", "number"],
                        label="A blank work unit means the role runs for the whole schedule")

                with g.Accordion("Generation assumptions", open=False):
                    with g.Row():
                        options = g.Slider(1, 20, value=5, step=1, label="Options per asset")
                        angles = g.Slider(1, 8, value=3, step=1, label="Angles per character")
                        loc_plates = g.Slider(1, 6, value=2, step=1, label="Plates per location")
                        prop_plates = g.Slider(1, 6, value=1, step=1, label="Plates per prop")
                    with g.Row():
                        hit_rate = g.Slider(0, 1, value=0.6, step=0.05,
                                            label="Shot revision hit rate")
                        asset_rounds = g.Slider(0, 5, value=2, step=1,
                                                label="Asset approval rounds")
                        asset_hit = g.Slider(0, 1, value=0.4, step=0.05,
                                             label="Asset revision hit rate")
                        seconds_per_shot = g.Slider(2, 30, value=5, step=1,
                                                    label="Seconds per shot")
                    with g.Row():
                        shots_simple = g.Number(value=5, label="Shots/page · simple")
                        shots_moderate = g.Number(value=7, label="Shots/page · moderate")
                        shots_complex = g.Number(value=9, label="Shots/page · complex")
                        shots_hero = g.Number(value=12, label="Shots/page · hero")
                with g.Accordion("Money and the traditional baseline", open=False):
                    with g.Row():
                        contingency = g.Slider(0, 50, value=15, step=1, label="Contingency %")
                        margin = g.Slider(0, 60, value=20, step=1, label="Margin %")
                    with g.Row():
                        pages_per_day = g.Number(value=3.0, label="Traditional: pages/shoot day")
                        day_rate = g.Number(value=85000, label="Traditional: cost per shoot day")
                        post_pct = g.Slider(0, 100, value=25, step=5, label="Traditional: post %")

                full_report = g.Markdown()

            with g.Tab("Breakdown"):
                g.Markdown("What the parser found. Argue with this before the money.")
                breakdown_out = g.Markdown()

            with g.Tab("Board"):
                g.Markdown("Derived from the script - every task traces to a scene or an asset.")
                board_out = g.Markdown()

            with g.Tab("Assets"):
                g.Markdown("Build the folder hierarchy and the approval ledger.")
                with g.Row():
                    root_in = g.Textbox(label="Project folder", placeholder="/Users/you/Shows/night-shift")
                    seed_shots = g.Checkbox(value=False, label="Also register per-shot plates and clips")
                scaffold_btn = g.Button("Scaffold project", variant="primary")
                scaffold_out = g.Markdown()

            with g.Tab("Sync"):
                g.Markdown("Only APPROVED assets are ever pushed.")
                with g.Row():
                    sync_root = g.Textbox(label="Project folder")
                    backend_name = g.Dropdown(["local", "gdrive", "frameio"], value="local",
                                              label="Backend")
                with g.Row():
                    dry_run = g.Checkbox(value=True, label="Dry run (show the calls, send nothing)")
                    token = g.Textbox(label="API token", type="password",
                                      placeholder="FRAMEIO_TOKEN / GOOGLE_DRIVE_TOKEN")
                    extra_root = g.Textbox(label="Destination root (folder id, or a local path)")
                sync_btn = g.Button("Push approved assets", variant="primary")
                sync_out = g.Markdown()

        run.click(
            run_estimate,
            inputs=[script_text, script_file, video_model, image_model, mode, weeks,
                    team_rows, role_rows, contingency, margin, pages_per_day, day_rate,
                    post_pct, options, angles, loc_plates, prop_plates, hit_rate,
                    asset_rounds, asset_hit, shots_simple, shots_moderate,
                    shots_complex, shots_hero, seconds_per_shot],
            outputs=[headline, full_report, csv_out, json_out, breakdown_out, board_out])
        scaffold_btn.click(run_scaffold, inputs=[script_text, script_file, root_in, seed_shots],
                           outputs=scaffold_out)
        sync_btn.click(run_sync, inputs=[sync_root, backend_name, dry_run, token, extra_root],
                       outputs=sync_out)
    return demo


def launch(**kwargs):
    return build_ui().launch(**kwargs)

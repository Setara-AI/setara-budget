"""
The formula, end to end.

    script  ->  runtime  ->  images  ->  keyframes  ->  generations  ->  cost
                                     \\-> revisions -> artist-weeks -> schedule

Every constant below is one of two things, and the difference is marked on each:

  SPEC   a number you gave: 10 generations an image, 8 a keyframe, a 4-second
         average shot, 4 generated minutes per usable minute, 2 revisions a
         scene, 3 finished minutes per artist per week
  OURS   an assumption we had to make to close the maths, with the reasoning
         written next to it

Read `Estimate.provenance()` to get that split back out at runtime, so a
producer can see exactly which parts of a bid are yours and which are ours.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import pricing
from .breakdown import Breakdown
from .runtime import Runtime, time_script
from .variants import VariantPlan, build_variants


@dataclass
class Assumptions:
    # --- SPEC -------------------------------------------------------------
    generations_per_image: int = 8
    """Attempts per image before one is approved - 8:1, and the same figure for
    a reference plate and a keyframe. One ratio is easier to argue about than
    two, and in practice they do not differ."""

    average_shot_seconds: float = 4.0
    """Average shot length. Runtime divided by this is the shot count."""

    generated_minutes_per_usable: float = 3.0
    """Video generated for every minute that survives the cut."""

    revisions_per_scene: int = 1
    """Revision rounds you pay the MODELS for - what you expect to spend in
    credits regenerating the cut."""

    labour_revisions: int = 2
    """Revision rounds you pay the PEOPLE for - how many times you expect to be
    asked to do it again.

    Reliably the larger of the two: a crew gets asked to redo a scene more often
    than anyone pays to regenerate it. Budgeting both off one number meant
    either under-staffing the show or over-buying credits.
    """

    minutes_per_artist_week: float = 3.0
    """Finished runtime one artist delivers in a week."""

    revision_shares: tuple = (1.0, 1.0)
    """How much of the runtime comes back on each revision round, in order.

    Every round is a FULL redo - assume the whole thing has to be made again.
    One round on top of the first pass is two passes over everything, so the
    effort is 2x the runtime.

    Rounds beyond this list reuse the last figure. `revision_multiplier` is what
    the schedule actually uses.

    NOTE the one place this could double-count: `generated_minutes_per_usable`
    (4x) is the all-in generate-to-use ratio, so revision passes are already
    paid for in GENERATION cost. This drives SCHEDULE and LABOUR only.
    """

    def _passes_over(self, rounds: int) -> float:
        """1 for the first pass, plus each revision round's share."""
        if not rounds:
            return 1.0
        shares = list(self.revision_shares) or [0.5]
        total = 1.0
        for index in range(rounds):
            total += shares[index] if index < len(shares) else shares[-1]
        return total

    @property
    def revision_multiplier(self) -> float:
        """How many times the film is made, in CREDITS."""
        return self._passes_over(self.revisions_per_scene)

    @property
    def labour_multiplier(self) -> float:
        """How many times the film is made, in CREW TIME."""
        return self._passes_over(self.labour_revisions)

    keyframes_per_scene: float = 8.0
    """Keyframes per SCENE, not per shot. You do not board every shot; a
    handful of frames covers a scene."""

    pre_revision_rounds: int = 2
    """Approval rounds on the reference pack, on top of the build pass."""

    anchors_per_artist_week: float = 90.0
    """Character sheets and location plates an artist builds in a week.

    Slower than a prop, because these are what everything else has to match:
    several angles, a look that has to hold across the film, and the one people
    argue about in review.
    """

    plates_per_artist_week: float = 160.0
    """Prop and wardrobe plates an artist builds in a week - one image that
    either reads or does not."""

    plate_rework_share: float = 0.5
    """Share of the pack that comes back with notes on each approval round.
    Unlike the video revisions, a plate round does not redo everything - most
    of the pack is signed off first time."""

    plates_reviewed_per_week: float = 600.0
    """How fast a producer and a director get through a batch. This is LATENCY,
    not work: hiring more artists does not move it, and a bigger pack takes
    proportionally longer to read."""

    review_floor_weeks: float = 0.75
    """The fastest an approval round can turn around at all, however small the
    batch - notes on a handful of plates still wait on someone getting to them.

    It only ever binds on SMALL packs: a feature's `plates / reviewed_per_week`
    is already past it, so raising this lengthens a trailer without touching a
    feature.
    """

    image_minimum_weeks: int = 2
    """Reviews take time on any size of pack, so nothing comes in under this."""

    image_maximum_weeks: int = 12
    """A GUIDE, not a clamp: past this the phase reports that it is running
    long. Clamping it stopped the phase responding to the crew, which is the one
    thing it has to do."""

    character_sheet_min_scenes: int = 2
    """Scenes a character has to appear in before a sheet is worth building.
    A one-scene walk-on rides on that scene's wardrobe plate."""

    scenes_per_artist_week: float = 22.0
    """Scenes an artist keyframes in a week, for ONE pass - about four or five a
    day at eight frames each. Calibrated so a feature boards in roughly eight
    weeks at a small crew and a short in two, which is where real shows land."""

    keyframe_revisions: int = 1
    """Revision rounds on keyframes, so every scene is boarded twice. 25 scenes
    at 5 a week over 2 passes is 10 artist-weeks."""

    @property
    def plate_passes(self) -> float:
        """Plate-passes of work: everything once, then the share that returns."""
        share = min(1.0, max(0.0, self.plate_rework_share))
        return 1 + max(0, self.pre_revision_rounds) * share

    def image_phase(self, plates: int, scenes: int, artists: int = 1,
                    anchors: int = 0) -> dict:
        """Every still the show needs, on one bar: the reference plates that
        lock the look, and the keyframes each clip is generated from.

        They were two phases because they are two jobs, but they are the same
        PEOPLE doing the same kind of work back to back, and splitting them made
        the schedule read as though a crew downed tools in between.

        BUILDING is work: images over a throughput, and a bigger crew divides
        it. REVIEWING the plates is latency: a producer and a director reading
        the batch, which no amount of hiring compresses and which takes longer
        on a bigger pack.
        """
        import math

        crew = max(1, artists or 1)
        anchor_count = min(anchors, plates)
        plate_work = (anchor_count / max(self.anchors_per_artist_week, 0.01)
                      + (plates - anchor_count) / max(self.plates_per_artist_week, 0.01)
                      ) * self.plate_passes
        frame_work = (scenes * self.keyframe_passes) / max(self.scenes_per_artist_week, 0.01)
        work = plate_work + frame_work
        build = work / crew
        # a round cannot come back instantly, but half a week is realistic on
        # a handful of plates
        per_round = max(self.review_floor_weeks,
                        plates / max(self.plates_reviewed_per_week, 1))
        review = max(0, self.pre_revision_rounds) * per_round

        # The ceiling used to CLAMP this, and that broke the arithmetic: pinned
        # at eight weeks the phase stopped responding to the crew at all. It is
        # a GUIDE now - the phase reports when it runs past it and the number
        # stays true. The floor stays a real floor: a pack has to be read.
        raw = build + review
        floor = max(1, self.image_minimum_weeks)
        weeks = max(floor, math.ceil(raw - 1e-9)) if (plates or scenes) else 0
        return {"weeks": weeks, "raw": raw, "build": build, "review": review,
                "per_round": per_round, "work": work,
                "plate_work": plate_work, "frame_work": frame_work,
                "over_guide": weeks > self.image_maximum_weeks,
                "floored": raw < floor - 1e-9}

    def image_weeks(self, plates: int, scenes: int, artists: int = 1,
                    anchors: int = 0) -> int:
        return self.image_phase(plates, scenes, artists, anchors)["weeks"]

    @property
    def keyframe_passes(self) -> int:
        """First pass plus each revision round."""
        return 1 + max(0, self.keyframe_revisions)



@dataclass
class Estimate:
    runtime: Runtime
    variants: VariantPlan
    assumptions: Assumptions
    breakdown: Breakdown

    # -- what has to exist -------------------------------------------------
    @property
    def reference_images(self) -> int:
        return self.variants.images

    @property
    def keyframes(self) -> int:
        import math
        scenes = len(self.breakdown.scenes)
        if not scenes:
            return 0
        return max(1, math.ceil(scenes * self.assumptions.keyframes_per_scene))

    @property
    def shots(self) -> int:
        """The SUM of the scenes, not runtime / shot length computed separately.

        Doing both independently left the scene table and the video bill
        disagreeing by a few shots on any long script - and the sum is the truer
        number anyway, because every scene needs at least one shot however short
        it is.
        """
        return sum(self.scene_shots.values()) or (1 if self.runtime.seconds else 0)

    @property
    def scene_shots(self) -> dict:
        """Shots per scene, sized by that scene's share of the runtime."""
        import math

        total = (self.runtime.content_minutes * 60) or 1
        scale = self.runtime.seconds / total     # 1 when content timing was chosen
        out = {}
        for scene in self.runtime.scenes:
            out[scene.number] = max(1, round(
                scene.seconds * scale / self.assumptions.average_shot_seconds))
        return out

    # -- what has to be generated -----------------------------------------
    @property
    def reference_generations(self) -> int:
        """Every PASS, not just the first.

        This used to count one pass and lean on the shooting ratio to cover the
        rest - defensible when a revision redid half the shots, indefensible now
        they are full redos. The schedule already counted those passes; the
        invoice did not.
        """
        return round(self.reference_images * self.assumptions.generations_per_image
                     * self.assumptions.plate_passes)

    @property
    def keyframe_generations(self) -> int:
        return round(self.keyframes * self.assumptions.generations_per_image
                     * self.assumptions.keyframe_passes)

    @property
    def image_generations(self) -> int:
        return self.reference_generations + self.keyframe_generations

    @property
    def generated_seconds(self) -> float:
        return self.runtime.seconds * self.assumptions.generated_minutes_per_usable

    # -- how long it takes -------------------------------------------------
    @property
    def scene_minutes(self) -> dict:
        return {s.number: s.minutes for s in self.runtime.scenes}

    @property
    def effort_minutes(self) -> float:
        """Runtime plus the revision passes the CREW works - the hours, not the
        credits."""
        return self.runtime.minutes * self.assumptions.labour_multiplier

    def phases(self, artists: int = 1) -> list:
        """The three phases, in the order they actually happen.

        Pre production is an estimate off script length - three weeks for a
        short, six for a feature at the baseline crew. A bigger crew compresses
        it down to the approval floor, no further. It is STAFFED by what the
        plates need,
        so like every other phase it bills work, not calendar. Keyframes run
        every
        scene through `keyframe_passes` rounds at `scenes_per_artist_week` a
        head.
        Weeks always round UP: nobody books 1.2 weeks.
        """
        import math

        if artists < 1:
            raise ValueError("need at least one artist")
        scenes = len(self.breakdown.scenes)
        if not scenes:
            return []
        a = self.assumptions
        whole = lambda n: max(1, math.ceil(n - 1e-9))

        delivery_weeks = self.effort_minutes / a.minutes_per_artist_week
        plates = self.reference_images
        anchors = len(self.variants.of("character")) + len(self.variants.of("location"))
        img = a.image_phase(plates, scenes, artists, anchors)
        return [
            # Bills the BUILD, not the calendar: the review weeks are the
            # reviewer's time, not the crew's, so more artists shorten the
            # phase without moving the bid.
            {"id": "images", "label": "Images", "fixed": False,
             "weeks": img["weeks"], "plates": plates, "scenes": scenes,
             "build": img["build"], "review": img["review"],
             "artist_weeks": img["work"],
             "over_guide": img["over_guide"], "floored": img["floored"]},
            {"id": "delivery", "label": "Generate & deliver", "fixed": False,
             "weeks": whole(delivery_weeks / artists),
             "artist_weeks": delivery_weeks},
        ]

    def artist_weeks_with(self, artists: int = 1) -> float:
        """Person-weeks of work across the phases."""
        return sum(p["artist_weeks"] for p in self.phases(artists))

    @property
    def artist_weeks(self) -> float:
        return self.artist_weeks_with(1)

    def weeks_with(self, artists: int) -> int:
        return int(sum(p["weeks"] for p in self.phases(artists)))

    def artists_for(self, weeks: float) -> int | None:
        """Smallest crew that lands inside `weeks`, or None if even an army
        cannot - the fixed pre-production block sets the floor."""
        for artists in range(1, 200):
            if self.weeks_with(artists) <= weeks:
                return artists
        return None

    # -- what it costs -----------------------------------------------------
    def costs(self, video_model_id: str = pricing.DEFAULT_VIDEO_MODEL,
              image_model_id: str = pricing.DEFAULT_IMAGE_MODEL) -> dict:
        video = pricing.video(video_model_id)
        image = pricing.image(image_model_id)
        # Billed off the RUNTIME, not the shot count: a 120-minute film at 4:1
        # over three passes is 1,440 minutes of generation, full stop. The take
        # factor is the one thing shots still contribute - if the model will not
        # bill a clip shorter than four seconds and the average shot is two, the
        # runtime is paid for twice over.
        billable_shot_seconds = video.clamp_seconds(self.assumptions.average_shot_seconds)
        take_factor = billable_shot_seconds / max(self.assumptions.average_shot_seconds, 0.01)
        attempts = self.assumptions.generated_minutes_per_usable
        video_seconds = (self.runtime.seconds * take_factor * attempts
                         * self.assumptions.revision_multiplier)

        reference = self.reference_generations * image.cost_per_image
        keyframes = self.keyframe_generations * image.cost_per_image
        clips = video_seconds * video.cost_per_second()
        return {
            "reference_images": reference,
            "keyframes": keyframes,
            "video": clips,
            "video_seconds_billed": video_seconds,
            "total": reference + keyframes + clips,
            "video_model": video,
            "image_model": image,
        }

    def labor(self, artists: int, weekly_rate: float) -> dict:
        """Labour is `max(work, retained)` - PER PHASE, not across the show.

        Doing it on the totals was the bug behind the bug. One crew number runs
        three phases with completely different appetites: on a feature, pre
        production can keep two people busy while boarding wants eight and
        delivery wants six. Sum first and a phase at 40% cancels a phase at
        139%, and the show reports a healthy-looking 97% while both halves of it
        are wrong. Per phase, the idle and the overrun are both visible - and
        both are paid for, because you do pay people who are waiting and the
        work that overruns still has to be done.
        """
        rows = []
        for phase in self.phases(artists):
            retained = phase["weeks"] * artists
            rows.append({
                **phase,
                "retained": retained,
                "billable": max(phase["artist_weeks"], retained),
                "utilisation": (phase["artist_weeks"] / retained) if retained else 0.0,
                # heads this phase can actually keep busy
                "crew_busy": (phase["artist_weeks"] / phase["weeks"]) if phase["weeks"] else 0.0,
                "idle": max(0.0, retained - phase["artist_weeks"]),
                "short": max(0.0, phase["artist_weeks"] - retained),
            })

        weeks = sum(r["weeks"] for r in rows)
        work = sum(r["artist_weeks"] for r in rows)
        retained = sum(r["retained"] for r in rows)
        billable = sum(r["billable"] for r in rows)
        return {
            "artists": artists,
            "weeks": weeks,
            "phases": rows,
            "artist_weeks": billable,
            "work_weeks": work,
            "retained": retained,
            "utilisation": (work / retained) if retained else 0.0,
            "idle": sum(r["idle"] for r in rows),
            "short": sum(r["short"] for r in rows),
            "cost": billable * weekly_rate,
            "weekly_rate": weekly_rate,
        }

    def busiest_crew(self, limit: int = 80) -> int:
        """The largest crew every phase can still keep busy - past it you are
        paying people to wait through the short phases."""
        best = 1
        for artists in range(1, limit + 1):
            phases = self.phases(artists)
            if not phases:
                break
            if all(p["weeks"] * artists <= p["artist_weeks"] + 1e-9 for p in phases):
                best = artists
        return best

    def total(self, artists: int = 2, weekly_rate: float = 4000.0,
              contingency: float = 0.20, margin: float = 0.0,
              video_model_id: str = pricing.DEFAULT_VIDEO_MODEL,
              image_model_id: str = pricing.DEFAULT_IMAGE_MODEL) -> dict:
        generation = self.costs(video_model_id, image_model_id)
        labor = self.labor(artists, weekly_rate)
        # Crew and generations. Nothing else - there was a tooling line here,
        # built on two rates nobody had researched, and an invented number in a
        # bid is worse than no number.
        direct = generation["total"] + labor["cost"]
        contingency_cost = direct * contingency
        deliver = direct + contingency_cost
        margin_cost = deliver * margin
        return {
            "generation": generation,
            "labor": labor,
            "direct": direct,
            "contingency": contingency_cost,
            "cost_to_deliver": deliver,
            "margin": margin_cost,
            "bid": deliver + margin_cost,
            "weeks": labor["weeks"],
            "runtime_minutes": self.runtime.minutes,
        }

    def provenance(self) -> dict:
        a = self.assumptions
        return {
            "yours": {
                "generations_per_image": a.generations_per_image,
                "average_shot_seconds": a.average_shot_seconds,
                "generated_minutes_per_usable": a.generated_minutes_per_usable,
                "revisions_per_scene": a.revisions_per_scene,
                "labour_revisions": a.labour_revisions,
                "minutes_per_artist_week": a.minutes_per_artist_week,
                "revision_shares": list(a.revision_shares),
                "keyframes_per_scene": a.keyframes_per_scene,
                "pre_revision_rounds": a.pre_revision_rounds,
                "anchors_per_artist_week": a.anchors_per_artist_week,
                "plates_per_artist_week": a.plates_per_artist_week,
                "plate_rework_share": a.plate_rework_share,
                "plates_reviewed_per_week": a.plates_reviewed_per_week,
                "image_minimum_weeks": a.image_minimum_weeks,
                "image_maximum_weeks": a.image_maximum_weeks,
                "scenes_per_artist_week": a.scenes_per_artist_week,
                "keyframe_revisions": a.keyframe_revisions,
            },
            "ours": {
                "character_sheet_min_scenes": a.character_sheet_min_scenes,
                "runtime_method": "content-timed (see runtime.py)",
                "character_looks": "a new look when the time of day turns over",
                "location_plates": "one per location x time-of-day x weather",
            },
        }


def build(breakdown: Breakdown, assumptions: Assumptions | None = None,
          character_looks: dict | None = None) -> Estimate:
    assumptions = assumptions or Assumptions()
    return Estimate(
        runtime=time_script(breakdown.script),
        variants=build_variants(breakdown, character_looks,
                                assumptions.character_sheet_min_scenes),
        assumptions=assumptions,
        breakdown=breakdown,
    )


def explain(estimate: Estimate, artists: int = 2, weekly_rate: float = 4000.0) -> str:
    """The formula with this script's numbers substituted in - the audit trail."""
    a = estimate.assumptions
    totals = estimate.total(artists=artists, weekly_rate=weekly_rate)
    generation = totals["generation"]
    counts = estimate.variants.counts()

    return "\n".join([
        "RUNTIME",
        f"  content timing                       = {estimate.runtime.minutes:.2f} min "
        f"({estimate.runtime.seconds:.0f}s)",
        f"  page rule cross-check                = {estimate.runtime.page_minutes:.2f} min "
        f"({estimate.runtime.disagreement * 100:+.0f}%)",
        "",
        "IMAGES  (one per variant, not one per name)",
        f"  characters {counts['character']:>3}  locations {counts['location']:>3}  "
        f"props {counts['prop']:>3}  wardrobe {counts['wardrobe']:>3}"
        f" = {estimate.reference_images} images",
        f"  x {a.generations_per_image} generations each                 "
        f"= {estimate.reference_generations:,} generations",
        "",
        "KEYFRAMES",
        f"  {estimate.runtime.seconds:.0f}s / {a.average_shot_seconds:g}s average shot        "
        f"= {estimate.shots} shots",
        f"  {len(estimate.breakdown.scenes)} scenes x {a.keyframes_per_scene:g} keyframes"
        f"          = {estimate.keyframes} keyframes",
        f"  x {a.generations_per_image} generations each                  "
        f"= {estimate.keyframe_generations:,} generations",
        "",
        "VIDEO",
        f"  {estimate.shots} shots x "
        f"{generation['video_model'].clamp_seconds(a.average_shot_seconds):g}s billed "
        f"x {a.generated_minutes_per_usable:g} attempts = {generation['video_seconds_billed']:,.0f}s generated",
        "",
        "SCHEDULE",
        f"  {estimate.runtime.minutes:.2f} min x {a.revision_multiplier:g} "
        f"(first pass + {' + '.join(f'{s:g}' for s in list(a.revision_shares)[:a.revisions_per_scene])} "
        f"regenerated) = {estimate.effort_minutes:.2f} min of effort",
        f"  / {a.minutes_per_artist_week:g} min per artist-week              "
        f"= {estimate.effort_minutes / a.minutes_per_artist_week:.2f} artist-weeks",
        f"  {len(estimate.breakdown.scenes)} scenes x {a.keyframe_passes} rounds / "
        f"{a.scenes_per_artist_week:g} a week  "
        f"= {len(estimate.breakdown.scenes) * a.keyframe_passes / a.scenes_per_artist_week:.2f} "
        f"artist-weeks of keyframing",
        f"  across {artists} artists, phased        = "
        + "  ".join(f"{p['label']} {p['weeks']:g}w" for p in estimate.phases(artists)),
        f"  total                                = {totals['weeks']} weeks",
        "",
        "COST",
        f"  reference images                     = ${generation['reference_images']:,.2f}",
        f"  keyframes                            = ${generation['keyframes']:,.2f}",
        f"  video                                = ${generation['video']:,.2f}",
        f"  crew {totals['labor']['artist_weeks']:.2f} artist-weeks x ${weekly_rate:,.0f}    "
        f"= ${totals['labor']['cost']:,.2f}",
        f"  contingency + margin                 = "
        f"${totals['contingency'] + totals['margin']:,.2f}",
        f"  BID                                  = ${totals['bid']:,.2f}",
    ])


# ---------------------------------------------------------------------------
# The roster: teams, and people who are not on for the whole run.
#
# `labor()` above bills one uniform crew at one rate, which is all a top-sheet
# needs. A real roster has two things it cannot express:
#
#   TEAMS      Two artists put on the same shots do not get through twice the
#              work - and they are not the same speed either. So a team
#              contributes ONE rate however many people are in it, and that rate
#              is the producer's to SET (`team_rates`), defaulting to the best
#              single rate in the pod until it is. Adding someone to a team does
#              not raise it on its own; every member is still paid.
#
#   PART RUN   Someone brought on for four weeks of a twenty week show bills
#              four weeks, and carries four twentieths of what a full-run head
#              would carry. Their duty factor scales both.
#
# Both are mirrored from the web app so the two engines cannot drift.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Role:
    """One line of the roster."""

    name: str
    rate: float                       # a week, per head
    count: int = 1
    per_week: float | None = None     # delivered minutes a week, per head
    team: str = ""                    # blank = works alone
    weeks: float | None = None        # None = on for the whole run

    def minutes(self, default_per_week: float) -> float:
        return self.per_week if self.per_week and self.per_week > 0 else default_per_week


def duty_factor(role: Role, project_weeks: float) -> float:
    """How much of the run this role is actually on for, 0..1."""
    if not role.weeks or role.weeks <= 0 or project_weeks <= 0:
        return 1.0
    return min(1.0, role.weeks / project_weeks)


def team_rate(key: str, roles, default_per_week: float, team_rates=None) -> float:
    """What a team delivers in a week.

    The producer's figure if they set one, else the best single rate in the pod -
    the honest reading of "these people are now on the same shots".
    """
    set_to = (team_rates or {}).get(key)
    if set_to and set_to > 0:
        return float(set_to)
    return max((r.minutes(default_per_week) for r in roles
                if (r.team or "").strip() == key and r.count > 0), default=0.0)


def crew_capacity(roles, project_weeks: float, default_per_week: float,
                  team_rates=None) -> float:
    """Delivered minutes a week for the whole crew.

    Solo roles add up head by head. Teams do not: each team contributes its own
    rate once, because its members share the same minutes.
    """
    total = 0.0
    duties: dict[str, float] = {}
    for role in roles:
        if role.count <= 0:
            continue
        key = (role.team or "").strip()
        if key:
            # a pod is on the show for as long as anybody in it is
            duties[key] = max(duties.get(key, 0.0), duty_factor(role, project_weeks))
        else:
            total += (role.minutes(default_per_week)
                      * duty_factor(role, project_weeks) * role.count)
    for key, duty in duties.items():
        total += team_rate(key, roles, default_per_week, team_rates) * duty
    return total


def crew_cost(roles, project_weeks: float) -> list[dict]:
    """Heads x weeks x rate, per role - checkable by hand.

    A role with a shorter engagement bills only the weeks it is on for.
    """
    seats = []
    for role in roles:
        if role.count <= 0:
            continue
        on = min(role.weeks, project_weeks) if role.weeks and role.weeks > 0 else project_weeks
        seats.append({
            "role": role.name,
            "count": role.count,
            "weeks": on,
            "full_run": not (role.weeks and role.weeks > 0),
            "team": (role.team or "").strip(),
            "artist_weeks": on * role.count,
            "cost": on * role.count * role.rate,
        })
    return seats

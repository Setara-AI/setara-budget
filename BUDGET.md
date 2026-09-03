# AI Production Budget

**What it answers:** given a script, what should a producer set aside for the AI scenes,
how does that compare to the traditional bid, how many people does it take, and how long
does it run.

```
python3 budget_app.py                                  # the app (port 7870)
python3 -m unittest discover -s tests -t .             # 192 tests, no API key, no network
```

Everything below `budget/ui.py` is pure Python — **no LLM calls, no network** — so the
numbers are reproducible and every one of them is testable.

## The headline finding

Model spend is almost never the number that matters. On a 28-page test script at the most
expensive tier, generation came to **$3,058 against a $458,377 bid — 0.67%**. The bid is
people and weeks. That is what this tool exists to show: the AI saving is a *labour and
schedule* saving, and pricing it as a per-second model cost will lose you money.

## The formula (`runtime.py` → `variants.py` → `formula.py`)

```
script → runtime → plates → keyframes → generations → cost
                          ↘ revisions → artist-weeks → schedule

**Shots are the sum of the scenes**, not `runtime ÷ shot length` computed
separately — every scene needs at least one shot however short it is, and
deriving the two independently left the scene table and the video bill
disagreeing.
```

Run `budget.formula.explain(est)` to print the whole chain with your script's
numbers substituted in — it is the audit trail for the bid.

**Reading the PDF.** The extractor is self-contained (no library) and rebuilds
lines from GLYPH GEOMETRY, not from operator structure. That matters because
producers batch text differently: Final Draft writes a line per operator, while
Quartz — macOS "Export as PDF", Preview, Pages — writes **one glyph per
`BT`/`ET` block**, each with its own text matrix. Flushing a line at `ET` turns
`SKY'S END` into nine one-character lines and the script reads as empty. So
every run of glyphs is recorded at the device position its matrices put it at
(`Tm × CTM`, tracked through `q`/`Q`/`cm`), runs sharing a baseline become a
line, and the page's median row gap gives the line pitch that decides where the
blank lines go. Fonts with no `/ToUnicode` fall back to their `/Encoding`,
including `/MacRomanEncoding` and `/Differences` — without that, an en dash
arrives as `Ð` and `EXT. JUNGLE – DAY` loses its time of day.

**The title comes off the title page**, not the filename. A screenplay says
what it is called before it says anything else — the reliable signal is the
byline, since whatever sits directly above `Written by` is the title. That
handles the three things which break naive first-line reading: a watermark or
recipient's name above the title (one Hannibal draft opens *Matthew Warter* /
*SURUS* / *Written by John Logan*), letter-spaced title pages that arrive as
`S K Y ' S   E N D`, and front matter that merely looks like a title — dates,
draft marks, the production company. Fountain's `Title:` key wins outright when
present, an all-caps title is cased for reading (`WALL-E` → *Wall-E*, `SKY'S
END` → *Sky's End*), a title that already has case is left alone, and the
filename is the fallback.

**Page count is read, not guessed.** Page boundaries survive extraction as form
feeds, so the page count is the PDF's own and lines-per-page is measured off
this script rather than assumed to be 55. Dividing lines by 55 remains the
fallback for pasted text. Verified exact on five features (126 / 12 / 155 /
116 / 114 pages).

**Runtime.** The one-page-one-minute rule measures paper, not screen time, so it
drifts on formatting. `runtime.py` times the content instead: dialogue at
160 wpm, action at 130 wpm, plus a 2s beat per scene heading. Both methods are
computed and the disagreement is reported — more than 15% apart means the
formatting is odd or a PDF lost its line breaks, and the number needs a look.
`fit_wpm()` tunes both constants against scripts whose real runtime you know.

**Images are variants, not names.** MARA at night and MARA at dawn are two
images. `variants.py` counts one plate per `location × time-of-day × weather`,
one character look per story-day turnover, one per prop. `CONTINUOUS` / `LATER`
inherit the time and the weather of the block they sit in.

**Two ratios do most of the work**, and they are the only levers on the face of
the Plan tab:

| | | |
|---|---|---|
| **Shooting ratio** | `3:1` | minutes generated per usable minute |
| **Generations per image** | `8:1` | attempts per plate *and* per keyframe |

One generations figure covers both — arguing about two was a distinction without
a difference. Revision rounds is the third and last slider.

**There is no Advanced panel.** Everything else — keyframes per scene,
throughput, the review floor, the image-phase guides — is calibration rather
than a decision about a job, so it lives in `FORMULA` / `Assumptions` and ships
in the assumptions export, where a bid can still be defended line by line
without eleven sliders competing with the three that matter.

**The throughput rates are calibrated, not picked.** They were solved against
five real scripts so that the two front phases land where shows actually land —
about eight weeks each on a feature at a small crew, two on a short:

| | | per day |
|---|---|---|
| `anchors_per_artist_week` | 90 | 18 character sheets or location plates |
| `plates_per_artist_week` | 160 | 32 prop or wardrobe plates |
| `scenes_per_artist_week` | 22 | 4–5 scenes boarded, 8 frames each |
| `plates_reviewed_per_week` | 600 | 120 read by the reviewer |
| `review_floor_weeks` | 0.75 | the fastest a round turns however small |

Change any rate and the shape moves with it — no duration is written into the
formula.

**The other multipliers** (yours): a 4-second average shot, 3 finished minutes
per artist-week, 8 keyframes per **scene**.

**Revisions happen three times, at three stages** — and they are separate knobs:

| Stage | Rounds | What a round costs |
|---|---|---|
| Reference pack | `pre_revision_rounds` = 2 | half the pack comes back |
| Keyframes | `keyframe_revisions` = 1 | every scene boarded again |
| Final video — credits | `revisions_per_scene` = 1 | a **full** redo — two passes |
| Final video — crew time | `labour_revisions` = 2 | three passes of hours |

**Wardrobe is per scene.** A character look covers a block of scenes, but
wardrobe has to match shot to shot *inside* a scene, so `variants.py` emits one
`wardrobe` plate per scene on top of the character, location and prop plates.
It costs generations like any other reference image.

**Keyframes are per scene, not per shot.** You do not board every shot. Eight
frames covers a scene, and the number is a lever (`keyframes_per_scene`).

**The schedule is two phases, in order** (`Estimate.phases(artists)`):

| Phase | Length | Scales with crew? |
|---|---|---|
| Images | `max(2, ceil((plates + keyframes work) ÷ crew + review))` | the build, yes; the review, no |
| Generate & deliver | `ceil(effort_minutes ÷ rate ÷ artists)` | yes |

**Two phases, not three.** Plates and keyframes were separate because they are
two jobs — but they are the same *people* doing the same kind of work back to
back, and splitting them made the schedule read as though a crew downed tools in
between. They are one **Images** phase now, on the schedule and in the cost
stack alike.

**Not every plate is the same job.** A character sheet or a location plate is
what everything else has to match — several angles, a look that has to hold
across the film, and the one people argue about in review. A prop or a wardrobe
still is one image that either reads or does not. Slightly different rates, not
wildly.

```
plate work  = (anchors ÷ 90 + props & wardrobe ÷ 160) × (1 + rounds × rework)
frame work  = scenes × (1 + keyframe_rounds)  ÷ scenes_per_artist_week
build       = (plate work + frame work) ÷ artists      ← compresses with crew
review      = rounds × max(0.75 wk, plates ÷ 600)      ← does not
weeks       = max(2, ceil(build + review))
```

**Every phase divides by the crew.** They used to be clamped into a fixed band,
and that clamp was what broke the arithmetic: pinned at its ceiling, a phase
stopped responding to headcount at all. The upper bound is a **guide** now — a
phase says when it is running long, and the number stays true.

**The throughput rates are calibrated, not picked.** They were solved against
five real scripts:

| | | per day |
|---|---|---|
| `plates_per_artist_week` | 140 | 28 plates — prompt, batch, pick, check |
| `scenes_per_artist_week` | 22 | 4–5 scenes boarded, 8 frames each |
| `plates_reviewed_per_week` | 600 | 120 read by the reviewer |
| `review_floor_weeks` | 0.75 | the fastest a round turns however small |

| At 2 artists | Plates / scenes | Images | Build + review |
|---|---|---|---|
| *Arrival* | 543 / 167 | **14 wk** | 11.5 + 1.8 |
| *12 Years a Slave* | 765 / 211 | **18** | 15.1 + 2.5 |
| Sky's End trailer | 75 / 5 | **3** | 0.7 + 1.5 |
| A one-page short | 17 / 5 | **2** | 0.4 + 1.5 |

The **review floor is the lever for short projects**. A feature's
`plates ÷ 600` already outruns it (Arrival's is 0.905), so raising the floor
lengthens a trailer without touching a feature — which is how the trailer went
from two weeks to three while both features stayed put.

It bills the **build**, not the calendar — the review weeks are the reviewer's
time, not the crew's — so the labour line does not move with headcount.

**Character sheets are for recurring cast only.** A character has to appear in
`character_sheet_min_scenes` (2) scenes before a sheet is worth building; a
one-scene walk-on is covered by that scene's wardrobe plate. An explicit
`character_looks` entry always overrides the rule.

Every phase **rounds up** to a whole week — nobody books 1.2 weeks. Because pre
production is a fixed front, `artists_for(weeks)` returns `None` for a deadline
no crew size can meet rather than pretending otherwise.

**The bid is crew plus generations, and contingency on top. Nothing else.**
There was a tooling line — a per-artist software seat and a weekly storage and
review charge — built on two rates nobody had researched. An invented number in
a bid is worse than no number, so it is gone. Crew is exactly
`heads × weeks × rate`: on a 104-week show with two artists at $4,000, exactly
$832,000, and a reader can check it by hand.

**Labour is `max(work, retained)` — per phase, not across the show.**

| | |
|---|---|
| **Work** | the artist-weeks a phase contains |
| **Retained** | that phase's `weeks × heads` — what you carry through it |

Billing the work alone was right that the pile does not grow when you hire — the
film is the film — and wrong that you can hold forty artists for nine weeks and
pay for the five each was busy.

Doing it on the *totals* was the bug behind that bug. **One crew number runs
three phases with completely different appetites.** On *Arrival* at eight
artists:

| Phase | Work | Retained | |
|---|---|---|---|
| Images | 22.9 aw | 56 | keeps **2.9** of 8 busy |
| Generate & deliver | 115.8 aw | 120 | keeps **7.7** of 8 busy |

Summed across the show, a phase at 40% and a phase at 97% average out to
something healthy-looking while one half of it is wrong. Per phase, the idle
time is visible — and it is paid for, because you do pay people who are
waiting.

*Arrival* (197 artist-weeks of work), billed per phase:

| Artists | 2 | 6 | **9** | 20 |
|---|---|---|---|---|
| Calendar | 74 wk | 34 | **26** | 14 |
| Billed | 199 aw | 223 | **234** | 280 |
| Overrunning | 51 aw | 19 | **0** | 0 |
| Idle | 2 aw | 26 | **37** | 83 |
| Bid | $1.03M | $1.13M | **$1.19M** | $1.41M |

Below nine artists the plan does not fit its own bars; above it you are paying
people to wait. Images idles at *every* crew size past three or four, because
a 543-plate pack and 167 scenes of boarding cannot keep more than that busy —
which is the argument for staffing the phases separately rather than with one
number.

`Estimate.provenance()` splits every constant into *yours* and *ours*.

**Credits and crew time carry different numbers of rounds, on purpose.** What
you budget for the models is what you expect to actually spend; what you budget
for the crew is how many times you expect to be *asked* to do it again — and
that is reliably the larger number, because a crew gets asked to redo a scene
more often than anyone pays to regenerate it.

| | Rounds | Multiplier | Drives |
|---|---|---|---|
| `labour_revisions` | 2 | **3×** | the delivery schedule and crew cost |
| `revisions_per_scene` | 1 | **2×** | the video bill |

Only the first is a lever, labelled simply **Revision rounds** — it is what a
producer is deciding when they say "assume two revisions": how many times the
team gets asked to do it again. Credits are held at one round, because you
rarely pay to regenerate every scene as often as you rework it, and quoting the
models for the crew's worst case would inflate the bid. Both appear in the
assumptions export, so the second is stated rather than hidden.

**Revisions are full redos.** Assume the whole thing has to be made again:
`revision_shares = (1.0, 1.0)`, so each round adds a whole pass. A partial round is still a lever (drop the share to 0.5 and it
costs half), and rounds past the list reuse the last share.

**No margin.** A bid is direct cost + 20% contingency. `total()` still takes a
`margin` argument for anyone who wants one, but it defaults to zero.

**Generations are billed for every pass, not just the first.** This used to
count one pass and lean on the shooting ratio to cover the rest — defensible
when a revision redid half the shots, indefensible now they are full redos. Two
rounds of revisions means making the film three times and the models charge
three times.

| Line | | *Arrival* |
|---|---|---|
| Reference plates | `plates × 8 × plate_passes (2.0)` | 8,688 generations |
| Keyframes | `frames × 8 × keyframe_passes (2.0)` | 21,376 generations |
| Video | `runtime × 3:1 × revision_multiplier (2.0)` | 695 min |

**Video is billed off the runtime, not the shot count.** A 120-minute film at
3:1 over two passes is 720 minutes of generation, full stop. Deriving it
from shots made the bill inherit every rounding in the shot allocation and
obscured what was being paid for. The shot count still contributes one thing —
the **take factor**: if the model will not bill a clip shorter than four seconds
and your average shot is two, you pay for the runtime twice over.

That took Arrival's generation line from $31k to **$90k**. It is still under
11% of the bid — labour dominates — but it was understated by two-thirds.

## Pipeline

```
script.py     screenplay → scenes            (Fountain / .fdx / .txt, no model needed)
breakdown.py  scenes → characters, locations, props, complexity score
plan.py       complexity → shots, plates, revision rounds
costs.py      plan → generation cost lines
labor.py      crew rates + throughput → headcount ⇄ schedule
estimate.py   everything → one bid, vs the traditional day-rate baseline
report.py     markdown / CSV / JSON
assets.py     folder hierarchy + option sets + approval ledger
tasks.py      Linear-style assignment, dependency-gated, week by week
sync/         approved assets → local / Frame.io / Google Drive
project.py    all of the above behind one object
```

## Prices — and which ones are real

Read 2026-08-26. Every rate in `pricing.py` carries `verified` and a `source`, and the
report prints the distinction rather than burying it.

| Tier | $/sec | Max take | Price |
| --- | --- | --- | --- |
| Seedance 2.5 · 480p | $0.2149 | 30s | published |
| Seedance 2.5 · 720p reference-to-video | $0.2765 | 30s | published |
| Seedance 2.0 · 720p | $0.3024 | 15s | published |
| Seedance 2.5 · 720p | $0.4622 | 30s | published |
| Seedance 2.0 · 1080p | $0.6804 | 15s | published |
| **Seedance 2.5 · 1080p (default)** | **$1.0400** | 30s | **PROJECTED** |
| Seedance 2.0 · 4K | $1.5552 | 15s | published |

Nano Banana Pro: **$0.134/image** at 1K/2K, $0.24 at 4K (published).

**On the default tier:** fal does not offer Seedance 2.5 above 720p. The 1080p figure
applies 2.5's own published token rate ($0.0214 per 1000 tokens) to 1920×1080. It is a
planning number, not a quote. `seedance-2.0-1080p` is the real, published 1080p lane and
comes out ~35% cheaper; the report shows every tier side by side so the swap is one click.

Video billing is `tokens = h × w × seconds × 24 / 1024`, which is why cost scales with
pixel count. Two traps the code handles so a spreadsheet doesn't have to:

- **Minimum takes.** A 2-second shot bills as 4 seconds. Shot lengths are clamped to the
  model's range before anything is multiplied.
- **Quoted drift.** Seedance 2.5's own per-second figures run ~2.5% above what its token
  rate produces. That gap gets its own line rather than being silently absorbed.

## Exports

Two, from the **Export** menu:

- **One-pager** — client facing, and four blocks only: the title, **what to set
  aside**, three tiles (runtime, delivery, crew size) and **where the money
  goes**. No kicker, no spec line, no unit rates, no footer — each was a second
  voice on a page that only has one thing to say. Deliberately **no weekly rates,
  no artist-weeks, no per-image unit costs and no assumptions** — none of those
  is the client's decision, and a page that answers one question is worth more
  to them than a page that answers twenty. Anyone who wants the workings takes
  the CSV, which still carries all of it.

  It opens a print window; "Save as PDF" in that dialog produces the PDF. A
  print stylesheet rather than a hand-rolled PDF writer, because laying out
  vector text by hand would mean embedding a font and doing our own line
  breaking. With so few blocks each one is set BIG: stripping the page back and
  keeping the old type sizes would have spread 400px of slack across three gaps,
  which reads as a page someone forgot to finish.

  **`@page` margin is 0 on purpose.** The browser prints its own header and
  footer — the URL, `about:blank`, the date, the page number — into the page
  margin, and a document cannot switch them off. With no margin there is
  nowhere for them to render, so the margin lives on the body as `padding`
  instead and the geometry is unchanged. `min-height` is `10.9in` rather than a
  full `11in` for the same class of reason: a body sized to the page exactly
  spills a near-blank second page on any engine that rounds up.

  It is **sized to fill one Letter page**: `min-height` on the body and
  `justify-content:space-between` spreads the slack across the seams instead of
  pooling it in one hole above the footer. Few blocks, so they are set BIG
  rather than spaced further apart — this page padded with air reads as thin.
  Add a block and something else has to give.

- **Line sheet** — one CSV of the lines that ADD UP TO THE BID, and nothing
  else: every crew line at its rate, every generation line at its unit cost,
  direct cost, contingency, total. Columns are Line / Detail / Quantity / Unit
  / Rate / Amount. It used to stack seven sheets (scenes, plates, schedule,
  assumptions, the works) behind banner rows, which is a reference document
  rather than a budget — what a producer wants out of a bidding tool is the
  rows that sum to the number.

## The roster: teams, and people not on for the whole run

Two roster ideas the uniform-crew maths cannot express. Both live in
`crewCapacity` / `crew_capacity` and are mirrored in `budget/formula.py`.

**Teams.** The roster is drawn **grouped**: each team is a box with an editable
name, auto-named `Team A`, `Team B`, … on creation. Solo roles collect under
**Working alone**.

Renaming a team rewrites it across every member. An empty or already-taken name
is refused and the old one put back: blank would silently disband the team and a
duplicate would silently merge two, and neither is what typing in a box means.

There is no separate list of teams — a team exists exactly as long as some role
carries its name, so nothing can fall out of step.

The roster is drawn as team boxes: the name on the left, the pod's **minutes a
week on the upper right**, its headcount and cost underneath. **+ New team** sits
in the section header and starts a team with somebody in it (a team lives only on
its members, so an empty one cannot exist); **+ Add to Team A** inside each box
adds another. A team disappears when its last member is removed.

A team contributes **one rate however many people are in it**, and that rate is
**the producer's to set** — the figure on the upper right of its box.

**Inside a team, members have no personal rate — not shown, not editable.** The
minutes belong to the pod, so printing a figure on every member repeated the
team's number as though each of them delivered it, which is the exact misreading
teams exist to prevent. A delivered-minutes figure appears on a row only when
that row is **working alone**. Consequently the team's own rate is **pinned when
the first member joins** rather than derived from member values nobody can see —
otherwise adding someone could move the pod's output invisibly. Two people on
one stream are not twice as fast, and they are not the same speed either, so the
number is a judgement rather than something to derive. Until it is set it
defaults to the best single rate in the pod.

So **adding someone to a team does not raise its minutes on its own** — you add
them and then say what the pod now delivers. Volume comes from **starting a new
team**. Every member is paid either way.

Solo roles are unchanged — they add up head by head.

The rate lives in `state.teamRates` / `team_rates`, keyed by team name rather
than on a member, so the pod's throughput does not lurch when people come and
go. Renaming a team moves the key; disbanding drops it; clearing the field hands
the pod back to its default.

**The default roster is two Senior AI Artists in teams of their own**, 3 min a
week each — six minutes a week as two independent streams, which is the shape
the schedule actually has.

**Part run.** A role can carry `weeks`; blank means the whole show. Someone on
for four weeks of a twenty week run bills four weeks, and carries four twentieths
of what a full-run head would carry (their *duty factor* scales both).

That makes the schedule circular — how much of the run someone covers depends on
how long the run is, which depends on how much the crew gets through — so
`scheduleForTeam` **solves** it: start with everyone full-time, take the length
that falls out, re-rate the crew against it, go again. Four passes, and it
settles in two whenever nobody is part-time.

Labour is then `heads × weeks × rate` per role, exactly, so the line can be
checked by hand.

## Your own model prices

Every rate in **Models** carries a pencil. Click it and the published price
becomes a box you can type your own into — an operator with a supply deal should
not have to carry a list price into their bid. The override feeds straight
through `perSecond()` / `imageCost()`, so the generation lines, the bubbles and
the bid all move with it, and the readout turns purple to say the number is
yours rather than the vendor's. Clearing the box restores the published price.

Under the pickers sits **What these cost** — images and video at the chosen
models, and the generation total as a share of the bid. The Models card was
three dropdowns and a third of a page of nothing, and the question you are
holding while you sit in it ("what does choosing this cost me?") was only
answerable by scrolling back up to the stack.

Overrides are keyed by **model**, not by row, so switching model shows that
model's own override rather than carrying one across, and they travel with the
production in its snapshot.

## The Assumptions panel

Renamed from "Ratios & revisions" when it stopped being only ratios and
revisions. It carries five dials: **shooting ratio**, **generations per image**,
**revision rounds**, **pacing** and **contingency** — everything that is a
judgement about this job rather than a fact read off the script.

## Runtime: the page rule, measured against 69 films

`budget/samples/page_runtime_corpus.json` holds the evidence — 69 produced films,
each one's **screenplay PDF page count** against its **released runtime**, both
read from source. (Agents were told to return `null` rather than infer one from
the other; inferring would have manufactured the correlation being measured.)

**A page is worth 1.007 minutes on average**, so "one page, one minute" is right
about the middle and wrong about the ends — it lands within 10% on only **61%**
of films and is out by **13 minutes** on average.

The error is not noise. It runs with **length**, in the opposite direction to
what most people expect:

| Pages | Min/page | n | What is happening |
|---|---|---|---|
| 60–90 | **1.336** | 3 | short scripts, long films — the picture is carried visually, and "they drift in silence" is four words and four minutes |
| 90–105 | 1.057 | 12 | |
| 105–120 | 1.017 | 13 | the classic 1:1 zone |
| 120–140 | 0.970 | 23 | |
| 140+ | 0.960 | 18 | long scripts, shorter films — the edit cuts |

A straight line says it more starkly: **runtime = 0.665 × pages + 41**. That
intercept is the tell — roughly **forty minutes of a feature is not on the page
at all**. But an intercept cannot go near short form (it claims 43 minutes for a
three-page script), so `PAGE_MINUTE_CURVE` carries the same shape safely.

Scored against 1:1 on the corpus:

| | 1:1 | curve |
|---|---|---|
| mean error | 13.0 min | **11.4 min** |
| median error | 9.0 min | **7.5 min** |
| within 10% | 61% | **65%** |
| within 20% | 81% | **88%** |
| R² | 0.365 | **0.490** |

**Below 60 pages the curve is pinned to 1.0.** The shortest film measured is 68
pages; under that nothing has been measured, so a trailer gets the plain rule
rather than an extrapolation.

**Known residual, deliberately not modelled:** animation runs **0.85** min/page
against live action's **1.02** — animated scripts are long for their screen time
(Toy Story 126 pages → 81 minutes). Six films from one studio is a hint, not a
coefficient. Genre generally is the rest of the residual: the worst misses are
epics predicted short (Casino, The Godfather) and animation predicted long.

`minutes_from_pages(pages, rate)` takes a flat override, which is what to use
once you have delivered shows of your own to fit against — that beats any
industry curve for your material.

## Pacing — the residual, made adjustable

Divide each film's real runtime by what the length curve predicts and what is
left is not length, it is **how the picture moves**:

    mean 0.998   median 1.009   sd 0.118   range 0.66 – 1.32
    p10 0.836    p25 0.931      p75 1.055  p90 1.128

The ends are exactly who you would expect, which is the check that the number
means what it claims:

| Expansive | | Brisk | |
|---|---|---|---|
| Casino | 1.32 | Toy Story | 0.66 |
| The Godfather | 1.29 | The Social Network | 0.76 |
| Goodfellas | 1.21 | Lady Bird | 0.81 |

Scorsese and Coppola at the top, Sorkin's overlapping dialogue at the bottom. A
director whose cut breathes is a measurable 1.2, so the **Pacing** slider runs
**0.75–1.30**, which spans p5 to p95 of the corpus. It multiplies the runtime and
nothing else — but runtime drives shots, video seconds and the delivery phase, so
it moves nearly every number under it.

The slider says both what a setting is called and **how unusual it is** ("the
corpus norm · slower than 47% of films"), interpolated between the measured
percentiles. Stepping to the nearest boundary reported the boundary rather than
the rank, and made the 1.00 default claim to be slower than only 25% of films.

## Why not the published 1.1 figure

Stephen Follows' 2,520-script study reports 1.1 *pages per minute*. It does not
reproduce here (this corpus says 1.01), and an earlier version of this module
applied it along with a 4.3-minute credits subtraction, which read **107 minutes
against 126** on a feature and took ~$95k off the bid. Two reasons it was wrong
to paste in:

- It measures **released** runtime including the crawl. Credits were never in the
  page count, so subtracting them took the time off twice.
- Page counts are not one convention. This corpus hit it repeatedly: *Whiplash*
  is 114 PDF pages but its own last printed page is 105 (A-pages from a pink
  revision); *Lost in Translation* is 138 PDF pages of which the back half are
  duplicated scan leaves over a 75-page script. Which number you count changes
  the ratio by a third.

## Type

One face (`--font`, Roboto) set on `html` **and** `body` — on `body` alone the
root stayed on the browser default, so anything escaping it rendered in Times.

Small-caps labels — kicks, table heads, tags, section eyebrows — run off two
tokens, `--label` / `--label-sm` with `--label-weight` and `--label-track`.
There were **26 of these across five sizes, three weights and seven tracking
values**, each invented where it was needed. Anything uppercase uses the tokens;
adding a new one means using them too, not picking a size.

The one-pager keeps its own scale on purpose: it is a print document at a fixed
physical size, not a screen.

## The assumptions (this is what you argue with)

Counting work is opinion; the report prints every one of these. Three are sliders
on the Plan tab; the rest are printed but not adjustable.

- **Revisions:** `attempts = 1 + rounds(tier) × hit_rate`. Rounds by tier 1/2/3/4,
  hit rate 60% — the share of shots that come back in a given round.
- **Shots per page** by tier: 5 / 7 / 9 / 12. **Seconds per shot:** 5–6.
- **Complexity** is a weighted score over cast size, prop count, effects language, crowds,
  animals, night, exterior, and action density. Every point awarded is recorded as a
  `driver` string, so a tier can be defended line by line.
- **Reference library:** 5 options per asset, 3 angles per character, 2 plates per
  location, 1 per prop, 2 approval rounds at a 40% hit rate.
- **Crew rates are placeholders.** They are in an editable table in the UI and they are the
  single biggest lever on the number. Replace them before you quote anything.
- **Traditional baseline** is day-rate arithmetic: pages per shoot day × cost per shoot
  day, plus post as a percentage. Also placeholders.

## Props

Props are detected from the screenwriting convention that a prop is CAPITALISED on first
appearance — no model required. Character names, crowd words, effects words, transitions
and slugs are filtered out. It is deliberate but literal: **review the list**. It is shown
on the Breakdown tab before any money is discussed, for exactly that reason.

## Approvals

The shape on disk is the shape of the process:

```
01_script/     02_work/<kind>/<NAME>/r1..rN/opt_01.png…     03_approved/     04_delivery/
```

Two rules the code enforces rather than trusts:

- Nothing enters `03_approved` except through `approve()`, which requires a selected option.
- A rejection **opens the next round** rather than overwriting the last one. Round 1 stays
  on disk, so the revision count in the ledger is a real count you can check the budget
  against — `library.revision_rounds_used()` versus what `plan.py` assumed.

## Board

Tasks are derived, never typed in — every one traces to a scene or an asset, which is what
makes it accountable. A scene cannot generate until the assets it uses are locked, and the
scheduler respects that.

The scheduler does **not** clamp work into the weeks you bought. If the dependency chain
and weekly capacity push past the horizon, tasks keep their true week and `overruns()`
reports it. A schedule that quietly folds three weeks of gated work into the final week
is not a schedule.

## Sync — confidence, stated plainly

| Backend | Status |
| --- | --- |
| `local` | **Verified.** It is `os` and `shutil`; tested against a real filesystem. |
| `gdrive` | Drive v3, implemented from the published API. **Not run** — no Drive credentials on this machine. |
| `frameio` | V4 auth and account discovery implemented from the published reference. Folder-create and upload shapes are **NOT published** in Frame.io's public index — they are written to the shapes V4 uses but are **unverified**. |

Both remote backends **default to `dry_run=True`**, which records the calls it would make
instead of making them. Run it, read `backend.calls`, check them against your account's API
reference, then go live. Frame.io also ships an official Python SDK — if these shapes have
moved, that SDK slots in behind the same `Backend` interface and `push_approved()` will
drive it unchanged.

Only APPROVED assets are ever pushed. Work folders stay local, so a link you send is always
a locked version.

## The web app: two front doors

`web/index.html` is the whole product — one file, no build step, deployed from
`web/` to Vercel at **budget.setara.ai**. Two screens come before the budget:

**The sign-in gate.** Username and password, not email. Supabase identifies
users by email address, so the username is mapped to `<name>@users.setara.ai`
before it is sent; a client types `acmefilms` and never sees an address, and
nothing is ever emailed. There is no self-service reset — you reset it in the
Supabase dashboard, which for a handful of clients keeps you in control of who
has access. Accounts are created by hand: **Authentication → Users → Add user**,
with **Auto Confirm User** ticked (no mailbox exists to confirm from).

Signed out, the app is not merely hidden — row-level security means the database
refuses the request too. If the Supabase CDN is blocked the app still runs, just
without sync, rather than showing a blank page.

The gate is **visible in the markup**, so signed out it is the thing that paints
rather than the thing that wins a race. A returning visitor is spared the
opposite flash by a parse-time script that recognises Supabase's stored session
key — a paint decision only, never trusted: the token is still verified over the
network and an expired one puts the gate straight back up.

`supabase/schema.sql` holds the tables, the trigger and every RLS policy. It is
idempotent, so it can be run against the live project safely. Admins (rows in
`public.admins`) may **read** every production; write policies stay owner-only,
so oversight can never quietly alter somebody's bid.

**The landing screen.** Every session opens here — signing in is the start of a
job, and the job starts with a screenplay, so the app never reopens on the
budget it happened to close on. The active production at sign-in is a fresh
blank, and that blank lives only in memory: `cloudSave` refuses to write a
production with no script, so signing in and looking around cannot litter the
account with empty rows.

Saved work stays one click away — the picker in the header, and chips under the
drop target listing the six most recent productions. The sample is there too,
so the tool can be shown to someone who has no screenplay on them.

Both screens are full-bleed film: twelve stills in `web/stills/`, cross-faded
two layers at a time so only two frames are ever decoded at once, shuffled per
visit, and held on a hidden tab. Every rule that dresses the app for film is
scoped to `body.gated` or `.gate`, so the moment a screenplay lands the app is
exactly the app again.

## Not built yet

- PDF screenplay parsing (Fountain, .fdx, .txt and .md work).
- The Linear-style board is derived and scheduled but has no write-back — marking a task
  done in the UI, webhooks, notifications.
- Actually *generating* the assets. This tool prices and schedules the work and holds the
  approvals; the generation loops live next door in `studio/`, and wiring the two together
  (approve here → generate there → back into the ledger) is the obvious next step.

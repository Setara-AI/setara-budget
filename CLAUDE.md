# This folder holds two apps

1. **Studio** — AI image QC for a film pipeline (`studio_app.py`, port 7860). Documented below.
2. **AI Production Budget** — script → bid, crew and schedule (`budget_app.py`, port 7870).
   See **BUDGET.md**. Pure Python, no LLM calls; `budget/pricing.py` is the model price
   registry and every rate there carries `verified` + `source`.

Both are verified with `python3 -m unittest discover -s tests -t .` (299 tests, no API key).

---

# Studio — AI image QC for a film pipeline

A Python/Gradio studio of tools that check (and in some cases fix) AI-generated film
frames against quality, continuity, and rights criteria. Vision checks run on
Google **Gemini** (`gemini-3-flash-preview`); image regeneration uses **Nano Banana
Pro** (`gemini-3-pro-image-preview`). Everything launches as one tabbed app.

## Run it

```
pip3 install -r requirements.txt          # core deps (Gemini tabs)
pip3 install -r requirements_face.txt     # only needed for the Character tab
python3 studio_app.py                     # opens a local web UI with tabs
python3 -m studio cinematic               # …or run one tool on its own
python3 -m unittest discover -s tests -t . # the test suite (no API key needed)
```

Most tabs need a Google Gemini API key (paste once in the UI; shared across tabs;
`GEMINI_API_KEY` prefills it). Tabs that regenerate images need **billing enabled**
for Nano Banana Pro.

## Layout

Everything lives in the `studio/` package; `studio_app.py` is just the entry point.

```
studio/
  config.py     model ids + output conventions (2K, PNG) — change them HERE
  gemini.py     the ONLY module that calls Google: judge() and render()
  criteria.py   Criterion + the one structured-output schema + score()/flags()
  loop.py       the check → fix → re-check agent loop, with loop hygiene built in
  report.py     markdown tables and verdict lines
  ui.py         shared Gradio widgets (key box, image inputs, sliders, gallery)
  app.py        the tabbed app
  tools/        one module per tab
tests/          unittest suite driven by fake verdicts — no API, no network
```

Every tool module exposes the same surface, so the app (and a future API) can treat
them uniformly: `TITLE`, `TAGLINE`, a `check()`, a pure `compute*()`, a
`report_markdown()`, a `run()` handler, and `build_tab()`.

## Tabs and the modules behind them

- **Trailer** — `studio/tools/trailer.py`: the pipeline's front end. Takes a
  **screenplay** + **reference images**; Gemini devises a trailer **concept**
  (logline, tone, visual style, ordered shotlist) as a Pydantic `TrailerConcept`,
  then Nano Banana Pro renders one cinematic still per shot — each rendered **fresh
  from the references**. `compute_shotlist` normalises/orders/caps the shotlist.
  The output gallery is the trailer as a still stringout. Stills are paid; the
  concept can be previewed on its own. (Nano Banana Pro)
- **Animation** — `studio/tools/animation.py`: match an image to a reference
  animation style without losing its framing. Three passes — style, then framing
  rescue (only if restyling actually moved the framing), then reconcile — each with
  its own base image. The standalone style comparison (old `style_match_app.py`)
  is folded in as `check_style` + `score_style`. (Nano Banana Pro)
- **Character** — `studio/tools/character.py`: local face recognition (InsightFace /
  ArcFace) to find whether an enrolled actor's face appears in a still. No API key;
  needs `requirements_face.txt`; downloads ~300 MB of models on first run.
- **Cinematic** — `studio/tools/cinematic.py`: **checker only** (no regeneration).
  Strict verdict on whether an image looks like a real cinematic film still. Shallow
  depth of field + photorealism are must-pass; high bar (`PASS_THRESHOLD = 0.85`).
  Lighting is judged as natural/dimensional, not "dramatic" (overcast passes).
- **Consistency** — `studio/tools/continuity.py`: one check across set, wardrobe,
  props, lighting and colour grade vs a reference; targeted Nano Banana Pro fix for
  only the drifted aspects, locking the people and framing. Up to 3 tries.
- **Clearance** — `studio/tools/clearance.py`: **checker only**. Flags possible
  celebrity / public-figure likeness, copyrighted characters, brand logos, and
  recognizable IP for rights review. Screening aid, not legal clearance.

## Conventions (please follow when extending)

- **One schema.** Every checker returns `studio.criteria.Verdict` — a list of
  `CriterionResult` plus a confidence and a summary. Don't add a per-tool schema;
  add a `Criterion` list and a prompt via `criteria.build_prompt`.
- **One place calls Google.** Use `gemini.judge()` for checks and `gemini.render()`
  for image generation. Nothing else imports `google.genai`.
- **Pure decision functions.** `criteria.score()` (criticals + a pass ratio) and
  `criteria.flags()` (confidence vs a sensitivity) do the deciding. Each tool wraps
  the one it needs (`compute_score`, `compute`, `compute_flags`) so it stays testable
  with fake verdicts.
- **Loop hygiene is enforced by `studio.loop`, not by each tool.** `run_loop` takes a
  base image and a `fix(base, failing_ids)` callback: a retry can only ever re-render
  from the base, never from the previous generation (stacking compounds artifacts).
  Two things follow, and `run_loop` handles both: failures **accumulate** across
  retries (a retry starts from the base again, so it must be told about everything
  that has failed so far), and the loop returns the **best** attempt rather than the
  last — sound only because the attempts are independent renders of one base.
- Image gen uses `image_config=types.ImageConfig(image_size="2K")` (via
  `config.IMAGE_SIZE`); all gallery / image outputs use `format="png"` (lossless).
- Gradio is imported lazily (`studio.ui.gr()`), so the logic and its tests import
  without a UI toolkit — and so an API can reuse the tools untouched.
- **Verify every change** with `python3 -m py_compile <files>` plus
  `python3 -m unittest discover -s tests -t .` (80 tests, fake verdicts, no live API).
  Add tests alongside — `tests/fakes.py` has the verdict/image builders.

## Caveats

- Nano Banana Pro is paid (~$0.13 / image at 2K) and needs billing enabled.
- Editing photos of **real, identifiable people** can be refused by Nano Banana
  (identity/deepfake restrictions); face-swap is blocked. Fixes are most reliable on
  AI-generated or non-identifiable subjects.
- The Character tab's InsightFace models are licensed for **non-commercial** use;
  commercial use needs a license (or use a commercial face API).
- Gradio 6 takes `css` at `launch()`, not on `Blocks()` — use `studio.app.launch()`.

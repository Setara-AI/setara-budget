# Handoff — continuing this project in Claude Code

Read this together with `CLAUDE.md` (which documents each module). This file captures **where the
project is and where it's going** — the context that was in the build conversation, not just the files.

## The product (combined vision)

A film-production pipeline that turns a **screenplay → cinematic still images → an image stringout on a
timeline**, with an automated **quality-control layer** that checks and refines every generated still.

It's two halves merging:
- **Generation pipeline** (a co-founder's spec): parse screenplay → clarify missing visuals → enriched
  screenplay → continuity tags → production Bible → character sheets → shotlist → generate stills with
  Nano Banana Pro → assemble stringout. (First milestone = stills, not video.)
- **QC layer** (this repo): Gemini-based checkers that score each still and re-render until it passes.

## Where we are now

- **Working today:** a Gradio "studio" of QC tools — `studio_app.py` on top of the `studio/` package
  (`studio/tools/{trailer,animation,character,cinematic,continuity,clearance}.py`). Verified with
  py_compile, an 80-test unittest suite (`python3 -m unittest discover -s tests -t .`, fake verdicts,
  no API needed) and a live launch. See `CLAUDE.md` for the layout and what each tool does.
- **Refactored (2026-08-26):** the flat one-file-per-tool scripts were folded into a package with a
  shared core — one Gemini client (`studio/gemini.py`), one checker schema and scoring rule
  (`studio/criteria.py`), one agent loop (`studio/loop.py`), shared markdown and Gradio widgets. The
  loop-degradation fix below shipped as part of it.
- **Gradio is the current front end.** It was the right call for prototyping the logic, but it's the
  styling bottleneck. The plan is to move off it onto a real, designed front end.

## What's next (priority order)

1. **Wrap the tool logic in a small API (FastAPI).** The check/fix functions are already decoupled from
   the Gradio UI, so this is mostly thin wrappers — one endpoint per tool (`/cinematic`, `/continuity`,
   `/clearance`, `/character`, `/animation`). This is the bridge a web front end needs.
2. **Design the front end in Claude Design** using `claude-design-prompt.md` (already written —
   Krea-referenced, covers the full pipeline + the QC badges). Then use developer handoff → Claude Code.
3. **Build the front end** (React + TypeScript + Tailwind + shadcn/ui) from the Claude Design handoff,
   using the **`frontend-design` skill** (in `frontend-design/SKILL.md`; copy it to
   `~/.claude/skills/frontend-design/` to activate it for Claude Code). Wire it to the FastAPI
   endpoints. Then retire Gradio.

## Pending fixes / known issues

- ~~**Loop degradation:** Animation and Consistency re-render each retry on top of the *previous*
  generation.~~ **Fixed.** `studio/loop.py` owns the rule now: `run_loop(base, fix=fix(base, failing))`
  can only re-render from the base, failures accumulate across retries, and the best attempt wins
  rather than the last. Animation was restructured around it (style pass → framing rescue → reconcile,
  each with its own base) instead of chaining three generations deep.
- Nano Banana Pro is paid (~$0.13/image at 2K) and needs billing enabled.
- Editing photos of real, identifiable people can be refused (identity/deepfake limits); reliable on
  AI-generated / non-identifiable subjects. Face-swap is blocked.
- The Character tab's InsightFace models are **non-commercial** license.

## Conventions

- Each tool: a Gemini **checker** returning the shared `studio.criteria.Verdict` + a pure, testable
  `compute_*` decision function. Fix tools use `studio.loop.run_loop` (check → fix → re-check).
- Only `studio/gemini.py` talks to Google; only `studio/config.py` names models.
- Models: `gemini-3-flash-preview` for checks; `gemini-3-pro-image-preview` (Nano Banana Pro) for image
  gen with `image_config=ImageConfig(image_size="2K")`; image outputs use `format="png"` (lossless).
- **Verify every change** with `python3 -m py_compile <files>` plus
  `python3 -m unittest discover -s tests -t .` (fake verdicts, no live API needed).

## First moves in Claude Code

```
cd ~/Desktop/"CLAUDE TESTS"
claude
```

Then a good first message:
> "Read CLAUDE.md and HANDOFF.md. Then scaffold a FastAPI app (api.py) that exposes each tool's run
> function as an endpoint, reusing the existing logic unchanged. Keep Gradio working in the meantime."

(The tools import without Gradio — `studio.ui.gr()` is lazy — so the API can import
`studio.tools.*` directly and call `check()` / `run_pipeline()` / `run_full()` with no UI in the way.)

After that: design in Claude Design with `claude-design-prompt.md`, then build the front end with the
`frontend-design` skill against the API.

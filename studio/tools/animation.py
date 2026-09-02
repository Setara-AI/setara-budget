"""
Animation - match an image to a reference animation style, without losing its framing.

Two things must be true when this tool is done:
  STYLE   - the image is rendered in the ART STYLE of the reference
  FRAMING - it still has the composition of the image you put in

Those pull against each other: restyling drifts the framing, reframing drifts
the style. The tool therefore runs in three passes:

  1. STYLE     re-render the ORIGINAL in the reference style, re-check, retry.
  2. FRAMING   only if the styled result drifted: reframe it back, re-check,
               retry. Every retry starts from the same styled image.
  3. RECONCILE only if either axis is still off: re-render from the ORIGINAL
               again, this time also naming the framing that drifted, and keep
               whichever candidate scores best on both axes.

LOOP HYGIENE: no pass ever stacks a fix on the previous fix. Each pass has one
base image and every retry re-renders from it (see studio.loop). This replaces
the older style->framing->reconcile chain, where each phase built on the last
and the third fix was three generations deep from the source.

The style checker doubles as a standalone comparison (check_style + score_style)
- that was style_match_app.py, folded in here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import gemini, report, ui
from ..criteria import Criterion, Verdict, build_prompt, by_id, score
from ..loop import run_loop

TITLE = "Animation"
TAGLINE = ("Fix an image's style to match a reference, then its framing - then a final check "
           "that both pass. Uses Nano Banana Pro (paid).")

PASS_THRESHOLD = 0.70
MAX_RETRIES = 3
RECONCILE_ROUNDS = 2

STYLE_DIMENSIONS = [
    Criterion(
        id="render", name="Rendering technique", critical=True,
        description="The fundamental medium and look: 2D vs 3D, hand-drawn vs CGI vs painted vs "
                    "pixel art. This is the biggest style differentiator.",
        fix="the rendering technique (2D vs 3D, hand-drawn vs CGI vs painted)",
    ),
    Criterion(
        id="lines", name="Linework & outlines",
        description="Presence, weight and style of outlines: bold black lines, thin lines, or "
                    "none at all.",
        fix="the linework and outlines",
    ),
    Criterion(
        id="shading", name="Shading style",
        description="How light and shadow are rendered: flat cel-shading vs smooth 3D gradients "
                    "vs painterly blending.",
        fix="the shading style",
    ),
    Criterion(
        id="color", name="Color palette",
        description="Overall color feel: saturation, warmth, contrast and range.",
        fix="the color palette",
    ),
    Criterion(
        id="design", name="Character design & proportions",
        description="Stylization of shapes and proportions: eye size, roundness, and how "
                    "realistic vs exaggerated the forms are.",
        fix="the character design and proportions",
    ),
    Criterion(
        id="aesthetic", name="Overall aesthetic",
        description="The general 'style family' it belongs to and its overall finish and mood.",
        fix="the overall aesthetic and finish",
    ),
]

FRAMING_DIMENSIONS = [
    Criterion(
        id="shot", name="Shot type & camera angle", critical=True,
        description="Same kind of shot and camera angle (e.g. close-up vs wide, eye-level vs "
                    "high/low angle).",
        fix="the shot type and camera angle",
    ),
    Criterion(
        id="placement", name="Subject placement", critical=True,
        description="The main subject sits in the same position within the frame "
                    "(left/center/right, high/low).",
        fix="the subject's placement in the frame",
    ),
    Criterion(
        id="scale", name="Subject scale / zoom",
        description="The subject fills roughly the same proportion of the frame.",
        fix="the subject's scale within the frame",
    ),
    Criterion(
        id="crop", name="Crop & edges",
        description="The same elements are included or cut off at the frame edges.",
        fix="the crop and what sits at the frame edges",
    ),
]


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def style_prompt(dimensions=STYLE_DIMENSIONS) -> str:
    return build_prompt(
        intro=[
            "You compare the ANIMATION STYLE of two images. Judge ONLY visual style, never "
            "subject matter or content.",
            "The FIRST image is the REFERENCE. The SECOND image is the one to CHECK.",
        ],
        criteria=dimensions,
        decision="the CHECK image clearly shares this with the REFERENCE",
        context="the reference image's animation style.",
    )


def framing_prompt(dimensions=FRAMING_DIMENSIONS) -> str:
    return build_prompt(
        intro=[
            "You compare the FRAMING and COMPOSITION of two images. Judge ONLY framing - camera "
            "angle, shot type, subject placement, scale and crop - and IGNORE art style, colors "
            "and content.",
            "The FIRST image is the ORIGINAL (the target framing). The SECOND image is the one "
            "to CHECK.",
        ],
        criteria=dimensions,
        decision="the CHECK image matches the ORIGINAL's framing on that dimension",
        context="the original image's framing.",
    )


def check_style(reference_image, check_image, api_key: str,
                dimensions=STYLE_DIMENSIONS) -> Verdict:
    return gemini.judge(
        [style_prompt(dimensions),
         "--- REFERENCE IMAGE ---", reference_image,
         "--- IMAGE TO CHECK ---", check_image],
        Verdict, api_key)


def check_framing(original_image, check_image, api_key: str,
                  dimensions=FRAMING_DIMENSIONS) -> Verdict:
    return gemini.judge(
        [framing_prompt(dimensions),
         "--- ORIGINAL IMAGE (target framing) ---", original_image,
         "--- IMAGE TO CHECK ---", check_image],
        Verdict, api_key)


def score_style(verdict: Verdict, threshold: float = PASS_THRESHOLD,
                dimensions=STYLE_DIMENSIONS):
    return score(dimensions, verdict, threshold)


def score_framing(verdict: Verdict, threshold: float = PASS_THRESHOLD,
                  dimensions=FRAMING_DIMENSIONS):
    return score(dimensions, verdict, threshold)


# ---------------------------------------------------------------------------
# Fixes
# ---------------------------------------------------------------------------

def _names(dimensions, ids) -> str:
    known = by_id(dimensions)
    return "; ".join(known[i].fix for i in ids if i in known)


def restyle_prompt(style_ids=(), framing_ids=()) -> str:
    lines = [
        "You are restyling an image. The FIRST image is the SOURCE to redraw. The SECOND image "
        "is the STYLE REFERENCE.",
        "Redraw the SOURCE image so it keeps EXACTLY the same composition, framing, characters, "
        "poses and scene, but rendered entirely in the ART STYLE of the STYLE REFERENCE - its "
        "rendering technique (e.g. 2D vs 3D), linework, shading, color palette and overall look.",
        "Do NOT change what is depicted or its layout. Only change the art style.",
    ]
    off = _names(STYLE_DIMENSIONS, style_ids)
    if off:
        lines.append(f"Earlier attempts got these wrong - pay particular attention to them: {off}.")
    drifted = _names(FRAMING_DIMENSIONS, framing_ids)
    if drifted:
        lines.append("Earlier attempts also drifted the framing. Hold these EXACTLY as they are "
                     f"in the SOURCE image: {drifted}.")
    lines.append("Output the restyled image.")
    return "\n".join(lines)


def reframe_prompt(framing_ids=()) -> str:
    lines = [
        "You are adjusting an image's framing. The FIRST image is the one to ADJUST. The SECOND "
        "image shows the TARGET FRAMING.",
        "Change ONLY the composition and framing of the FIRST image - its camera angle, shot "
        "type, subject placement, scale and crop - so they match the SECOND image's framing. "
        "KEEP the FIRST image's art style, characters, colors and content unchanged.",
    ]
    off = _names(FRAMING_DIMENSIONS, framing_ids)
    if off:
        lines.append(f"These are the ones that are off: {off}.")
    lines.append("Output the reframed image.")
    return "\n".join(lines)


def restyle(source_image, reference_image, api_key, style_ids=(), framing_ids=()):
    return gemini.render(
        [restyle_prompt(style_ids, framing_ids), source_image, reference_image], api_key)


def reframe(source_image, original_image, api_key, framing_ids=()):
    return gemini.render(
        [reframe_prompt(framing_ids), source_image, original_image], api_key)


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """An image graded on BOTH axes - what we compare when choosing what to ship."""

    label: str
    image: Any
    style: Any        # Score
    framing: Any      # Score

    @property
    def ok(self) -> bool:
        return self.style.ok and self.framing.ok

    @property
    def passed(self) -> int:
        return self.style.passed + self.framing.passed

    @property
    def total(self) -> int:
        return self.style.total + self.framing.total


def _best(candidates: list[Candidate]) -> Candidate:
    """Both-axes pass wins; then most criteria passed; ties keep the earlier one."""
    best = candidates[0]
    for c in candidates[1:]:
        if (c.ok, c.passed) > (best.ok, best.passed):
            best = c
    return best


def run_full(reference_image, original_image, api_key, max_retries=MAX_RETRIES,
             threshold=PASS_THRESHOLD, reconcile_rounds=RECONCILE_ROUNDS,
             style_check_fn=None, framing_check_fn=None, restyle_fn=None, reframe_fn=None):
    """Style pass, framing pass, then reconcile. Every fn is injectable for tests.

    style_check_fn(image) -> Verdict          framing_check_fn(image) -> Verdict
    restyle_fn(source, style_ids, framing_ids) -> image
    reframe_fn(source, framing_ids) -> image
    """
    style_check_fn = style_check_fn or (lambda img: check_style(reference_image, img, api_key))
    framing_check_fn = framing_check_fn or (lambda img: check_framing(original_image, img, api_key))
    restyle_fn = restyle_fn or (
        lambda src, s_ids, f_ids: restyle(src, reference_image, api_key, s_ids, f_ids))
    reframe_fn = reframe_fn or (
        lambda src, f_ids: reframe(src, original_image, api_key, f_ids))

    grade_style = lambda v: score_style(v, threshold)
    grade_framing = lambda v: score_framing(v, threshold)

    # -- Pass 1: style. Every retry re-renders from the ORIGINAL.
    style_pass = run_loop(
        original_image, check=style_check_fn, grade=grade_style,
        fix=lambda base, failing: restyle_fn(base, failing, ()),
        max_retries=max_retries, phase="Style")

    styled = style_pass.best
    candidates = [Candidate("After style pass", styled.image, styled.score,
                            grade_framing(framing_check_fn(styled.image)))]

    # -- Pass 2: framing rescue, only if restyling actually moved the framing.
    framing_pass = None
    if not candidates[-1].framing.ok and style_pass.used:
        framing_pass = run_loop(
            styled.image, check=framing_check_fn, grade=grade_framing,
            fix=lambda base, failing: reframe_fn(base, failing),
            max_retries=max_retries, phase="Framing")
        framed = framing_pass.best
        candidates.append(Candidate("After framing pass", framed.image,
                                    grade_style(style_check_fn(framed.image)), framed.score))

    # -- Pass 3: reconcile. Back to the ORIGINAL, now naming what drifted on both axes.
    reconciled = []
    rounds = 0
    while not _best(candidates).ok and rounds < reconcile_rounds:
        rounds += 1
        latest = candidates[-1]
        image = restyle_fn(original_image, latest.style.failing, latest.framing.failing)
        candidate = Candidate(f"Reconcile {rounds}", image,
                              grade_style(style_check_fn(image)),
                              grade_framing(framing_check_fn(image)))
        candidates.append(candidate)
        reconciled.append(candidate)

    return {
        "best": _best(candidates),
        "candidates": candidates,
        "style_pass": style_pass,
        "framing_pass": framing_pass,
        "reconcile": reconciled,
        "threshold": threshold,
    }


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

def _pass_table(loop_result) -> str:
    return report.table(
        ["Step", "Verdict", "Matching"],
        [[a.label, "MATCH" if a.ok else "no", a.score.tally()] for a in loop_result.attempts])


def report_markdown(res) -> str:
    best = res["best"]
    verdict = ("YES" if best.ok
               else "NOT FULLY (raise retries or lower strictness)")
    head = [f"## Final result - both style & framing pass: {verdict}", "",
            f"- **Shipping:** {best.label} - style {best.style.tally()}, "
            f"framing {best.framing.tally()}",
            f"- **{report.outcome(res['style_pass'].ok, res['style_pass'].used, 'Style')}**"]
    if res["framing_pass"] is not None:
        head.append(f"- **{report.outcome(res['framing_pass'].ok, res['framing_pass'].used, 'Framing')}**")
    else:
        head.append("- **Framing: never drifted (no reframing needed)**")
    if res["reconcile"]:
        head.append(f"- **Reconcile rounds:** {len(res['reconcile'])}")

    blocks = ["\n".join(head),
              "### Pass 1 - Style",
              _pass_table(res["style_pass"])]
    if res["framing_pass"] is not None:
        blocks += ["### Pass 2 - Framing", _pass_table(res["framing_pass"])]
    blocks += ["### Candidates (graded on both axes)",
               report.table(["Candidate", "Style", "Framing", "Both"],
                            [[c.label, c.style.tally(), c.framing.tally(),
                              "pass" if c.ok else "no"] for c in res["candidates"]])]
    return report.join(*blocks)


def run(reference_image, original_image, api_key, threshold, max_retries):
    if reference_image is None or original_image is None:
        return None, "Please add both a **style reference** and an **image to fix**."
    key, err = ui.key_or_error(api_key)
    if err:
        return None, err
    try:
        res = run_full(reference_image, original_image, key,
                       max_retries=int(max_retries), threshold=float(threshold))
    except Exception as e:
        return None, report.error_block(e)

    items = ui.attempt_gallery(res["style_pass"].attempts)
    if res["framing_pass"] is not None:
        items += ui.attempt_gallery(res["framing_pass"].attempts)
    items += [(c.image, f"{c.label} - style {c.style.tally()}, framing {c.framing.tally()}")
              for c in res["reconcile"]]
    return items, report_markdown(res)


def build_tab(api_key):
    gr = ui.gr()
    with gr.Row():
        with gr.Column():
            reference = ui.image_input("1) Style reference (target look)")
            source = ui.image_input("2) Image to fix (also defines framing)")
            threshold = ui.strictness(PASS_THRESHOLD)
            tries = ui.retries(MAX_RETRIES, label="Max regenerations per pass")
            button = gr.Button("Check & fix (style, then framing)", variant="primary")
        with gr.Column():
            attempts = ui.gallery("Attempts (style pass, framing pass, reconcile)")
            out = gr.Markdown()
    button.click(run, inputs=[reference, source, api_key, threshold, tries],
                 outputs=[attempts, out])

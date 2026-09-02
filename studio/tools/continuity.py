"""
Consistency - continuity check + targeted fix.

Two images in: a REFERENCE (the canonical look of the scene) and an image to
CHECK. In ONE pass Gemini judges whether the candidate is continuity-consistent
across set, wardrobe, props, lighting and color grade - ignoring the camera
framing and the subject's pose, which are allowed to differ between shots.

If anything drifted, Nano Banana Pro re-renders it to match the reference,
changing ONLY the drifted aspects and locking the people and framing.

LOOP HYGIENE: every retry re-renders from the ORIGINAL check image, never from
the previous attempt, and is told about every aspect that has failed so far
(see studio.loop). This used to stack fix on fix, which compounded artifacts.
"""

from __future__ import annotations

from .. import gemini, report, ui
from ..criteria import Criterion, Verdict, build_prompt, by_id, score
from ..loop import run_loop

TITLE = "Consistency"
TAGLINE = ("Check set, wardrobe, props, lighting and color grade against a reference all at "
           "once, and re-render whatever drifted to match - keeping the people and framing "
           "locked. Nano Banana Pro (paid).")

PASS_THRESHOLD = 0.70
MAX_RETRIES = 3

ASPECTS = [
    Criterion(
        id="set", name="Set / location", critical=True,
        description="Set / location: the same environment - architecture, layout, walls, doors, "
                    "windows, furniture, set dressing, materials, fixtures and background.",
        fix="the SET / environment (location, architecture, layout, furniture, set dressing, "
            "materials, fixtures and background)",
    ),
    Criterion(
        id="wardrobe", name="Wardrobe", critical=True,
        description="Wardrobe / costume: the characters wear the same garments, colors, "
                    "patterns, accessories and footwear.",
        fix="the WARDROBE / costume on the people (garments, colors, patterns, accessories, "
            "footwear)",
    ),
    Criterion(
        id="props", name="Props",
        description="Props: the same key objects are present and look the same (appearance, "
                    "condition).",
        fix="the PROPS / objects (presence, appearance and condition of the key props)",
    ),
    Criterion(
        id="lighting", name="Lighting",
        description="Lighting: the same key-light direction, hard/soft quality, contrast, color "
                    "temperature and mood.",
        fix="the LIGHTING (key-light direction, hard/soft quality, contrast, color temperature "
            "and mood)",
    ),
    Criterion(
        id="color", name="Color grade",
        description="Color grade: the same palette, contrast, black levels, saturation, white "
                    "balance and overall look/LUT.",
        fix="the COLOR GRADE (palette, contrast, saturation, white balance and overall look)",
    ),
]


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------

def prompt(aspects=ASPECTS) -> str:
    return build_prompt(
        intro=[
            "You check whether a film still is CONTINUITY-CONSISTENT with a reference frame from "
            "the same scene. Judge ONLY the continuity aspects listed below. IGNORE the camera "
            "framing and the subject's exact pose/action - those are allowed to differ between "
            "shots.",
            "The FIRST image is the REFERENCE. The SECOND image is the one to CHECK.",
        ],
        criteria=aspects,
        decision="the CHECK image matches the REFERENCE on that aspect",
        context="the reference scene.",
    )


def check(reference_image, check_image, api_key: str, aspects=ASPECTS) -> Verdict:
    return gemini.judge(
        [prompt(aspects),
         "--- REFERENCE ---", reference_image,
         "--- IMAGE TO CHECK ---", check_image],
        Verdict, api_key)


def compute(verdict: Verdict, threshold: float = PASS_THRESHOLD, aspects=ASPECTS):
    """Pure decision function: both critical aspects plus enough of the rest."""
    return score(aspects, verdict, threshold)


# ---------------------------------------------------------------------------
# Fix - change only the drifted aspects, lock people + framing
# ---------------------------------------------------------------------------

def build_fix_prompt(failing_ids, aspects=ASPECTS) -> str:
    known = by_id(aspects)
    items = "; ".join(known[i].fix for i in failing_ids if i in known) or "the drifted aspects"
    return (
        "You are making a film still continuity-consistent with a reference, by changing ONLY "
        "specific aspects while LOCKING the people and the framing.\n"
        "The FIRST image is the shot to adjust. The SECOND image is the reference.\n"
        "\n"
        "KEEP EXACTLY AS-IS in the FIRST image: the people's faces and identity, their pose and "
        "body position, and the framing/composition (camera angle, shot size, crop, subject "
        "placement and scale, aspect ratio). Do NOT move, re-pose, or re-compose them.\n"
        "\n"
        f"CHANGE ONLY the following to match the SECOND image (the reference): {items}.\n"
        "If an aspect is not listed above, leave it exactly as it is in the FIRST image.\n"
        "\n"
        "Output the same people, the same pose and the same framing, with those aspects now "
        "matching the reference."
    )


def fix(check_image, reference_image, failing_ids, api_key, aspects=ASPECTS):
    return gemini.render(
        [build_fix_prompt(failing_ids, aspects), check_image, reference_image], api_key)


# ---------------------------------------------------------------------------
# Loop
# ---------------------------------------------------------------------------

def run_pipeline(reference_image, check_image, api_key, threshold=PASS_THRESHOLD,
                 max_retries=MAX_RETRIES, check_fn=None, fix_fn=None):
    """check_fn(image) and fix_fn(base_image, failing_ids) are injectable for tests.

    fix_fn receives the ORIGINAL check image every time - see studio.loop.
    """
    check_fn = check_fn or (lambda img: check(reference_image, img, api_key))
    fix_fn = fix_fn or (lambda img, failing: fix(img, reference_image, failing, api_key))
    return run_loop(check_image, check=check_fn,
                    grade=lambda v: compute(v, threshold),
                    fix=fix_fn, max_retries=max_retries, phase="Continuity")


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

def report_markdown(result, threshold: float = PASS_THRESHOLD, aspects=ASPECTS) -> str:
    best, sc = result.best, result.score
    header = ("## Verdict: CONTINUITY CONSISTENT" if result.ok
              else "## Verdict: STILL INCONSISTENT")
    lines = [f"- **{report.outcome(result.ok, result.used, 'Continuity')}**",
             f"- **Aspects passing across attempts:** {report.progress(result.attempts)}"]
    if result.used and best is not result.attempts[-1]:
        lines.append(f"- **Kept:** {best.label} (the best of the attempts)")
    table = report.criteria_table(aspects, best.verdict, ["Aspect", "Verdict", "Note"],
                                 lambda c, r: report.verdict_row(c, r, yes="match", no="drifted",
                                                                 critical_suffix=" (must-match)"))
    return report.join(header, "\n".join(lines),
                       report.score_line(sc, best.verdict, noun="aspects"), table,
                       f"**Summary:** {best.verdict.summary}")


def run(reference_image, check_image, api_key, threshold, max_retries):
    if reference_image is None or check_image is None:
        return None, "Please add both a **reference** image and an **image to fix**."
    key, err = ui.key_or_error(api_key)
    if err:
        return None, err
    try:
        result = run_pipeline(reference_image, check_image, key,
                              threshold=float(threshold), max_retries=int(max_retries))
    except Exception as e:
        return None, report.error_block(e)
    return ui.attempt_gallery(result.attempts), report_markdown(result, float(threshold))


def build_tab(api_key):
    gr = ui.gr()
    with gr.Row():
        with gr.Column():
            reference = ui.image_input("Reference (canonical look of the scene)")
            source = ui.image_input("Image to fix")
            threshold = ui.strictness(PASS_THRESHOLD,
                                      "Strictness (fraction of aspects that must match)")
            tries = ui.retries(MAX_RETRIES)
            button = gr.Button("Check & fix continuity", variant="primary")
        with gr.Column():
            attempts = ui.gallery("Attempts (original then fixes)")
            out = gr.Markdown()
    button.click(run, inputs=[reference, source, api_key, threshold, tries],
                 outputs=[attempts, out])

"""
Cinematic - checker only (no regeneration).

Judges, in one pass, whether an image looks like a real CINEMATIC film still -
not a flat snapshot, and not AI-generated - and gives a strict yes/no with a
per-trait breakdown. It never modifies the image.

The bar is deliberately high: shallow depth of field and photorealism are
must-pass, and at least PASS_THRESHOLD of all traits must pass too (0.85 over 8
traits => both criticals plus at least 7 of 8).

Lighting is judged for being natural and dimensional, NOT for being dramatic:
soft / overcast light is perfectly cinematic; only dead-flat light fails.
"""

from __future__ import annotations

from .. import gemini, report, ui
from ..criteria import Criterion, Verdict, build_prompt, score

TITLE = "Cinematic"
TAGLINE = ("Tells you whether an image looks like a real, cinematic film still (not flat, not "
           "AI-looking), with a high bar. Verdict only - it does not change the image.")

PASS_THRESHOLD = 0.85

TRAITS = [
    Criterion(
        id="dof", name="Shallow depth of field / focus falloff", critical=True,
        description="A clear sharp focal subject with a softly blurred background (lens bokeh, "
                    "focus falloff) - NOT everything-equally-sharp deep focus.",
    ),
    Criterion(
        id="photoreal", name="Photoreal, no 'AI' look", critical=True,
        description="Real film-photographic micro-texture and natural detail (skin, fabric, "
                    "frost). None of the plastic, over-smooth or uniform 'AI' look, and no "
                    "artifacts (warped hands, garbled text, melted edges).",
    ),
    Criterion(
        id="depth", name="Atmospheric depth",
        description="Distant elements lose contrast and gain haze so the planes separate; the "
                    "scene does not look flat or pasted-together (e.g. far mountains should not "
                    "be as crisp as the foreground).",
    ),
    Criterion(
        id="grade", name="Filmic contrast & color grade",
        description="Intentional contrast, controlled blacks and a cohesive palette - not flat, "
                    "gray, undirected color.",
    ),
    Criterion(
        id="lighting", name="Natural, dimensional lighting",
        description="The light is believable and gives the scene modeling and depth. It may be "
                    "soft / overcast OR directional - overcast is perfectly fine - it only fails "
                    "if it is dead-flat and characterless. Shadows/highlights are consistent.",
    ),
    Criterion(
        id="lens", name="Cinematic lens character",
        description="Gentle vignetting, natural bokeh, and subtle bloom/halation or flare only "
                    "where a real light source exists; not a flat, characterless render.",
    ),
    Criterion(
        id="grain", name="Natural grain & texture",
        description="Natural film grain and analog texture rather than clinical digital "
                    "smoothness or an even 'overlay' of particles.",
    ),
    Criterion(
        id="composition", name="Believable composition & elements",
        description="Coherent background and elements with intentional framing; not rigid "
                    "AI-centered symmetry, and not uniform pasted-on particles (e.g. evenly "
                    "spaced, identical snowflakes).",
    ),
]


def prompt(traits=TRAITS) -> str:
    return build_prompt(
        intro=[
            "You judge whether an image looks like a REAL CINEMATIC FILM STILL - a believable "
            "frame from a movie - as opposed to a flat phone snapshot or an obviously "
            "AI-generated image. Hold a HIGH bar: only a genuinely cinematic, photoreal frame "
            "should pass.",
            "Judge lighting for being natural and dimensional, NOT for being dramatic: soft or "
            "overcast light is perfectly cinematic; only dead-flat, characterless light fails.",
        ],
        criteria=traits,
        decision="the image clearly satisfies this trait",
    )


def check(image, api_key: str, traits=TRAITS) -> Verdict:
    return gemini.judge([prompt(traits), image], Verdict, api_key)


def compute_score(verdict: Verdict, traits=TRAITS, threshold: float = PASS_THRESHOLD):
    """Pure decision function: both criticals plus enough of the rest."""
    return score(traits, verdict, threshold)


def report_markdown(verdict: Verdict, traits=TRAITS, threshold: float = PASS_THRESHOLD) -> str:
    sc = compute_score(verdict, traits, threshold)
    header = "## Verdict: CINEMATIC & REAL" if sc.ok else "## Verdict: NOT CINEMATIC / NOT REAL"
    table = report.criteria_table(traits, verdict, ["Trait", "Verdict", "Why"],
                                  report.verdict_row)
    return report.join(header, report.score_line(sc, verdict, noun="traits"), table,
                       f"**Read:** {verdict.summary}")


def run(image, api_key, threshold):
    if image is None:
        return "Please drop in an image first."
    key, err = ui.key_or_error(api_key)
    if err:
        return err
    try:
        verdict = check(image, key)
    except Exception as e:
        return report.error_block(e)
    return report_markdown(verdict, TRAITS, float(threshold))


def build_tab(api_key):
    gr = ui.gr()
    with gr.Row():
        with gr.Column():
            image = ui.image_input("Image to check")
            threshold = ui.strictness(PASS_THRESHOLD, "Bar (fraction of traits that must pass)")
            button = gr.Button("Check", variant="primary")
        with gr.Column():
            out = gr.Markdown()
    button.click(run, inputs=[image, api_key, threshold], outputs=out)

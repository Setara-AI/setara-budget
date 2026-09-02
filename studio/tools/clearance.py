"""
Clearance - rights/likeness & IP screener (checker only).

Screens an image and FLAGS anything that could need clearance, across four
categories: celebrity / public-figure likeness, copyrighted character, brand
logo, recognizable IP. It never modifies the image and makes NO legal
determination - it surfaces risks for a person (or a legal team) to review.

Unlike the quality checkers, a "passed" criterion here is bad news: the
condition being judged is "this category appears in the image". A flag counts
only when the model is at least `sensitivity` confident, so the slider trades
false alarms against misses.

LIMIT: Gemini reliably spots copyrighted characters and brand logos and will
flag a resemblance to a real public figure, but its policies often stop it
naming a specific person. For authoritative celebrity identification, AWS
Rekognition's RecognizeCelebrities is the purpose-built tool.
"""

from __future__ import annotations

from .. import gemini, report, ui
from ..criteria import Criterion, Verdict, build_prompt, flags

TITLE = "Clearance"
TAGLINE = ("Flags possible celebrity likenesses, copyrighted characters, brand logos and "
           "recognizable IP for rights review. Screening aid only - not legal clearance.")

DEFAULT_SENSITIVITY = 50   # minimum confidence (0-100) for a flag to count

CATEGORIES = [
    Criterion(
        id="celebrity", name="Celebrity / public-figure likeness",
        description="The image appears to depict a real, recognizable public figure or celebrity "
                    "(actor, musician, athlete, politician, influencer). Flag the resemblance as "
                    "a likeness-rights risk. Name the person only if you are confident; "
                    "otherwise just say it strongly resembles a well-known public figure.",
    ),
    Criterion(
        id="character", name="Copyrighted character",
        description="A recognizable character from a film, TV show, game, comic or animation "
                    "(e.g. a known superhero, mascot, or franchise character).",
    ),
    Criterion(
        id="logo", name="Brand logo / trademark",
        description="A visible brand logo, trademark, branded product, team jersey, or packaging.",
    ),
    Criterion(
        id="ip", name="Recognizable IP / artwork",
        description="Recognizable copyrighted artwork, an iconic film still or scene, an album "
                    "cover, or another recognizable protected design.",
    ),
]

DISCLAIMER = ("_Screening aid only - not legal clearance. A person should review every flag, "
              "and a clean result does not guarantee the image is cleared._")


def prompt(categories=CATEGORIES) -> str:
    return build_prompt(
        intro=[
            "You are a rights-clearance screener for a film production. Your job is to FLAG any "
            "content in this image that could raise likeness or intellectual-property concerns "
            "and need clearance before use. You are NOT making a legal determination - you are "
            "surfacing potential risks for a human to review.",
        ],
        criteria=categories,
        decision="the category appears present in the image",
        per_result_confidence=True,
        conservative=False,
        closing=["When in doubt, flag it for review - a human makes the call."],
    )


def check(image, api_key: str, categories=CATEGORIES) -> Verdict:
    return gemini.judge([prompt(categories), image], Verdict, api_key)


def compute_flags(verdict: Verdict, categories=CATEGORIES,
                  min_confidence: int = DEFAULT_SENSITIVITY):
    """Pure decision function: flagged AND confident enough to be worth a look."""
    return flags(categories, verdict, min_confidence)


def _row(category: Criterion, result):
    if result is None:
        return [category.name, "-", "-", "no result returned"]
    return [category.name, "FLAG" if result.passed else "clear",
            str(result.confidence), report.cell(result.note)]


def report_markdown(verdict: Verdict, categories=CATEGORIES,
                    min_confidence: int = DEFAULT_SENSITIVITY) -> str:
    found = compute_flags(verdict, categories, min_confidence)
    header = "## NEEDS RIGHTS REVIEW" if found.needs_review else "## No flags (above sensitivity)"
    info = (f"**Flagged categories:** {', '.join(found.flagged)}" if found.needs_review
            else "Nothing flagged above the current sensitivity.")

    def row(category, result):
        cells = _row(category, result)
        if result is not None and result.passed and result.confidence < min_confidence:
            cells[1] = "(low-conf)"     # the model flagged it, the sensitivity discounted it
        return cells

    table = report.criteria_table(categories, verdict,
                                  ["Category", "Flag", "Conf.", "Note"], row)
    return report.join(header, info, table, f"**Summary:** {verdict.summary}", DISCLAIMER)


def run(image, api_key, sensitivity):
    if image is None:
        return "Please drop in an image first."
    key, err = ui.key_or_error(api_key)
    if err:
        return err
    try:
        verdict = check(image, key)
    except Exception as e:
        return report.error_block(e)
    return report_markdown(verdict, CATEGORIES, int(sensitivity))


def build_tab(api_key):
    gr = ui.gr()
    with gr.Row():
        with gr.Column():
            image = ui.image_input("Image to screen")
            sensitivity = gr.Slider(
                0, 100, value=DEFAULT_SENSITIVITY, step=5,
                label="Sensitivity (min confidence to flag; lower = more flags)")
            button = gr.Button("Screen for IP / likeness", variant="primary")
        with gr.Column():
            out = gr.Markdown()
    button.click(run, inputs=[image, api_key, sensitivity], outputs=out)

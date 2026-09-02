"""
Trailer - screenplay + references -> concept -> generated stills.

Stage 1 CONCEPT  Gemini reads the screenplay AND looks at the reference images,
                 then devises a teaser concept - logline, tone, visual style,
                 music vibe - broken into an ordered shotlist (hook -> build ->
                 climax -> tag), returned as structured JSON.
Stage 2 STILLS   Nano Banana Pro renders one cinematic 2K still per shot.

LOOP HYGIENE: every shot renders FRESH from the reference images. No shot is
ever conditioned on the previously generated still, so nothing compounds down
the cut.

The ordered gallery IS the trailer as a still stringout. Stage 2 is paid
(~$0.13/still), so the concept can be previewed on its own first.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .. import config, gemini, report, ui

TITLE = "Trailer"
TAGLINE = ("Upload a **screenplay** and **reference images**; Gemini devises a trailer "
           "**concept** and shotlist, then Nano Banana Pro renders a still for each shot (in cut "
           "order). Generating stills is paid (~$0.13 each) - untick to preview the concept first.")

CONCEPT_MODEL = config.CHECK_MODEL
CONCEPT_TEMPERATURE = 0.4       # a little creative latitude for concepting

DEFAULT_SHOTS = 8
MIN_SHOTS = 3
MAX_SHOTS = 16

# The trailer arc the concept should hit (guidance for the model; not enforced).
BEATS = ["hook", "setup", "build", "turn", "climax", "tag"]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class Shot(BaseModel):
    order: int = Field(description="1-based position of this shot in the trailer cut.")
    beat: str = Field(description="Which trailer beat it serves (hook, setup, build, turn, "
                                  "climax, tag).")
    title: str = Field(description="A short 2-4 word label for the shot.")
    description: str = Field(description="A SELF-CONTAINED visual prompt for ONE cinematic film "
                                         "still - who/where/action/framing/lighting - renderable "
                                         "on its own. No on-screen text in the image itself.")
    duration_sec: float = Field(description="Seconds on screen (~0.5-3s; the final beat may be "
                                            "longer).")
    title_card: str = Field(default="", description="Punchy on-screen trailer text for this "
                                                    "beat, or empty string if none.")


class TrailerConcept(BaseModel):
    logline: str = Field(description="One punchy sentence selling the film.")
    tone: str = Field(description="Genre/mood in a few words (e.g. 'tense neo-noir thriller').")
    visual_style: str = Field(description="The look to render, grounded in the reference images "
                                          "(film stock, palette, lighting, lens).")
    music_vibe: str = Field(description="The kind of music/sound the cut implies.")
    shots: list[Shot]
    summary: str = Field(description="1-2 sentence overall description of the trailer concept.")


# ---------------------------------------------------------------------------
# Stage 1 - concept
# ---------------------------------------------------------------------------

def concept_prompt(num_shots: int) -> str:
    return "\n".join([
        "You are a trailer director and editor for a film production. You are given a SCREENPLAY "
        "(text) and one or more REFERENCE IMAGES that define the visual world (look, characters, "
        "locations, palette). From these, devise the CONCEPT for a short teaser trailer and break "
        "it into a shot-by-shot sequence that an image generator can render.",
        "",
        "Work from the ACTUAL screenplay: use its real characters, locations, tone and key story "
        "beats. Match the visual style, characters and palette of the REFERENCE IMAGES so every "
        "shot belongs to the same film.",
        "",
        "Return, as structured JSON:",
        "- logline: one punchy sentence selling the film.",
        "- tone: the genre/mood in a few words.",
        "- visual_style: the look to render, grounded in the reference images (film stock, "
        "palette, lighting, lens).",
        "- music_vibe: the kind of music/sound the cut implies.",
        f"- shots: an ORDERED list of EXACTLY {num_shots} shots forming a trailer arc - open with "
        "a HOOK, build tension, escalate to a CLIMAX, and end on a final TAG / title beat. For "
        "each shot:",
        "    - order: 1-based position in the cut.",
        "    - beat: which trailer beat it serves (hook, setup, build, turn, climax, tag).",
        "    - title: a 2-4 word label.",
        "    - description: a SELF-CONTAINED visual prompt for ONE cinematic film still - who is "
        "in frame, where, the action, the framing and lighting - specific enough to render on its "
        "own, consistent with the screenplay and the references. Do NOT include any on-screen "
        "text or lettering in the image itself.",
        "    - duration_sec: seconds on screen (trailer shots are short, ~0.5-3s; let the final "
        "title beat breathe a little longer).",
        "    - title_card: punchy on-screen trailer text for this beat (a few words, like a real "
        "trailer card), or an empty string if none.",
        "- summary: 1-2 sentences describing the trailer concept overall.",
        "",
        "Return ONLY the structured JSON described by the schema.",
    ])


def make_concept(screenplay: str, references, api_key: str,
                 num_shots: int = DEFAULT_SHOTS) -> TrailerConcept:
    contents = [concept_prompt(num_shots), "--- SCREENPLAY ---", screenplay]
    if references:
        contents.append("--- REFERENCE IMAGES (the visual world) ---")
        contents.extend(references)
    return gemini.judge(contents, TrailerConcept, api_key, model=CONCEPT_MODEL,
                        temperature=CONCEPT_TEMPERATURE)


# ---------------------------------------------------------------------------
# Decision logic (pure, testable) - normalise the shotlist
# ---------------------------------------------------------------------------

def compute_shotlist(concept: TrailerConcept, min_shots: int = MIN_SHOTS,
                     max_shots: int = MAX_SHOTS) -> dict:
    """Order the shots, cap to max_shots, renumber 1..N, and summarise the cut."""
    shots = sorted(concept.shots, key=lambda s: s.order)[:max_shots]
    norm = [s.model_copy(update={"order": i}) for i, s in enumerate(shots, start=1)]
    runtime = round(sum(s.duration_sec for s in norm), 1)
    beats: list[str] = []
    for s in norm:
        if s.beat not in beats:
            beats.append(s.beat)
    return {
        "shots": norm,
        "count": len(norm),
        "runtime_sec": runtime,
        "beats": beats,
        "enough": len(norm) >= min_shots,
    }


# ---------------------------------------------------------------------------
# Stage 2 - stills
# ---------------------------------------------------------------------------

def shot_prompt(shot: Shot, concept: TrailerConcept) -> str:
    return "\n".join([
        "Generate ONE cinematic film still for a movie trailer - a single frame, photoreal and "
        "filmic, as if shot on a real camera.",
        f"TRAILER TONE: {concept.tone}.",
        f"VISUAL STYLE: {concept.visual_style}.",
        f"THIS SHOT ({shot.beat}): {shot.description}",
        "",
        "If REFERENCE IMAGES are provided, match their visual style, palette and any recurring "
        "characters and locations so this shot belongs in the same film.",
        "Make it cinematic: shallow depth of field with a clear focal subject, natural "
        "dimensional lighting, filmic contrast and color, and real photographic texture. Avoid a "
        "flat or 'AI' look.",
        "Do NOT render any text, letters, captions, subtitles or title cards in the image.",
        "Output a single image.",
    ])


def generate_shot(shot: Shot, concept: TrailerConcept, references, api_key: str):
    contents = [shot_prompt(shot, concept)]
    if references:
        contents.extend(references)
    return gemini.render(contents, api_key)


def run_image_process(shots, concept: TrailerConcept, references, api_key: str, gen_fn=None):
    """Render every shot, each one FRESH from the references (no stacking).

    A per-shot failure (an identity refusal, say) is captured, not fatal - the
    rest of the trailer still renders. gen_fn is injectable for offline testing.
    """
    gen_fn = gen_fn or (lambda shot: generate_shot(shot, concept, references, api_key))
    results = []
    for shot in shots:
        try:
            results.append({"shot": shot, "image": gen_fn(shot), "error": None})
        except Exception as e:              # one bad shot shouldn't sink the whole cut
            results.append({"shot": shot, "image": None, "error": str(e)})
    return results


def run_pipeline(screenplay: str, references, api_key: str, num_shots: int = DEFAULT_SHOTS,
                 generate_images: bool = True, concept_fn=None, gen_fn=None,
                 min_shots: int = MIN_SHOTS, max_shots: int = MAX_SHOTS):
    concept = (concept_fn or (lambda: make_concept(screenplay, references, api_key, num_shots)))()
    meta = compute_shotlist(concept, min_shots, max_shots)
    results = (run_image_process(meta["shots"], concept, references, api_key, gen_fn)
               if generate_images else [])
    return concept, meta, results


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

def format_concept(concept: TrailerConcept, meta: dict) -> str:
    head = [
        f"## {concept.logline}", "",
        f"**Tone:** {concept.tone}  ",
        f"**Visual style:** {concept.visual_style}  ",
        f"**Music:** {concept.music_vibe}  ",
        f"**Shots:** {meta['count']} · **runtime ≈** {meta['runtime_sec']}s · "
        f"**beats:** {', '.join(meta['beats'])}",
    ]
    if not meta["enough"]:
        head += ["", f"_Only {meta['count']} shot(s) came back - re-run for a fuller cut._"]

    table = report.table(
        ["#", "Beat", "Shot", "Secs", "Title card", "Visual"],
        [[str(s.order), s.beat, report.cell(s.title), str(s.duration_sec),
          report.cell(s.title_card) or "—", report.cell(s.description)]
         for s in meta["shots"]])
    return report.join("\n".join(head), table, f"**Concept:** {concept.summary}")


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def resolve_screenplay(text, file) -> tuple[str, str]:
    """(screenplay_text, error_message). Prefers pasted text; else a text file."""
    text = (text or "").strip()
    if text:
        return text, ""
    if file:
        path = file if isinstance(file, str) else getattr(file, "name", None)
        if path:
            if str(path).lower().endswith(".pdf"):
                return "", ("PDF screenplays aren't supported yet - paste the text, or upload a "
                            "`.txt` / `.md` / `.fountain` file.")
            try:
                with open(path, "rb") as fh:
                    return fh.read().decode("utf-8", errors="ignore").strip(), ""
            except Exception as e:
                return "", f"Couldn't read the screenplay file: {e}"
    return "", ""


def load_references(ref_files):
    if not ref_files:
        return []
    from PIL import Image

    refs = []
    for f in ref_files:
        path = f if isinstance(f, str) else getattr(f, "name", None)
        if not path:
            continue
        try:
            image = Image.open(path)
            image.load()
            refs.append(image)
        except Exception:
            continue
    return refs


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def run(screenplay_text, screenplay_file, ref_files, api_key, num_shots, generate_images):
    screenplay, err = resolve_screenplay(screenplay_text, screenplay_file)
    if err:
        return None, err
    if not screenplay:
        return None, "Please paste or upload a **screenplay** first."
    key, err = ui.key_or_error(api_key)
    if err:
        return None, err

    references = load_references(ref_files)
    try:
        concept, meta, results = run_pipeline(
            screenplay, references, key,
            num_shots=int(num_shots), generate_images=bool(generate_images))
    except Exception as e:
        return None, report.error_block(e)

    md = format_concept(concept, meta)
    if not generate_images:
        return [], md + "\n\n_Concept only - tick “Generate stills now” to render the shots (paid)._"

    gallery, errors = [], []
    for r in results:
        shot = r["shot"]
        if r["image"] is not None:
            gallery.append((r["image"], f"{shot.order}. {shot.beat} - {shot.title}"))
        else:
            errors.append(f"Shot {shot.order} ({shot.title}): {r['error']}")
    md += f"\n\n**Stills generated:** {len(gallery)}/{len(results)}."
    if errors:
        md += "\n\n**Shots that did not render:**\n" + "\n".join(f"- {e}" for e in errors)
    return gallery, md


def build_tab(api_key):
    gr = ui.gr()
    with gr.Row():
        with gr.Column():
            refs = ui.files_input("Reference images (visual world: look, characters, locations)")
            script = gr.Textbox(label="Screenplay (paste)", lines=10,
                                placeholder="Paste the screenplay / scene text here…")
            script_file = gr.File(label="…or upload a screenplay (.txt, .md, .fountain)",
                                  file_count="single",
                                  file_types=[".txt", ".md", ".fountain", "text"],
                                  type="filepath")
            shots = gr.Slider(MIN_SHOTS, MAX_SHOTS, value=DEFAULT_SHOTS, step=1,
                              label="Number of shots")
            generate = gr.Checkbox(value=True,
                                   label="Generate stills now (Nano Banana Pro, paid)")
            button = gr.Button("Create trailer concept & stills", variant="primary")
        with gr.Column():
            gallery = ui.gallery("Trailer stills (in cut order)")
            out = gr.Markdown()
    button.click(run, inputs=[script, script_file, refs, api_key, shots, generate],
                 outputs=[gallery, out])

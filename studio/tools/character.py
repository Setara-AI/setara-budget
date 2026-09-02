"""
Character - local face recognition (no API key, no Gemini).

Enroll an actor from a few reference photos, then check whether that actor's
FACE appears in a still. Read-only: it draws boxes and reports yes/no +
similarity, and never alters the image.

Method: dedicated face recognition (InsightFace + ArcFace), run locally. Far
more reliable for identity than a vision LLM, and the footage stays on the
machine.

SETUP: pip3 install -r requirements_face.txt
       (the first run downloads the face models, ~300 MB, automatically)
NOTE:  the InsightFace models are licensed for NON-COMMERCIAL use.
"""

from __future__ import annotations

import numpy as np

from .. import report, ui

TITLE = "Character"
TAGLINE = ("Find whether a specific actor's face appears in a still. Runs locally (no API key); "
           "needs `requirements_face.txt`.")

THRESHOLD = 0.40          # cosine similarity above which a face is "the same person"
MODEL_PACK = "buffalo_l"  # InsightFace pack; "buffalo_s" is lighter/faster

_FACE_APP = None


def get_face_app():
    """Lazy singleton - the model pack is heavy, so load it once."""
    global _FACE_APP
    if _FACE_APP is None:
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name=MODEL_PACK, providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))     # ctx_id=-1 = CPU
        _FACE_APP = app
    return _FACE_APP


def _pil_to_bgr(pil_image):
    arr = np.array(pil_image.convert("RGB"))
    return arr[:, :, ::-1]      # RGB -> BGR, the format InsightFace expects


def detect_faces(pil_image, face_app=None):
    face_app = face_app or get_face_app()
    return face_app.get(_pil_to_bgr(pil_image))


# ---------------------------------------------------------------------------
# Pure logic (no InsightFace needed - easy to test)
# ---------------------------------------------------------------------------

def cosine(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return -1.0
    return float(np.dot(a, b) / (na * nb))


def best_similarity(embedding, reference_embeddings) -> float:
    """Highest similarity between one face and any enrolled reference face."""
    return max((cosine(embedding, r) for r in reference_embeddings), default=-1.0)


def decide_present(similarities, threshold: float = THRESHOLD) -> bool:
    """The character is present if ANY detected face clears the threshold."""
    return any(s >= threshold for s in similarities)


# ---------------------------------------------------------------------------
# Enrollment + checking
# ---------------------------------------------------------------------------

def enroll(reference_pils, face_app=None):
    """Turn reference photos into a list of face embeddings for the actor."""
    face_app = face_app or get_face_app()
    embeddings = []
    for image in reference_pils:
        faces = detect_faces(image, face_app)
        if faces:
            clearest = max(faces, key=lambda f: f.det_score)
            embeddings.append(clearest.normed_embedding)
    return embeddings


def check_image(check_pil, reference_embeddings, threshold: float = THRESHOLD, face_app=None):
    """Detect faces in check_pil and compare each to the enrolled actor."""
    face_app = face_app or get_face_app()
    results = []
    for face in detect_faces(check_pil, face_app):
        similarity = best_similarity(face.normed_embedding, reference_embeddings)
        results.append({
            "bbox": [float(x) for x in face.bbox],
            "sim": similarity,
            "match": similarity >= threshold,
        })
    return decide_present([r["sim"] for r in results], threshold), results


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

def annotate(check_pil, results):
    """Draw boxes on a copy of the image: green = match, red = other face."""
    from PIL import ImageDraw

    image = check_pil.convert("RGB").copy()
    draw = ImageDraw.Draw(image)
    for r in results:
        x1, y1, x2, y2 = r["bbox"]
        color = (40, 200, 80) if r["match"] else (220, 60, 60)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        draw.text((x1, max(0, y1 - 12)), f"{r['sim']:.2f}", fill=color)
    return image


def report_markdown(present, results, threshold: float) -> str:
    if not results:
        return "**No faces detected** in this image."
    header = "## Character IS in the shot" if present else "## Character not found"
    matches = [r for r in results if r["match"]]
    info = (f"Faces detected: {len(results)} · matches: {len(matches)} · "
            f"threshold: {threshold:.2f}")
    table = report.table(
        ["Face", "Similarity", "Match"],
        [[str(i), f"{r['sim']:.2f}", "YES" if r["match"] else "no"]
         for i, r in enumerate(sorted(results, key=lambda r: -r["sim"]), 1)])
    return report.join(header, info, table)


def run(reference_files, check_pil, threshold):
    if not reference_files:
        return None, "Please add at least one **reference photo** of the actor."
    if check_pil is None:
        return None, "Please add an **image to check**."

    from PIL import Image

    paths = [getattr(f, "name", f) for f in reference_files]
    try:
        face_app = get_face_app()
        embeddings = enroll([Image.open(p) for p in paths], face_app)
        if not embeddings:
            return None, ("No face was found in the reference photos. Use clear, front-facing "
                          "photos of just the actor.")
        present, results = check_image(check_pil, embeddings, float(threshold), face_app)
    except Exception as e:
        return None, report.error_block(e)

    return annotate(check_pil, results), report_markdown(present, results, float(threshold))


def build_tab(api_key=None):
    """api_key is accepted and ignored - this tool runs entirely locally."""
    gr = ui.gr()
    with gr.Row():
        with gr.Column():
            references = ui.files_input("Reference photos of the actor (1-5, clear faces)")
            check = ui.image_input("Image to check")
            threshold = gr.Slider(0.2, 0.8, value=THRESHOLD, step=0.02,
                                  label="Match threshold (higher = stricter)")
            button = gr.Button("Check for character", variant="primary")
        with gr.Column():
            annotated = ui.image_output("Detected faces (green = match, red = other)")
            out = gr.Markdown()
    button.click(run, inputs=[references, check, threshold], outputs=[annotated, out])

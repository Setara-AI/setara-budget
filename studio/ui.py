"""
Shared Gradio widgets.

Every tab used to build its own key box, image inputs, sliders and gallery with
slightly different arguments. They come from here now, so the studio looks and
behaves the same everywhere and the conventions (PNG output, PIL images,
clipboard paste) are set in one place.

Gradio is imported lazily: importing `studio.tools.*` for tests or for an API
must not require a UI toolkit.
"""

from __future__ import annotations

from . import config
from .gemini import resolve_key

# Linear-style typography (Inter). Font only - everything else stays Gradio default.
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*, button, input, textarea, select, .gradio-container {
  font-family: 'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont,
               system-ui, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif !important;
}
"""

NO_KEY = "Please paste your Gemini API key above."


def gr():
    import gradio

    return gradio


def api_key_box(label: str = "Gemini API key"):
    return gr().Textbox(label=label, type="password", value=config.env_key(),
                        placeholder="Paste your key from aistudio.google.com")


def image_input(label: str):
    return gr().Image(label=label, type="pil", sources=["upload", "clipboard"])


def image_output(label: str):
    return gr().Image(label=label, format=config.IMAGE_FORMAT)


def gallery(label: str, columns: int = 2):
    return gr().Gallery(label=label, columns=columns, height="auto",
                        format=config.IMAGE_FORMAT)


def strictness(value: float, label: str = "Strictness (fraction of checks that must pass)"):
    return gr().Slider(0.0, 1.0, value=value, step=0.05, label=label)


def retries(value: int, maximum: int = 3, label: str = "Max regenerations"):
    return gr().Slider(1, maximum, value=value, step=1, label=label)


def files_input(label: str, **kwargs):
    return gr().File(label=label, file_count="multiple", file_types=["image"],
                     type="filepath", **kwargs)


# ---------------------------------------------------------------------------
# Handler helpers
# ---------------------------------------------------------------------------

def key_or_error(api_key) -> tuple[str, str]:
    """(key, "") when a key is available, else ("", message-to-show)."""
    key = resolve_key(api_key)
    return (key, "") if key else ("", NO_KEY)


def attempt_gallery(attempts, tag=None) -> list:
    """Loop attempts -> Gradio gallery items, skipping any that failed to render."""
    tag = tag or (lambda a: f"{a.label} - {a.score.tally()}")
    return [(a.image, tag(a)) for a in attempts if a.image is not None]

"""
The only module that talks to Google.

Two calls, used by every tool:

  judge(...)   send a prompt + image(s), get a Pydantic object back
  render(...)  send a prompt + image(s) to Nano Banana Pro, get a PIL.Image back

Both import `google.genai` lazily so the pure logic (and its tests) can run
without the SDK or a key installed.
"""

from __future__ import annotations

import io
import json
from typing import Any, Sequence

from . import config


class NoImageReturned(RuntimeError):
    """Nano Banana Pro answered, but without an image (usually a content refusal)."""


def resolve_key(api_key: str | None) -> str:
    """The pasted key, else GEMINI_API_KEY, else ''."""
    return (api_key or config.env_key()).strip()


def _client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------

def judge(contents: Sequence[Any], schema: type, api_key: str,
          model: str = config.CHECK_MODEL,
          temperature: float = config.CHECK_TEMPERATURE):
    """Structured vision call. `contents` mixes strings and PIL images.

    Returns an instance of `schema` (a Pydantic model).
    """
    from google.genai import types

    response = _client(api_key).models.generate_content(
        model=model,
        contents=list(contents),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
        ),
    )
    parsed = getattr(response, "parsed", None)
    if parsed is None:                       # older/edge responses: parse the text ourselves
        parsed = schema(**json.loads(response.text))
    return parsed


# ---------------------------------------------------------------------------
# Generating
# ---------------------------------------------------------------------------

def render(contents: Sequence[Any], api_key: str,
           model: str = config.IMAGE_MODEL,
           image_size: str = config.IMAGE_SIZE):
    """Nano Banana Pro call. Returns a PIL.Image, or raises NoImageReturned."""
    from google.genai import types
    from PIL import Image

    response = _client(api_key).models.generate_content(
        model=model,
        contents=list(contents),
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(image_size=image_size),
        ),
    )
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in (getattr(content, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline is not None and getattr(inline, "data", None):
                image = Image.open(io.BytesIO(inline.data))
                image.load()
                return image
    text = (getattr(response, "text", "") or "")[:300]
    raise NoImageReturned(f"Nano Banana Pro did not return an image. Response text: {text}")

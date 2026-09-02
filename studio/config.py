"""Model ids and output conventions. Change them here, nowhere else."""

from __future__ import annotations

import os

# Vision checks (cheap, ~1.5c) and image generation (Nano Banana Pro, paid ~$0.13/2K image).
CHECK_MODEL = "gemini-3-flash-preview"
IMAGE_MODEL = "gemini-3-pro-image-preview"

# Conventions: 2K renders, lossless PNG everywhere in the UI.
IMAGE_SIZE = "2K"
IMAGE_FORMAT = "png"

# Checkers are graded; 0 keeps verdicts reproducible.
CHECK_TEMPERATURE = 0.0

ENV_KEY = "GEMINI_API_KEY"


def env_key() -> str:
    return os.environ.get(ENV_KEY, "")

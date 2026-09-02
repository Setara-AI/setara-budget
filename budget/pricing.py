"""
The price registry.

Every rate here is either taken from the provider's own published pricing page
(`verified=True`, with the date it was read) or projected by us from a published
token rate (`verified=False`). A budget is only as trustworthy as its sources, so
the report prints that distinction rather than hiding it.

Video models are billed by TOKENS on fal:

    tokens = (height * width * duration_seconds * 24) / 1024
    cost   = tokens / 1000 * rate_per_1k

which is why per-second cost scales with pixel count. The published per-second
figures on the model pages are quoted alongside for cross-checking; where they
disagree with the formula (Seedance 2.5 quotes ~2.3% above it) the difference is
noted on the entry and `PRICE_DRIFT` covers it in the estimate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PRICES_READ_ON = "2026-08-26"

# fal's own quoted per-second figures for Seedance 2.5 sit ~2.3% above what its
# published token rate produces. Rather than silently pick one, the estimate adds
# this as an explicit line.
PRICE_DRIFT = 0.025


@dataclass(frozen=True)
class VideoModel:
    """A video generator priced per second of output."""

    id: str
    name: str
    width: int
    height: int
    rate_per_1k_tokens: float
    min_seconds: int
    max_seconds: int
    verified: bool
    source: str
    quoted_per_second: float | None = None   # the provider's own per-second figure
    note: str = ""

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    def tokens_per_second(self) -> float:
        return (self.height * self.width * 24) / 1024

    def cost_per_second(self) -> float:
        """From the token formula - the authoritative calculation."""
        return self.tokens_per_second() / 1000 * self.rate_per_1k_tokens

    def cost(self, seconds: float) -> float:
        return self.cost_per_second() * seconds

    def clamp_seconds(self, seconds: float) -> float:
        """Clip length the model can actually produce."""
        return max(self.min_seconds, min(self.max_seconds, seconds))

    def drift(self) -> float:
        """How far the provider's quoted per-second figure sits above the formula."""
        if not self.quoted_per_second:
            return 0.0
        return self.quoted_per_second / self.cost_per_second() - 1


@dataclass(frozen=True)
class ImageModel:
    """An image generator priced per image."""

    id: str
    name: str
    label: str
    cost_per_image: float
    verified: bool
    source: str
    note: str = ""

    def cost(self, images: int) -> float:
        return self.cost_per_image * images


FAL_2_5 = "https://fal.ai/models/bytedance/seedance-2.5/text-to-video"
FAL_2_5_REF = "https://fal.ai/models/bytedance/seedance-2.5/reference-to-video"
FAL_2_0 = "https://fal.ai/models/bytedance/seedance-2.0/image-to-video"
GEMINI_IMAGE = "https://ai.google.dev/gemini-api/docs/pricing"


VIDEO_MODELS = {
    m.id: m for m in [
        # --- Seedance 2.5. fal publishes 480p and 720p only; 4-30s per pass. ---
        VideoModel(
            id="seedance-2.5-1080p", name="Seedance 2.5", width=1920, height=1080,
            rate_per_1k_tokens=0.0214, min_seconds=4, max_seconds=30,
            verified=False, source=FAL_2_5,
            note="PROJECTED. fal does not currently offer 2.5 above 720p - this "
                 "applies 2.5's published token rate ($0.0214/1k) to 1920x1080. "
                 "Treat it as a planning figure, not a quote.",
        ),
        VideoModel(
            id="seedance-2.5-720p", name="Seedance 2.5", width=1280, height=720,
            rate_per_1k_tokens=0.0214, min_seconds=4, max_seconds=30,
            verified=True, source=FAL_2_5, quoted_per_second=0.4730,
            note="Top resolution fal offers on 2.5. Audio is included in the token count.",
        ),
        VideoModel(
            id="seedance-2.5-720p-ref", name="Seedance 2.5 (reference-to-video)",
            width=1280, height=720, rate_per_1k_tokens=0.0128,
            min_seconds=4, max_seconds=30,
            verified=True, source=FAL_2_5_REF, quoted_per_second=0.2838,
            note="Reference-to-video WITH video references - the cheap lane, and the "
                 "one that consumes generated reference plates. Up to 50 reference inputs.",
        ),
        VideoModel(
            id="seedance-2.5-480p", name="Seedance 2.5", width=864, height=496,
            rate_per_1k_tokens=0.0214, min_seconds=4, max_seconds=30,
            verified=True, source=FAL_2_5, quoted_per_second=0.2205,
        ),
        # --- Seedance 2.0. The only lane fal actually offers at 1080p / 4K. ---
        VideoModel(
            id="seedance-2.0-1080p", name="Seedance 2.0", width=1920, height=1080,
            rate_per_1k_tokens=0.014, min_seconds=4, max_seconds=15,
            verified=True, source=FAL_2_0, quoted_per_second=0.682,
            note="Real, published 1080p. Shorter maximum take than 2.5 (15s vs 30s).",
        ),
        VideoModel(
            id="seedance-2.0-720p", name="Seedance 2.0", width=1280, height=720,
            rate_per_1k_tokens=0.014, min_seconds=4, max_seconds=15,
            verified=True, source=FAL_2_0, quoted_per_second=0.3034,
        ),
        VideoModel(
            id="seedance-2.0-4k", name="Seedance 2.0", width=3840, height=2160,
            rate_per_1k_tokens=0.008, min_seconds=4, max_seconds=15,
            verified=True, source=FAL_2_0,
            note="4K bills on the token rate only - no per-second figure published.",
        ),
    ]
}

IMAGE_MODELS = {
    m.id: m for m in [
        ImageModel(
            id="nano-banana-pro-2k", name="Nano Banana Pro", label="1K / 2K",
            cost_per_image=0.134, verified=True, source=GEMINI_IMAGE,
            note="1,120 output tokens at $120/M. 1K and 2K cost the same.",
        ),
        ImageModel(
            id="nano-banana-pro-4k", name="Nano Banana Pro", label="4K",
            cost_per_image=0.24, verified=True, source=GEMINI_IMAGE,
            note="2,000 output tokens at $120/M.",
        ),
    ]
}

DEFAULT_VIDEO_MODEL = "seedance-2.5-1080p"
DEFAULT_IMAGE_MODEL = "nano-banana-pro-2k"


def video(model_id: str = DEFAULT_VIDEO_MODEL) -> VideoModel:
    try:
        return VIDEO_MODELS[model_id]
    except KeyError:
        raise KeyError(f"Unknown video model {model_id!r}. "
                       f"Known: {', '.join(VIDEO_MODELS)}") from None


def image(model_id: str = DEFAULT_IMAGE_MODEL) -> ImageModel:
    try:
        return IMAGE_MODELS[model_id]
    except KeyError:
        raise KeyError(f"Unknown image model {model_id!r}. "
                       f"Known: {', '.join(IMAGE_MODELS)}") from None


def comparison_table() -> list[dict]:
    """Every video tier side by side - the 'what would this bid be at each tier' view."""
    return [
        {
            "id": m.id,
            "model": m.name,
            "resolution": m.resolution,
            "per_second": m.cost_per_second(),
            "quoted": m.quoted_per_second,
            "max_take": m.max_seconds,
            "verified": m.verified,
        }
        for m in sorted(VIDEO_MODELS.values(), key=lambda m: m.cost_per_second())
    ]

"""One module per tab. `TOOLS` is the order they appear in the studio."""

from . import trailer, animation, character, cinematic, continuity, clearance

TOOLS = [trailer, animation, character, cinematic, continuity, clearance]

BY_NAME = {m.__name__.rsplit(".", 1)[-1]: m for m in TOOLS}

__all__ = ["TOOLS", "BY_NAME", "trailer", "animation", "character",
           "cinematic", "continuity", "clearance"]

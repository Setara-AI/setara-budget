"""
The studio: every tool in one tabbed app.

  python3 studio_app.py            all tabs
  python3 -m studio                same thing
  python3 -m studio cinematic      just that tool, on its own

The Gemini tabs share one API key box - paste it once. Trailer, Animation and
Consistency call Nano Banana Pro (paid, billing must be enabled); Cinematic and
Clearance are checkers only; Character runs locally.
"""

from __future__ import annotations

from . import ui
from .tools import BY_NAME, TOOLS


def build_ui(tools=None):
    """One Blocks with a tab per tool. `tools` defaults to all of them."""
    import gradio as gr

    tools = list(tools or TOOLS)
    single = len(tools) == 1
    title = tools[0].TITLE if single else "Studio"

    with gr.Blocks(title=title) as demo:
        if single:
            gr.Markdown(f"# {title}\n{tools[0].TAGLINE}")
        else:
            gr.Markdown("# Studio\nAll your tools in one place. Pick a tab.")

        api_key = ui.api_key_box()

        if single:
            tools[0].build_tab(api_key)
        else:
            with gr.Tabs():
                for tool in tools:
                    with gr.Tab(tool.TITLE):
                        gr.Markdown(tool.TAGLINE)
                        tool.build_tab(api_key)
    return demo


def launch(demo=None, **kwargs):
    """Launch with the studio's typography. Gradio 6 takes css at launch(), not Blocks()."""
    return (demo or build_ui()).launch(css=ui.CUSTOM_CSS, **kwargs)


def main(argv=None):
    import sys

    names = list(argv if argv is not None else sys.argv[1:])
    unknown = [n for n in names if n not in BY_NAME]
    if unknown:
        raise SystemExit(f"Unknown tool(s): {', '.join(unknown)}. "
                         f"Available: {', '.join(BY_NAME)}")
    launch(build_ui([BY_NAME[n] for n in names] if names else None))


if __name__ == "__main__":
    main()

"""
Studio - AI image QC for a film pipeline.

Package layout
--------------
  studio.config     model ids and output conventions (one place to change them)
  studio.gemini     the only place that talks to Google: judge() and render()
  studio.criteria   Criterion + the ONE structured-output schema every checker uses
  studio.loop       the hygienic check -> fix -> re-check agent loop
  studio.report     markdown rendering shared by every tool
  studio.ui         shared Gradio widgets + the tabbed app
  studio.tools.*    one module per tab (trailer, animation, character,
                    cinematic, continuity, clearance)

Every tool module exposes the same surface, so the app (and, later, an API) can
treat them uniformly:

  TITLE     str   - tab label
  TAGLINE   str   - one-paragraph blurb shown at the top of the tab
  check()         - Gemini call returning a Verdict (except `character`, local)
  compute*()      - pure, testable decision function (no API needed)
  report()        - Verdict -> markdown
  run()           - the handler wired to the button
  build_tab()     - the Gradio panel
"""

__all__ = ["config", "criteria", "gemini", "loop", "report", "ui", "tools"]

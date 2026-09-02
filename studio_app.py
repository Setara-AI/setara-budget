"""
Studio - all your tools in one app, navigable by tabs.

RUN:  python3 studio_app.py   (restart after changes; a browser refresh won't reload it)

Tabs: Trailer | Animation | Character | Cinematic | Consistency | Clearance

Everything lives in the `studio/` package - this file is just the entry point:
  studio/tools/*.py   one module per tab
  studio/gemini.py    the only place that calls Google
  studio/criteria.py  the shared checker schema + scoring
  studio/loop.py      the check -> fix -> re-check loop (with loop hygiene)

To run one tool on its own:  python3 -m studio cinematic
"""

from studio.app import launch

if __name__ == "__main__":
    launch()

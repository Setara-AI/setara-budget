"""
AI Production Budget - script in, bid out.

RUN:  python3 budget_app.py

Tabs: Estimate | Breakdown | Board | Assets | Sync

The engine is the `budget/` package and has no network and no LLM calls, so the
numbers are reproducible:
  budget/pricing.py   the model price registry (every rate carries its source)
  budget/script.py    the screenplay parser
  budget/estimate.py  the bid
  budget/project.py   the whole pipeline behind one object
"""

import os

from budget.ui import launch

if __name__ == "__main__":
    launch(server_port=int(os.environ.get("PORT", "7870")))

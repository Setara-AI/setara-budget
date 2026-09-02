"""
Budget - AI production budgeting and pipeline accountability.

What it answers: given a script, what should a producer set aside for the AI
scenes, how does that compare to the traditional-production bid, how many people
does it take, and how long does it run?

  pricing.py    the model/price registry - every rate carries its source
  script.py     screenplay -> scenes (pure Python, no LLM calls)
  breakdown.py  scenes -> characters, locations, props, complexity
  plan.py       complexity -> shots, plates, revision rounds
  costs.py      the plan -> generation cost lines
  labor.py      crew + AI operators: rates, throughput, headcount <-> schedule
  estimate.py   everything -> one budget, with contingency and a traditional baseline
  report.py     the budget -> markdown / CSV / JSON
  assets.py     the folder hierarchy, option sets and approval ledger
  tasks.py      Linear-style assignment and accountability
  sync/         where approved assets land (local, Frame.io, Google Drive)

Everything above `ui` is pure Python with no network and no LLM token calls, so
the numbers are reproducible and testable.
"""

__all__ = ["pricing", "script", "breakdown", "plan", "costs", "labor",
           "estimate", "report", "assets", "tasks", "sync"]

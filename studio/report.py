"""Markdown rendering shared by every tool (tables, headers, outcome lines)."""

from __future__ import annotations

from typing import Callable, Iterable

from .criteria import Criterion, Score, Verdict


def cell(text: str) -> str:
    """Make a string safe to drop into a markdown table cell."""
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def table(headers: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    headers = list(headers)
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def criteria_table(criteria: list[Criterion], verdict: Verdict,
                   headers: Iterable[str],
                   row: Callable[[Criterion, object], Iterable[str]]) -> str:
    """One row per criterion, in the tool's declared order - so a criterion the
    model forgot to return still shows up (as a gap), instead of vanishing."""
    return table(headers, (list(row(c, verdict.result_for(c.id))) for c in criteria))


def verdict_row(criterion: Criterion, result, *, yes: str = "PASS", no: str = "fail",
                critical_suffix: str = " (must-pass)") -> list[str]:
    """The common three-column row: name, verdict, why."""
    name = criterion.name + (critical_suffix if criterion.critical else "")
    if result is None:
        return [name, "-", "no result returned"]
    return [name, yes if result.passed else no, cell(result.note)]


def score_line(sc: Score, verdict: Verdict, *, noun: str = "criteria") -> str:
    line = (f"**Passed:** {sc.tally()} {noun} ({sc.percent}%) · "
            f"**confidence** {verdict.confidence}/100")
    if sc.critical_misses:
        line += "  \n**Failing must-pass " + noun + ":** " + ", ".join(sc.critical_misses)
    return line


def outcome(ok: bool, used: int, what: str) -> str:
    if ok and used == 0:
        return f"{what}: already correct"
    if ok:
        return f"{what}: fixed after {used} regeneration(s)"
    return f"{what}: still off after {used} regeneration(s)"


def progress(attempts) -> str:
    """e.g. `3/6 -> 5/6 -> 6/6` across the attempts of a loop."""
    return " -> ".join(a.score.tally() for a in attempts)


def error_block(exc: Exception) -> str:
    return f"**Something went wrong:**\n\n```\n{exc}\n```"


def join(*blocks: str) -> str:
    """Join markdown blocks with blank lines, dropping empties."""
    return "\n\n".join(b for b in blocks if b)

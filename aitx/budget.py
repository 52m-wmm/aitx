"""Daily LLM spend cap (decision 2026-11-05: the paid balance is small).

Before every LLM call, today's spend so far is added up from runs/llm_calls.jsonl (every real call is logged
there with its token usage; cached answers cost nothing and are not logged) and compared with the cap in
AITX_LLM_BUDGET_USD (default 0.3). Over the cap, OverBudget is raised instead of calling: the caller stops and
keeps whatever it has already finished, exactly as with a peak window (aitx.peak).

"Today" is a calendar day in the provider's own timezone (config/llm_peak_hours.json), the same clock the
peak windows use, so a run that starts before midnight and a run that starts after it are counted separately.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ENV = "AITX_LLM_BUDGET_USD"
DEFAULT_USD = 0.3


class OverBudget(Exception):
    """Today's LLM spend has reached the cap; nothing was sent to the server."""


def cap() -> float | None:
    """The cap in USD, or None when it is switched off with AITX_LLM_BUDGET_USD=off / empty."""
    raw = os.environ.get(ENV)
    if raw is None:
        return DEFAULT_USD
    raw = raw.strip()
    if raw == "" or raw.lower() in ("off", "none", "unlimited"):
        return None
    try:
        v = float(raw)
    except ValueError as e:
        raise ValueError(f"{ENV}={raw!r} is not a number (use a dollar amount, or 'off')") from e
    if v < 0:
        raise ValueError(f"{ENV}={raw!r} is negative")
    return v


def day_start(now: dt.datetime | None = None) -> float:
    """Unix time of midnight today in the provider's timezone (same config as the peak windows)."""
    from aitx import peak as P
    tz = ZoneInfo(P.load()["timezone"])
    now = (now or dt.datetime.now(tz)).astimezone(tz)
    return dt.datetime.combine(now.date(), dt.time(0, 0), tz).timestamp()


def spent_today(now: dt.datetime | None = None, log: Path | None = None) -> float:
    """Today's spend in USD, priced by scripts/llm_cost.py (the single pricing table)."""
    import sys
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import llm_cost
    path = log or llm_cost.LOG
    if not Path(path).exists():
        return 0.0
    return llm_cost.summarize(day_start(now), Path(path))["usd"]


def check_before_call(now: dt.datetime | None = None, log: Path | None = None) -> None:
    """Raise OverBudget when today's spend has reached the cap. Called before every LLM call."""
    limit = cap()
    if limit is None:
        return
    spent = spent_today(now, log)
    if spent >= limit:
        raise OverBudget(f"today's LLM spend ${spent:.4f} has reached the ${limit:.2f} cap ({ENV}); stopping before "
                         f"the next call. Finished work is kept. Raise the cap or wait for the next day.")


def left(now: dt.datetime | None = None, log: Path | None = None) -> str:
    """One line for the run log: what has been spent today and what is left."""
    limit = cap()
    spent = spent_today(now, log)
    if limit is None:
        return f"LLM spend today ${spent:.4f} (no cap set)"
    return f"LLM spend today ${spent:.4f} of ${limit:.2f} cap (${max(0.0, limit - spent):.4f} left)"

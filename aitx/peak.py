"""Peak-price hours of the LLM provider (config/llm_peak_hours.json, US Pacific time).

`--offpeak-only` on a run command calls guard(): inside a peak window it prints how long until the window
ends and exits without making any LLM call.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

CONFIG = Path(__file__).resolve().parents[1] / "config" / "llm_peak_hours.json"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def load(path: Path = CONFIG) -> dict:
    return json.loads(path.read_text())


def _hm(s: str) -> dt.time:
    h, m = s.split(":")
    return dt.time(int(h), int(m))


def current_window(now: dt.datetime | None = None, cfg: dict | None = None) -> tuple[dt.datetime, dt.datetime] | None:
    """(start, end) of the peak window containing `now` (aware datetime; default: now), or None."""
    cfg = cfg or load()
    tz = ZoneInfo(cfg["timezone"])
    now = (now or dt.datetime.now(tz)).astimezone(tz)
    for day_offset in (0, -1):                       # a window may have started yesterday and cross midnight
        day = (now + dt.timedelta(days=day_offset)).date()
        for w in cfg["windows"]:
            if DAYS[day.weekday()] not in w["days"]:
                continue
            start = dt.datetime.combine(day, _hm(w["start"]), tz)
            end = dt.datetime.combine(day, _hm(w["end"]), tz)
            if end <= start:
                end += dt.timedelta(days=1)
            if start <= now < end:
                return start, end
    return None


def guard(now: dt.datetime | None = None) -> None:
    """Exit (code 3) with a message if we are inside a peak window."""
    w = current_window(now)
    if w:
        left = w[1] - (now or dt.datetime.now(w[1].tzinfo)).astimezone(w[1].tzinfo)
        mins = math.ceil(left.total_seconds() / 60)
        print(f"Peak-price hours ({w[0]:%a %H:%M}-{w[1]:%H:%M} {w[1].tzname()}): no LLM calls now. "
              f"Off-peak in {mins // 60} h {mins % 60} min (at {w[1]:%H:%M}). Run again then.")
        raise SystemExit(3)

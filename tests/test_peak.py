"""Peak-hours guard (config/llm_peak_hours.json, US Pacific time)."""
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from aitx import peak

PT = ZoneInfo("America/Los_Angeles")


@pytest.mark.parametrize("when,in_peak", [
    (dt.datetime(2026, 11, 1, 17, 30, tzinfo=PT), True),    # Sunday 17:30
    (dt.datetime(2026, 11, 3, 20, 0, tzinfo=PT), False),    # Tuesday 20:00 (window end is exclusive)
    (dt.datetime(2026, 11, 3, 21, 15, tzinfo=PT), False),   # between the two windows
    (dt.datetime(2026, 11, 3, 23, 0, tzinfo=PT), True),     # Tuesday 23:00
    (dt.datetime(2026, 11, 4, 1, 30, tzinfo=PT), True),     # Wednesday 01:30: Tuesday's window crosses midnight
    (dt.datetime(2026, 11, 7, 1, 30, tzinfo=PT), False),    # Saturday 01:30: Friday has no window
    (dt.datetime(2026, 11, 6, 18, 0, tzinfo=PT), False),    # Friday 18:00
    (dt.datetime(2026, 11, 3, 10, 0, tzinfo=dt.timezone.utc), True),  # 02:00 PST is outside... see below
])
def test_windows(when, in_peak):
    if when.tzinfo is dt.timezone.utc:                      # 10:00 UTC = 02:00 PST Tuesday: window ended at 02:00
        assert peak.current_window(when) is None
        return
    assert (peak.current_window(when) is not None) is in_peak


def test_guard_exits_with_wait_time(capsys):
    with pytest.raises(SystemExit) as e:
        peak.guard(dt.datetime(2026, 11, 3, 18, 15, tzinfo=PT))
    assert e.value.code == 3
    out = capsys.readouterr().out
    assert "1 h 45 min" in out and "20:00" in out
    peak.guard(dt.datetime(2026, 11, 3, 21, 0, tzinfo=PT))  # off-peak: returns


def test_cache_only_blocks_real_calls(monkeypatch):
    import pytest
    from aitx import llm
    monkeypatch.setenv("AITX_LLM_CACHE_ONLY", "1")
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    with pytest.raises(llm.CacheOnly):
        llm.chat([{"role": "user", "content": "x"}])

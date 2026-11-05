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


def test_streamed_response_is_assembled(monkeypatch, tmp_path):
    import io
    import json as J
    from aitx import llm
    chunks = [{"id": "c1", "model": "deepseek-flash", "choices": [{"delta": {"reasoning_content": "think"}}]},
              {"id": "c1", "model": "deepseek-flash", "choices": [{"delta": {"content": '{"a": '}}]},
              {"id": "c1", "model": "deepseek-flash", "choices": [{"delta": {"content": "1}"}, "finish_reason": "stop"}]},
              {"id": "c1", "model": "deepseek-flash", "choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 3}}]
    body = b": keep-alive\n\n" + b"".join(b"data: " + J.dumps(c).encode() + b"\n\n" for c in chunks) + b"data: [DONE]\n\n"
    sent = {}

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout):
        sent.update(J.loads(req.data))
        return R(body)

    monkeypatch.delenv("AITX_LLM_CACHE_ONLY", raising=False)
    monkeypatch.setenv("AITX_LLM_API_KEY", "k")
    monkeypatch.setattr(llm, "LOG", tmp_path / "calls.jsonl")
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    r = llm.chat([{"role": "user", "content": "x"}])
    assert sent["stream"] is True and sent["stream_options"] == {"include_usage": True}
    m = r["choices"][0]
    assert m["message"]["content"] == '{"a": 1}' and m["message"]["reasoning_content"] == "think"
    assert m["finish_reason"] == "stop" and r["model"] == "deepseek-flash" and r["usage"]["completion_tokens"] == 3
    assert J.loads((tmp_path / "calls.jsonl").read_text())["usage"]["prompt_tokens"] == 5


PT = ZoneInfo("America/Los_Angeles")


def test_offpeak_only_checks_before_every_call(monkeypatch):
    # decision 2026-11-04: not only at start - a run that reaches a peak window stops before the next call
    monkeypatch.setenv(peak.ENV, "1")
    peak.check_before_call(dt.datetime(2026, 11, 4, 21, 59, tzinfo=PT))          # Wed 21:59: off-peak, no error
    with pytest.raises(peak.PeakHours):
        peak.check_before_call(dt.datetime(2026, 11, 4, 22, 1, tzinfo=PT))      # Wed 22:01: peak
    monkeypatch.delenv(peak.ENV)
    peak.check_before_call(dt.datetime(2026, 11, 4, 22, 1, tzinfo=PT))          # reverse: without --offpeak-only, no stop


def test_guard_arms_the_per_call_check(monkeypatch):
    monkeypatch.delenv(peak.ENV, raising=False)
    peak.guard(dt.datetime(2026, 11, 4, 21, 0, tzinfo=PT))
    import os
    assert os.environ.get(peak.ENV) == "1"
    monkeypatch.delenv(peak.ENV)


def test_llm_call_refused_inside_peak_and_nothing_cached(monkeypatch, tmp_path):
    from aitx.disease import extract as X
    monkeypatch.setattr(X, "CACHE_DIR", tmp_path)
    monkeypatch.setenv(peak.ENV, "1")
    monkeypatch.setattr(peak, "current_window", lambda now=None, cfg=None: (dt.datetime(2026, 11, 4, 22, tzinfo=PT),
                                                                           dt.datetime(2026, 11, 5, 2, tzinfo=PT)))
    called = []
    monkeypatch.setattr(X.llm, "chat", lambda *a, **k: called.append(1))
    monkeypatch.setattr(X.llm, "config", lambda: {"model": "m", "base_url": "u"})
    with pytest.raises(peak.PeakHours):
        X._cached_chat([{"role": "user", "content": "x"}], 0, True)
    assert not called and not list(tmp_path.iterdir())


def test_pipeline_stops_with_exit_code_3_keeping_finished_cases(monkeypatch, tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import run_pipeline as RP
    written = []
    monkeypatch.setattr(RP.runmeta, "write_output", lambda k, case, result, upstream=None, **kw: written.append(case["id"]) or "h")
    monkeypatch.setattr(RP.runmeta, "path", lambda k, cid, *a, **kw: tmp_path / f"{cid}.json")

    def step(case, prior, ctx):
        if case["id"] == "B":
            raise peak.PeakHours("peak began")
        return {"ok": True}
    monkeypatch.setattr(RP, "STEPS", {1: step})
    monkeypatch.setattr(RP, "Context", lambda cases, use_cache: None)
    assert RP.run([{"id": "A"}, {"id": "B"}, {"id": "C"}], 1, 1) == 3
    assert written == ["A"]                                              # A kept, B not written, C not started

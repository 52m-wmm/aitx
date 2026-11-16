"""Daily LLM spend cap (decision 2026-11-05)."""
import datetime as dt
import json

import pytest

from aitx import budget as B

NOW = dt.datetime(2026, 11, 6, 22, 0, tzinfo=dt.timezone.utc)   # Fri 14:00 Pacific, off-peak
NOON = 12 * 3600                                                 # midday in the provider timezone: never a peak window


def _log(tmp_path, calls):
    p = tmp_path / "llm_calls.jsonl"
    p.write_text("".join(json.dumps(c) + "\n" for c in calls))
    return p


def _call(ts, out_tokens):
    return {"ts": ts, "served": "deepseek-flash",
            "usage": {"prompt_tokens": 0, "completion_tokens": out_tokens,
                      "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0}}


def test_default_cap_and_overrides(monkeypatch):
    monkeypatch.delenv(B.ENV, raising=False)
    assert B.cap() == 0.3
    monkeypatch.setenv(B.ENV, "1.5")
    assert B.cap() == 1.5
    for off in ("off", "", "none", "unlimited"):
        monkeypatch.setenv(B.ENV, off)
        assert B.cap() is None
    monkeypatch.setenv(B.ENV, "abc")
    with pytest.raises(ValueError):
        B.cap()
    monkeypatch.setenv(B.ENV, "-1")
    with pytest.raises(ValueError):
        B.cap()


def test_only_todays_calls_count(monkeypatch, tmp_path):
    monkeypatch.delenv(B.ENV, raising=False)
    start = B.day_start(NOW)
    log = _log(tmp_path, [_call(start - 3600, 1_000_000), _call(start + NOON, 100_000)])
    assert B.spent_today(NOW, log) == pytest.approx(0.06, abs=1e-4)      # 0.1M output tokens off-peak at $0.60/1M


def test_stops_at_the_cap(monkeypatch, tmp_path):
    start = B.day_start(NOW)
    log = _log(tmp_path, [_call(start + NOON, 400_000)])                    # $0.24
    monkeypatch.setenv(B.ENV, "0.3")
    B.check_before_call(NOW, log)                                         # under the cap: no exception
    monkeypatch.setenv(B.ENV, "0.2")
    with pytest.raises(B.OverBudget) as e:
        B.check_before_call(NOW, log)
    assert "0.2" in str(e.value) and "0.24" in str(e.value)
    monkeypatch.setenv(B.ENV, "off")
    B.check_before_call(NOW, log)                                         # switched off: never stops


def test_exactly_at_the_cap_stops(monkeypatch, tmp_path):
    log = _log(tmp_path, [_call(B.day_start(NOW) + NOON, 500_000)])         # exactly $0.30
    monkeypatch.setenv(B.ENV, "0.3")
    with pytest.raises(B.OverBudget):
        B.check_before_call(NOW, log)


def test_no_log_yet(monkeypatch, tmp_path):
    monkeypatch.setenv(B.ENV, "0.3")
    assert B.spent_today(NOW, tmp_path / "missing.jsonl") == 0.0
    B.check_before_call(NOW, tmp_path / "missing.jsonl")


@pytest.mark.parametrize("usage", [None, {}])
def test_review_missing_usage_uses_the_logged_reservation_and_marks_unknown(monkeypatch, tmp_path, usage):
    from scripts import llm_cost
    call = dict(_call(B.day_start(NOW) + NOON, 0), usage=usage, reserved_usd=0.012)
    log = _log(tmp_path, [call])
    s = llm_cost.summarize(B.day_start(NOW), log)
    assert s["usd"] == pytest.approx(0.012)
    assert s["known_usd"] == 0 and s["reserved_usd"] == pytest.approx(0.012) and s["missing_usage"] == 1
    monkeypatch.setenv(B.ENV, "0.01")
    with pytest.raises(B.OverBudget):
        B.check_before_call(NOW, log)


def test_review_missing_usage_and_reservation_stops_instead_of_inventing_zero(tmp_path):
    from scripts import llm_cost
    log = _log(tmp_path, [dict(_call(B.day_start(NOW) + NOON, 0), usage=None)])
    with pytest.raises(KeyError, match="reserved_usd"):
        llm_cost.summarize(B.day_start(NOW), log)


def test_review_missing_usage_reservation_is_not_rounded_down_for_the_cap(monkeypatch, tmp_path):
    log = _log(tmp_path, [dict(_call(B.day_start(NOW) + NOON, 0), usage=None, reserved_usd=0.0107479)])
    monkeypatch.setenv(B.ENV, "0.01073")
    assert B.spent_today(NOW, log) == pytest.approx(0.0107479)
    with pytest.raises(B.OverBudget):
        B.check_before_call(NOW, log)


@pytest.mark.parametrize("usage", [{"completion_tokens": 12}, {"prompt_tokens": 12}])
def test_review_partial_usage_cannot_silently_count_missing_tokens_as_zero(tmp_path, usage):
    from scripts import llm_cost
    from aitx import session
    log = _log(tmp_path, [dict(_call(B.day_start(NOW) + NOON, 0), usage=usage)])
    with pytest.raises(KeyError):
        llm_cost.summarize(0, log)
    with pytest.raises(KeyError):
        session.cost(usage, NOW.timestamp())


def test_review_known_usage_is_charged_at_its_actual_tokens_not_the_reservation(tmp_path):
    from scripts import llm_cost
    log = _log(tmp_path, [dict(_call(B.day_start(NOW) + NOON, 100000), reserved_usd=1)])
    s = llm_cost.summarize(B.day_start(NOW), log)
    assert s["usd"] == pytest.approx(0.06) and s["missing_usage"] == 0 and s["reserved_usd"] == 0


def test_review_chat_records_the_request_reservation_before_a_usage_missing_response(monkeypatch, tmp_path):
    from aitx import llm
    from scripts import llm_cost
    monkeypatch.delenv("AITX_LLM_CACHE_ONLY", raising=False)
    monkeypatch.setattr(llm, "STREAM", False)
    monkeypatch.setattr(llm, "LOG", tmp_path / "requests.jsonl")
    monkeypatch.setattr(llm, "config", lambda: {"model": "deepseek-flash", "base_url": "https://api.deepseek.com",
        "api_key": "test-only", "expect_model_prefix": "deepseek-flash"})
    response = {"model": "deepseek-flash", "usage": None, "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return json.dumps(response).encode()
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *args, **kwargs: Reply())
    got = llm.chat([{"role": "user", "content": "test"}], max_tokens=4096)
    rec = json.loads(llm.LOG.read_text())
    assert rec["usage"] is None and rec["reserved_usd"] > 0 and got["reserved_usd"] == rec["reserved_usd"]
    s = llm_cost.summarize(0, llm.LOG)
    assert s["usd"] > 0 and s["missing_usage"] == 1 and s["known_usd"] == 0


def test_left_line(monkeypatch, tmp_path):
    log = _log(tmp_path, [_call(B.day_start(NOW) + NOON, 100_000)])
    monkeypatch.setenv(B.ENV, "0.3")
    assert B.left(NOW, log) == "LLM spend today $0.0600 of $0.30 cap ($0.2400 left)"
    monkeypatch.setenv(B.ENV, "off")
    assert B.left(NOW, log) == "LLM spend today $0.0600 (no cap set)"


def test_checked_before_every_call():
    """The cap is checked in the one place every real call goes through, next to the peak check."""
    src = open("aitx/disease/extract.py").read()
    assert "budget.check_before_call()" in src
    i, j = src.index("peak.check_before_call()"), src.index("budget.check_before_call()")
    assert 0 < j - i < 200                      # in the same retry loop, before llm.chat
    assert src.index("llm.chat(", j) > j
    run = open("scripts/run_pipeline.py").read()
    assert "except OverBudget" in run and "return 4" in run

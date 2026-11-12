"""Session log (1a) and ledger attribution (1b), 2026-11-12. Offline: fake LLM, temporary run directory."""
import json

from aitx import session
from aitx.disease import extract as X
from aitx.evidence import ledger as LG

MSG = [{"role": "system", "content": "sys"}, {"role": "user", "content": "the full prompt"}]


def _calls(tmp_path):
    files = list((tmp_path / "runs" / "sessions").rglob("calls.jsonl"))
    return [json.loads(l) for f in files for l in f.read_text().splitlines()]


def _live(monkeypatch, tmp_path, content='{"a": 1}'):
    monkeypatch.setattr(X, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(X.llm, "LOG", tmp_path / "runs" / "llm_calls.jsonl")
    monkeypatch.setattr(X.llm, "config", lambda: {"base_url": "https://api.deepseek.com", "model": "deepseek-flash",
                                                  "api_key": "", "expect_model_prefix": ""})
    sent = []

    def chat(messages, **kw):
        sent.append(messages)
        return {"model": "deepseek-flash", "choices": [{"message": {"content": content, "reasoning_content": "thinking"},
                                                        "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 100,
                          "completion_tokens": 50}}
    monkeypatch.setattr(X.llm, "chat", chat)
    return sent


def test_a_live_call_and_its_cache_hit_are_both_logged_with_one_call_id(monkeypatch, tmp_path):
    sent = _live(monkeypatch, tmp_path)
    session.start(["run_pipeline.py"], "fp")
    t0 = session.step_started("PRAC-X", 3)
    live = X._cached_chat(MSG, 0, True, prompt_version="v1")
    hit = X._cached_chat(MSG, 0, True, prompt_version="v1")
    assert len(sent) == 1 and live["call_id"] == hit["call_id"]
    cached = json.loads(next((tmp_path / "cache").glob("*.json")).read_text())
    assert "call_id" not in cached                         # the cache file itself is unchanged in shape
    a, b = _calls(tmp_path)
    assert a["call_id"] == b["call_id"] == live["call_id"] and (a["case"], a["step"]) == ("PRAC-X", 3)
    assert a["messages"] == MSG and a["content"] == '{"a": 1}' and a["reasoning_content"] == "thinking"
    assert not a["cache_hit"] and a["usd"] > 0 and a["usage"]["completion_tokens"] == 50
    assert b["cache_hit"] and b["usd"] == 0 and b["served_model"] == "deepseek-flash"
    session.step_finished("PRAC-X", 3, t0, "done")
    steps = [json.loads(l) for l in next((tmp_path / "runs" / "sessions").rglob("steps.jsonl")).read_text().splitlines()]
    assert [s["status"] for s in steps] == ["running", "done"] and steps[1]["calls"] == 2 and steps[1]["live_calls"] == 1


def test_a_done_step_is_snapshotted_with_its_input(monkeypatch, tmp_path):
    session.start(["x"], "fp")
    out = tmp_path / "step3.json"
    out.write_text(json.dumps({"ok": True}))
    t0 = session.step_started("PRAC-X", 3)
    session.step_finished("PRAC-X", 3, t0, "done", output=out, upstream={1: "h1"}, case={"id": "PRAC-X"})
    snap = json.loads(next((tmp_path / "runs" / "sessions").rglob("PRAC-X/step3.json")).read_text())
    assert snap["output"] == {"ok": True} and snap["input_case"] == {"id": "PRAC-X"} and snap["upstream"] == {"1": "h1"}


def test_reverse_calls_outside_a_run_go_to_an_adhoc_session(monkeypatch, tmp_path):
    _live(monkeypatch, tmp_path)
    X._cached_chat(MSG, 0, True, prompt_version="v1")
    (c,) = _calls(tmp_path)
    assert c["run_id"] is None and c["case"] is None
    assert next((tmp_path / "runs" / "sessions").glob("adhoc-*")).is_dir()


# --- 1b: ledger attribution

def _ledger():
    br = {"id": "B", "gene": "G", "diagnosis": {"label": "D"}}
    led = LG.Ledger("P", [br])
    src = {"type": "nbk", "id": "NBK1", "url": "u", "section": "s", "credit": "c"}
    e = led.add(LG.sourced("claim", "supportive_management", ["B"], src, "quote", "a quote here", 1,
                           produced_by={"llm": "m", "served_model": "m", "call_id": "abc"}, retrieved_by="3a genereviews",
                           action={"key": "k"}))
    rec = LG.action_record("k", "supportive_management", "thing", ["B"], [], [e["id"]], {"B": "why"})
    rec["context_check"] = {"call_ids": ["v1", "v2", "v3"], "limit_followup": {"q": {"call_ids": ["f1", "f2", "f3"]}}}
    led.actions.append(rec)
    return led


def test_actions_name_the_calls_rules_and_votes_behind_them():
    a = _ledger().to_dict()["actions"][0]
    assert a["provenance"] == {"llm_calls": ["abc"], "rules": ["3a genereviews"], "code_only": False,
                               "check_calls": ["v1", "v2", "v3", "f1", "f2", "f3"]}
    chk = next(c for c in _ledger().checks() if c["name"] == "llm_calls_attributed")
    assert chk["status"] == "pass"


def test_reverse_an_llm_item_without_a_call_id_is_flagged():
    led = _ledger()
    next(iter(led.evidence.values()))["produced_by"].pop("call_id")
    chk = next(c for c in led.checks() if c["name"] == "llm_calls_attributed")
    assert chk["status"] == "warn"

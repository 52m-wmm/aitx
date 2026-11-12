"""Session log (1a, 2026-11-12): every LLM call - cache hits included - and every pipeline step, kept locally.

    runs/sessions/<run_id>/meta.json        run arguments, code fingerprint, start time
    runs/sessions/<run_id>/calls.jsonl      one line per LLM call: call id, case, step, prompt version, full prompt,
                                            raw answer, requested / served model, provider, cache hit, tokens, cost,
                                            seconds
    runs/sessions/<run_id>/steps.jsonl      one line per step event: running / done / failed, seconds, cost, calls
    runs/sessions/<run_id>/<case>/step<N>.json   snapshot of the step's input fingerprints and its output

`runs/` is not in the repository (.gitignore). Calls made outside a pipeline run (acceptance and validation scripts)
go to runs/sessions/adhoc-<date>/. The call id is the LLM cache key - content-addressed, so a cache hit and the live
call that produced it carry the same id, and ledger records can point at it (1b).

The pipeline runs cases one after another, so the current case and step are module state (worker threads of one step
inherit them); the log is appended under a lock.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_lock = threading.Lock()
_state: dict = {"run_id": None, "dir": None, "case": None, "step": None}
_step_calls: dict = {"n": 0, "live": 0, "usd": 0.0}


def base() -> Path:
    return Path(os.environ.get("AITX_RUN_DIR", ROOT / "runs")) / "sessions"


def start(argv: list[str], code_fingerprint: str = "") -> str:
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
    d = base() / run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps({"run_id": run_id, "argv": argv, "code_fingerprint": code_fingerprint,
                                             "started": time.time()}, indent=1))
    _state.update(run_id=run_id, dir=d, case=None, step=None)
    return run_id


def current() -> dict:
    return {"run_id": _state["run_id"], "case": _state["case"], "step": _state["step"]}


def _dir() -> Path:
    if _state["dir"] is not None:
        return _state["dir"]
    d = base() / f"adhoc-{time.strftime('%Y%m%d')}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _append(name: str, rec: dict) -> None:
    with _lock:
        with (_dir() / name).open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cost(usage: dict | None, ts: float) -> float:
    """USD for one live call, priced by scripts/llm_cost.py (the single pricing table)."""
    if not usage:
        return 0.0
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import llm_cost
    hit = usage.get("prompt_cache_hit_tokens", 0)
    miss = usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0) - hit)
    i = 1 if llm_cost.peak(ts) else 0
    p = llm_cost.PRICE
    return (hit * p["cache_hit"][i] + miss * p["cache_miss"][i] + usage.get("completion_tokens", 0) * p["output"][i]) / 1e6


def log_call(*, call_id: str, messages: list[dict], entry: dict, cache_hit: bool, k: int, params: dict,
             usage: dict | None = None, seconds: float = 0.0, reasoning: str | None = None) -> None:
    ts = time.time()
    usd = 0.0 if cache_hit else cost(usage, ts)
    rec = {"call_id": call_id, "at": ts, **current(), "prompt_version": entry.get("prompt_version"), "sample": k,
           "requested_model": entry.get("requested_model"), "served_model": entry.get("served_model"),
           "provider": entry.get("provider"), "cache_hit": cache_hit, "call_params": params, "messages": messages,
           "content": entry.get("content"), "usage": usage, "usd": round(usd, 6), "seconds": round(seconds, 2)}
    if reasoning:
        rec["reasoning_content"] = reasoning
    with _lock:
        _step_calls["n"] += 1
        _step_calls["live"] += 0 if cache_hit else 1
        _step_calls["usd"] += usd
    _append("calls.jsonl", rec)


def step_started(case_id: str, step: int) -> float:
    _state.update(case=case_id, step=step)
    with _lock:
        _step_calls.update(n=0, live=0, usd=0.0)
    _append("steps.jsonl", {"at": time.time(), "case": case_id, "step": step, "status": "running"})
    return time.time()


def step_finished(case_id: str, step: int, t0: float, status: str, *, output: Path | None = None,
                  upstream: dict | None = None, case: dict | None = None, error: str | None = None) -> None:
    """status: done / failed / stopped. A done step's output is copied into the session (input fingerprints too)."""
    with _lock:
        calls = dict(_step_calls)
    rec = {"at": time.time(), "case": case_id, "step": step, "status": status, "seconds": round(time.time() - t0, 1),
           "calls": calls["n"], "live_calls": calls["live"], "usd": round(calls["usd"], 6)}
    if error:
        rec["error"] = error[:500]
    if output is not None and Path(output).exists():
        snap = _dir() / case_id / f"step{step}.json"
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(json.dumps({"case": case_id, "step": step, "input_case": case, "upstream": upstream or {},
                                    "output_file": str(output), "output": json.loads(Path(output).read_text())},
                                   ensure_ascii=False))
        rec["snapshot"] = str(snap)
    _append("steps.jsonl", rec)
    _state.update(case=None, step=None)

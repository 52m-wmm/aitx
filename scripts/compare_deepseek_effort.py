"""DeepSeek with another reasoning_effort on the context-check validation set (experiment, 2026-11-12; user-approved
run, cap $0.03 for both temperatures). Changes no pipeline code; the production result in out/ is never written.

Same 26 entries, prompts and decision code as scripts/validate_context_check.py; only the call parameters differ
(reasoning_effort, temperature). Isolation:
  - LLM cache in out_alt/<label>/cache: the production cache key does not include the call parameters, so a shared
    cache would make these calls overwrite the production entries for the same prompts;
  - the calls ARE logged to runs/llm_calls.jsonl (real spend: the daily cap and the cost report must see them);
  - result in out_alt/<label>/context_check_validation.json, per-call timing in out_alt/<label>/calls.jsonl.

Usage (off-peak, with AITX_LLM_API_KEY and AITX_LLM_BUDGET_USD set by the caller):
    python3 scripts/compare_deepseek_effort.py --effort none --temperature 0
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--effort", required=True, choices=("none", "low", "high", "max"))
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()
    label = f"deepseek-{args.effort}-t{args.temperature:g}"
    out = ROOT / "out_alt" / label
    out.mkdir(parents=True, exist_ok=True)
    os.environ["AITX_LLM_CACHE_DIR"] = str(out / "cache")
    if not os.environ.get("AITX_LLM_API_KEY"):
        print("set AITX_LLM_API_KEY")
        return 2

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    from aitx import llm, peak
    from aitx.disease import extract as X
    from aitx.evidence import context_check as CC
    import validate_context_check as V

    assert X.CACHE_DIR == out / "cache"
    assert llm.config()["base_url"].startswith("https://api.deepseek.com")
    peak.guard()
    real_chat, calls_log = llm.chat, out / "calls.jsonl"

    def chat(messages, **kw):
        t0 = time.time()
        resp = real_chat(messages, **kw)
        content = resp["choices"][0]["message"].get("content") or ""
        try:
            json.loads(content)
            bad = False
        except json.JSONDecodeError:
            bad = True
        with calls_log.open("a") as f:
            f.write(json.dumps({"ts": t0, "seconds": round(time.time() - t0, 2), "served": resp.get("model"),
                                "usage": resp.get("usage"), "error": None, "bad_json": bad}) + "\n")
        return resp
    llm.chat = chat

    CC.CALL_PARAMS = {**CC.CALL_PARAMS, "reasoning_effort": args.effort, "temperature": args.temperature}
    V.OUT = out / "context_check_validation.json"
    (out / "run_meta.json").write_text(json.dumps({"label": label, "call_params": CC.CALL_PARAMS,
                                                   "prompt_version": CC.PROMPT_VERSION, "started": int(time.time()),
                                                   "note": "in-sample: v3 questions were revised on these 26 entries"},
                                                  indent=1))
    sys.argv = [sys.argv[0], "--offpeak-only"]
    return V.main()


if __name__ == "__main__":
    raise SystemExit(main())

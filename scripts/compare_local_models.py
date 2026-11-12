"""Local-model comparison on the context-check validation set (experiment, 2026-11-12). Changes no pipeline code.

Runs the same 26 judged entries as scripts/validate_context_check.py (same prompts, same decision code, same harm
measure) against a model served by LM Studio on this Mac, and writes everything under out_alt/<label>/.

Isolation (all set here, before any aitx import):
  - endpoint fixed to the local LM Studio server; every call is checked to go to localhost, and the DeepSeek key is
    removed from this process, so a local failure can never fall back to the paid API;
  - LLM cache in out_alt/<label>/cache, call log in out_alt/<label>/runs (not .cache/llm, not runs/);
  - the daily spend cap is off for this process (local calls cost nothing and are not in the DeepSeek log);
  - results go to out_alt/<label>/context_check_validation.json (the DeepSeek result in out/ is never written).
Call parameters: the pipeline's CALL_PARAMS without reasoning_effort (not supported locally); --json picks the
response_format (object = as DeepSeek, schema = JSON Schema of the same answer shape, none = prompt only).

Usage:
    python3 scripts/compare_local_models.py --model qwen3.5-9b --label qwen3.5-9b-mlx-4bit --smoke 3
    python3 scripts/compare_local_models.py --model qwen3.5-9b --label qwen3.5-9b-mlx-4bit
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LOCAL = "http://127.0.0.1:1234/v1"

SCHEMA = {"type": "json_schema", "json_schema": {"name": "context_check_answers", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["answers"],
    "properties": {"answers": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["q", "answer", "quote"],
        "properties": {"q": {"type": "integer"}, "answer": {"type": "string"}, "quote": {"type": "string"}}}}}}}}


def isolate(model: str, out: Path) -> None:
    for k in ("DEEPSEEK_API_KEY", "AITX_LLM_API_KEY"):
        os.environ.pop(k, None)
    os.environ.update({
        "AITX_LLM_BASE_URL": LOCAL, "AITX_LLM_MODEL": model, "AITX_LLM_API_KEY": "local-no-key",
        "AITX_EXPECT_MODEL_PREFIX": model, "AITX_LLM_CACHE_DIR": str(out / "cache"), "AITX_RUN_DIR": str(out / "runs"),
        "AITX_LLM_BUDGET_USD": "off", "AITX_LLM_TIMEOUT": "1800", "AITX_LLM_CACHE_ONLY": "0"})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="model id as LM Studio serves it")
    ap.add_argument("--label", required=True, help="directory name under out_alt/ (model, backend, quantization)")
    ap.add_argument("--json", choices=("object", "schema", "none"), default="object")
    ap.add_argument("--temperature", type=float, default=0.0, help="0 as the pipeline; 0.7 to see independent votes")
    ap.add_argument("--smoke", type=int, default=0, help="only the first N entries (wrong 3a, wrong 3c, correct)")
    args = ap.parse_args()
    out = ROOT / "out_alt" / args.label
    out.mkdir(parents=True, exist_ok=True)
    isolate(args.model, out)

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    from aitx import llm
    from aitx.disease import extract as X
    from aitx.evidence import context_check as CC
    import validate_context_check as V

    assert urlparse(llm.config()["base_url"]).hostname in ("127.0.0.1", "localhost")
    assert X.CACHE_DIR == out / "cache" and llm.LOG == out / "runs" / "llm_calls.jsonl"
    real_chat, calls_log = llm.chat, out / "calls.jsonl"

    def chat(messages, **kw):                       # every call: localhost only, logged with timing and JSON validity
        cfg = llm.config()
        if urlparse(cfg["base_url"]).hostname not in ("127.0.0.1", "localhost"):
            raise SystemExit(f"refusing a non-local endpoint: {cfg['base_url']}")
        t0 = time.time()
        err = None
        try:
            resp = real_chat(messages, **kw)
        except Exception as e:                      # noqa: BLE001 - recorded, then re-raised (no fallback)
            err, resp = f"{type(e).__name__}: {e}", None
        msg = (resp or {}).get("choices", [{}])[0].get("message", {}) if resp else {}
        from_reasoning = False
        if msg and not (msg.get("content") or "").strip() and msg.get("reasoning_content"):
            # LM Studio + JSON Schema + Qwen3.5: the model writes the JSON at once and the server files it as
            # reasoning_content (decision 2026-11-12: take it when it is valid JSON; experiment script only)
            try:
                json.loads(msg["reasoning_content"])
                msg["content"], from_reasoning = msg["reasoning_content"], True
            except json.JSONDecodeError:
                pass
        content = msg.get("content") or ""
        try:
            json.loads(content)
            bad_json = False
        except (json.JSONDecodeError, TypeError):
            bad_json = True
        with calls_log.open("a") as f:
            f.write(json.dumps({"ts": t0, "seconds": round(time.time() - t0, 2), "served": (resp or {}).get("model"),
                                "usage": (resp or {}).get("usage"), "error": err, "bad_json": bad_json,
                                "reasoning_chars": len(msg.get("reasoning_content") or ""), "from_reasoning": from_reasoning,
                                "content": content}, ensure_ascii=False) + "\n")
        if err:
            raise RuntimeError(err)
        return resp
    llm.chat = chat

    params = {k: v for k, v in CC.CALL_PARAMS.items() if k != "reasoning_effort"}
    params["temperature"] = args.temperature
    if args.json == "schema":
        params["response_format"] = SCHEMA
    elif args.json == "none":
        params.pop("response_format", None)
    CC.CALL_PARAMS = params
    V.OUT = out / "context_check_validation.json"
    meta = {"model": args.model, "label": args.label, "endpoint": LOCAL, "json_mode": args.json,
            "call_params": params, "temperature": args.temperature, "prompt_version": CC.PROMPT_VERSION, "started": int(time.time())}
    (out / "run_meta.json").write_text(json.dumps(meta, indent=1))

    if args.smoke:
        entries = V.build_set()
        pick = [next(e for e in entries if e["verdict"] == "wrong" and e["section"] in V.S3A),
                next(e for e in entries if e["verdict"] == "wrong" and e["section"] == V.S3C),
                next(e for e in entries if e["verdict"] == "correct")][:args.smoke]
        for e in pick:
            c = V.checks_for(e)[0]
            t0 = time.time()
            res = CC.ask(c["header"], c["passage"], c["patient"], c["questions"])
            print(f"\n== {e['verdict']} {e['case']} {e['label']}  ({time.time() - t0:.0f}s, served {res['llm']})")
            for q in res["questions"]:
                print(f"  {q['id']:14} final {q['final']:12} votes {q['answers']}")
        rows = [json.loads(l) for l in calls_log.read_text().splitlines()]
        print(f"\ncalls {len(rows)}, bad JSON {sum(r['bad_json'] for r in rows)}, errors {sum(bool(r['error']) for r in rows)}, "
              f"with reasoning_content {sum(r['reasoning_chars'] > 0 for r in rows)}, "
              f"mean {sum(r['seconds'] for r in rows) / max(len(rows), 1):.1f}s")
        return 0
    sys.argv = [sys.argv[0]]
    return V.main()


if __name__ == "__main__":
    raise SystemExit(main())

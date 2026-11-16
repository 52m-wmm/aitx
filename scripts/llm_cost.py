"""LLM token use and cost from runs/llm_calls.jsonl (every real call is logged there with its usage).

Usage:  python3 scripts/llm_cost.py --since 1793760000      # calls at or after this Unix time
        python3 scripts/llm_cost.py --last-minutes 30

Prices: DeepSeek pricing page (api-docs.deepseek.com/quick_start/pricing, read 2026-11-03), model deepseek-flash,
USD per 1M tokens. Peak windows come from config/llm_peak_hours.json (US Pacific time), the same file the
--offpeak-only guard reads (Chinese public holidays are not handled: billed off-peak, so a holiday run is overstated). Cached LLM answers cost nothing and are not logged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "runs" / "llm_calls.jsonl"
PRICE = {   # (off-peak, peak) per 1M tokens
    "cache_hit": (0.003, 0.006), "cache_miss": (0.15, 0.30), "output": (0.60, 1.20),
}


def peak(ts: float) -> bool:
    """Same windows as the --offpeak-only guard (config/llm_peak_hours.json)."""
    from aitx import peak as P
    return P.current_window(dt.datetime.fromtimestamp(ts, dt.timezone.utc)) is not None


def request_reservation(messages: list[dict], max_tokens: int, ts: float, tools: list[dict] | None = None) -> float:
    """Conservative maximum: one token per input UTF-8 byte, chat overhead, and the requested output limit."""
    wire = json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False).encode()
    i = int(peak(ts))
    return ((len(wire) + 1024 + 256 * len(messages)) * PRICE["cache_miss"][i]
            + max_tokens * PRICE["output"][i]) / 1e6 + 0.0001


def summarize(since: float, log: Path = LOG) -> dict:
    out = {"calls": 0, "cache_hit": 0, "cache_miss": 0, "output": 0, "reasoning": 0, "usd": 0.0, "peak_calls": 0,
           "known_usd": 0.0, "reserved_usd": 0.0, "missing_usage": 0}
    for line in log.read_text().splitlines():
        r = json.loads(line)
        if r["ts"] < since:
            continue
        out["peak_calls"] += int(peak(r["ts"]))
        out["calls"] += 1
        u = r.get("usage")
        if u is not None and not isinstance(u, dict):
            raise ValueError("LLM usage must be an object or null")
        if not u:
            out["reserved_usd"] += r["reserved_usd"]  # no reservation recorded: stop, never substitute zero
            out["missing_usage"] += 1
            continue
        hit = u.get("prompt_cache_hit_tokens", 0)
        miss = u["prompt_cache_miss_tokens"] if "prompt_cache_miss_tokens" in u else u["prompt_tokens"] - hit
        outp = u["completion_tokens"]
        i = 1 if peak(r["ts"]) else 0
        out["cache_hit"] += hit
        out["cache_miss"] += miss
        out["output"] += outp
        out["reasoning"] += (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
        out["known_usd"] += (hit * PRICE["cache_hit"][i] + miss * PRICE["cache_miss"][i] + outp * PRICE["output"][i]) / 1e6
    out["usd"] = out["known_usd"] + out["reserved_usd"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=float)
    ap.add_argument("--last-minutes", type=float)
    args = ap.parse_args()
    since = args.since if args.since is not None else time.time() - 60 * (args.last_minutes or 60)
    s = summarize(since)
    print(f"{s['calls']} LLM calls ({s['peak_calls']} at peak rates): input {s['cache_hit']:,} cached + "
          f"{s['cache_miss']:,} uncached tokens, output {s['output']:,} tokens ({s['reasoning']:,} reasoning) "
          f"-> ${s['known_usd']:.4f} with known usage")
    if s["missing_usage"]:
        print(f"{s['missing_usage']} request(s) have missing usage: actual cost unknown; "
              f"${s['reserved_usd']:.6f} reserved, budget accounting ${s['usd']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Quote a rerun from the LLM cache alone (no paid call, nothing written to out/). 2026-11-12.

Runs steps 1-3 in memory for the given case files with AITX_LLM_CACHE_ONLY=1; every call the cache cannot answer is
counted (by case and prompt version) and answered with an empty JSON object so the run goes on. The quote is the
count times the measured price per call of that prompt version (live calls in runs/sessions/*/calls.jsonl).
Calls that an empty answer never triggers (a follow-up after a limit was found, for instance) are not counted, so the
quote is a floor; the worst case adds a margin.

Usage: python3 scripts/dry_run_quote.py data/cases/practice/official_examples.json data/cases/blind/retest-20261112.json
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys
from pathlib import Path

os.environ["AITX_LLM_CACHE_ONLY"] = "1"
os.environ["AITX_LLM_BUDGET_USD"] = "0"
os.environ.pop("AITX_LLM_API_KEY", None)
ROOT = Path(__file__).resolve().parents[1]
os.environ["AITX_RUN_DIR"] = str(ROOT / "out_alt" / "dry_run")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from aitx import llm  # noqa: E402
from aitx.disease import extract as X  # noqa: E402

MISS: collections.Counter = collections.Counter()
CURRENT = {"case": None}


def unit_prices() -> dict[str, float]:
    by = collections.defaultdict(lambda: [0, 0.0])
    for f in glob.glob(str(ROOT / "runs" / "sessions" / "*" / "calls.jsonl")):
        for line in open(f):
            x = json.loads(line)
            if not x["cache_hit"]:
                by[x["prompt_version"]][0] += 1
                by[x["prompt_version"]][1] += x["usd"]
    return {k: u / n for k, (n, u) in by.items() if n}


def main() -> int:
    real = X._cached_chat

    def counting(messages, k, use_cache, prompt_version=None, call_params=None):
        try:
            return real(messages, k, use_cache, prompt_version=prompt_version, call_params=call_params)
        except (llm.CacheOnly, Exception) as e:          # noqa: BLE001 - CacheOnly, or the budget guard at 0
            if not isinstance(e, llm.CacheOnly) and "budget" not in type(e).__name__.lower() \
                    and "OverBudget" not in type(e).__name__:
                raise
            MISS[(CURRENT["case"], prompt_version or X.PROMPT_VERSION)] += 1
            return {"content": "{}", "served_model": "dry-run", "call_id": "dry-run"}
    X._cached_chat = counting
    import run_pipeline as RP
    cases = [c for f in sys.argv[1:] for c in json.loads(Path(f).read_text())]
    ctx = RP.Context(cases, True)
    for case in cases:
        CURRENT["case"] = case["id"]
        try:
            s1 = RP.step1(case, {}, ctx)
            s2 = RP.step2(case, {1: s1}, ctx)
            RP.step3(case, {1: s1, 2: s2}, ctx)
            print(f"{case['id']}: done, uncached {sum(v for (c, _), v in MISS.items() if c == case['id'])}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"{case['id']}: stopped ({type(e).__name__}: {str(e)[:120]})", flush=True)
    price = unit_prices()
    total = 0.0
    print("\nuncached calls by case and prompt version (price per call measured in today's sessions):")
    for (c, pv), n in sorted(MISS.items()):
        u = price.get(pv, 0.001)
        total += n * u
        print(f"  {c:22} {pv:22} {n:4} x ${u:.5f} = ${n * u:.4f}")
    print(f"\nTOTAL ${total:.3f} (floor); worst with a 1.5x margin ${total * 1.5:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

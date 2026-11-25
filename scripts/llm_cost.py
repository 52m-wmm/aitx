"""CLI for LLM token use and costs; implementation is in aitx.llm_cost."""
import argparse
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aitx.llm_cost import LOG, PRICE, peak, request_reservation, summarize


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

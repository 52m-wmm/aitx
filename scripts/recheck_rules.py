"""Run the support check again on rules whose conditions were narrowed by hand, without redrafting them.

draft_rules.py would ask the LLM to draft the gene's rules afresh and would overwrite a hand-narrowed
condition. This script keeps the rule exactly as written and only re-runs the support check (step 3.0
contract, section 4) on it, so a reviewer can see whether the quotes support the narrowed wording.

Usage:
    python3 scripts/recheck_rules.py --rule COL1A1-1 --rule COL1A1-4 --estimate     # cost estimate only
    python3 scripts/recheck_rules.py --rule COL1A1-1 --offpeak-only                 # run it

A rule is rewritten in place with its new support_check, and its status is set from the result:
"verified" when the check finds it supported, otherwise "pending_review" (a reviewer may still accept it
with a reason, as before). Needs AITX_LLM_API_KEY unless every answer is cached.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from aitx import budget, peak  # noqa: E402
from aitx.evidence import rules as RU  # noqa: E402
from aitx.evidence import support_check as SC  # noqa: E402

N_CHECKS = SC.N_CHECKS
PRICE_OUT = 0.60 / 1e6          # off-peak output price (scripts/llm_cost.py)
PRICE_IN = 0.15 / 1e6
SEEN_OUTPUT_TOKENS = 1400       # one judgement of one rule, from the earlier runs in runs/llm_calls.jsonl
SEEN_INPUT_TOKENS = 700


def names_for(gene: str) -> dict[str, dict]:
    """OMIM id -> step 2 candidate names, as the drafting step supplies them (never the rule's own wording)."""
    out: dict[str, dict] = {}
    for f in sorted((ROOT / "out" / "step2").glob("*.json")):
        r = json.loads(f.read_text())
        if not isinstance(r, dict):                # some step 2 files hold a list (older runs)
            continue
        for c in r.get("candidates") or []:
            if c.get("gene") != gene:
                continue
            for o in c.get("omim") or []:
                out.setdefault(o["id"], {"label": c.get("label"), "synonyms": c.get("synonyms") or []})
    return out


def find(rule_ids: list[str]) -> list[tuple[Path, dict, list[dict]]]:
    found = []
    for f in sorted(RU.RULES_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        for r in data.get("rules") or []:
            if r["id"] in rule_ids:
                found.append((f, data, r))
    missing = set(rule_ids) - {r["id"] for _, _, r in found}
    if missing:
        raise SystemExit(f"no such rule: {sorted(missing)}")
    return found


def estimate(n_rules: int) -> str:
    calls = n_rules * N_CHECKS
    usd = calls * (SEEN_INPUT_TOKENS * PRICE_IN + SEEN_OUTPUT_TOKENS * PRICE_OUT)
    return (f"{n_rules} rules x {N_CHECKS} judgements = {calls} LLM calls; about {SEEN_INPUT_TOKENS} input and "
            f"{SEEN_OUTPUT_TOKENS} output tokens each (seen in earlier runs) -> about ${usd:.3f} off-peak")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", action="append", required=True, help="rule id (repeatable)")
    ap.add_argument("--estimate", action="store_true", help="print the cost estimate and stop")
    ap.add_argument("--offpeak-only", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()
    found = find(args.rule)
    print(estimate(len(found)))
    if args.estimate:
        return 0
    if args.offpeak_only:
        peak.guard()
    print(budget.left())
    changed: dict[Path, dict] = {}
    for f, data, r in found:
        items = SC.rule_items(r, names_for(r["gene"]))
        quotes = [s["quote"] for s in r.get("sources") or []]
        sc = SC.check_support(f"{r['gene']} rule: {r['statement']}", items, quotes, use_cache=not args.no_cache)
        r["support_check"] = sc
        r.pop("support_check_superseded", None)
        r["status"] = "verified" if sc["overall"] == "supported" else "pending_review"
        r["content_sha256"] = RU.content_hash(r)
        changed[f] = data
        print(f"\n{r['id']} (v{r.get('version')}): {sc['overall']} -> status {r['status']}")
        for it in sc["items"]:
            print(f"  [{it['verdict']}] {it['item'][:110]}")
            print(f"      judgements {it['judgements']}; reason: {it['reason'][:220]}")
        print("  problems:", RU.validate(r) or "none")
    for f, data in changed.items():
        f.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        print(f"\nwritten {f.relative_to(ROOT)}")
    print(budget.left())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

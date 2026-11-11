"""Regression set for the support check (aitx/evidence/support_check.py).

Every rule a person has reviewed (accepted or vetoed, with the reason) becomes a labelled case:
  accepted -> the check should find it supported
  vetoed   -> the check should NOT find it supported (block it)
Cases are collected from data/rules/*.json into data/eval/support_check_regression.json, keyed by rule
identity (statement, conditions, effect, quotes); new reviews are appended, nothing is removed.

Before adopting any change to the check's prompt or decision method, run this and compare with the
previous result: accuracy, false passes (should block, was supported) and false blocks (should pass,
was blocked). False passes are worse than false blocks; a change that makes them worse is not adopted.
Test cases must never appear in the check's prompt (leak guard below).

Usage:  python3 scripts/eval_support_check.py            # collect new reviews, then evaluate
        python3 scripts/eval_support_check.py --collect  # only collect
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx.evidence import support_check as SC  # noqa: E402
from aitx.evidence.rules import RULES_DIR, identity  # noqa: E402

SET = ROOT / "data" / "eval" / "support_check_regression.json"


def collect(rules_dir: Path = RULES_DIR, path: Path = SET) -> list[str]:
    """Append reviewed rules not yet in the set (or with a changed decision). Returns added ids."""
    data = json.loads(path.read_text()) if path.exists() else {
        "description": "Support-check regression cases: rules a person reviewed. expected = supported (accepted) "
                       "or blocked (vetoed). Collected automatically; never used as prompt examples.", "cases": []}
    by_id = {c["identity"]: c for c in data["cases"]}
    added = []
    for f in sorted(rules_dir.glob("*.json")):
        doc = json.loads(f.read_text())
        names = {o: {"label": c["label"], "synonyms": c.get("synonyms") or []} for c in doc.get("candidates", [])
                 for o in c["omim"]}
        for r in doc.get("rules", []):
            rev = r.get("review") or {}
            if rev.get("decision") not in ("accepted", "vetoed"):
                continue
            ident = identity(r)
            expected = "supported" if rev["decision"] == "accepted" else "blocked"
            old = by_id.get(ident)
            if old and old["expected"] == expected:
                continue
            case = {"identity": ident, "rule_id": r["id"], "gene": r["gene"], "expected": expected,
                    "review": rev, "collected_at": time.strftime("%Y-%m-%d"),
                    "rule": {k: r[k] for k in ("gene", "statement", "applies_when", "effect")}
                    | {"sources": [{"quote": s["quote"]} for s in r["sources"]]},
                    "names": {o: names[o] for o in r["effect"].get("supports", []) + r["effect"].get("argues_against", [])
                              if o in names}}
            if old:
                case["history"] = old.get("history", []) + [{"expected": old["expected"], "review": old["review"]}]
                data["cases"] = [c for c in data["cases"] if c["identity"] != ident]
            data["cases"].append(case)
            by_id[ident] = case
            added.append(r["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return added


def case_quotes(c: dict) -> list[str]:
    if c.get("kind") == "same_action":
        return [x["quote"] for x in c["entries"]]
    if c.get("kind") == "claim":
        return list(c["claim"]["quotes"]) + list(c["claim"].get("context_quotes") or [])
    return [s["quote"] for s in c["rule"]["sources"]]


def leaks(cases: list[dict]) -> list[str]:
    """Test material that appears in the check's prompt (must be empty)."""
    out = []
    for c in cases:
        if c["gene"] in SC.SYSTEM:
            out.append(f"{c['rule_id']}: gene {c['gene']} in prompt")
        for q in case_quotes(c):
            if q[:40] and q[:40] in SC.SYSTEM:
                out.append(f"{c['rule_id']}: quote in prompt")
    return out


def check_case(c: dict, use_cache: bool) -> dict:
    """A reviewed rule goes through check_rule; a report claim (kind 'claim', added 2026-11-11) is judged with its
    quotes AND its context quotes - the case records that the check needs the full context (who the patients are)."""
    if c.get("kind") == "claim":
        return SC.check_support(c["claim"]["topic"], c["claim"]["items"], case_quotes(c), use_cache=use_cache)
    return SC.check_rule(c["rule"], c["names"], use_cache=use_cache)


def evaluate(cases: list[dict], *, use_cache: bool = True) -> dict:
    # same_action cases (2026-11-11) have no judge yet: listed, not scored
    unscored = [c["rule_id"] for c in cases if c.get("kind") == "same_action"]
    cases = [c for c in cases if c.get("kind") != "same_action"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda c: check_case(c, use_cache), cases))
    rows, fp, fb, ok = [], [], [], 0
    for c, r in zip(cases, results):
        passed = r["overall"] == "supported"
        right = passed == (c["expected"] == "supported")
        ok += right
        if c["expected"] == "blocked" and passed:
            fp.append(c["rule_id"])
        if c["expected"] == "supported" and not passed:
            fb.append(c["rule_id"])
        rows.append({"rule_id": c["rule_id"], "expected": c["expected"], "check": r["overall"], "correct": right,
                     "items": [(i["item"].split(":")[0], i["judgements"]) for i in r["items"]]})
    n = len(cases)
    return {"prompt_version": SC.PROMPT_VERSION, "n_checks": SC.N_CHECKS, "n": n,
            "accuracy": round(ok / n, 3) if n else None, "false_pass": fp, "false_block": fb, "rows": rows,
            "unscored": unscored}


def report(r: dict) -> None:
    print(f"support check {r['prompt_version']} (x{r['n_checks']}): {r['n']} cases, accuracy {r['accuracy']}, "
          f"false passes {len(r['false_pass'])} {r['false_pass']}, false blocks {len(r['false_block'])} {r['false_block']}")
    if r.get("unscored"):
        print(f"  not scored (no cross-section judge yet): {r['unscored']}")
    for row in r["rows"]:
        print(f"  {'OK ' if row['correct'] else 'BAD'} {row['rule_id']:<10} expected {row['expected']:<9} check {row['check']:<20} {row['items']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="only collect new reviews")
    ap.add_argument("--offpeak-only", action="store_true",
                    help="exit without LLM calls during the provider's peak-price hours (config/llm_peak_hours.json)")
    args = ap.parse_args()
    if args.offpeak_only:
        from aitx import peak
        peak.guard()
    added = collect()
    print(f"collected {len(added)} new case(s): {added}")
    if args.collect:
        return 0
    cases = json.loads(SET.read_text())["cases"]
    bad = leaks(cases)
    if bad:
        print("LEAK: test cases appear in the prompt:\n  " + "\n  ".join(bad))
        return 2
    r = evaluate(cases)
    report(r)
    out = ROOT / "out" / f"eval_support_check_{r['prompt_version']}.json"
    out.write_text(json.dumps(r, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

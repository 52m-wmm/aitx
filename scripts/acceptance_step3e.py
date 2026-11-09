"""Step 3e acceptance (docs/step3e_contract.md): verified expectations vs the 3e rows in out/step3.

Usage:  python3 scripts/acceptance_step3e.py     # exit 0 when every expectation holds on a fresh ledger

Writes out/acceptance/step3e.json. Only fresh ledgers are scored (runmeta.freshness); a stale case is reported
and not counted. The summary also prints, per case, how many drug records were returned and how many were
excluded for direction, which is the number that shows whether the direction rule is doing its work.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx import runmeta  # noqa: E402

EXPECT = ROOT / "data" / "eval" / "step3e_expectations.json"
RESULT = ROOT / "out" / "acceptance" / "step3e.json"
SECTION = "drug_repurposing"


def rows(led: dict, branch: str | None) -> list[dict]:
    return [a for a in led.get("actions", []) if a.get("section") == SECTION
            and (branch is None or branch in a.get("applies_to", []))]


def compare(item: dict, led: dict | None) -> dict:
    if led is None:
        return {"ok": False, "actual": None, "problem": "no step 3 ledger for this case"}
    want, probs = item["expect"], []
    got = rows(led, item.get("branch"))
    labels = {str(a.get("label") or "").upper() for a in got}
    searched = led.get("repurposing_searches") or {}
    one = next(iter(searched.values()), {}) if searched else {}

    row = None
    if want.get("present"):
        row = next((a for a in got if str(a.get("label") or "").upper() == want["present"].upper()), None)
        if row is None:
            probs.append(f"{want['present']} is not in the section (kept: {sorted(labels)})")
    for name in want.get("absent") or []:
        if name.upper() in labels:
            probs.append(f"{name} must not be in the section")
    if want.get("excluded_reason_contains"):
        whys = " | ".join(str(x.get("why") or "") for s in searched.values() for x in s.get("excluded") or [])
        if want["excluded_reason_contains"] not in whys:
            probs.append(f"no excluded record saying '{want['excluded_reason_contains']}'")
    if row is not None:
        if want.get("direction") and row.get("direction") != want["direction"]:
            probs.append(f"direction {row.get('direction')} (want {want['direction']})")
        if want.get("target_level") and row.get("target_level") != want["target_level"]:
            probs.append(f"target_level {row.get('target_level')} (want {want['target_level']})")
        if want.get("evidence_level_in") and row.get("evidence_level") not in want["evidence_level_in"]:
            probs.append(f"evidence_level {row.get('evidence_level')} not in {want['evidence_level_in']}")
        for s in want.get("conclusion_contains") or []:
            if s not in (row.get("conclusion") or ""):
                probs.append(f"conclusion lacks '{s}'")
        for s in want.get("conclusion_lacks") or []:
            if s in (row.get("conclusion") or "").lower():
                probs.append(f"conclusion contains '{s}'")
        if row.get("human_precedent"):
            probs.append("has a human precedent, so it belongs in 3c")
    if want.get("all_target_levels") is not None and got:
        levels = sorted({a.get("target_level") for a in got})
        if levels != sorted(want["all_target_levels"]):
            probs.append(f"target levels {levels} (want {sorted(want['all_target_levels'])})")
    if want.get("subunit_level_molecules") is not None and one:
        if one.get("subunit_level_molecules") != want["subunit_level_molecules"]:
            probs.append(f"subunit_level_molecules {one.get('subunit_level_molecules')} "
                         f"(want {want['subunit_level_molecules']})")
    if want.get("no_actions") and got:
        probs.append(f"candidates were written although none should be: {sorted(labels)}")
    if want.get("candidates") is not None and one and one.get("candidates") != want["candidates"]:
        probs.append(f"{one.get('candidates')} candidates matched the direction (want {want['candidates']})")
    if want.get("negative_evidence"):
        neg = [e for e in led.get("evidence", []) if e.get("section") == SECTION and e.get("kind") == "negative"
               and e.get("status") == "verified"]
        if not neg:
            probs.append("no verified 'searched, found nothing' record for this section")
    return {"ok": not probs, "problem": "; ".join(probs) or None,
            "actual": {"kept": sorted(labels), "search": {k: {x: v.get(x) for x in
                       ("mechanism", "needed_direction", "candidates", "kept", "subunit_level_molecules")}
                       for k, v in searched.items()},
                       "conclusions": [a.get("conclusion") for a in got]}}


def run() -> dict:
    spec = json.loads(EXPECT.read_text())
    cases = sorted({i["case"] for i in spec["items"]})
    runmeta.refuse_eval_cases(cases, f"step 3e acceptance")
    leds, code = {}, runmeta.code_fingerprint()
    for cid in cases:
        p = runmeta.path(3, cid)
        leds[cid] = json.loads(p.read_text()) if p.exists() else None
    out_rows = [{**{k: i.get(k) for k in ("id", "case", "expect", "what", "source")},
                 **compare(i, leds[i["case"]])} for i in spec["items"]]
    fresh = {cid: runmeta.freshness(3, cid, code=code) for cid in cases}
    runmeta.apply_freshness(out_rows, fresh)
    n_ok = sum(r["ok"] for r in out_rows)
    per_case = {}
    for cid, led in leds.items():
        s = (led or {}).get("repurposing_searches") or {}
        per_case[cid] = {"fresh": fresh[cid], "ledger_ok": (led or {}).get("ok"),
                         "branches": {b: {"mechanism": v.get("mechanism"), "needed": v.get("needed_direction"),
                                          "candidates": v.get("candidates"), "kept": v.get("kept"),
                                          "excluded": len(v.get("excluded") or []),
                                          "excluded_for_direction": sum(
                                              1 for x in v.get("excluded") or []
                                              if "direction" in str(x.get("why") or ""))}
                                      for b, v in s.items()}}
    return {"schema": "acceptance-step3e-v1", "created_at": int(time.time()), "code_commit": runmeta.code_commit(),
            "expectations_verified_on": spec.get("verified_on"), "n": len(out_rows), "n_ok": n_ok,
            "ok": n_ok == len(out_rows) and all((l or {}).get("ok") for l in leds.values()),
            "cases": per_case, "rows": out_rows}


def main() -> int:
    r = run()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(r, indent=1, ensure_ascii=False))
    for cid, m in r["cases"].items():
        state = "fresh" if m["fresh"]["fresh"] else "STALE: " + "; ".join(m["fresh"]["reasons"])
        print(f"{cid}: ledger {'ok' if m['ledger_ok'] else 'FAILED'}, {state}")
        for b, v in m["branches"].items():
            print(f"    {b}: mechanism {v['mechanism']} -> needs {v['needed']}; {v['candidates']} matched, "
                  f"{v['kept']} kept, {v['excluded']} excluded ({v['excluded_for_direction']} for direction)")
    for row in r["rows"]:
        tag = "OK " if row["ok"] else ("STL" if row.get("stale") else "BAD")
        print(f"  {tag} {row['id']:<34} {row['what']['en']}" + (f"  -- {row['problem']}" if row["problem"] else ""))
    print(f"{r['n_ok']}/{r['n']} expectations hold "
          f"({sum(1 for x in r['rows'] if x.get('stale'))} on stale outputs, not scored); "
          f"overall {'PASS' if r['ok'] else 'FAIL'} -> {RESULT.relative_to(ROOT)}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

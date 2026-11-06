"""Step 3b acceptance (docs/step3b_contract.md, 验收): verified expectations vs the step 3 ledgers in out/step3.

No LLM and no network. Produce the ledgers first (off-peak):
    python3 scripts/run_pipeline.py --offpeak-only --from-step 3 --case PRAC-SLC35A2-ex7 --case PRAC-SLC35A2-ex8 \
        --case PRAC-AGXT-c33dup --case PRAC-CFTR-F508del --case PRAC-OTC
Writes out/acceptance/step3b.json. Exit 0 when every expectation holds and every ledger passes its checks.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx import runmeta  # noqa: E402

EXPECT = ROOT / "data" / "eval" / "step3b_expectations.json"
RESULT = ROOT / "out" / "acceptance" / "step3b.json"
SECTION = "clinical_trial_eligibility"


def compare(item: dict, led: dict | None) -> dict:
    if led is None:
        return {"ok": False, "actual": None, "problem": "no step 3 ledger for this case"}
    want = item["expect"]
    ts = led.get("trial_searches") or {}
    acts = [a for a in led["actions"] if a["section"] == SECTION]
    if want["status"] == "cap":
        n = {b: len(s.get("analysed") or []) for b, s in ts.items()}
        filt = {b: sum(1 for e in s.get("excluded") or [] if e["reason"] == "relevance") for b, s in ts.items()}
        probs = [f"{b}: {k} analysed > {want['max_analysed']}" for b, k in n.items() if k > want["max_analysed"]]
        if want.get("relevance_filtered_recorded") and not any(filt.values()):
            probs.append("no relevance-filtered study recorded")
        return {"ok": bool(ts) and not probs, "actual": {"analysed": n, "relevance_filtered": filt,
                                                         "over_cap": {b: len(s.get("over_cap") or []) for b, s in ts.items()}},
                "problem": "; ".join(probs) or (None if ts else "no trial searches in the ledger")}
    if want["status"] == "excluded_by_status":
        listed = {b: next((e for e in s.get("excluded") or [] if e["nct"] == item["match"]), None) for b, s in ts.items()}
        hit = {b: e for b, e in listed.items() if e}
        enrollable = [a for a in acts if a.get("nct") == item["match"]]
        probs = ([] if hit and all(e["reason"] == "status" for e in hit.values()) else ["not in the excluded list with reason status"]) \
            + (["listed as a trial action"] if enrollable else [])
        return {"ok": not probs, "actual": {b: e and e["detail"] for b, e in listed.items()}, "problem": "; ".join(probs) or None}
    rec = next((a for a in acts if a.get("nct") == item["match"]), None)
    if not rec:
        return {"ok": False, "actual": None, "problem": f"{item['match']} not in the section"}
    probs = []
    sts = {b: v["status"] for b, v in rec["status_by_branch"].items()}
    if want["status"] != "any" and any(s != want["status"] for s in sts.values()):
        probs.append(f"status {sts}")
    for key, res in (("pass", "pass"), ("unknown", "unknown")):
        for pat in want.get(key) or []:
            if not any(re.search(pat, l["requirement"]) and l["result"] == res for l in rec["requirements"]):
                probs.append(f"no {res} requirement matching /{pat}/")
    for unit, outcome in (want.get("scenarios") or {}).items():
        got = [s for l in rec["requirements"] for s in ((l.get("details") or {}).get("lab") or {}).get("scenarios") or []
               if s["unit"] == unit]
        if not got or got[0]["result"] != outcome:
            probs.append(f"scenario {unit}: {got[0]['result'] if got else 'missing'} (want {outcome})")
    for unit, pat in (want.get("scenario_reason") or {}).items():
        why = " ".join(f"{l.get('note') or ''} {(((l.get('details') or {}).get('lab') or {}).get('patient') or {}).get('why') or ''}"
                       for l in rec["requirements"] if (l.get("details") or {}).get("lab"))
        if not (re.search(re.escape(unit) + r".{0,40}" + pat, why) or (unit in why and re.search(pat, why))):
            probs.append(f"scenario {unit}: reason /{pat}/ not stated")
    lines = [{"requirement": l["requirement"], "result": l["result"], "note": l.get("note")} for l in rec["requirements"]]
    return {"ok": not probs, "actual": {"status": sts, "reasons": {b: v["reason"] for b, v in rec["status_by_branch"].items()},
                                        "requirements": lines}, "problem": "; ".join(probs) or None}


def run() -> dict:
    spec = json.loads(EXPECT.read_text())
    ledgers = {}
    for cid in sorted({i["case"] for i in spec["items"]}):
        p = runmeta.path(3, cid)
        ledgers[cid] = json.loads(p.read_text()) if p.exists() else None
    rows = [{**{k: i[k] for k in ("id", "case", "match", "expect", "what", "source")}, **compare(i, ledgers[i["case"]])}
            for i in spec["items"]]
    code = runmeta.code_fingerprint()
    fresh = {cid: runmeta.freshness(3, cid, code=code) for cid in ledgers}
    runmeta.apply_freshness(rows, fresh)
    meta = {cid: {"fresh": fresh[cid], "exists": l is not None, "ledger_ok": (l or {}).get("ok"),
                  "failed_checks": [c["name"] for c in (l or {}).get("checks", []) if c["status"] == "fail"],
                  "created_at": ((l or {}).get("_meta") or {}).get("created_at")} for cid, l in ledgers.items()}
    n_ok = sum(r["ok"] for r in rows)
    return {"schema": "acceptance-step3b-v1", "created_at": int(time.time()), "code_commit": runmeta.code_commit(),
            "expectations_verified_on": spec.get("verified_on"), "n": len(rows), "n_ok": n_ok,
            "ok": n_ok == len(rows) and all(m["ledger_ok"] for m in meta.values()), "cases": meta, "rows": rows}


def main() -> int:
    r = run()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(r, indent=1, ensure_ascii=False))
    for cid, m in r["cases"].items():
        print(f"{cid}: ledger {'ok' if m['ledger_ok'] else 'FAILED ' + str(m['failed_checks'])}")
    for row in r["rows"]:
        print(f"  {'OK ' if row['ok'] else ('STL' if row.get('stale') else 'BAD')} {row['id']:<20} {row['what']['en']}" + (f"  -- {row['problem']}" if row["problem"] else ""))
    n_stale = sum(1 for row in r["rows"] if row.get("stale"))
    print(f"{r['n_ok']}/{r['n']} expectations hold ({n_stale} on stale outputs, not scored); overall {'PASS' if r['ok'] else 'FAIL'} -> {RESULT.relative_to(ROOT)}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

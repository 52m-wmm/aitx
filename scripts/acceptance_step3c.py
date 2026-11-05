"""Step 3c acceptance (docs/step3c_contract.md): verified expectations vs the step 3 ledgers. No LLM, no network.
Items marked blocked_by wait on a pending decision: reported, but not counted against the code.
Usage:  python3 scripts/acceptance_step3c.py      -> out/acceptance/step3c.json
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

EXPECT = ROOT / "data" / "eval" / "step3c_expectations.json"
RESULT = ROOT / "out" / "acceptance" / "step3c.json"
SECTION = "off_label_expanded_access"


def compare(item: dict, led: dict | None) -> dict:
    if led is None:
        return {"ok": False, "actual": None, "problem": "no step 3 ledger"}
    want = item["expect"]
    hits = [a for a in led["actions"] if a["section"] == SECTION and a.get("action_key")
            and re.search(item["match"], f"{a['label']} {a['action_key']}", re.I)]
    decisions = [d for s in (led.get("offlabel_searches") or {}).values() for d in s.get("drug_decisions") or []
                 if re.search(item["match"], f"{d['drug']} {d['key']}", re.I)]
    probs = []
    if want["status"] == "absent":
        if hits:
            probs.append("present: " + "; ".join(a["label"] for a in hits))
        for pmid, why in (want.get("excluded_pmid") or {}).items():
            p = next((p for s in (led.get("offlabel_searches") or {}).values() for p in s.get("papers") or [] if p["pmid"] == pmid), None)
            if p is not None and not re.search(why, p.get("excluded") or "", re.I):
                probs.append(f"PMID {pmid} not excluded as {why} ({p.get('excluded')})")
        return {"ok": not probs, "actual": {"found": [a["label"] for a in hits], "decisions": decisions}, "problem": "; ".join(probs) or None}
    if not hits:
        return {"ok": False, "actual": {"decisions": decisions}, "problem": "not in the section" + (
            f" (decision: {decisions[0]['decision']})" if decisions else "")}
    a = hits[0]
    pm = {p["pmid"]: p for p in a.get("precedents") or []}
    sts = {b: v["status"] for b, v in a["status_by_branch"].items()}
    if want["status"] not in ("present",) and any(s != want["status"] for s in sts.values()):
        probs.append(f"status {sts}")
    for pmid, want_design in (want.get("design") or {}).items():
        if pmid in pm and pm[pmid].get("design") != want_design:
            probs.append(f"PMID {pmid} design {pm[pmid].get('design')} (want {want_design})")
    for pmid, q in (want.get("design_quote") or {}).items():
        if pmid in pm and q.lower() not in str(pm[pmid].get("design_quote") or "").lower():
            probs.append(f"PMID {pmid} design quote {pm[pmid].get('design_quote')!r} lacks {q!r}")
    if want.get("see_also_3b") and not a.get("see_also"):
        probs.append("no cross-reference to 3b")
    for k in ("access_route", "efficacy_direction"):
        if want.get(k) and a.get(k) != want[k]:
            probs.append(f"{k} {a.get(k)} (want {want[k]})")
    for pmid in want.get("precedent_pmids") or []:
        if pmid not in pm:
            probs.append(f"precedent PMID {pmid} missing")
    if want.get("precedent_pmids_any") and not set(want["precedent_pmids_any"]) & set(pm):
        probs.append(f"none of the precedents {want['precedent_pmids_any']}")
    for pmid, n in (want.get("n_disease") or {}).items():
        if pm.get(pmid, {}).get("n_disease") != n:
            probs.append(f"PMID {pmid} n_disease {pm.get(pmid, {}).get('n_disease')} (want {n})")
    if want.get("conclusion") and want["conclusion"] not in (a.get("conclusion") or ""):
        probs.append(f"conclusion lacks '{want['conclusion']}'")
    unknown = [(l.get("patient_fact") or {}).get("field", "") for l in a["requirements"] if l["result"] == "unknown"]
    for pat in want.get("unknown") or []:
        if not any(re.search(pat, u, re.I) for u in unknown):
            probs.append(f"no unknown condition /{pat}/")
    return {"ok": not probs, "actual": {"status": sts, "access_route": a.get("access_route"), "efficacy": a.get("efficacy_direction"),
                                        "conclusion": a.get("conclusion"), "precedents": [{k: p.get(k) for k in ("pmid", "design", "n_disease", "direction")} for p in pm.values()]},
            "problem": "; ".join(probs) or None}


def main() -> int:
    spec = json.loads(EXPECT.read_text())
    leds = {}
    for cid in {i["case"] for i in spec["items"]}:
        p = runmeta.path(3, cid)
        leds[cid] = json.loads(p.read_text()) if p.exists() else None
    rows = [{**{k: i.get(k) for k in ("id", "case", "match", "expect", "what", "source", "blocked_by", "note")}, **compare(i, leds[i["case"]])}
            for i in spec["items"]]
    counted = [r for r in rows if not r.get("blocked_by") or r["ok"]]
    res = {"schema": "acceptance-step3c-v1", "created_at": int(time.time()), "code_commit": runmeta.code_commit(),
           "n": len(rows), "n_ok": sum(r["ok"] for r in rows), "n_blocked": sum(1 for r in rows if r.get("blocked_by") and not r["ok"]),
           "ok": all(r["ok"] for r in counted) and all((l or {}).get("ok") for l in leds.values()),
           "ledgers_ok": {c: (l or {}).get("ok") for c, l in leds.items()}, "rows": rows}
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for c, ok in res["ledgers_ok"].items():
        print(f"{c}: ledger {'ok' if ok else 'FAILED'}")
    for r in rows:
        tag = "OK " if r["ok"] else ("BLK" if r.get("blocked_by") else "BAD")
        print(f"  {tag} {r['id']:<24} {r['what']['en']}" + (f"  -- {r['problem']}" if r["problem"] else ""))
    print(f"{res['n_ok']}/{res['n']} hold, {res['n_blocked']} blocked by pending decisions; overall {'PASS' if res['ok'] else 'FAIL'}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

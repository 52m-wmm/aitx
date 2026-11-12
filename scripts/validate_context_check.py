"""Validate the context check on judged blind-test entries (decision 2026-11-11). No pipeline rerun.

Usage:
    python scripts/validate_context_check.py --list       # the set and the expected corrections, no LLM
    python scripts/validate_context_check.py --offpeak-only   # run the check (cost: see --list)

The set: every 3a / 3c entry judged WRONG that the context check is meant to catch, and the same number of entries
judged CORRECT (the judged correct 3a / 3c entries, topped up with a seeded sample of the group A DDC entries the
review judged correct; GeneReviews-sourced only, so the passage is rebuilt exactly as the pipeline builds it).

For each entry the script rebuilds what the pipeline would send (passage, patient, questions) from the existing blind
ledgers, runs the check, applies the code's decision, and compares:
  caught  - a wrong entry gets the correction its verdict calls for (EXPECT below);
  harmed  - a correct entry changes status, or its precedent is dropped (decision 2026-11-11: a "gene not stated"
            mark that leaves the status unchanged follows reading rule R3 and is reported apart).
Caveat lines added to a correct entry that leave its status unchanged are reported apart.
Pass mark (decision 2026-11-11): caught >= 80 %, harmed <= 5 %.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx.evidence import context_check as CC  # noqa: E402
from aitx.evidence import established as E  # noqa: E402
from aitx.evidence import ledger as LG  # noqa: E402
from aitx.evidence import offlabel as O  # noqa: E402

BATCH = "20261108"
JUDGED = ROOT / "data" / "eval" / "blind" / f"{BATCH}.json"
OUT = ROOT / "out" / "context_check_validation.json"
SEED = "cc-validate-2026-11-11"
S3A = ("existing_targeted_therapies", "supportive_management", "contraindications_precautions")
S3C = "off_label_expanded_access"

# what catching each wrong entry means (from its verdict note)
EXPECT = {
    ("BLIND-SNRNP200", "bright light"): ("status", "conditional"),
    ("BLIND-RRM2B", "valproic acid"): ("status", "applicable"),
    ("BLIND-LRPPRC", "Sodium bicarbonate"): ("status", "conditional"),
    ("BLIND-LRPPRC", "Sodium citrate"): ("status", "conditional"),
    ("BLIND-GEMIN5", "Coenzyme Q10 (CoQ10)"): ("direction", "positive"),
    ("BLIND-LRPPRC", "riboflavin"): ("direction", "positive"),
    ("BLIND-LRPPRC", "intravenous ketogenic emulsion"): ("direction", "positive"),
    ("BLIND-MPZ", "pilocarpine"): ("direction", "positive"),
    ("BLIND-SFTPC", "Methylprednisolone"): ("direction", "positive"),
    ("BLIND-MPZ", "voriconazole"): ("treatment", False),
    ("BLIND-LRPPRC", "sildenafil citrate (Revatio ® )"): ("subject", "not_same"),
    ("BLIND-MPZ", "PXT3003"): ("subject", "not_same"),
    ("BLIND-LRPPRC", "idebenone"): ("subject", "not_same"),
}
# limit follow-up cases (fix 2026-11-12): (case, section, label, limit words, expected answer) - the question alone is
# scored, on a fresh practice ledger. CFTR F508del homozygous: the GeneReviews ETI row is another genotype's row.
FOLLOWUP_EXPECT = [
    ("PRAC-CFTR-F508del", "existing_targeted_therapies", "Elexacaftor/tezacaftor/ivacaftor",
     "heterozygous for p.Phe508del & a minimal function variant 3 or other known responsive PV", "no"),
]
# judged wrong, but not what the context check is for - listed, not counted
OUT_OF_SCOPE = {
    ("BLIND-SNRNP200", "UV-blocking sunglasses"): "the same action reworded in two sections (fix plan N3)",
    ("BLIND-SNRNP200", "Argus II"): "outdated source (Step 4: show source dates)",
    ("BLIND-SFTPC", "methylprednisolone"): "one drug twice across diagnosis branches (fix plan N4)",
}


def ledger(case: str) -> dict:
    return json.loads((ROOT / "out" / "step3" / f"{case}.json").read_text())


def facts(case: str) -> dict:
    s1 = json.loads((ROOT / "out" / "step1" / f"{case}.json").read_text())
    s2 = json.loads((ROOT / "out" / "step2" / f"{case}.json").read_text())
    return E.facts(s1, s2)


def action(led: dict, section: str, label: str) -> dict:
    return next(a for a in led["actions"] if a["section"] == section and a["label"] == label)


def build_set() -> list[dict]:
    judged = json.loads(JUDGED.read_text())["judgements"]
    wrong, correct = [], []
    for j in judged.values():
        if j.get("section") not in S3A + (S3C,):
            continue
        key = (j["case"], j["label"])
        if j["verdict"] == "wrong" and key in EXPECT:
            wrong.append({"case": j["case"], "section": j["section"], "label": j["label"], "verdict": "wrong",
                          "expect": EXPECT[key]})
        elif j["verdict"] == "correct":
            correct.append({"case": j["case"], "section": j["section"], "label": j["label"], "verdict": "correct",
                            "from": "judgement file"})
    need = len(wrong) - len(correct)
    if need > 0:                       # group A, DDC: every non-supportive entry was judged correct (2026-11-09)
        led = ledger("AITX-00007")
        ev = {e["id"]: e for e in led["evidence"]}
        pool = sorted(a["label"] for a in led["actions"]
                      if a["section"] in ("existing_targeted_therapies", "contraindications_precautions")
                      and a["label"] != "None found"
                      and all((ev.get(i, {}).get("source") or {}).get("type") == "nbk" for i in a["evidence_ids"]))
        for lab in random.Random(SEED).sample(pool, min(need, len(pool))):
            a = action(led, "existing_targeted_therapies", lab) if any(
                x["label"] == lab and x["section"] == "existing_targeted_therapies" for x in led["actions"]) \
                else action(led, "contraindications_precautions", lab)
            correct.append({"case": "AITX-00007", "section": a["section"], "label": lab, "verdict": "correct",
                            "from": "group A review (all non-supportive entries judged correct)"})
    return wrong + correct


def checks_for(entry: dict) -> list[dict]:
    """One context check per 3a entry, one per precedent of a 3c entry: (header, passage, patient, questions)."""
    led, pf = ledger(entry["case"]), facts(entry["case"])
    a = action(led, entry["section"], entry["label"])
    br = next(b for b in led["branches"] if b["id"] in a["applies_to"])
    patient = CC.patient_text(pf, br)
    disease = (br.get("diagnosis") or {}).get("label") or ""
    if entry["section"] in S3A:
        ev = {e["id"]: e for e in led["evidence"]}
        main = next(ev[i] for i in a["evidence_ids"] if (ev[i].get("source") or {}).get("type") in E.CONTEXT_SOURCES)
        header, passage = E.context_passage({"src": main["source"], "quote": main["quote"], "source_text": ""})
        return [{"kind": "3a", "header": header, "passage": passage, "patient": patient, "ev_id": main["id"],
                 "questions": CC.questions_3a(entry["section"], a["label"], disease, a["requirements"], main["quote"]),
                 "action": a, "branches": a["applies_to"]}]
    recs = O._fetch_records([p["pmid"] for p in a.get("precedents") or []])
    out = []
    for p in a.get("precedents") or []:
        r = recs.get(p["pmid"]) or {}
        out.append({"kind": "3c", "header": f"PubMed {p['pmid']} ({p.get('year')})",
                    "passage": "\n".join(x for x in (r.get("title"), r.get("abstract")) if x), "patient": patient,
                    "questions": CC.questions_3c(a["label"], disease, br.get("gene")), "pmid": p["pmid"]})
    return out


def outcome(entry: dict, results: list[dict]) -> dict:
    """What the code's decision does to the entry."""
    if entry["section"] in S3A:
        c = results[0]
        a = c["action"]
        c["followups"] = {}

        def followup(q):                 # the limit follow-up the pipeline asks (fix 2026-11-12)
            r = CC.ask(c["header"], c["passage"], c["patient"], CC.questions_limit(a["label"], q))
            c["followups"][q] = CC.summary(r)["answers"]
            return r["questions"][0]["final"]
        lines, notes = CC.decide_3a(c["res"], a["requirements"], c["ev_id"], c["passage"], c["branches"],
                                    limit_followup=followup)
        before = sorted({LG.status_of(a["requirements"], b)[0] for b in c["branches"]})
        after = sorted({LG.status_of(lines, b)[0] for b in c["branches"]})
        return {"status_before": before, "status_after": after, "notes": notes,
                "added": [l["requirement"] for l in lines if l.get("context_check") in ("scope", "limit")]}
    decs = [CC.decide_3c(c["res"]) for c in results]
    return {"precedents": [{"pmid": c["pmid"], **d} for c, d in zip(results, decs)]}


def judge(entry: dict, out: dict) -> tuple[bool, str]:
    """(caught or harmed, why) for one entry."""
    if entry["verdict"] == "wrong":
        what, want = entry["expect"]
        if what == "status":
            return out["status_after"] == [want], f"status {out['status_before']} -> {out['status_after']}"
        ps = out["precedents"]
        if what == "direction":           # the verdict was about the conclusion contradicting a reported improvement
            got = [p["direction"] for p in ps if p["treatment"]]
            agg = O.aggregate(got)
            return agg in ("reported_improvement", "partial_improvement"), f"directions {got} -> {agg}"
        if what == "treatment":
            return all(p["treatment"] is False for p in ps), f"treatment {[p['treatment'] for p in ps]}"
        if what == "subject":
            return any(p["subject"] != "same" for p in ps), f"subjects {[p['subject'] for p in ps]}"
    if entry["section"] in S3A:
        return out["status_after"] != out["status_before"], f"status {out['status_before']} -> {out['status_after']}"
    # harm (decision 2026-11-11): the status changes or the precedent is dropped. A "gene not stated" mark on a precedent
    # that stays conditional follows reading rule R3 (as for idebenone) and is reported apart, not counted as harm.
    ps = out["precedents"]
    dropped = [p for p in ps if not p["treatment"]]
    return bool(dropped), f"treatment {[p['treatment'] for p in ps]}, subjects {[p['subject'] for p in ps]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="show the set and the number of calls; no LLM")
    ap.add_argument("--offpeak-only", action="store_true")
    args = ap.parse_args()
    entries = build_set()
    plan = [(e, checks_for(e)) for e in entries]
    n_checks = sum(len(c) for _, c in plan)
    print(f"{sum(e['verdict'] == 'wrong' for e in entries)} wrong + {sum(e['verdict'] == 'correct' for e in entries)} "
          f"correct entries -> {n_checks} context checks x {CC.N_CHECKS} = {n_checks * CC.N_CHECKS} LLM calls")
    for e, cs in plan:
        print(f"  {e['verdict']:7} {e['case']:15} {e['section'][:12]:12} {e['label'][:40]:40} checks {len(cs)}"
              + (f"  expect {e['expect']}" if e.get("expect") else ""))
    print("not counted (out of scope): " + "; ".join(f"{k[1]} - {v}" for k, v in OUT_OF_SCOPE.items()))
    if args.list:
        return 0
    if args.offpeak_only:
        from aitx import peak
        peak.guard()
    t0 = time.time()
    rows = []
    for e, cs in plan:
        for c in cs:
            c["res"] = CC.ask(c["header"], c["passage"], c["patient"], c["questions"])
        out = outcome(e, cs)
        hit, why = judge(e, out)
        rows.append({**{k: v for k, v in e.items()}, "hit": hit, "why": why, "outcome": out,
                     "answers": [CC.summary(c["res"])["answers"] for c in cs]})
        print(f"  {'CAUGHT' if hit and e['verdict'] == 'wrong' else 'missed' if e['verdict'] == 'wrong' else 'HARMED' if hit else 'ok'}"
              f"  {e['case']:15} {e['label'][:40]:40} {why}")
    followup_rows = []
    for case, section, label, limit, want in FOLLOWUP_EXPECT:
        led, pf = ledger(case), facts(case)
        a = action(led, section, label)
        ev = {e["id"]: e for e in led["evidence"]}
        main = next(ev[i] for i in a["evidence_ids"] if (ev[i].get("source") or {}).get("type") == "nbk")
        header, passage = E.context_passage({"src": main["source"], "quote": main["quote"], "source_text": ""})
        br = next(b for b in led["branches"] if b["id"] in a["applies_to"])
        r = CC.ask(header, passage, CC.patient_text(pf, br), CC.questions_limit(label, limit))
        got = r["questions"][0]
        followup_rows.append({"case": case, "label": label, "limit": limit, "want": want, "final": got["final"],
                              "answers": got["answers"], "hit": got["final"] == want})
        print(f"  {'OK    ' if got['final'] == want else 'MISSED'}  follow-up {case} {label}: {got['answers']} (want {want})")
    wrong = [r for r in rows if r["verdict"] == "wrong"]
    corr = [r for r in rows if r["verdict"] == "correct"]
    caught, harmed = sum(r["hit"] for r in wrong), sum(r["hit"] for r in corr)
    caveats = [r for r in corr if not r["hit"] and (r["outcome"].get("added") or any(
        p["subject"] != "same" for p in r["outcome"].get("precedents") or []))]
    sys.path.insert(0, str(ROOT / "scripts"))
    import llm_cost  # noqa: E402
    cost = llm_cost.summarize(t0)
    res = {"prompt_version": CC.PROMPT_VERSION, "call_params": CC.CALL_PARAMS, "ran_at": int(t0),
           "caught": caught, "wrong": len(wrong), "harmed": harmed, "correct": len(corr),
           "caught_rate": round(caught / len(wrong), 3) if wrong else None,
           "harmed_rate": round(harmed / len(corr), 3) if corr else None,
           "caveats_on_correct": [{"case": r["case"], "label": r["label"], "added": r["outcome"].get("added"),
                                   "subjects": [p["subject"] for p in r["outcome"].get("precedents") or []]} for r in caveats],
           "harm_measure": "status changed or precedent dropped (decision 2026-11-11)",
           "cost": cost, "pass": bool(wrong and corr and caught / len(wrong) >= 0.8 and harmed / len(corr) <= 0.05),
           "rows": rows, "followup_cases": followup_rows, "out_of_scope": [{"case": k[0], "label": k[1], "why": v} for k, v in OUT_OF_SCOPE.items()]}
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"\ncaught {caught}/{len(wrong)} ({res['caught_rate']}), harmed {harmed}/{len(corr)} ({res['harmed_rate']}), "
          f"caveats added to correct entries without a status change: {len(caveats)}")
    print(f"cost: {cost['calls']} calls, ${cost['usd']:.4f}; pass mark (>= 80 % caught, <= 5 % harmed): "
          f"{'PASS' if res['pass'] else 'FAIL'} -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

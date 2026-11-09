"""Step 3d acceptance (docs/step3d_contract.md): verified expectations vs the 3d rows in out/step3.

Usage:  python3 scripts/acceptance_step3d.py        # exit 0 when every expectation holds on a fresh ledger

Writes out/acceptance/step3d.json, which also carries `unassessable_summary`: how many judgements came out
"unable to assess" and for which missing input. That tally is what the review uses to decide whether to connect
the deferred data sources (mechanism sources beyond GeneReviews, gene-dosage scores, UniProt domains).
Only fresh ledgers are scored (runmeta.freshness); a stale case is reported and not counted.
"""
from __future__ import annotations

import collections
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx import runmeta  # noqa: E402

EXPECT = ROOT / "data" / "eval" / "step3d_expectations.json"
RESULT = ROOT / "out" / "acceptance" / "step3d.json"


def row_of(led: dict, modality: str, branch: str | None) -> dict | None:
    """The 3d row to compare against. A case with several diagnosis branches has one row per branch; when an
    expectation names no branch they must agree on the verdict, otherwise the expectation has to name one
    (2026-11-06: DMD and COL1A1 have three branches each and the old 'exactly one row' rule failed them)."""
    rows = [a for a in led.get("actions", []) if a.get("section") == "bespoke_therapies"
            and a.get("modality") == modality and (branch is None or branch in a.get("applies_to", []))]
    if not rows:
        return None
    if len({(r.get("classification"), r.get("failed_criterion")) for r in rows}) > 1:
        return None
    return rows[0]


def compare(item: dict, led: dict | None) -> dict:
    if led is None:
        return {"ok": False, "actual": None, "problem": "no step 3 ledger for this case"}
    want = item["expect"]
    a = row_of(led, item["modality"], item.get("branch"))
    if a is None:
        got = [r for r in led.get("actions", []) if r.get("section") == "bespoke_therapies"
               and r.get("modality") == item["modality"]]
        why = (f"the branches disagree on {item['modality']}: "
               + "; ".join(f"{r['applies_to']} {r.get('classification')}" for r in got)
               + " - name a branch in the expectation") if got else f"no 3d row for {item['modality']}"
        return {"ok": False, "actual": None, "problem": why}
    probs, facts = [], a.get("facts") or {}
    if want.get("classification") and a.get("classification") != want["classification"]:
        probs.append(f"classification {a.get('classification')} (want {want['classification']})")
    if want.get("failed_criterion") and want["failed_criterion"] not in (a.get("failed_criterion") or ""):
        probs.append(f"failed_criterion lacks '{want['failed_criterion']}'")
    if want.get("unassessable_reason") and not any(want["unassessable_reason"] in x
                                                   for x in a.get("unassessable_reason") or []):
        probs.append(f"no unassessable reason mentioning '{want['unassessable_reason']}'")
    for k, v in (want.get("facts") or {}).items():
        if facts.get(k) != v:
            probs.append(f"facts.{k} = {facts.get(k)!r} (want {v!r})")
    if want.get("mechanism"):
        got = {b: (r or {}).get("mechanism") for b, r in (led.get("bespoke_mechanism") or {}).items()}
        ok = want["mechanism"] if isinstance(want["mechanism"], list) else [want["mechanism"]]
        if not set(ok) & set(got.values()):
            probs.append(f"mechanism {got} (want {want['mechanism']})")
        elif not a.get("evidence_ids"):
            probs.append("mechanism-based verdict cites no evidence")
    return {"ok": not probs, "problem": "; ".join(probs) or None,
            "actual": {"classification": a.get("classification"), "failed_criterion": a.get("failed_criterion"),
                       "unassessable_reason": a.get("unassessable_reason"), "facts": facts,
                       "conclusion": a.get("conclusion")}}


def unassessable_summary(ledgers: dict[str, dict]) -> dict:
    per_reason: collections.Counter = collections.Counter()
    per_modality: collections.Counter = collections.Counter()
    total = 0
    for led in ledgers.values():
        if not led:
            continue
        rows = [a for a in led.get("actions", []) if a.get("section") == "bespoke_therapies"]
        total += len(rows)
        for r in led.get("bespoke_unassessable") or []:
            per_reason[r["reason"]] += 1
            per_modality[r["modality"]] += 1
    return {"judgements": total, "unassessable_rows": sum(per_reason.values()),
            "share_of_judgements": round(sum(per_modality.values()) / total, 3) if total else None,
            "by_reason": dict(per_reason.most_common()), "by_modality": dict(per_modality.most_common())}


def run() -> dict:
    spec = json.loads(EXPECT.read_text())
    cases = sorted({i["case"] for i in spec["items"]})
    runmeta.refuse_eval_cases(cases, f"step 3d acceptance")
    leds, code = {}, runmeta.code_fingerprint()
    for cid in cases:
        p = runmeta.path(3, cid)
        leds[cid] = json.loads(p.read_text()) if p.exists() else None
    rows = [{**{k: i.get(k) for k in ("id", "case", "modality", "expect", "what", "source")},
             **compare(i, leds[i["case"]])} for i in spec["items"]]
    fresh = {cid: runmeta.freshness(3, cid, code=code) for cid in cases}
    runmeta.apply_freshness(rows, fresh)
    n_ok = sum(r["ok"] for r in rows)
    return {"schema": "acceptance-step3d-v1", "created_at": int(time.time()), "code_commit": runmeta.code_commit(),
            "expectations_verified_on": spec.get("verified_on"), "n": len(rows), "n_ok": n_ok,
            "ok": n_ok == len(rows) and all((l or {}).get("ok") for l in leds.values()),
            "cases": {c: {"fresh": fresh[c], "ledger_ok": (leds[c] or {}).get("ok"),
                          "mechanism": {b: (r or {}).get("mechanism") for b, r in
                                        ((leds[c] or {}).get("bespoke_mechanism") or {}).items()}} for c in cases},
            "unassessable_summary": unassessable_summary(leds), "rows": rows}


def main() -> int:
    r = run()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(r, indent=1, ensure_ascii=False))
    for cid, m in r["cases"].items():
        state = "fresh" if m["fresh"]["fresh"] else "STALE: " + "; ".join(m["fresh"]["reasons"])
        print(f"{cid}: ledger {'ok' if m['ledger_ok'] else 'FAILED'}, {state}, mechanism {m['mechanism']}")
    for row in r["rows"]:
        tag = "OK " if row["ok"] else ("STL" if row.get("stale") else "BAD")
        print(f"  {tag} {row['id']:<36} {row['what']['en']}" + (f"  -- {row['problem']}" if row["problem"] else ""))
    u = r["unassessable_summary"]
    print(f"\n{u['unassessable_rows']} of {u['judgements']} judgements could not be assessed "
          f"(share {u['share_of_judgements']}); by missing input:")
    for why, n in u["by_reason"].items():
        print(f"  {n:>3}  {why}")
    print(f"{r['n_ok']}/{r['n']} expectations hold "
          f"({sum(1 for x in r['rows'] if x.get('stale'))} on stale outputs, not scored); "
          f"overall {'PASS' if r['ok'] else 'FAIL'} -> {RESULT.relative_to(ROOT)}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

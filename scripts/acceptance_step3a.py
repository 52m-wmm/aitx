"""Step 3a acceptance (docs/step3a_contract.md, 验收): verified expectations vs the ledgers in out/step3.

No LLM and no network: it reads data/eval/step3a_expectations.json (each item checked against the label
or GeneReviews text, with its source) and the step 3 ledgers already produced by
    python3 scripts/run_pipeline.py --offpeak-only --from-step 3 --case PRAC-AGXT-c33dup ...
and writes out/acceptance/step3a.json, which the viewer's acceptance page displays as is.

Usage:  python3 scripts/acceptance_step3a.py           # exit 0 when every expectation holds and every ledger passes its checks
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

EXPECT = ROOT / "data" / "eval" / "step3a_expectations.json"
RESULT = ROOT / "out" / "acceptance" / "step3a.json"


def _branches(led: dict, pattern: str | None) -> list[str]:
    return [b["id"] for b in led["branches"]
            if not pattern or re.search(pattern, ((b.get("diagnosis") or {}).get("label") or b.get("gene") or ""), re.I)]


def compare_tier(item: dict, led: dict) -> dict:
    """Supportive fallback-chain record of a branch (ledger supportive_tiers) against expect.tier:
    {tier, literature_searched, no_literature_actions, disabled_category}."""
    want = item["expect"]["tier"]
    branches = _branches(led, item.get("branch"))
    recs = {b: (led.get("supportive_tiers") or {}).get(b) for b in branches}
    if not branches or not all(recs.values()):
        return {"ok": False, "actual": None, "problem": "no supportive tier record for the branch"}
    probs, actual = [], {}
    for b, r in recs.items():
        lit = r.get("literature") or {}
        lit_actions = [a["label"] for a in led["actions"] if a.get("tier_source") == "literature" and b in a["applies_to"]]
        disabled = (r.get("symptomatic") or {}).get("disabled") or []
        actual[b] = {"tier": r.get("tier"), "literature_count": lit.get("count"), "literature_error": lit.get("error"),
                     "literature_actions": lit_actions, "disabled": disabled}
        if "tier" in want and r.get("tier") != want["tier"]:
            probs.append(f"{b}: tier {r.get('tier')} (want {want['tier']})")
        if want.get("literature_searched") and (lit.get("error") or lit.get("count") is None):
            probs.append(f"{b}: literature not searched ({lit.get('error') or 'no record'})")
        if want.get("no_literature_actions") and lit_actions:
            probs.append(f"{b}: literature actions {lit_actions}")
        if want.get("disabled_category") and want["disabled_category"] not in disabled:
            probs.append(f"{b}: category {want['disabled_category']} not recorded as disabled")
        if want.get("disabled_category"):
            made = [a["label"] for a in led["actions"] if a.get("tier_source") == "symptomatic" and b in a["applies_to"]
                    and (a.get("for_symptom") or {}).get("hpo_id") in set(want.get("disabled_hpo") or [])]
            if made:
                probs.append(f"{b}: actions for a disabled category {made}")
    return {"ok": not probs, "actual": actual, "problem": "; ".join(probs) or None}


def compare(item: dict, led: dict | None) -> dict:
    """One expectation against one ledger -> {ok, actual, problem}. Code only; the page shows this."""
    if led is None:
        return {"ok": False, "actual": None, "problem": "no step 3 ledger for this case"}
    want = item["expect"]
    if "tier" in want:
        return compare_tier(item, led)
    branches = _branches(led, item.get("branch"))
    if not branches:
        return {"ok": False, "actual": None, "problem": f"no branch matches {item.get('branch')!r}"}
    here = [a for a in led["actions"] if a["section"] == item["section"] and set(a["applies_to"]) & set(branches)]
    # the label decides; the action key only when no label matches (a combination product's key lists every ingredient)
    hits = [a for a in here if re.search(item["match"], a["label"], re.I)] or \
        [a for a in here if re.search(item["match"], a.get("action_key") or "", re.I)]
    # actions kept in the ledger but not written to the report (e.g. pregnancy-only for a boy) are not what the
    # report says; they count only when nothing reported matches (2026-11-04: a hidden pregnancy-only "intravenous
    # fluid administration" failed the IV fluids expectation although the reported "IV fluid" action held)
    shown = [a for a in hits if a.get("report", True) is not False]
    hits = shown or hits
    elsewhere = [f"{a['label']} in {a['section']}" for a in led["actions"] if a["section"] != item["section"]
                 and re.search(item["match"], f"{a['label']} {a.get('action_key') or ''}", re.I)]
    if want["status"] == "absent":            # e.g. emerging evidence must not be written into an established section
        return {"ok": not hits, "actual": [{"label": a["label"], "tier_source": a.get("tier_source")} for a in hits],
                "problem": ("present: " + "; ".join(a["label"] for a in hits)) if hits else None}
    if not hits:
        return {"ok": False, "actual": {"found_elsewhere": elsewhere},
                "problem": "not found in this section" + (f" (found: {'; '.join(elsewhere)})" if elsewhere else "")}
    actual, problems = [], []
    for a in hits:
        per = {b: a["status_by_branch"][b] for b in branches if b in a["status_by_branch"]}
        unknown = [r["requirement"] for r in a["requirements"] if r["result"] == "unknown" and set(r["applies_to"]) & set(per)]
        actual.append({"action_key": a.get("action_key"), "label": a["label"], "report": a.get("report", True),
                       "status_by_branch": per, "unknown_requirements": unknown})
        if want["status"] != "present":
            bad = {b: s["status"] for b, s in per.items() if s["status"] != want["status"]}
            if bad:
                problems.append(f"{a['label']}: " + ", ".join(f"{s} ({b})" for b, s in bad.items()))
        for pat in want.get("unknown") or []:
            if not any(re.search(pat, u, re.I) for u in unknown):
                problems.append(f"{a['label']}: no unknown requirement matching /{pat}/")
        if want.get("tier_source") and a.get("tier_source") != want["tier_source"]:
            problems.append(f"{a['label']}: tier_source {a.get('tier_source')} (want {want['tier_source']})")
        if want.get("for_symptom") and not re.search(want["for_symptom"], (a.get("for_symptom") or {}).get("label", ""), re.I):
            problems.append(f"{a['label']}: for_symptom {(a.get('for_symptom') or {}).get('label')}")
    return {"ok": not problems, "actual": actual, "problem": "; ".join(problems) or None}


def run() -> dict:
    spec = json.loads(EXPECT.read_text())
    cases = sorted({i["case"] for i in spec["items"]})
    ledgers, meta = {}, {}
    for cid in cases:
        p = runmeta.path(3, cid)
        led = json.loads(p.read_text()) if p.exists() else None
        ledgers[cid] = led
        m = (led or {}).get("_meta") or {}
        pb = [x.get("produced_by") for x in (led or {}).get("evidence", []) if x.get("section") != "background"]
        prompt = sorted({p["prompt_version"] for p in pb if isinstance(p, dict) and p.get("prompt_version")})
        meta[cid] = {"exists": led is not None, "created_at": m.get("created_at"), "code_commit": m.get("code_commit"),
                     "schema_version": (led or {}).get("schema_version"), "ledger_ok": (led or {}).get("ok"),
                     "failed_checks": [c["name"] for c in (led or {}).get("checks", []) if c["status"] == "fail"],
                     "prompt_versions": prompt,
                     "reextracted_rows": len((led or {}).get("reextracted_rows") or []),
                     "reextracted_no_treatment": sum(1 for r in (led or {}).get("reextracted_rows") or [] if r.get("no_treatment")),
                     "branches": {b["id"]: (b.get("diagnosis") or {}).get("label") or b.get("gene") for b in (led or {}).get("branches", [])}}
    rows = [{**{k: i.get(k) for k in ("id", "case", "section", "match", "expect", "what", "source", "provisional")}, "branch": i.get("branch"),
             **compare(i, ledgers[i["case"]])} for i in spec["items"]]
    code = runmeta.code_fingerprint()
    fresh = {cid: runmeta.freshness(3, cid, code=code) for cid in cases}
    runmeta.apply_freshness(rows, fresh)
    for cid in cases:
        meta[cid]["fresh"] = fresh[cid]
    n_ok = sum(r["ok"] for r in rows)
    ok = n_ok == len(rows) and all(m["ledger_ok"] for m in meta.values())
    return {"schema": "acceptance-step3a-v1", "created_at": int(time.time()), "code_commit": runmeta.code_commit(),
            "expectations_verified_on": spec.get("verified_on"), "n": len(rows), "n_ok": n_ok, "ok": ok,
            "cases": meta, "rows": rows}


def main() -> int:
    r = run()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(r, indent=1, ensure_ascii=False))
    for cid, m in r["cases"].items():
        made = time.strftime("%Y-%m-%d %H:%M", time.localtime(m["created_at"] or 0))
        print(f"{cid}: ledger {'ok' if m['ledger_ok'] else 'FAILED ' + str(m['failed_checks'])}, made {made}, "
              f"prompt {m['prompt_versions']}, rows extracted again {m['reextracted_rows']} "
              f"(no treatment {m['reextracted_no_treatment']})")
    for row in r["rows"]:
        print(f"  {'OK ' if row['ok'] else ('STL' if row.get('stale') else 'BAD')} {row['id']:<22} {row['what']['en']}" + (f"  -- {row['problem']}" if row["problem"] else ""))
    n_stale = sum(1 for row in r["rows"] if row.get("stale"))
    print(f"{r['n_ok']}/{r['n']} expectations hold ({n_stale} on stale outputs, not scored); overall {'PASS' if r['ok'] else 'FAIL'} -> {RESULT.relative_to(ROOT)}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

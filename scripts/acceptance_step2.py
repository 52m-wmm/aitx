"""Online acceptance test for step 2 (needs network and AITX_LLM_API_KEY).

Runs the official Phase 0 examples and the four challenge cases and checks the
contract's acceptance criteria (docs/step2_disease_contract.md):
  HARD  data integrity, IDs, HPO quotes, no outside candidates, ClinVar exact
        match, patient_facts quotes, practice-case answers, the two trap cases,
        identical output on a cached rerun, eval primaries stable across samples
  SOFT  values printed for a human to check (eval-case primaries, GRIN2B, ...)

Usage:
    python scripts/acceptance_step2.py               # LLM samples from cache when present
    python scripts/acceptance_step2.py --fresh-llm   # 3 new LLM calls per case (stability report)
Exit code 0 only if every HARD expectation passes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx.disease import extract, pipeline, resolve  # noqa: E402

# (case id, expected OMIM of a resolved primary, where the expectation comes from)
EXPECT = [
    ("PRAC-AGXT-c33dup", "OMIM:259900", "only high-strength association + nephrocalcinosis"),
    ("PRAC-AGXT-c508GA", "OMIM:259900", "same"),
    ("PRAC-CFTR-F508del", "OMIM:219700", "named in the text"),
    ("PRAC-OTC", "OMIM:311250", "hemizygous male infant + hyperammonemia"),
    ("PRAC-KMT2B", "OMIM:617284", "childhood-onset generalized dystonia"),
    ("PRAC-ANO10", "OMIM:613728", "homozygous + ataxia"),
    ("PRAC-NF1", "OMIM:162200", "MPNST + pheochromocytoma"),
]
SOFT = {
    "PRAC-DMD-del": "Duchenne vs Becker (in-frame deletion favours Becker; gene-specific rule is step 3/4)",
    "PRAC-GRIN2B": "ID6 613970 vs DEE27 616139",
    "PRAC-SLC35A2": "primary and confidence",
    "AITX-40001": "expected DEE76 618468; AD 618470 downgraded by inheritance",
    "AITX-40002": "expected SCA29 117360; Gillespie needs aniridia (not stated)",
    "AITX-40003": "HSAN1 162400 vs ALS27 620285; possibly ambiguous",
    "AITX-40004": "BAGOS 618218 named in text, should be adopted",
}


def load_cases() -> list[dict]:
    cases = json.loads((ROOT / "data/cases/practice/official_examples.json").read_text())
    return cases + json.loads((ROOT / "data/cases/aitx_final_patients.json").read_text())


def omims(r: dict, key: str) -> set[str]:
    c = next((c for c in r["candidates"] + r["not_supported"] if c["key"] == key), None)
    return {o["id"] for o in c["omim"]} if c else set()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh-llm", action="store_true", help="use an empty LLM cache (3 new calls per case)")
    args = ap.parse_args()
    if args.fresh_llm:
        extract.CACHE_DIR = Path(tempfile.mkdtemp(prefix="aitx-llm-"))
    if not os.environ.get("AITX_LLM_API_KEY"):
        print("set AITX_LLM_API_KEY")
        return 2

    cases = load_cases()
    res = resolve.load_resources({v["gene"] for c in cases for v in c["patient"]["genotype"]})
    results, fails = {}, []

    def hard(ok: bool, what: str):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}")
        if not ok:
            fails.append(what)

    print("== per-case checks (HARD) ==")
    for case in cases:
        r = pipeline.run_case(case, res)
        results[case["id"]] = r
        bad = [f"{c['name']}: {c['detail']}" for c in r["checks"] if c["status"] == "fail"]
        hard(not bad, f"{case['id']} checks" + (f" -> {bad}" if bad else ""))

    print("\n== cached rerun identical (HARD) ==")
    for case in cases:
        again = pipeline.run_case(case, res)
        same = json.dumps(again, sort_keys=True) == json.dumps(results[case["id"]], sort_keys=True)
        hard(same, f"{case['id']} rerun identical")

    print("\n== practice answers (HARD) ==")
    for cid, want, why in EXPECT:
        p = results[cid]["primary"]
        got = set(p["omim"])
        hard(p["status"] == "resolved" and want in got,
             f"{cid}: {p['status']} {p['label']} {sorted(got)} (want resolved {want}; {why})")

    print("\n== trap cases (HARD) ==")
    r = results["PRAC-COL1A1"]
    order = [c["key"] for c in sorted(r["candidates"], key=lambda c: -(c["phenotype"]["score"] or -1))]
    eds = [c["key"] for c in r["candidates"] if "ehlers-danlos" in c["label"].lower()]
    oi = [c["key"] for c in r["candidates"] if "osteogenesis imperfecta" in c["label"].lower()
          and "ehlers" not in c["label"].lower()]
    p = r["primary"]
    listed = {p["id"]} | {a["id"] for a in p["alternatives"]}
    ranked_first = bool(eds) and (not oi or min(order.index(k) for k in eds) < min(order.index(k) for k in oi))
    amb_both = p["status"] == "ambiguous" and listed & set(eds) and listed & set(oi)
    eds_primary = p["id"] in eds
    hard(bool(eds) and (amb_both or (eds_primary and ranked_first)),
         f"PRAC-COL1A1: EDS in candidates and (primary EDS ranked before OI, or ambiguous with both) "
         f"-> {p['status']} {p['label']}; alternatives {[a['label'] for a in p['alternatives']]}")
    r = results["PRAC-DMD-del"]
    all_omim = {o["id"] for c in r["candidates"] for o in c["omim"]}
    hard({"OMIM:310200", "OMIM:300376"} <= all_omim, f"PRAC-DMD-del: Duchenne 310200 and Becker 300376 in candidates")

    print("\n== ClinVar exact match (HARD) ==")
    used = [(rec["vcv"], rec["title"]) for rec in results["AITX-40002"]["clinvar"][0]["records"]]
    hard(all("c.101A>G" not in t for _, t in used), f"AITX-40002 ITPR1: c.101A>G not used -> {used}")
    cf = results["PRAC-CFTR-F508del"]["clinvar"][0]
    cf_ok = [rec for rec in cf["records"] if rec["used_for_ranking"]
             and any("OMIM:219700" in omims(results["PRAC-CFTR-F508del"], k) for k in rec["mapped_candidates"])]
    hard(bool(cf_ok), "PRAC-CFTR-F508del: P/LP record linked to cystic fibrosis -> "
         + str([(x["vcv"], x["clinical_significance"], x["match"]) for x in cf_ok]))

    print("\n== patient_facts (HARD) ==")
    f = results["PRAC-OTC"]["patient_facts"]
    hard(f["age"].get("months") == 3 and f["sex"].get("value") == "male",
         f"PRAC-OTC: age {f['age'].get('months')} months, sex {f['sex'].get('value')} (want 3, male)")

    print("\n== stability across LLM samples ==")
    for cid, r in results.items():
        ps = r["primary"]["per_sample"]
        distinct = {(p["status"], p["id"]) for p in ps}
        terms = [set(map(tuple, s["terms"])) for s in r["phenotype_extraction"]["samples"]]
        common = set.intersection(*terms) if terms else set()
        diff = sorted({t for s in terms for t in s} - common)
        line = f"{cid}: primaries {'identical' if len(distinct) == 1 else 'DIFFER ' + str(sorted(distinct, key=str))}"
        if diff:
            line += f"; terms not in every sample: {diff}"
        if cid.startswith("AITX-"):
            hard(len(distinct) == 1 or r["primary"]["status"] != "resolved", line + " (eval: unstable -> not resolved)")
        else:
            print("  [INFO] " + line)

    print("\n== to check by hand (SOFT) ==")
    for cid, note in SOFT.items():
        p = results[cid]["primary"]
        print(f"  {cid}: {p['status']} -> {p['label']} {p['omim']} ({p['basis']}, {p.get('confidence')})  # {note}")
        for a in p["alternatives"]:
            print(f"        alt: {a['label']} {sorted(omims(results[cid], a['id']))}")
        print("        HPO: " + ", ".join(f"{'NOT ' if x['status'] == 'excluded' else ''}{x['label']}"
                                        for x in results[cid]["phenotypes"]))

    out = ROOT / "out" / "acceptance_step2.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"failed": fails, "results": results}, indent=2, ensure_ascii=False))
    print(f"\n{'ALL HARD CHECKS PASSED' if not fails else f'{len(fails)} HARD CHECK(S) FAILED'}  (details: {out})")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

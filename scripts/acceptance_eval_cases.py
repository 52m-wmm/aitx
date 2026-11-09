"""Acceptance expectations that are written against the four evaluation cases (--eval only).

These were written while the evaluation cases were still being run during development, from public database
records (RefSeq, UniProt, OMIM, ClinVar). They are kept because those records are public and checkable, but
they live here and run only with --eval, so regular acceptance never touches the evaluation cases
(decision 2026-11-08; see CLAUDE.md).

Usage:  python scripts/acceptance_eval_cases.py --eval
        python scripts/acceptance_eval_cases.py --eval --step 1

Step 1 expectations are checked by building the variant profiles from the live RefSeq records. Step 2
expectations are read from the step 2 outputs already on disk (out/step2/); this script never runs the
pipeline itself and makes no LLM call.
Exit code 0 only if every HARD expectation passes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx import runmeta  # noqa: E402

SPEC = ROOT / "data" / "eval" / "eval_case_expectations.json"
CASES = ROOT / "data" / "cases" / "aitx_final_patients.json"


def get(d: dict, path: str):
    for k in path.split("."):
        d = d.get(k) if isinstance(d, dict) else None
    return d


def step1(cases: list[dict], spec: dict) -> int:
    from aitx.variant.profile import build_profile
    from aitx.variant.transcript import fetch_transcript
    fails, results = 0, {}
    print("== step 1: consistency and re-translation (HARD) ==")
    for case in cases:
        v = case["patient"]["genotype"][0]
        try:
            t = fetch_transcript(v["transcript"])
            p = build_profile(v, t).to_dict()
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {case['id']:<14} could not build profile: {e}")
            fails += 1
            continue
        results[case["id"]] = p
        bad = [c for c in p["checks"] if c["status"] == "fail"]
        selfcheck = next(c for c in p["checks"] if c["name"] == "independent_translation")
        ok = not bad and selfcheck["status"] == "pass"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {case['id']:<14} {v['gene']:<8} {v['variant_cdna']:<16} "
              f"{p['variant_class']:<17} NMD {p['nmd']['prediction']}")
        for c in bad:
            print(f"       FAIL {c['name']}: {c['detail']}")
    print("\n== step 1: stated expectations (HARD) ==")
    for e in spec["step1_hard"]:
        got = get(results.get(e["case"], {}), e["path"])
        ok = got == e["want"]
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {e['case']:<14} {e['path']:<20} want {e['want']!r:<8} got {got!r}"
              f"   [{e['source']}]")
    print("\n== step 1: values to eyeball (SOFT) ==")
    for e in spec["step1_soft"]:
        print(f"  {e['case']:<14} {e['path']:<8} {json.dumps(get(results.get(e['case'], {}), e['path']))[:160]}"
              f"   [{e['note']}]")
    return fails


def step2(spec: dict) -> int:
    """Reads the step 2 outputs on disk. Nothing is run and no LLM call is made."""
    fails = 0
    out = {}
    for e in spec["step2_soft"]:
        p = runmeta.path(2, e["case"])
        out[e["case"]] = json.loads(p.read_text()) if p.exists() else None
    print("\n== step 2: ClinVar exact match (HARD) ==")
    r = out.get("AITX-40002")
    if r is None:
        print("SKIP AITX-40002: no step 2 output on disk (run it with --eval first)")
    else:
        used = [(rec["vcv"], rec["title"]) for rec in r["clinvar"][0]["records"]]
        ok = all("c.101A>G" not in t for _, t in used)
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} AITX-40002 ITPR1: c.101A>G not used for ranking -> {used}")
    print("\n== step 2: primaries to eyeball (SOFT) ==")
    for e in spec["step2_soft"]:
        r = out.get(e["case"])
        if r is None:
            print(f"  {e['case']:<14} (no step 2 output on disk)   [{e['note']}]")
            continue
        pr = r.get("primary") or {}
        print(f"  {e['case']:<14} {pr.get('status', '?'):<12} {str(pr.get('label'))[:48]:<50}   [{e['note']}]")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", action="store_true", dest="eval_cases",
                    help="required: these expectations use the four evaluation cases")
    ap.add_argument("--step", type=int, choices=(1, 2), help="only this step")
    args = ap.parse_args()
    if not args.eval_cases:
        print(__doc__.strip().splitlines()[0])
        raise SystemExit("this script uses the evaluation cases: pass --eval to run it deliberately")
    spec = json.loads(SPEC.read_text())
    cases = json.loads(CASES.read_text())
    held = sorted(runmeta.eval_ids())
    print(f"[EVAL] running expectations for the evaluation cases {held}\n      {spec['why_kept']}\n")
    fails = 0
    if args.step in (None, 1):
        fails += step1(cases, spec)
    if args.step in (None, 2):
        fails += step2(spec)
    print(f"\n{'ALL HARD EXPECTATIONS PASSED' if not fails else f'{fails} HARD EXPECTATION(S) FAILED'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())

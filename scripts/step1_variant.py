"""Step 1 CLI: patient case JSON -> VariantProfile JSON.

Usage:
    python scripts/step1_variant.py data/cases/aitx_final_patients.json
    python scripts/step1_variant.py data/cases/practice/AGXT-c33dup.json --out out/step1

Accepts a single case object or an array of cases. Writes one JSON per case
and prints a one-line summary per variant. Exit code 1 if any check fails.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitx.variant.profile import build_profile, patient_summary  # noqa: E402
from aitx.variant.transcript import fetch_transcript  # noqa: E402


def run_case(case: dict) -> dict:
    profiles = []
    for v in case["patient"]["genotype"]:
        t = fetch_transcript(v["transcript"])
        profiles.append(build_profile(v, t))
    return {
        "id": case["id"],
        "step": "variant_profile",
        "variants": [p.to_dict() for p in profiles],
        "patient_summary": patient_summary(profiles),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", type=Path)
    ap.add_argument("--out", type=Path, default=Path("out/step1"))
    args = ap.parse_args()

    data = json.loads(args.cases.read_text())
    cases = data if isinstance(data, list) else [data]
    args.out.mkdir(parents=True, exist_ok=True)

    failed = False
    for case in cases:
        try:
            result = run_case(case)
        except Exception as e:  # noqa: BLE001 - report and continue with other cases
            print(f"[ERROR] {case.get('id')}: {e}")
            failed = True
            continue
        (args.out / f"{case['id']}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
        for v in result["variants"]:
            status = "OK  " if v["ok"] else "FAIL"
            ex = v["exon"]
            print(f"[{status}] {case['id']} {v['gene']} {v['variant_cdna']} | {v['variant_class']} | "
                  f"exon {ex.get('number')}/{ex.get('total')} | protein {v['protein_length']} aa | "
                  f"PTC {v['ptc_aa_position']} | NMD {v['nmd']['prediction']} | "
                  f"{v['mechanism_hypothesis']['hypothesis']} ({v['mechanism_hypothesis']['confidence']})")
            for c in v["checks"]:
                if c["status"] != "pass":
                    print(f"        {c['status'].upper()} {c['name']}: {c['detail']}")
            failed |= not v["ok"]
    print(f"\nWrote results to {args.out}/")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

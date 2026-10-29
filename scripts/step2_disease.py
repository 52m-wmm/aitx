"""Step 2 CLI: patient case JSON -> DiseaseResolution JSON.

Usage:
    AITX_LLM_API_KEY=... python scripts/step2_disease.py data/cases/practice/official_examples.json
    python scripts/step2_disease.py data/cases/aitx_final_patients.json --out out/step2

Accepts a single case object or an array of cases. Writes one JSON per case
plus sources_manifest.json, and prints a short summary per case. Exit code 1
if any check fails.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitx.disease import pipeline, resolve  # noqa: E402
from aitx.disease.sources import dump  # noqa: E402


def summary(r: dict) -> list[str]:
    p = r["primary"]
    lines = [f"[{'OK  ' if r['ok'] else 'FAIL'}] {r['patient_id']}: {p['status']} -> {p['label']} "
             f"{p['omim']} ({p['basis']}, confidence {p.get('confidence')})"]
    for a in p["alternatives"]:
        lines.append(f"        alt: {a['label']} ({a['id']})")
    for why in p["reasons"]:
        lines.append(f"        - {why}")
    terms = ", ".join(f"{'NOT ' if x['status'] == 'excluded' else ''}{x['label']}" for x in r["phenotypes"])
    lines.append(f"        phenotypes: {terms or '(none)'}")
    for c in r["checks"]:
        if c["status"] != "pass":
            lines.append(f"        {c['status'].upper()} {c['name']}: {c['detail']}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", type=Path)
    ap.add_argument("--out", type=Path, default=Path("out/step2"))
    ap.add_argument("--no-cache", action="store_true", help="bypass LLM and API caches")
    args = ap.parse_args()

    data = json.loads(args.cases.read_text())
    cases = data if isinstance(data, list) else [data]
    genes = {v["gene"] for c in cases for v in c["patient"]["genotype"]}
    res = resolve.load_resources(genes, use_cache=not args.no_cache)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "sources_manifest.json").write_text(dump(pipeline.S.manifest(res.files)))

    failed = False
    for case in cases:
        try:
            r = pipeline.run_case(case, res, use_cache=not args.no_cache)
        except Exception as e:  # noqa: BLE001 - report and continue with other cases
            print(f"[ERROR] {case.get('id')}: {type(e).__name__}: {e}")
            failed = True
            continue
        (args.out / f"{case['id']}.json").write_text(dump(r))
        print("\n".join(summary(r)))
        failed |= not r["ok"]
    print(f"\nWrote results to {args.out}/")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

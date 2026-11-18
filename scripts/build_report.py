"""Step 4: build reports from the ledgers (contract docs/step4_contract.md v1.0). No LLM.

Usage: python3 scripts/build_report.py --case PRAC-AGXT-c33dup
Writes out/step4/<case>.md, out/step4/<case>.trace.json and out/step4/submission.json (the upload array, the cases
built in this run), and prints the format check. Evaluation cases are refused.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx import runmeta  # noqa: E402
from aitx.evidence import action_identity
from aitx.report import assemble as A, sources as SRC, validate as V  # noqa: E402
from scripts.validate_report import validate_case  # noqa: E402


def report_safety(led: dict) -> dict:
    """Present every ledger drug, including drugs outside the recorded candidate-combination check.

    Missing operational records mean 'no check recorded', never absence of a clinical interaction or risk.
    No label is fetched and no clinical verdict or ledger check is rewritten here.
    """
    safety = copy.deepcopy(led["report_context"]["safety"])
    coverage = safety["coverage"]
    recorded = {r["drug"] for r in coverage}
    for a in led["actions"]:
        if action_identity.is_drug(a, led) and a["label"] not in recorded:
            coverage.append({"drug": a["label"], "interactions_checked": False, "contraindications_checked": False,
                             "evidence_ids": a["evidence_ids"], "note": "No safety-check record in the ledger; outside the checked drug combination."})
            recorded.add(a["label"])
    return safety


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", action="append", required=True)
    args = ap.parse_args()
    runmeta.refuse_eval_cases(args.case, "step 4 report")
    out = ROOT / "out" / "step4"
    out.mkdir(parents=True, exist_ok=True)
    sub, bad = [], []
    for cid in args.case:
        case = runmeta.find_case(cid)
        led = json.loads((ROOT / "out" / "step3" / f"{cid}.json").read_text())
        safety = report_safety(led)
        md, trace = A.assemble(led, case, SRC.date_of, safety)
        (out / f"{cid}.md").write_text(md)
        (out / f"{cid}.trace.json").write_text(json.dumps({"trace": trace, "safety": safety}, indent=1, ensure_ascii=False))
        sub.append({"id": cid, "report_markdown": md})
        bad += [f"{cid}: {p}" for p in V.check_markdown(md)]
        bad += [f"{cid}: {p}" for p in validate_case(cid)]
    text = json.dumps(sub, indent=1, ensure_ascii=False)
    (out / "submission.json").write_text(text)
    bad += V.check_submission(text)
    print("FORMAT CHECK: " + ("PASS" if not bad else "FAIL\n  " + "\n  ".join(bad)))
    print("STEP 5 CHECK: " + ("FAIL" if bad else "PASS"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

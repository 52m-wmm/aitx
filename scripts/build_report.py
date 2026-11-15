"""Step 4: build reports from the ledgers (contract docs/step4_contract.md v1.0). No LLM.

Usage: python3 scripts/build_report.py --case PRAC-AGXT-c33dup
Writes out/step4/<case>.md, out/step4/<case>.trace.json and out/step4/submission.json (the upload array, the cases
built in this run), and prints the format check. Evaluation cases are refused.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx import runmeta  # noqa: E402
from aitx.report import assemble as A, safety as S, sources as SRC, validate as V  # noqa: E402


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
        safety = S.check(A.drugs_for_safety(led))
        md, trace = A.assemble(led, case, SRC.date_of, safety)
        (out / f"{cid}.md").write_text(md)
        (out / f"{cid}.trace.json").write_text(json.dumps({"trace": trace, "safety": safety}, indent=1, ensure_ascii=False))
        sub.append({"id": cid, "report_markdown": md})
        bad += [f"{cid}: {p}" for p in V.check_markdown(md)]
    text = json.dumps(sub, indent=1, ensure_ascii=False)
    (out / "submission.json").write_text(text)
    bad += V.check_submission(text)
    print("FORMAT CHECK: " + ("PASS" if not bad else "FAIL\n  " + "\n  ".join(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

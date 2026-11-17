"""Step 5 deterministic report checks. No LLM or network. Run: --case PRAC-AGXT-c33dup."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx import runmeta
from aitx.report.validate import check_report


def validate_case(cid: str) -> list[str]:
    runmeta.refuse_eval_cases([cid], "Step 5 report validation")
    led = json.loads((ROOT / "out/step3" / f"{cid}.json").read_text())
    md = (ROOT / "out/step4" / f"{cid}.md").read_text()
    return check_report(md, led, cid)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", required=True)
    args = parser.parse_args()
    bad = [f"{cid}: {problem}" for cid in args.case for problem in validate_case(cid)]
    print("STEP 5 CHECK: " + ("FAIL\n" + "\n".join(bad) if bad else "PASS"))
    return int(bool(bad))


if __name__ == "__main__":
    raise SystemExit(main())

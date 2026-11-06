"""Did the 3e trial case write a complete ledger? (new-section rule, 2026-11-06)

Usage: python3 scripts/check_3e_trial.py PRAC-GRIN2B
Exit 0 only when the step 3 output exists, has no failing check, and carries the 3e search record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    case = sys.argv[1] if len(sys.argv) > 1 else "PRAC-GRIN2B"
    p = ROOT / "out" / "step3" / f"{case}.json"
    if not p.exists():
        print(f"3e trial: no output at {p}")
        return 1
    d = json.loads(p.read_text())
    bad = [c["name"] for c in d["checks"] if c["status"] == "fail"]
    rows = [a for a in d.get("actions", []) if a.get("section") == "drug_repurposing"]
    searched = d.get("repurposing_searches") or {}
    print(f"3e trial on {case}: {len(rows)} candidate rows, search recorded for {len(searched)} branch(es); "
          f"failing checks: {bad or 'none'}")
    for a in rows:
        print(f"    {a['label']} | {a['direction']} | {a['evidence_level']} | {a['target_level']}")
    for b, r in searched.items():
        print(f"    {b}: mechanism {r.get('mechanism')}, needed {r.get('needed_direction')}, "
              f"kept {r.get('kept')}, excluded {len(r.get('excluded') or [])}")
    return 1 if bad or not searched else 0


if __name__ == "__main__":
    raise SystemExit(main())

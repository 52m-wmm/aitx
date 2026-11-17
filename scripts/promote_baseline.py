"""Promote an explicitly approved candidate; never alter historical baselines.

Run only after the user has approved every change:
  .venv/bin/python scripts/promote_baseline.py --candidate <snapshot.json> --approval <approval.json>

Approval JSON: {date, commit, approver, reason, baseline_sha256, candidate_sha256,
               approved_changes: [{change_id, approved: true, reason}, ...]}.
Hashes must match the exact snapshots; approved change IDs must exactly match the recomputed diff.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import tempfile

from status_diff import BASELINES, ROOT, cell, compare, digest, load_snapshot


def promote(candidate: Path, approval: dict, commit: str, baselines: Path = BASELINES) -> None:
    current = baselines / "current/snapshot.json"
    before, after = load_snapshot(current), load_snapshot(candidate)
    candidate_bytes = candidate.read_bytes()
    (baselines / "approvals.md").read_text()  # an absent approval history must not be silently replaced
    if set(before["cases"]) != set(after["cases"]):
        raise ValueError("candidate must retain the complete baseline case set")
    if approval["baseline_sha256"] != digest(current.read_bytes()) or approval["candidate_sha256"] != digest(candidate_bytes):
        raise ValueError("approval does not match the exact current/candidate snapshots")
    if approval["commit"] != commit:
        raise ValueError("approval commit does not match HEAD")
    dt.date.fromisoformat(approval["date"])
    for field in ("approver", "reason"):
        if not isinstance(approval[field], str) or not approval[field].strip():
            raise ValueError(f"approval requires {field}")
    changes = compare(before, after)["changes"]
    approved = approval["approved_changes"]
    wanted = {r["change_id"] for r in changes}
    if len(approved) != len(wanted) or {r["change_id"] for r in approved} != wanted:
        raise ValueError("every diff entry must be individually approved; no missing or extra change IDs")
    for r in approved:
        if r["approved"] is not True or not isinstance(r["reason"], str) or not r["reason"].strip():
            raise ValueError(f"unapproved/unexplained change: {r['change_id']}")
    by_id = {r["change_id"]: r for r in approved}
    lines = ["", f"## {approval['date']} — {commit}", "", f"- Approver: {cell(approval['approver'])}",
             f"- Reason: {cell(approval['reason'])}", f"- Previous snapshot: {approval['baseline_sha256']}",
             f"- Approved candidate: {approval['candidate_sha256']}", "",
             "| Change ID | Case ID | Action | Branch | Old status | New status | Approved rationale |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in changes:
        values = [r[k] for k in ("change_id", "case_id", "action", "branch", "old_status", "new_status")]
        lines.append("| " + " | ".join(cell(v) for v in values + [by_id[r["change_id"]]["reason"]]) + " |")
    if not changes:
        lines.append("No action/status/reason/evidence changes (explicit empty change-list approval).")
    # Prepare the replacement first. Record approval before the atomic swap, so no unlogged candidate can enter current.
    with tempfile.TemporaryDirectory(prefix=".promote-", dir=current.parent) as directory:
        ready = Path(directory) / "snapshot.json"
        ready.write_bytes(candidate_bytes)
        with (baselines / "approvals.md").open("a") as log:
            log.write("\n".join(lines) + "\n")
        ready.replace(current)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--approval", type=Path, required=True)
    args = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    promote(args.candidate, json.loads(args.approval.read_text()), commit)
    print("Promoted the approved snapshot to baselines/current; historical baselines unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline action x branch snapshots. Never writes a baseline; promotion requires explicit approvals.

Run: .venv/bin/python scripts/status_diff.py --output-dir out/status_diff/review
     .venv/bin/python scripts/status_diff.py --compare step3a.2-accepted --output-dir out/status_diff/history
     .venv/bin/python scripts/status_diff.py --compare <earlier snapshot.json> --output-dir <new run>
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aitx import runmeta

BASELINES = ROOT / "baselines"
SCHEMA = "aitx-status-snapshot-v1"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def case_ids() -> list[str]:
    files = ("data/cases/practice/official_examples.json", "data/cases/blind/retest-20261112.json")
    ids = [c["id"] for f in files for c in json.loads((ROOT / f).read_text()) if c["id"] != "PRAC-DMD-del"]
    runmeta.refuse_eval_cases(ids, "status snapshot")
    if len(ids) != 15 or len(set(ids)) != 15:
        raise ValueError("expected the 15 approved practice/retest cases, excluding deferred DMD")
    return sorted(ids)


def action_id(a: dict) -> str:
    if a.get("action_key"):
        return a["action_key"]
    if a["section"] == "bespoke_therapies":
        return "modality:" + a["modality"]
    if a.get("searched_none") is True or (a.get("status_by_branch") and
            all(s["status"] == "searched_none" for s in a["status_by_branch"].values())):
        return "searched_none:" + a["section"]
    raise ValueError(f"action has no stable identity: {a['label']}")


def row_key(row: dict) -> tuple:
    return row["case_id"], row["section"], row["action_id"], row["branch"]


def build_snapshot(ledgers: Path, ids: list[str], label: str, missing: tuple = ()) -> dict:
    """Missing current files fail. Only explicitly absent historical cases are marked unavailable."""
    cases, grouped = {}, {}
    for cid in ids:
        if cid in missing:
            cases[cid] = {"available": False, "reason": "case/Step 3 not present in this historical baseline"}
            continue
        path = ledgers / f"{cid}.json"
        raw = path.read_bytes()
        led = json.loads(raw)
        meta = led["_meta"]
        cases[cid] = {"available": True, "ledger_path": str(path.resolve()), "ledger_sha256": digest(raw),
                      "code_commit": meta["code_commit"], "input_fingerprint": meta["input_fingerprint"]}
        for a in led["actions"]:
            for field in ("applies_to", "evidence_ids"):
                if not isinstance(a[field], list) or any(not isinstance(v, str) or not v for v in a[field]):
                    raise ValueError(f"{cid}: {field} must be a list of nonempty IDs")
            for branch in a["applies_to"] or [None]:
                if branch is not None and a.get("status_by_branch"):
                    state = a["status_by_branch"][branch]
                    status, reason = state["status"], state["reason"]
                elif a["section"] == "bespoke_therapies":
                    status, reason = a["classification"], a["conclusion"]
                    if a.get("failed_criterion"):
                        reason += " Failed criterion: " + a["failed_criterion"]
                    for field in ("exceptions", "unassessable_reason"):
                        if a.get(field):
                            reason += f" {field}: " + "; ".join(a[field])
                elif a["section"] == "drug_repurposing" and a["hypothesis"]:
                    status = "ungraded"
                    reason = "Hypothesis; no patient applicability grade recorded. " + a["conclusion"]
                else:
                    raise ValueError(f"{cid}: no status recorded for {a['label']} / {branch}")
                if not isinstance(status, str) or not status or not isinstance(reason, str) or not reason:
                    raise ValueError(f"{cid}: invalid status/reason for {a['label']} / {branch}")
                row = {"case_id": cid, "section": a["section"], "action_id": action_id(a),
                       "action": a["label"], "branch": branch}
                key = row_key(row)
                if key not in grouped:
                    grouped[key] = dict(row, statuses=[], reasons=[], evidence_ids=[], records=0)
                target = grouped[key]
                target["statuses"].append(status)
                target["reasons"].append(reason)
                target["evidence_ids"] += a["evidence_ids"]
                target["evidence_ids"] += [r["requirement_evidence"] for r in a.get("requirements", [])
                                           if branch in r["applies_to"]]
                target["records"] += 1
    rows = []
    for key in sorted(grouped, key=str):
        row = grouped[key]
        row["status"] = "; ".join(sorted(set(row.pop("statuses"))))
        row["reason"] = " | ".join(dict.fromkeys(row.pop("reasons")))
        row["evidence_ids"] = sorted(set(row["evidence_ids"]))
        rows.append(row)
    return {"schema": SCHEMA, "label": label, "created_at": int(time.time()), "cases": cases, "rows": rows}


def load_snapshot(path: Path) -> dict:
    snapshot = json.loads(path.read_text())
    if snapshot["schema"] != SCHEMA:
        raise ValueError(f"unsupported status snapshot: {path}")
    # Access required fields; missing data must never turn into an empty comparison.
    snapshot["cases"], snapshot["rows"], snapshot["label"]
    keys = [row_key(row) for row in snapshot["rows"]]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate action x branch rows in {path}")
    return snapshot


def compare(old: dict, new: dict) -> dict:
    before = {row_key(r): r for r in old["rows"]}
    after = {row_key(r): r for r in new["rows"]}
    changes = []
    for key in sorted(before.keys() | after.keys(), key=str):
        o, n = before.get(key), after.get(key)
        if o is not None and n is not None:
            fields = [f for f in ("status", "reason", "evidence_ids", "records", "action") if o[f] != n[f]]
            if not fields:
                continue
            kind = "status_changed" if "status" in fields else "details_changed"
            reason = f"Old ledger reason: {o['reason']} | New ledger reason: {n['reason']}"
        elif n is not None:
            available = key[0] in old["cases"] and old["cases"][key[0]]["available"]
            kind = "action_added" if available else "baseline_missing"
            fields = ["presence"]
            reason = ("No matching action/branch in baseline. " if available else
                      "Case/Step 3 absent from historical baseline; no old clinical status can be inferred. ") + n["reason"]
        else:
            kind, fields = "action_removed", ["presence"]
            reason = "No matching action/branch in current ledger. Old ledger reason: " + o["reason"]
        identity = json.dumps([key, kind, o, n], sort_keys=True, ensure_ascii=False).encode()
        r = n if n is not None else o
        changes.append({"change_id": digest(identity)[:16], "kind": kind, "case_id": r["case_id"],
                        "action": r["action"], "action_id": r["action_id"], "section": r["section"], "branch": r["branch"],
                        "old_status": o["status"] if o is not None else None,
                        "new_status": n["status"] if n is not None else None,
                        "change_reason": reason, "changed_fields": fields,
                        "old_evidence_ids": o["evidence_ids"] if o is not None else [],
                        "new_evidence_ids": n["evidence_ids"] if n is not None else [],
                        "review": "not_comparable" if kind == "baseline_missing" else "needs_review"})
    return {"baseline": old["label"], "candidate": new["label"],
            "baseline_missing_cases": [cid for cid in new["cases"]
                                       if cid not in old["cases"] or not old["cases"][cid]["available"]],
            "counts": dict(Counter(r["kind"] for r in changes)), "changes": changes}


def cell(value) -> str:
    return str(value if value is not None else "not recorded (absence, not a clinical status)").replace("\n", " ").replace("|", "\\|")


def markdown(result: dict) -> str:
    lines = ["# Action x branch status comparison", "", f"Baseline: {result['baseline']}",
             f"Counts: {json.dumps(result['counts'], sort_keys=True)}", "",
             "Baseline missing cases: " + (", ".join(result["baseline_missing_cases"]) or "none"), "",
             "Ledger reasons are recorded explanations, not proof a change is justified. Review every change; investigate unexplained changes as potential defects.", "",
             "| Change ID | Kind | Case ID | Section | Action | Branch | Old status | New status | Change reason |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in result["changes"]:
        lines.append("| " + " | ".join(cell(r[k]) for k in ("change_id", "kind", "case_id", "section", "action", "branch",
                                                          "old_status", "new_status", "change_reason")) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compare", default="current", help="current (default), step3a.2-accepted, or a status snapshot JSON")
    ap.add_argument("--ledgers", type=Path, default=ROOT / "out/step3")
    ap.add_argument("--output-dir", type=Path, default=ROOT / "out/status_diff")
    args = ap.parse_args()
    if BASELINES.resolve() == args.output_dir.resolve() or BASELINES.resolve() in args.output_dir.resolve().parents:
        raise ValueError("status_diff never writes baselines; use promote_baseline with explicit approvals")
    ref = {"current": BASELINES / "current/snapshot.json",
           "step3a.2-accepted": BASELINES / "historical/step3a.2-accepted/snapshot.json"}
    old_path = ref[args.compare] if args.compare in ref else Path(args.compare)
    old = load_snapshot(old_path)
    new = build_snapshot(args.ledgers, case_ids(), "current ledger " + runmeta.code_commit())
    result = compare(old, new)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate = json.dumps(new, ensure_ascii=False, indent=1) + "\n"
    result.update(baseline_sha256=digest(old_path.read_bytes()), candidate_sha256=digest(candidate.encode()))
    (args.output_dir / "snapshot.json").write_text(candidate)
    (args.output_dir / "diff.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    (args.output_dir / "diff.md").write_text(markdown(result))
    print(json.dumps({"cases": len(new["cases"]), "rows": len(new["rows"]), "baseline": str(old_path),
                      "baseline_missing_cases": result["baseline_missing_cases"], "changes": result["counts"],
                      "output_dir": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

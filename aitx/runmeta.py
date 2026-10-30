"""Step outputs on disk with provenance, so the pipeline can restart from any step.

Every out/step<N>/<case id>.json carries a "_meta" block:
  input_fingerprint     sha256 of the case JSON the step ran on
  upstream              {step: sha256 of that step's output file} it consumed
  code_commit           git HEAD at run time (with "+dirty" if the tree had changes)
Loading an earlier step's output checks that it was made from the same case input;
otherwise it is stale and the caller must rerun from that step.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


class StaleOutput(RuntimeError):
    pass


def fingerprint(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def code_commit() -> str:
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        return head + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def path(step: int, case_id: str, out: Path = OUT) -> Path:
    return out / f"step{step}" / f"{case_id}.json"


def write_output(step: int, case: dict, result: dict, upstream: dict[int, str] | None = None,
                 out: Path = OUT) -> str:
    """Write result with _meta; return the sha256 of the written file (for downstream 'upstream')."""
    result = dict(result)
    result["_meta"] = {"step": step, "case_id": case["id"], "input_fingerprint": fingerprint(case),
                       "upstream": {str(k): v for k, v in sorted((upstream or {}).items())},
                       "code_commit": code_commit(), "created_at": int(time.time())}
    p = path(step, case["id"], out)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    p.write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def load_output(step: int, case: dict, out: Path = OUT) -> tuple[dict, str]:
    """(result, file sha256) of an earlier step, or StaleOutput if missing / made from another input."""
    p = path(step, case["id"], out)
    if not p.exists():
        raise StaleOutput(f"{case['id']}: no step {step} output at {p}; run from step {step}")
    text = p.read_text()
    result = json.loads(text)
    meta = result.get("_meta") or {}
    if meta.get("input_fingerprint") != fingerprint(case):
        raise StaleOutput(f"{case['id']}: step {step} output was made from a different case input "
                          f"(or before provenance was recorded); run from step {step}")
    return result, hashlib.sha256(text.encode()).hexdigest()


def check_upstream(result: dict, step: int, upstream_hashes: dict[int, str]) -> None:
    """A loaded output must have been built on the upstream files that exist now."""
    want = (result.get("_meta") or {}).get("upstream", {})
    for k, h in upstream_hashes.items():
        if str(k) in want and want[str(k)] != h:
            raise StaleOutput(f"{result.get('_meta', {}).get('case_id')}: step {step} output was built on an "
                              f"older step {k} output; run from step {step}")

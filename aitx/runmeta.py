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
                       "code_commit": code_commit(), "code_fingerprint": code_fingerprint(), "created_at": int(time.time())}
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


# ------------------------------------------------------------------ freshness (acceptance, 2026-11-05)
# An acceptance score counts only outputs made by the current code from the current upstream files and case input.
CODE_PATHS = ("aitx", "config", "scripts/run_pipeline.py")
CASE_FILES = (ROOT / "data/cases/practice/official_examples.json", ROOT / "data/cases/aitx_final_patients.json",
              ROOT / "data/cases/validation/phase1_hf_unseen_genes.json")      # same list as scripts/run_pipeline.py


def code_fingerprint(root: Path = ROOT) -> str:
    """sha256 over the content of every tracked or new (not ignored) file the pipeline runs: code, prompts, config.
    Unlike code_commit it also tells two uncommitted ("+dirty") states apart."""
    try:
        files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "--", *CODE_PATHS], cwd=root,
                               capture_output=True, text=True, check=True).stdout.split("\n")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    h = hashlib.sha256()
    for f in sorted(x for x in files if x and not x.endswith((".pyc",)) and "__pycache__" not in x):
        p = root / f
        if p.is_file():
            h.update(f.encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


EVAL_FILE = ROOT / "data/cases/aitx_final_patients.json"


def eval_ids(path: Path = EVAL_FILE) -> set[str]:
    """Ids of the evaluation cases, read from their own file (decision 2026-11-08: nothing but an explicit
    --eval run may touch them, acceptance scripts included)."""
    if not Path(path).exists():
        return set()
    data = json.loads(Path(path).read_text())
    return {c["id"] for c in (data if isinstance(data, list) else [data])}


def refuse_eval_cases(case_ids, what: str = "acceptance") -> None:
    """Stop an acceptance run that names an evaluation case: expectations are tuned against what they show."""
    held = sorted(set(case_ids) & eval_ids())
    if held:
        raise SystemExit(f"{what} must not use the evaluation case(s) {held}: expectations are written from what "
                         f"a case shows, so using them would fit the pipeline to the cases it is judged on")


def find_case(case_id: str, files=CASE_FILES) -> dict | None:
    for f in files:
        if Path(f).exists():
            data = json.loads(Path(f).read_text())
            for c in data if isinstance(data, list) else data.get("cases", []):
                if c.get("id") == case_id:
                    return c
    return None


def freshness(step: int, case_id: str, out: Path = OUT, code: str | None = None) -> dict:
    """{fresh, reasons}: stale when the output is missing, has no code fingerprint (made before this check), was
    made by other code, from another case input, or on upstream step outputs that have since changed."""
    p = path(step, case_id, out)
    if not p.exists():
        return {"fresh": False, "reasons": ["no output"]}
    meta = json.loads(p.read_text()).get("_meta") or {}
    why = []
    have = meta.get("code_fingerprint")
    if not have:
        why.append(f"no code fingerprint (made {meta.get('code_commit')}, before the freshness check)")
    elif have != (code or code_fingerprint()):
        why.append(f"made by other code ({meta.get('code_commit')})")
    case = find_case(case_id)
    if case is None or meta.get("input_fingerprint") != fingerprint(case):
        why.append("made from another case input")
    for k, h in (meta.get("upstream") or {}).items():
        up = path(int(k), case_id, out)
        if not up.exists() or hashlib.sha256(up.read_bytes()).hexdigest() != h:
            why.append(f"step {k} output changed since")
    return {"fresh": not why, "reasons": why}


def apply_freshness(rows: list[dict], fresh: dict[str, dict]) -> None:
    """Rows on a stale case are not scored: ok False, stale True, the reasons as the problem."""
    for r in rows:
        f = fresh.get(r["case"]) or {"fresh": False, "reasons": ["not checked"]}
        r["stale"] = not f["fresh"]
        if r["stale"]:
            r["ok"] = False
            r["problem"] = "STALE output, not scored: " + "; ".join(f["reasons"])

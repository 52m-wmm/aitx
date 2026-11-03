"""Run the pipeline end to end, or restart from any step using earlier outputs on disk.

Usage:
    python scripts/run_pipeline.py data/cases/aitx_final_patients.json               # all steps
    python scripts/run_pipeline.py data/cases/aitx_final_patients.json --from-step 2  # reuse out/step1
    python scripts/run_pipeline.py cases.json --from-step 2 --to-step 2
    python scripts/run_pipeline.py --case PRAC-OTC --from-step 2           # one case, looked up in CASE_FILES

With --from-step N, outputs of steps < N are read from out/step<k>/<id>.json and must
have been produced from the same case input (and on the upstream files that exist
now); otherwise the run stops and says which step to rerun from. Steps N.. are run
and rewritten. Steps not implemented yet are listed in PLANNED.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from aitx import runmeta  # noqa: E402

PLANNED = {3: "therapy matching", 4: "existing options lookup", 5: "report assembly"}
USES_LLM = {2}                        # steps that call the LLM (the viewer warns before rerunning them)
CASE_FILES = [ROOT / "data/cases/practice/official_examples.json", ROOT / "data/cases/aitx_final_patients.json",
              ROOT / "data/cases/validation/phase1_hf_unseen_genes.json"]


def load_cases(path: Path | None, ids: list[str] | None) -> list[dict]:
    """Cases from `path` (default: every file in CASE_FILES), optionally only the given ids."""
    files = [path] if path else [f for f in CASE_FILES if f.exists()]
    cases = []
    for f in files:
        data = json.loads(f.read_text())
        cases += data if isinstance(data, list) else [data]
    if ids:
        missing = set(ids) - {c["id"] for c in cases}
        if missing:
            raise SystemExit(f"case id(s) not found: {sorted(missing)}")
        cases = [c for c in cases if c["id"] in ids]
    return cases


class Context:
    """Shared, lazily built resources (step-2 datasets are loaded once per run)."""

    def __init__(self, cases: list[dict], use_cache: bool):
        self.cases, self.use_cache, self._res = cases, use_cache, None

    def step2_resources(self):
        if self._res is None:
            from aitx.disease import resolve
            self._res = resolve.load_resources({v["gene"] for c in self.cases for v in c["patient"]["genotype"]},
                                               use_cache=self.use_cache)
        return self._res


def step1(case: dict, prior: dict, ctx: Context) -> dict:
    from step1_variant import run_case
    return run_case(case)


def step2(case: dict, prior: dict, ctx: Context) -> dict:
    from aitx.disease import pipeline
    return pipeline.run_case(case, ctx.step2_resources(), use_cache=ctx.use_cache, step1=prior.get(1))


STEPS = {1: step1, 2: step2}          # step -> fn(case, prior outputs {step: result}, ctx) -> result


def run(cases: list[dict], start: int, stop: int, use_cache: bool = True) -> int:
    ctx = Context(cases, use_cache)
    failed = False
    for case in cases:
        prior, hashes = {}, {}
        try:
            for k in range(1, start):
                prior[k], hashes[k] = runmeta.load_output(k, case)
                runmeta.check_upstream(prior[k], k, {j: hashes[j] for j in range(1, k)})
        except runmeta.StaleOutput as e:
            print(f"[STALE] {e}")
            failed = True
            continue
        for k in range(start, stop + 1):
            try:
                result = STEPS[k](case, prior, ctx)
            except Exception as e:  # noqa: BLE001 - report and move to the next case
                print(f"[ERROR] {case['id']} step {k}: {type(e).__name__}: {e}")
                failed = True
                break
            hashes[k] = runmeta.write_output(k, case, result, upstream={j: hashes[j] for j in range(1, k)})
            prior[k] = result
            ok = result.get("ok", all(v.get("ok", True) for v in result.get("variants", [])))
            print(f"[{'OK  ' if ok else 'FAIL'}] {case['id']} step {k} -> {runmeta.path(k, case['id'])}")
            failed |= not ok
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", type=Path, nargs="?", help="case JSON file (default: all files in CASE_FILES)")
    ap.add_argument("--case", action="append", dest="ids", help="run only this case id (repeatable)")
    ap.add_argument("--from-step", type=int, default=1)
    ap.add_argument("--to-step", type=int, default=max(STEPS))
    ap.add_argument("--no-cache", action="store_true", help="bypass LLM and API caches")
    args = ap.parse_args()
    for k in (args.from_step, args.to_step):
        if k not in STEPS:
            note = f" ({PLANNED[k]}, not implemented yet)" if k in PLANNED else ""
            ap.error(f"step {k} is not available{note}; implemented steps: {sorted(STEPS)}")
    if args.from_step > args.to_step:
        ap.error("--from-step is after --to-step")
    if not args.cases and not args.ids:
        ap.error("give a case file, --case ID, or both")
    return run(load_cases(args.cases, args.ids), args.from_step, args.to_step, not args.no_cache)


if __name__ == "__main__":
    raise SystemExit(main())

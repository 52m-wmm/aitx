"""The recommendation question (R15) on RETEST-PFN1 at reasoning_effort low and high (experiment, user request
2026-11-12, cap $0.05). Only the new question is asked; no pipeline output is written.

Entries: the 13 supplements the user judged wrong, plus three entries the chapter does recommend as controls.
The low run uses the production LLM cache (its answers are the ones the pipeline will reuse); the high run uses its
own cache in out_alt/recommend-effort-high/ because the production cache key does not include call parameters.

Usage (off-peak, AITX_LLM_API_KEY and AITX_LLM_BUDGET_USD set by the caller):
    python3 scripts/compare_recommend_effort.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from aitx import budget, peak  # noqa: E402
from aitx.disease import extract as X  # noqa: E402
from aitx.evidence import context_check as CC  # noqa: E402
import llm_cost  # noqa: E402
import validate_context_check as V  # noqa: E402

CASE = "RETEST-PFN1"
WRONG = ["vitamin E", "vitamin C", "B vitamins", "selenium", "zinc", "coenzyme Q10", "ginseng", "ginkgo biloba",
         "Maharishi Amrit Kalesh", "beta-carotene", "N-acetylcysteine", "L-methionine", "selegiline"]
CONTROLS = ["baclofen", "benzodiazepines", "gastrostomy tube"]
OUT = ROOT / "out_alt" / "recommend-effort"


def main() -> int:
    peak.guard()
    OUT.mkdir(parents=True, exist_ok=True)
    checks = {lab: V.checks_for({"case": CASE, "section": "supportive_management", "label": lab})[0]
              for lab in WRONG + CONTROLS}
    prod_cache, base = X.CACHE_DIR, dict(CC.CALL_PARAMS)
    res = {}
    for effort in ("low", "high"):
        CC.CALL_PARAMS = {**base, "reasoning_effort": effort}
        X.CACHE_DIR = prod_cache if effort == "low" else ROOT / "out_alt" / "recommend-effort-high" / "cache"
        t0 = time.time()
        rows = {}
        for lab, c in checks.items():
            try:
                r = CC.ask(c["header"], c["passage"], c["patient"], CC.questions_recommendation(lab, c["disease"]))
            except budget.OverBudget as e:            # the cap stops the run; what is done is kept and reported
                print(f"  {effort:4} STOPPED at {lab}: {e}")
                break
            q = r["questions"][0]
            rows[lab] = {"answers": q["answers"], "not_recommended": CC.not_recommended(r)}
            print(f"  {effort:4} {lab:28} {q['answers']} -> {'BLOCKED' if rows[lab]['not_recommended'] else 'kept'}",
                  flush=True)
        cost = llm_cost.summarize(t0)
        res[effort] = {"rows": rows, "cost": cost,
                       "asked": len(rows),
                       "blocked_wrong": sum(rows[l]["not_recommended"] for l in WRONG if l in rows),
                       "blocked_controls": sum(rows[l]["not_recommended"] for l in CONTROLS if l in rows)}
        print(f"== {effort}: blocked {res[effort]['blocked_wrong']}/{len(WRONG)} wrong, "
              f"{res[effort]['blocked_controls']}/{len(CONTROLS)} controls; {cost['calls']} calls, ${cost['usd']}")
    CC.CALL_PARAMS, X.CACHE_DIR = base, prod_cache
    (OUT / "result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

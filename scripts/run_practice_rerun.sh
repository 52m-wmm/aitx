#!/bin/zsh
# Practice-case rerun (steps 1-3) under caffeinate, off-peak only, with an optional wait and a run-specific cap.
#
#   scripts/run_practice_rerun.sh [--at HH:MM] [--batch-budget USD] [PRAC-X ...]
#
# --batch-budget: this run's own cap on top of what the Pacific day has already spent (AITX_LLM_BUDGET_USD
# counts the whole day). No case ids = all practice cases. Evaluation cases are never run from here.
set -u
if [[ -z "${AITX_CAFFEINATED:-}" ]]; then
  AITX_CAFFEINATED=1 exec caffeinate -i "$0" "$@"
fi
cd "$(dirname "$0")/.."
AT="" PER_RUN="0.3" CASES=()
while (( $# )); do
  case "$1" in
    --at) AT="$2"; shift 2;;
    --batch-budget) PER_RUN="$2"; shift 2;;
    *) CASES+=(--case "$1"); shift;;
  esac
done
P="${AITX_PYTHON:-python3}"
if [[ -n "$AT" ]]; then
  WAIT=$($P -c "
import datetime as d, zoneinfo as z
tz=z.ZoneInfo('America/Los_Angeles'); now=d.datetime.now(tz); h,m=map(int,'$AT'.split(':'))
t=now.replace(hour=h,minute=m,second=0,microsecond=0)
t+=d.timedelta(days=1) if t<=now else d.timedelta(0)
print(int((t-now).total_seconds()))")
  echo "=== waiting ${WAIT}s until $AT Pacific (caffeinate -i)"
  sleep "$WAIT"
fi
export AITX_LLM_API_KEY="${DEEPSEEK_API_KEY:?DEEPSEEK_API_KEY not set}"
export AITX_EXPECT_MODEL_PREFIX="deepseek-flash"
export AITX_LLM_BUDGET_USD=$($P -c "import sys;sys.path.insert(0,'.');from aitx import budget;print(round(budget.spent_today()+$PER_RUN,4))")
START=$(date +%s)
echo "=== practice rerun start $(TZ=America/Los_Angeles date '+%a %H:%M')  $($P -c 'import sys;sys.path.insert(0,".");from aitx import budget;print(budget.left())')"
$P scripts/run_pipeline.py data/cases/practice/official_examples.json --from-step 1 --to-step 3 "${CASES[@]}" --offpeak-only
echo "PIPELINE EXIT $?"
echo "=== cost"
$P scripts/llm_cost.py --last-minutes $(( ( $(date +%s) - START ) / 60 + 2 ))
echo "=== finished $(TZ=America/Los_Angeles date '+%a %H:%M %Z')"

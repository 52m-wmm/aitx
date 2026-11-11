#!/bin/zsh
# One blind-test batch: pipeline steps 1-3 for the named cases, then the machine check and the cost report.
#
#   scripts/run_blind_batch.sh [--at HH:MM] [--budget USD] BLIND-X BLIND-Y ...
#
# --at waits until that US-Pacific clock time (today, or tomorrow if it has passed) before starting.
# The whole script - the wait included - re-runs itself under `caffeinate -i`, so idle sleep cannot stall the wait
# (2026-11-11: a plain `sleep` did not count the hours the Mac slept and batch 2 never started) or the run.
# caffeinate -i does not stop sleep on a closed lid without external power.
# The budget is the day's cap (AITX_LLM_BUDGET_USD counts the whole Pacific day); the run is --offpeak-only.
set -u
if [[ -z "${AITX_CAFFEINATED:-}" ]]; then
  AITX_CAFFEINATED=1 exec caffeinate -i "$0" "$@"
fi
cd "$(dirname "$0")/.."
AT="" BUDGET="0.35" CASES=()
while (( $# )); do
  case "$1" in
    --at) AT="$2"; shift 2;;
    --budget) BUDGET="$2"; shift 2;;
    *) CASES+=(--case "$1"); shift;;
  esac
done
(( ${#CASES} )) || { echo "no cases given"; exit 2; }
P="${AITX_PYTHON:-python3}"
BATCH="${AITX_BLIND_BATCH:-20261108}"
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
export AITX_LLM_BUDGET_USD="$BUDGET"
echo "=== blind batch start $(TZ=America/Los_Angeles date '+%a %H:%M')  $($P -c 'import sys;sys.path.insert(0,".");from aitx import budget;print(budget.left())')"
$P scripts/run_pipeline.py "data/cases/blind/$BATCH.json" --from-step 1 --to-step 3 "${CASES[@]}" --offpeak-only
echo "PIPELINE EXIT $?"
echo "=== machine check"
$P scripts/blind_machine_check.py --batch "$BATCH"
echo "=== cost"
$P scripts/llm_cost.py --last-minutes 300
echo "=== finished $(TZ=America/Los_Angeles date '+%a %H:%M %Z')"

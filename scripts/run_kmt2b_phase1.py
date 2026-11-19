"""Two separately capped v6.1 extraction votes, second only after operational acceptance."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import llm_cost
from scripts.step2_stability import dump


def operational_anomalies(out):
    state=json.loads((out/'state.json').read_text());q=json.loads((out/'execution_proposal.json').read_text())
    fee=llm_cost.summarize(0,out/'llm_calls.jsonl');issues=[]
    if state['sources_completed']!=q['first_requests']:issues.append('incomplete blocks')
    if len(list((out/'raw_extractions').glob('*.json')))!=q['first_requests']:issues.append('response/input cache gap')
    if 'output truncated' in (out/'execution.log').read_text():issues.append('truncation occurred')
    if fee['missing_usage']:issues.append('unknown usage/fee')
    if fee['usd']>.035+1e-12:issues.append('stage fee above .035')
    if fee['peak_calls']:issues.append('peak call')
    if state['status']!='one new extraction vote complete; stopped pending user approval':issues.append(state['status'])
    return issues,fee


def run(out):
    if (out/'phase_state.json').exists():raise FileExistsError('phase already started; do not repeat')
    plan=json.loads((out/'plan.json').read_text());state={'votes':[],'status':'running'};dump(out/'phase_state.json',state)
    spent=0
    for vote in [2,3]:
        d=out/('vote'+str(vote));d.mkdir(exist_ok=True)
        q=json.loads((d/'execution_proposal.json').read_text())
        if vote==3:
            q.update(parent_spend_usd=round(plan['parent_prior_usd']+spent,9),parent_remaining_usd=round(plan['parent_remaining_usd']-spent,9),kmt_prior_usd=round(plan['kmt_prior_usd']+spent,9))
            (d/'execution_proposal.json').write_text(json.dumps(q,indent=2))
        argv=[str(ROOT/'.venv/bin/python'),'-u',str(ROOT/'scripts/run_kmt2b_extraction_vote.py'),'--out',str(d),'--proposal',str(d/'execution_proposal.json'),'--offpeak-only']
        with (d/'execution.log').open('w') as f:code=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,cwd=ROOT).returncode
        if not (d/'state.json').exists():
            state.update(status='stopped: runner failed before state persisted',failed_vote=vote,exit_code=code);dump(out/'phase_state.json',state);return 1
        issues,fee=operational_anomalies(d);spent+=fee['usd']
        state['votes'].append({'vote':vote,'exit_code':code,'operational_anomalies':issues,'fee':fee})
        state.update(spent_usd=round(spent,9),parent_remaining_usd=round(plan['parent_remaining_usd']-spent,9))
        budget_path=ROOT/'runs/step3_remaining_budget.json';b=json.loads(budget_path.read_text())
        b.update(accounted_usd=round(plan['parent_prior_usd']+spent,9),remaining_usd=round(plan['parent_remaining_usd']-spent,9),phase1={'path':str(out),'spent_usd':round(spent,9)},active_paid_processes=0)
        dump(budget_path,b)
        print('VOTE',vote,'cost',fee['usd'],'operational issues',issues,flush=True)
        if code or issues:
            state['status']='stopped on operational anomaly; no next vote';dump(out/'phase_state.json',state);return 1
        dump(out/'phase_state.json',state)
    state['status']='both authorized new votes complete; all paid execution stopped';dump(out/'phase_state.json',state)
    return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();raise SystemExit(run(a.out.resolve()))

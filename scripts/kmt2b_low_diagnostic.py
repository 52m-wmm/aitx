"""Exactly one authorized low-effort DD/ID request; no automatic retry or clinical write."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx import llm,peak,runmeta,session
from aitx.disease import extract as X
from scripts.run_kmt2b_extraction_vote import balance
from scripts.step2_stability import dump,install_campaign_guard
from scripts import llm_cost
OUT=ROOT/'runs/kmt2b-low-diagnostic-20261119'


def run():
    if (OUT/'started.json').exists():raise FileExistsError('diagnostic already started; do not repeat')
    peak.guard()
    inputs=json.loads((ROOT/'runs/kmt2b-v6_1-phase1-20261119/vote2/first_vote_source_records.json').read_text())
    unit=inputs[-1]
    if 'Developmental Delay / Intellectual Disability' not in unit['messages'][1]['content'].splitlines()[0]:raise ValueError('wrong target block')
    params=dict(X.CALL_PARAMS,reasoning_effort='low',max_tokens=14000)
    reservation=llm_cost.request_reservation(unit['messages'],params['max_tokens'],time.time())
    if reservation>.01:raise ValueError('single request reservation exceeds .01')
    OUT.mkdir(exist_ok=True);dump(OUT/'input.json',unit);dump(OUT/'params.json',params)
    balance(OUT/'balance_before.json')
    dump(OUT/'started.json',{'at':time.time(),'cap_usd':.01,'requests_authorized':1,'retry_authorized':False,'reservation_usd':reservation,'code_fingerprint':runmeta.code_fingerprint()})
    spent=install_campaign_guard(OUT,.01)
    sid=session.start(['KMT2B low diagnostic; exactly one call'],runmeta.code_fingerprint());dump(OUT/'session.json',{'id':sid})
    state={'status':'incomplete','completed':False,'no_retry':True,'reasoning_effort':'low'}
    try:
        response=llm.chat(unit['messages'],**params)
        dump(OUT/'api_response.json',response)
        if response['model']!='deepseek-flash':raise llm.ModelMismatch('model mismatch')
        choice=response['choices'][0];state['finish_reason']=choice['finish_reason']
        if choice['finish_reason']=='length':
            state['status']='truncated; stop, no retry'
        else:
            parsed=json.loads(choice['message']['content']);parsed['items'] # Required shape; never substitute defaults.
            dump(OUT/'parsed.json',parsed)
            state.update(status='complete; requires source comparison before any further spending',completed=True)
    finally:
        state['accounted_usd']=spent();dump(OUT/'state.json',state)
    balance(OUT/'balance_after.json')
    print(json.dumps(state),flush=True)
    return 0 if state['completed'] else 1

if __name__=='__main__':raise SystemExit(run())

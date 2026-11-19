"""One authorized new KMT2B extraction vote. Never launches checks or other Step 3 branches."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx import llm,peak,runmeta,session,budget
from aitx.disease import extract as X
from scripts.step2_stability import dump,install_campaign_guard
from scripts import llm_cost


def balance(path):
    cfg=llm.config()
    if not cfg['api_key']:raise ValueError('API key environment variable missing')
    req=urllib.request.Request(cfg['base_url']+'/user/balance',headers={'Authorization':'Bearer '+cfg['api_key']})
    with urllib.request.urlopen(req,timeout=30) as response:data=json.loads(response.read())
    dump(path,{'at':time.time(),'response':data})
    if not data['is_available']:raise ValueError('DeepSeek account unavailable')
    return data


def execute(out,proposal):
    if (out/'started.json').exists():raise FileExistsError('this authorized vote already started; do not repeat')
    peak.guard()
    q=json.loads(proposal.read_text())
    if q['code_fingerprint']!=runmeta.code_fingerprint():raise ValueError('clinical code changed since quotation')
    for name,sha in q['fixed_file_sha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('frozen input changed: '+name)
    cfg=llm.config()
    if cfg['base_url']!=q['provider'] or cfg['model']!=q['model']:raise ValueError('provider/model differs from quote')
    inputs=json.loads((proposal.parent/'first_vote_source_records.json').read_text())
    expected=q['first_requests'] if 'first_requests' in q else 4
    if len(inputs)!=expected:raise ValueError('fixed source request count differs from proposal')
    out.mkdir(parents=True,exist_ok=True)
    sample=q['sample'] if 'sample' in q else 1
    cap=min(q['incremental_cap_usd'],q['kmt_total_cap_usd']-q['kmt_prior_usd'],q['parent_remaining_usd']) if 'incremental_cap_usd' in q else .08
    if cap<=0:raise budget.OverBudget('no authorized funds remain')
    b=balance(out/'balance_before.json')
    dump(out/'started.json',{'at':time.time(),'case':'PRAC-KMT2B','authorized_new_votes':1,'first_requests':expected,'hard_cap_usd':cap,
                             'parent_spend_usd':q['parent_spend_usd'],'latest_instruction':'Run one new vote, report, then wait for approval'})
    dump(out/'frozen_inputs.json',inputs)
    os.environ.pop('AITX_LLM_CACHE_ONLY',None)
    X.CACHE_DIR=out/'responses';X.CACHE_DIR.mkdir(exist_ok=False)
    spend=install_campaign_guard(out,cap)
    sid=session.start(['one KMT2B extraction vote',str(out)],runmeta.code_fingerprint());dump(out/'session.json',{'id':sid})
    state={'status':'running','completed':[],'model':'deepseek-flash','new_vote':sample,'second_vote_authorized':False}
    try:
        for item in inputs:
            print('START',item['messages'][1]['content'].splitlines()[0],flush=True)
            # Distinct sample identity and no response-cache reuse.
            result=X._cached_chat(item['messages'],sample,False,prompt_version=item['prompt_version'],call_params=X.CALL_PARAMS)
            if result['served_model']!=q['model']:raise llm.ModelMismatch('server model alias differs from fixed model')
            path=out/'raw_extractions'/(item['call_id']+'.json')
            record={'complete':False,'safety_validation':'incomplete','source_selector_key':item['call_id'],
                    'messages':item['messages'],'response':result}
            dump(path,record)
            record['parsed']=json.loads(result['content']);dump(path,record)
            state['completed'].append({'selector_key':item['call_id'],'actual_call_id':result['call_id'],'source':item['messages'][1]['content'].splitlines()[0]})
            dump(out/'state.json',dict(state,accounted_usd=spend()))
            print('DONE',state['completed'][-1]['source'],'accounted_usd',spend(),flush=True)
        state['status']='one new extraction vote complete; stopped pending user approval'
    except (budget.OverBudget,peak.PeakHours,RuntimeError,llm.ModelMismatch) as e:
        state.update(status='stopped incomplete',error=str(e));print('STOP',type(e).__name__,str(e),flush=True)
    finally:
        if state['status']=='running':state['status']='stopped incomplete: exception; see execution.log'
        state.update(accounted_usd=spend(),remaining_parent_usd=q['parent_remaining_usd']-spend(),sources_completed=len(state['completed']),
                     next_vote_not_run=True,complete_step3a=False)
        dump(out/'state.json',state)
    balance(out/'balance_after.json')
    print('STOPPED',state['status'],'sources',len(state['completed']),'accounted_usd',spend(),flush=True)
    return 0 if len(state['completed'])==expected else 1


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--proposal',type=Path,required=True);ap.add_argument('--offpeak-only',action='store_true',required=True)
    a=ap.parse_args();raise SystemExit(execute(a.out.resolve(),a.proposal.resolve()))

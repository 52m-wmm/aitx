"""Read-only exact-input KMT2B quote; no API client is invoked."""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from aitx import runmeta
from aitx.disease import extract as X
from aitx.evidence import established as E,action_identity as I
from scripts import llm_cost
from scripts.step2_stability import dump


def offpeak_cost(usage):
    return (usage['prompt_cache_hit_tokens']*.003+usage['prompt_cache_miss_tokens']*.15+usage['completion_tokens']*.6)/1e6


def quote(out):
    if out.exists():raise FileExistsError(str(out))
    out.mkdir(parents=True)
    inputs=json.loads((ROOT/'runs/step3a-vote-quote-complete-20261118/PRAC-KMT2B.json').read_text())
    if len(inputs)!=4:raise ValueError('frozen source catalog changed; re-quote before running')
    keys={r['call_id']:r for r in inputs};samples=defaultdict(list)
    for n in [1,2]:
        source_session=json.loads((ROOT/'runs/step3-staged-050-v3-20261118/executions/PRAC-KMT2B'/str(n)/'session.json').read_text())
        path=Path(source_session['path'])/'calls.jsonl'
        with path.open() as stream:
            for line in stream:
                r=json.loads(line)
                if r['call_id'] not in keys or r['cache_hit']:continue
                if not r['usage']:raise ValueError('historical same-input paid usage missing; quote is unknown')
                if r['provider']!='https://api.deepseek.com' or r['served_model']!='deepseek-flash':continue
                if r['messages']!=keys[r['call_id']]['messages']:raise ValueError('source identity mismatch')
                samples[r['call_id']].append({'session':str(path),'cost_offpeak_usd':offpeak_cost(r['usage']),
                                             'usage':r['usage'],'accepted_max_tokens':r['call_params']['max_tokens']})
    units=[]
    for key,src in keys.items():
        if not samples[key]:raise ValueError('no exact-input real usage: '+key)
        units.append({'key':key,'source':src['messages'][1]['content'].splitlines()[0],'new_requests':2,
                      'mean_accepted_response_usd':statistics.mean(r['cost_offpeak_usd'] for r in samples[key]),
                      'two_new_responses_usd':2*statistics.mean(r['cost_offpeak_usd'] for r in samples[key]),'samples':samples[key],
                      'base_reservation_usd':llm_cost.request_reservation(src['messages'],16384,1795014000),
                      'length_retry_reservation_usd':llm_cost.request_reservation(src['messages'],32768,1795014000)})
    session_paths={r['session'] for unit in units for r in unit['samples']};chapter=0
    for path in session_paths:
        for line in Path(path).read_text().splitlines():
            r=json.loads(line)
            if not r['cache_hit'] and r['messages'][0]['content']==E.CHAPTERS_SYSTEM:chapter+=offpeak_cost(r['usage'])
    attempts=json.loads((ROOT/'runs/step3-staged-050-v3-20261118/attempt_summary.json').read_text())
    observed=[r for r in attempts if r['profile']=='v3' and r['case']=='PRAC-KMT2B']
    if len(observed)!=2:raise ValueError('historical two-vote accounting changed')
    total=sum(r['usd'] for r in observed);accepted=sum(u['two_new_responses_usd'] for u in units)
    files=[I.REGISTRY,ROOT/'out/step1/PRAC-KMT2B.json',ROOT/'out/step2/PRAC-KMT2B.json',ROOT/'out/step3/PRAC-KMT2B.json',ROOT/'scripts/replay_step3a.py']
    files.extend(p for p in (ROOT/'data/rules').rglob('*') if p.is_file())
    result={'case':'PRAC-KMT2B','units':units,'base_new_requests':8,'historical_length_retries':sum(r['truncation_retries'] for r in observed),
            'historical_accepted_responses_estimate_usd':accepted,'historical_length_retry_usd':total-chapter-accepted,
            'historical_two_votes_total_excluding_chapter_usd':total-chapter,'proposed_hard_cap_usd':.08,
            'scope':'Two new source-extraction votes only; cache-only normalization/assembly/checks. New context/support/repair/synonym work remains untested. Never Step3b-e.',
            'provider':'https://api.deepseek.com','model':'deepseek-flash','documented_version':'DeepSeek-V4.1-Flash-1017',
            'base_params':dict(X.CALL_PARAMS),'prompt_version':E.PROMPT_VERSION,'length_retry_max_tokens':32768,
            'code_fingerprint':runmeta.code_fingerprint(),'fixed_file_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            'model_calls':0,'actual_usd':0,'approved_for_real_calls':False,'parent_spend_usd':0.216072843,'parent_remaining_usd':0.283927157,'new_budget_granted':False}
    dump(out/'quote.json',result);dump(out/'first_vote_source_records.json',inputs)
    print(json.dumps({k:v for k,v in result.items() if k not in ['units','fixed_file_sha256']},indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();quote(a.out.resolve())

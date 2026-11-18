"""Quote three-vote extraction from current ledgers and recorded source inputs; no APIs."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import status_diff as SD
from scripts.step2_stability import dump
from aitx.evidence import established as E,support_check as SC


def counts(records):
    unique={r['call_id']:r for r in records}
    return {'per_case_inputs':len(records),'unique_inputs':len(unique),
            'by_type_per_case':dict(Counter(r['extract_kind'] for r in records)),
            'by_type_unique':dict(Counter(r['extract_kind'] for r in unique.values())),
            'extra_votes_shared':2*len(unique),'extra_votes_independent_cases':2*len(records),
            'full_triple_cold_shared':3*len(unique)}


def quote(out):
    if out.exists():raise FileExistsError(str(out))
    out.mkdir(parents=True)
    ledgers={c:json.loads((ROOT/'out/step3'/(c+'.json')).read_text()) for c in SD.case_ids()}
    systems={E.EXTRACT_SYSTEM:'GR section',E.ROW_SYSTEM:'GR row',E.REQ_SYSTEM:'FDA conditions',E.F.LIT_SYSTEM:'literature'}
    runs=defaultdict(lambda:defaultdict(list))
    for path in (ROOT/'runs/sessions').glob('*/calls.jsonl'):
        with path.open() as stream:
            for line in stream:
                r=json.loads(line)
                if r['case'] not in ledgers or r['prompt_version']!=E.PROMPT_VERSION:continue
                if r['at']>ledgers[r['case']]['_meta']['created_at']+1:continue
                if r['messages'][0]['content'] not in systems:continue
                runs[r['case']][r['run_id']].append(dict(r,extract_kind=systems[r['messages'][0]['content']],source_log=str(path)))
    allrows=[];percase=[];context_keys=set();auxiliary=[]
    def walk(v):
        if isinstance(v,dict):
            if 'call_ids' in v:context_keys.update(x for x in v['call_ids'] if isinstance(x,str))
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    for cid,led in ledgers.items():
        sessions=runs[cid]
        if sessions:
            selected=max(sessions,key=lambda k:max(r['at'] for r in sessions[k]))
            rows=list({r['call_id']:r for r in sessions[selected]}.values())
            reason='latest recorded source-input session preceding current ledger creation'
        else:
            # Only an explicit no-source ledger may contribute zero, never a missing-log default.
            if not all(not t['chapters'] and 'literature' in t and t['literature']['count']==0 and not t['literature']['papers'] for t in led['supportive_tiers'].values()):
                raise ValueError('source input history missing: '+cid)
            if any(a['action_key'] for a in led['actions'] if a['section'] in E.SECTIONS_3A):raise ValueError('unexplained zero source inputs: '+cid)
            rows=[];selected=None;reason='explicit no selected chapters or literature sources'
        if selected is not None:
            path=ROOT/'runs/sessions'/selected/'calls.jsonl'
            with path.open() as stream:
                for line in stream:
                    r=json.loads(line)
                    if r['case']!=cid:continue
                    sysmsg=r['messages'][0]['content'];user=r['messages'][1]['content']
                    if r['prompt_version']==E.PROMPT_VERSION and sysmsg in [E.CHAPTERS_SYSTEM,E.SYNONYM_SYSTEM]:
                        auxiliary.append(dict(r,aux_kind='chapter selection' if sysmsg==E.CHAPTERS_SYSTEM else 'synonym merge'))
                    elif r['prompt_version']==SC.PROMPT_VERSION and sysmsg==SC.SYSTEM and ('The article recommends or presents' in user or 'acts on the defective gene product or the disease mechanism' in user):
                        auxiliary.append(dict(r,aux_kind='3a support check'))
        allrows+=rows
        percase.append({'case':cid,'session':selected,'reason':reason,**counts(rows)})
        dump(out/(cid+'.json'),rows)
        for a in led['actions']:
            if a['section'] in E.SECTIONS_3A and 'context_check' in a:walk(a['context_check'])
    calibration=json.loads((ROOT/'runs/step3a-replay-v2-20261118/analysis.json').read_text())['cost_samples']
    mean=calibration[E.PROMPT_VERSION]['mean_offpeak_usd'];cm=calibration['context-check-v3']['mean_offpeak_usd']
    result={'cases':percase,**counts(allrows),'source_request_mean_usd':mean,'context_request_mean_usd':cm,
            'extra_extraction_estimate_shared_usd':counts(allrows)['extra_votes_shared']*mean,
            'extra_extraction_estimate_independent_cases_usd':counts(allrows)['extra_votes_independent_cases']*mean,
            'full_cold_extraction_estimate_shared_usd':counts(allrows)['full_triple_cold_shared']*mean,
            'existing_context_request_keys':len(context_keys),'existing_context_cold_reference_usd':len(context_keys)*cm,
            'model_calls':0,'network_calls':0,'actual_usd':0,
            'limitation':'Frozen historical source-input catalog, same-model pooled fee estimate. New union-driven inputs/checks, auxiliary calls, and retries are additional; this is not a proof of 15-case cache completeness.'}
    aux={r['call_id']:r for r in auxiliary}
    result.update(auxiliary_requests=len(aux),auxiliary_types=dict(Counter(r['aux_kind'] for r in aux.values())),
                  full_cold_reference_requests=result['full_triple_cold_shared']+len(context_keys)+len(aux),
                  full_cold_reference_usd=result['full_cold_extraction_estimate_shared_usd']+result['existing_context_cold_reference_usd']+len(aux)*mean,
                  auxiliary_price_note='Uses pooled 3a-v5 mean as a proxy for auxiliary/support calls; no source-specific measured price claimed.')
    dump(out/'auxiliary_calls.json',list(aux.values()))
    dump(out/'selected_source_calls.json',list({r['call_id']:r for r in allrows}.values()));dump(out/'quote.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();quote(a.out.resolve())

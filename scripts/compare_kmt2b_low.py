"""Source-scoped comparison for the one-call low diagnostic; no model/network use."""
import json
from pathlib import Path
from aitx.evidence import actions as A,ledger as L
from scripts.step2_stability import dump
from scripts import llm_cost
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/kmt2b-low-diagnostic-20261119'


def name_key(name):
    n=L._norm(name)
    if n in {'iep','individualized education plan (iep)','individualized education plan'}:return 'IEP'
    if n in {'504 plan','section 504 plan'}:return '504 plan'
    t=A.therapy_type(name)
    if t in {'physical_therapy','occupational_therapy','speech_language_therapy','feeding_therapy','early_intervention'}:return t
    return n


def missing_actions(items,expected):
    observed={name_key(i['name']) for i in items}
    return [name for name in expected if name_key(name) not in observed]


def compare():
    input=json.loads((OUT/'input.json').read_text());selector=input['call_id'];text=input['messages'][1]['content'];refs={}
    first=ROOT/'runs/kmt2b-v6-chunked-20261119/raw_extractions'/(selector+'.json')
    refs['v6.1_first_full']=json.loads(first.read_text())['parsed']['items']
    scope={}
    for vote in [1,2]:
        p=ROOT/'runs/step3-offline-audit-v2-20261118/PRAC-KMT2B'/str(vote)/'raw_extractions'/(selector.split('-chunk')[0]+'.json')
        items=json.loads(p.read_text())['parsed']['items']
        refs['v5_'+str(vote)]=[i for i in items if L.quote_in(i['quote'],text)]
        scope['v5_'+str(vote)]={'reference':str(p),'outside_target_block':[i for i in items if not L.quote_in(i['quote'],text)]}
    refs['low']=json.loads((OUT/'parsed.json').read_text())['items']
    expected=json.loads((OUT/'expected_before_call.json').read_text())['expected_clear_actions']
    missing=missing_actions(refs['low'],expected);names=list(dict.fromkeys(name_key(i['name']) for items in refs.values() for i in items))
    rows=[{'action':name,'by_reference':{k:[i for i in items if name_key(i['name'])==name] for k,items in refs.items()}} for name in names]
    response=json.loads((OUT/'api_response.json').read_text());usage=response['usage'];reason=usage['completion_tokens_details']['reasoning_tokens']
    quote_fail=[i for i in refs['low'] if not L.quote_in(i['quote'],text)]
    completed=response['choices'][0]['finish_reason']=='stop'
    result={'completed':completed,'gate_passed':completed and not missing and not quote_fail,
        'missing_predeclared_actions':missing,'invalid_source_quotes':quote_fail,'scope':scope,'comparisons':rows,
        'request_params':json.loads((OUT/'params.json').read_text()),'model':response['model'],
        'reasoning_tokens':reason,'content_tokens':usage['completion_tokens']-reason,'cost':llm_cost.summarize(0,OUT/'llm_calls.jsonl'),
        'followup_authorization_condition_met':completed and not missing and not quote_fail,'continue_paid_execution':False,
        'note':'Gate uses predeclared named actions, never their incidental occurrence inside another quote. Default remains unchanged if gate fails.'}
    dump(OUT/'comparison.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['scope','comparisons']},ensure_ascii=False,indent=2))

if __name__=='__main__':compare()

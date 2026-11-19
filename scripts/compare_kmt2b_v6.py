"""Compare the authorized v6 extraction with frozen v5 observations, no pipeline/network calls."""
import json,re
from collections import Counter,defaultdict
from pathlib import Path
from scripts.kmt2b_condition_recount import canonical,risk_rationale
from scripts.kmt2b_shadow_votes import norm
from scripts.step2_stability import dump
from scripts import llm_cost
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/kmt2b-v6-one-vote-20261119'

def compare():
    raw=[json.loads(p.read_text()) for p in sorted((RUN/'raw_extractions').glob('*.json'))]
    complete=len(raw)==4
    items=defaultdict(list)
    for r in raw:
        for it in r['parsed']['items']:
            items[norm(it['name'])].append({'item':it,'source':r['messages'][1]['content'].splitlines()[0],
                'input':r['messages'][1]['content'],'call_id':r['response']['call_id'],
                'quote_in_input':norm(it['quote']) in norm(r['messages'][1]['content'])})
    old=json.loads((ROOT/'runs/kmt2b-condition-recount-20261119/semantic_shadow.json').read_text())
    candidate_rows=[];risk_rows=[]
    for a in old['actions']:
        hits=items[a['name']];new_conditions=[]
        for hit in hits:
            it=hit['item'];reqs=it['requirements']+([{'text':it['manifestation'],'field':'manifestation'}] if it['manifestation'] else [])
            for req in reqs:new_conditions.append({'canonical':canonical(req),'requirement':req,'quote':it['quote'],'source':hit['source'],'call_id':hit['call_id']})
        for c in a['conditions']:
            result={'action':a['name'],'old':c,'new_action_literal_match':bool(hits) if complete else None,'new_conditions':new_conditions,
                'canonical_condition_retained':any(tuple(c['canonical'])==tuple(x['canonical']) for x in new_conditions) if complete else None,
                'verdict':'needs source review; presence is not medical correctness' if complete else 'not_tested: incomplete source extraction',
                'comparison_valid':complete}
            if len(c['votes'])<3:candidate_rows.append(result)
            if c['purpose_or_risk_rationale']:
                result=dict(result,new_risk_misextract=any(risk_rationale(x['requirement']['text'],x['quote']) for x in new_conditions) if complete else None)
                risk_rows.append(result)
    assert len(candidate_rows)==42
    oldnames={a['name'] for a in old['actions']};newnames={k for k,v in items.items() if v}
    result={'source_extraction_complete':complete,'sources_completed':len(raw),'scope':'one v6 extraction only; no checks, assembly, other steps or new medical conclusions',
        'items':dict(items),'old42_comparison':candidate_rows,'risk3_comparison':risk_rows,
        'new_literal_names':sorted(newnames-oldnames),'old_literal_names_absent':sorted(oldnames-newnames) if complete else [],
        'source_counts':[(r['messages'][1]['content'].splitlines()[0],len(r['parsed']['items'])) for r in raw],
        'cost':llm_cost.summarize(0,RUN/'llm_calls.jsonl')}
    dump(RUN/'comparison.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('items','old42_comparison','risk3_comparison')},ensure_ascii=False,indent=2))
    for row in risk_rows:print('RISK',row['action'],row['new_risk_misextract'],row['new_action_literal_match'])
if __name__=='__main__':compare()

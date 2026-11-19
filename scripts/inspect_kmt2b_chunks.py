"""Read saved chunk responses; group names/conditions without clinical grading or new calls."""
from pathlib import Path
from collections import defaultdict,Counter
import json
from scripts.kmt2b_shadow_votes import norm
from scripts.kmt2b_condition_recount import canonical,risk_rationale
from scripts.step2_stability import dump
from scripts import llm_cost
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/kmt2b-v6-chunked-20261119'

def inspect():
    manifest=json.loads((RUN/'chunk_manifest.json').read_text());seen=[];actions=defaultdict(list)
    for row in manifest:
        p=RUN/'raw_extractions'/(row['selector_key']+'.json')
        if not p.exists():continue
        r=json.loads(p.read_text());seen.append(row)
        for item in r['parsed']['items']:
            actions[norm(item['name'])].append({'item':item,'call_id':r['response']['call_id'],'source':row['source'],
                'start':row['start'],'end':row['end'],'quote_in_chunk':norm(item['quote']) in norm(r['messages'][1]['content'])})
    complete=len(seen)==len(manifest);raw=[];meaning=[];risk=[]
    for name,mentions in sorted(actions.items()):
        conditions=defaultdict(list);sem=defaultdict(list)
        for m in mentions:
            it=m['item']
            for req in it['requirements']:
                key=json.dumps({k:norm(v) if isinstance(v,str) else v for k,v in req.items()},sort_keys=True)
                conditions[key].append(dict(m,requirement=req));sem[canonical(req)].append(dict(m,requirement=req))
            if it['manifestation']:
                req={'text':it['manifestation'],'field':'manifestation'}
                conditions['manifestation:'+norm(it['manifestation'])].append(dict(m,requirement=req));sem[canonical(req)].append(dict(m,requirement=req))
        raw.append({'action':name,'conditions':[{'key':k,'observations':v} for k,v in conditions.items()]})
        meaning.append({'action':name,'conditions':[{'key':k,'observations':v} for k,v in sem.items()]})
        for k,v in sem.items():
            if any(risk_rationale(x['requirement']['text'],x['item']['quote']) for x in v):risk.append({'action':name,'key':k,'observations':v})
    result={'complete_source_extraction':complete,'chunks_complete':len(seen),'chunks_planned':len(manifest),
        'action_name_groups':len(actions),'raw_item_mentions':sum(map(len,actions.values())),
        'raw_condition_variants':sum(len(x['conditions']) for x in raw),'canonical_condition_variants':sum(len(x['conditions']) for x in meaning),
        'actions':dict(actions),'raw_conditions':raw,'semantic_conditions':meaning,'risk_rationale_misextract_candidates':risk,
        'cost':llm_cost.summarize(0,RUN/'llm_calls.jsonl'),'complete_step3a':False,'no_new_checks':True}
    dump(RUN/'inspection.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['actions','raw_conditions','semantic_conditions','risk_rationale_misextract_candidates']},ensure_ascii=False,indent=2))
    for name,items in actions.items():
        if any(s in name for s in ['dbs','brain stimulation','504','dda','developmental disabilities','orthos','walkers','adaptive','iep','education plan']):print('FOCUS',name,len(items))
    for r in risk:print('RISK',r['action'],r['key'])
def review_old42(result):
    r=RUN;s=result;old=json.loads((ROOT/'runs/kmt2b-condition-recount-20261119/semantic_shadow.json').read_text())
    aliases={'antimuscarinic (anticholinergic) agents':'anticholinergic agents','augmentative and alternative communication (aac)':'augmentative and alternative communication [aac]','physical therapy (pt)':'physical therapy','occupational therapy (ot)':'occupational therapy','iep':'individualized education plan (iep)','dbs':'deep brain stimulation (dbs)'}
    review=[]
    for a in old['actions']:
     for c in a['conditions']:
      if len(c['votes'])==3:continue
      newname=aliases[a['name']] if a['name'] in aliases else a['name'];items=s['actions'][newname] if newname in s['actions'] else []
      new=[]
      for m in items:
       it=m['item'];reqs=it['requirements']+([{'text':it['manifestation'],'field':'manifestation'}] if it['manifestation'] else [])
       for q in reqs:new.append({'canonical':canonical(q),'original':q,'quote':it['quote'],'call_id':m['call_id']})
      key=c['canonical'];retained=any(tuple(x['canonical'])==tuple(key) for x in new)
      if not items:category='not recalled or name unresolved; needs_review'
      elif retained:category='retained/reexpressed; not a medical correctness verdict'
      elif 'confirmed diagnosis' in ' '.join(map(str,key)):category='explicit same-sentence diagnosis restriction omitted; needs_review'
      elif "academic material" in ' '.join(map(str,key)):category='local IEP service restriction not extracted; needs_review'
      elif key[0]=='age_interval_closed' or 'developmental delay / intellectual disability' in ' '.join(map(str,key)):category='chapter/paragraph context no longer inferred; code handling not tested; needs_review'
      elif a['name']=='chest physical therapy' and key[1]=='pulmonary infections':category='risk rationale removed in this item; improvement supported by quote'
      elif a['name']=='adaptive aids' and key[1]=='ambulation':category='functional objective no longer treated as patient manifestation; source review retained'
      elif a['name']=='applied behavior analysis (aba)' and key[0]=='manifestation':category='individualization rationale no longer treated as manifestation; source review retained'
      else:category='different/absent condition; needs_review'
      review.append({'action':a['name'],'matched_new_name':newname,'old':c,'new':new,'retained':retained,'review':category,'clinical_effective':False})
    assert len(review)==42
    (r/'old42_review.json').write_text(json.dumps({'aliases_for_review_only':aliases,'note':'Display alignment backed by literal parenthetical/abbreviation or same quoted action; does not alter action keys, medical rules, raw condition counts or Ledger','counts':dict(Counter(x['review'] for x in review)),'conditions':review},ensure_ascii=False,indent=2))
    print(json.dumps(dict(Counter(x['review'] for x in review)),ensure_ascii=False,indent=2))

if __name__=='__main__':
    inspect()
    review_old42(json.loads((RUN/'inspection.json').read_text()))

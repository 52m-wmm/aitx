"""Deterministic three-vote shadow audit; never calls a provider or publishes a Ledger."""
from collections import defaultdict,Counter
import json,re
from pathlib import Path
from aitx.evidence import actions as A,examples as EX
from scripts.kmt2b_condition_recount import canonical,risk_rationale
from scripts.step2_stability import dump
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/kmt2b-v6_1-phase1-20261119'
SECTIONS={'existing_targeted_therapies','supportive_management','contraindications_precautions'}


def identity(name,quote=""):
    n=EX.norm(name)
    n=re.sub(r'\s*[\[(](?:gpi-dbs|aac|pt|ot)[\])]$','',n)
    if n in {'anticholinergic agents','antimuscarinic agents','antimuscarinic (anticholinergic) agents'}:return 'antimuscarinic (anticholinergic) agents'
    if n=='antibiotics' and 'prophylactic antibiotics' in EX.norm(quote):return 'prophylactic antibiotics'  # Review alignment only; original name/quote retained.
    if n=='subthalamic nucleus deep brain stimulation':return 'subthalamic nucleus dbs'
    t=A.therapy_type(n)
    if t in {'physical_therapy','occupational_therapy','speech_language_therapy','feeding_therapy','early_intervention'}:return 'therapy:'+t
    return n


def evaluate():
    plan=json.loads((OUT/'plan.json').read_text());dirs=[Path(plan['vote1']),OUT/'vote2',OUT/'vote3']
    groups=defaultdict(list);complete=[];stats=[];sources=[]
    for vote,d in enumerate(dirs,1):
        inputs=json.loads((d/'first_vote_source_records.json').read_text());units=[];per_source=defaultdict(list)
        for entry in inputs:
            p=d/'raw_extractions'/(entry['call_id']+'.json')
            if not p.exists():continue
            raw=json.loads(p.read_text());units.append(raw)
            for item in raw['parsed']['items']:per_source[entry['messages'][1]['content'].splitlines()[0]].append(dict(item,_call_id=raw['response']['call_id'],_quote_in_input=EX.norm(item['quote']) in EX.norm(raw['messages'][1]['content'])))
        complete.append(len(units)==len(inputs));rawnames=set();groupednames=set()
        for section,items in per_source.items():
            for item in items:rawnames.add(identity(item['name']))
            for item in EX.group_items(items):
                key=identity(item['name'],item['quote']);groupednames.add(key)
                groups[key].append({'vote':vote,'source':section,'item':item,'call_id':item['_call_id'],
                    'kind_source':'member inference; unknown' if item['example_member'] is not None else 'model' } if 'example_member' in item else
                    {'vote':vote,'source':section,'item':item,'call_id':item['_call_id'],'kind_source':'model'})
        stats.append({'vote':vote,'completed_blocks':len(units),'expected_blocks':len(inputs),'raw_names_after_review_alignment':len(rawnames),'post_examples_groups':len(groupednames)})
    actions=[];bad_majority=[];single=[];risk_predicates=defaultdict(list)
    for key,observations in sorted(groups.items()):
        conditions=defaultdict(list);members=defaultdict(list);kinds=defaultdict(set)
        for o in observations:
            item=o['item']
            if o['kind_source']=='model':kinds[item['kind']].add(o['vote'])
            reqs=item['requirements']+([{'field':'manifestation','text':item['manifestation']}] if item['manifestation'] else [])
            for req in reqs:conditions[('parent',)+canonical(req)].append(dict(o,requirement=req))
            if 'examples' in item:
                for name in item['examples']:members[name].append(o)
            member=item['example_member'] if 'example_member' in item else None
            if member:
                for req in member['requirements']+([{'field':'manifestation','text':member['manifestation']}] if member['manifestation'] else []):
                    conditions[('member:'+EX.norm(member['name']),)+canonical(req)].append(dict(o,requirement=req))
        cs=[]
        for ck,obs in conditions.items():
            votes=sorted({o['vote'] for o in obs});risk_votes=sorted({o['vote'] for o in obs if risk_rationale(o['requirement']['text'],o['item']['quote'])})
            c={'canonical':ck,'votes':votes,'majority':len(votes)>=2,'risk_votes':risk_votes,'needs_review':len(votes)<3 or bool(risk_votes),
               'clinical_effective':False,'observations':obs}
            cs.append(c)
            for o in obs:
                if risk_rationale(o['requirement']['text'],o['item']['quote']):risk_predicates[(key,EX.norm(o['requirement']['text']))].append(o)
            if len(votes)==1:single.append({'action':key,'condition':c})
        majority=[kind for kind,votes in kinds.items() if len(votes)>=2]
        actions.append({'action':key,'votes':sorted({o['vote'] for o in observations}),'examples':{name:sorted({o['vote'] for o in obs}) for name,obs in members.items()},
            'kind_votes':{k:sorted(v) for k,v in kinds.items()},'kind_majority':majority[0] if len(majority)==1 else None,
            'kind_needs_review':len(majority)!=1 or len(kinds)>1,'conditions':cs,'observations':observations})
    for (action,text),obs in risk_predicates.items():
        votes=sorted({o['vote'] for o in obs})
        if len(votes)>=2:bad_majority.append({'action':action,'condition':{'text':text,'votes':votes,'observations':obs,'note':'risk target aligned across field/operator variants'}})
    coverage=[];baseline=json.loads((ROOT/'baselines/current/snapshot.json').read_text())
    for row in baseline['rows']:
        if row['case_id']!='PRAC-KMT2B' or row['section'] not in SECTIONS or row['action']=='None found':continue
        key=identity(row['action']);direct=[a for a in actions if a['action']==key and any(o['item']['_quote_in_input'] for o in a['observations'])]
        example=[a for a in actions if any(identity(n)==key for n in a['examples']) and any(o['item']['_quote_in_input'] for o in a['observations'])]
        coverage.append({'accepted':row,'found_direct':bool(direct),'examples_grouping':bool(example),'union_matches':[a['action'] for a in direct+example],
            'explanation':'named union action (review identity alignment)' if direct else 'source examples member retained under parent, not a standalone action' if example else 'unexplained/unresolved absence; needs_review'})
    result={'scope':'source-only, shadow, no patient applicability changes','complete_votes':complete,'vote_stats':stats,'actions':actions,
        'accepted_coverage':coverage,'unresolved_accepted_absences':[r for r in coverage if not(r['found_direct'] or r['examples_grouping'])],
        'bad_majority_risk_conditions':bad_majority,'single_vote_conditions':single,
        'criteria':{'three_votes_complete_no_truncation':False,'accepted_actions_covered_or_explained':not any(not(r['found_direct'] or r['examples_grouping']) for r in coverage),
                    'no_majority_risk_as_existing_disease':not bad_majority,'AGXT_fluids':'not evaluated; no AGXT execution'},
        'engineering_frozen':False,'accepted_updated':False}
    if all(complete):
        result['criteria']['three_votes_complete_no_truncation']=all('output truncated' not in (d/'execution.log').read_text() for d in dirs)
    if not all(complete):
        result['criteria']['accepted_actions_covered_or_explained']=None
        result['criteria']['no_majority_risk_as_existing_disease']=None
        result['interpretation']='Incomplete votes: medical criteria unscored; observed duplicates are exploratory, not a completed three-vote majority'
    result['KMT2B_meets_criteria']=all(result['criteria'][k] for k in ('three_votes_complete_no_truncation','accepted_actions_covered_or_explained','no_majority_risk_as_existing_disease'))
    dump(OUT/'shadow/result.json',result)
    print(json.dumps({'complete':complete,'criteria':result['criteria'],'coverage':len(coverage),'unresolved_absences':len(result['unresolved_accepted_absences']),
        'bad_majority_risk':[(r['action'],r['condition']['votes']) for r in bad_majority],'condition_groups':sum(len(a['conditions']) for a in actions),'single_vote_conditions':len(single)},ensure_ascii=False,indent=2))

if __name__=='__main__':evaluate()

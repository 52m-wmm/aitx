"""Offline shadow union; exact text consensus never overrides patient classification."""
import copy
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path
from scripts import status_diff as SD
from aitx.evidence import action_identity as I
from scripts.step2_stability import dump

ROOT=Path(__file__).resolve().parents[1]
DIRS=[ROOT/'runs/kmt2b-two-vote-quote-20261118',ROOT/'runs/kmt2b-new-vote1-20261119',ROOT/'runs/kmt2b-third-vote-20261119']
def norm(text):return ' '.join(text.lower().split())
def shadow(dirs,out):
    grouped=defaultdict(list);ledgers=[]
    for vote,d in enumerate(dirs,1):
        raw=d/('first_vote_raw' if vote==1 else 'raw_extractions')
        for p in sorted(raw.glob('*.json')):
            r=json.loads(p.read_text());source=r['messages'][1]['content']
            for item in r['parsed']['items']:
                grouped[norm(item['name'])].append({'vote':vote,'source_selector':p.stem,'source_section':source.splitlines()[0],
                    'quote_in_fixed_input':norm(item['quote']) in norm(source),'item':item,'fixed_input':source})
        ledgers.append(json.loads((d/('first-vote-reassembled/replay.json' if vote==1 else 'assembled/replay.json')).read_text()))
    rows=[]
    for name,mentions in sorted(grouped.items()):
        presence=sorted({m['vote'] for m in mentions});kind=defaultdict(set);cs=defaultdict(list)
        for m in mentions:
            kind[m['item']['kind']].add(m['vote'])
            for req in m['item']['requirements']:
                cs[json.dumps({k:(norm(v) if isinstance(v,str) else v) for k,v in req.items()},sort_keys=True)].append({'vote':m['vote'],'requirement':req,'quote':m['item']['quote'],
                    'source_selector':m['source_selector'],'source_section':m['source_section'],
                    'literal_support':norm(req['text']) in norm(m['item']['quote'])})
            manifestation=m['item']['manifestation']
            if manifestation:
                cs['manifestation:'+norm(manifestation)].append({'vote':m['vote'],'requirement':{'text':manifestation,'field':'manifestation'},
                    'quote':m['item']['quote'],'source_selector':m['source_selector'],'source_section':m['source_section'],
                    'literal_support':norm(manifestation) in norm(m['item']['quote'])})
        conditions=[]
        for text,observations in cs.items():
            votes=sorted({x['vote'] for x in observations})
            conditions.append({'text':text,'votes':votes,'consensus_candidate':len(votes)>=2,
                'review_status':'exact_text_consensus_candidate' if len(votes)>=2 else 'needs_review',
                'effective':False,'observations':observations})
        majority=[k for k,v in kind.items() if len(v)>=2]
        rows.append({'name':name,'votes':presence,'single_vote':len(presence)==1,'review_status':'needs_review',
            'kind_votes':{k:sorted(v) for k,v in kind.items()},'kind_majority':majority[0] if len(majority)==1 else None,
            'kind_disagreement':len(kind)>1,'conditions':conditions,'mentions':mentions})
    dump(out/'shadow.json',{'mode':'shadow','clinical_effective':False,'grouping':'exact normalized name only; no generic/specific or acronym merges',
        'notes':'All medical conditions retained. Text majority is only a consensus candidate, not semantic or source validation. No patient status inferred.',
        'actions':rows})
    # Shadow union keeps distinct literal names and every requirement variant.
    union=copy.deepcopy(ledgers[0]);actions={};used=set()
    for led in ledgers:
        for action in led['actions']:
            if not action['action_key']:continue
            key=norm(action['label'])
            if key not in actions:
                a=copy.deepcopy(action)
                if a['action_key'] in used:a['action_key']+=':shadow:'+hashlib.sha256(key.encode()).hexdigest()[:12]
                used.add(a['action_key']);actions[key]=a
            else:
                a=actions[key]
                for r in action['requirements']:
                    if r not in a['requirements']:a['requirements'].append(copy.deepcopy(r))
                a['evidence_ids']=sorted(set(a['evidence_ids']+action['evidence_ids']))
    for a in actions.values():
        for i,r in enumerate(a['requirements']):r['id']='shadow-r'+str(i)
        a['status_by_branch']={b:{'status':'not_tested','reason':'shadow union; unresolved conditions retained; not clinically effective'} for b in a['status_by_branch']}
    union['actions']=list(actions.values());union['evidence']=list({e['id']:e for led in ledgers for e in led['evidence']}.values())
    ledgers.append(union)
    snapshots=[]
    for i,led in enumerate(ledgers,1):
        directory=out/('vote'+str(i)+'-ledgers')
        for cid in SD.case_ids():
            can=json.loads((ROOT/'out/step3'/(cid+'.json')).read_text())
            if cid=='PRAC-KMT2B':
                can['actions']=[a for a in can['actions'] if a['section'] not in ('existing_targeted_therapies','supportive_management','contraindications_precautions')]+led['actions']
                can['evidence']=list({e['id']:e for e in can['evidence']+led['evidence']}.values())
            dump(directory/(cid+'.json'),I.rewrite(can,I.case_map(cid,reverse=True)))
        snapshots.append(SD.build_snapshot(directory,SD.case_ids(),'shadow vote '+str(i)+' incomplete cached assembly',detailed=True))
    for i,snapshot in enumerate(snapshots):
        refs=[('accepted',SD.load_snapshot(ROOT/'baselines/current/snapshot.json'))]+[('vote'+str(j+1),snapshots[j]) for j in range(i)]
        for label,ref in refs:
            d=SD.compare(ref,snapshot);dest=out/'status_diff'/('vote'+str(i+1)+'-vs-'+label)
            dump(dest/'snapshot.json',snapshot);dump(dest/'diff.json',d);(dest/'diff.md').write_text(SD.markdown(d))
    counts={'union_exact_names':len(rows),'presence_counts':dict(Counter(len(r['votes']) for r in rows)),
        'kind_disagreements':[r['name'] for r in rows if r['kind_disagreement']],
        'conditions':sum(len(r['conditions']) for r in rows),'single_vote_conditions':sum(sum(len(c['votes'])==1 for c in r['conditions']) for r in rows),
        'complete_step3a':False,'clinical_effective':False,'status_diff_vote4_is_shadow_union':True}
    dump(out/'counts.json',counts);print(json.dumps(counts,ensure_ascii=False))

if __name__=='__main__':shadow(DIRS,DIRS[-1]/'shadow')

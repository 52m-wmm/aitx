"""Report all pre-registered runs without choosing a favourable result."""
from __future__ import annotations
import itertools
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.step2_stability import changes, compare, dump
from aitx import session

OUT = ROOT/'runs/step2-stability-20261118'


def semantic(r):
    return {'hpo': sorted((p['hpo_id'],p['status']) for p in r['phenotypes']),
            'samples': [s['terms'] for s in r['phenotype_extraction']['samples']],
            'facts':r['patient_facts']}


def raw_calls(folder):
    rows = []
    for p in (folder/'llm').glob('*.json'):
        e = json.loads(p.read_text())
        # Each cache filename identifies the exact request; all entries here were written live.
        phase = 'hpo_selection' if 'choices' in json.loads(e['content']) else 'symptom_extraction'
        rows.append({'request_id':p.stem, 'phase':phase, **e})
    return sorted(rows,key=lambda x:(x['sample'],x['phase']))


def feature_spans(calls):
    return [[e['sample'], sorted((p['quote'],p['status']) for p in json.loads(e['content'])['phenotypes'])]
            for e in calls if e['phase']=='symptom_extraction']


def pick_answers(calls):
    return [[e['sample'],json.loads(e['content'])] for e in calls if e['phase']=='hpo_selection']


def main():
    summary=json.loads((OUT/'summary.json').read_text())
    proposal=json.loads((OUT/'proposal.json').read_text())
    sessions=[p.parent for p in (ROOT/'runs/sessions').glob('*/meta.json') if json.loads(p.read_text())['argv']==['step2_stability','--execute']]
    if len(sessions)!=1:
        raise ValueError('expected exactly one independent experiment session')
    sess=sessions[0]
    logs=[json.loads(x) for x in (sess/'calls.jsonl').read_text().splitlines()]
    if any(x['cache_hit'] for x in logs):
        raise ValueError('response cache hit in independent execution')
    steps=[json.loads(x) for x in (sess/'steps.jsonl').read_text().splitlines()]
    round_counts={}
    per_round=[]
    for start,end in zip(steps[::2],steps[1::2]):
        if start['status']!='running' or end['status']!='done':
            raise ValueError('incomplete execution')
        cid=start['case']
        round_counts[cid]=round_counts.setdefault(cid,0)+1
        n=round_counts[cid]
        cs=[c for c in logs if start['at']<=c['at']<=end['at']]
        cost=sum(session.cost(c['usage'],c['at'],c['reserved_usd'] if 'reserved_usd' in c else None) for c in cs)
        rec={'case':cid,'round':n,'calls':len(cs),'usd':cost,'models':sorted({c['served_model'] for c in cs}),'cached_responses':0}
        per_round.append(rec)
        folder=OUT/'executions'/cid/str(n)
        dump(folder/'cost.json',rec)
        (folder/'calls.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cs))
    dump(OUT/'per_round_costs.json',per_round)
    if sum(r['calls'] for r in per_round)!=summary['cost']['calls']:
        raise ValueError('unattributed response/retry cost; investigate before acceptance')
    pairs={}
    metrics={}
    votes=[]
    lines=['# Step 2 independent stability acceptance — 2026-11-18','',
           'All 20 pre-registered executions are included. No diagnostic rule changes. No evaluation cases.', '',
           '| Case | HPO semantic differences / 10 pairs | Raw extraction differences / 10 pairs | Diagnosis differences / 10 pairs |',
           '| --- | --- | --- | --- |']
    for cid in proposal['cases']:
        folders=[OUT/'executions'/cid/str(i) for i in range(1,6)]
        runs=[json.loads((f/'result.json').read_text()) for f in folders]
        calls=[raw_calls(f) for f in folders]
        rows=[]
        # Remove request identity before comparing raw answers: round labels do not mean different answers.
        raw=[[{'sample':e['sample'], 'phase':e['phase'], 'content':e['content']} for e in cs] for cs in calls]
        for i,j in itertools.combinations(range(5),2):
            rows.append({'rounds':[i+1,j+1], **compare(runs[i],runs[j]),
                         'raw_response_diff':changes(raw[i],raw[j]),
                         'symptom_extraction_diff':changes([e for e in raw[i] if e['phase']=='symptom_extraction'],[e for e in raw[j] if e['phase']=='symptom_extraction']),
                         'hpo_selection_diff':changes([e for e in raw[i] if e['phase']=='hpo_selection'],[e for e in raw[j] if e['phase']=='hpo_selection']),
                         'hpo_semantic_changed':semantic(runs[i])['hpo']!=semantic(runs[j])['hpo'],
                         'extracted_feature_spans_changed':feature_spans(calls[i])!=feature_spans(calls[j]),
                         'selection_answers_changed':pick_answers(calls[i])!=pick_answers(calls[j]),
                         'three_vote_hpo_diff':changes(semantic(runs[i])['samples'],semantic(runs[j])['samples'])})
        pairs[cid]=rows
        metrics[cid]={key:sum(bool(r[key]) for r in rows) for key in ['hpo_semantic_changed','extracted_feature_spans_changed','selection_answers_changed','three_vote_hpo_diff','diagnosis_changed','candidate_set_changed']}
        identical_pick_requests={}
        for cs in calls:
            for e in cs:
                if e['phase']=='hpo_selection':
                    identical_pick_requests.setdefault(e['request_id'],[]).append(json.loads(e['content']))
        metrics[cid]['same_pick_request_groups']=sum(len(v)>1 for v in identical_pick_requests.values())
        metrics[cid]['same_pick_request_answer_disagreements']=sum(len(v)>1 and len({json.dumps(a,sort_keys=True) for a in v})>1 for v in identical_pick_requests.values())
        for i,r in enumerate(runs):
            votes.append({'case':cid,'round':i+1,'primary':r['primary'], 'samples':r['phenotype_extraction']['samples'], 'hpo':semantic(r)['hpo'], 'reasons':r['primary']['reasons']})
        lines.append(f"| {cid} | {sum(r['hpo_semantic_changed'] for r in rows)} | {sum(bool(r['raw_response_diff']) for r in rows)} | {sum(r['diagnosis_changed'] for r in rows)} |")
    dump(OUT/'complete_comparisons.json',pairs)
    dump(OUT/'difference_metrics.json',metrics)
    dump(OUT/'votes_and_reasons.json',votes)
    lines += ['', 'Full per-round results, extractions, raw responses and exact request parameters are in `executions/<case>/<round>/`; `complete_comparisons.json` includes every pair, and each execution has `diff_reference.json`.', '',
              'Cost accounting: '+json.dumps(summary['cost'])+'.',
              'Critical differences from fixed reference: '+json.dumps(summary['critical_changes'])+'.', '',
              'Model alias was recorded per request. Server-reported aliases alone do not independently verify model weights.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    main()

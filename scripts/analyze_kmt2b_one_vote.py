"""Offline comparison of one saved KMT2B vote with its historical first vote."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx.evidence import ledger as L,action_identity as I
from scripts import status_diff as SD,llm_cost
from scripts.step2_stability import dump,changes


def raw_groups(items):
    groups=defaultdict(list)
    for it in items:groups[L._norm(it['name'])].append(it)
    return dict(groups)


def conditions(a,extraction_only=False):
    return sorted([{k:r[k] for k in ('kind','requirement','result','alternative') if k in r} for r in a['requirements'] if not extraction_only or 'context_check' not in r],key=lambda r:json.dumps(r,sort_keys=True))


def state(a):
    return a['replay_deterministic_status_by_branch'] if 'replay_deterministic_status_by_branch' in a else a['status_by_branch']


def context_unmeasured(value):
    if isinstance(value,dict):return value.get('final')=='not_tested' or any(context_unmeasured(v) for v in value.values())
    return isinstance(value,list) and any(context_unmeasured(v) for v in value)


def analyze(run,first):
    out=run/'analysis';out.mkdir(exist_ok=True)
    rawdiff=[]
    for p in sorted((run/'raw_extractions').glob('*.json')):
        old=json.loads((first/'first_vote_raw'/p.name).read_text());new=json.loads(p.read_text())
        if old['messages']!=new['messages']:raise ValueError('source input changed')
        og=raw_groups(old['parsed']['items']);ng=raw_groups(new['parsed']['items'])
        common=og.keys()&ng.keys()
        rawdiff.append({'key':p.stem,'source':new['messages'][1]['content'].splitlines()[0],
                        'full_diff':changes(old['parsed'],new['parsed']),
                        'first_items':old['parsed']['items'],'new_items':new['parsed']['items'],
                        'first_raw_count':len(old['parsed']['items']),'new_raw_count':len(new['parsed']['items']),
                        'exact_name_removed':sorted(og.keys()-ng.keys()),'exact_name_added':sorted(ng.keys()-og.keys()),
                        'common_name_changes':[{'name':n,'diff':changes(og[n],ng[n]),'old':og[n],'new':ng[n]} for n in sorted(common) if og[n]!=ng[n]]})
    dump(out/'raw_diffs.json',rawdiff)
    old=json.loads((first/'first-vote-reassembled/replay.json').read_text());new=json.loads((run/'assembled/replay.json').read_text())
    before={a['action_key']:a for a in old['actions'] if a['action_key']};after={a['action_key']:a for a in new['actions'] if a['action_key']}
    matched={k:k for k in before.keys()&after.keys()}
    # Same literal normalized label identifies key/type routing differences, not a new therapy.
    for ok,a in before.items():
        if ok in matched:continue
        hits=[nk for nk,b in after.items() if nk not in matched.values() and L._norm(a['label'])==L._norm(b['label'])]
        if len(hits)==1:matched[ok]=hits[0]
    rows=[]
    for ok,nk in matched.items():
        a,b=before[ok],after[nk]
        rows.append({'first_label':a['label'],'new_label':b['label'],'old_key':ok,'new_key':nk,
                     'first_provisional_state':state(a),'new_provisional_state':state(b),
                     'first_conditions':conditions(a),'new_conditions':conditions(b),
                     'condition_changed':conditions(a)!=conditions(b),'extraction_condition_changed':conditions(a,True)!=conditions(b,True),'state_changed':state(a)!=state(b),
                     'new_context_unmeasured':context_unmeasured(b),
                     'first_evidence_ids':a['evidence_ids'],'new_evidence_ids':b['evidence_ids'],
                     'evidence_id_changed':set(a['evidence_ids'])!=set(b['evidence_ids']),
                     'first_extraction_kinds':a['extraction_kinds'] if 'extraction_kinds' in a else [],
                     'new_extraction_kinds':b['extraction_kinds'] if 'extraction_kinds' in b else [],
                     'safety_validation':'incomplete'})
    removed=[before[k] for k in before.keys()-matched.keys()];added=[after[k] for k in after.keys()-set(matched.values())]
    dbs=[r for r in rows if 'dbs' in r['first_label'].lower() or 'deep brain stimulation' in r['first_label'].lower()]
    def quotes(led):
        d=defaultdict(list)
        for e in led['evidence']:
            if e['kind']=='sourced':d[e['source']['type'],e['source']['id'],e['source']['section'] if 'section' in e['source'] else None,L._norm(e['quote'])].append(e)
        return d
    oe,ne=quotes(old),quotes(new);idonly=[]
    for key in oe.keys()&ne.keys():
        if {e['id'] for e in oe[key]}!={e['id'] for e in ne[key]}:
            idonly.append({'source_type':key[0],'source_id':key[1],'source_section':key[2],'same_normalized_quote':key[3],
                           'first':[{k:e[k] for k in ('id','claim','action','applies_to')} for e in oe[key]],
                           'new':[{k:e[k] for k in ('id','claim','action','applies_to')} for e in ne[key]]})
    oldids={e['id'] for e in old['evidence']};newids={e['id'] for e in new['evidence']}
    p0={r['key'] for r in old['replay']['pending']};p1={r['key'] for r in new['replay']['pending']}
    # Full status_diff snapshots: overlay only 3a, never publish an experimental action/status.
    snapshots=[]
    for name,led in [('first',old),('new',new)]:
        ld=out/(name+'-ledgers');ld.mkdir(exist_ok=True)
        for cid in SD.case_ids():
            canonical=json.loads((ROOT/'out/step3'/(cid+'.json')).read_text())
            if cid=='PRAC-KMT2B':
                canonical['actions']=[a for a in canonical['actions'] if a['section'] not in ('existing_targeted_therapies','supportive_management','contraindications_precautions')]+led['actions']
                canonical['evidence']=list({e['id']:e for e in canonical['evidence']+led['evidence']}.values())
            dump(ld/(cid+'.json'),canonical)
        snapshots.append(SD.build_snapshot(ld,SD.case_ids(),'KMT2B '+name+' extraction vote; partial cached assembly',detailed=True))
    for label,ref in [('first-vs-new',snapshots[0]),('accepted-current',SD.load_snapshot(ROOT/'baselines/current/snapshot.json'))]:
        diff=SD.compare(ref,snapshots[1]);target=ROOT/'out/status_diff/kmt2b-one-vote-20261119'/label
        dump(target/'snapshot.json',snapshots[1]);dump(target/'diff.json',diff);(target/'diff.md').write_text(SD.markdown(diff))
    sid=json.loads((run/'session.json').read_text())['id'];calls=[json.loads(l) for l in (ROOT/'runs/sessions'/sid/'calls.jsonl').read_text().splitlines()]
    assert len(calls)==4 and all(not r['cache_hit'] for r in calls)
    finance=llm_cost.summarize(0,run/'llm_calls.jsonl')
    result={'comparison':'historical first vote vs ONE new vote; third vote not run; no majority verdict',
            'first_action_records':len(before),'new_action_records':len(after),'matched_action_records':len(rows),
            'removed_records':removed,'added_records':added,'matched_changes':rows,'dbs':dbs,
            'condition_changed_matched_actions':sum(r['condition_changed'] for r in rows),
            'extraction_condition_changed_matched_actions':sum(r['extraction_condition_changed'] for r in rows),
            'state_changes_with_missing_context_check':sum(r['state_changed'] and r['new_context_unmeasured'] for r in rows),
            'provisional_state_changed_matched_actions':sum(r['state_changed'] for r in rows),
            'evidence_id_changed_matched_actions':sum(r['evidence_id_changed'] for r in rows),
            'all_assembly_evidence_ids_added':sorted(newids-oldids),'all_assembly_evidence_ids_removed':sorted(oldids-newids),
            'same_source_quote_changed_ids':idonly,'new_source_quote_units':len(ne.keys()-oe.keys()),'removed_source_quote_units':len(oe.keys()-ne.keys()),
            'first_pending':len(p0),'new_pending':len(p1),'new_pending_keys':len(p1-p0),'no_longer_pending_keys':len(p0-p1),
            'first_pending_by_version':dict(Counter(r['prompt_version'] for r in old['replay']['pending'])),
            'new_pending_by_version':dict(Counter(r['prompt_version'] for r in new['replay']['pending'])),
            'source_sections_raw_json_different':sum(bool(d['full_diff']) for d in rawdiff),
            'actual_model':sorted({r['served_model'] for r in calls}),'cost':finance,
            'second_new_vote_run':False,'full_step3a_complete':False,'accepted_baseline_updated':False}
    dump(out/'summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['matched_changes','removed_records','added_records','same_source_quote_changed_ids','all_assembly_evidence_ids_added','all_assembly_evidence_ids_removed','dbs']},indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--first',type=Path,required=True)
    a=ap.parse_args();analyze(a.run.resolve(),a.first.resolve())

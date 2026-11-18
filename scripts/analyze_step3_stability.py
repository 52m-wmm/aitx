"""Offline complete/partial Step 3 comparisons; never promotes a baseline."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import status_diff as SD
from scripts.step2_stability import dump


def vote_map(ledger):
    votes=SD.extract_votes(ledger['actions'])
    return {(tuple(v['call_ids']),v['question']):v for v in votes if v['call_ids']}


def measures(old,new,diff):
    ov,nv=vote_map(old),vote_map(new);common=ov.keys()&nv.keys()
    def ids(led):return {e['id'] for e in led['evidence']}
    def quotes(led):
        return {(e['source']['type'],e['source']['id'],e['quote']) for e in led['evidence'] if 'source' in e and 'quote' in e}
    oe,ne=ids(old),ids(new);oq,nq=quotes(old),quotes(new)
    return {'action_branch_changes':diff['counts'],
            'changed_field_row_counts':dict(Counter(f for r in diff['changes'] for f in r['changed_fields'])),
            'evidence_ids_added':sorted(ne-oe),'evidence_ids_removed':sorted(oe-ne),
            'source_quotes_added':len(nq-oq),'source_quotes_removed':len(oq-nq),
            'old_vote_questions':len(ov),'new_vote_questions':len(nv),
            'old_disagreed_questions':sum(v['tested'] and len(set(v['answers']))>1 for v in ov.values()),
            'new_disagreed_questions':sum(v['tested'] and len(set(v['answers']))>1 for v in nv.values()),
            'old_unmeasured_questions':sum(not v['tested'] for v in ov.values()),
            'new_unmeasured_questions':sum(not v['tested'] for v in nv.values()),
            'same_prompt_common_questions':len(common),
            'same_prompt_vote_answers_changed':sum(ov[k]['answers']!=nv[k]['answers'] for k in common),
            'same_prompt_final_changed':sum(ov[k]['final']!=nv[k]['final'] for k in common),
            'new_prompt_questions':len(nv.keys()-ov.keys()),'removed_prompt_questions':len(ov.keys()-nv.keys())}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--campaign',type=Path,required=True);args=ap.parse_args()
    root=args.campaign.resolve();m=json.loads((root/'manifest.json').read_text())
    report={'campaign':str(root),'completed_runs':{},'pairs':{}}
    snapshots={};ledgers={}
    for cid in m['cases']:
        for n in [1,2]:
            d=root/'executions'/cid/str(n);p=d/'result.json'
            if not p.exists():continue
            led=json.loads(p.read_text());ld=d/'ledgers';ld.mkdir(exist_ok=True)
            for case_id in SD.case_ids():
                src=p if case_id==cid else ROOT/'out/step3'/(case_id+'.json')
                shutil.copyfile(src,ld/(case_id+'.json'))
            snap=SD.build_snapshot(ld,SD.case_ids(),cid+' independent '+str(n),detailed=True)
            diff=SD.compare(SD.load_snapshot(ROOT/'baselines/current/snapshot.json'),snap)
            target=d/'comparison-current';dump(target/'snapshot.json',snap);dump(target/'diff.json',diff)
            (target/'diff.md').write_text(SD.markdown(diff))
            snapshots[cid,n]=snap;ledgers[cid,n]=led
            report['completed_runs'].setdefault(cid,[]).append(n)
    for cid in m['cases']:
        if (cid,1) not in snapshots or (cid,2) not in snapshots:
            report['pairs'][cid]={'status':'unavailable: two complete runs required'};continue
        diff=SD.compare(snapshots[cid,1],snapshots[cid,2]);dest=root/'pairwise'/cid
        dump(dest/'diff.json',diff);(dest/'diff.md').write_text(SD.markdown(diff))
        detail=measures(ledgers[cid,1],ledgers[cid,2],diff)
        dump(dest/'metrics.json',detail);report['pairs'][cid]={'status':'compared',**detail}
    dump(root/'stability_summary.json',report);print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()

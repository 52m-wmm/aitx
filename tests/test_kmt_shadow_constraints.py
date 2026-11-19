"""The shadow audit must preserve single-vote medical restrictions and kind disagreement."""
import json
from pathlib import Path
from scripts import kmt2b_shadow_votes as S


def test_shadow_retains_minority_condition_and_does_not_merge_general_aids(tmp_path,monkeypatch):
    dirs=[]
    for vote in range(1,4):
        d=tmp_path/str(vote);dirs.append(d)
        raw=d/('first_vote_raw' if vote==1 else 'raw_extractions');raw.mkdir(parents=True)
        req=[{'text':'only children','field':'age','op':'<','value':18,'unit':'year'}] if vote==1 else []
        item={'name':'walkers' if vote==1 else 'adaptive aids','kind':['device','therapy','other'][vote-1],
              'quote':'walkers and adaptive aids; only children','manifestation':'','requirements':req}
        (raw/'x.json').write_text(json.dumps({'messages':[{}, {'content':'Section: X\nwalkers and adaptive aids; only children'}],'parsed':{'items':[item]}}))
        assembly=d/('first-vote-reassembled' if vote==1 else 'assembled');assembly.mkdir()
        (assembly/'replay.json').write_text('{"actions":[],"evidence":[]}')
    monkeypatch.setattr(S.SD,'case_ids',lambda:[])
    monkeypatch.setattr(S.SD,'build_snapshot',lambda *a,**kw:{})
    monkeypatch.setattr(S.SD,'load_snapshot',lambda *a:{})
    monkeypatch.setattr(S.SD,'compare',lambda *a:{})
    monkeypatch.setattr(S.SD,'markdown',lambda *a:'')
    out=tmp_path/'result';S.shadow(dirs,out)
    r=json.loads((out/'shadow.json').read_text())
    assert len(r['actions'])==2
    walker=next(x for x in r['actions'] if x['name']=='walkers')
    assert walker['single_vote'] and walker['conditions'][0]['review_status']=='needs_review'
    assert walker['conditions'][0]['effective'] is False
    aids=next(x for x in r['actions'] if x['name']=='adaptive aids')
    assert aids['kind_disagreement'] and aids['kind_majority'] is None

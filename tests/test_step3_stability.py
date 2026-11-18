import json
import pytest
from aitx import http
from scripts import step3_stability as S


def test_frozen_http_replays_known_errors_and_never_fetches_missing(tmp_path,monkeypatch):
    monkeypatch.setattr(http,'CACHE_DIR',tmp_path/'http')
    monkeypatch.setattr(http,'get',http.get)
    path=http._key('https://example.test/known')
    snapshot=tmp_path/'snapshot.json'
    snapshot.write_text(json.dumps({'/old/cache/'+path.name:{'url':'https://example.test/known','error':'HTTP 404 for source'}}))
    S.fixed_http(tmp_path,snapshot)
    with pytest.raises(RuntimeError,match='HTTP 404'):
        http.get('https://example.test/known')
    with pytest.raises(S.FixedInputMissing,match='fixed database cache missing'):
        http.get('https://example.test/missing')


def test_detailed_votes_deduplicate_repeated_summaries_and_keep_unmeasured():
    from scripts.status_diff import extract_votes
    q={'call_ids':['a','b','c'],'answers':{'scope':{'final':'split','answers':['yes','no','yes']}}}
    value={'summary':q,'passages':[q], 'unmeasured':{'call_ids':[], 'answers':{'limit':{'final':'not_tested','answers':[]}}}}
    rows=extract_votes(value)
    assert len(rows)==2
    assert sum(r['tested'] and len(set(r['answers']))>1 for r in rows)==1
    assert sum(not r['tested'] for r in rows)==1
    incomplete=extract_votes({'call_ids':['d','e','f'],'answers':{'scope':{'final':'split','answers':['yes',None,'no']}}})
    assert not incomplete[0]['tested']


def test_detailed_condition_change_is_visible_but_legacy_baseline_is_unavailable():
    import copy
    from scripts.status_diff import compare
    row={'case_id':'C','section':'supportive_management','action_id':'x','branch':'B','action':'X',
         'status':'conditional','reason':'unknown','evidence_ids':['E'],'records':1,
         'classification':[{}],'conditions':[[{'result':'unknown'}]],'citations':[],'check_votes':[]}
    old={'label':'old','cases':{'C':{'available':True}},'rows':[row]}
    new=copy.deepcopy(old);new['label']='new';new['rows'][0]['conditions']=[[{'result':'pass'}]]
    diff=compare(old,new)
    assert diff['counts']=={'details_changed':1}
    assert diff['changes'][0]['changed_fields']==['conditions']
    assert diff['changes'][0]['old_details']['conditions']==[[{'result':'unknown'}]]
    legacy=copy.deepcopy(old)
    for field in ['classification','conditions','citations','check_votes']:
        del legacy['rows'][0][field]
    diff=compare(legacy,new)
    assert diff['changes']==[]
    assert diff['detailed_comparison'].startswith('unavailable')

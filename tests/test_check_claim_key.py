import copy
from aitx.disease import extract as X
from aitx.evidence import context_check as C

CFG={'model':'m','base_url':'https://provider'}
def key(action,passage='source',patient='age 7'):
    return X.cache_key(C.messages('h',passage,patient,C.questions_recommendation(action,'disease')),0,CFG,'context-check-v3')
def test_claim_case_whitespace_equivalent_and_original_preserved():
    a=C.messages('h','source','age 7',C.questions_recommendation('GPi-DBS','disease'));before=copy.deepcopy(a)
    assert key('GPi-DBS')==key('gpi-dbs')==key('  GPi-DBS  ')==key('\nGPi-DBS\t')
    X.cache_key(a,0,CFG,'context-check-v3');assert a==before

def test_no_wrong_collision_for_patient_source_or_claim_meaning():
    assert len({key('DBS'),key('no DBS'),key('DBS',patient='age 8'),key('DBS',passage='SOURCE'),key('D B S')})==5
    a=C.messages('h','source','age 7',C.questions_recommendation('DBS','disease'))
    b=C.messages('h','source','age 7',C.questions_recommendation('dbs','disease'))
    assert X.cache_key(a,0,CFG,'3a-v5')!=X.cache_key(b,0,CFG,'3a-v5')

def test_equivalent_key_really_hits_cache_without_network(tmp_path,monkeypatch):
    cfg=dict(CFG,expect_model_prefix='m')
    monkeypatch.setattr(X,'CACHE_DIR',tmp_path)
    a=C.messages('h','source','age 7',C.questions_recommendation('GPi-DBS','disease'))
    b=C.messages('h','source','age 7',C.questions_recommendation('gpi-dbs','disease'))
    entry={'call_params':X.CALL_PARAMS,'served_model':'m','content':'saved'}
    (tmp_path/(X.cache_key(a,0,cfg,'context-check-v3')+'.json')).write_text(__import__('json').dumps(entry))
    assert X.cache_lookup(b,0,cfg,'context-check-v3')['content']=='saved'

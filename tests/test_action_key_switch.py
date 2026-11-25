import copy
import pytest
from aitx.evidence import action_identity as I
from scripts.experiments.switch_action_keys import validate


def test_key_rewrite_preserves_evidence_and_inverts_all_machine_references():
    old={'patient_id':'C','actions':[{'action_key':'drug:name:a','label':'A','requirements':[{'requirement':'unchanged'}],
                                   'narrower_than':{'key':'procedure:b'}}],
         'evidence':[{'id':'E','action':{'key':'drug:name:a'},'quote':'original'}],
         'possible_duplicates':[{'action_key':'drug:name:a'}]}
    mapping={'drug:name:a':'source:X','procedure:b':'source:Y'}
    new=I.rewrite(old,mapping)
    assert new['evidence']==old['evidence']
    assert new['actions'][0]['narrower_than']['key']=='source:Y'
    assert I.rewrite(new,{v:k for k,v in mapping.items()})==old
    validate(old,new,mapping)
    new['actions'][0]['requirements'][0]['requirement']='changed'
    with pytest.raises(ValueError,match='non-key'):validate(old,new,mapping)


def test_different_actions_must_not_merge():
    old={'actions':[{'action_key':'a','label':'A'},{'action_key':'b','label':'B'}],'evidence':[]}
    with pytest.raises(ValueError,match='injective'):validate(old,copy.deepcopy(old),{'a':'new','b':'new'})


def test_anchored_drug_class_still_enters_safety_and_export_does_not_mutate_runtime(monkeypatch):
    monkeypatch.setattr(I,'registry',lambda:{'active':True,'cases':{'C':{'drug:name:class':'source:C'}}})
    raw={'patient_id':'C','actions':[{'action_key':'drug:name:class'}],'evidence':[]}
    out=I.export(raw)
    assert I.is_drug(out['actions'][0],out)
    assert raw['actions'][0]['action_key']=='drug:name:class'
    assert out['actions'][0]['action_key']=='source:C'


def test_rollback_restores_exact_bytes_and_can_handle_partial_apply(tmp_path,monkeypatch):
    import json
    from scripts.experiments import switch_action_keys as S
    monkeypatch.setattr(S,'ROOT',tmp_path)
    monkeypatch.setattr(I,'REGISTRY',tmp_path/'data/registry.json')
    before=b'{"original": true}\n';after=b'{"new":true}\n'
    official=tmp_path/'out/step3/C.json';official.parent.mkdir(parents=True);official.write_bytes(after)
    backup=tmp_path/'backup';(backup/'before').mkdir(parents=True);(backup/'before/C.json').write_bytes(before)
    (backup/'manifest.json').write_text(json.dumps({'cases':{'C':{'before_sha256':S.sha(backup/'before/C.json'),'after_sha256':S.sha(official)}}}))
    (backup/'registry.json').write_text(json.dumps({'active':True,'cases':{}}))
    S.rollback(backup)
    assert official.read_bytes()==before
    assert json.loads(I.REGISTRY.read_text())['active'] is False
    official.write_text('unexpected later change')
    with pytest.raises(ValueError,match='later ledger changes'):S.rollback(backup)
    I.registry.cache_clear()


def test_inactive_forward_registry_still_decodes_archived_new_keys(monkeypatch):
    monkeypatch.setattr(I,'registry',lambda:{'active':False,'cases':{'C':{'drug:name:class':'source:C'}}})
    assert I.case_map('C')=={}
    assert I.is_drug({'action_key':'source:C'},{'patient_id':'C'})

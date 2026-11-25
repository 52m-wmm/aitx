import pytest
from scripts.experiments.migrate_current_keys_offline import convert,read_mapping


def test_offline_mapping_changes_identity_only_and_keeps_unmatched_rows():
    rows=[{'case_id':'C','section':'S','action_id':k,'branch':'B','status':'conditional','conditions':[{'result':'unknown'}],'evidence_ids':['E']} for k in ('old','unmapped')]
    before={'cases':{'C':{'available':True}},'rows':rows}
    after,changed=convert(before,{'C':{'old':'new'}})
    assert after['rows'][0]==dict(rows[0],action_id='new')
    assert after['rows'][1]==rows[1] and before['rows'][0]['action_id']=='old'
    assert len(changed)==1


def test_mapping_collision_fails():
    before={'rows':[{'case_id':'C','section':'S','action_id':k,'branch':'B'} for k in ('old','new')]}
    with pytest.raises(ValueError,match='collided'):convert(before,{'C':{'old':'new'}})


def test_literal_tab_mapping_is_read_without_mutating_source(tmp_path):
    p=tmp_path/'mapping.tsv';s='Case\\tOld key\\tProposed key\nC\\told\\tnew\n';p.write_text(s)
    assert read_mapping(p)=={'C':{'old':'new'}} and p.read_text()==s

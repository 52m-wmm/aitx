import pytest
from aitx.evidence.actions import resolve_kind


@pytest.mark.parametrize('name,expected',[
    ('high oral fluid intake','diet'),('intravenous fluids','procedure'),
    ('oral fluid intake','diet'),('IV fluids','procedure'),('wrist braces','device')])
def test_unsupported_kind_maps_by_intervention(name,expected):
    assert resolve_kind(name,'therapy')==(expected,False)


def test_unmapped_action_is_retained_as_other_and_missing_kind_errors():
    assert resolve_kind('unrecognized intervention','novel_type')==('other',True)
    assert resolve_kind('physical therapy','therapy')==('therapy',False)
    with pytest.raises(ValueError):resolve_kind('named intervention',None)


def test_existing_evidence_identity_depends_on_action_key_and_claim():
    from aitx.evidence import ledger as L
    source={'type':'nbk','id':'NBK1'}
    a=L.sourced('First wording','supportive_management',['B'],source,'Use fluids.','Use fluids.',1,action={'key':'diet:first'})
    b=L.sourced('Second wording','supportive_management',['B'],source,'Use fluids.','Use fluids.',1,action={'key':'diet:second'})
    assert a['id']!=b['id']  # must not feed this ID back into a supposedly wording-independent action key

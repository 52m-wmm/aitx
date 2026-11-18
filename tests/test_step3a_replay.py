from scripts.replay_step3a import mark_pending


def test_pending_does_not_corrupt_searched_none_identity():
    a={'action_key':'drug:rxcui:1','status_by_branch':{'B':{'status':'applicable','reason':'source'}},'context_check':{'final':'not_tested'}}
    empty={'action_key':None,'status_by_branch':{'B':{'status':'searched_none','reason':'no results'}}}
    value={'actions':[a,empty]}
    mark_pending(value,[])
    assert a['status_by_branch']['B']['status']=='not_tested'
    assert a['replay_deterministic_status_by_branch']['B']['status']=='applicable'
    assert empty['status_by_branch']['B']['status']=='searched_none'
    assert 'replay_deterministic_status_by_branch' not in empty


def test_missing_merge_cannot_produce_complete_applicability():
    a={'action_key':'procedure:1','status_by_branch':{'B':{'status':'conditional','reason':'missing age'}}}
    mark_pending({'actions':[a]},[{'kind':'synonym merge'}])
    assert a['status_by_branch']['B']['status']=='not_tested'
    assert a['replay_deterministic_status_by_branch']['B']['reason']=='missing age'

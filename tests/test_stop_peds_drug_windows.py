"""Focused offline checks; these synthetic trees are not model experiment results."""
import copy
import pytest
from scripts.experiments import stop_peds_drug_windows as E


@pytest.fixture
def specimen(monkeypatch):
    monkeypatch.setattr(E.B,'verify_expression',E.V.verify_expression)
    q='not taking tezacaftor-ivacaftor or lumacaftor-ivacaftor for at least 3 months'
    def atom(name):return {'op':'atom','quote':name,'fact':'medication','name':name,'comparison':'unspecified','value':None,'unit':''}
    w={'quote':'for at least 3 months','anchor':'enrollment','direction':'lookback','comparison':'>=','value':3,'unit':'months'}
    raw={'op':'not','quote':q,'window':w,'children':[{'op':'any','quote':'tezacaftor-ivacaftor or lumacaftor-ivacaftor',
          'children':[atom('tezacaftor-ivacaftor'),atom('lumacaftor-ivacaftor')]}]}
    normalized={'op':'all','quote':q,'children':[{'op':'not','quote':q,'window':copy.deepcopy(w),'children':[atom(d)]} for d in sorted(E.DRUGS)]}
    return {'cohort':'non-HEMT','clause_quote':q,'attachment':{'operator':'all','connector_quote':'and also'},'source_expression':raw,'independent_expression':normalized}


def test_two_independent_quoted_not_windows_stay_unknown(specimen):
    r=E.verify(specimen,(E.OUT/'eligibility-original.txt').read_text())
    assert r['structure_verified'] and set(r['per_drug'])==E.DRUGS
    assert all(v['status']=='unknown' for v in r['per_drug'].values())


@pytest.mark.parametrize('damage',['quote','window','or','missing_op','atom_window'])
def test_core_quote_window_or_errors_are_rejected(specimen,damage):
    if damage=='quote':specimen['independent_expression']['children'][0]['children'][0]['quote']='taking lumacaftor-ivacaftor'
    elif damage=='window':specimen['independent_expression']['children'][0]['window']['value']=2
    elif damage=='or':specimen['source_expression']['children'][0]['op']='all'
    elif damage=='missing_op':specimen['independent_expression']['children'][0]['children'][0].pop('op')
    else:
        n=specimen['independent_expression']['children'][0]
        n['children'][0]['window']=n.pop('window')
    with pytest.raises((ValueError,KeyError)):E.verify(specimen,(E.OUT/'eligibility-original.txt').read_text())

"""NOT v2 offline mechanics, synthetic trees only; no model/network calls."""
import pytest
from scripts.experiments import stop_peds_full_context as B, stop_peds_nonhemt_not as V


@pytest.fixture(autouse=True)
def scoped(monkeypatch):
    monkeypatch.setattr(B,'verify_expression',V.verify_expression)


def not_use():
    quote='not taking tezacaftor-ivacaftor or lumacaftor-ivacaftor for at least 3 months'
    return {'op':'not','quote':quote,'window':{'quote':'for at least 3 months','anchor':'enrollment',
            'direction':'lookback','comparison':'>=','value':3,'unit':'months'},
            'children':[{'op':'atom','quote':'tezacaftor-ivacaftor','fact':'medication','name':'tezacaftor-ivacaftor',
                         'comparison':'unspecified','value':None,'unit':''}]}


def test_not_unknown_and_quoted_complete_lookback():
    node=not_use();V.verify_expression(node,node['quote'])
    assert B.evaluate(node,{}, {},[], 'inclusion')['status']=='unknown'
    node['window']['value']=2
    with pytest.raises(ValueError,match='window'):V.verify_expression(node,node['quote'])


def test_boolean_zero_rejected_even_if_zero_appears_in_source():
    node={'op':'atom','quote':'eligible 0','fact':'eligibility','name':'eligibility','comparison':'==','value':0,'unit':''}
    with pytest.raises(ValueError,match='boolean'):V.verify_expression(node,node['quote'])


def test_future_window_remains_unknown():
    q='no plans to start HEMT in the next year'
    node={'op':'not','quote':q,'window':{'quote':'in the next year','anchor':'enrollment','direction':'future',
          'comparison':'within','value':1,'unit':'year'},'children':[{'op':'atom','quote':'plans to start HEMT',
          'fact':'plan','name':'plan to start HEMT','comparison':'unspecified','value':None,'unit':''}]}
    V.verify_expression(node,q)
    assert B.evaluate(node,{}, {},[], 'inclusion')['status']=='unknown'


def test_full_source_and_explicit_negation_instruction():
    assert 'Numeric 0/1 MUST NEVER' in V.SYSTEM
    assert 'positive genotype-based eligibility' in V.SYSTEM
    source=(V.OUT/'eligibility-original.txt').read_text()
    assert source==(V.PREVIOUS/'eligibility-original.txt').read_text()

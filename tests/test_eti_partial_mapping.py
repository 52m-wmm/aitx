"""ETI cached partial mapping: retain reviewed conditions without relaxing validation."""
import copy

import pytest

from aitx.evidence import ledger as LG
from aitx.step3.b import criteria as C
from tests.test_criteria import _PF, _conf_branch

TEXT = ('Cystic Fibrosis patients with at least one F508del mutation treated with the combination '
        'elexacaftor/tezacaftor/ivacaftor for a time sufficient to reach steady-state (8 days)')
VARIANT = 'at least one F508del mutation'
TREATMENT = 'treated with the combination elexacaftor/tezacaftor/ivacaftor for a time sufficient to reach steady-state (8 days)'
RAW = [
    {'id':'inc1','quote':'Cystic Fibrosis patients','fact':'diagnosis','op':'','value':['Cystic Fibrosis'],'unit':'','group':''},
    {'id':'inc1','quote':VARIANT,'fact':'variant','op':'>=','value':1,'unit':'','group':''},
    {'id':'inc1','quote':TREATMENT,'fact':'current_medication','op':'>=','value':8,'unit':'days','group':''},
]


def mapped(monkeypatch):
    monkeypatch.setattr(C,'_llm',lambda *a,**kw: ({'criteria':copy.deepcopy(RAW)},'code'))
    study={'nct':'NCT07809867','criteria':'Inclusion Criteria:\n* '+TEXT}
    return study,C.map_study(study)


def lines(study, result):
    branch=dict(_conf_branch(),gene='CFTR',diagnosis={'label':'cystic fibrosis'},parent_names=[])
    pf=dict(_PF,variants=[{'gene':'CFTR','quote':'CFTR p.Phe508del homozygous'}])
    return C.lines_for(study,result,pf,{'facts':[]},branch,['cystic fibrosis'])


def test_reviewed_eti_partial_clause_stays_unknown_and_diagnosis_stays_pass(monkeypatch):
    study,result=mapped(monkeypatch)
    assert [r['rejected'] for r in result['rejected']]==['threshold 1 not in the quote',"comparison '>=' not as written"]
    rows=lines(study,result)
    assert rows[0]['text']=='Cystic Fibrosis patients' and rows[0]['patient_status']=='satisfies'
    unresolved=[r for r in rows if r['patient_status']=='unknown']
    assert len(unresolved)==1 and unresolved[0]['text']==TEXT
    assert {r['quote'] for r in unresolved[0]['details']['reviewed_rejections']}=={VARIANT,TREATMENT}
    assert LG.status_from([LG.requirement_result(r['kind'],r['patient_status']) for r in rows])=='conditional'


def test_unreviewed_or_duplicate_rejections_do_not_become_new_conditions(monkeypatch):
    study,result=mapped(monkeypatch)
    result['rejected']=[{'id':'inc1','fact':'other','quote':'Invented medical condition','rejected':'quote not verbatim in the criterion'}]
    assert len(lines(study,result))==1
    study,result=mapped(monkeypatch)
    result['rejected'].append(copy.deepcopy(result['rejected'][0]))
    unknown=[r for r in lines(study,result) if r['patient_status']=='unknown']
    assert len(unknown)==1 and len(unknown[0]['details']['reviewed_rejections'])==2


def test_already_accepted_fragment_is_not_reintroduced_from_duplicate_rejection(monkeypatch):
    study,result=mapped(monkeypatch)
    result['mappings'].append({'id':'inc1','fact':'variant','quote':VARIANT})
    rows=C.reviewed_rejected_lines(study,result)
    assert len(rows)==1
    assert [r['quote'] for r in rows[0]['details']['reviewed_rejections']]==[TREATMENT]


@pytest.mark.parametrize('change',['nct','source'])
def test_review_is_bound_to_this_trial_and_exact_original_clause(monkeypatch,change):
    study,result=mapped(monkeypatch)
    if change=='nct':study['nct']='NCT00000001'
    else:
        result['items'][0]['text']=TEXT+' Additional condition.'
        study['criteria']='Inclusion Criteria:\n* '+result['items'][0]['text']
    assert len(lines(study,result))==1

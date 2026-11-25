"""STOP PEDS only: frozen cached scopes, half-open ages, and unresolved treatment paths."""
import json
from pathlib import Path

import pytest

from aitx.evidence import ledger as LG, trials as T
from aitx.step3.b import criteria as C
from tests.test_criteria import PF, BR, _mapped

REVIEW=json.loads((Path(__file__).resolve().parents[1]/'config/reviewed_trial_cohorts.json').read_text())[0]


def rows(months=180,extra=None):
    # Minimal source fixture: six cached clauses/IDs and the rejected lower-bound pattern.
    clauses={c['item']:c for c in REVIEW['clauses']}
    items=[{'id':i,'kind':'inclusion','text':c['text'],'level':2,'parent':None} for i,c in clauses.items()]
    mappings=[]
    for i,c in clauses.items():
        if c['comparison']=='age':
            lower,upper=(6,19) if i=='inc2' else (3,6)
            mappings.extend([{'id':i,'fact':'age','quote':c['text'],'op':op,'value':v,'unit':'years'}
                             for op,v in [('>=',lower),('<',upper)]])
        else:
            mappings.append({'id':i,'fact':'current_medication' if i in ('inc9','inc10') else 'other',
                             'quote':c['text'],'name':'HEMT','op':'','value':'','group':''})
    accepted=[];rejected=[];by_id={i['id']:i for i in items}
    for m in mappings:
        why=C.check_mapping(m,by_id)
        (rejected if why else accepted).append(dict(m,rejected=why) if why else m)
    study={'nct':'NCT06654752','criteria':'Inclusion Criteria:\n'+'\n'.join('* '+i['text'] for i in items)}
    mapped=dict(_mapped(items,accepted),rejected=rejected)
    pf=dict(PF,age_months=months,age_quote=None if months is None else f'Age {months} months')
    return C.lines_for(study,mapped,pf,extra or {'facts':[]},BR,[])


@pytest.mark.parametrize('months,cohorts',[(180,{'main','non-HEMT'}),(60,{'preschool'}),(72,{'main','non-HEMT'}),
                                         (36,{'preschool'}),(228,{'main','non-HEMT','preschool'}),
                                         (None,{'main','non-HEMT','preschool'})])
def test_complete_age_bounds_and_reviewed_cohort_selection(months,cohorts):
    result=rows(months)
    assert {r['alternative'].split(':')[-1] for r in result}==cohorts
    ages=[r for r in result if r.get('fact')=='age']
    assert all(r['patient_status']==('unknown' if months in (None,228) else 'satisfies') for r in ages)
    if months==180:
        assert all('preschool' not in r['alternative'] for r in result)
        assert any(r['details']['reviewed_cohort']['inactive_cohorts'] for r in result)


def requirements(result):
    return [LG.requirement(f'r{i}',r['kind'],r['text'],'e',r['patient_fact'],r['patient_status'],['b'],r['note'],
                           alternative=r.get('alternative')) for i,r in enumerate(result)]


def test_presence_only_hemt_does_not_prove_duration_or_non_hemt_eligibility():
    extra={'facts':[{'kind':'current_medication','name':'HEMT','status':'present','value':None,'unit':'','quote':'Taking HEMT'}]}
    result=rows(extra=extra)
    meds=[r for r in result if r['item'] in ('inc9','inc10')]
    assert len(meds)==2 and all(r['patient_status']=='unknown' for r in meds)
    assert LG.status_of(requirements(result),'b')[0]=='conditional'


def test_resolved_main_cohort_is_not_blocked_by_other_cohort_unknowns_and_common_fail_wins():
    reqs=requirements(rows())
    # Aggregation probe only: assume all main-cohort checks were separately verified.
    for r in reqs:
        if r['alternative']=='cohort:main':r.update(result='pass',patient_status='satisfies')
    assert LG.status_of(reqs,'b')[0]=='applicable'
    reqs.append(LG.requirement('shared','exclusion','Shared hard exclusion','e',{'quote':'known fact'},'satisfies',['b']))
    assert LG.status_of(reqs,'b')[0]=='not_applicable'


def test_review_requires_trial_identity_and_exact_reviewed_source():
    lines=[{'item':'inc2'}]
    for study in ({}, {'nct':'NCT00000001'}):
        assert C.reviewed_cohort_lines(study,{},lines,PF) is lines
    items=[{'id':c['item'],'text':c['text']} for c in REVIEW['clauses']]
    items[0]['text']='For main cohort and non-HEMT cohort: age 8 to <19 years'
    with pytest.raises(ValueError,match='reviewed cohort source changed'):
        C.reviewed_cohort_lines({'nct':'NCT06654752'},{'items':items},lines,PF)

"""Offline mechanics checks. These synthetic expressions are NOT model experiment results."""
import copy
import pytest
from scripts.experiments import stop_peds_full_context as S


def age():
    return {'op':'atom','quote':'For main cohort and non-HEMT cohort: age 6 to \\<19 years',
            'fact':'age_interval','name':'age','comparison':'[)','value':[6,19],'unit':'years'}


def test_full_original_including_headers_and_nesting_is_sent_without_patient():
    msgs=S.messages()
    original=(S.OUT/'eligibility-original.txt').read_text()
    assert original in msgs[1]['content']
    assert original.startswith('Inclusion Criteria:') and '\nExclusion Criteria:' in original
    assert '   2. For preschool cohort:' in original
    assert '15-year-old' not in str(msgs) and '[inc' not in str(msgs)


def test_quoted_complete_age_bounds_and_python_boundary_comparison():
    expr=age();S.verify_expression(expr,expr['quote'])
    for months,want in [(60,'does_not_satisfy'),(72,'satisfies'),(180,'satisfies'),(228,'does_not_satisfy'),(None,'unknown')]:
        assert S.evaluate(expr,{'age_months':months,'age_quote':'synthetic age'}, {},[], 'inclusion')['status']==want
    expr['value']=[8,19]
    with pytest.raises(ValueError):S.verify_expression(expr,expr['quote'])


def test_invalid_reference_and_logical_structure_are_rejected():
    expr=age()
    with pytest.raises(ValueError):S.verify_expression(expr,'unrelated source')
    with pytest.raises(ValueError):S.verify_expression({'op':'not','quote':'source','children':[]},'source')
    invented=copy.deepcopy(expr);invented['fact']='duration';invented['value']=99
    with pytest.raises(ValueError):S.verify_expression(invented,invented['quote'])


def test_unproven_duration_and_negation_stay_unknown():
    atom={'op':'atom','quote':'Taking HEMT for at least 3 months at enrollment','fact':'duration',
          'name':'HEMT duration','comparison':'>=','value':3,'unit':'months'}
    S.verify_expression(atom,atom['quote'])
    assert S.evaluate(atom,{}, {},[], 'inclusion')['status']=='unknown'
    parent={'op':'not','quote':atom['quote'],'children':[atom]}
    assert S.evaluate(parent,{}, {},[], 'inclusion')['status']=='unknown'
    one=age()
    composite={'op':'all','quote':one['quote']+'; '+atom['quote'],'children':[one,atom]}
    assert S.evaluate(composite,{'age_months':180,'age_quote':'synthetic'}, {},[], 'inclusion')['status']=='unknown'


def test_rejected_quote_or_unquoted_zero_stays_unknown_without_patient_comparison():
    expr=age()
    condition={'id':'x','kind':'inclusion','scope':['main'],'quote':'invented quote','expression':expr}
    rejected=S.evaluate_condition(condition,expr['quote'],{}, {},[])
    assert rejected['verification_status']=='rejected' and rejected['python_result']=='unknown'
    condition['quote']=expr['quote'];condition['expression']=dict(expr,fact='eligibility',comparison='==',value=0)
    rejected=S.evaluate_condition(condition,expr['quote'],{}, {},[])
    assert rejected['verification_status']=='rejected' and rejected['python_result']=='unknown'

"""Production entry and safety invariants; no model or network calls."""
import json
from aitx.evidence import trials as T, ledger as LG
from aitx.step3.b import screening as S
from aitx.step3.b import records as R


def study(criteria='Inclusion Criteria:\n* Age 18 to 70 years.\nExclusion Criteria:\n* Pregnancy.'):
    return T.flat({'protocolSection':{
        'identificationModule':{'nctId':'NCT12345678','briefTitle':'Example'},
        'statusModule':{'overallStatus':'RECRUITING'},
        'designModule':{'studyType':'OBSERVATIONAL'},
        'conditionsModule':{'conditions':['Example disease']},
        'eligibilityModule':{'minimumAge':'18 Years','maximumAge':'70 Years','sex':'ALL',
                             'healthyVolunteers':False,'eligibilityCriteria':criteria}}})


def test_formal_entry_uses_new_screener(monkeypatch):
    calls=[]
    monkeypatch.setattr(S,'add_trials',lambda *a,**kw:calls.append((a,kw)))
    R.add_trials('ledger','case','step1','step2',use_cache=True)
    assert calls==[(('ledger','case','step1','step2'),{'use_cache':True})]


def test_complete_input_and_conservative_registry_age():
    case={'id':'P','patient':{'clinical_context':'Age unknown.','genotype':[]}}
    s=study('Only enrolling under 6 years.\nInclusion Criteria:\n* Part A: 18 to 70 years.\n* Part B: 3 to 17 years.')
    p=S.sample(case,s);m=S.messages(p)
    assert json.loads(p['patient_text'])==case
    assert p['trial_text'].endswith(s['criteria'])
    assert m[0]['content']==S.PROMPT
    assert S.prefilter(s,None,None)['result']=='unknown'
    assert S.prefilter(s,7*12,None)['result']=='unknown'
    assert S.prefilter(study(),7*12,None)['result']=='fail'


def test_quotes_do_not_prove_logic_and_or_keeps_candidate(tmp_path,monkeypatch):
    monkeypatch.setattr(S,'REVIEW_DIR',tmp_path)
    s=study();p={'patient_text':'A male infant.','trial_text':s['criteria']}
    c={'axis':'clinical_history','patient_fact_quote':'male infant','trial_rule_quote':'Pregnancy.',
       'other_cohort_applicable':False,'reason':'unsupported'}
    pf={'age_months':3,'sex':'male'}
    assert not S.verify(p,c,s,pf,[])['accepted']
    c.update(axis='age_sex',trial_rule_quote='Age 18 to 70 years.',other_cohort_applicable=True)
    assert not S.verify(p,c,s,pf,[])['accepted']
    assert LG.status_from(['unknown'])=='conditional'

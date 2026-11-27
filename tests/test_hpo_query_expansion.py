"""Single extraction retains synonyms as queries, never as additional votes."""
import json
import pytest
from aitx.disease import extract as X
from tests.test_disease import ont


def blank():
    return {"phenotypes": [], "clinical_facts": [], "background": [], "facts": {
        "age": {"value": None, "unit": None, "quote": None, "scope": "unknown", "status": "unknown"},
        "onset": {"quote": None, "scope": "unknown", "status": "unknown"},
        "sex": {"value": "unknown", "quote": None, "scope": "unknown", "status": "unknown"},
        "variant_origin": {"value": "unknown", "quote": None, "scope": "unknown", "status": "unknown"},
        "family_history": {"statement": None, "quote": None, "scope": "unknown", "status": "unknown"}}}


def feature(quote, description="Seizure", status="present", scope="patient"):
    return dict(quote=quote, description=description, alternatives=[], status=status, scope=scope,
                presenting=False, onset=None, severity=None, course=None)


def run(monkeypatch, ont, context, parsed):
    calls = []
    def chat(messages, k, use_cache):
        calls.append((messages, k))
        assert messages[0]["content"] == X.SYSTEM  # all test terms have deterministic mappings
        return {"content": json.dumps(parsed), "served_model": "fixture"}
    monkeypatch.setattr(X, "_cached_chat", chat)
    result = X.extract(context, ont)
    assert len(calls) == 1 and calls[0][1] == 0
    return result


def test_four_states_and_general_scope_never_become_patient_facts(monkeypatch, ont):
    ctx = "Seizure. No hearing loss. Possible developmental delay. Hyperammonemia status unknown. General: focal seizures."
    p = blank()
    p["phenotypes"] = [feature("Seizure"), feature("No hearing loss", "Hearing impairment", "absent"),
        feature("Possible developmental delay", "Global developmental delay", "possible"),
        feature("Hyperammonemia status unknown", "Hyperammonemia", "unknown"),
        feature("focal seizures", "Focal-onset seizure", scope="general")]
    out = run(monkeypatch, ont, ctx, p)
    assert {(v['hpo_id'],v['status']) for v in out['phenotypes']} == {('HP:0001250','present'),('HP:0000365','excluded')}
    native = out['patient_facts']['clinical']['phenotypes']
    assert [v['status'] for v in native] == ['present','absent','possible','unknown','present']
    assert native[-1]['scope'] == 'general' and not native[-1]['valid']


def test_conflicting_assertions_retained_unknown(monkeypatch, ont):
    p=blank();p['phenotypes']=[feature('Seizure'),feature('No seizures',status='absent')]
    out=run(monkeypatch,ont,'Seizure. No seizures.',p)
    assert out['phenotypes']==[] and len(out['phenotype_conflicts'])==2
    assert all(v['status']=='unknown' for v in out['patient_facts']['clinical']['phenotypes'])


def test_alternative_wording_not_promoted(monkeypatch,ont):
    p=blank();p['phenotypes']=[feature('normal or mildly delayed','Global developmental delay')]
    out=run(monkeypatch,ont,'Development is normal or mildly delayed.',p)
    assert out['phenotypes']==[]
    assert out['patient_facts']['clinical']['phenotypes'][0]['status']=='possible'


def test_general_demographics_and_onset_not_promoted(monkeypatch,ont):
    p=blank();p['facts']['age']=dict(value=3,unit='year',quote='3 years',scope='general',status='present')
    p['facts']['onset']=dict(quote='childhood',scope='general',status='present')
    out=run(monkeypatch,ont,'Onset at 3 years in childhood.',p)
    assert out['patient_facts']['age']['months'] is None
    assert out['patient_facts']['onset']['months_min'] is None
    assert out['patient_facts']['clinical']['facts']==p['facts']


def test_clinical_categories_numbers_units_and_unknown_trial(monkeypatch,ont):
    ctx='Diagnosed OTC deficiency. Born at 35 weeks. Taking arginine. Ammonia 120. Trial status unknown. Hospitalized.'
    p=blank()
    for kind,name,quote,value,status in [
        ('diagnosis','OTC deficiency','Diagnosed OTC deficiency',None,'present'),
        ('demographic','Born','Born at 35 weeks',35,'present'),
        ('treatment','arginine','Taking arginine',None,'present'),
        ('lab','Ammonia','Ammonia 120',120,'present'),
        ('trial_status','Trial','Trial status unknown',None,'unknown'),
        ('history','Hospitalized','Hospitalized',None,'present')]:
        p['clinical_facts'].append(dict(kind=kind,name=name,quote=quote,value=value,status=status,
            scope='patient',unit=None,timing=None))
    out=run(monkeypatch,ont,ctx,p)
    assert out['patient_facts']['clinical']['items']==p['clinical_facts']
    assert out['patient_facts']['clinical']['items'][3]['unit'] is None


@pytest.mark.parametrize('field',['facts','phenotypes','clinical_facts','background'])
def test_missing_required_collection_stops(field):
    p=blank();del p[field]
    with pytest.raises(KeyError):X.structure_clinical(p,'Seizure')


@pytest.mark.parametrize('mutation', ['status','quote','scope','onset'])
def test_malformed_source_stops(mutation):
    p=blank();f=feature('Seizure');p['phenotypes']=[f]
    f[mutation]={'quote':'invented'} if mutation=='onset' else 'invented'
    with pytest.raises(ValueError):X.structure_clinical(p,'Seizure')


def test_no_three_sample_mode(ont):
    with pytest.raises(ValueError,match='one sample'):X.extract('Seizure',ont,n=3)


def test_retrieval_still_uses_single_items_alternatives(ont):
    p=feature('fits','Spells');p['alternatives']=['Seizure']
    tid,_,how=X.candidates_for(p,ont)
    assert tid=='HP:0001250' and how=='exact HPO name match of the alternative name'


@pytest.mark.parametrize('value,valid',[('male',True),('female',False),(14,True),(15,False)])
def test_clinical_values_are_verbatim_not_coerced(value,valid):
    p=blank();p['clinical_facts']=[dict(kind='demographic',name='male',quote='14 year old male',
        value=value,unit=None,timing=None,scope='patient',status='present')]
    if valid:
        assert X.structure_clinical(p,'14 year old male')[2]['items'][0]['value']==value
    else:
        with pytest.raises(ValueError):X.structure_clinical(p,'14 year old male')


@pytest.mark.parametrize('reply',[{}, {'choices':[]}, {'choices':[{'feature':1}]},
    {'choices':[{'feature':1,'candidate':True}]}])
def test_missing_or_invalid_selection_stops(monkeypatch,ont,reply):
    monkeypatch.setattr(X,'_cached_chat',lambda *a,**kw:{'content':json.dumps(reply),'served_model':'fixture'})
    it=X.check_item({'quote':'focal seizures in infancy','description':'focal seizures in infancy','status':'present'},
                    'focal seizures in infancy')
    with pytest.raises((KeyError,ValueError)):
        X.map_items([it],'focal seizures in infancy',ont,0,True)


def test_symptom_onset_echo_is_not_disease_onset(monkeypatch,ont):
    p=blank();f=feature('Seizure');f['onset']={'quote':'during childhood'};p['phenotypes']=[f]
    p['facts']['onset']=dict(quote='during childhood',scope='patient',status='present')
    out=run(monkeypatch,ont,'Seizure began during childhood.',p)
    assert out['patient_facts']['onset']['months_min'] is None
    assert out['patient_facts']['clinical']['facts']['onset']['status']=='unknown'
    assert out['phenotypes'][0]['onset']['months_min']==12


def test_explicit_presentation_can_supply_disease_onset(monkeypatch,ont):
    p=blank();f=feature('Seizure');f.update(presenting=True,onset={'quote':'during childhood'})
    p['phenotypes']=[f];p['facts']['onset']=dict(quote='during childhood',scope='patient',status='present')
    out=run(monkeypatch,ont,'Presented with Seizure during childhood.',p)
    assert out['patient_facts']['onset']['months_min']==12


def test_verbatim_de_novo_alias_is_normalized(monkeypatch,ont):
    p=blank();p['facts']['variant_origin']=dict(value='de novo',quote='de novo variant',scope='patient',status='present')
    out=run(monkeypatch,ont,'A de novo variant.',p)
    assert out['patient_facts']['variant_origin']['value']=='de_novo'
    assert out['patient_facts']['clinical']['facts']['variant_origin']['source_value']=='de novo'

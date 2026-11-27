import copy
import pytest
from aitx.disease.output import build_layers
from aitx.disease import pipeline as P, resolve as R
from tests.test_step2_molecular import joined, record


@pytest.fixture
def bundle(joined, record):
    v, step1 = joined
    molecular = P.molecular_variants([v], step1, 'C')
    mol = R.molecular_fit(molecular, [record], 'male')
    c = dict(key='D1', label='Disease 1', gene='G', grouping=[], merge={}, excluded=False,
             exclusion_reasons=[], compete=True, specific=True, clinvar=[], clinvar_info=[],
             validity=dict(has_ranked_evidence=True, only_disputed_or_refuted=False),
             inheritance=dict(result='consistent', per_moi=[dict(result='consistent', moi='AD')]),
             phenotype=dict(score=2, matches=[dict(ic=2)], penalties=[], onset=dict(adjustment=0)),
             molecular_assessment=mol, g2p_evidence=[record], orphanet_mechanism_hint=[])
    primary=dict(id='D1', status='ambiguous', basis='phenotype', reasons=['kept uncertain'], alternatives=[])
    clinical=dict(items=[dict(kind='diagnosis',scope='general',status='present',quote='General text'),
                        dict(kind='diagnosis',scope='patient',status='possible',quote='Possible diagnosis')],
                  phenotypes=[dict(scope='general',status='present'),dict(scope='patient',status='unknown')],
                  source_text='General text. Possible diagnosis.', background=['General text'], facts={})
    out=dict(patient_facts=dict(clinical=clinical), molecular_evidence=molecular, primary=primary,
             candidates=[c,dict(copy.deepcopy(c),key='D2',label='Disease 2')],
             not_supported=[dict(copy.deepcopy(c),key='D3',excluded=True,exclusion_reasons=['obsolete'])],
             explicit_diagnosis=None, phenotypes=[], phenotype_extraction={}, g2p_records=[record],
             sources_manifest=[dict(name='g2p',sha256='frozen')], evidence=[])
    case=dict(id='C', patient=dict(genotype=[v], clinical_context=clinical['source_text']))
    return case, step1, out


def test_lossless_and_no_new_decision(bundle):
    case, step1, out = bundle
    before=copy.deepcopy((case,step1,out))
    layers=build_layers(case,step1,out)
    assert (case,step1,out)==before
    assert layers['L1']['step1_result']==step1
    assert layers['L1']['clinical']==out['patient_facts']['clinical']
    assert layers['L2']['diagnostic_resolution']==out['primary']
    assert [c['record'] for c in layers['L3']['candidates']]==out['candidates']
    assert [c['record'] for c in layers['L3']['not_supported']]==out['not_supported']
    layers['L3']['candidates'][0]['record']['label']='changed'
    assert out==before[2]


def test_preserves_candidates_outside_alternatives(bundle):
    layers=build_layers(*bundle)
    assert [(c['id'],c['selection_role']) for c in layers['L3']['candidates']]==[('D1','primary'),('D2','retained')]
    assert layers['L3']['not_supported'][0]['id']=='D3'


def test_general_or_possible_diagnosis_not_confirmed(bundle):
    layers=build_layers(*bundle)
    assert layers['L2']['reported_diagnosis_status']=='unknown'
    assert [d['status'] for d in layers['L2']['reported_diagnoses']]==['possible']
    assert layers['L2']['disease_category']['status']=='unknown'
    assert layers['L4']['patient_mechanism']['status']=='unknown'


def test_documented_diagnosis_is_reported_not_new_adjudication(bundle):
    bundle[2]['patient_facts']['clinical']['items'][1]['status']='present'
    layers=build_layers(*bundle)
    assert layers['L2']['reported_diagnosis_status']=='documented'
    assert layers['L2']['diagnostic_resolution']['status']=='ambiguous'


def test_legacy_scope_remains_unknown(bundle):
    del bundle[2]['patient_facts']['clinical']
    bundle[2]['phenotypes']=[dict(status='present',quote='original old answer')]
    layers=build_layers(*bundle)
    assert layers['L1']['clinical'] is None
    assert layers['L1']['clinical_coverage']=='legacy_scope_and_four_state_not_available'
    assert layers['L1']['saved_phenotypes']==bundle[2]['phenotypes']
    assert layers['L2']['reported_diagnosis_status']=='unknown'


def test_zero_match_and_zero_penalty_not_negative_evidence(bundle):
    c=bundle[2]['candidates'][0]
    c['phenotype'].update(score=None,matches=[dict(ic=0)],penalties=[dict(penalty=0)])
    c['inheritance']=dict(result='unknown',per_moi=[])
    layers=build_layers(*bundle)
    row=layers['L3']['candidates'][0]
    assert row['opposing_evidence']==[]
    assert {'inheritance_unknown','phenotype_annotations_unavailable'} <= {r['kind'] for r in row['pending_information']}


def test_references_resolve_within_standalone_layers(bundle):
    layers=build_layers(*bundle)
    def walk(node):
        if isinstance(node,dict):
            if 'ref' in node:
                target=layers
                for part in node['ref'][2:].split('/'):
                    target=target[int(part)] if isinstance(target,list) else target[part]
            for value in node.values():walk(value)
        elif isinstance(node,list):
            for value in node:walk(value)
    walk(layers)


def test_missing_required_output_field_stops(bundle):
    del bundle[2]['candidates'][0]['inheritance']
    with pytest.raises(KeyError):build_layers(*bundle)


@pytest.mark.parametrize('nmd,hypothesis,mechanism,expected',[
    ('likely_triggers','loss_of_function','loss of function','predicted_compatible'),
    ('likely_triggers','loss_of_function','dominant negative','prediction_tension'),
    ('likely_escapes','loss_of_function_or_altered_function','loss of function','unknown'),
    ('uncertain','loss_of_function_or_altered_function','loss of function','unknown'),
])
def test_nonsense_nmd_reaches_decision_and_layers(bundle,record,nmd,hypothesis,mechanism,expected):
    case,step1,out=bundle
    prof=step1['variants'][0]
    prof.update(variant_class='nonsense',nmd=dict(prediction=nmd),
                mechanism_hypothesis=dict(hypothesis=hypothesis,confidence='moderate'))
    record['mechanism']=mechanism
    molecular=P.molecular_variants(case['patient']['genotype'],step1,'C')
    mol=R.molecular_fit(molecular,[record],'male')
    out['molecular_evidence']=molecular
    for c in out['candidates']:
        c['molecular_assessment']=mol
    out['candidates'][1]['inheritance']['result']='conditional'
    original=R.select(out['candidates'],['HP:1'],[],[])
    assert original['status']=='resolved' and original['basis']=='inheritance'
    selection=R.molecular_selection(original,out['candidates'])
    assert selection['status']=='ambiguous' and set(selection['tied'])=={'D1','D2'}
    assert any('variant mechanism='+expected in r for r in selection['reasons'])
    out['primary'].update(status=selection['status'],reasons=selection['reasons'])
    layers=build_layers(case,step1,out)
    assert layers['L4']['candidate_mechanisms'][0]['assessment']['paths'][0]['variant_assessments'][0]['status']==expected
    assert layers['L4']['patient_mechanism']['status']=='unknown'
    assert len(layers['L3']['candidates'])==2
    assert layers['L2']['diagnostic_resolution']['status']=='ambiguous'

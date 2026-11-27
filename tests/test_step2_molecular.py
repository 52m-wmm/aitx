import copy
import pytest
from aitx.disease.pipeline import molecular_variants
from aitx.disease.resolve import molecular_fit, molecular_selection


@pytest.fixture
def joined():
    v = dict(gene='G', transcript='NM_1.1', variant_cdna='c.1A>G',
             variant_protein='p.X1Y', zygosity='heterozygous')
    p = dict(v, ok=True, variant_class='missense',
             nmd={'prediction': 'not_applicable', 'reasons': ['no premature stop codon']},
             mechanism_hypothesis={'hypothesis': 'unknown', 'confidence': 'low'}, checks=[], evidence=[])
    return v, {'id': 'C', 'variants': [p]}


@pytest.fixture
def record():
    return dict(id='G2P1', allelic_requirement='monoallelic_autosomal', mechanism='loss of function',
                mechanism_support='inferred', variant_consequence='absent gene product', variant_types='',
                cross_cutting_modifier='', cite={'dataset': 'g2p', 'line': 2}, url='source')


def assess(joined, record):
    v, s = joined
    return molecular_fit(molecular_variants([v], s, 'C'), [record], 'male')


@pytest.mark.parametrize('field,value', [('transcript', 'NM_1.2'), ('variant_cdna', 'c.2A>G'), ('gene', 'H')])
def test_profile_join_does_not_cross_variant_identity(joined, field, value):
    v, s = joined
    s['variants'][0][field] = value
    with pytest.raises(ValueError, match='exact Step 1'):
        molecular_variants([v], s, 'C')


def test_profile_must_be_unique_and_case_matched(joined):
    v, s = joined
    with pytest.raises(ValueError, match='case identity'):
        molecular_variants([v], s, 'other')
    s['variants'].append(copy.deepcopy(s['variants'][0]))
    with pytest.raises(ValueError, match='found 2'):
        molecular_variants([v], s, 'C')


def test_missing_required_field_fails(joined):
    v, s = joined
    del s['variants'][0]['nmd']
    with pytest.raises(KeyError):
        molecular_variants([v], s, 'C')


def test_missense_nmd_na_does_not_prove_or_refute_lof(joined, record):
    out = assess(joined, record)
    assert out['status'] == 'conditional'
    assert out['paths'][0]['allelic_fit'] == 'compatible'
    assert out['paths'][0]['variant_assessments'][0]['status'] == 'unknown'
    assert 'unknown' in out['pathogenicity_prediction']


def test_truncation_and_nmd_are_used_as_prediction_only(joined, record):
    v, s = joined
    p = s['variants'][0]
    p.update(variant_class='nonsense', nmd={'prediction': 'likely_triggers'},
             mechanism_hypothesis={'hypothesis': 'loss_of_function', 'confidence': 'moderate'})
    out = assess(joined, record)
    assert out['paths'][0]['variant_assessments'][0]['status'] == 'predicted_compatible'
    assert out['status'] == 'conditional'
    p['nmd']['prediction'] = 'likely_escapes'
    assert assess(joined, record)['paths'][0]['variant_assessments'][0]['status'] == 'unknown'
    p['nmd']['prediction'] = 'likely_triggers'
    record['mechanism'] = 'dominant negative'
    assert assess(joined, record)['paths'][0]['variant_assessments'][0]['status'] == 'prediction_tension'


def test_biallelic_missing_second_allele_is_conditional_not_exclusion(joined, record):
    record['allelic_requirement'] = 'biallelic_autosomal'
    out = assess(joined, record)
    assert out['paths'][0]['allelic_fit'] == 'conditional'
    assert out['status'] == 'conditional'


def test_multiple_heterozygous_variants_do_not_imply_trans(joined, record):
    v, s = joined
    v2 = dict(v, variant_cdna='c.2A>G')
    s['variants'].append(dict(s['variants'][0], variant_cdna='c.2A>G'))
    record['allelic_requirement'] = 'biallelic_autosomal'
    out = molecular_fit(molecular_variants([v, v2], s, 'C'), [record], 'male')
    assert out['paths'][0]['allelic_fit'] == 'conditional'


def test_restricted_dn_and_biallelic_routes_remain_separate(joined, record):
    record.update(mechanism='dominant negative', cross_cutting_modifier='restricted mutation set')
    ar = dict(record, id='G2P2', allelic_requirement='biallelic_autosomal', mechanism='loss of function')
    v, s = joined
    paths = molecular_fit(molecular_variants([v], s, 'C'), [record, ar], 'male')['paths']
    assert [p['allelic_fit'] for p in paths] == ['compatible', 'conditional']
    assert paths[0]['restricted_mutation_set'] == 'membership_unknown'
    assert all(p['variant_assessments'][0]['status'] == 'unknown' for p in paths)


@pytest.mark.parametrize('kind', ['zygosity', 'variant_protein', 'checks'])
def test_conflicting_or_failed_profile_not_used_as_fact(joined, record, kind):
    v, s = joined
    if kind == 'checks':
        s['variants'][0]['ok'] = False
    else:
        s['variants'][0][kind] = 'different'
    m = molecular_variants([v], s, 'C')
    assert m[0]['effective_zygosity'] == 'unknown'
    out = molecular_fit(m, [record], 'male')
    assert out['status'] == 'conflicting' and out['paths'][0]['allelic_fit'] == 'unknown'


def test_missing_step1_and_missing_g2p_stay_unknown(joined, record):
    v, s = joined
    assert molecular_fit(molecular_variants([v], None, 'C'), [record], 'male')['paths'][0]['allelic_fit'] == 'unknown'
    assert molecular_fit(molecular_variants([v], s, 'C'), [], 'male')['status'] == 'unknown'


def test_molecular_conditions_actually_constrain_selection(joined, record):
    mol = assess(joined, record)
    candidates = [dict(key='D1', label='Disease 1', gene='G', excluded=False, compete=True, molecular_assessment=mol),
                  dict(key='D2', label='Disease 2', gene='G', excluded=False, compete=True, molecular_assessment=mol)]
    selection = dict(status='resolved', id='D1', basis='inheritance', reasons=['old basis'], tied=[])
    after = molecular_selection(selection, candidates)
    assert after['status'] == 'ambiguous' and after['tied'] == ['D1', 'D2']
    assert selection['status'] == 'resolved'  # no mutation
    assert not any(c['excluded'] for c in candidates)
    selection['basis'] = 'explicit'
    assert molecular_selection(selection, candidates)['status'] == 'resolved'
    mol['status'] = 'conflicting'
    assert molecular_selection(selection, candidates)['status'] == 'ambiguous'


def test_standalone_entry_passes_saved_step1(tmp_path, monkeypatch, joined):
    import json
    import sys
    from scripts import step2_disease as cli
    v, step1 = joined
    case = {'id': 'C', 'patient': {'genotype': [v]}}
    path = tmp_path / 'case.json'
    path.write_text(json.dumps(case))
    calls = []
    class Resources:
        files = {}
    monkeypatch.setattr(cli.resolve, 'load_resources', lambda *a, **k: Resources())
    monkeypatch.setattr(cli.runmeta, 'load_output', lambda step, c: (step1, 'sha'))
    def run(c, res, **kwargs):
        calls.append(kwargs['step1'])
        return {'ok': True}
    monkeypatch.setattr(cli.pipeline, 'run_case', run)
    monkeypatch.setattr(cli, 'summary', lambda r: [])
    monkeypatch.setattr(sys, 'argv', ['step2_disease', str(path), '--out', str(tmp_path / 'out')])
    assert cli.main() == 0 and calls == [step1]

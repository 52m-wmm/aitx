import copy
import json
from pathlib import Path

import pytest

from aitx.evidence import genecontext as GC, trials as T, ledger as LG
from aitx.step3.b import criteria as C
from aitx.step3.b import records as TR
from tests.test_criteria import PF

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def local_genes(monkeypatch):
    monkeypatch.setattr(GC, '_KNOWN', {'OTC', 'CPS1', 'PAH', 'AGXT', 'HAO1'})


def study(target='CPS1'):
    return {'title': 'Single gene base editing', 'study_type': 'interventional', 'interventions': [],
            'criteria': f'Inclusion Criteria:\n1. Diagnosis of severe urea cycle disorder.\n2. Molecular testing showing a disease-causing mutation in {target}.\nExclusion Criteria:\n* Active infection.',
            'population_groups': [{'label': 'Experimental'}]}


@pytest.mark.parametrize('target', ['CPS1', 'PAH', 'AGXT'])
def test_single_target_conflict_is_not_nct_specific(target):
    s = study(target)
    result = C.single_target_conflict(s, ['OTC'])
    assert result['target_gene'] == target
    assert result['trial_rule_quote'] in s['criteria']
    assert result['other_cohort_applicable'] is False
    assert C.single_target_conflict(s, [target]) is None
    assert C.single_target_conflict(s, ['OTC', target]) is None
    assert C.single_target_conflict(s, []) is None


def test_alternatives_unknown_scope_and_nontherapy_do_not_exclude():
    original = study()
    variants = []
    s = copy.deepcopy(original);s['criteria'] = s['criteria'].replace('mutation in CPS1', 'mutation in CPS1 or OTC');variants.append(s)
    s = copy.deepcopy(original);s['criteria'] = s['criteria'].replace('mutation in CPS1', 'mutation in CPS1 or a diagnosis of any urea cycle disorder');variants.append(s)
    s = copy.deepcopy(original);s['criteria'] = s['criteria'].replace('2. Molecular', 'Cohort A:\n2. Molecular');variants.append(s)
    s = copy.deepcopy(original);s['population_groups'] = [{'label': 'CPS1', 'description': 'CPS1 mutation'}, {'label': 'All UCD patients', 'description': 'Any UCD regardless of genotype'}];variants.append(s)
    s = copy.deepcopy(original);s['population_groups'] = [{'label': 'CPS1 or OTC patients'}];variants.append(s)
    s = copy.deepcopy(original);s['study_type'] = 'observational';variants.append(s)
    s = copy.deepcopy(original);del s['population_groups'];variants.append(s)
    s = copy.deepcopy(original);s['criteria'] = s['criteria'].replace('Molecular testing showing', 'No requirement for molecular testing showing');variants.append(s)
    s = copy.deepcopy(original);s['criteria'] = s['criteria'].replace('2. Molecular', 'PartA:\n2. Molecular');variants.append(s)
    for s in variants:
        assert C.single_target_conflict(s, ['OTC']) is None, s


def test_title_only_restriction_has_title_provenance():
    s = study();s['title'] = 'CPS1-deficiency gene therapy';s['criteria'] = 'Inclusion Criteria:\n* Severe metabolic disease.'
    result = C.single_target_conflict(s, ['OTC'])
    assert result['quote_source'] == 'title'
    assert result['trial_rule_quote'] == s['title']


def test_cached_cps1_unmapped_requirement_still_excludes_in_real_recorder():
    raw = json.loads((ROOT/'out/step3b-otc-e2e-20261124/studies.json').read_text())['NCT07667387']
    s = dict(T.flat(raw), _accessed_at=1, relevance={}, specific=True)
    branch = {'id': 'b1', 'gene': 'OTC', 'diagnosis': {'label': 'OTC deficiency'}, 'confirmed': True}
    pf = dict(PF, age_months=3, sex='male', variants=[{'gene':'OTC', 'protein':'p.Arg129His', 'quote':'OTC p.Arg129His (hemizygous)', 'zygosity':'hemizygous', 'class':'missense'}])
    mapped = {'items': T.split_criteria(s['criteria']), 'mappings': [], 'rejected': [], 'produced_by':'code'}
    led = LG.Ledger('TEST', [branch])
    TR._record(led, s, {'b1':'analysed'}, mapped, pf, {'facts':[]}, {'b1':branch}, {'candidates':[]})
    action = led.actions[0]
    assert action['status_by_branch']['b1']['status'] == 'not_applicable'
    assert 'CPS1' in action['status_by_branch']['b1']['reason'] and 'OTC' in action['status_by_branch']['b1']['reason']
    req = next(r for r in action['requirements'] if r['item'] == 'code:molecular-target')
    assert req['result'] == 'fail' and req['requirement'] in s['criteria']
    assert req['details']['molecular_target_conflict']['target_gene'] == 'CPS1'
    assert not [check for check in led.checks() if check['status']=='fail']


def test_real_model_quotes_confirm_target_mismatch_but_not_cross_gene_zygosity():
    from scripts.experiments.rescreen_molecular_targets import review_molecular_answer
    folder = ROOT/'out/step3b-otc-e2e-20261124/trials/NCT07667387'
    answer = json.loads((folder/'parsed.json').read_text())
    sample = json.loads((folder/'sample.json').read_text())
    raw = json.loads((folder/'api-study.json').read_text())
    original = copy.deepcopy(answer)
    conflict = C.single_target_conflict(T.flat(raw), ['OTC'])
    reviewed = review_molecular_answer(answer, sample, conflict)
    assert [r['quote_audit']['both_valid'] for r in reviewed] == [True, True]
    assert [r['semantic_confirmed'] for r in reviewed] == [True, False]
    assert answer == original


def test_mechanistic_target_or_relative_gene_is_not_patient_disease_requirement():
    s = study();s['title'] = 'HAO1-targeted siRNA in hyperoxaluria';s['criteria'] = 'Inclusion Criteria:\n* Primary hyperoxaluria.'
    assert C.single_target_conflict(s, ['AGXT']) is None
    s = study();s['criteria'] = s['criteria'].replace('Molecular testing showing a disease-causing mutation in CPS1.', 'Family member of someone with a disease-causing mutation in CPS1.')
    assert C.single_target_conflict(s, ['OTC']) is None


def test_explicit_otc_diagnosis_can_confirm_target_without_clinvar_record():
    branch={'id':'b','gene':'OTC'}
    one={'variants':[{'gene':'OTC'}]}
    two={'primary':{'id':'b','status':'resolved'},'clinvar':[]}
    case={'id':'C','patient':{'clinical_context':'The patient was diagnosed with OTC deficiency following genetic testing.'}}
    assert not TR.confirmed(branch,one,two)
    assert TR.confirmed_target_gene(branch,case,one,two)
    unknown=copy.deepcopy(case);unknown['patient']['clinical_context']='Possible OTC deficiency, awaiting diagnosis.'
    assert not TR.confirmed_target_gene(branch,unknown,one,two)
    assert not TR.confirmed_target_gene(branch,case,one,{'primary':{'id':'b','status':'unresolved'}})


def test_search_synonym_limit_does_not_hide_halt_and_target_gate_records_cps1(monkeypatch):
    data=json.loads((ROOT/'out/step3b-otc-e2e-20261124/studies.json').read_text())
    hits=[T.flat(data[n]) for n in ['NCT05092685','NCT07667387']]
    queries=[]
    def search(params,**kwargs):
        queries.append(params)
        return {'studies':hits,'query':params,'url':'local','page_urls':['local'],'queried_at':1,
                'total_count':2,'n_retrieved':2,'complete':True}
    monkeypatch.setattr(T,'search',search)
    names=['ornithine carbamoyltransferase deficiency','OCT deficiency','OTC deficiency','ornithine transcarbamylase deficiency']
    plan=T.plan_branch(names,'OTC',3,'male',diagnosed_genes=['OTC'])
    assert {s['nct'] for s in plan['analysed']}=={'NCT05092685'}
    assert {s['nct'] for s in plan['ineligible']}=={'NCT07667387'}
    assert len(queries)==4  # Three condition queries plus the gene query; matching keeps all synonyms.

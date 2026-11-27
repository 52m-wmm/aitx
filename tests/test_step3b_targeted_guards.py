"""Real saved positive cases and false-exclusion counterexamples; no external I/O."""
import copy
import json
from pathlib import Path
import socket

import pytest

from aitx.evidence import trials as T
from aitx.step3.b import guards as G, screening as S

ROWS = json.loads((Path(__file__).parent/'fixtures/step3b_targeted_guards.json').read_text())
FIXTURES = {r['protocol']['identificationModule']['nctId']: r for r in ROWS}


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('Network forbidden')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(S, 'REVIEW_DIR', tmp_path)


def audits(nct, mutate=None):
    row = copy.deepcopy(FIXTURES[nct])
    study = T.flat({'protocolSection': row['protocol']})
    if mutate:
        mutate(row, study)
    return [S.verify(S.sample(row['case'], study), c, study, row['facts'],
                     [v['gene'] for v in row['facts']['variants']]) for c in row['conflicts']]


@pytest.mark.parametrize('nct', ['NCT04430426', 'NCT06160713', 'NCT03670472',
    'NCT06620354', 'NCT06621082', 'NCT07407803', 'NCT05199376', 'NCT07888517', 'NCT07401121'])
def test_supported_model_conflicts_are_accepted(nct):
    accepted = [a for a in audits(nct) if a['accepted']]
    assert accepted
    assert all(a['patient_quote_valid'] and a['trial_quote_valid'] for a in accepted)


@pytest.mark.parametrize('nct', ['NCT04750928', 'NCT06541847', 'NCT06188741',
    'NCT06763315', 'NCT06502171', 'NCT07088991', 'NCT05512208', 'NCT05402384',
    'NCT07505394', 'NCT07516496', 'NCT06818916'])
def test_qualifiers_unknown_facts_and_other_cohorts_not_accepted(nct):
    assert all(not a['accepted'] for a in audits(nct))


@pytest.mark.parametrize('change', ['bad_patient_quote', 'bad_trial_quote', 'other_cohort', 'exempt_gene'])
def test_genetic_exclusion_requires_valid_anchors_and_no_exemption(change):
    def mutate(row, study):
        c = row['conflicts'][0]
        if change == 'bad_patient_quote':
            c['patient_fact_quote'] = 'invented patient'
        elif change == 'bad_trial_quote':
            c['trial_rule_quote'] = 'invented criterion'
        elif change == 'other_cohort':
            c['other_cohort_applicable'] = True
        else:
            row['facts']['variants'].append(dict(row['facts']['variants'][0], gene='TARDBP'))
    assert not any(a['accepted'] for a in audits('NCT07401121', mutate))


def test_same_zygosity_does_not_conflict():
    def mutate(row, study):
        row['facts']['variants'][0]['zygosity'] = 'heterozygous'
    assert not any(a['accepted'] for a in audits('NCT04430426', mutate))


@pytest.mark.parametrize('nct,category', [('NCT07573059', 'different_disease_gene'),
    ('NCT07538947', 'unrelated_oncology'), ('NCT07788456', 'opposite_phenotype')])
def test_relevance_rejected_before_model_queue(nct, category):
    row = FIXTURES[nct]; study = T.flat({'protocolSection': row['protocol']})
    plan = {'analysed': [study], 'ineligible': [], 'excluded': []}
    S.filter_relevance(plan, row['case'], row['facts'], [])
    assert plan['analysed'] == []
    assert plan['excluded'][0]['category'] == category
    assert plan['excluded'][0]['conditions'] == study['conditions']
    assert plan['excluded'][0]['inclusion']


@pytest.mark.parametrize('nct', ['NCT07573059', 'NCT07538947', 'NCT07788456'])
def test_explicit_alternative_population_prevents_whole_study_rejection(nct):
    row = FIXTURES[nct]; study = T.flat({'protocolSection': row['protocol']})
    study['population_groups'].append({'label': 'Healthy volunteers', 'type': 'OTHER'})
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None


def test_known_cancer_patient_keeps_oncology_candidate():
    row = FIXTURES['NCT07538947']; study = T.flat({'protocolSection': row['protocol']})
    patient = dict(row['case']['patient'], clinical_context='Malignant Peripheral Nerve Sheath Tumor')
    assert G.relevance(study, patient, row['facts'], []) is None


def test_reported_target_gene_keeps_disease_candidate():
    row = copy.deepcopy(FIXTURES['NCT07573059']); study = T.flat({'protocolSection': row['protocol']})
    row['facts']['variants'].append(dict(row['facts']['variants'][0], gene='ARG1'))
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None


def test_possible_or_absent_platelet_direction_is_not_a_positive_fact():
    row = copy.deepcopy(FIXTURES['NCT07788456']); study = T.flat({'protocolSection': row['protocol']})
    row['facts']['present'] = []
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None


@pytest.mark.parametrize('nct', ['NCT05931718', 'NCT06873672'])
def test_low_platelets_in_only_one_alternative_disease_path_does_not_exclude(nct):
    row = FIXTURES[nct]; study = T.flat({'protocolSection': row['protocol']})
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None


@pytest.mark.parametrize('nct', ['NCT07586813', 'NCT06673498', 'NCT07911800'])
def test_required_low_platelet_population_not_rescued_by_other_condition_labels(nct):
    row = FIXTURES[nct]; study = T.flat({'protocolSection': row['protocol']})
    assert G.relevance(study, row['case']['patient'], row['facts'], [])['category'] == 'opposite_phenotype'


def test_no_reported_gene_is_not_a_gene_mismatch():
    row = copy.deepcopy(FIXTURES['NCT07573059']); study = T.flat({'protocolSection': row['protocol']})
    row['facts']['variants'] = []
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None

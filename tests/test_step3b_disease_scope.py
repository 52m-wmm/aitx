import copy
import json
from pathlib import Path
import socket

import pytest

from aitx.evidence import trials as T
from aitx.step3.b import guards as G, screening as S

ROWS = json.loads((Path(__file__).parent/'fixtures/step3b_disease_scope.json').read_text())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Network forbidden')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)


def specimen(nct):
    row = copy.deepcopy(next(r for r in ROWS if r['nct'] == nct))
    return row, T.flat({'protocolSection': row['protocol']})


@pytest.mark.parametrize('nct', [r['nct'] for r in ROWS])
def test_nine_explicit_other_disease_populations_removed_before_model(nct):
    row, study = specimen(nct)
    plan = {'analysed': [study], 'ineligible': [], 'excluded': []}
    S.filter_relevance(plan, row['case'], row['facts'], [])
    assert not plan['analysed']
    rejection = plan['excluded'][0]
    assert rejection['scope'] == 'patient_disease_candidates'
    assert rejection['disease_scope_anchors']
    assert rejection['reason'] == 'relevance'


def test_dppm_auxiliary_routes_are_preserved_as_unknown():
    row, study = specimen('NCT06092346')
    rejection = G.relevance(study, row['case']['patient'], row['facts'], [])
    assert len(rejection['auxiliary_populations']) == 2
    assert all(r['eligibility'] == 'unknown' and r['description'] for r in rejection['auxiliary_populations'])


@pytest.mark.parametrize('gene', ['NF2', 'CAD', 'ITPA'])
def test_reported_disease_gene_keeps_candidate(gene):
    row, study = specimen('NCT00598351' if gene == 'NF2' else 'NCT06092346')
    row['facts']['variants'].append(dict(row['facts']['variants'][0], gene=gene))
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None


@pytest.mark.parametrize('description', ['NF1 patients are eligible', 'Patients with neurofibromatosis type 1', 'Other patient diagnoses are eligible'])
def test_additional_patient_population_is_not_discarded(description):
    row, study = specimen('NCT00598351')
    study['population_groups'].append({'label': 'Additional patients', 'description': description})
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None


def test_dppm_unknown_extra_patient_population_keeps_candidate():
    row, study = specimen('NCT06092346')
    study['population_groups'].append({'label': 'Other neurological patients'})
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None


@pytest.mark.parametrize('context', ['Known DPPM', 'Suspected disorder of purine and pyrimidine metabolism', 'Persistent elevated uric acid'])
def test_recorded_metabolic_evidence_keeps_dppm_for_review(context):
    row, study = specimen('NCT06092346')
    row['case']['patient']['clinical_context'] += '; ' + context
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None


def test_title_only_nf2_mention_is_not_a_diagnosis_requirement():
    row, study = specimen('NCT00598351')
    study['criteria'] = 'Inclusion Criteria:\n* Patients with neurological disease.\nExclusion Criteria:\n* NF2.'
    study['population_groups'] = []
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None


def test_unknown_gene_is_not_a_cross_gene_conflict():
    row, study = specimen('NCT00598351')
    row['facts']['variants'] = []
    assert G.relevance(study, row['case']['patient'], row['facts'], []) is None

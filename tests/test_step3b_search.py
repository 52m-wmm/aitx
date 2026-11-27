"""Retrieval changes must not turn reported genes into confirmed causal genes."""
import copy

import pytest

from aitx.disease import live
from aitx.evidence import patient_matching as E, trials as T
from aitx.step3.b import search, screening
from tests.test_step3b_pipeline import REFERENCE, offline
from aitx.step3.b import pipeline as P
from aitx.evidence import ledger as LG


def test_all_full_synonyms_and_gene_are_independent_queries():
    queries = search.queries(
        ['cystic fibrosis', 'CF', 'Cystic   Fibrosis', 'mucoviscidosis', 'EDS VIIA', 'cEDS'],
        ['cystic fibrosis'], ['GRIN2B', 'GRIN2B'])
    assert queries == [
        {'query.cond': '"cystic fibrosis"', 'filter.overallStatus': search.OPEN_STATUSES},
        {'query.cond': '"mucoviscidosis"', 'filter.overallStatus': search.OPEN_STATUSES},
        {'query.term': '"GRIN2B"',
         'filter.overallStatus': search.OPEN_STATUSES},
    ]


def test_short_gene_symbols_require_adjacent_context_not_record_wide_cooccurrence():
    clauses = search.gene_query('OTC').split(' OR ')
    assert '"OTC"' not in clauses
    assert '"OTC mutation"' in clauses
    assert '"mutations in OTC"' in clauses
    assert '"OTC deficiency"' in clauses
    assert ' AND ' not in search.gene_query('OTC')
    assert search.gene_query('SLC35A2') == '"SLC35A2"'


def test_short_codes_alone_cannot_produce_a_negative_search():
    with pytest.raises(ValueError, match='full disease name'):
        search.queries(['CF', 'PH1'], [], ['CFTR'])


def test_explicit_families_do_not_expand_by_ontology_order(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Mechanical ontology expansion must not run')
    monkeypatch.setattr(live, 'mondo_parents', forbidden)
    monkeypatch.setattr(E, 'disease_names', lambda *args: ['Example disease'])
    for disease, expected in [
        ('MONDO:0009061', []),  # no respiratory-system superclass
        ('MONDO:0009007', []),  # no hereditary-disease superclass
        ('MONDO:0013891', ['familial amyotrophic lateral sclerosis',
                          'amyotrophic lateral sclerosis', 'ALS']),
        ('MONDO:0015519', ['leukoencephalopathy with vanishing white matter']),
        ('unlisted', []),
    ]:
        _, family, genes = search.branch_terms(
            {'id': disease, 'gene': 'PFN1'}, {'variants': [{'gene': 'PFN1'}]}, {})
        assert family == expected
        assert genes == ['PFN1']


def test_synonym_and_gene_only_hits_are_kept_and_nct_deduplicated(monkeypatch):
    study = copy.deepcopy(REFERENCE[0]['studies'][0])
    queries = []
    def fetch(params, **kwargs):
        queries.append(params)
        studies = [] if params.get('query.cond') == '"Example disease"' else [study]
        return {'query': params, 'studies': studies, 'queried_at': 1}
    monkeypatch.setattr(T, 'search', fetch)
    plan = screening.plan(['Example disease', 'Full synonym'], [], None, None, [],
                          search_genes=['OTC'])
    assert len(queries) == 3
    assert plan['n_unique'] == 1
    assert len(plan['analysed']) == 1
    assert len(plan['analysed'][0]['relevance']['queries']) == 2
    assert plan['gene'] is None  # retrieval is not confirmed causality


def test_production_preserves_reported_gene_with_ambiguous_subtype(monkeypatch):
    specimen = copy.deepcopy(REFERENCE[0])
    calls = offline(monkeypatch, specimen)
    specimen['step2']['primary']['status'] = 'ambiguous'
    observed = []
    original = screening.plan
    def plan(*args, **kwargs):
        observed.append((args[4], kwargs['search_genes']))
        return original(*args, **kwargs)
    monkeypatch.setattr(screening, 'plan', plan)
    ledger = LG.Ledger('TEST', specimen['branches'])
    P.add_trials(ledger, specimen['case'], specimen['step1'], specimen['step2'])
    assert observed == [(['OTC'], ['OTC'])]
    assert len(calls) == 1
    assert ledger.actions[0]['status_by_branch']['b0']['status'] == 'conditional'


@pytest.mark.parametrize('disease,full,alias', [
    ('MONDO:0013891', 'amyotrophic lateral sclerosis', 'ALS'),
    ('MONDO:0013509', 'developmental and epileptic encephalopathy', 'DEE'),
    ('MONDO:0014505', 'developmental and epileptic encephalopathy', 'DEE'),
])
def test_authorized_generic_family_queries_are_not_removed_as_abbreviations(disease, full, alias):
    queries = search.queries(['Specific disease'], list(search.FAMILIES[disease]), [])
    conditions = [q['query.cond'] for q in queries]
    assert '"'+full+'"' in conditions
    assert '"'+alias+'"' in conditions
    assert all(q['filter.overallStatus'] == search.OPEN_STATUSES for q in queries)
    assert search.condition_names([alias, 'CF', 'PH1']) == []

"""Public production entry against frozen pre-rebuild outputs; all I/O is stubbed."""
import copy
import json
from pathlib import Path
import socket

import pytest

from aitx.disease import extract as X
from aitx.evidence import genecontext as GC, ledger as LG, patient_matching as E, trials as T
from aitx.step3.b import pipeline as P, screening as S

REFERENCE = json.loads((Path(__file__).parent/'fixtures/step3b_screening_reference.json').read_text())


def offline(monkeypatch, specimen, answer=None):
    def network_forbidden(*args, **kwargs):
        raise AssertionError('No network or paid model calls allowed')
    monkeypatch.setattr(socket.socket, 'connect', network_forbidden)
    monkeypatch.setattr(X.llm, 'chat', network_forbidden)
    monkeypatch.setattr(E, 'facts', lambda *args: copy.deepcopy(specimen['pf']))
    monkeypatch.setattr(E, 'disease_names', lambda *args: ['Example disease'])
    monkeypatch.setattr(GC, 'known_genes', lambda: {'OTC', 'CPS1'})
    def search(params, **kwargs):
        studies = copy.deepcopy(specimen['studies'])
        return {'studies': studies, 'query': params, 'url': 'local', 'page_urls': ['local'],
                'queried_at': 1, 'total_count': len(studies), 'n_retrieved': len(studies), 'complete': True}
    monkeypatch.setattr(T, 'search', search)
    calls = []
    def chat(messages, sample, use_cache, **kwargs):
        calls.append((messages, sample, use_cache, kwargs))
        return {'parsed': {'hard_conflicts': []} if answer is None else answer,
                'served_model': 'fixture', 'call_id': 'fixture'}
    monkeypatch.setattr(X, '_cached_chat', chat)
    monkeypatch.setattr(X, '_parse', lambda entry: entry)
    monkeypatch.setattr(X.llm, 'config', lambda: {'model': 'fixture'})
    return calls


@pytest.mark.parametrize('specimen', REFERENCE, ids=lambda row: row['name'])
def test_public_entry_matches_frozen_before_output(monkeypatch, specimen):
    calls = offline(monkeypatch, specimen)
    original = copy.deepcopy(specimen)
    ledger = LG.Ledger('TEST', specimen['branches'])
    P.add_trials(ledger, specimen['case'], specimen['step1'], specimen['step2'])
    assert ledger.to_dict() == specimen['expected']
    assert specimen == original
    for messages, sample, use_cache, params in calls:
        assert params == {'prompt_version': S.VERSION, 'call_params': S.PARAMS}
        assert sample == 0 and use_cache is True
        assert messages[0]['content'] == S.PROMPT
    if specimen['name'] in ('age', 'preamble', 'molecular', 'closed', 'empty'):
        assert calls == []


def test_refresh_keeps_other_sections_and_does_not_mutate_input(monkeypatch):
    specimen = REFERENCE[0]
    offline(monkeypatch, specimen)
    ledger = LG.Ledger('TEST', specimen['branches'])
    ledger.note_missing('unreported', 'another step', 'unreported', '3c')
    negative = ledger.add(LG.negative(
        'off_label_expanded_access', ['b0'], database='fixture', endpoint='local',
        query='saved query', queried_at=1, n_results=0, response_count=0, excluded=[]))
    ledger.actions.append(LG.action_record(
        None, 'off_label_expanded_access', 'None found', ['b0'], [], [negative['id']],
        {'b0': 'saved other section'}, searched_none=True))
    ledger.mark_searched('off_label_expanded_access')
    previous = ledger.to_dict()
    previous.update(report_context={'saved': 'unchanged'}, branches_dropped=[])
    original = copy.deepcopy(previous)
    updated = P.refresh_trials(previous, specimen['case'], specimen['step1'], specimen['step2'])
    assert previous == original
    assert updated['report_context'] == previous['report_context']
    assert updated['sections_status']['off_label_expanded_access'] == previous['sections_status']['off_label_expanded_access']
    assert previous['missing_information'][0] in updated['missing_information']
    assert updated['actions'][0] == previous['actions'][0]
    assert negative in updated['evidence']
    assert updated['actions'][1:] == specimen['expected']['actions']


def test_model_response_missing_conflicts_stops_instead_of_empty_success(monkeypatch):
    specimen = REFERENCE[0]
    offline(monkeypatch, specimen, answer={})
    ledger = LG.Ledger('TEST', specimen['branches'])
    with pytest.raises(KeyError, match='hard_conflicts'):
        P.add_trials(ledger, specimen['case'], specimen['step1'], specimen['step2'])
    assert ledger.actions == []


@pytest.mark.parametrize('alternative,quote,axis,want', [
    (False, 'Age 18 to 70 years.', 'age_sex', 'not_applicable'),
    (True, 'Age 18 to 70 years.', 'age_sex', 'conditional'),
    (False, 'invented source', 'age_sex', 'conditional'),
    (False, 'Age 18 to 70 years.', 'clinical_history', 'conditional'),
])
def test_model_conflicts_need_quotes_scope_and_code_proof(
        monkeypatch, tmp_path, alternative, quote, axis, want):
    specimen = copy.deepcopy(REFERENCE[0])
    specimen['pf'].update(age_months=84, age_quote='7-year-old')
    study = specimen['studies'][0]
    study['criteria'] = 'Inclusion Criteria:\n* Age 18 to 70 years.'
    study['protocolSection']['eligibilityModule']['eligibilityCriteria'] = study['criteria']
    conflict = {'axis': axis, 'patient_fact_quote': '7-year-old',
                'trial_rule_quote': quote, 'other_cohort_applicable': alternative,
                'reason': 'proposed by model'}
    monkeypatch.setattr(S, 'REVIEW_DIR', tmp_path)
    offline(monkeypatch, specimen, answer={'hard_conflicts': [conflict]})
    ledger = LG.Ledger('TEST', specimen['branches'])
    P.add_trials(ledger, specimen['case'], specimen['step1'], specimen['step2'])
    action = ledger.actions[0]
    assert action['status_by_branch']['b0']['status'] == want
    assert action['screening']['raw_answer'] == {'hard_conflicts': [conflict]}
    assert action['screening']['conflict_audits'][0]['accepted'] == (want == 'not_applicable')
    assert not [check for check in ledger.checks() if check['status'] == 'fail']

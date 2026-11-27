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


def expected_with_new_search_metadata(specimen):
    """Keep the frozen clinical assertions; only retrieval provenance changes."""
    expected = copy.deepcopy(specimen['expected'])
    queries = [
        {'query.cond': '"Example disease"',
         'filter.overallStatus': 'RECRUITING,NOT_YET_RECRUITING,ENROLLING_BY_INVITATION'},
        {'query.term': ('"OTC gene" OR "OTC mutation" OR "OTC variant" OR "OTC deficiency" OR '
                        '"gene OTC" OR "mutation in OTC" OR "mutations in OTC" OR '
                        '"variant in OTC" OR "variants in OTC"'),
         'filter.overallStatus': 'RECRUITING,NOT_YET_RECRUITING,ENROLLING_BY_INVITATION'},
    ]
    for plan in expected['trial_searches'].values():
        original = plan['searches'][0]
        plan['searches'] = [dict(original, query=q) for q in queries]
        plan['search_genes'] = ['OTC']
        plan['gene'] = 'OTC'  # reported fact survives secondary/ambiguous branches
    for action in expected['actions']:
        if 'relevance' in action:
            action['relevance'] = {'by': 'disease_family_or_gene_query', 'queries': queries}
    for i, evidence in enumerate(expected['evidence']):
        if evidence['kind'] == 'negative':
            search = evidence['search']
            replacement = LG.negative(
                evidence['section'], evidence['applies_to'], database=search['database'],
                endpoint=search['endpoint'], query='; '.join(str(q) for q in queries),
                queried_at=search['queried_at'], n_results=search['n_results'],
                response_count=search['n_results'], excluded=search['excluded'])
            expected['evidence'][i] = replacement
            for action in expected['actions']:
                action['evidence_ids'] = [replacement['id'] if eid == evidence['id'] else eid
                                          for eid in action['evidence_ids']]
                action['provenance']['rules'] = [
                    replacement['retrieved_by'] if rule == evidence['retrieved_by'] else rule
                    for rule in action['provenance']['rules']]
    if specimen['name'] == 'molecular':
        action = expected['actions'][0]
        reason = '疾病基因不匹配：试验明确要求 CPS1，病例已报告变异基因为 OTC；无其他适用基因队列，不推断未报告基因检测阴性。'
        action['status_by_branch']['b0']['reason'] = reason
        for req in action['requirements']:
            if req['fact'] == 'molecular target':
                req['note'] = reason
    return expected


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
    assert ledger.to_dict() == expected_with_new_search_metadata(specimen)
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
    assert updated['actions'][1:] == expected_with_new_search_metadata(specimen)['actions']


def test_model_response_missing_conflicts_stops_instead_of_empty_success(monkeypatch):
    specimen = REFERENCE[0]
    offline(monkeypatch, specimen, answer={})
    ledger = LG.Ledger('TEST', specimen['branches'])
    with pytest.raises(KeyError, match='hard_conflicts'):
        P.add_trials(ledger, specimen['case'], specimen['step1'], specimen['step2'])
    assert ledger.actions == []


def test_all_reported_genes_prevent_false_single_target_exclusion(monkeypatch):
    specimen = copy.deepcopy(next(s for s in REFERENCE if s['name'] == 'molecular'))
    specimen['step2']['primary']['status'] = 'ambiguous'
    # The second reported gene matches the trial, even though this is the OTC branch.
    specimen['pf']['variants'].append(dict(specimen['pf']['variants'][0],
                                          gene='CPS1', quote='CPS1 reported variant'))
    offline(monkeypatch, specimen)
    ledger = LG.Ledger('TEST', specimen['branches'])
    P.add_trials(ledger, specimen['case'], specimen['step1'], specimen['step2'])
    assert ledger.actions[0]['status_by_branch']['b0']['status'] == 'conditional'


@pytest.mark.parametrize('nct', ['NCT05432466', 'NCT05994664'])
def test_col1a1_report_is_not_a_col3a1_negative_result(monkeypatch, tmp_path, nct):
    from aitx import runmeta
    root = Path(__file__).resolve().parents[1]
    case = runmeta.find_case('PRAC-COL1A1')
    step1 = json.loads((root/'out/step1/PRAC-COL1A1.json').read_text())
    step2 = json.loads((root/'out/step2/PRAC-COL1A1.json').read_text())
    saved = json.loads((root/'out/step3/PRAC-COL1A1.json').read_text())
    action = next(a for a in saved['actions'] if a.get('nct') == nct)
    study = T.flat({'protocolSection': action['protocolSection']})
    facts = E.facts(step1, step2)
    monkeypatch.setattr(S, 'REVIEW_DIR', tmp_path)
    # Published deterministic exclusions need not retain a model answer.
    from aitx.step3.b import rules
    target = rules.single_target_conflict(study, ['COL1A1'])
    conflict = {'axis': 'molecular', 'patient_fact_quote': 'COL1A1',
                'trial_rule_quote': target['trial_rule_quote'],
                'other_cohort_applicable': False,
                'reason': 'Required disease gene differs from reported COL1A1.'}
    audit = S.verify(S.sample(case, study), conflict, study, facts, ['COL1A1'])
    assert audit['patient_quote_valid'] and audit['trial_quote_valid']
    assert audit['accepted'] is True
    assert audit['conflict'] == conflict
    assert audit['reported_gene_evidence'] == [
        {'gene': 'COL1A1', 'quote': facts['variants'][0]['quote'], 'step': 1}]
    assert '不证明该基因检测阴性' in audit['gene_evidence_scope']


def test_refresh_preserves_existing_reciprocal_links_without_changing_verdict(monkeypatch):
    specimen = REFERENCE[0]
    offline(monkeypatch, specimen)
    previous = copy.deepcopy(specimen['expected'])
    previous.update(report_context={}, branches_dropped=[])
    links = [{'action_key': 'drug:rxcui:2054968', 'section': 'off_label_expanded_access'}]
    previous['actions'][0]['see_also'] = links
    updated = P.refresh_trials(previous, specimen['case'], specimen['step1'], specimen['step2'])
    assert updated['actions'][0]['see_also'] == links
    assert updated['actions'][0]['see_also'] is not links
    assert updated['actions'][0]['status_by_branch'] == previous['actions'][0]['status_by_branch']


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

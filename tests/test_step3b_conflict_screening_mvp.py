"""Offline behavioral checks; mocked model responses are not clinical experiment results."""
import copy
import json
import pytest
from scripts.experiments import step3b_conflict_screening_mvp as E


SAMPLE = {'case_id': 'child', 'nct_id': 'trial', 'patient_text': 'A 7-year-old male.',
          'trial_text': 'Only enrolling under 6 years of age.',
          'expected': 'exclude', 'category': 'preamble_conflict'}
CONFLICT = {'axis': 'preamble_or_cohort', 'patient_fact_quote': '7-year-old',
            'trial_rule_quote': 'Only enrolling under 6 years of age.',
            'other_cohort_applicable': False, 'reason': 'Age exceeds the current enrollment limit.'}


def test_g3_requires_two_quotes_and_no_alternative():
    assert E.decide(3, {'hard_conflicts': []}, SAMPLE)[0] == 'candidate'
    for field, value, expected in [
        ('patient_fact_quote', '  7-YEAR-OLD ', 'exclude'),
        ('patient_fact_quote', '8-year-old', 'candidate'),
        ('trial_rule_quote', 'Only enrolling under 5 years of age.', 'candidate'),
        ('patient_fact_quote', '', 'candidate'),
        ('trial_rule_quote', ' ', 'candidate'),
        ('other_cohort_applicable', True, 'candidate'),
    ]:
        c = dict(CONFLICT, **{field: value})
        assert E.decide(3, {'hard_conflicts': [c]}, SAMPLE)[0] == expected
    original = {'hard_conflicts': [copy.deepcopy(CONFLICT)]}
    assert E.decide(3, original, SAMPLE)[0] == 'exclude'
    assert original == {'hard_conflicts': [CONFLICT]}
    assert E.decide(3, {'hard_conflicts': [dict(CONFLICT, other_cohort_applicable=True), CONFLICT]}, SAMPLE)[0] == 'exclude'


def test_bad_schema_and_missing_sample_fields_stop(tmp_path):
    with pytest.raises(ValueError):
        E.decide(3, {'hard_conflicts': [dict(CONFLICT, other_cohort_applicable='false')]}, SAMPLE)
    with pytest.raises(KeyError):
        E.decide(3, {}, SAMPLE)
    p = tmp_path / 'samples.json'
    p.write_text(json.dumps([{'case_id': 'missing fields'}]))
    with pytest.raises(KeyError):
        E.load_samples(p)


def test_complete_mock_run_and_metrics(tmp_path, monkeypatch):
    samples = [SAMPLE, dict(SAMPLE, case_id='unknown', expected='candidate', category='missing_info')]
    calls = []
    systems = {1: 'minimal', 2: 'old', 3: 'conflict'}

    def fake_chat(messages, **kwargs):
        calls.append((messages, kwargs))
        patient = json.loads(messages[1]['content'].split('\nReturn strictly valid JSON.')[0])
        assert 'expected' not in patient and 'category' not in patient
        assert patient['patient_text'] == SAMPLE['patient_text']
        group = {v: k for k, v in systems.items()}[messages[0]['content']]
        decision = 'exclude' if patient['case_id'] == 'child' else 'candidate'
        answer = {'decision': decision, 'reason': 'mocked'} if group != 3 else {
            'hard_conflicts': [CONFLICT] if decision == 'exclude' else []}
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(answer)}}]}

    monkeypatch.setattr(E.llm, 'chat', fake_chat)
    monkeypatch.setattr(E.peak, 'check_before_call', lambda: None)
    monkeypatch.setattr(E.budget, 'check_before_call', lambda: None)
    monkeypatch.setattr(E.budget, 'cap', lambda: None)
    params = {'temperature': 0, 'max_tokens': 100, 'response_format': {'type': 'json_object'}}
    records = E.run_experiment(samples, systems, tmp_path, params)
    assert len(calls) == 18
    assert all(p['temperature'] == 0 and p['response_format'] == {'type': 'json_object'} for _, p in calls)
    metrics = E.summarize(samples, records)
    assert all(m['FER']['rate'] == 0 and m['hard_conflict_recall']['rate'] == 1 for m in metrics.values())
    assert metrics[3]['quote_pair_pass_rate']['rate'] == 1
    # Identical decisions can mask varying full JSON answers.
    records[0]['answer']['reason'] = 'different reason'
    metrics = E.summarize(samples, records)
    assert metrics[1]['full_json_consistency']['rate'] == .5
    assert metrics[1]['decision_consistency']['rate'] == 1
    with pytest.raises(ValueError):
        E.summarize(samples, records[:-1])


def test_frozen_defaults_and_no_conflict_quote_denominator():
    samples = E.load_samples(E.DEFAULT_SAMPLES)
    assert len(samples) == 4
    assert {s['nct_id'] for s in samples} == {'NCT06654752', 'NCT07148739', 'NCT04580420', 'NCT02026388'}
    assert 'only enrolling potential participants under 6 years' in samples[2]['trial_text']
    assert len(E.prompts()) == 3
    assert E.fraction(0, 0)['rate'] is None


def test_error_rate_denominators_and_empty_quotes():
    samples = [SAMPLE, dict(SAMPLE, case_id='candidate', expected='candidate')]
    records = []
    for group in (1, 2, 3):
        for i, s in enumerate(samples):
            decisions = ['exclude', 'candidate', 'candidate']
            for repeat, decision in enumerate(decisions, 1):
                records.append({'group': group, 'sample_index': i, 'repeat': repeat,
                                'expected': s['expected'], 'decision': decision,
                                'answer': {'decision': decision}, 'quote_audit': []})
    metrics = E.summarize(samples, records)
    assert metrics[1]['FER'] == {'numerator': 1, 'denominator': 3, 'rate': 1 / 3}
    assert metrics[1]['hard_conflict_recall']['rate'] == 1 / 3
    assert metrics[1]['full_json_consistency']['rate'] == 0
    assert metrics[3]['quote_pair_pass_rate']['rate'] is None

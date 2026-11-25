"""Current enrollment notes decide records through the production assembler."""
import json
from pathlib import Path

import pytest

from aitx.evidence import ledger as LG, trials as T
from aitx.step3.b import rules as C
from aitx.step3.b import records as TR, screening as S
from tests.trial_fixtures import PF, BR, STUDY

NOTE = 'Note: Currently, the DCR-PHXC-204 study is only enrolling potential participants under 6 years of age.'


def record(text, months=84):
    pf = dict(PF, age_months=months, age_quote=None if months is None else f'Age {months} months')
    study = dict(STUDY, criteria=text, min_age=None, _accessed_at=1, relevance={}, specific=True, interventions=[])
    study['protocolSection'] = {'identificationModule':{'briefTitle':study['title']},
        'designModule':{'studyType':'INTERVENTIONAL','designInfo':{'primaryPurpose':'TREATMENT'}},
        'eligibilityModule':{'eligibilityCriteria':text}}
    study['prefilter'] = S.prefilter(study, pf['age_months'], pf['sex'])
    study['code_molecular_conflict'] = None
    led = LG.Ledger('TEST', [BR])
    TR.record(led, study, 'b1', pf, {'id':'TEST'}, {'hard_conflicts':[]}, 'code', [])
    assert not [c for c in led.checks() if c['status'] == 'fail']
    return led, led.actions[0]


def test_current_note_overrides_historical_age_cohort():
    fixture = json.loads((Path(__file__).parent / 'fixtures/agxt_trial_criteria_review.json').read_text())['NCT04580420']
    text = fixture['criteria']
    assert text.startswith(NOTE)
    led, action = record(text)
    line = next(r for r in action['requirements'] if r['requirement'] == NOTE)
    assert line['result'] == 'fail'
    assert action['status_by_branch']['b1']['status'] == 'not_applicable'
    ev = led.evidence[line['requirement_evidence']]
    assert ev['quote'] == NOTE and ev['quote_verified'] and ev['status'] == 'verified'


@pytest.mark.parametrize('months,want', [(60, 'pass'), (72, 'fail'), (84, 'fail'), (None, 'unknown')])
def test_open_age_boundary_and_missing_patient_age(months, want):
    _, a = record(NOTE + '\nInclusion Criteria:\n* Further screening required', months)
    assert next(r for r in a['requirements'] if r['requirement'] == NOTE)['result'] == want
    assert a['status_by_branch']['b1']['status'] == ('not_applicable' if want == 'fail' else 'conditional')


@pytest.mark.parametrize('note,want', [
    ('Currently only enrolling participants aged 6 years or older.', 'pass'),
    ('Currently only enrolling participants aged 8 years or older.', 'fail'),
    ('Currently closed to participants under 8 years of age.', 'fail'),
    ('Currently closed  to participants under 8 years of age.', 'fail'),
    ('Currently only enrolling participants aged 6 to 11 years.', 'pass'),
    ('Currently only enrolling participants under 6 months of age.', 'fail'),
    ('Currently only enrolling cohort A.', 'unknown'),
    ('Cohort A is closed to participants under 8 years of age.', 'unknown'),
    ('Previously only enrolling participants under 6 years of age.', 'unknown'),
    ('Currently not only enrolling participants under 6 years of age.', 'unknown'),
    ('If cohort A is full, only enrolling participants under 6 years of age.', 'unknown'),
    ('Currently only enrolling participants under 6 years or over 18 years.', 'unknown'),
])
def test_explicit_restriction_or_unresolved_scope(note, want):
    _, a = record(note + '\nInclusion Criteria:\n* Further screening required')
    assert next(r for r in a['requirements'] if r['requirement'] == note)['result'] == want


def test_fail_priority_is_independent_of_unknowns_and_cohort_passes():
    assert LG.status_from(['unknown', 'pass', 'fail']) == 'not_applicable'
    assert LG.status_from(['fail', 'unknown', 'pass']) == 'not_applicable'


def test_multiline_cohort_context_is_not_applied_to_every_patient():
    _, action = record('Cohort A:\nCurrently only enrolling participants under 6 years of age.\nInclusion Criteria:\n* Further screening required')
    assert all(r['result'] == 'unknown' for r in action['requirements'] if r['fact'] not in ('age','sex'))
    assert action['status_by_branch']['b1']['status'] == 'conditional'


@pytest.mark.parametrize('sex,result', [('male', 'pass'), ('female', 'fail'), (None, 'unknown')])
def test_current_explicit_population_checks_do_not_invent_sex(sex, result):
    pf = dict(PF, sex=sex, sex_quote=None if sex is None else sex)
    row = C.enrollment_note_lines({'criteria': 'Currently only enrolling males.\nInclusion Criteria:\n* Other'}, pf)[0]
    assert LG.requirement_result(row['kind'], row['patient_status']) == result

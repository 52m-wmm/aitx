"""Whole-population exclusion must not flatten OR, unknowns or treatment arms."""
import copy
import json
from pathlib import Path
import socket

import pytest

from aitx.evidence import trials as T
from aitx.step3.b import cohorts as C, screening as S

ROWS = json.loads((Path(__file__).parent/'fixtures/step3b_targeted_guards.json').read_text())


def specimen(nct):
    r = copy.deepcopy(next(r for r in ROWS if r['protocol']['identificationModule']['nctId'] == nct))
    return r, T.flat({'protocolSection': r['protocol']})


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('No network/model calls')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(S, 'REVIEW_DIR', tmp_path)


@pytest.mark.parametrize('nct,count', [('NCT06302270', 2), ('NCT06797206', 3)])
def test_all_populations_conflict_with_15_year_old_male(nct, count):
    row, study = specimen(nct)
    check = C.evaluate(study, row['facts'])
    assert check['all_conflict']
    assert len(check['populations']) == count
    audit = S.verify(S.sample(row['case'], study), row['conflicts'][0], study, row['facts'], ['CFTR'])
    assert audit['accepted']
    assert audit['verified_trial_rule_quote'] in study['criteria']
    assert audit['cohort_check'] == check


@pytest.mark.parametrize('months', [None, 0, 6, 12, 18, 24, 36, 60, 72, 192])
def test_unknown_or_possible_population_keeps_study(months):
    row, study = specimen('NCT06797206')
    row['facts']['age_months'] = months
    # 12--24 months conflicts with the body, but is supported by cohort metadata.
    assert not C.evaluate(study, row['facts'])['all_conflict']


@pytest.mark.parametrize('months,sex', [(None, 'male'), (None, 'unknown'), (0, 'male'), (6, 'male'), (180, 'female'), (180, 'unknown')])
def test_mother_newborn_unknown_or_potential_route_kept(months, sex):
    row, study = specimen('NCT06302270')
    row['facts'].update(age_months=months, sex=sex)
    assert not C.evaluate(study, row['facts'])['all_conflict']


@pytest.mark.parametrize('change', ['extra_group', 'unknown_age', 'conditional_age', 'alternative_age', 'treatment_arm', 'unparsed_header'])
def test_incomplete_population_scope_cannot_exclude(change):
    row, study = specimen('NCT06797206')
    if change == 'extra_group':
        study['population_groups'].append({'label': 'Other patients'})
    elif change == 'unknown_age':
        study['criteria'] = study['criteria'].replace('Age three to six years at time of visit', 'Age eligibility determined by investigator')
        study['population_groups'][2]['description'] = 'Age eligibility determined by investigator'
    elif change == 'conditional_age':
        study['criteria'] = study['criteria'].replace('Age three to six years at time of visit', 'Age three to six years at time of visit unless older siblings are included')
    elif change == 'alternative_age':
        study['criteria'] = study['criteria'].replace('Age three to six years at time of visit', 'Age three to six years at time of visit or adolescents')
    elif change == 'treatment_arm':
        study['population_groups'][0]['type'] = 'PLACEBO_COMPARATOR'
    else:
        study['criteria'] = study['criteria'].replace('Exclusion Criteria:', 'Other eligible participants:\n\n* Age unknown\n\nExclusion Criteria:')
    check = C.evaluate(study, row['facts'])
    assert check is None or not check['all_conflict']


def test_male_or_female_population_is_not_female_only():
    row, study = specimen('NCT06302270')
    study['criteria'] = study['criteria'].replace('Woman with', 'Woman or man with')
    check = C.evaluate(study, row['facts'])
    assert not check['all_conflict']


@pytest.mark.parametrize('field,value', [('patient_fact_quote', 'invented'), ('trial_rule_quote', 'invented'), ('other_cohort_applicable', True)])
def test_invalid_anchor_or_reported_alternative_still_blocks_acceptance(field, value):
    row, study = specimen('NCT06797206')
    row['conflicts'][0][field] = value
    assert not S.verify(S.sample(row['case'], study), row['conflicts'][0], study, row['facts'], ['CFTR'])['accepted']

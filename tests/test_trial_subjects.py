"""A patient's diagnosis is not evidence that a relative has that diagnosis."""
import pytest

from aitx.evidence import ledger as LG
from aitx.step3.b import criteria as C
from aitx.step3.b import records as TR
from tests.test_criteria import _PF, _conf_branch, _mapped, STUDY

RELATIVE = 'Relative of someone with confirmed primary hyperoxaluria.'
PATIENT = 'Diagnosis of primary hyperoxaluria'
DESCRIPTION = 'Diagnosis of Primary Hyperoxaluria, or a family member of someone with this diagnosis.'


@pytest.mark.parametrize('text', [RELATIVE, 'Family member of someone with primary hyperoxaluria.',
                                'Individuals have a family history of a sibling with Primary Hyperoxaluria.'])
@pytest.mark.parametrize('fact', ['diagnosis', 'genetic_confirmation'])
def test_self_diagnosis_does_not_satisfy_relative_or_family_history(text, fact):
    st, patient_fact, why, details = C.evaluate({'fact': fact, 'quote': 'primary hyperoxaluria', 'criterion_text': text},
                                              _PF, {'facts': []}, _conf_branch(), ['primary hyperoxaluria'])
    assert st == 'unknown' and patient_fact['value'] is None
    assert details['subject'] == 'relative'


def rows_with_context(groups):
    items = [{'id': 'inc1', 'kind': 'inclusion', 'text': PATIENT, 'level': 0, 'parent': None},
             {'id': 'inc2', 'kind': 'inclusion', 'text': RELATIVE, 'level': 0, 'parent': None}]
    mappings = [{'id': it['id'], 'fact': 'diagnosis', 'quote': it['text']} for it in items]
    text = 'Inclusion Criteria:\n* ' + PATIENT + '\n* ' + RELATIVE
    return C.lines_for({'criteria': text, 'population_groups': groups}, _mapped(items, mappings), _PF,
                       {'facts': []}, _conf_branch(), ['primary hyperoxaluria'])


def as_requirements(rows):
    return [LG.requirement(f'r{i}', r['kind'], r['text'], 'e1', r['patient_fact'], r['patient_status'], ['b'],
                           r['note'], alternative=r.get('alternative')) for i, r in enumerate(rows)]


def test_explicit_patient_or_relative_cohorts_use_existing_alternatives():
    rows = rows_with_context([{'label': 'PH', 'description': DESCRIPTION}])
    assert len(rows) == 2
    assert rows[0]['patient_status'] == 'satisfies' and rows[1]['patient_status'] == 'unknown'
    assert rows[0]['alternative'] != rows[1]['alternative']
    assert LG.status_of(as_requirements(rows), 'b')[0] == 'applicable'
    assert rows[0]['details']['population_relation']['sources'][0]['quote'] == DESCRIPTION
    # A shared hard exclusion still overrides an eligible patient cohort.
    reqs = as_requirements(rows) + [LG.requirement('shared', 'exclusion', 'shared exclusion', 'e2',
                                                {'quote': 'known fact'}, 'satisfies', ['b'])]
    assert LG.status_of(reqs, 'b')[0] == 'not_applicable'


@pytest.mark.parametrize('groups', [[], [{'label': 'PH', 'description': 'Patients and relatives are required.'}],
                                  [{'label': 'Other', 'description': 'Diagnosis of Dent Disease, or a family member of someone with this diagnosis.'}]])
def test_absent_ambiguous_or_unrelated_population_context_does_not_invent_or(groups):
    rows = rows_with_context(groups)
    assert all('alternative' not in r for r in rows)
    assert LG.status_of(as_requirements(rows), 'b')[0] == 'conditional'


def test_production_recorder_keeps_unknown_relative_and_verified_or_source():
    branch = _conf_branch()
    text = 'Inclusion Criteria:\n* ' + PATIENT + '\n* ' + RELATIVE
    groups = [{'label': 'PH', 'description': DESCRIPTION}]
    from aitx.evidence import trials as T
    items = T.split_criteria(text)
    mappings = [{'id': it['id'], 'fact': 'diagnosis', 'quote': it['text']} for it in items]
    study = dict(STUDY, criteria=text, min_age=None, max_age=None, population_groups=groups, _accessed_at=1,
                 relevance={}, specific=True)
    led = LG.Ledger('TEST', [branch])
    TR._record(led, study, {branch['id']: 'analysed'}, _mapped(items, mappings), _PF,
               {'facts': []}, {branch['id']: branch}, {'candidates': []})
    action = led.actions[0]
    assert action['status_by_branch'][branch['id']]['status'] == 'applicable'
    relative = next(r for r in action['requirements'] if r['requirement']==RELATIVE)
    assert relative['result']=='unknown' and relative['alternative'].startswith('population:relative:')
    from aitx.report.assemble import unknown_lines
    assert relative not in unknown_lines(action)
    for proof in relative['details']['population_relation']['sources']:
        ev=led.evidence[proof['evidence_id']]
        assert ev['quote']==DESCRIPTION and ev['status']=='verified' and ev['produced_by']=='code'
        assert ev['id'] in action['evidence_ids']
    assert not [check for check in led.checks() if check['status']=='fail']


def test_nested_genetic_condition_keeps_its_relative_subject():
    from aitx.evidence import trials as T
    text = 'Inclusion Criteria:\n* Relative of someone with primary hyperoxaluria:\n  * Diagnosis confirmed by genetic testing'
    items = T.split_criteria(text)
    mappings = [{'id': 'inc1', 'fact': 'header', 'quote': items[0]['text']},
                {'id': 'inc2', 'fact': 'genetic_confirmation', 'quote': items[1]['text']}]
    rows = C.lines_for({'criteria': text}, _mapped(items,mappings), _PF, {}, _conf_branch(), ['primary hyperoxaluria'])
    assert len(rows)==1 and rows[0]['patient_status']=='unknown'
    assert rows[0]['details']['scope_quote']==items[0]['text']


def test_resolved_patient_group_uses_the_matching_diagnosis_cohort_proof():
    study={'criteria': 'Inclusion Criteria:\n* '+PATIENT+'\n* '+RELATIVE,
           'population_groups': [{'label': 'PH', 'description': DESCRIPTION}]}
    rows=[{'kind': 'inclusion','text':PATIENT,'item':'diagnoses:inc1','details':{},'patient_status':'satisfies',
           'any_of':[{'requirement':PATIENT,'patient_status':'satisfies'},
                     {'requirement':'Diagnosis of another disease','patient_status':'unknown'}]},
          {'kind':'inclusion','text':RELATIVE,'item':'inc2','details':{},'patient_status':'unknown'}]
    C.population_alternatives(study,rows)
    assert rows[0]['alternative'].startswith('population:patient:')
    assert rows[1]['alternative'].startswith('population:relative:')


def test_mandatory_eligibility_conflict_is_not_overridden_by_group_description():
    from aitx.evidence import trials as T
    text='Inclusion Criteria:\nAll of the following criteria are required:\n* '+PATIENT+'\n* '+RELATIVE
    items=T.split_criteria(text)
    mappings=[{'id':it['id'],'fact':'diagnosis','quote':it['text']} for it in items[1:]]
    rows=C.lines_for({'criteria':text,'population_groups':[{'description':DESCRIPTION}]},
                     _mapped(items,mappings),_PF,{},_conf_branch(),['primary hyperoxaluria'])
    assert all('alternative' not in row for row in rows)

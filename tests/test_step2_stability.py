from scripts.step2_stability import changes, compare
import pytest
from scripts import step2_stability


def test_full_diff_preserves_additions_removals_and_values():
    assert changes({'a':1,'b':2},{'a':3,'c':4}) == [
        {'path':'/a','old':1,'new':3}, {'path':'/b','removed':2}, {'path':'/c','added':4}]


def test_extraction_changes_are_separate_from_diagnostic_changes():
    r = {'primary':{'id':'A','status':'ambiguous','alternatives':[{'id':'B'}]},
         'phenotypes':[], 'patient_facts':{}, 'candidates':[{'key':'A'},{'key':'B'}]}
    changed = dict(r, phenotypes=[{'hpo_id':'HP:1'}])
    d = compare(r,changed)
    assert d['hpo_diff'] and not d['diagnosis_changed'] and not d['candidate_set_changed']
    changed = dict(r, primary={'id':'A','status':'resolved','alternatives':[]})
    assert compare(r,changed)['diagnosis_changed']


def test_completed_experiment_refuses_before_preflight_writes(tmp_path, monkeypatch):
    out = tmp_path/'runs/step2-stability-20261118'
    out.mkdir(parents=True)
    (out/'proposal.json').write_text('{}')
    (out/'attempts.jsonl').touch()
    monkeypatch.setattr(step2_stability, 'ROOT', tmp_path)
    monkeypatch.setattr('sys.argv', ['step2_stability'])
    with pytest.raises(FileExistsError, match='already started'):
        step2_stability.main()
    assert not (out/'fixed_inputs.json').exists()

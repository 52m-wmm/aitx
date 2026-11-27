import json
import tarfile

import pytest

from scripts import cleanup_run_history as C


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_retains_recent_activity_and_latest_batches_then_verifies_archive(tmp_path, monkeypatch):
    root = tmp_path/'project'
    now = 1000000
    monkeypatch.setattr(C.time, 'time', lambda: now)
    for name, started, last in [('old', now-400000, now-300000),
                                ('active', now-400000, now-10), ('new', now-5, now-5)]:
        save(root/f'runs/sessions/{name}/meta.json', {'started':started})
        save(root/f'runs/sessions/{name}/calls.jsonl', {'at':last})
    save(root/'runs/old-experiment/data.json', {'old':'source'})
    save(root/'runs/llm_calls.jsonl', {'amount':12})
    save(root/'runs/step3_remaining_budget.json', {'remaining':1})
    for name, at in [('old',1), ('new',2)]:
        save(root/f'runs/step3a/CASE/{name}/plan.json', {'case_id':'CASE','source_path':'chapter'})
        save(root/f'runs/step3a/CASE/{name}/01/request.json', {'at':at})
        save(root/f'.cache/step3b/CASE/{name}/execution.json', {'started_at':at})
    save(root/'out/current.json', {'step3a':{'CASE':'old'}})
    save(root/'out/step3/CASE.json', {'formal':'unchanged'})
    link = root/'runs/old-experiment/cache-link.json'
    link.symlink_to(root/'out/step3/CASE.json')
    decision = C.plan(root)
    assert [r['session'] for r in decision['sessions']] == ['active','new']
    assert 'runs/sessions/old/meta.json' in decision['remove']
    assert 'runs/sessions/active/meta.json' not in decision['remove']
    assert decision['step3a'] == ['runs/step3a/CASE/new']
    assert decision['step3b'] == ['.cache/step3b/CASE/new']
    originals = {name:(root/name).read_bytes() for name in decision['remove'] if not (root/name).is_symlink()}
    archive = tmp_path/'archive/history.tar.gz'
    result = C.apply(root, decision, archive)
    assert result['removed_files'] == len(originals) + 1
    with tarfile.open(archive) as tar:
        member = tar.getmember('runs/old-experiment/cache-link.json')
        assert member.issym()
        assert member.linkname == str(root/'out/step3/CASE.json')
        assert not link.is_symlink()
        for name, data in originals.items():
            assert tar.extractfile(name).read() == data
            assert not (root/name).exists()
    assert json.loads((root/'out/current.json').read_text())['step3a']['CASE'] == 'new'
    assert json.loads((root/'out/step3/CASE.json').read_text()) == {'formal':'unchanged'}
    assert json.loads((root/'runs/llm_calls.jsonl').read_text()) == {'amount':12}
    assert C.plan(root)['remove'] == []


def test_refuses_archive_inside_project_before_removing(tmp_path):
    with pytest.raises(ValueError, match='outside'):
        C.apply(tmp_path, {'remove':[]}, tmp_path/'history.tar.gz')

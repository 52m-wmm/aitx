import json
import os

import pytest

from aitx import runmeta
from aitx.step3.b import results as R
from scripts import step3b_view as V
from scripts.viewer_app import Watcher


def setup_case(tmp_path, monkeypatch):
    monkeypatch.setattr(V, 'ROOT', tmp_path)
    monkeypatch.setattr(runmeta, 'code_fingerprint', lambda: 'test')
    monkeypatch.setattr(runmeta, 'code_commit', lambda: 'test')
    case = {'id': 'CASE', 'patient': {'clinical_context': 'Unknown'}}
    ledger = {'schema_version': 'evidence-ledger-v3', 'patient_id': 'CASE',
              'ok': True, 'actions': [], 'evidence': [], 'trial_searches': {}}
    path = tmp_path/'out/step3/CASE.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(ledger))
    return case, ledger, path


def test_run_publishes_archive_cards_and_watcher_update(tmp_path, monkeypatch):
    case, ledger, path = setup_case(tmp_path, monkeypatch)
    before = path.read_bytes()
    calls = []
    def refresh(previous, actual_case, one, two):
        calls.append((previous, actual_case, one, two))
        assert '运行中' in V.panel('CASE')
        return ledger
    monkeypatch.setattr(R, 'refresh_trials', refresh)
    watcher = Watcher(root=tmp_path)
    folder = R.run_case(tmp_path, case, {'one': 1}, {'two': 2}, {1: 'h1', 2: 'h2'})
    assert len(calls) == 1
    assert (folder/'previous-ledger.json').read_bytes() == before
    assert (folder/'ledger.json').read_bytes() == path.read_bytes()
    assert json.loads(path.read_text())['_meta']['upstream'] == {'1': 'h1', '2': 'h2'}
    assert R.latest_folder(tmp_path, 'CASE') == folder
    page = V.panel('CASE')
    assert folder.name in page and '执行完成，待内容审核' in page
    assert '本次结果' in page
    watcher.poll()
    assert str((folder/'execution.json').relative_to(tmp_path)) in watcher.changed
    assert str((folder/'result.json').relative_to(tmp_path)) in watcher.changed


def test_failure_keeps_formal_output_and_shows_latest_failed_batch(tmp_path, monkeypatch):
    case, ledger, path = setup_case(tmp_path, monkeypatch)
    monkeypatch.setattr(R, 'refresh_trials', lambda *args: ledger)
    old = R.run_case(tmp_path, case, {}, {}, {})
    before = path.read_bytes()
    def fail(*args):
        raise ValueError('missing source')
    monkeypatch.setattr(R, 'refresh_trials', fail)
    with pytest.raises(ValueError, match='missing source'):
        R.run_case(tmp_path, case, {}, {}, {})
    latest = R.latest_folder(tmp_path, 'CASE')
    assert latest != old and path.read_bytes() == before
    assert json.loads((latest/'execution.json').read_text())['state'] == 'failed'
    assert not (latest/'result.json').exists()
    assert '失败 / 未完成' in V.panel('CASE')
    assert '不自动切回旧结果' in V.panel('CASE')


def test_conversion_error_does_not_publish_ledger(tmp_path, monkeypatch):
    case, ledger, path = setup_case(tmp_path, monkeypatch)
    before = path.read_bytes()
    monkeypatch.setattr(R, 'refresh_trials', lambda *args: ledger)
    def fail(*args):
        raise KeyError('protocolSection')
    monkeypatch.setattr(R, 'ledger_view', fail)
    with pytest.raises(KeyError, match='protocolSection'):
        R.run_case(tmp_path, case, {}, {}, {})
    assert path.read_bytes() == before
    assert '失败 / 未完成' in V.panel('CASE')


def test_import_preserves_bytes_and_time_not_copy_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(V, 'ROOT', tmp_path)
    source = tmp_path/'old.json'
    source.write_text('{"case_id":"CASE","patient":{"id":"CASE"}}')
    os.utime(source, (100, 100))
    first = R.import_saved(tmp_path, source)
    assert (first/'result.json').read_bytes() == source.read_bytes()
    os.utime(source, (200, 200))
    second = R.import_saved(tmp_path, source)
    os.utime(first/'execution.json', (999, 999))
    assert R.latest_folder(tmp_path, 'CASE') == second
    assert R.latest_folder(tmp_path, 'OTHER') is None
    monkeypatch.setattr(V, 'result_panel', lambda cid, path: str(path))
    assert str(second/'result.json') in V.panel('CASE')
    # A later legacy export remains visible until the next cached batch.
    exported = tmp_path/'out/3b/CASE/result.json'
    exported.parent.mkdir(parents=True)
    exported.write_bytes(source.read_bytes())
    os.utime(exported, (300, 300))
    monkeypatch.setattr(V, 'experiment_panel', lambda cid: 'new legacy export')
    assert V.panel('CASE') == 'new legacy export'

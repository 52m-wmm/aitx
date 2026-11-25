import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from scripts import viewer_app as A
from aitx.viewer import step3a as V


def test_independent_api_uses_exact_batch_and_explicit_budget(tmp_path, monkeypatch):
    folder = tmp_path/'runs/step3a/CASE/batch'
    folder.mkdir(parents=True)
    (folder/'plan.json').write_text('{"case_id":"CASE","source_path":"/sources/a.xml"}')
    monkeypatch.setattr(A, 'ROOT', tmp_path)
    runner = A.Runner(tmp_path/'logs')
    calls = []
    def start(case_id, first, last, no_cache, *, command):
        calls.append(command)
        return SimpleNamespace(record=lambda:{'id':'test','command':command})
    monkeypatch.setattr(runner, 'start', start)
    client = TestClient(A.create_app(runner=runner))
    body = {'case_id':'CASE','batch':'batch','action':'recover'}
    result = client.post('/api/step3a/runs',json=body)
    assert result.status_code == 201
    assert 'run_step3a.py' in calls[-1][2] and calls[-1][3] == 'recover'
    assert '--max-cost-usd' not in calls[-1]
    body['action'] = 'resume'
    assert client.post('/api/step3a/runs',json=body).status_code == 400
    body['max_cost_usd'] = .5
    assert client.post('/api/step3a/runs',json=body).status_code == 201
    assert '--resume' in calls[-1] and calls[-1][calls[-1].index('--concurrency')+1]=='4'
    (folder/'plan.json').write_text('{"case_id":"OTHER"}')
    assert client.post('/api/step3a/runs',json=body).status_code == 400
    body['batch'] = '../batch'
    assert client.post('/api/step3a/runs',json=body).status_code == 400
    assert len(calls)==2


def test_step3a_execution_controls_are_not_on_case_page():
    html = A.rerun_panel('CASE','zh')
    for text in ('独立 Step3a', '操作批次', 'step3a-budget', 'data-3a-action', '离线恢复', '本轮总费用上限'):
        assert text not in html
    assert "data-step='1'" in html and "data-step='2'" in html
    assert "data-step='3'" not in html


def test_watcher_detects_index_and_archived_batch_updates(tmp_path):
    folder=tmp_path/'runs/step3a/CASE/batch';folder.mkdir(parents=True)
    (tmp_path/'out').mkdir()
    watcher=A.Watcher(tmp_path)
    (tmp_path/'out/current.json').write_text('{"step3a":{}}')
    (folder/'execution.json').write_text('{"state":"running"}')
    watcher.poll()
    assert 'out/current.json' in watcher.changed
    assert 'runs/step3a/CASE/batch/execution.json' in watcher.changed

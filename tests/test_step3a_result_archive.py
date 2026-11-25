import json
import os
import pytest
from pathlib import Path

from aitx.viewer import step3a as V
from aitx.step3.a.results import archive, current_folder, select


def test_cli_selection_is_explicit_but_page_automatically_shows_latest_batch(tmp_path, monkeypatch):
    root=tmp_path/'runs/step3a/CASE';root.mkdir(parents=True)
    for name in ['complete','prepared']:
        folder=root/name;folder.mkdir()
        (folder/'plan.json').write_text(json.dumps({'case_id':'CASE','source_path':'/sources/chapter.xml','blocks':[{'index':1}]}))
    (tmp_path/'out').mkdir()
    (tmp_path/'out/current.json').write_text('{"step3a":{"CASE":"complete"}}')
    monkeypatch.setattr(V,'ROOT',tmp_path)
    monkeypatch.setattr(V,'render',lambda folder, prefix='':folder.name)
    os.utime(root/'prepared/plan.json',(2000000000,2000000000))
    assert current_folder(tmp_path,'CASE').name == 'complete'
    assert '>prepared<' in V.panel('CASE')
    select(tmp_path,'CASE','prepared')
    assert '>prepared<' in V.panel('CASE')
    assert current_folder(tmp_path,'OTHER') is None
    (root/'prepared/plan.json').unlink()
    with pytest.raises(FileNotFoundError):
        current_folder(tmp_path,'CASE')


def test_missing_index_and_mismatched_case_fail_instead_of_falling_back(tmp_path):
    with pytest.raises(FileNotFoundError):
        current_folder(tmp_path,'CASE')
    folder=tmp_path/'runs/step3a/CASE/batch';folder.mkdir(parents=True)
    (folder/'plan.json').write_text('{"case_id":"OTHER"}')
    (tmp_path/'out').mkdir()
    (tmp_path/'out/current.json').write_text('{"step3a":{"CASE":"batch"}}')
    with pytest.raises(ValueError,match='different case'):
        current_folder(tmp_path,'CASE')


def test_archive_preserves_raw_result_and_selection(tmp_path):
    source=tmp_path/'source';prepared=tmp_path/'prepared';destination=tmp_path/'official'
    for folder in [source,prepared]:
        folder.mkdir();(folder/'case-input.json').write_text('{"id":"CASE"}')
        (folder/'management.xml').write_text('<sec/>');(folder/'source-map.json').write_text('{}')
    (source/'plan.json').write_text('{"blocks":[{"index":1,"source_id":"N1"}]}')
    (prepared/'plan.json').write_text(json.dumps({'case_id':'CASE','blocks':[{'index':1,'source_id':'N1','request_sha256':'old','estimated_request_tokens':1,'reservation_usd':1}]}))
    section=source/'01';section.mkdir()
    response='{"choices":[{"finish_reason":"stop","message":{"content":"original answer"}}]}'
    (section/'response.json').write_text(response);(section/'request.json').write_text('{"messages":[]}')
    original='{"selected_roots":["N1"],"interpretation":"human transcription"}'
    (section/'selection.json').write_text(original)
    archive(source,prepared,destination)
    assert (destination/'01/response.json').read_text()==response
    assert (destination/'01/selection.original.json').read_text()==original
    assert (source/'01/selection.json').read_text()==original
    assert json.loads((destination/'01/selection.json').read_text())['selected_node_ids']==['N1']
    assert json.loads((destination/'plan.json').read_text())['state']=='imported_completed'

def test_completed_batch_recovery_does_not_rewrite_files(tmp_path):
    from aitx.step3.a.source_selection import recover
    (tmp_path/'plan.json').write_text('{}')
    raw='{"state":"complete", "blocks":[]}\n'
    (tmp_path/'execution.json').write_text(raw)
    before=(tmp_path/'execution.json').stat().st_mtime_ns
    assert recover(tmp_path)['state']=='complete'
    assert (tmp_path/'execution.json').read_text()==raw
    assert (tmp_path/'execution.json').stat().st_mtime_ns==before


def test_latest_run_uses_recorded_request_time_not_touched_old_plan(tmp_path, monkeypatch):
    from aitx.step3.a.results import latest_folder
    for name, at in [('old',100),('new',200)]:
        folder=tmp_path/'runs/step3a/CASE'/name
        (folder/'01').mkdir(parents=True)
        (folder/'plan.json').write_text('{"case_id":"CASE"}')
        (folder/'01/request.json').write_text(json.dumps({'at':at}))
    os.utime(tmp_path/'runs/step3a/CASE/old/plan.json',(2000000000,2000000000))
    assert latest_folder(tmp_path,'CASE').name=='new'
    assert latest_folder(tmp_path,'OTHER') is None


def test_latest_batch_is_independent_per_source(tmp_path, monkeypatch):
    from aitx.step3.a.results import latest_folders
    for name, source, at in [('a-old','a.xml',100),('a-new','a.xml',300),('b-only','b.xml',200)]:
        folder = tmp_path/'runs/step3a/CASE'/name
        (folder/'01').mkdir(parents=True)
        (folder/'plan.json').write_text(json.dumps({'case_id':'CASE','source_path':source}))
        (folder/'01/request.json').write_text(json.dumps({'at':at}))
    assert [p.name for p in latest_folders(tmp_path,'CASE')] == ['a-new','b-only']
    monkeypatch.setattr(V,'ROOT',tmp_path)
    monkeypatch.setattr(V,'render',lambda folder,prefix='':f'<p id="{prefix}original">{folder.name}</p>')
    page = V.panel('CASE')
    assert 'a-old' not in page and 'a-new' in page and 'b-only' in page
    assert 'chapter-1-original' in page and 'chapter-2-original' in page

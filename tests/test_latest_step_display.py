import json
import os
from scripts import build_viewer as B, step3b_view as T


def test_3b_uses_newest_published_result(tmp_path, monkeypatch):
    monkeypatch.setattr(T,'ROOT',tmp_path)
    monkeypatch.setattr(T,'saved_panel',lambda cid:'ledger')
    monkeypatch.setattr(T,'experiment_panel',lambda cid:'export')
    ledger=tmp_path/'out/step3/CASE.json';ledger.parent.mkdir(parents=True);ledger.write_text('{}')
    export=tmp_path/'out/3b/CASE/result.json';export.parent.mkdir(parents=True);export.write_text('{}')
    os.utime(ledger,(100,100));os.utime(export,(200,200))
    assert T.panel('CASE')=='export'
    os.utime(ledger,(300,300))
    assert T.panel('CASE')=='ledger'


def test_saved_sections_and_report_refresh_without_reanalysis(tmp_path, monkeypatch):
    monkeypatch.setattr(B,'OUT',tmp_path)
    (tmp_path/'step3').mkdir()
    p=tmp_path/'step3/CASE.json'
    p.write_text(json.dumps({'actions':[{'section':'off_label_expanded_access','label':'<saved>'}]}))
    assert '&lt;saved&gt;' in B.saved_section('CASE','c')
    assert '结果未知' in B.saved_section('CASE','e')
    (tmp_path/'step4').mkdir();report=tmp_path/'step4/CASE.md'
    report.write_text('# First report')
    assert 'First report' in B.saved_output('CASE',4)
    report.write_text('# New report <script>')
    assert 'New report &lt;script&gt;' in B.saved_output('CASE',4)
    assert '核查是否通过未知' in B.saved_output('CASE',5)
    (tmp_path/'step5').mkdir();(tmp_path/'step5/CASE.json').write_text('{"status":"fail"}')
    assert 'fail' in B.saved_output('CASE',5)

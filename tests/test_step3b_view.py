import copy
import json

from aitx import runmeta
from scripts import step3b_view as V


def test_saved_trial_view_preserves_branches_and_hides_details(tmp_path, monkeypatch):
    monkeypatch.setattr(V, 'ROOT', tmp_path)
    monkeypatch.setattr(runmeta, 'freshness', lambda *a, **kw: {'fresh': False, 'reasons': ['old code']})
    assert '尚无 Step 3 账本' in V.panel('TEST')
    evidence = {'id': 'e1', 'quote': 'Exact <source> criterion', 'source': {'id': 'NCT1'}, 'accessed_at': 1}
    row = {'kind': 'exclusion', 'result': 'unknown', 'requirement': 'No <therapy>',
           'patient_fact': None, 'note': 'not stated', 'applies_to': ['b1'], 'requirement_evidence': 'e1'}
    action = {'section': V.SECTION, 'nct': 'NCT1', 'title': '<script>unsafe</script>', 'label': 'Trial A',
              'study_type': 'interventional', 'url': 'https://clinicaltrials.gov/study/NCT1',
              'overall_status': 'RECRUITING', 'phases': [], 'requirements': [row],
              'status_by_branch': {'b1': {'status': 'conditional', 'reason': 'unknown fact'},
                                   'b2': {'status': 'not_applicable', 'reason': 'age excluded'}}}
    plan = {'analysed': ['NCT1'], 'ineligible': [], 'over_cap': [{'nct': 'NCT2'}],
            'excluded': [{'nct': 'NCT3', 'title': 'Closed trial', 'status': 'COMPLETED', 'reason': 'status', 'detail': 'COMPLETED'}],
            'searches': [{'queried_at': 1, 'query': {'gene': 'G'}, 'total_count': 3, 'url': 'https://example.org'}]}
    led = {'actions': [action], 'evidence': [evidence], 'branches': [
        {'id': 'b1', 'diagnosis': {'label': 'Disease A'}}, {'id': 'b2', 'diagnosis': {'label': 'Disease B'}}],
        'trial_searches': {'b1': plan}, '_meta': {'created_at': 1}, 'ok': True}
    path = tmp_path / 'out/step3/TEST.json'
    path.parent.mkdir(parents=True)
    original = json.dumps(led)
    path.write_text(original)
    page = V.panel('TEST')
    assert '<details class="trial-group"><summary><strong>干预试验</strong>' in page
    assert '<details class="trial-group" open' not in page
    for text in ('有条件 · 尚有未知', '不符合', 'Disease A', 'Disease B',
                 'NCT2', 'NCT3', 'COMPLETED', '历史结果', '检索已超过 1 天'):
        assert text in page
    for text in ('逐条标准与证据', '试验相关性与映射记录', 'Exact &lt;source&gt; criterion'):
        assert text not in page
    assert '<script>unsafe</script>' not in page
    assert path.read_text() == original
    # Missing trial search is unknown, distinct from a completed search with no hits.
    empty = copy.deepcopy(led)
    empty.update(actions=[], trial_searches={})
    path.write_text(json.dumps(empty))
    assert '不能认定没有相关试验' in V.panel('TEST')
    del empty['trial_searches']
    path.write_text(json.dumps(empty))
    import pytest
    with pytest.raises(KeyError):
        V.panel('TEST')

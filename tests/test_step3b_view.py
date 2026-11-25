import copy
import json

from aitx import runmeta
from scripts import step3b_view as V


def test_saved_trial_view_preserves_branches_and_hides_details(tmp_path, monkeypatch):
    monkeypatch.setattr(V, 'ROOT', tmp_path)
    monkeypatch.setattr(runmeta, 'freshness', lambda *a, **kw: {'fresh': False, 'reasons': ['old code']})
    assert '尚无 Step 3 账本' in V.saved_panel('TEST')
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
    page = V.saved_panel('TEST')
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
    assert '不能认定没有相关试验' in V.saved_panel('TEST')
    del empty['trial_searches']
    path.write_text(json.dumps(empty))
    import pytest
    with pytest.raises(KeyError):
        V.saved_panel('TEST')


def test_cohort_display_preserves_or_and_only_focuses_possible_scope():
    def row(scope, status, route='alternative', name='年龄条件', kind='age'):
        return {'scope': scope, 'status': status, 'route': route, 'prerequisite': name, 'kind': kind}
    adult = row('Part A', 'conflict', name='成人Part A年龄≥18')
    child = row('Part B', 'confirmed', name='儿童Part B年龄≥6且<18')
    adult_unknown = row('Part A', 'unknown', 'required', '成人治疗条件', 'medical')
    child_unknown = row('Part B', 'unknown', 'required', '儿童治疗条件', 'medical')
    common = row('共同', 'unknown', 'required', 'eGFR≥30', 'medical')
    original = [adult, child, adult_unknown, child_unknown, common]
    before = copy.deepcopy(original)
    result = V.cohort_display(original)
    assert V.cohort_label(result['preferred'][0]) == '儿童 Part B'
    assert result['inactive'] == [adult]
    assert child_unknown in result['focused'] and common in result['focused']
    assert adult_unknown not in result['focused'] and adult not in result['focused']
    assert child_unknown['status'] == common['status'] == 'unknown'
    assert original == before
    # Same rule works without a known trial ID and without Part A/B names.
    other = V.cohort_display([row('家属队列', 'conflict'), row('患者队列', 'unknown')])
    assert other['preferred'][0]['scope'] == '患者队列'
    assert other['preferred'][0]['status'] == 'unknown'
    # No evidence chooses a specific path when all alternatives remain unknown.
    assert V.cohort_display([row('甲队列', 'unknown'), row('乙队列', 'unknown')])['preferred'] == []


def test_experiment_page_does_not_render_formal_ledger(monkeypatch):
    monkeypatch.setattr(V, 'experiment_panel', lambda cid: '<div>experiment</div>')
    def unexpected_ledger_read(cid):
        raise AssertionError('experimental page must not render the formal ledger')
    monkeypatch.setattr(V, 'saved_panel', unexpected_ledger_read)
    assert V.panel('CASE') == '<div>experiment</div>'


def test_generic_export_and_view_keep_cases_separate(tmp_path, monkeypatch):
    import pytest
    from scripts.build_step3b_experiment_view import export
    monkeypatch.setattr(V, 'ROOT', tmp_path)
    assert '尚未运行新版' in V.panel('NOT-RUN')
    destination = tmp_path / 'out/3b'
    for case_id, known in [('CASE-A', '甲病例依据'), ('CASE-B', '乙病例依据')]:
        source = tmp_path / case_id
        trial = source / 'trials/NCT-NEW'
        trial.mkdir(parents=True)
        (trial / 'eligibility.txt').write_text('Original <criterion>')
        records = {
            'patient': {'id': case_id, 'patient': {'clinical_context': known}},
            'candidates': [{'nct_id': 'NCT-NEW', 'display_name': '新研究', 'title': 'Trial',
                            'status': 'RECRUITING', 'study_type': 'INTERVENTIONAL',
                            'decision': 'candidate', 'matched_evidence': known,
                            'missing_information': '用药史未知', 'llm_hard_conflicts': []}],
            'excluded': [{'nct_id': 'NCT-OUT', 'title': 'Excluded', 'reason': 'Age',
                          'raw_conflicts': [{'trial_rule_quote': 'Adult only',
                                             'patient_fact_quote': 'Child'}]}],
            'counts': {'api_query_returned_with_duplicates': 3, 'api_unique': 2,
                       'sent_to_deepseek': 1, 'final_candidates': 1},
            'manual-conflict-review': [],
            'studies': {'NCT-NEW': {'protocolSection': {
                'designModule': {'studyType': 'INTERVENTIONAL', 'designInfo': {'primaryPurpose': 'TREATMENT'}},
                'identificationModule': {'briefTitle': 'Trial'},
                'armsInterventionsModule': {'interventions': [{'type': 'DRUG', 'name': 'Therapy'}]}}}},
        }
        for name, record in records.items():
            (source / f'{name}.json').write_text(json.dumps(record))
        original = (source / 'candidates.json').read_bytes()
        export(source, destination)
        page = V.panel(case_id)
        assert known in page and '用药史未知' in page
        assert '未评估' not in page and '1</strong><span>项治疗性干预研究' in page
        assert 'Original &lt;criterion&gt;' in page
        assert 'Adult only' in page and 'Child' in page
        assert 'data-decision="candidate"' in page
        assert '正式账本' not in page and '已保存结果' not in page
        assert (source / 'candidates.json').read_bytes() == original
    assert '乙病例依据' not in V.panel('CASE-A')
    assert '甲病例依据' not in V.panel('CASE-B')
    path = destination / 'CASE-A' / 'result.json'
    data = json.loads(path.read_text())
    data['case_id'] = 'CASE-B'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='another case'):
        V.panel('CASE-A')
    data['case_id'] = 'CASE-A'
    del data['counts']
    path.write_text(json.dumps(data))
    with pytest.raises(KeyError):
        V.panel('CASE-A')


def test_pathway_classification_and_priority_are_deterministic():
    from scripts.build_step3b_experiment_view import pathway, priority_key
    def protocol(kind, purpose, interventions):
        return {'designModule': {'studyType': kind, 'designInfo': {'primaryPurpose': purpose}},
                'identificationModule': {'briefTitle': 'Trial'},
                'armsInterventionsModule': {'interventions': interventions}}
    candidate = {'prerequisites': []}
    facts = {'known_conditions': ['diagnosis', 'age'], 'pending_prerequisites': ['open cohort'],
             'cohort_note': 'Pediatric expansion; opening unknown', 'target_path_supported': True}
    gene = pathway(candidate, protocol('INTERVENTIONAL', 'TREATMENT', [{'type': 'GENETIC', 'name': 'AAV'}]), facts)
    assert gene['category_rank'] == 0 and gene['therapeutic']
    assert '需确认开放队列' in gene['status']
    assert pathway(candidate, protocol('INTERVENTIONAL', 'DIAGNOSTIC', [{'type': 'GENETIC', 'name': 'Assay'}]), facts)['category_rank'] == 2
    assert pathway(candidate, protocol('INTERVENTIONAL', 'OTHER', [{'type': 'DEVICE', 'name': 'Arginine Test System'}]), facts)['category_rank'] == 2
    observed = pathway(candidate, protocol('OBSERVATIONAL', None, [{'type': 'DRUG', 'name': 'Drug follow-up'}]), facts)
    assert observed['category_rank'] == 3 and not observed['therapeutic']
    missing = pathway(candidate, protocol('INTERVENTIONAL', 'TREATMENT', [{'type': 'DRUG', 'name': 'Therapy'}]), None)
    assert missing['known_conditions'] is None and missing['pending_prerequisites'] is None
    rows = [
        {'nct_id': 'diagnostic', 'pathway': {**gene, 'category_rank': 2}},
        {'nct_id': 'more_pending', 'pathway': {**gene, 'pending_prerequisites': ['a', 'b']}},
        {'nct_id': 'fewer_known', 'pathway': {**gene, 'known_conditions': ['age']}},
        {'nct_id': 'best', 'pathway': gene},
        {'nct_id': 'unreviewed', 'pathway': {**gene, 'known_conditions': None, 'pending_prerequisites': None}},
    ]
    expected = ['best', 'more_pending', 'fewer_known', 'unreviewed', 'diagnostic']
    assert [r['nct_id'] for r in sorted(rows, key=priority_key)] == expected
    assert [r['nct_id'] for r in sorted(reversed(rows), key=priority_key)] == expected

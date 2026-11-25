import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from aitx.step3.a import source_selection as S
from aitx.viewer import step3a as V

ROOT = Path(__file__).resolve().parents[1]
XML = ROOT/'.cache/datasets/genereviews_book/2026-11-03/chapters/otc-def.nxml'
CASE = {'id':'TEST','patient':{'genotype':[{'gene':'G'}],'clinical_context':'Age and current stage unknown.'}}


@pytest.fixture
def prepared(tmp_path):
    xml=tmp_path/'source.xml'
    xml.write_text('''<book><body><sec id="g.Management"><title>Management</title><p>Intro</p>
    <sec id="g.Treatment"><title>Treatment</title><table-wrap id="t1"><label>Table 1</label><caption><p>Full title</p></caption><table><thead><tr><th>Treatment</th><th>Considerations</th></tr></thead><tbody><tr><td rowspan="2">Parent therapy</td><td><list><list-item><p>First paragraph.</p><p>Second paragraph.</p><list><list-item><p>Nested dose</p></list-item></list></list-item></list><xref rid="fn1">1</xref></td></tr><tr><td>Exception</td></tr></tbody></table><table-wrap-foot><fn id="fn1"><p>Footnote caution</p></fn></table-wrap-foot></table-wrap></sec>
    <sec><title>Avoid</title><p>No fasting.</p></sec></sec></body></book>''')
    out=tmp_path/'out';plan=S.prepare(CASE,xml,out)
    return out,plan,json.loads((out/'source-map.json').read_text())


def test_roundtrip_and_complete_partition(prepared):
    out,plan,mapping=prepared
    annotated=ET.fromstring((out/'annotated-management.xml').read_text())
    for n in annotated.iter():del n.attrib['source-node-id']
    assert ET.tostring(annotated)==ET.tostring(ET.fromstring((out/'management.xml').read_text()))
    requested=[s for b in plan['blocks'] for s in b['node_ids']]
    assert len(requested)==len(set(requested))
    expected={n.attrib['source-node-id'] for sec in ET.fromstring((out/'annotated-management.xml').read_text()).findall('sec') for n in sec.iter()}
    assert set(requested)==expected
    assert [mapping[s]['text'] for s in plan['management_intro_ids']]==['Intro']


def test_recursive_split_keeps_parent_content_and_tail_section_order():
    root=ET.fromstring('<sec><title>M</title><sec><title>T</title><p>before</p><sec><title>C</title><p>'+('x'*400)+'</p><sec><title>D</title><p>deep</p></sec></sec><p>after</p></sec></sec>')
    for i,n in enumerate(root.iter()):n.set('source-node-id',f'N{i:04d}')
    blocks=S.split_sections(root,100,max_block_tokens=100)
    assert len(blocks)>=3
    direct=ET.fromstring(blocks[0]['xml'])
    assert [p.text for p in direct.findall('p')]==['before','after']
    assert any(b['status']=='oversize_unsplittable' for b in blocks)
    assert any('deep' in b['xml'] for b in blocks)
    ids=[s for b in blocks for s in b['node_ids']]
    assert len(ids)==len(set(ids))


def test_exact_threshold_does_not_split():
    root=ET.fromstring('<sec><title>M</title><sec><title>A</title><p>x</p><sec><title>B</title><p>y</p></sec></sec></sec>')
    for i,n in enumerate(root.iter()):n.set('source-node-id',f'N{i:04d}')
    size=S.estimate_tokens(ET.tostring(root.find('sec'),encoding='unicode'))
    assert len(S.split_sections(root,size))==1
    assert len(S.split_sections(root,size-1))==2


def test_hydration_preserves_source_and_table_context(prepared):
    out,plan,m=prepared
    sid=next(k for k,v in m.items() if v['tag']=='p' and v['text']=='First paragraph.')
    result=S.hydrate({'selected_node_ids':[sid],'references':[]},m,set(plan['blocks'][0]['node_ids']))
    rec=result['records'][0]
    assert rec['xml']==m[sid]['xml']
    assert m[rec['context_id']]['tag']=='table-wrap'
    assert 'Footnote caution' in m[rec['context_id']]['xml']
    assert 'rowspan="2"' in m[rec['context_id']]['xml']
    assert rec['source_references'][0]['target_id'] in m
    assert result['selected_node_ids']==[sid] # Context is not promoted to selected.


@pytest.mark.parametrize('selection',[{}, {'selected_node_ids':['N9999'],'references':[]}, {'selected_node_ids':'N0001','references':[]}, {'selected_node_ids':[],'references':[{'from_id':'N0001','to_id':'N0002'}]}])
def test_invalid_result_stops(prepared,selection):
    _,p,m=prepared
    with pytest.raises(ValueError):S.hydrate(selection,m,set(p['blocks'][0]['node_ids']))


def test_parent_selection_subsumes_child_without_altering_raw_ids(prepared):
    _,p,m=prepared
    parent=p['blocks'][0]['source_id'];child=p['blocks'][0]['node_ids'][-1]
    result=S.hydrate({'selected_node_ids':[parent,child],'references':[]},m,set(p['blocks'][0]['node_ids']))
    assert len(result['records'])==1
    assert result['selected_node_ids']==[parent,child]


def mock_runtime(monkeypatch):
    monkeypatch.setattr(S.peak,'guard',lambda:None)
    monkeypatch.setattr(S.peak,'check_before_call',lambda:None)
    monkeypatch.setattr(S.budget,'spent_today',lambda:0)
    monkeypatch.setattr(S.budget,'cap',lambda:1)
    monkeypatch.setattr(S.llm,'config',lambda:{'model':'deepseek-flash','base_url':'https://api.deepseek.com'})


def test_one_call_per_block_and_no_retry(prepared,monkeypatch):
    out,plan,_=prepared;mock_runtime(monkeypatch);calls=[]
    def chat(messages,**params):
        calls.append((messages,params))
        return {'model':'mock','choices':[{'finish_reason':'stop','message':{'content':'{"selected_node_ids":[],"references":[]}'}}], 'usage':{'prompt_tokens':10,'completion_tokens':5}}
    monkeypatch.setattr(S.llm,'chat',chat)
    result=S.run(out,max_cost_usd=1)
    assert len(calls)==len(plan['blocks'])==2
    assert all(p==S.PARAMS for _,p in calls)
    assert result['state']=='complete'
    with pytest.raises(FileExistsError):S.run(out,max_cost_usd=1)
    assert len(calls)==2
    page=V.render(out)
    assert '模型未选择节点' in page and '原文仍完整保存' in page


@pytest.mark.parametrize('finish,content',[('length','{'),('stop','not JSON'),('stop','{"selected_node_ids":["N9999"],"references":[]}')])
def test_bad_response_is_saved_stops_without_retry(prepared,monkeypatch,finish,content):
    out,_,_=prepared;mock_runtime(monkeypatch);calls=[]
    def chat(*a,**k):
        calls.append(1)
        return {'choices':[{'finish_reason':finish,'message':{'content':content}}],'usage':{'prompt_tokens':1,'completion_tokens':1}}
    monkeypatch.setattr(S.llm,'chat',chat)
    with pytest.raises(ValueError):S.run(out,max_cost_usd=1)
    assert len(calls)==1
    assert (out/'01/response.json').exists()
    assert not (out/'01/selection.json').exists()
    assert '尚无通过解析的节点结果' in V.render(out)


def test_budget_blocks_before_request(prepared,monkeypatch):
    out,_,_=prepared;mock_runtime(monkeypatch)
    monkeypatch.setattr(S.llm,'chat',lambda *a,**k:pytest.fail('No paid request allowed'))
    with pytest.raises(S.budget.OverBudget):S.run(out,max_cost_usd=.000001)
    assert not (out/'execution.json').exists()


def test_missing_context_and_existing_output_stop(prepared,tmp_path):
    out,_,_=prepared
    bad=copy.deepcopy(CASE);del bad['patient']['clinical_context']
    with pytest.raises(KeyError):S.prepare(bad,tmp_path/'source.xml',tmp_path/'bad')
    with pytest.raises(FileExistsError):S.prepare(CASE,tmp_path/'source.xml',out)


def test_viewer_retains_original_tables_and_escapes_text(prepared):
    out,_,_=prepared
    page=V.render(out)
    for text in ['Full title','First paragraph.','Second paragraph.','Nested dose','Exception','Footnote caution','rowspan="2"','尚未调用模型']:
        assert text in page
    assert '<script' not in page


@pytest.mark.skipif(not XML.exists() or not (ROOT/"runs/step3a/PRAC-OTC/PRAC-OTC/source-map.original.json").exists(), reason="Requires local OTC XML and historical snapshot")
def test_otc_actual_partition_and_historical_source_ids(tmp_path):
    cases=json.loads((ROOT/'data/cases/practice/official_examples.json').read_text())
    case=next(c for c in cases if c['id']=='PRAC-OTC')
    out=tmp_path/'otc';plan=S.prepare(case,XML,out)
    mapping=json.loads((out/'source-map.json').read_text())
    assert len(plan['blocks'])==12
    assert all(b['status']=='ready' for b in plan['blocks'])
    expected=json.loads((ROOT/'runs/step3a/PRAC-OTC/PRAC-OTC/source-map.original.json').read_text())
    assert {k:(v['xpath'],v['text']) for k,v in mapping.items()}=={k:(v['xpath'],v['text']) for k,v in expected.items()}
    blocks=[ET.fromstring((out/f'{i:02d}/section.xml').read_text()) for i in range(1,13)]
    ids=[n.attrib['source-node-id'] for b in blocks for n in b.iter()]
    assert len(ids)==len(set(ids))==615
    assert '让他在一个负责任的监护人的角度周全考虑。' in (out/'06/planned-request.json').read_text()
    original=ET.fromstring((out/'management.xml').read_text())
    for tag in ('table-wrap','tr','td','fn','list-item'):
        assert sum(len(list(b.iter(tag))) for b in blocks)==len(list(original.iter(tag)))


def test_partial_parent_selection_does_not_select_separately_called_children():
    xml=ET.fromstring('<sec source-node-id="N0001"><title source-node-id="N0002">Parent</title><p source-node-id="N0003">Direct</p><sec source-node-id="N0004"><title source-node-id="N0005">Child</title><p source-node-id="N0006">Not submitted in parent call</p></sec></sec>')
    mapping={}
    def index(n,path):
        sid=n.attrib.pop('source-node-id');counts={}
        for c in n:
            counts[c.tag]=counts.get(c.tag,0)+1
            index(c,f'{path}/{c.tag}[{counts[c.tag]}]')
        mapping[sid]=dict(xpath=path,tag=n.tag,section=['Parent'],text=''.join(n.itertext()),xml=ET.tostring(n,encoding='unicode'),attributes=dict(n.attrib))
    index(xml,'/sec[1]')
    out=S.hydrate({'selected_node_ids':['N0001'],'references':[]},mapping,{'N0001','N0002','N0003'})
    assert 'Direct' in out['records'][0]['text']
    assert 'Not submitted' not in out['records'][0]['text']
    assert '<sec>' not in out['records'][0]['xml'].replace('<sec>', '',1)


@pytest.mark.skipif(not (ROOT/"runs/step3a/PRAC-OTC/PRAC-OTC/plan.json").exists(), reason="Requires saved local OTC output")
def test_integrated_case_keeps_steps_1_2_and_embeds_step3_tabs():
    from scripts import build_viewer as B
    html=B.render_page('cases/PRAC-OTC.html')
    assert html.count("class='chain'") == 1
    assert html.index("class='chain'") < html.index('<h1>')
    assert html.index("class='chain'") < html.index("id='patient-background'") < html.index("data-main-step='1'")
    background = B.patient_background({'id': 'TEST', 'steps': {
        1: {'variants': [{'gene': 'G', 'variant_cdna': 'c.1A>G', 'variant_protein': 'p.X'}]},
        2: {'patient_facts': {'age': {'months': None}, 'sex': {'value': 'unknown'}}}}}, '<patient original>')
    assert '年龄：未知' in background and '性别：未知' in background
    assert '&lt;patient original&gt;' in background
    for target in ('variant', 'disease', 'step3', 'step4', 'step5'):
        assert f"href='#{target}'" in html
    assert "href='#board'" not in html
    assert 'Step 1 变异事实' in html and 'Step 2 结论' in html
    assert html.index("id='step3'") > html.index("id='disease'")
    for x in 'abcde':
        assert f"id='tab-3{x}'" in html
        assert f"id='panel-3{x}'" in html
    assert '<iframe' not in html
    assert '病例相关原文筛选' not in html # No second full-page header inside the case.
    assert '完整 Management 原文' in html


@pytest.mark.parametrize('fail_first', [False, True])
def test_four_concurrent_calls_and_failure_stops_next_batch(prepared, monkeypatch, fail_first):
    import shutil
    import threading
    out, plan, _ = prepared
    mock_runtime(monkeypatch)
    for index in range(3, 7):
        shutil.copytree(out/'01', out/f'{index:02d}')
        block = copy.deepcopy(plan['blocks'][0])
        block['index'] = index
        plan['blocks'].append(block)
    S.dump(out/'plan.json', plan)
    barrier = threading.Barrier(4, timeout=5)
    lock = threading.Lock()
    calls = []
    def chat(*args, **kwargs):
        with lock:
            calls.append(len(calls)+1)
            number = calls[-1]
        if number <= 4:
            barrier.wait()
        content = 'not JSON' if fail_first and number == 1 else '{"selected_node_ids":[],"references":[]}'
        return {'choices':[{'finish_reason':'stop','message':{'content':content}}],
                'usage':{'prompt_tokens':1,'completion_tokens':1}}
    monkeypatch.setattr(S.llm, 'chat', chat)
    if fail_first:
        with pytest.raises(ValueError):
            S.run(out, max_cost_usd=1, concurrency=4)
        assert len(calls) == 4
        assert all((out/f'{i:02d}/response.json').exists() for i in range(1,5))
        assert not (out/'05/request.json').exists()
    else:
        result = S.run(out, max_cost_usd=1, concurrency=4)
        assert len(calls) == 6 and result['state'] == 'complete'
    execution = json.loads((out/'execution.json').read_text())
    assert execution['accounted_usd'] == pytest.approx(sum(b['accounted_usd'] for b in execution['blocks']))


def test_hydration_accepts_inline_xml_tail_without_losing_text(prepared):
    _, plan, mapping = prepared
    sid = next(k for k, v in mapping.items() if v['tag'] == 'xref')
    target = next(k for k, v in mapping.items() if v['tag'] == 'fn')
    mapping[sid]['xml'] += ' text after the inline reference.'
    result = S.hydrate({'selected_node_ids':[sid], 'references':[{'from_id':sid,'to_id':target}]},
                       mapping, set(plan['blocks'][0]['node_ids']))
    assert result['selected_node_ids'] == [sid]
    assert result['records'][0]['text'] == mapping[sid]['text']
    assert result['records'][0]['xml'].endswith(' text after the inline reference.')
    assert result['references'] == [{'from_id':sid,'to_id':target}]


def test_offline_recovery_then_resume_only_unstarted_block(prepared, monkeypatch):
    out, plan, _ = prepared
    mock_runtime(monkeypatch)
    calls = []
    def chat(*args, **kwargs):
        calls.append(1)
        return {'choices':[{'finish_reason':'stop','message':{'content':'{"selected_node_ids":[],"references":[]}'}}],
                'usage':{'prompt_tokens':10,'completion_tokens':5}}
    monkeypatch.setattr(S.llm, 'chat', chat)
    original = S.hydrate
    def broken(*args):
        raise ET.ParseError('simulated local parser failure')
    monkeypatch.setattr(S, 'hydrate', broken)
    with pytest.raises(ET.ParseError):
        S.run(out, max_cost_usd=1)
    raw = (out/'01/response.json').read_bytes()
    execution = json.loads((out/'execution.json').read_text())
    assert execution['state'] == 'failed' and 'parser failure' in execution['error']
    monkeypatch.setattr(S, 'hydrate', original)
    monkeypatch.setattr(S.llm, 'chat', lambda *a,**k: pytest.fail('Offline recovery must not call model'))
    recovered = S.recover(out)
    assert recovered['state'] == 'incomplete' and recovered['remaining_blocks'] == [2]
    assert (out/'01/response.json').read_bytes() == raw
    assert '当前批次' in V.render(out) and '已完成 1/2' in V.render(out)
    monkeypatch.setattr(S.llm, 'chat', chat)
    result = S.run(out, max_cost_usd=1, concurrency=4, resume=True)
    assert len(calls) == 2 and result['state'] == 'complete'
    assert (out/'01/response.json').read_bytes() == raw
    assert '执行完成，待内容审核' in V.render(out)


def test_no_response_is_not_automatically_retried(prepared, monkeypatch):
    out, _, _ = prepared
    mock_runtime(monkeypatch)
    calls = []
    def unavailable(*args, **kwargs):
        calls.append(1)
        raise ConnectionError('lost response')
    monkeypatch.setattr(S.llm, 'chat', unavailable)
    with pytest.raises(ConnectionError):
        S.run(out, max_cost_usd=1)
    with pytest.raises(ValueError, match='no response'):
        S.run(out, max_cost_usd=1, resume=True)
    assert len(calls) == 1


def test_structural_split_keeps_tables_and_assigns_each_body_node_once(prepared):
    out, _, mapping = prepared
    root = ET.fromstring((out/'annotated-management.xml').read_text())
    blocks = S.split_sections(root, threshold=100)
    body_ids = [sid for b in blocks for sid in (b['selectable_ids'] if 'selectable_ids' in b else b['node_ids'])
                if mapping[sid]['tag'] not in ('sec', 'title')]
    expected = [n.attrib['source-node-id'] for sec in root.findall('sec') for n in sec.iter()
                if n.tag not in ('sec', 'title')]
    assert body_ids == expected
    for b in blocks:
        if 'selectable_ids' in b:
            assert set(b['selectable_ids']).isdisjoint(b['context_ids'])
    table = next(root.iter('table-wrap'))
    tables = [t for b in blocks for t in ET.fromstring(b['xml']).iter('table-wrap')]
    assert len(tables) == 1
    assert ET.tostring(tables[0]) == ET.tostring(table)


def test_context_is_not_selectable_but_remains_a_reference_target(prepared):
    _, plan, mapping = prepared
    sid = next(k for k,v in mapping.items() if v['tag']=='xref')
    target = next(k for k,v in mapping.items() if v['tag']=='fn')
    block = dict(plan['blocks'][0], selectable_ids=[sid], context_ids=[target])
    selected = {'selected_node_ids':[sid], 'references':[{'from_id':sid,'to_id':target}]}
    assert S.hydrate_block(selected, mapping, block)['references'] == selected['references']
    with pytest.raises(ValueError, match='read-only context'):
        S.hydrate_block({'selected_node_ids':[target],'references':[]}, mapping, block)


def test_highlighting_keeps_unselected_rows_and_original_rowspan(prepared):
    out, _, mapping = prepared
    rows = [sid for sid,v in mapping.items() if v['tag']=='tr']
    S.dump(out/'01/selection.json', {'selected_node_ids':[rows[1]],'references':[]})
    page = V.render(out, prefix='chapter-1-')
    assert f'id="chapter-1-src-{rows[1]}" class="selected-source"' in page
    assert f'id="chapter-1-src-{rows[2]}" class="selected-source"' not in page
    assert 'rowspan="2"' in page and 'Exception' in page
    assert f'href="#chapter-1-src-{rows[1]}"' in page
    assert 'id="chapter-1-original"' in page


def test_xml_reference_recovery_uses_rid_not_the_model_target(prepared):
    _, plan, mapping = prepared
    xref = next(k for k,v in mapping.items() if v['tag']=='xref')
    target = next(k for k,v in mapping.items() if v['tag']=='fn')
    model = {'selected_node_ids':[xref],'references':[{'from_id':xref,'to_id':xref}]}
    before = copy.deepcopy(model)
    result = S.hydrate_xml_references(model, mapping, plan['blocks'][0])
    assert model == before
    assert result['selected_node_ids'] == [xref]
    assert result['references'] == [{'from_id':xref,'to_id':target}]
    assert result['model_references'] == before['references']
    assert result['xml_references'] == [dict(from_id=xref, xref_id=xref, rid='fn1',
                                           target_id=target, target_scope='in_request')]
    with pytest.raises(ValueError):
        S.hydrate_block(model, mapping, plan['blocks'][0])  # Legacy path stays strict.


def test_xml_reference_recovery_preserves_out_of_map_citations(prepared):
    _, plan, mapping = prepared
    xref = next(k for k,v in mapping.items() if v['tag']=='xref')
    target = next(k for k,v in mapping.items() if v['tag']=='fn')
    mapping = copy.deepcopy(mapping)
    del mapping[target]['attributes']['id']
    result = S.hydrate_xml_references({'selected_node_ids':[xref],'references':[]},mapping,plan['blocks'][0])
    assert result['references'] == []
    assert result['xml_references'][0]['rid'] == 'fn1'
    assert result['xml_references'][0]['target_id'] is None
    assert result['xml_references'][0]['target_scope'] == 'outside_source_map'
    assert result['records'][0]['xml'] == mapping[xref]['xml']


def test_xml_reference_recovery_does_not_accept_invalid_or_context_selection(prepared):
    _,plan,mapping=prepared
    block=dict(plan['blocks'][0],selectable_ids=[plan['blocks'][0]['node_ids'][-1]])
    for sid in ['N9999',block['source_id']]:
        with pytest.raises(ValueError):
            S.hydrate_xml_references({'selected_node_ids':[sid],'references':[]},mapping,block)


def test_xml_reference_recovery_does_not_import_unsubmitted_links(prepared):
    _,plan,mapping=prepared
    xref=next(k for k,v in mapping.items() if v['tag']=='xref')
    target=next(k for k,v in mapping.items() if v['tag']=='fn')
    block=copy.deepcopy(plan['blocks'][0])
    block['node_ids'].remove(target)
    result=S.hydrate_xml_references({'selected_node_ids':[xref],'references':[]},mapping,block)
    assert result['references']==[]
    assert result['xml_references'][0]['target_scope']=='outside_request'
    assert result['xml_references'][0]['target_id']==target
    block['node_ids'].remove(xref)
    result=S.hydrate_xml_references({'selected_node_ids':[block['source_id']],'references':[]},mapping,block)
    assert result['xml_references']==[]

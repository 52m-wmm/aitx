"""Read-only Step 3a source-selection Viewer: self-contained static HTML, no API calls."""
from __future__ import annotations
from html import escape as esc
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from aitx.step3.a import results
ROOT = Path(__file__).resolve().parents[2]

def render_xml(node, ids, prefix='src-', targets=None, selected=frozenset()):
    """Safe JATS rendering; all original text/tails retained, never execute XML markup."""
    sid = ids[id(node)]
    attrs = f' id="{prefix}{sid}"'
    tags = {'sec':'section','title':'h3','p':'p','list':'ul','list-item':'li',
            'bold':'strong','italic':'em','sup':'sup','sub':'sub','table':'table',
            'thead':'thead','tbody':'tbody','tr':'tr','td':'td','th':'th','label':'strong',
            'fn':'div','table-wrap':'div','caption':'div','table-wrap-foot':'div'}
    tag = tags.get(node.tag, 'span')
    marked = sid in selected and node.tag != 'sec'
    classes = (['table'] if node.tag == 'table-wrap' else []) + (['selected-source'] if marked else [])
    if classes:
        attrs += ' class="'+' '.join(classes)+'"'
    if node.tag in ('td','th'):
        for k in ('rowspan','colspan'):
            if k in node.attrib:
                attrs += f' {k}="{int(node.attrib[k])}"'
    if node.tag == 'xref' and targets is not None and node.attrib.get('rid') in targets:
        tag = 'a'
        attrs += ' href="#'+prefix+targets[node.attrib['rid']]+'"'
    text = esc(node.text or '')
    inner = ''.join(render_xml(c, ids, prefix, targets, selected) + esc(c.tail or '') for c in node)
    return f'<{tag}{attrs}>{text}{inner}</{tag}>'


def details(title, text):
    return '<details><summary>'+esc(title)+'</summary><pre>'+esc(text)+'</pre></details>'


def render(folder: Path, prefix='') -> str:
    plan = json.loads((folder/'plan.json').read_text())
    mapping = json.loads((folder/'source-map.json').read_text())
    root = ET.fromstring((folder/'management.xml').read_text())
    elements = dict(zip(mapping, root.iter()))
    if len(elements) != len(mapping) or len(list(root.iter())) != len(mapping):
        raise ValueError('Source map/XML mismatch')
    for sid,node in elements.items():
        if node.tag != mapping[sid]['tag'] or ''.join(node.itertext()) != mapping[sid]['text']:
            raise ValueError('Source map/XML text mismatch')
    ids = {id(n):s for s,n in elements.items()}
    execution_path = folder/'execution.json'
    execution = json.loads(execution_path.read_text()) if execution_path.exists() else None
    entries = {b['index']: b for b in execution['blocks']} if execution is not None else {}
    state = execution['state'] if execution is not None else plan['state']
    labels = {'prepared_not_run':'已准备，未执行', 'running':'运行中', 'incomplete':'未完成',
              'failed':'失败', 'complete':'执行完成，待内容审核', 'imported_completed':'历史审核结果导入'}
    html = ['<div class="card"><strong>当前批次：'+esc(folder.name)+'</strong><p>状态：'+esc(labels.get(state, state))+'</p>']
    html.append('<p>来源章节：'+esc(Path(plan['source_path']).name)+'</p>')
    if execution is not None:
        complete = sum(e['state']=='complete' for e in entries.values())
        html.append(f'<p>已完成 {complete}/{len(plan["blocks"])} 块 · 尚未发出请求 {len(plan["blocks"])-len(entries)} 块</p>')
        if 'error' in execution:
            html.append('<p class="unknown">失败原因：'+esc(execution['error'])+'</p>')
        html.append('<p>预算计入（含未结算预留）：$'+f'{execution["accounted_usd"]:.6f}'+'</p>')
    html.append('<p>按来源章节自动展示最新运行批次；未完成时显示当前进度，不自动切回旧结果。执行完成不等于医学正确性审核通过。</p></div>')
    selected_ids = set()
    for b in plan['blocks']:
        i = b['index'];d = folder/f'{i:02d}'
        title = ' / '.join(b['section'])
        html.append(f'<article id="{prefix}block-{i}"><h2>{i}. {esc(title)}</h2>')
        block_state = entries[i]['state'] if i in entries else ('未执行' if execution is not None else b['status'])
        html.append(f'<p>XML 约 {b["estimated_xml_tokens"]:,} tokens · {esc(b["kind"])} · {esc(block_state)}</p>')
        if i in entries and 'error' in entries[i]:
            html.append('<p class="unknown">'+esc(entries[i]['error'])+'</p>')
        if (d/'selection.json').exists():
            selection = json.loads((d/'selection.json').read_text())
            selected = selection['selected_node_ids']
            selected_ids.update(s for s in b['node_ids'] if any(
                mapping[s]['xpath'] == mapping[t]['xpath'] or mapping[s]['xpath'].startswith(mapping[t]['xpath'] + '/')
                for t in selected))
            html.append('<p>选中来源节点：'+str(len(selected))+'（不是治疗数量或医学召回率）</p>')
            if not selected:
                html.append('<p>模型未选择节点；原文仍完整保存在下方。</p>')
            for sid in selected:
                src = mapping[sid]
                html.append('<p><a href="#'+prefix+'src-'+sid+'">'+esc(sid+' · '+' '.join(src['text'].split())[:150])+'</a></p>')
                html.append(details('来源 XPath',src['xpath']))
            html.append(details('结构化筛选结果',json.dumps(selection,ensure_ascii=False,indent=2)))
        elif (d/'response.json').exists():
            html.append('<p class="unknown">响应已保存，尚无通过解析的节点结果。不能视为空选择。</p>')
        else:
            html.append('<p class="unknown">'+('请求已开始但尚无保存的响应，结果未知' if i in entries else '尚未调用模型 · 结果未知')+'</p>')
        if (d/'response.json').exists():
            response = json.loads((d/'response.json').read_text());ch = response['choices'][0]
            html.append(details('模型原始输出（未经修复）',ch['message']['content']))
            html.append(details('Token 与结束状态',json.dumps(dict(usage=response['usage'],finish_reason=ch['finish_reason']),ensure_ascii=False,indent=2)))
        req = d/('request.json' if (d/'request.json').exists() else 'planned-request.json')
        if req.exists():
            html.append(details('实际请求' if (d/'request.json').exists() else '待执行请求',req.read_text()))
        html.append(details('本次完整输入 XML',(d/'section.xml').read_text()))
        html.append('</article>')
    html.append('<article id="'+prefix+'original"><h2>完整 Management 原文</h2><p>以下全部来自 XML，包括未选中内容；浅绿色标出模型选中部分，不代表已确认适用。点击上方节点链接可定位；表格完整显示，保留合并单元格、表头与脚注。总体管理段落保留在此，不推断适用性。</p>')
    html.append(render_xml(root,ids,prefix=prefix+'src-',selected=selected_ids,targets={n.attrib['id']:s for s,n in elements.items() if 'id' in n.attrib}))
    html.append(details('原始 XML',(folder/'management.xml').read_text()))
    html.append('</article>')
    return '\n'.join(html)


def latest_folder(case_id: str) -> Path | None:
    return results.latest_folder(ROOT, case_id)


def latest_folders(case_id: str) -> list[Path]:
    return results.latest_folders(ROOT, case_id)


def panel(case_id: str) -> str:
    folders = latest_folders(case_id)
    if not folders:
        return '<p class="muted">此病例尚无 3a 批次。</p>'
    content = '\n'.join(render(folder, prefix=f'chapter-{i}-') for i, folder in enumerate(folders, 1))
    # Scope the source renderer to this panel; preserve the existing Step 1–2 CSS.
    styles = '.source-selection .selected-source{background:#e1f1e7;color:#152e22}.source-selection table{border-collapse:collapse;width:100%}.source-selection td,.source-selection th{border:1px solid var(--line);padding:8px;vertical-align:top}.source-selection .table{overflow-x:auto}.source-selection pre{white-space:pre-wrap;overflow-wrap:anywhere}.source-selection :target{outline:3px solid #d69b19;background:var(--hl)}.source-selection [id]{scroll-margin-top:150px}.source-selection article{border-top:1px solid var(--line);padding:16px 0}'
    return '<style>'+styles+'</style><div class="source-selection">'+content+'</div>'

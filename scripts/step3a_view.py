"""Read-only Step 3a source-selection Viewer: self-contained static HTML, no API calls."""
from html import escape as esc
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def render_xml(node, ids, prefix='src-', targets=None):
    """Safe JATS rendering; all original text/tails retained, never execute XML markup."""
    sid = ids[id(node)]
    attrs = f' id="{prefix}{sid}"'
    tags = {'sec':'section','title':'h3','p':'p','list':'ul','list-item':'li',
            'bold':'strong','italic':'em','sup':'sup','sub':'sub','table':'table',
            'thead':'thead','tbody':'tbody','tr':'tr','td':'td','th':'th','label':'strong',
            'fn':'div','table-wrap':'div','caption':'div','table-wrap-foot':'div'}
    tag = tags.get(node.tag, 'span')
    if node.tag == 'table-wrap':
        attrs += ' class="table"'
    if node.tag in ('td','th'):
        for k in ('rowspan','colspan'):
            if k in node.attrib:
                attrs += f' {k}="{int(node.attrib[k])}"'
    if node.tag == 'xref' and targets is not None and node.attrib.get('rid') in targets:
        tag = 'a'
        attrs += ' href="#'+prefix+targets[node.attrib['rid']]+'"'
    text = esc(node.text or '')
    inner = ''.join(render_xml(c, ids, prefix, targets) + esc(c.tail or '') for c in node)
    return f'<{tag}{attrs}>{text}{inner}</{tag}>'


def details(title, text):
    return '<details><summary>'+esc(title)+'</summary><pre>'+esc(text)+'</pre></details>'


def render(folder: Path) -> str:
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
    html = []
    for b in plan['blocks']:
        i = b['index'];d = folder/f'{i:02d}'
        title = ' / '.join(b['section'])
        html.append(f'<article id="block-{i}"><h2>{i}. {esc(title)}</h2>')
        html.append(f'<p>XML 约 {b["estimated_xml_tokens"]:,} tokens · {esc(b["kind"])} · {esc(b["status"])}</p>')
        if (d/'selection.json').exists():
            selection = json.loads((d/'selection.json').read_text())
            selected = selection['selected_node_ids']
            html.append('<p>选中来源节点：'+str(len(selected))+'（不是治疗数量或医学召回率）</p>')
            if not selected:
                html.append('<p>模型未选择节点；原文仍完整保存在下方。</p>')
            for sid in selected:
                src = mapping[sid]
                html.append('<p><a href="#src-'+sid+'">'+esc(sid+' · '+' '.join(src['text'].split())[:150])+'</a></p>')
                html.append(details('来源 XPath',src['xpath']))
            html.append(details('结构化筛选结果',json.dumps(selection,ensure_ascii=False,indent=2)))
        elif (d/'response.json').exists():
            html.append('<p class="unknown">响应已保存，尚无通过解析的节点结果。不能视为空选择。</p>')
        else:
            html.append('<p class="unknown">尚未调用模型 · 结果未知</p>')
        if (d/'response.json').exists():
            response = json.loads((d/'response.json').read_text());ch = response['choices'][0]
            html.append(details('模型原始输出（未经修复）',ch['message']['content']))
            html.append(details('Token 与结束状态',json.dumps(dict(usage=response['usage'],finish_reason=ch['finish_reason']),ensure_ascii=False,indent=2)))
        req = d/('request.json' if (d/'request.json').exists() else 'planned-request.json')
        if req.exists():
            html.append(details('实际请求' if (d/'request.json').exists() else '待执行请求',req.read_text()))
        html.append(details('本次完整输入 XML',(d/'section.xml').read_text()))
        html.append('</article>')
    html.append('<article id="original"><h2>完整 Management 原文</h2><p>以下全部来自 XML，包括未选中内容。点击上方节点链接可定位；表格完整显示，保留合并单元格、表头与脚注。总体管理段落保留在此，不推断适用性。</p>')
    html.append(render_xml(root,ids,targets={n.attrib['id']:s for s,n in elements.items() if 'id' in n.attrib}))
    html.append(details('原始 XML',(folder/'management.xml').read_text()))
    html.append('</article>')
    return '\n'.join(html)


def panel(case_id: str) -> str:
    folders = [p.parent for p in (ROOT/'out/step3a-source-selection').glob('*/plan.json')
               if json.loads(p.read_text())['case_id'] == case_id]
    if not folders:
        return '<p class="muted">此病例尚无新的 3a 章节筛选结果。</p>'
    folder = max(folders, key=lambda p: (p/'plan.json').stat().st_mtime_ns)
    content = render(folder)
    # Scope the source renderer to this panel; preserve the existing Step 1–2 CSS.
    styles = '.source-selection table{border-collapse:collapse;width:100%}.source-selection td,.source-selection th{border:1px solid var(--line);padding:8px;vertical-align:top}.source-selection .table{overflow-x:auto}.source-selection pre{white-space:pre-wrap;overflow-wrap:anywhere}.source-selection :target{outline:3px solid #d69b19;background:var(--hl)}.source-selection [id]{scroll-margin-top:150px}.source-selection article{border-top:1px solid var(--line);padding:16px 0}'
    return '<style>'+styles+'</style><div class="source-selection">'+content+'</div>'

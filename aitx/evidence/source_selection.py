"""Step 3a source selection: section calls, original XML hydration, no Action inference."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import time
import xml.etree.ElementTree as ET

from aitx import budget, llm, peak, session
from scripts.llm_cost import request_reservation

PROMPT = '''你是一名医学文献研究助手。

让他在一个负责任的监护人的角度周全考虑。

根据以下患者的年龄、性别、疾病、基因变异、临床症状及治疗背景，从提供的医学章节中找出与该患者治疗决策相关的原文内容。

要求：

1. 只筛选相关原文，不进行医学总结、改写或补充。
2. 保留完整医学语义，包括治疗措施、适用条件、剂量、注意事项和例外说明。
3. 如果是表格，必须保留表格标题、完整列标题及多层表头、对应的完整表格行、合并单元格继承的信息，以及相关脚注。
4. 如果是正文，保留所属章节标题及完整相关段落；如果是列表，保留必要的列表上下文。
5. 不只筛选已经确认适用的治疗。对于与患者疾病相关、但需要额外临床条件才能使用的方案，也应保留原文。
6. 可以省略明确针对其他人群、与本患者无关的内容，但不得因病例未提供某项信息就直接排除相关治疗。
7. 保留原文顺序和来源节点 ID，不得编造或修改原文。

输出筛选到的原文节点及其引用关系。最终展示的英文原文由程序从 XML 原始节点提取，避免模型重新生成时改变文字。

患者病例：
{case_json}

当前 Management 章节（{section_path}；{kind}）：
{section_xml}

仅返回 JSON：{{"selected_node_ids":["Nxxxx"],"references":[{{"from_id":"Nxxxx","to_id":"Nxxxx"}}]}}。
selected_node_ids 仅列明确选中的完整内容节点；其后代自动保留，不重复列出。未选中时返回空列表。
references 仅记录本次 XML 中 xref 的真实引用关系，目标必须也在本次输入中；没有则返回空列表。
不要将仅作目录或上下文的节点列为选中内容。不得返回不存在的 ID。'''
PARAMS = dict(temperature=0, max_tokens=65536, thinking={'type': 'enabled'},
              reasoning_effort='low', response_format={'type': 'json_object'})


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def estimate_tokens(text: str) -> int:
    """Offline approximation, not a DeepSeek tokenizer or billing measurement."""
    return math.ceil(len(text.encode('utf-8')) / 3)


def document(xml_path: Path, management_id: str | None = None):
    tree = ET.parse(xml_path).getroot()
    matches = [n for body in tree.iter('body') for n in body.findall('sec')
               if (n.attrib.get('id') == management_id if management_id is not None
                   else ' '.join(n.findtext('title', '').split()).casefold() in ('management', 'management of als'))]
    if len(matches) != 1:
        raise ValueError('Expected one body Management section; supply its exact --management-id')
    paths, sections = {}, {}
    def index(node, path, parents):
        own = parents
        if node.tag == 'sec':
            title = node.find('title')
            if title is None:
                raise ValueError('Section has no title: ' + path)
            own = parents + [' '.join(''.join(title.itertext()).split())]
        paths[id(node)], sections[id(node)] = path, own
        counts = {}
        for child in node:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            index(child, f'{path}/{child.tag}[{counts[child.tag]}]', own)
    index(tree, '/' + tree.tag + '[1]', [])
    original = matches[0]
    annotated = copy.deepcopy(original)
    mapping = {}
    for i, (src, dst) in enumerate(zip(original.iter(), annotated.iter()), 1):
        sid = f'N{i:04d}'
        mapping[sid] = dict(xpath=paths[id(src)], section=sections[id(src)], tag=src.tag,
                            text=''.join(src.itertext()), xml=ET.tostring(src, encoding='unicode'),
                            attributes=dict(src.attrib))
        dst.set('source-node-id', sid)
    return original, annotated, mapping


def split_sections(root, threshold=8000):
    if threshold <= 0:
        raise ValueError('token threshold must be positive')
    blocks = []
    def add(node, kind):
        xml = ET.tostring(node, encoding='unicode')
        tokens = estimate_tokens(xml)
        blocks.append(dict(source_id=node.attrib['source-node-id'], kind=kind,
                           xml=xml, estimated_xml_tokens=tokens,
                           status='ready' if tokens <= threshold else 'oversize_unsplittable',
                           node_ids=[n.attrib['source-node-id'] for n in node.iter()]))
    def descend(node):
        children = node.findall('sec')
        if estimate_tokens(ET.tostring(node, encoding='unicode')) <= threshold or not children:
            add(node, '完整章节')
            return
        # Preserve parent content in source order, including content AFTER child sections.
        # Parent copies contain no child sec; never split bullets or logical table rows.
        direct = copy.deepcopy(node)
        for child in list(direct):
            if child.tag == 'sec':
                direct.remove(child)
        if any(c.tag != 'title' for c in direct) or (direct.text or '').strip():
            add(direct, '父章节直属内容；子章节另行处理')
        for child in children:
            descend(child)
    children = root.findall('sec')
    if children:
        for child in children:
            descend(child)
    else:
        descend(root)
    return blocks


def prepare(case: dict, xml_path: Path, output: Path, *, threshold=8000, management_id=None) -> dict:
    if not case['id'] or not isinstance(case['patient']['genotype'], list) or not case['patient']['genotype']:
        raise ValueError('Case ID and genotype are required')
    if not isinstance(case['patient']['clinical_context'], str):
        raise ValueError('clinical_context must be a string; missing context is not assumed')
    original, annotated, mapping = document(xml_path, management_id)
    blocks = split_sections(annotated, threshold)
    output.mkdir(parents=True, exist_ok=False)
    dump(output / 'case-input.json', case)
    dump(output / 'source-map.json', mapping)
    (output / 'management.xml').write_text(ET.tostring(original, encoding='unicode'))
    (output / 'annotated-management.xml').write_text(ET.tostring(annotated, encoding='unicode'))
    intro = [n.attrib['source-node-id'] for n in annotated if n.tag != 'sec' and n.tag != 'title'] if annotated.findall('sec') else []
    for i, block in enumerate(blocks, 1):
        block['index'] = i
        block['section'] = mapping[block['source_id']]['section']
        folder = output / f'{i:02d}'
        folder.mkdir()
        (folder / 'section.xml').write_text(block.pop('xml'))
        messages = [dict(role='user', content=PROMPT.format(
            case_json=json.dumps(case, ensure_ascii=False, indent=2),
            section_path=' / '.join(block['section']), kind=block['kind'],
            section_xml=(folder / 'section.xml').read_text()))]
        request = dict(model='deepseek-flash', messages=messages, params=copy.deepcopy(PARAMS))
        dump(folder / 'planned-request.json', request)
        block['request_sha256'] = hashlib.sha256((folder / 'planned-request.json').read_bytes()).hexdigest()
        block['estimated_request_tokens'] = estimate_tokens(messages[0]['content'])
        block['reservation_usd'] = request_reservation(messages, PARAMS['max_tokens'], time.time())
    plan = dict(version='step3a-source-selection-v1', case_id=case['id'], state='prepared_not_run',
                source_path=str(xml_path.resolve()), source_sha256=hashlib.sha256(xml_path.read_bytes()).hexdigest(),
                threshold=threshold, token_estimator='ceil(UTF-8 bytes / 3); approximate XML only',
                management_intro_ids=intro, intro_policy='Retained by code, not submitted to model or inferred applicable',
                blocks=blocks, total_reservation_usd=sum(b['reservation_usd'] for b in blocks))
    dump(output / 'plan.json', plan)
    return plan


def hydrate(selection, mapping, allowed):
    if not isinstance(selection, dict) or set(selection) != {'selected_node_ids', 'references'}:
        raise ValueError('Expected selected_node_ids and references')
    ids, refs = selection['selected_node_ids'], selection['references']
    if not isinstance(ids, list) or not all(isinstance(s, str) and s in allowed for s in ids):
        raise ValueError('Selected node ID outside this request')
    if len(ids) != len(set(ids)) or not isinstance(refs, list):
        raise ValueError('Duplicate IDs or invalid references')
    def submitted(sid):
        node = ET.fromstring(mapping[sid]['xml'])
        allowed_paths = {mapping[k]['xpath'] for k in allowed}
        def trim(n, path):
            counts = {}
            for child in list(n):
                counts[child.tag] = counts.get(child.tag, 0) + 1
                child_path = f'{path}/{child.tag}[{counts[child.tag]}]'
                if child_path not in allowed_paths:
                    n.remove(child)
                else:
                    trim(child, child_path)
        trim(node, mapping[sid]['xpath'])
        return node
    xml_ids = {v['attributes']['id']: k for k, v in mapping.items() if 'id' in v['attributes']}
    def targets(sid):
        links = []
        for x in (submitted(sid) if sid in allowed else ET.fromstring(mapping[sid]['xml'])).iter('xref'):
            for rid in x.attrib['rid'].split():
                links.append(dict(rid=rid, target_id=xml_ids.get(rid)))
        return links
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {'from_id', 'to_id'}:
            raise ValueError('Invalid reference shape')
        if ref['from_id'] not in allowed or ref['to_id'] not in allowed:
            raise ValueError('Reference outside this request')
        if ref['to_id'] not in [x['target_id'] for x in targets(ref['from_id'])]:
            raise ValueError('Reference is not an XML xref')
    # Parent selections subsume descendants without changing what the model returned.
    roots = [s for s in mapping if s in ids and not any(
        mapping[s]['xpath'].startswith(mapping[t]['xpath'] + '/') for t in ids if t != s)]
    records = []
    for sid in roots:
        path = mapping[sid]['xpath']
        # Full tables/lists are display CONTEXT, never additional model-selected content.
        ancestors = [k for k,v in mapping.items() if v['tag'] in ('table-wrap', 'list') and
                     (path == v['xpath'] or path.startswith(v['xpath'] + '/'))]
        context = min(ancestors, key=lambda k: len(mapping[k]['xpath'])) if ancestors else sid
        node = submitted(sid)
        record = dict(mapping[sid], xml=ET.tostring(node, encoding='unicode'), text=''.join(node.itertext()))
        record['scope'] = 'submitted subtree only; full context is not additional model selection'
        records.append(dict(source_id=sid, **record, context_id=context,
                            source_references=targets(context)))
    return dict(selected_node_ids=ids, references=refs, records=records,
                interpretation='Source selection only; not a determination of patient eligibility or treatment received')


def run(output: Path, *, max_cost_usd: float) -> dict:
    """One request per planned block, no retry/resume; persist raw response before decoding."""
    if not math.isfinite(max_cost_usd) or max_cost_usd <= 0:
        raise ValueError('A positive finite approved run budget is required')
    plan = json.loads((output / 'plan.json').read_text())
    if any(b['status'] != 'ready' for b in plan['blocks']):
        raise ValueError('Oversize leaf/direct content has no subsection to split; no calls sent')
    if (output / 'execution.json').exists():
        raise FileExistsError('This plan has already been attempted; no automatic retry')
    cfg = llm.config()
    if cfg['model'] != 'deepseek-flash' or cfg['base_url'] != 'https://api.deepseek.com':
        raise ValueError('Expected DeepSeek Flash configuration')
    requests = []
    for block in plan['blocks']:
        p = output / f"{block['index']:02d}" / 'planned-request.json'
        if hashlib.sha256(p.read_bytes()).hexdigest() != block['request_sha256']:
            raise ValueError('Frozen request changed')
        requests.append(json.loads(p.read_text()))
    peak.guard()
    reserves = [request_reservation(r['messages'], r['params']['max_tokens'], time.time()) for r in requests]
    daily_cap = budget.cap()
    if sum(reserves) > max_cost_usd or (daily_cap is not None and budget.spent_today() + sum(reserves) > daily_cap):
        raise budget.OverBudget('Whole-run reservation exceeds run or daily budget; no calls sent')
    mapping = json.loads((output / 'source-map.json').read_text())
    execution = dict(state='incomplete', max_cost_usd=max_cost_usd, accounted_usd=0, blocks=[])
    dump(output / 'execution.json', execution)
    for block, request in zip(plan['blocks'], requests):
        peak.check_before_call()
        folder = output / f"{block['index']:02d}"
        at = time.time()
        reserve = request_reservation(request['messages'], request['params']['max_tokens'], at)
        if execution['accounted_usd'] + reserve > max_cost_usd or (daily_cap is not None and budget.spent_today() + reserve > daily_cap):
            raise budget.OverBudget('Remaining budget insufficient')
        dump(folder / 'request.json', dict(**request, at=at, reserved_usd=reserve))
        entry = dict(index=block['index'], state='request_started', accounted_usd=reserve)
        execution['blocks'].append(entry)
        execution['accounted_usd'] += reserve
        dump(output / 'execution.json', execution)
        response = llm.chat(request['messages'], **request['params'])
        dump(folder / 'response.json', response)
        choice = response['choices'][0]
        entry.update(state='response_saved', usage=response['usage'], finish_reason=choice['finish_reason'],
                     accounted_usd=session.cost(response['usage'], at, reserve))
        execution['accounted_usd'] += entry['accounted_usd'] - reserve
        dump(output / 'execution.json', execution)
        if choice['finish_reason'] != 'stop':
            raise ValueError('Incomplete model response; raw response saved, not repaired')
        parsed = json.loads(choice['message']['content'])
        dump(folder / 'parsed.json', parsed)
        result = hydrate(parsed, mapping, set(block['node_ids']))
        dump(folder / 'selection.json', result)
        entry['state'] = 'complete'
        dump(output / 'execution.json', execution)
    execution['state'] = 'complete'
    dump(output / 'execution.json', execution)
    return execution

"""Step 3a source selection: section calls, original XML hydration, no Action inference."""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor, wait
from threading import Lock
import hashlib
import json
import math
from pathlib import Path
import time
import xml.etree.ElementTree as ET

from aitx import budget, llm, peak, session
from aitx.llm_cost import request_reservation

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
CONTEXT_RULES = '输入分为 read_only_context（共同上下文）和 selection_body（本次筛选正文）。\n共同上下文只用于理解，不能把其中节点加入 selected_node_ids；其中的共用正文另有自己的筛选分块，章节标题始终作为来源上下文保留。\nselected_node_ids 只能选本次筛选正文中存在的节点；禁止选取跨越上下文和正文的父节点。\n完整表格作为正文输入时，仍按患者筛选，不因输入整表就默认整表相关。明确针对其他人群的行可不选；病例信息未知的条件性方案仍保留。不要把行的其他人群限制丢掉。\n需要显示的共同标题、表头、跨行继承和脚注作为来源上下文保留，不将它们算成额外选中的治疗内容。\nreferences 可以指向本次输入中真实存在的上下文或正文节点；不得编造引用。\n'
MAX_BLOCK_TOKENS = 16000  # XML estimate including context; tables remain intact.

PARAMS = dict(temperature=0, max_tokens=65536, thinking={'type': 'enabled'},
              reasoning_effort='low', response_format={'type': 'json_object'})


def dump(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


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


def split_sections(root, threshold=8000, max_block_tokens=MAX_BLOCK_TOKENS):
    if threshold <= 0:
        raise ValueError('token threshold must be positive')
    blocks = []
    def units(node):
        title = node.find('title')
        if title is None:
            raise ValueError('Section has no title')
        content = [n for n in node if n.tag != 'title']
        heads = [i for i,n in enumerate(content) if n.tag == 'p' and not (n.text or '').strip()
                 and len(n) and n[0].tag == 'bold']
        if heads:
            starts = ([0] if heads[0] else []) + heads
            groups = [content[a:b] for a,b in zip(starts, starts[1:]+[len(content)])]
            intro = groups[0] if heads[0] else []
            return [(g, [title]+(intro if g is not intro else [])) for g in groups]
        groups, pending = [], []
        for n in content:
            pending.append(n)
            if n.tag == 'table-wrap':
                groups.append(pending)
                pending = []
        if pending:
            groups.append(pending)
        intro = []
        for n in content:
            if n.tag == 'table-wrap':
                break
            intro.append(n)
        return [(g, [title]+[n for n in intro if n not in g]) for g in groups]

    def fragment(nodes, tag):
        wrapper = ET.Element(tag)
        for n in nodes:
            wrapper.append(copy.deepcopy(n))
        return wrapper

    def add(node, kind):
        if estimate_tokens(ET.tostring(node, encoding='unicode')) > threshold:
            for body, context in units(node):
                wrapper = ET.Element('source-input')
                wrapper.append(fragment(context, 'read_only_context'))
                wrapper.append(fragment(body, 'selection_body'))
                xml = ET.tostring(wrapper, encoding='unicode')
                tokens = estimate_tokens(xml)
                blocks.append(dict(source_id=node.attrib['source-node-id'], kind='完整主题/整表；上下文与正文分离',
                                   xml=xml, estimated_xml_tokens=tokens,
                                   status='ready' if tokens <= max_block_tokens else 'oversize_unsplittable',
                                   node_ids=[n.attrib['source-node-id'] for nodes in (context, body) for top in nodes for n in top.iter()],
                                   selectable_ids=[n.attrib['source-node-id'] for top in body for n in top.iter()],
                                   context_ids=[n.attrib['source-node-id'] for top in context for n in top.iter()]))
            return
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
            section_xml=(folder / 'section.xml').read_text()) + (CONTEXT_RULES if 'selectable_ids' in block else ''))]
        request = dict(model='deepseek-flash', messages=messages, params=copy.deepcopy(PARAMS))
        dump(folder / 'planned-request.json', request)
        block['request_sha256'] = hashlib.sha256((folder / 'planned-request.json').read_bytes()).hexdigest()
        block['estimated_request_tokens'] = estimate_tokens(messages[0]['content'])
        block['reservation_usd'] = request_reservation(messages, PARAMS['max_tokens'], time.time())
    plan = dict(version='step3a-source-selection-v2', case_id=case['id'], state='prepared_not_run',
                source_path=str(xml_path.resolve()), source_sha256=hashlib.sha256(xml_path.read_bytes()).hexdigest(),
                threshold=threshold, max_block_tokens=MAX_BLOCK_TOKENS, token_estimator='ceil(UTF-8 bytes / 3); approximate XML only',
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
    def source_node(sid):
        return ET.fromstring('<source-fragment>' + mapping[sid]['xml'] + '</source-fragment>')[0]

    def submitted(sid):
        node = source_node(sid)
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
        for x in (submitted(sid) if sid in allowed else source_node(sid)).iter('xref'):
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



def hydrate_block(selection, mapping, block):
    if 'selectable_ids' in block:
        if not isinstance(selection, dict) or not isinstance(selection['selected_node_ids'], list):
            raise ValueError('Expected selected_node_ids list')
        if not set(selection['selected_node_ids']).issubset(block['selectable_ids']):
            raise ValueError('Selected node is read-only context or outside this body')
    return hydrate(selection, mapping, set(block['node_ids']))

def hydrate_xml_references(selection, mapping, block):
    """Explicit offline recovery: keep selected IDs, derive links from submitted XML.

    Model references remain provenance only. Targets absent from the Management
    map keep their original XML rid; absence from this map is not a broken citation.
    """
    if not isinstance(selection, dict) or set(selection) != {'selected_node_ids', 'references'}:
        raise ValueError('Expected selected_node_ids and references')
    if not isinstance(selection['references'], list):
        raise ValueError('Expected references list')
    result = hydrate_block(dict(selected_node_ids=selection['selected_node_ids'], references=[]), mapping, block)
    allowed = set(block['node_ids'])
    targets = {v['attributes']['id']: sid for sid, v in mapping.items() if 'id' in v['attributes']}
    links = []
    for record in result['records']:
        path = record['xpath']
        for sid, source in mapping.items():
            if sid not in allowed or source['tag'] != 'xref':
                continue
            if source['xpath'] != path and not source['xpath'].startswith(path + '/'):
                continue
            for rid in source['attributes']['rid'].split():
                target = targets.get(rid)
                links.append(dict(from_id=record['source_id'], xref_id=sid, rid=rid, target_id=target,
                                  target_scope='outside_source_map' if target is None else
                                  ('in_request' if target in allowed else 'outside_request')))
    result['references'] = [dict(from_id=link['from_id'], to_id=link['target_id'])
                            for link in links if link['target_scope'] == 'in_request']
    result['xml_references'] = links
    result['reference_provenance'] = 'derived from submitted XML; model references are not used'
    result['model_references'] = copy.deepcopy(selection['references'])
    return result


def recover(output: Path) -> dict:
    """Hydrate saved responses offline. Never send requests or invent missing answers."""
    plan = json.loads((output / 'plan.json').read_text())
    execution = json.loads((output / 'execution.json').read_text())
    if execution['state'] == 'complete':
        return execution
    mapping = json.loads((output / 'source-map.json').read_text())
    entries = {e['index']: e for e in execution['blocks']}
    errors = []
    for block in plan['blocks']:
        folder = output / f"{block['index']:02d}"
        if block['index'] not in entries:
            continue
        entry = entries[block['index']]
        if not (folder / 'response.json').exists():
            entry.update(state='failed', error='Request was started but no response was saved; automatic retry forbidden')
            errors.append(entry['error'])
            continue
        request = json.loads((folder / 'request.json').read_text())
        response = json.loads((folder / 'response.json').read_text())
        entry['accounted_usd'] = session.cost(response['usage'], request['at'], request['reserved_usd'])
        try:
            if response['choices'][0]['finish_reason'] != 'stop':
                raise ValueError('Incomplete model response; no automatic retry')
            parsed = json.loads(response['choices'][0]['message']['content'])
            result = hydrate_block(parsed, mapping, block)
        except (ValueError, KeyError, ET.ParseError) as error:
            entry.update(state='failed', error=f'{type(error).__name__}: {error}')
            errors.append(entry['error'])
        else:
            dump(folder / 'parsed.json', parsed)
            dump(folder / 'selection.json', result)
            if 'error' in entry:
                entry['previous_error'] = entry.pop('error')
            entry.update(state='complete', recovered_offline=True)
    execution['accounted_usd'] = sum(e['accounted_usd'] for e in execution['blocks'])
    execution['state'] = 'failed' if errors else ('complete' if len(entries) == len(plan['blocks']) else 'incomplete')
    execution['remaining_blocks'] = [b['index'] for b in plan['blocks'] if b['index'] not in entries]
    execution.pop('error', None)
    if errors:
        execution['error'] = '; '.join(errors)
    dump(output / 'execution.json', execution)
    if errors:
        raise ValueError(execution['error'])
    return execution


def run(output: Path, *, max_cost_usd: float, concurrency: int = 1, resume: bool = False) -> dict:
    """One request per unstarted block; explicit resume reuses saved responses without retrying calls."""
    if not math.isfinite(max_cost_usd) or max_cost_usd <= 0:
        raise ValueError('A positive finite approved run budget is required')
    if concurrency not in (1, 2, 3, 4):
        raise ValueError('Concurrency must be between 1 and 4')
    plan = json.loads((output / 'plan.json').read_text())
    if any(b['status'] != 'ready' for b in plan['blocks']):
        raise ValueError('Oversize leaf/direct content has no subsection to split; no calls sent')
    previous = None
    if (output / 'execution.json').exists():
        if not resume:
            raise FileExistsError('This plan has already been attempted; use explicit resume')
        previous = recover(output)
        if previous['state'] == 'complete':
            return previous
    elif resume:
        raise FileNotFoundError('No execution exists to resume')
    cfg = llm.config()
    if cfg['model'] != 'deepseek-flash' or cfg['base_url'] != 'https://api.deepseek.com':
        raise ValueError('Expected DeepSeek Flash configuration')
    completed = {e['index'] for e in previous['blocks']} if previous is not None else set()
    pending_blocks = [b for b in plan['blocks'] if b['index'] not in completed]
    requests = []
    for block in pending_blocks:
        p = output / f"{block['index']:02d}" / 'planned-request.json'
        if hashlib.sha256(p.read_bytes()).hexdigest() != block['request_sha256']:
            raise ValueError('Frozen request changed')
        requests.append(json.loads(p.read_text()))
    peak.guard()
    reserves = [request_reservation(r['messages'], r['params']['max_tokens'], time.time()) for r in requests]
    daily_cap = budget.cap()
    accounted = previous['accounted_usd'] if previous is not None else 0
    if accounted + sum(reserves) > max_cost_usd or (daily_cap is not None and budget.spent_today() + sum(reserves) > daily_cap):
        raise budget.OverBudget('Whole-run reservation exceeds run or daily budget; no calls sent')
    mapping = json.loads((output / 'source-map.json').read_text())
    execution = previous if previous is not None else dict(accounted_usd=0, blocks=[])
    execution.update(state='running', max_cost_usd=max_cost_usd, concurrency=concurrency)
    execution.pop('error', None)
    dump(output / 'execution.json', execution)
    lock = Lock()

    def execute(block, request, entry, at, reserve):
        folder = output / f"{block['index']:02d}"
        peak.check_before_call()
        response = llm.chat(request['messages'], **request['params'])
        dump(folder / 'response.json', response)
        choice = response['choices'][0]
        with lock:
            entry.update(state='response_saved', usage=response['usage'], finish_reason=choice['finish_reason'],
                         accounted_usd=session.cost(response['usage'], at, reserve))
            execution['accounted_usd'] += entry['accounted_usd'] - reserve
            dump(output / 'execution.json', execution)
        if choice['finish_reason'] != 'stop':
            raise ValueError('Incomplete model response; raw response saved, not repaired')
        parsed = json.loads(choice['message']['content'])
        dump(folder / 'parsed.json', parsed)
        result = hydrate_block(parsed, mapping, block)
        dump(folder / 'selection.json', result)
        with lock:
            entry['state'] = 'complete'
            dump(output / 'execution.json', execution)

    # Reserve each entire batch before dispatch; settle all in-flight requests before
    # raising a failure. No next batch is submitted after a failed block.
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for offset in range(0, len(requests), concurrency):
            peak.check_before_call()
            batch = list(zip(pending_blocks[offset:offset+concurrency], requests[offset:offset+concurrency]))
            at = time.time()
            batch_reserves = [request_reservation(r['messages'], r['params']['max_tokens'], at) for _, r in batch]
            reserved = sum(batch_reserves)
            if execution['accounted_usd'] + reserved > max_cost_usd or (daily_cap is not None and budget.spent_today() + reserved > daily_cap):
                raise budget.OverBudget('Remaining budget insufficient for concurrent batch')
            jobs = []
            for (block, request), reserve in zip(batch, batch_reserves):
                folder = output / f"{block['index']:02d}"
                dump(folder / 'request.json', dict(**request, at=at, reserved_usd=reserve))
                entry = dict(index=block['index'], state='request_started', accounted_usd=reserve)
                execution['blocks'].append(entry)
                execution['accounted_usd'] += reserve
                jobs.append((block, request, entry, at, reserve))
            dump(output / 'execution.json', execution)
            futures = [pool.submit(execute, *job) for job in jobs]
            wait(futures)
            failures = []
            for future, job in zip(futures, jobs):
                error = future.exception()
                if error is not None:
                    job[2].update(state='failed', error=f'{type(error).__name__}: {error}')
                    failures.append(job[2]['error'])
            if failures:
                execution.update(state='failed', error='; '.join(failures))
                dump(output / 'execution.json', execution)
                for future in futures:
                    future.result()
    execution['state'] = 'complete'
    execution['remaining_blocks'] = []
    dump(output / 'execution.json', execution)
    return execution

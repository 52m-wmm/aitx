"""Import reviewed source-selection results without model calls."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil


def batch_folder(root: Path, case_id: str, batch: str) -> Path:
    base = root/'runs/step3a'
    if not case_id or Path(case_id).name != case_id or case_id in ('.', '..'):
        raise ValueError('Invalid case ID')
    if not batch or Path(batch).name != batch or batch in ('.', '..'):
        raise ValueError('Invalid batch name')
    folder = base/case_id/batch
    if folder.resolve().parent != (base/case_id).resolve() or (base/case_id).resolve().parent != base.resolve():
        raise ValueError('Batch must be inside runs/step3a/<case-id>')
    plan = json.loads((folder/'plan.json').read_text())
    if plan['case_id'] != case_id:
        raise ValueError('Batch belongs to a different case')
    return folder


def current_folder(root: Path, case_id: str) -> Path | None:
    index = json.loads((root/'out/current.json').read_text())
    if case_id not in index['step3a']:
        return None
    return batch_folder(root, case_id, index['step3a'][case_id])


def latest_folder(root: Path, case_id: str) -> Path | None:
    """Newest run by its first request time; unstarted plans use preparation mtime."""
    if not case_id or Path(case_id).name != case_id or case_id in ('.', '..'):
        raise ValueError('Invalid case ID')
    batches = []
    for plan in (root/'runs/step3a'/case_id).glob('*/plan.json'):
        folder = batch_folder(root, case_id, plan.parent.name)
        requests = list(folder.glob('*/request.json'))
        at = min(json.loads(p.read_text())['at'] for p in requests) if requests else plan.stat().st_mtime
        batches.append((at, folder.name, folder))
    return max(batches)[2] if batches else None


def latest_folders(root: Path, case_id: str) -> list[Path]:
    """Each source chapter keeps its own newest batch, including unfinished runs."""
    if not case_id or Path(case_id).name != case_id or case_id in ('.', '..'):
        raise ValueError('Invalid case ID')
    newest = {}
    for path in (root/'runs/step3a'/case_id).glob('*/plan.json'):
        folder = batch_folder(root, case_id, path.parent.name)
        plan = json.loads(path.read_text())
        source = str(Path(plan['source_path']).resolve())
        requests = list(folder.glob('*/request.json'))
        at = min(json.loads(p.read_text())['at'] for p in requests) if requests else path.stat().st_mtime
        candidate = (at, folder.name, folder)
        if source not in newest or candidate > newest[source]:
            newest[source] = candidate
    return [newest[source][2] for source in sorted(newest)]


def select(root: Path, case_id: str, batch: str) -> Path:
    """Select the default CLI batch explicitly; the viewer uses latest_folder."""
    folder = batch_folder(root, case_id, batch)
    path = root/'out/current.json'
    index = json.loads(path.read_text())
    index['step3a'][case_id] = batch
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(index, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(path)
    return folder


def archive(source: Path, prepared: Path, destination: Path):
    def read(path):
        return json.loads(path.read_text())
    old, plan = read(source/'plan.json'), read(prepared/'plan.json')
    if read(source/'case-input.json') != read(prepared/'case-input.json'):
        raise ValueError('Case input differs')
    if (source/'management.xml').read_bytes() != (prepared/'management.xml').read_bytes():
        raise ValueError('Management source differs')
    if [(b['index'], b['source_id']) for b in old['blocks']] != [(b['index'], b['source_id']) for b in plan['blocks']]:
        raise ValueError('Section boundaries differ')
    shutil.copytree(source, destination)
    shutil.copyfile(destination/'plan.json', destination/'plan.original.json')
    shutil.copyfile(destination/'source-map.json', destination/'source-map.original.json')
    shutil.copyfile(prepared/'source-map.json', destination/'source-map.json')
    for block in plan['blocks']:
        directory = destination/f"{block['index']:02d}"
        response = read(directory/'response.json')
        if response['choices'][0]['finish_reason'] != 'stop':
            raise ValueError('Incomplete response')
        selection = read(directory/'selection.json')
        shutil.copyfile(directory/'selection.json', directory/'selection.original.json')
        selection['selected_node_ids'] = selection['selected_roots']
        selection['imported_from'] = str((source/directory.name/'selection.json').resolve())
        (directory/'selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2))
        block['status'] = '已完成 · 导入既有审核结果'
        for field in ('request_sha256','estimated_request_tokens','reservation_usd'):
            del block[field]
        block['original_request_sha256'] = hashlib.sha256((directory/'request.json').read_bytes()).hexdigest()
    plan.update(state='imported_completed', imported_from=str(source.resolve()),
                interpretation='既有模型回答的人工审核节点转录；非新Prompt运行结果，未补选节点。')
    (destination/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    return destination


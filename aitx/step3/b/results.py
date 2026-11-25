"""Step 3b run storage. Raw HTTP/LLM caches keep their existing locations."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import time

from aitx import runmeta
from aitx.step3.b.presentation import ledger_view
from aitx.step3.b.pipeline import refresh_trials


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(path)


def latest_folder(root: Path, case_id: str) -> Path | None:
    paths = list((root/'.cache/step3b'/case_id).glob('*/execution.json'))
    return max(paths, key=lambda p: (json.loads(p.read_text())['started_at'], p.parent.name)).parent if paths else None


def run_case(root: Path, case: dict, step1: dict, step2: dict, upstream: dict) -> Path:
    """Run the existing refresh, archive it, and publish its cards as one batch."""
    case_id = case['id']
    previous_path = root/'out/step3'/f'{case_id}.json'
    previous = json.loads(previous_path.read_text())
    batch = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    folder = root/'.cache/step3b'/case_id/batch
    folder.mkdir(parents=True, exist_ok=False)
    shutil.copy2(previous_path, folder/'previous-ledger.json')
    write_json(folder/'case-input.json', case)
    state = {'case_id': case_id, 'started_at': time.time(), 'state': 'running'}
    write_json(folder/'execution.json', state)
    complete = False
    try:
        ledger = refresh_trials(previous, case, step1, step2)
        if not ledger['ok']:
            raise RuntimeError(f'{case_id}: Ledger checks failed; original output retained')
        # Build the view before publishing so conversion errors cannot replace formal output.
        view = ledger_view(ledger, case, folder/'ledger.json')
        runmeta.write_output(3, case, ledger, upstream=upstream, out=folder/'output')
        staged = folder/'output/step3'/f'{case_id}.json'
        staged.replace(folder/'ledger.json')
        staged.parent.rmdir()
        staged.parent.parent.rmdir()
        write_json(folder/'result.json', view)
        temporary = previous_path.with_suffix('.json.tmp')
        shutil.copyfile(folder/'ledger.json', temporary)
        temporary.replace(previous_path)
        complete = True
    finally:
        state.update(state='complete' if complete else 'failed', finished_at=time.time())
        error = sys.exc_info()[1]
        if error is not None:
            state['error'] = f'{type(error).__name__}: {error}'
        write_json(folder/'execution.json', state)
    return folder


def import_saved(root: Path, source: Path) -> Path:
    """Copy an existing viewer export byte-for-byte; keep its saved time and provenance."""
    data = json.loads(source.read_text())
    case_id = data['case_id']
    if data['patient']['id'] != case_id:
        raise ValueError('Step 3b result belongs to another case')
    saved_at = source.stat().st_mtime
    batch = 'import-'+datetime.fromtimestamp(saved_at, timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    folder = root/'.cache/step3b'/case_id/batch
    folder.mkdir(parents=True, exist_ok=False)
    shutil.copy2(source, folder/'result.json')
    write_json(folder/'execution.json', {'case_id': case_id, 'started_at': saved_at,
               'state': 'imported', 'source': str(source.resolve())})
    return folder

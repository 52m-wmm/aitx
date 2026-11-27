"""Keep 72-hour sessions and newest per-case step batches; archive before pruning.

Default is a read-only plan. --apply --archive /outside/project/history.tar.gz
archives superseded run files before removing their original copies. Raw source
and model caches, formal outputs, baselines and the global cost ledger are untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aitx.step3.a import results as A
from aitx.step3.b import results as B


def digest(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def files(path):
    return {p for p in path.rglob('*') if p.is_file()} if path.is_dir() else {path}


def plan(root):
    remove = set()
    sessions = root/'runs/sessions'
    cutoff = time.time() - 72 * 3600
    retained_sessions = []
    for folder in sessions.iterdir():
        if not folder.is_dir():
            continue
        activity = []
        meta = folder/'meta.json'
        if meta.exists():
            activity.append(json.loads(meta.read_text())['started'])
        for name in ('steps.jsonl', 'calls.jsonl'):
            path = folder/name
            if path.exists():
                with path.open() as source:
                    for line in source:
                        activity.append(json.loads(line)['at'])
        if not activity:
            raise ValueError(f'Session has no recorded time: {folder}')
        latest_at = max(activity)
        if latest_at >= cutoff:
            retained_sessions.append({'session': folder.name, 'last_activity_at': latest_at})
        else:
            remove.update(files(folder))
    retained_a = []
    for case in (root/'runs/step3a').iterdir():
        if case.is_dir():
            keep = set(A.latest_folders(root, case.name))
            retained_a.extend(keep)
            for folder in case.iterdir():
                if folder.is_dir() and folder not in keep:
                    remove.update(files(folder))
    retained_b = []
    for case in (root/'.cache/step3b').iterdir():
        if case.is_dir():
            keep = B.latest_folder(root, case.name)
            if keep is not None:
                retained_b.append(keep)
            for folder in case.iterdir():
                if folder.is_dir() and folder != keep:
                    remove.update(files(folder))
    # Old review/experiment outputs leave the active run area. Their contents
    # remain recoverable from the archive, including original call/approval records.
    preserve = {'sessions', 'step3a', 'llm_calls.jsonl', 'step3_remaining_budget.json', 'latest.json', 'README.md'}
    for path in (root/'runs').iterdir():
        if path.name not in preserve:
            remove.update(files(path))
    return {
        'remove': sorted(str(p.relative_to(root)) for p in remove),
        'bytes': sum(p.stat().st_size for p in remove),
        'session_cutoff': cutoff,
        'sessions': sorted(retained_sessions, key=lambda row: row['session']),
        'step3a': sorted(str(p.relative_to(root)) for p in retained_a),
        'step3b': sorted(str(p.relative_to(root)) for p in retained_b),
    }


def apply(root, decision, archive):
    archive = archive.resolve()
    if archive == root or root in archive.parents:
        raise ValueError('Archive must be outside the project')
    archive.parent.mkdir(parents=True, exist_ok=True)
    hashes = {}
    index_path = root/'out/current.json'
    members = decision['remove'] + ['out/current.json']
    with archive.open('xb') as output:
        with tarfile.open(fileobj=output, mode='w:gz', compresslevel=6) as tar:
            for name in members:
                path = root/name
                if path.is_symlink():
                    hashes[name] = 'symlink:' + os.readlink(path)
                else:
                    with path.open('rb') as source:
                        hashes[name] = digest(source)
                tar.add(path, arcname=name, recursive=False)
    # Re-read every compressed member before removing anything.
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            if member.issym():
                actual = 'symlink:' + member.linkname
            else:
                with tar.extractfile(member) as source:
                    actual = digest(source)
            if actual != hashes[member.name]:
                raise ValueError(f'Archive verification failed: {member.name}')
    # Prevent pruning a file changed by another process after archive creation.
    for name in members:
        path = root/name
        if path.is_symlink():
            actual = 'symlink:' + os.readlink(path)
        else:
            with path.open('rb') as source:
                actual = digest(source)
        if actual != hashes[name]:
            raise ValueError(f'File changed during archive: {name}')
    manifest = {**decision, 'archive': str(archive), 'sha256': hashes}
    archive.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    # Keep the CLI's explicit selection valid when its old batch is pruned.
    index = json.loads(index_path.read_text())
    for cid in index['step3a']:
        index['step3a'][cid] = A.latest_folder(root, cid).name
    temporary = index_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(index, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(index_path)
    for name in decision['remove']:
        (root/name).unlink()
    for base in (root/'runs', root/'.cache/step3b'):
        for directory in sorted((p for p in base.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()
    (root/'runs/latest.json').write_text(json.dumps(
        {k: v for k, v in manifest.items() if k not in ('remove', 'sha256')}, ensure_ascii=False, indent=2)+'\n')
    return {'removed_files': len(decision['remove']), 'archived_bytes': decision['bytes'],
            'archive': str(archive), 'compressed_bytes': archive.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    decision = plan(ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, ensure_ascii=False, indent=2)+'\n')
    if args.apply:
        if args.archive is None:
            parser.error('--apply requires --archive')
        print(json.dumps(apply(ROOT, decision, args.archive), ensure_ascii=False))
    else:
        print(json.dumps({k: v for k, v in decision.items() if k != 'remove'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

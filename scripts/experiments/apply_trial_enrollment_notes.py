"""Offline note-only replay of the 15 saved ledgers; writes a new review directory, never a baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aitx.evidence import ledger as LG, trials as T
from aitx.step3.b import criteria as C
from aitx.step3.b import records as TR
from scripts.status_diff import case_ids


def replay(source: Path, destination: Path) -> list[dict]:
    destination.mkdir(parents=True, exist_ok=False)
    changes = []
    for cid in case_ids():
        original = (source / f'{cid}.json').read_bytes()
        data = json.loads(original)
        led = LG.Ledger(data['patient_id'], data['branches'])
        for key in led.__dict__:
            setattr(led, key, {e['id']: e for e in data['evidence']} if key == 'evidence' else data[key])
        studies = {}
        for plan in data['trial_searches'].values():
            for search in plan['searches']:
                for url in search['page_urls']:
                    cache = ROOT / '.cache/http' / (hashlib.sha256(url.encode()).hexdigest() + '.json')
                    response = json.loads(cache.read_text())
                    if response['url'] != url:
                        raise ValueError(f'cache URL mismatch: {cache}')
                    for study in json.loads(response['text'])['studies']:
                        flat = T.flat(study)
                        studies[flat['nct']] = dict(flat, _accessed_at=response['accessed_at'])
        pc = data['patient_context']
        pf = {k: pc[k] for k in ('age_months', 'age_quote', 'sex', 'sex_quote')}
        count = 0
        for action in data['actions']:
            if action['section'] != TR.SECTION or not action.get('nct'):
                continue
            study = studies[action['nct']]
            if not C.enrollment_note_lines(study, pf):
                continue
            # Use the production recorder with no body mappings, then append only its note rows.
            scratch = LG.Ledger(cid, data['branches'])
            study.update(relevance=action['relevance'], specific=action['specific'])
            TR._record(scratch, study, {b: 'analysed' for b in action['applies_to']},
                       {'items': [], 'mappings': [], 'rejected': [], 'produced_by': 'code'},
                       pf, {'facts': []}, {b['id']: b for b in data['branches']}, {'candidates': []})
            rows = [r for r in scratch.actions[0]['requirements'] if r.get('details', {}).get('enrollment_note')]
            old_status = dict(action['status_by_branch'])
            for row in rows:
                row['id'] = f"r{1 + max(int(r['id'][1:]) for r in action['requirements'])}" if action['requirements'] else 'r1'
                action['requirements'].append(row)
                eid = row['requirement_evidence']
                led.add(scratch.evidence[eid])
                action['evidence_ids'] = sorted(set(action['evidence_ids']) | {eid})
                if row['result'] == 'unknown':
                    led.note_missing(row['patient_fact']['field'], action['label'], row['requirement'][:120], '3b')
            for bid in action['applies_to']:
                status = LG.status_of(action['requirements'], bid)[0]
                if status != action['status_by_branch'][bid]['status']:
                    failed = next((r for r in action['requirements'] if bid in r['applies_to'] and r['result'] == 'fail'), None)
                    reason = ('not met: ' + failed['requirement']) if failed else 'depends on: unresolved enrollment note'
                    action['status_by_branch'][bid] = {'status': status, 'reason': reason}
            count += len(rows)
            changes.append({'case': cid, 'nct': action['nct'], 'added_requirements': rows,
                            'before': old_status, 'after': action['status_by_branch']})
        if count:
            data['evidence'] = list(led.evidence.values())
            data['checks'] = led.checks()
            failed = [c for c in data['checks'] if c['status'] == 'fail']
            if failed:
                raise ValueError(f'{cid} ledger checks failed: {failed}')
            data['_meta']['enrollment_note_update'] = {'at': int(time.time()), 'note_only': True,
                                                       'source_ledger_sha256': hashlib.sha256(original).hexdigest()}
            (destination / f'{cid}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')
        else:
            (destination / f'{cid}.json').write_bytes(original)
    return changes


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--destination', type=Path, required=True)
    args = ap.parse_args()
    records = replay(args.source, args.destination)
    (args.destination.parent / 'note-changes.json').write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print(json.dumps({'changed_trials': len(records), 'added_requirements': sum(len(r['added_requirements']) for r in records),
                      'status_changes': [r for r in records if r['before'] != r['after']]}, ensure_ascii=False))

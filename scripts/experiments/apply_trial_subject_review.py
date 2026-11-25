"""Offline subject correction and source-proven cohort OR; preserve saved body extraction and IDs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aitx.evidence import ledger as LG, trials as T
from aitx.step3.b import criteria as C
from scripts.status_diff import case_ids


def replay(source: Path, destination: Path, context_dir: Path) -> list[dict]:
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
                    cached = ROOT / '.cache/http' / (hashlib.sha256(url.encode()).hexdigest() + '.json')
                    response = json.loads(cached.read_text())
                    if response['url'] != url:
                        raise ValueError(f'cache URL mismatch: {cached}')
                    for study in json.loads(response['text'])['studies']:
                        flat = T.flat(study)
                        studies[flat['nct']] = dict(flat, _accessed_at=response['accessed_at'], _context_accessed_at=response['accessed_at'])
        updated = False
        for action in data['actions']:
            if action['section'] != 'clinical_trial_eligibility' or not action.get('nct'):
                continue
            old = copy.deepcopy(action)
            nct = action['nct']
            study = studies[nct]
            context_path = context_dir / f'{nct}.json'
            if context_path.exists():
                context = json.loads(context_path.read_text())
                full = T.flat(context['record'])
                if full['nct'] != nct or full['criteria'] != study['criteria']:
                    raise ValueError(f'context and saved eligibility differ: {nct}')
                study['population_groups'] = full['population_groups']
                study['_context_accessed_at'] = context['accessed_at']
            items = {it['id']: it for it in T.split_criteria(study['criteria'])}
            for row in action['requirements']:
                text = C.subject_context(items[row['item']], items) if row['item'] in items else row['requirement']
                if row.get('fact') in ('diagnosis', *C.GENOTYPE_FACTS) and C.relative_subject(text):
                    # This comparison intentionally cannot infer any relative's disease from the patient's.
                    st, fact, note, details = C.evaluate({'fact': row['fact'], 'quote': row['requirement'], 'criterion_text': text},
                                                       {}, {}, {}, [])
                    row.update(patient_status=st, patient_fact=fact, note=note,
                               result=LG.requirement_result(row['kind'], st), details=details)
                    led.note_missing(fact['field'], action['label'], row['requirement'][:120], '3b')
            lines = [dict(row, text=row['requirement'], details=dict(row.get('details', {}))) for row in action['requirements']]
            C.population_alternatives(study, lines)
            for row, line in zip(action['requirements'], lines):
                if 'alternative' not in line:
                    continue
                row['alternative'] = line['alternative']
                relation = copy.deepcopy(line['details']['population_relation'])
                for proof in relation['sources']:
                    source_text = '\n'.join(g['description'] for g in study['population_groups'] if 'description' in g)
                    ev = LG.sourced(f"{nct} population relation criterion: {proof['quote'][:120]}",
                                    action['section'], action['applies_to'], {'type': 'nct', 'id': nct, 'url': T.study_url(nct)},
                                    proof['quote'], source_text, study['_context_accessed_at'],
                                    retrieved_by='3b clinicaltrials.gov', action={'key': action['action_key']})
                    led.add(ev)
                    action['evidence_ids'] = sorted(set(action['evidence_ids']) | {ev['id']})
                    proof['evidence_id'] = ev['id']
                row['details'] = dict(line['details'], population_relation=relation)
            for bid in action['applies_to']:
                status, chosen = LG.status_of(action['requirements'], bid)
                mine = [r for r in action['requirements'] if bid in r['applies_to']]
                if chosen and LG.status_from([r['result'] for r in mine if r.get('alternative')==chosen])=='applicable':
                    mine = [r for r in mine if not r.get('alternative') or r['alternative']==chosen]
                if status != action['status_by_branch'][bid]['status']:
                    fail = next((r for r in mine if r['result']=='fail'), None)
                    unknown = sorted({r['patient_fact']['field'] for r in mine if r['result']=='unknown'})
                    reason = 'not met: '+fail['requirement'] if fail else 'depends on: '+'; '.join(unknown) if unknown else 'registry and assessed criteria met'
                    action['status_by_branch'][bid] = {'status': status, 'reason': reason}
            if action != old:
                changes.append({'case': cid, 'nct': nct, 'before': old, 'after': copy.deepcopy(action)})
                updated = True
        if updated:
            data['evidence'] = list(led.evidence.values())
            data['checks'] = led.checks()
            failed = [check for check in data['checks'] if check['status']=='fail']
            if failed:
                raise ValueError(f'{cid} ledger checks failed: {failed}')
            data['_meta']['subject_review_update'] = {'at': int(time.time()), 'subject_only': True,
                                                       'source_ledger_sha256': hashlib.sha256(original).hexdigest()}
            (destination / f'{cid}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1)+'\n')
        else:
            (destination / f'{cid}.json').write_bytes(original)
    return changes


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--destination', type=Path, required=True)
    ap.add_argument('--context-dir', type=Path, required=True)
    args = ap.parse_args()
    changes = replay(args.source, args.destination, args.context_dir)
    (args.destination.parent / 'subject-changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2))
    print(json.dumps({'changed_trials': len(changes), 'trials': [(x['case'], x['nct']) for x in changes]}, ensure_ascii=False))

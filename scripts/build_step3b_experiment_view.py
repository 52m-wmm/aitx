"""Export one completed experiment for the viewer. Never runs screening or writes ledgers.

python scripts/build_step3b_experiment_view.py --source out/<experiment>
Optional --prerequisites DIR and --presentation JSON retain reviewed card summaries.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx.evidence.trials import CATEGORIES, classify_pathway, clinical_priority_key as priority_key


def pathway(candidate, protocol, facts):
    classification = classify_pathway(protocol)
    rank, therapeutic = classification['category_rank'], classification['therapeutic']
    if facts is not None:
        known, pending = facts['known_conditions'], facts['pending_prerequisites']
        scope = facts['cohort_note']
        target_supported = facts['target_path_supported']
    else:
        from scripts.step3b_view import cohort_display
        rows = candidate['prerequisites']
        cohorts = cohort_display(rows)
        focused = cohorts['focused'] if cohorts['preferred'] else rows
        known = list(dict.fromkeys(r['prerequisite'] for r in focused if r['status'] == 'confirmed')) if rows else None
        pending = list(dict.fromkeys(r['prerequisite'] for r in focused if r['status'] == 'unknown')) if rows else None
        target_supported = bool(cohorts['supported'])
        scope = ('替代队列有已知依据；仍需确认开放队列及其余资格' if target_supported else
                 '年龄等部分条件有依据；目标诊断/队列及开放情况待确认' if known else
                 '目标队列及开放情况待确认')
    state = ('可能适用目标人群干预路径；需确认开放队列' if therapeutic and target_supported else
             '治疗干预路径存在；目标队列待确认' if therapeutic else
             '仅诊断性测定/生物标志物路径' if rank == 2 else
             '仅观察性/登记路径' if rank == 3 else '研究性质及目标路径待核实')
    return {**classification, 'status': state,
            'therapeutic': therapeutic, 'target_path_supported': target_supported,
            'cohort_note': scope, 'known_conditions': known, 'pending_prerequisites': pending}


def read(path):
    return Path(path).read_text() if Path(path).suffix == '.txt' else json.loads(Path(path).read_text())


def export_ledger(ledger_path: Path, destination: Path) -> Path:
    """Compatibility export; formal card assembly lives with Step 3b."""
    from aitx import runmeta
    from aitx.step3.b.presentation import ledger_view
    ledger = read(ledger_path)
    result = ledger_view(ledger, runmeta.find_case(ledger['patient_id']), ledger_path)
    folder = destination/ledger['patient_id']
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/'result.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return path


def export(source: Path, destination: Path, prerequisites: Path | None = None,
           presentation: Path | None = None, pathway_review: Path | None = None) -> Path:
    patient = read(source / 'patient.json')
    case_id = patient['id']
    rows = read(prerequisites / 'prerequisites.json') if prerequisites else []
    summaries = {s['nct_id']: s for s in read(prerequisites / 'summary.json')} if prerequisites else {}
    copy = read(presentation) if presentation else {}
    reviews = read(source / 'manual-conflict-review.json')
    facts = read(pathway_review) if pathway_review else None
    if facts is not None and facts['case_id'] != case_id:
        raise ValueError('Pathway review belongs to another case')
    studies = read(source / 'studies.json')
    candidates = []
    for candidate in read(source / 'candidates.json'):
        nct = candidate['nct_id']
        requirements = [r for r in rows if r['nct_id'] == nct]
        if prerequisites:
            known, pending = copy[nct] if nct in copy else (
                candidate['reason'], summaries[nct]['unknown_key_medical_prerequisites'])
            supported = summaries[nct]['known_supported_full_clinical_alternative']
        else:
            known, pending = candidate['matched_evidence'], [candidate['missing_information']]
            supported = None  # This experiment did not audit full clinical pathways.
        candidates.append({**candidate, 'card_known': known, 'card_pending': pending,
                           'prerequisites': requirements, 'clinical_path_supported': supported,
                           'conflict_reviews': [r for r in reviews if r['nct_id'] == nct],
                           'eligibility_text': read(source / 'trials' / nct / 'eligibility.txt')})
        candidates[-1]['pathway'] = pathway(candidates[-1], studies[nct]['protocolSection'],
                                           facts['trials'][nct] if facts else None)
    candidates.sort(key=priority_key)
    excluded = []
    for record in read(source / 'excluded.json'):
        if 'raw_conflicts' in record:
            evidence = [{'trial_quote': c['trial_rule_quote'], 'patient_quote': c['patient_fact_quote']}
                        for c in record['raw_conflicts']]
        else:
            evidence = [{k: record[k] for k in ('trial_quote', 'patient_quote')}]
        excluded.append({**record, 'display_evidence': evidence})
    result = {'case_id': case_id, 'patient': patient, 'source': str(source.resolve()),
              'counts': read(source / 'counts.json'), 'candidates': candidates, 'excluded': excluded}
    case_directory = destination / case_id
    case_directory.mkdir(parents=True, exist_ok=True)
    path = case_directory / 'result.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    report = ['# 临床试验路径与排序', '',
              f"{sum(c['pathway']['therapeutic'] for c in candidates)} 项治疗性干预路径；"
              f"{sum(c['pathway']['therapeutic'] and c['pathway']['target_path_supported'] for c in candidates)} 项有目标队列依据。仍需确认开放及完整资格。", '',
              '排序：研究性质 → 已知条件条目数降序 → 待确认前提条目数升序 → NCT ID。未逐条审核的数据不按零条处理。', '',
              '|NCT|研究性质|路径状态|队列说明|已知/待确认条目|', '|---|---|---|---|---|']
    for c in candidates:
        p = c['pathway']
        counts = '/'.join(str(len(p[k])) if p[k] is not None else '尚未逐条审核' for k in ('known_conditions', 'pending_prerequisites'))
        report.append(f"|{c['nct_id']}|{p['category']}|{p['status']}|{p['cohort_note']}|{counts}|")
    path.with_name('report.md').write_text('\n'.join(report) + '\n')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--source', type=Path)
    inputs.add_argument('--ledger', type=Path)
    parser.add_argument('--prerequisites', type=Path)
    parser.add_argument('--presentation', type=Path)
    parser.add_argument('--pathway-review', type=Path)
    parser.add_argument('--destination', type=Path, default=ROOT / 'out' / '3b')
    args = parser.parse_args()
    print(export_ledger(args.ledger, args.destination) if args.ledger else
          export(args.source, args.destination, args.prerequisites, args.presentation, args.pathway_review))


if __name__ == '__main__':
    main()

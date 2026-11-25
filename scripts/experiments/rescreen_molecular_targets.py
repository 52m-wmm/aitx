"""Recheck saved candidate studies with the approved single-target rule; no API or LLM calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aitx.evidence import trials as T
from aitx.step3.b import criteria as C
from scripts.experiments import step3b_conflict_screening_mvp as E


def review_molecular_answer(answer, sample, conflict):
    _, quotes = E.decide(3, answer, sample)
    result = []
    for i, proposed in enumerate(answer['hard_conflicts']):
        accepted = (conflict is not None and proposed['axis'] == 'molecular'
                    and quotes[i]['both_valid'] and proposed['other_cohort_applicable'] is False
                    and proposed['trial_rule_quote'] in conflict['trial_rule_quote']
                    and re.search(rf"\b{re.escape(conflict['target_gene'])}\b", proposed['trial_rule_quote']) is not None)
        result.append({'index': i, 'raw_conflict': proposed, 'quote_audit': quotes[i],
                       'semantic_confirmed': accepted, 'accepted_for_exclusion': accepted,
                       'review': conflict['reason'] if accepted else
                       '不能跨基因比较合子状态；分子冲突须由完整单靶点要求及确诊病因共同证实。'})
    return result


def rescreen(source, destination, diagnosed_genes):
    patient = E.read(source/'patient.json')
    context = patient['patient']['clinical_context']
    variants = {v['gene'] for v in patient['patient']['genotype']}
    for gene in diagnosed_genes:
        if gene not in variants or not re.search(rf'diagnosed with\s+{re.escape(gene)}\s+deficiency', context, re.I):
            raise ValueError('This raw-case adapter requires an explicit matching gene and diagnosed deficiency; use confirmed Step 2 facts for other case formats.')
    destination.mkdir(exist_ok=False)
    for name in ('patient.json', 'studies.json', 'code-screen.json'):
        shutil.copyfile(source/name, destination/name)
    shutil.copytree(source/'trials', destination/'trials')
    studies = E.read(source/'studies.json')
    candidates, excluded = [], E.read(source/'excluded.json')
    audit = E.read(source/'manual-conflict-review.json')
    changes = []
    for candidate in E.read(source/'candidates.json'):
        nct = candidate['nct_id']
        conflict = C.single_target_conflict(T.flat(studies[nct]), diagnosed_genes)
        if conflict is None:
            candidates.append(candidate)
            continue
        sample = E.read(source/'trials'/nct/'sample.json')
        answer = E.read(source/'trials'/nct/'parsed.json')
        reviewed = review_molecular_answer(answer, sample, conflict)
        audit = [r for r in audit if r['nct_id'] != nct] + [dict(r, nct_id=nct) for r in reviewed]
        patient_quote = context
        excluded.append({**candidate, 'decision': 'exclude', 'stage': 'code_molecular_target',
                         'trial_quote': conflict['trial_rule_quote'], 'patient_quote': patient_quote,
                         'reason': conflict['reason'], 'code_conflict': conflict,
                         'model_conflicts_review': reviewed})
        changes.append({'nct_id': nct, 'before': 'candidate', 'after': 'exclude', 'evidence': conflict})
    counts = E.read(source/'counts.json')
    counts.update(final_candidates=len(candidates), final_excluded=len(excluded),
                  code_molecular_exclusions=len(changes),
                  rejected_semantic_conflicts=sum(not r['semantic_confirmed'] for r in audit))
    for name, value in [('candidates', candidates), ('excluded', excluded), ('counts', counts),
                        ('manual-conflict-review', audit), ('decision-diff', changes)]:
        E.save(destination/(name+'.json'), value)
    E.save(destination/'replay.json', {'original_experiment':str(source.resolve()), 'diagnosed_genes':diagnosed_genes,
                                     'reused_original_llm_calls': counts['model_responses'], 'new_llm_calls':0,
                                     'new_llm_cost_usd':0, 'api_calls':0, 'rule':'single_target_conflict'})
    return changes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--destination', type=Path, required=True)
    ap.add_argument('--diagnosed-gene', action='append', required=True)
    args = ap.parse_args()
    print(json.dumps(rescreen(args.source, args.destination, args.diagnosed_gene), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

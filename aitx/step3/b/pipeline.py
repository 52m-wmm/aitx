"""Public Step 3b entry: search, screen, then assemble existing verdicts.

add_trials integrates with the full Step 3 pipeline; refresh_trials replaces only
3b in a saved Ledger. Disk publication belongs to results.run_case.
"""
from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor

from aitx.disease import extract as X, live as L
from aitx.evidence import ledger as LG, patient_matching as E, trials as T
from aitx.step3.b import rules, screening, records

SECTION = 'clinical_trial_eligibility'


def add_trials(led, case, step1, step2, use_cache=True):
    """One production route; code rejects known conflicts before any model call."""
    facts = E.facts(step1, step2)
    plans = {}
    for branch in [b for b in led.branches if b['diagnosis']]:
        names = E.disease_names(branch, step2)
        parents = L.mondo_parents(branch['id'], use_cache=use_cache) if branch['id'].startswith('MONDO:') else []
        family = list(dict.fromkeys(label.split(' or ')[0] for _, label in parents[:1]))
        genes = [branch['gene']] if rules.confirmed_target_gene(branch, case, step1, step2) else []
        plan = screening.plan(names, family, facts['age_months'], facts['sex'], genes, use_cache=use_cache)
        when = min(s['queried_at'] for s in plan['searches'])

        def fetch(study):
            return X._cached_chat(
                screening.messages(screening.sample(case, study)), 0, use_cache,
                prompt_version=screening.VERSION, call_params=screening.PARAMS)

        with ThreadPoolExecutor(max_workers=4) as pool:
            answers = dict(zip(
                (s['nct'] for s in plan['analysed']), pool.map(fetch, plan['analysed'])))
        studies = [(s, True) for s in plan['analysed']] + [(s, False) for s in plan['ineligible']]
        for study, needs_model in studies:
            study = dict(study, _accessed_at=when)
            answer, provenance, audits = {'hard_conflicts': []}, 'code', []
            if needs_model:
                payload = screening.sample(case, study)
                entry = answers[study['nct']]
                answer = X._parse(entry)['parsed']
                provenance = {
                    'llm': X.llm.config()['model'], 'served_model': entry['served_model'],
                    'call_id': entry['call_id'], 'prompt_version': screening.VERSION,
                }
                audits = [screening.verify(payload, conflict, study, facts, genes)
                          for conflict in answer['hard_conflicts']]
            records.record(led, study, branch['id'], facts, case, answer, provenance, audits)

        if not plan['analysed'] and not plan['ineligible']:
            negative = led.add(LG.negative(
                SECTION, [branch['id']], database='clinicaltrials.gov', endpoint=T.API,
                query='; '.join(str(r['query']) for r in plan['searches']), queried_at=when,
                n_results=plan['n_unique'], response_count=plan['n_unique'],
                excluded=[{'id': r['nct'], 'reason': r['reason'] + ': ' + r['detail']}
                          for r in plan['excluded']]))
            led.actions.append(LG.action_record(
                None, SECTION, 'None found', [branch['id']], [], [negative['id']],
                {branch['id']: '未检索到开放研究'}, searched_none=True))
        plans[branch['id']] = {
            **{k: v for k, v in plan.items() if k not in ('analysed', 'ineligible')},
            'analysed': [s['nct'] for s in plan['analysed']],
            'ineligible': [s['nct'] for s in plan['ineligible']],
        }
    led.trial_searches = plans
    led.mark_searched(SECTION)


def refresh_trials(previous: dict, case: dict, step1: dict, step2: dict) -> dict:
    """Refresh only 3b, explicitly preserving the accepted outputs of other sections."""
    if previous['schema_version'] != LG.SCHEMA_VERSION or previous['patient_id'] != case['id']:
        raise ValueError('Expected the same case and current Ledger schema')
    led = LG.Ledger(case['id'], previous['branches'])
    for name in vars(led):
        if name == 'evidence':
            led.evidence = {e['id']: copy.deepcopy(e) for e in previous['evidence']}
        else:
            setattr(led, name, copy.deepcopy(previous[name]))
    frozen_actions = [a for a in led.actions if a['section'] != SECTION]
    retained_context = json.dumps(
        frozen_actions + [e for e in previous['evidence'] if e['section'] != SECTION], ensure_ascii=False)
    led.evidence = {eid: e for eid, e in led.evidence.items()
                    if e['section'] != SECTION or eid in retained_context}
    led.actions = list(frozen_actions)
    led.missing_information = [m for m in led.missing_information if m['asked_by'] != '3b']
    add_trials(led, case, step1, step2)
    result = led.to_dict()
    if [a for a in result['actions'] if a['section'] != SECTION] != frozen_actions:
        raise ValueError('A frozen non-3b action changed')
    result['report_context'] = copy.deepcopy(previous['report_context'])
    result['branches_dropped'] = copy.deepcopy(previous['branches_dropped'])
    result['refresh_scope'] = {
        'updated': ['3b'], 'reused': ['step1', 'step2', '3a', '3c', '3d', '3e', 'report_context'],
    }
    result['ok'] = all(c['status'] != 'fail' for c in result['checks'])
    return result

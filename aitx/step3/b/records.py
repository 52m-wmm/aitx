"""Assemble screened studies into the shared Evidence Ledger.

Consumes existing code checks and verified model conflicts; never calls a model
or performs a search. This is the only Step 3b study-to-Ledger implementation.
"""
from __future__ import annotations

from aitx.evidence import ledger as LG, trials as T
from aitx.step3.b import rules, screening

SECTION = 'clinical_trial_eligibility'


def record(led, study, branch, facts, case, answer, provenance, audits):
    nct = study['nct']
    source = {'type': 'nct', 'id': nct, 'url': T.study_url(nct)}
    payload = screening.sample(case, study)
    requirements = []

    def add(text, kind, status, fact, note, source_text, produced='code'):
        evidence = led.add(LG.sourced(
            f'{nct}: screening criterion {text[:100]}', SECTION, [branch], source,
            text, source_text, study['_accessed_at'], produced_by=produced,
            retrieved_by='3b conflict-only screening', action={'key': f'trial:{nct}'}))
        requirement = LG.requirement(
            f'r{len(requirements) + 1}', kind, text, evidence['id'], fact, status, [branch], note)
        requirement['fact'] = fact['field']
        requirements.append(requirement)
        if requirement['result'] == 'unknown':
            led.note_missing(fact['field'], nct, text[:120], '3b')

    for row in rules.registry_lines(study, facts):
        note = row['note']
        for check in study['prefilter']['checks']:
            if check['field'] == row['patient_fact']['field'] and 'note' in check:
                note = check['note']
                break
        add(row['text'], row['kind'], row['patient_status'], row['patient_fact'],
            note, rules.registry_source(study))
    for row in rules.enrollment_note_lines(study, facts):
        add(row['text'], row['kind'], row['patient_status'], row['patient_fact'],
            row['note'], T.unescape(study['criteria']))
    target = study['code_molecular_conflict']
    if target:
        own = next(v for v in facts['variants'] if v['gene'] in target['patient_genes'])
        add(target['trial_rule_quote'], 'inclusion', 'does_not_satisfy',
            {'field': 'molecular target', 'value': own['gene'], 'quote': own['quote'], 'step': 1},
            target['reason'], study['title'] if target['quote_source'] == 'title' else study['criteria'])
    for audit in audits:
        if audit['accepted']:
            conflict = audit['conflict']
            add(conflict['trial_rule_quote'], 'exclusion', 'satisfies',
                {'field': conflict['axis'], 'value': conflict['patient_fact_quote'],
                 'quote': conflict['patient_fact_quote'], 'step': '3b'},
                audit['basis'], payload['trial_text'], provenance)

    # No confirmed conflict is not proof of full eligibility.
    if not any(r['result'] == 'fail' for r in requirements):
        add(study['criteria'], 'other', 'unknown',
            {'field': 'other trial criteria', 'value': None, 'quote': None, 'step': None},
            '尚未证实完整入组资格，需研究团队逐项核实', study['criteria'])
    ids = list(dict.fromkeys(r['requirement_evidence'] for r in requirements))
    failures = [r for r in requirements if r['result'] == 'fail']
    if failures:
        first = failures[0]
        reason = ('年龄条件与病例不符' if first['fact'] == 'age' else
                  '性别条件与病例不符' if first['fact'] == 'sex' else first['note'])
    else:
        reason = '未发现已证实硬冲突；仍有资格条件待核实'
    action = LG.action_record(
        f'trial:{nct}', SECTION, f"{study['acronym'] or study['title']} ({nct})",
        [branch], requirements, ids, {branch: reason})
    classification = T.classify_pathway(study['protocolSection'])
    action.update(
        nct=nct, title=study['title'], url=T.study_url(nct), study_type=study['study_type'],
        overall_status=study['status'], phases=study['phases'], interventions=study['interventions'],
        specific=study['specific'], relevance=study['relevance'], protocolSection=study['protocolSection'],
        screening={'method': screening.VERSION, 'raw_answer': answer,
                   'conflict_audits': audits, 'provenance': provenance},
        pathway={
            **classification,
            'known_conditions': [r['requirement'] for r in requirements if r['result'] == 'pass'],
            'pending_prerequisites': [r['requirement'] for r in requirements if r['result'] == 'unknown'],
            'status': ('治疗性干预研究；需核实队列和完整资格' if classification['therapeutic'] else
                       '测定或观察性研究；非治疗入组结论'),
            'target_path_supported': False, 'cohort_note': '完整病例与招募原文已用于初筛，剩余条件须研究团队核实',
        })

    # Keep a single action per study; preserve each diagnosis branch's verdict.
    existing = next((a for a in led.actions if a['action_key'] == action['action_key']), None)
    if existing is None:
        led.actions.append(action)
    else:
        for requirement in requirements:
            requirement['id'] = f"r{len(existing['requirements']) + 1}"
            existing['requirements'].append(requirement)
        existing['applies_to'] = sorted(set(existing['applies_to'] + [branch]))
        existing['evidence_ids'] = sorted(set(existing['evidence_ids'] + ids))
        existing['status_by_branch'].update(action['status_by_branch'])
        existing['screening'].setdefault('other_branch_audits', {})[branch] = action['screening']

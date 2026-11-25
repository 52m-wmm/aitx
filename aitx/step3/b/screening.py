"""Search planning and conflict verification; no model calls or Ledger mutation.

The pipeline supplies model responses. Missing facts, invalid quotes and
unverified proposed conflicts retain the study for professional screening.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from aitx.evidence import trials as T
from aitx.step3.b import rules

PROMPT = Path(__file__).with_name('screening_prompt.txt').read_text()
VERSION = '3b-conflict-screen-v1'
PARAMS = {'temperature': 0, 'max_tokens': 4096,
          'response_format': {'type': 'json_object'}, 'thinking': {'type': 'disabled'}}
# Preserve the existing review binding/location; storage migration cannot alter verdicts.
REVIEW_DIR = Path(__file__).resolve().parents[3]/'.cache/trial-conflict-reviews'


def sample(case, study):
    """Keep the complete case and source text; this serialization defines cache identity."""
    protocol = study['protocolSection']
    eligibility = protocol['eligibilityModule']
    shared = {
        'title': study['title'], 'status': study['status'],
        'eligibility_metadata': {k: v for k, v in eligibility.items()
                                 if k not in ('eligibilityCriteria', 'studyPopulation')},
    }
    if 'studyPopulation' in eligibility:
        shared['studyPopulation'] = eligibility['studyPopulation']
    if 'armsInterventionsModule' in protocol:
        shared['armsInterventionsModule'] = protocol['armsInterventionsModule']
    return {
        'case_id': case['id'], 'nct_id': study['nct'],
        'patient_text': json.dumps(case, ensure_ascii=False, indent=2),
        'trial_text': ('Registry context (verbatim field values):\n'
                       + json.dumps(shared, ensure_ascii=False, indent=2)
                       + '\n\nEligibilityCriteria (verbatim):\n' + eligibility['eligibilityCriteria']),
    }


def messages(payload):
    return [
        {'role': 'system', 'content': PROMPT},
        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, indent=2)
                                  + '\nReturn strictly valid JSON.'},
    ]


def review_key(payload, conflict):
    return hashlib.sha256(json.dumps(
        [payload, conflict], ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def quote_checks(payload, conflict):
    norm = lambda text: ' '.join(text.split()).casefold()
    return {
        'patient_quote_valid': (bool(norm(conflict['patient_fact_quote']))
                                and norm(conflict['patient_fact_quote']) in norm(payload['patient_text'])),
        'trial_quote_valid': (bool(conflict['trial_rule_quote'].strip())
                              and conflict['trial_rule_quote'] in payload['trial_text']),
    }


def verify(payload, conflict, study, facts, diagnosed_genes):
    """Quotes alone do not prove a conflict; require existing deterministic proof or a bound review."""
    proof = quote_checks(payload, conflict)
    axes = ('preamble_or_cohort', 'age_sex', 'molecular', 'clinical_history')
    if conflict['axis'] not in axes or type(conflict['other_cohort_applicable']) is not bool:
        raise ValueError('Invalid conflict schema')
    accepted = False
    basis = '证据或适用范围尚不能独立确认，保留人工复核'
    if all(proof.values()) and not conflict['other_cohort_applicable']:
        if conflict['axis'] == 'molecular':
            target = rules.single_target_conflict(study, diagnosed_genes)
            accepted = (target is not None
                        and conflict['trial_rule_quote'] in target['trial_rule_quote']
                        and re.search(rf"\b{re.escape(target['target_gene'])}\b",
                                      conflict['trial_rule_quote']) is not None)
            if accepted:
                basis = target['reason']
        elif conflict['axis'] in ('age_sex', 'preamble_or_cohort'):
            pre = prefilter(study, facts['age_months'], facts['sex'])
            accepted = any(c['result'] == 'fail' and c['field'] in ('age', 'sex') for c in pre['checks'])
            accepted = accepted or any(
                (n['kind'] == 'inclusion' and n['patient_status'] == 'does_not_satisfy')
                or (n['kind'] == 'exclusion' and n['patient_status'] == 'satisfies')
                for n in rules.enrollment_note_lines(study, facts))
            # Compare simple global body age clauses without flattening cohort alternatives.
            if (not accepted and facts['age_months'] is not None
                    and not re.search(r'\bcohort|\b(?:part|group)\s*[A-Z0-9]\b', study['criteria'], re.I)):
                for item in T.split_criteria(study['criteria']):
                    if (item['kind'] != 'inclusion' or item['parent']
                            or conflict['trial_rule_quote'] not in item['text']):
                        continue
                    text = re.sub(r'^[\W_]*(?:patients?|participants?|subjects?)?\s*',
                                  '', T.unescape(item['text']), flags=re.I)
                    text = re.sub(r'\bage of\b', 'age', text, flags=re.I)
                    note = {'criteria': 'Note: Currently, the study is only enrolling ' + text}
                    rows = rules.enrollment_note_lines(note, facts)
                    accepted = any(r['patient_status'] == 'does_not_satisfy' for r in rows)
                    if accepted:
                        break
            if accepted:
                basis = '已知年龄/性别与完整适用范围内的强制要求冲突'
        cached = REVIEW_DIR/(review_key(payload, conflict) + '.json')
        if not accepted and cached.exists():
            reviewed = json.loads(cached.read_text())
            if reviewed['payload'] != payload or reviewed['conflict'] != conflict:
                raise ValueError('Review binding mismatch')
            accepted, basis = reviewed['accepted'], reviewed['basis']
    return {**proof, 'conflict': conflict, 'accepted': accepted, 'basis': basis}


def prefilter(study, age, sex):
    """Conflicting textual age ranges require review rather than an API-only exclusion."""
    pre = T.prefilter(study, age, sex)
    if age is not None:
        spans = [(T.age_months(f"{m['lo']} {m['unit']}"), T.age_months(f"{m['hi']} {m['unit']}"))
                 for m in rules._NOTE_RANGE.finditer(T.unescape(study['criteria']))]
        if any(lo <= age <= hi for lo, hi in spans):
            for check in pre['checks']:
                if check['field'] == 'age' and check['result'] == 'fail':
                    check.update(result='unknown', note='API年龄范围与正文可能适用的年龄范围不一致，需核实队列')
    results = [c['result'] for c in pre['checks']]
    pre['result'] = 'fail' if 'fail' in results else 'unknown' if 'unknown' in results else 'pass'
    return pre


def plan(names, family, age, sex, genes, *, use_cache=True):
    """Search, deduplicate and separate code conflicts from studies needing model review."""
    query_names = list(dict.fromkeys([names[0]] + family))
    searches = [T.search({
        'query.cond': name,
        'filter.overallStatus': 'RECRUITING,NOT_YET_RECRUITING,ENROLLING_BY_INVITATION',
    }, use_cache=use_cache) for name in query_names]
    seen = {s['nct']: s for response in reversed(searches) for s in response['studies']}
    analysed, ineligible, excluded = [], [], []
    for study in seen.values():
        if study['status'] not in ('RECRUITING', 'NOT_YET_RECRUITING', 'ENROLLING_BY_INVITATION'):
            excluded.append(T._ex(study, 'status', study['status']))
            continue
        pre = prefilter(study, age, sex)
        notes = rules.enrollment_note_lines(study, {'age_months': age, 'age_quote': None, 'sex': None})
        bad_note = any(
            (n['kind'] == 'inclusion' and n['patient_status'] == 'does_not_satisfy')
            or (n['kind'] == 'exclusion' and n['patient_status'] == 'satisfies') for n in notes)
        target = rules.single_target_conflict(study, genes)
        entry = {
            **study, 'prefilter': pre, 'code_molecular_conflict': target,
            'relevance': {'by': 'disease_or_family_query', 'name': query_names},
            'specific': T.specific(study, names, genes[0] if genes else ''),
        }
        (ineligible if pre['result'] == 'fail' or bad_note or target else analysed).append(entry)
    analysed.sort(key=lambda s: T.rank_key(s, names, genes[0] if genes else ''))
    return {
        'names': query_names, 'gene': genes[0] if genes else None,
        'searches': [{k: v for k, v in s.items() if k != 'studies'} for s in searches],
        'n_unique': len(seen), 'analysed': analysed, 'ineligible': ineligible, 'excluded': excluded,
        'over_cap': [], 'n_closed_relevant': 0, 'closed_listed': [],
        'parent_names': family, 'screening_method': VERSION,
    }

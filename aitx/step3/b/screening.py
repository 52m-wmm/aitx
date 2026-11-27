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
from aitx.step3.b import rules, search, guards, cohorts

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


def verify(payload, conflict, study, facts, patient_genes):
    """Quotes alone do not prove a conflict; require existing deterministic proof or a bound review."""
    proof = quote_checks(payload, conflict)
    axes = ('preamble_or_cohort', 'age_sex', 'molecular', 'clinical_history')
    if conflict['axis'] not in axes or type(conflict['other_cohort_applicable']) is not bool:
        raise ValueError('Invalid conflict schema')
    accepted = False
    cohort_check = None
    basis = '证据或适用范围尚不能独立确认，保留人工复核'
    if all(proof.values()) and not conflict['other_cohort_applicable']:
        if conflict['axis'] == 'molecular':
            target = rules.single_target_conflict(study, patient_genes)
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
            cohort_check = cohorts.evaluate(study, facts)
            if cohort_check is not None:
                accepted = cohort_check['all_conflict']
                basis = ('全部已识别招募队列均与患者已知年龄/性别冲突：' +
                         '、'.join(p['label'] for p in cohort_check['populations']) if accepted else
                         '至少一个招募队列未证实冲突，或登记范围存在差异，保留核实')
        if not accepted:
            patient = json.loads(payload['patient_text'])['patient']
            supported = guards.core_conflict(study, facts, patient, conflict)
            if supported:
                accepted = True
                basis = '采纳有原文及患者事实支持的核心冲突（' + supported + '）：' + conflict['reason']
        cached = REVIEW_DIR/(review_key(payload, conflict) + '.json')
        if not accepted and cached.exists():
            reviewed = json.loads(cached.read_text())
            if reviewed['payload'] != payload or reviewed['conflict'] != conflict:
                raise ValueError('Review binding mismatch')
            accepted, basis = reviewed['accepted'], reviewed['basis']
    audit = {**proof, 'conflict': conflict, 'accepted': accepted, 'basis': basis}
    if cohort_check is not None:
        audit['cohort_check'] = cohort_check
        if accepted and cohort_check['all_conflict']:
            audit['verified_trial_rule_quote'] = cohort_check['trial_quote']
    if conflict['axis'] == 'molecular':
        audit['reported_gene_evidence'] = [
            {'gene': v['gene'], 'quote': v['quote'], 'step': 1}
            for v in facts['variants']]
        audit['gene_evidence_scope'] = (
            '已报告变异仅证明相应基因事实；与试验要求的基因不同，不证明该基因检测阴性。'
            '按试验明确要求的疾病基因及队列范围核验，不限干预方式；其他冲突保留复核。')
    return audit


def filter_relevance(plan, case, facts, names):
    """Filter both queues before model calls, retaining evidence in the search audit."""
    for queue in ('analysed', 'ineligible'):
        retained = []
        for study in plan[queue]:
            rejection = guards.relevance(study, case['patient'], facts, names)
            if rejection is None:
                retained.append(study)
            else:
                plan['excluded'].append(rejection)
        plan[queue] = retained


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


def plan(names, family, age, sex, genes, *, search_genes=None, use_cache=True):
    """Search, deduplicate and separate code conflicts from studies needing model review."""
    query_names = search.condition_names(names + family,
        abbreviations=search.FAMILY_ABBREVIATIONS.intersection(family))
    search_genes = genes if search_genes is None else search_genes
    searches = [T.search(params, use_cache=use_cache)
                for params in search.queries(names, family, search_genes)]
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
            'relevance': {'by': 'disease_family_or_gene_query',
                          'queries': [r['query'] for r in searches
                                      if any(s['nct'] == study['nct'] for s in r['studies'])]},
            'specific': T.specific(study, names, genes[0] if genes else ''),
        }
        (ineligible if pre['result'] == 'fail' or bad_note or target else analysed).append(entry)
    analysed.sort(key=lambda s: T.rank_key(s, names, genes[0] if genes else ''))
    return {
        'names': query_names, 'gene': genes[0] if genes else None,
        'searches': [{k: v for k, v in s.items() if k != 'studies'} for s in searches],
        'n_unique': len(seen), 'analysed': analysed, 'ineligible': ineligible, 'excluded': excluded,
        'over_cap': [], 'n_closed_relevant': 0, 'closed_listed': [],
        'parent_names': family, 'search_genes': search_genes, 'screening_method': VERSION,
    }

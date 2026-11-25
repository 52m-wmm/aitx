"""Independent Step 3b screening comparison; default is prepare-only, --run makes paid calls.

Example: .venv/bin/python scripts/experiments/step3b_conflict_screening_mvp.py --run
Use --samples PATH to replace the frozen smoke JSON. No production ledger is written.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aitx import budget, llm, peak
from scripts import llm_cost

DEFAULT_SAMPLES = Path(__file__).with_name('step3b_conflict_screening_smoke.json')
# Frozen copy of out/step3b-phyox7-preamble-prescreen-20261124/prompt.txt.
D_PROMPT = Path(__file__).with_name('step3b_conflict_screening_d_prompt.txt')
D_PROMPT_SHA256 = '1d18780defd22d45286349fbae09a84aa3b9a88b66f5751bb3738b08a15f91c8'
REPEATS = 3
AXES = {'preamble_or_cohort', 'age_sex', 'molecular', 'clinical_history'}
CATEGORIES = {'preamble_conflict', 'hard_conflict', 'multi_cohort_or', 'missing_info'}
MINIMAL_PROMPT = '''Read the complete patient summary and trial text. If an explicitly known patient fact clearly violates a mandatory enrollment requirement and no alternative cohort applies, return exclude; otherwise return candidate. Do not infer missing information.
Return JSON: {"decision": "candidate" or "exclude", "reason": "..."}.'''
CONFLICT_PROMPT = 'You are a clinical trial eligibility conflict screener.\nYour ONLY task is to identify undeniable, direct hard conflicts between EXPLICITLY STATED patient facts and MANDATORY clinical trial eligibility requirements.\n\nCheck the entire trial text (INCLUDING any preamble or notes BEFORE "Inclusion Criteria") along these 4 axes ONLY:\n1. preamble_or_cohort: Current enrollment restrictions, closed cohorts/age groups, or active-enrollment notes in the preamble or eligibility text.\n2. age_sex: Explicit age or biological sex requirements/exclusions.\n3. molecular: Explicit required or excluded gene, variant type, or zygosity criteria.\n4. clinical_history: Direct conflict with a diagnosis, symptom, lab value, or treatment EXPLICITLY documented in the patient summary.\n\nSTRICT RULES:\n- MISSING INFORMATION = IGNORE. If a trial criterion asks for information not explicitly stated in the patient summary (e.g., unmentioned labs, prior therapies, dialysis, Visit 1 timing, consent), DO NOT evaluate it and DO NOT output it. Never infer or assume unstated facts.\n- CHECK ALTERNATIVE COHORTS (OR LOGIC). If the patient conflicts with one cohort/group (e.g., "unaffected relatives" or "adult cohort") but another cohort in the same trial may still apply (e.g., "affected patients" or "pediatric cohort"), set "other_cohort_applicable": true.\n- VERBATIM QUOTES ONLY. Both "patient_fact_quote" and "trial_rule_quote" MUST be exact substrings copied from the input texts.\n- If no undeniable hard conflict exists, return {"hard_conflicts": []}.\n\nOutput strictly valid JSON matching this schema:\n{\n  "hard_conflicts": [\n    {\n      "axis": "preamble_or_cohort | age_sex | molecular | clinical_history",\n      "patient_fact_quote": "exact substring from patient summary",\n      "trial_rule_quote": "exact substring from trial text",\n      "other_cohort_applicable": false,\n      "reason": "one concise sentence explaining the direct conflict"\n    }\n  ]\n}'


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load_samples(path):
    samples = read(path)
    if not isinstance(samples, list) or not samples:
        raise ValueError('samples must be a nonempty JSON list')
    seen = set()
    for s in samples:
        for field in ('case_id', 'nct_id', 'patient_text', 'trial_text', 'expected', 'category'):
            if not isinstance(s[field], str) or not s[field].strip():
                raise ValueError(f'empty/non-string sample field: {field}')
        if s['expected'] not in ('candidate', 'exclude') or s['category'] not in CATEGORIES:
            raise ValueError('invalid expected/category')
        identity = (s['case_id'], s['nct_id'])
        if identity in seen:
            raise ValueError(f'duplicate sample: {identity}; use distinct case_id for variants')
        seen.add(identity)
    return samples


def prompts():
    d = D_PROMPT.read_text()
    if hashlib.sha256(d.encode()).hexdigest() != D_PROMPT_SHA256:
        raise ValueError('frozen experiment D prompt has changed')
    return {1: MINIMAL_PROMPT, 2: d, 3: CONFLICT_PROMPT}


def messages(system, sample):
    # Common format instruction is required by json_object mode; clinical rules stay in System.
    payload = {k: sample[k] for k in ('case_id', 'nct_id', 'patient_text', 'trial_text')}
    return [{'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, indent=2)
             + '\nReturn strictly valid JSON.'}]


def normalized(text):
    return ' '.join(text.split()).casefold()


def decide(group, answer, sample):
    if group != 3:
        decision = answer['decision']
        if decision not in ('candidate', 'exclude'):
            raise ValueError('invalid decision')
        if group == 1 and (not isinstance(answer['reason'], str) or not answer['reason'].strip()):
            raise ValueError('missing reason')
        return decision, []
    conflicts = answer['hard_conflicts']
    if not isinstance(conflicts, list):
        raise ValueError('hard_conflicts must be a list')
    audit = []
    for conflict in conflicts:
        if conflict['axis'] not in AXES or type(conflict['other_cohort_applicable']) is not bool:
            raise ValueError('invalid conflict axis or non-boolean cohort flag')
        for key in ('patient_fact_quote', 'trial_rule_quote', 'reason'):
            if not isinstance(conflict[key], str):
                raise ValueError(f'non-string {key}')
        if not conflict['reason'].strip():
            raise ValueError('empty conflict reason')
        pq, tq = conflict['patient_fact_quote'], conflict['trial_rule_quote']
        patient_valid = bool(normalized(pq)) and normalized(pq) in normalized(sample['patient_text'])
        trial_valid = bool(tq.strip()) and tq in sample['trial_text']
        audit.append({'conflict': conflict, 'patient_quote_valid': patient_valid,
                      'trial_quote_valid': trial_valid, 'both_valid': patient_valid and trial_valid,
                      'exclude_evidence': patient_valid and trial_valid
                      and conflict['other_cohort_applicable'] is False})
    return ('exclude' if any(a['exclude_evidence'] for a in audit) else 'candidate'), audit


def fraction(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'rate': numerator / denominator if denominator else None}


def summarize(samples, records):
    result = {}
    for group in (1, 2, 3):
        rows = [r for r in records if r['group'] == group]
        if len(rows) != len(samples) * REPEATS:
            raise ValueError('incomplete experiment; do not report partial data as complete')
        candidates = [r for r in rows if r['expected'] == 'candidate']
        excludes = [r for r in rows if r['expected'] == 'exclude']
        full_same = decision_same = 0
        for i in range(len(samples)):
            runs = [r for r in rows if r['sample_index'] == i]
            if sorted(r['repeat'] for r in runs) != [1, 2, 3]:
                raise ValueError('missing/duplicate repeat')
            full_same += len({json.dumps(r['answer'], sort_keys=True, ensure_ascii=False) for r in runs}) == 1
            decision_same += len({r['decision'] for r in runs}) == 1
        quotes = [a for r in rows for a in r['quote_audit']]
        result[group] = {
            'FER': fraction(sum(r['decision'] == 'exclude' for r in candidates), len(candidates)),
            'hard_conflict_recall': fraction(sum(r['decision'] == 'exclude' for r in excludes), len(excludes)),
            'full_json_consistency': fraction(full_same, len(samples)),
            'decision_consistency': fraction(decision_same, len(samples)),
            'quote_pair_pass_rate': fraction(sum(a['both_valid'] for a in quotes), len(quotes)),
            'individual_quote_pass_rate': fraction(sum(a['patient_quote_valid'] + a['trial_quote_valid'] for a in quotes), 2 * len(quotes)),
        }
    return result


def render_table(metrics):
    def cell(r):
        return 'N/A (0 denominator)' if r['rate'] is None else f"{r['rate']:.1%} ({r['numerator']}/{r['denominator']})"
    lines = ['| Group | FER ↓ | Hard-conflict recall ↑ | 3-run full JSON consistency | Decision consistency | G3 quote pairs |',
             '|---|---|---|---|---|---|']
    for group, m in metrics.items():
        lines.append('| ' + str(group) + ' | ' + ' | '.join(cell(m[k]) for k in
                     ('FER', 'hard_conflict_recall', 'full_json_consistency', 'decision_consistency'))
                     + ' | ' + (cell(m['quote_pair_pass_rate']) if group == 3 else '—') + ' |')
    return '\n'.join(lines)


def run_experiment(samples, systems, output, params):
    records = []
    cfg = llm.config()
    for group in (1, 2, 3):
        for i, sample in enumerate(samples):
            for repeat in range(1, REPEATS + 1):
                d = output / f'group-{group}' / f'sample-{i:02d}' / f'run-{repeat}'
                d.mkdir(parents=True, exist_ok=False)
                msgs = messages(systems[group], sample)
                body = {'model': cfg['model'], 'messages': msgs, **params}
                if llm.STREAM:
                    body.update(stream=True, stream_options={'include_usage': True})
                save(d / 'request.json', {'url': cfg['base_url'] + '/chat/completions', 'body': body})
                peak.check_before_call()
                budget.check_before_call()
                reserve = llm_cost.request_reservation(msgs, params['max_tokens'], time.time())
                if budget.cap() is not None and budget.spent_today() + reserve > budget.cap():
                    raise budget.OverBudget('remaining daily cap cannot cover next request reservation')
                save(d / 'started.json', {'timestamp': time.time(), 'reservation_usd': reserve})
                print(f'Group {group} {sample["case_id"]}/{sample["nct_id"]} repeat {repeat}/3', flush=True)
                try:
                    response = llm.chat(msgs, **params)
                except urllib.error.HTTPError as exc:
                    save(d / 'error.json', {'status': exc.code, 'body': exc.read().decode(), 'retry': False})
                    raise
                save(d / 'response.json', response)
                if response['choices'][0]['finish_reason'] != 'stop':
                    raise ValueError(f'incomplete response at {d}; no retry')
                # Invalid JSON/schema stops; it is never silently counted as candidate.
                answer = json.loads(response['choices'][0]['message']['content'])
                decision, audit = decide(group, answer, sample)
                record = {'group': group, 'sample_index': i, 'repeat': repeat,
                          'case_id': sample['case_id'], 'nct_id': sample['nct_id'],
                          'expected': sample['expected'], 'category': sample['category'],
                          'answer': answer, 'decision': decision, 'quote_audit': audit}
                save(d / 'result.json', record)
                records.append(record)
                with (output / 'results.jsonl').open('a') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples', '--input', type=Path, default=DEFAULT_SAMPLES)
    ap.add_argument('--output', type=Path, default=ROOT / 'out/step3b-conflict-mvp')
    ap.add_argument('--max-tokens', type=int, default=4096)
    ap.add_argument('--run', action='store_true', help='make the paid model calls; otherwise prepare only')
    args = ap.parse_args()
    if args.max_tokens <= 0:
        raise ValueError('max-tokens must be positive')
    samples, systems = load_samples(args.samples), prompts()
    params = {'temperature': 0, 'max_tokens': args.max_tokens,
              'response_format': {'type': 'json_object'}, 'thinking': {'type': 'disabled'}}
    output = args.output / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'samples.json', samples)
    for group, system in systems.items():
        (output / f'group-{group}-system.txt').write_text(system)
    jobs = [messages(systems[g], s) for g in systems for s in samples]
    save(output / 'plan.json', {'sample_file': str(args.samples.resolve()), 'samples': len(samples),
         'groups': 3, 'repeats': REPEATS, 'calls': len(jobs) * REPEATS, 'params': params,
         'reservation_usd': REPEATS * sum(llm_cost.request_reservation(m, args.max_tokens, time.time()) for m in jobs),
         'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'mode': 'run' if args.run else 'prepare-only',
         'metric_definitions': 'FER/recall per call; full JSON equality ignores object key order/formatting, preserves array order; N/A for zero denominator'})
    print(f'Plan: {len(samples)} samples × 3 groups × 3 repeats = {len(jobs) * REPEATS} calls; {output}')
    if not args.run:
        print('Prepared only; no API calls. Add --run to execute.')
        return
    if not llm.config()['api_key']:
        raise RuntimeError('export DEEPSEEK_API_KEY before --run; do not put credentials in samples/logs')
    peak.guard()
    records = run_experiment(samples, systems, output, params)
    metrics = summarize(samples, records)
    save(output / 'metrics.json', metrics)
    table = render_table(metrics)
    (output / 'report.md').write_text('# Step 3b conflict-screening MVP\n\n' + table
        + '\n\nFER and recall use individual calls, not majority vote. Consistency uses samples with all three runs.\n'
        + 'Quote-pair validity only checks provenance, not medical correctness; no-conflict output gives N/A, not 100%.\n'
        + 'No final enrollment eligibility is established. Raw requests/responses and decisions remain in each run directory.\n')
    print(table)


if __name__ == '__main__':
    main()

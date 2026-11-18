"""Independent Step 2 experiment; production rules and outputs remain untouched."""
from __future__ import annotations
import argparse
import difflib
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aitx import budget, caseinput, http, llm, peak, session
from aitx.disease import datasets as D, extract as X, pipeline, resolve
from scripts import llm_cost


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changes(old, new, path=''):
    if type(old) is not type(new):
        return [{'path': path, 'old': old, 'new': new}]
    if isinstance(old, dict):
        out = []
        for key in sorted(old.keys() | new.keys()):
            p = path + '/' + key
            if key not in old:
                out.append({'path': p, 'added': new[key]})
            elif key not in new:
                out.append({'path': p, 'removed': old[key]})
            else:
                out.extend(changes(old[key], new[key], p))
        return out
    if old != new:
        return [{'path': path, 'old': old, 'new': new}]
    return []


def diagnostic(r):
    p = r['primary']
    return {'top1': p['id'], 'status': p['status'],
            'branches': sorted([p['id']] + [a['id'] for a in p['alternatives']])}


def compare(old, new):
    return {'full_diff': changes(old, new),
            'hpo_diff': changes(old['phenotypes'], new['phenotypes']),
            'facts_diff': changes(old['patient_facts'], new['patient_facts']),
            'candidate_set_changed': sorted(c['key'] for c in old['candidates']) != sorted(c['key'] for c in new['candidates']),
            'diagnosis_changed': diagnostic(old) != diagnostic(new),
            'old_diagnosis': diagnostic(old), 'new_diagnosis': diagnostic(new)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    args = ap.parse_args()
    out = ROOT / 'runs/step2-stability-20261118'
    proposal = json.loads((out / 'proposal.json').read_text())
    for p, expected in proposal['code_and_input_sha256'].items():
        if sha(ROOT / p) != expected:
            raise ValueError('proposed version changed: ' + p)
    if args.execute:
        peak.guard()
    cases = {c['id']: c for c in json.loads((ROOT / 'data/cases/practice/official_examples.json').read_text())}
    selected = [cases[cid] for cid in proposal['cases']]
    references = {c['id']: json.loads((out / (c['id']+'.reference.json')).read_text()) for c in selected}
    files_by_case = {}
    for cid, reference in references.items():
        files = {}
        for entry in reference['sources_manifest']:
            name = entry['name']
            f = D._load_meta(D.DATA_DIR / name / entry['snapshot'])
            if f is None or sha(f.path) != entry['sha256']:
                raise ValueError('missing or changed fixed dataset: ' + name)
            files[name] = f
        files_by_case[cid] = files
    # No database network access is permitted, including cache misses swallowed by live.py.
    frozen = {}
    locked = False
    def fixed_get(url, *, headers=None, **kwargs):
        p = http._key(url, headers)
        key = str(p)
        if key not in frozen:
            if locked or not p.exists():
                raise FileNotFoundError('fixed HTTP input missing: ' + url)
            frozen[key] = json.loads(p.read_text())
        d = frozen[key]
        return http.Fetched(d['url'], d['text'], d['accessed_at'], True)
    http.get = fixed_get
    resources = {}
    grouped = {}
    genes = {v['gene'] for c in selected for v in c['patient']['genotype']}
    for cid, files in files_by_case.items():
        key = tuple((n, f.sha256) for n, f in sorted(files.items()))
        if key not in grouped:
            D.ensure_all = lambda files=files: files
            grouped[key] = resolve.load_resources(genes)
        resources[cid] = grouped[key]
    original_chat = llm.chat
    def no_chat(*a, **kw):
        raise llm.CacheOnly('preflight is cache only')
    llm.chat = no_chat
    step1 = {c['id']: json.loads((ROOT / 'out/step1' / (c['id']+'.json')).read_text()) for c in selected}
    fixed_results = {}
    for case in selected:
        cid = case['id']
        fixed_results[cid] = pipeline.run_case(case, resources[cid], step1=step1[cid])
        if not fixed_results[cid]['ok']:
            raise ValueError('preflight self-check failed: ' + cid)
    locked = True
    dump(out/'fixed_http.json', frozen)
    dump(out/'fixed_inputs.json', {'datasets': {cid:[f.manifest_entry() for f in files.values()] for cid,files in files_by_case.items()}, 'cases': selected, 'step1': step1})
    dump(out/'fixed_reference.json', fixed_results)
    dump(out/'reference_preflight_diff.json', {cid: compare(references[cid], r) for cid, r in fixed_results.items()})
    print('PREFLIGHT PASS; frozen HTTP responses', len(frozen), flush=True)
    if not args.execute:
        return
    llm.chat = original_chat
    llm.LOG = out/'llm_calls.jsonl'
    if llm.LOG.exists() or (out/'attempts.jsonl').exists():
        raise FileExistsError('experiment already started; do not overwrite or silently repeat')
    llm.LOG.touch()
    journal = out/'attempts.jsonl'
    spent = 0.0
    def guarded_chat(messages, *, max_tokens=8192, tools=None, **kwargs):
        nonlocal spent
        peak.check_before_call()
        reserve = llm_cost.request_reservation(messages, max_tokens, time.time(), tools)
        if spent + reserve > proposal['campaign_cap_usd']:
            raise budget.OverBudget('campaign remaining funds below request reservation')
        before = llm.LOG.stat().st_size
        spent += reserve
        with journal.open('a') as f:
            f.write(json.dumps({'at':time.time(), 'event':'reserved', 'usd':reserve, 'campaign_accounted':spent})+'\n')
        try:
            return original_chat(messages, max_tokens=max_tokens, tools=tools, **kwargs)
        finally:
            with llm.LOG.open() as f:
                f.seek(before)
                rows = [json.loads(line) for line in f]
            actual = sum(session.cost(r['usage'], r['ts'], r['reserved_usd']) for r in rows) if rows else reserve
            spent += actual - reserve
            with journal.open('a') as f:
                f.write(json.dumps({'at':time.time(),'event':'settled','usd':actual,'usage_available':bool(rows and rows[0]['usage']), 'campaign_accounted':spent})+'\n')
    llm.chat = guarded_chat
    # The campaign guard above checks reservations and all attempts across calendar days.
    budget.check_before_call = lambda **kw: None
    session.start(['step2_stability', '--execute'], proposal['commit'])
    results = {cid: [] for cid in references}
    for n in range(1, proposal['rounds_per_case']+1):
        for case in selected:
            cid = case['id']
            d = out/'executions'/cid/str(n)
            X.CACHE_DIR = d/'llm'
            X.CACHE_DIR.mkdir(parents=True, exist_ok=False)
            t = session.step_started(cid, 2)
            ext = X.extract(caseinput.clinical_context(case), resources[cid].ont, use_cache=False)
            dump(d/'extraction.json', ext)
            r = pipeline.run_case(case, resources[cid], extraction=ext, step1=step1[cid])
            dump(d/'result.json', r)
            session.step_finished(cid, 2, t, 'done', output=d/'result.json', case=case)
            results[cid].append(r)
            diff = compare(fixed_results[cid], r)
            dump(d/'diff_reference.json', diff)
            print(cid, n, diagnostic(r), 'critical_change', diff['diagnosis_changed'], 'accounted', spent, flush=True)
            dump(out/'progress.json', {'completed':sum(map(len,results.values())), 'accounted_usd':spent})
            if not r['ok']:
                raise ValueError('execution self-check failed: '+cid)
    pairs = {cid: [{'rounds':[i+1,j+1], **compare(a,b)} for (i,a),(j,b) in itertools.combinations(enumerate(rs),2)] for cid,rs in results.items()}
    dump(out/'pairwise_diffs.json', pairs)
    summary = {'completed':20, 'cost': llm_cost.summarize(0,llm.LOG), 'campaign_accounted_usd':spent,
               'critical_changes':{cid:[i+1 for i,r in enumerate(rs) if diagnostic(r)!=diagnostic(fixed_results[cid])] for cid,rs in results.items()},
               'pairwise':{cid:{'comparisons':len(ps),'hpo_changed':sum(bool(p['hpo_diff']) for p in ps),'facts_changed':sum(bool(p['facts_diff']) for p in ps),'candidates_changed':sum(p['candidate_set_changed'] for p in ps),'diagnosis_changed':sum(p['diagnosis_changed'] for p in ps)} for cid,ps in pairs.items()}}
    dump(out/'summary.json', summary)
    print(json.dumps(summary),flush=True)

if __name__ == '__main__':
    main()

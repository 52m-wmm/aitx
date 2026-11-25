"""Apply approved key aliases with complete backups and exact inverse regression; no APIs."""
from __future__ import annotations

# Repository imports work from the relocated CLI as well as python -m.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from aitx.evidence import action_identity as I
from scripts import status_diff as SD
from scripts.step2_stability import dump


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(before,after,mapping):
    if len(set(mapping.values()))!=len(mapping):raise ValueError('mapping is not injective')
    old=[a['action_key'] for a in before['actions']]
    new=[a['action_key'] for a in after['actions']]
    for i in range(len(old)):
        for j in range(i):
            if old[i] and old[j] and (old[i]==old[j])!=(new[i]==new[j]):
                raise ValueError('changed action equivalence: '+before['actions'][i]['label'])
    inverse={v:k for k,v in mapping.items()}
    if I.rewrite(after,inverse)!=before:raise ValueError('non-key fields changed or irreversible')
    if before['evidence']!=after['evidence']:raise ValueError('evidence changed')


def apply(audit,out):
    if out.exists():raise FileExistsError(str(out))
    if I.REGISTRY.exists():raise FileExistsError('registry already exists')
    out.mkdir(parents=True)
    approved=json.loads((audit/'mapping.json').read_text());protected=json.loads((audit/'protected_sha256.json').read_text())
    maps={cid:{} for cid in SD.case_ids()}
    for row in approved:
        if row['case_id'] not in maps:raise ValueError('unapproved case')
        maps[row['case_id']][row['old_key']]=row['proposed_key']
    before=SD.build_snapshot(ROOT/'out/step3',SD.case_ids(),'before formal key switch',detailed=True)
    dump(out/'before_snapshot.json',before)
    manifest={'schema':'action-key-switch-v1','mapping_sha256':sha(audit/'mapping.json'),'cases':{},'baseline_hashes':{k:v for k,v in protected.items() if '/baselines/' in k}}
    for cid,mapping in maps.items():
        path=ROOT/'out/step3'/(cid+'.json')
        if sha(path)!=protected[str(path)]:raise ValueError('ledger changed since approved audit: '+cid)
        raw=path.read_bytes();old=json.loads(raw);candidate=I.rewrite(old,mapping);validate(old,candidate,mapping)
        dump(out/'staged'/(cid+'.json'),candidate)
        backup=out/'before'/(cid+'.json');backup.parent.mkdir(exist_ok=True);backup.write_bytes(raw)
        # Exercise rollback bytes on an isolated copy, never on the official output.
        with tempfile.TemporaryDirectory() as td:
            test=Path(td)/'ledger.json';test.write_bytes((out/'staged'/(cid+'.json')).read_bytes());test.write_bytes(raw)
            if sha(test)!=sha(backup):raise ValueError('rollback byte check failed')
        manifest['cases'][cid]={'before_sha256':sha(backup),'after_sha256':sha(out/'staged'/(cid+'.json')),
                                'changed_action_records':sum(a['action_key']!=b['action_key'] for a,b in zip(old['actions'],candidate['actions']))}
    # All cases have passed before any official mutation.
    data={'schema':'approved-action-key-aliases-v1','active':True,'approved_audit_sha256':manifest['mapping_sha256'],
          'approval':'User approved switching after injectivity/reversibility and zero clinical-delta checks, 2026-11-18',
          'cases':maps,
          'name_dependent_keys':{cid:sorted(r['proposed_key'] for r in approved if r['case_id']==cid and r['status']=='name_dependent') for cid in maps},
          'unconfirmed_normalization_keys':{cid:sorted(r['proposed_key'] for r in approved if r['case_id']==cid and r['normalization']=='unconfirmed') for cid in maps}}
    dump(out/'registry.json',data);dump(out/'manifest.json',manifest)
    for cid in maps:(ROOT/'out/step3'/(cid+'.json')).write_bytes((out/'staged'/(cid+'.json')).read_bytes())
    dump(I.REGISTRY,data);I.registry.cache_clear()
    after=SD.build_snapshot(ROOT/'out/step3',SD.case_ids(),'after formal key switch',detailed=True)
    normalized=copy.deepcopy(after)
    for row in normalized['rows']:
        inv={v:k for k,v in maps[row['case_id']].items()}
        if row['action_id'] in inv:row['action_id']=inv[row['action_id']]
    for label,old,new in [('since-before-raw',before,after),('since-before-normalized',before,normalized),
                          ('current-raw',SD.load_snapshot(ROOT/'baselines/current/snapshot.json'),after),
                          ('current-normalized',SD.load_snapshot(ROOT/'baselines/current/snapshot.json'),normalized)]:
        diff=SD.compare(old,new);d=ROOT/'out/status_diff/formal-key-switch-20261118'/label
        dump(d/'snapshot.json',new);dump(d/'diff.json',diff);(d/'diff.md').write_text(SD.markdown(diff))
        if label=='since-before-normalized' and diff['changes']:raise ValueError('clinical snapshot regression')
    reference=SD.load_snapshot(ROOT/'baselines/current/snapshot.json')
    initial_current=SD.compare(reference,before);final_current=SD.compare(reference,normalized)
    if initial_current['changes']!=final_current['changes']:raise ValueError('new non-key differences versus current')
    dump(out/'existing-current-diff-before.json',initial_current)
    for path,h in manifest['baseline_hashes'].items():
        if sha(Path(path))!=h:raise ValueError('baseline changed')
    print(json.dumps({'cases':len(maps),'changed_action_records':sum(v['changed_action_records'] for v in manifest['cases'].values()),'non_key_changes':0}))


def rollback(out):
    m=json.loads((out/'manifest.json').read_text())
    for cid,record in m['cases'].items():
        if sha(ROOT/'out/step3'/(cid+'.json')) not in (record['before_sha256'],record['after_sha256']):raise ValueError('refuse to overwrite later ledger changes: '+cid)
        if sha(out/'before'/(cid+'.json'))!=record['before_sha256']:raise ValueError('backup changed')
    for cid in m['cases']:(ROOT/'out/step3'/(cid+'.json')).write_bytes((out/'before'/(cid+'.json')).read_bytes())
    reg=json.loads((I.REGISTRY if I.REGISTRY.exists() else out/'registry.json').read_text());reg['active']=False;dump(I.REGISTRY,reg);I.registry.cache_clear()
    print('Restored original bytes for all 15 ledgers; export aliases disabled')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['apply','rollback']);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--audit',type=Path)
    a=ap.parse_args()
    if a.mode=='apply':
        if a.audit is None:raise ValueError('--audit required')
        apply(a.audit.resolve(),a.out.resolve())
    else:rollback(a.out.resolve())

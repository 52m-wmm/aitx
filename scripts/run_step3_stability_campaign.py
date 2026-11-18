"""Four pre-registered complete Step 3 executions, one cumulative $0.50 cap."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx import runmeta,peak
from aitx.disease import datasets as D
from scripts.step2_stability import dump
from scripts import llm_cost


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):
            h.update(b)
    return h.hexdigest()


def prepare(out):
    if (out/'manifest.json').exists():
        raise FileExistsError('frozen campaign already prepared')
    out.mkdir(parents=True,exist_ok=True)
    cases=['PRAC-AGXT-c33dup','PRAC-KMT2B']
    shutil.copytree(ROOT/'.cache/http',out/'http')
    fixed=[]
    for cid in cases:
        for k in [1,2,3]:
            src=runmeta.path(k,cid);dest=out/'upstream'/f'step{k}'/(cid+'.json')
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);fixed.append(dest)
        source='agxt-quote' if cid=='PRAC-AGXT-c33dup' else 'kmt2b-publish'
        dest=out/(cid+'.http.json')
        shutil.copyfile(ROOT/'runs/step3-stability-20261118'/source/'fixed_http.json',dest);fixed.append(dest)
    dirs={}
    for name in list(D.STEP2_DATASETS)+['genereviews_book']:
        metas=sorted((D.DATA_DIR/name).glob('*/meta.json'))
        meta=metas[-1];item=D._load_meta(meta.parent)
        if item is None:
            raise FileNotFoundError(str(meta))
        dirs[name]=str(meta.parent.resolve());fixed.extend([meta,item.path])
    fixed.extend(p for folder in ['data/rules','.cache/rxnorm','.cache/fda_gras'] for p in (ROOT/folder).rglob('*') if p.is_file())
    fixed.extend([ROOT/'scripts/step3_stability.py',ROOT/'scripts/run_step3_stability_campaign.py',ROOT/'scripts/step2_stability.py'])
    manifest={'cases':cases,'rounds':2,'budget_usd':.50,'allow_rxnav':False,'code_commit':runmeta.code_commit(),
              'code_fingerprint':runmeta.code_fingerprint(),'model':'deepseek-flash','documented_version':'DeepSeek-V4.1-Flash-1017',
              'dataset_meta_dirs':dirs,'fixed_file_sha256':{str(p.resolve()):sha(p) for p in fixed},
              'http_sha256':{p.name:sha(p) for p in sorted((out/'http').iterdir()) if p.is_file()},
              'accepted_baseline_sha256':sha(ROOT/'baselines/current/snapshot.json')}
    dump(out/'manifest.json',manifest)
    print('PREPARED',len(manifest['http_sha256']),'HTTP responses; fixed code and upstream inputs',flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--prepare',action='store_true')
    args=ap.parse_args();out=args.out.resolve()
    if args.prepare:
        prepare(out);return
    peak.guard()
    if (out/'started.json').exists():
        raise FileExistsError('campaign already started; do not repeat or overwrite runs')
    m=json.loads((out/'manifest.json').read_text())
    dump(out/'started.json',{'at':time.time(),'approved_cap_usd':.50})
    state={'completed':[],'status':'running'}
    for n in range(1,3):
        for cid in m['cases']:
            d=out/'executions'/cid/str(n)
            d.mkdir(parents=True,exist_ok=False)
            argv=[str(ROOT/'.venv/bin/python'),'-u',str(ROOT/'scripts/step3_stability.py'),'independent','--case',cid,
                  '--out',str(d),'--campaign',str(out),'--http-snapshot',str(out/(cid+'.http.json'))]
            print('START',cid,n,flush=True)
            with (d/'execution.log').open('w') as log:
                code=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT).returncode
            state['cost']=llm_cost.summarize(0,out/'llm_calls.jsonl') if (out/'llm_calls.jsonl').exists() else None
            state['accounted_usd']=json.loads((out/'attempts.jsonl').read_text().splitlines()[-1])['campaign_accounted'] if (out/'attempts.jsonl').exists() else 0
            if code:
                state.update(status='stopped',stopped_case=cid,stopped_round=n,exit_code=code)
                dump(out/'state.json',state)
                print('STOP',cid,n,'exit',code,'accounted',state['accounted_usd'],flush=True)
                print((d/'execution.log').read_text()[-2000:],flush=True)
                raise SystemExit(code)
            r=json.loads((d/'result.json').read_text())
            state['completed'].append({'case':cid,'round':n,'ok':r['ok']})
            dump(out/'state.json',state)
            print('DONE',cid,n,'ok',r['ok'],'accounted',state['accounted_usd'],flush=True)
            if not r['ok']:
                state.update(status='stopped',reason='ledger self-check failed');dump(out/'state.json',state);raise SystemExit(1)
    state['status']='finished';dump(out/'state.json',state)
    print('FINISHED',state,flush=True)

if __name__=='__main__':
    main()

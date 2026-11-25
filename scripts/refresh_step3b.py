"""Refresh formal Step 3b while preserving the saved outputs of the other Step 3 sections.

Writes the checked v3 Ledger to out/step3. Build Step 4 and validate Step 5 separately.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx import runmeta,session
from aitx.step3.b.records import refresh_trials


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--case',action='append',required=True)
    ap.add_argument('--cache-only',action='store_true',help='Do not make new LLM calls')
    ap.add_argument('--offpeak-only',action='store_true')
    args=ap.parse_args()
    runmeta.refuse_eval_cases(args.case,'Step 3b refresh')
    if args.cache_only:os.environ['AITX_LLM_CACHE_ONLY']='1'
    elif args.offpeak_only:
        from aitx import peak
        peak.guard()
    session.start(sys.argv,runmeta.code_fingerprint())
    for cid in args.case:
        case=runmeta.find_case(cid)
        one,h1=runmeta.load_output(1,case);two,h2=runmeta.load_output(2,case)
        runmeta.check_upstream(two,2,{1:h1})
        path=runmeta.path(3,cid);previous=json.loads(path.read_text())
        backup=ROOT/'out'/'3b'/cid/'history'/hashlib.sha256(path.read_bytes()).hexdigest()/'ledger.json'
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():backup.write_bytes(path.read_bytes())
        result=refresh_trials(previous,case,one,two)
        if not result['ok']:raise RuntimeError(f'{cid}: Ledger checks failed; original output retained')
        runmeta.write_output(3,case,result,upstream={1:h1,2:h2})
        print(f'{cid}: evidence-ledger-v3 PASS; frozen other sections; {path}')


if __name__=='__main__':main()

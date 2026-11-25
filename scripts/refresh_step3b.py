"""Refresh formal Step 3b while preserving the saved outputs of the other Step 3 sections.

Archives each run and viewer cards in .cache/step3b/<case>/<batch>, then publishes
the checked v3 Ledger to out/step3. Build Step 4 and validate Step 5 separately.
"""
import argparse
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx import runmeta,session
from aitx.step3.b.results import run_case


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
        folder=run_case(ROOT,case,one,two,{1:h1,2:h2})
        print(f'{cid}: evidence-ledger-v3 PASS; latest viewer result: {folder}')


if __name__=='__main__':main()

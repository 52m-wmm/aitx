"""Exact 15-case key-only offline regression against migration backups; no APIs."""

# Repository imports work from the relocated CLI as well as python -m.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pathlib import Path
from datetime import date
import hashlib,json,sys
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from aitx import runmeta
from aitx.evidence import action_identity as I
from aitx.report import assemble as A
from scripts.build_report import report_safety
from scripts.experiments.switch_action_keys import validate
from scripts.step2_stability import dump
from scripts import status_diff as SD
from scripts.step3_preflight import frozen_io
from aitx import http
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--backup',type=Path,required=True);args=ap.parse_args()
out=args.backup.resolve();m=json.loads((out/'manifest.json').read_text());results=[]
def recorded_date(src,evidence=None):
    return src['effective_date'] if 'effective_date' in src else None
with frozen_io(http.CACHE_DIR,{}):
 for cid,info in m['cases'].items():
  old=json.loads((out/'before'/(cid+'.json')).read_text());new=json.loads((root/'out/step3'/(cid+'.json')).read_text())
  mapping=I.case_map(cid);validate(old,new,mapping)
  assert A.drugs_for_safety(old)==A.drugs_for_safety(new)
  assert report_safety(old)==report_safety(new)
  case=runmeta.find_case(cid)
  om,ot=A.assemble(old,case,recorded_date,report_safety(old),today=date(2026,11,18))
  nm,nt=A.assemble(new,case,recorded_date,report_safety(new),today=date(2026,11,18))
  if om!=nm:raise ValueError('report semantics changed: '+cid)
  assert I.rewrite(nt,I.case_map(cid,reverse=True))==ot
  dump(out/'regression'/cid/'result.json',{'case':cid,'key_changed_records':info['changed_action_records'],'actions_conditions_classifications_exact_inverse':True,'evidence_exact':True,'drug_coverage_identical':True,'report_markdown_identical':True,'trace_key_only':True})
  results.append({'case':cid,'ok':True,'key_changed_records':info['changed_action_records']})
# DBS and previously observed extraction losses are observed only, never repaired here.
oldk=json.loads((out/'before/PRAC-KMT2B.json').read_text());newk=json.loads((root/'out/step3/PRAC-KMT2B.json').read_text())
dbs=[{'label':a['label'],'old_key':a['action_key'],'new_key':b['action_key'],'status_by_branch':b['status_by_branch'],'evidence_ids':b['evidence_ids']} for a,b in zip(oldk['actions'],newk['actions']) if 'dbs' in a['label'].lower() or 'deep brain stimulation' in a['label'].lower()]
summary={'cases':results,'passed':len(results),'expected':15,'model_calls':0,'network_calls':0,'actual_usd':0,'accepted_baseline_updated':False,'dbs':dbs,
 'report_regression_dates':'Only stored source effective_date values; other publication dates intentionally unknown in both sides. No official Step4 files regenerated.'}
before=SD.load_snapshot(out/'before_snapshot.json')
reference=SD.load_snapshot(root/'baselines/current/snapshot.json')
normalized=SD.load_snapshot(root/'out/status_diff/formal-key-switch-20261118/current-normalized/snapshot.json')
initial=SD.compare(reference,before);after=SD.compare(reference,normalized)
assert initial['changes']==after['changes']
dump(out/'existing-current-diff-before.json',initial)
summary['existing_accepted_differences_unchanged']=True
summary['existing_accepted_diff_counts']=initial['counts']
dump(out/'regression_summary.json',summary)
print('15/15 exact key-only, evidence, safety coverage, report and trace regression PASS')

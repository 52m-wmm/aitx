"""User-authorized offline key-only baseline mapping; never copies live clinical fields."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from scripts import status_diff as SD
from scripts.promote_baseline import promote

CATEGORY='仅 key 迁移（离线映射）'


def read_mapping(path):
    lines=path.read_text().splitlines()
    separator='\t' if '\t' in lines[0] else '\\t'
    header=lines[0].split(separator);result={}
    for line in lines[1:]:
        fields=line.split(separator)
        if len(fields)!=len(header):raise ValueError('invalid mapping row')
        row=dict(zip(header,fields));cid,old,new=row['Case'],row['Old key'],row['Proposed key']
        if not cid or not old or not new:raise ValueError('missing mapping identity')
        mapping=result.setdefault(cid,{})
        if old in mapping:raise ValueError('duplicate old identity')
        mapping[old]=new
    for mapping in result.values():
        if len(set(mapping.values()))!=len(mapping):raise ValueError('non-injective mapping')
    return result


def convert(before,mapping):
    after=copy.deepcopy(before);changed=[]
    for old,row in zip(before['rows'],after['rows']):
        cid=old['case_id'];key=old['action_id']
        if cid in mapping and key in mapping[cid] and mapping[cid][key]!=key:
            row['action_id']=mapping[cid][key]
            changed.append({'case_id':cid,'section':row['section'],'branch':row['branch'],'old_key':key,'new_key':row['action_id']})
        restored=dict(row,action_id=old['action_id'])
        if restored!=old:raise ValueError('changed non-key baseline content')
    keys=[SD.row_key(r) for r in after['rows']]
    if len(set(keys))!=len(keys):raise ValueError('mapping collided baseline rows')
    return after,changed


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mapping',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    current=ROOT/'baselines/current/snapshot.json';raw=current.read_bytes();before=SD.load_snapshot(current)
    (args.out/'before.json').write_bytes(raw)
    (args.out/'approvals-before.md').write_bytes((ROOT/'baselines/approvals.md').read_bytes())
    mapping=read_mapping(args.mapping)
    registry=json.loads((ROOT/'data/action_key_registry.json').read_text())
    if mapping!={cid:entries for cid,entries in registry['cases'].items() if entries}:
        raise ValueError('mapping.tsv differs from approved export registry')
    after,changed=convert(before,mapping)
    after['label']=CATEGORY+'; '+before['label']
    path=args.out/'candidate.json';path.write_text(json.dumps(after,ensure_ascii=False,indent=1)+'\n')
    delta=SD.compare(before,after);(args.out/'diff.json').write_text(json.dumps(delta,ensure_ascii=False,indent=2)+'\n');(args.out/'diff.md').write_text(SD.markdown(delta))
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    approval={'date':'2026-11-19','commit':commit,'approver':'user (explicit chat authorization: directly map baselines/current old keys without rerunning)',
              'reason':CATEGORY+'：用户明确授权按mapping.tsv直接转换current旧key，不依赖重跑。逐行仅改action_id；状态、条件、证据及其他字段原样保留，不吸收正式账本的医学差异。',
              'baseline_sha256':SD.digest(raw),'candidate_sha256':SD.digest(path.read_bytes()),
              'approved_changes':[{'change_id':r['change_id'],'approved':True,'reason':CATEGORY+'；按已批准mapping.tsv一一映射，基线非key字段逐字保留。'} for r in delta['changes']]}
    (args.out/'approval.json').write_text(json.dumps(approval,ensure_ascii=False,indent=2)+'\n')
    (args.out/'mapped-rows.json').write_text(json.dumps(changed,ensure_ascii=False,indent=2)+'\n')
    if args.apply:promote(path,approval,commit)
    print(json.dumps({'mapped_rows':len(changed),'diff':delta['counts'],'baseline_rows':len(after['rows']),'applied':args.apply},ensure_ascii=False))

if __name__=='__main__':main()

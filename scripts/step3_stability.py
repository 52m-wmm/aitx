"""Isolated Step 3 refresh, cache sensitivity, and cache-only quote inventory."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx import http,llm,peak,runmeta,session
from aitx.disease import extract as X, datasets as D
from aitx.evidence import pipeline as P, ledger as LG, context_check as CC
from aitx.evidence.branches import build_branches,patient_context
from aitx.evidence.rules import apply_rules,load_rules
from scripts.step2_stability import dump,install_campaign_guard
from scripts import status_diff as SD,llm_cost


class FixedInputMissing(LookupError):
    """A required frozen input is absent; never treat it as a network-negative result."""


def fixed_http(out, snapshot=None):
    responses={str(http.CACHE_DIR/Path(k).name):v for k,v in json.loads(snapshot.read_text()).items()} if snapshot else {}
    original_get=http.get
    def get(url, *,headers=None,**kw):
        p=http._key(url,headers)
        if str(p) not in responses:
            if not p.exists():
                if snapshot:
                    raise FixedInputMissing('fixed database cache missing: '+url)
                try:
                    original_get(url,headers=headers)
                except RuntimeError as e:
                    if not str(e).startswith(('HTTP 400 ', 'HTTP 404 ')):
                        raise
                    responses[str(p)]={'url':url,'error':str(e)}
                    dump(out/'fixed_http.json',responses)
                    raise
            if str(p) not in responses:
                responses[str(p)]=json.loads(p.read_text())
        d=responses[str(p)]
        if 'error' in d:
            raise RuntimeError(d['error'])
        return http.Fetched(d['url'],d['text'],d['accessed_at'],True)
    http.get=get
    return responses


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('mode',choices=['refresh','sensitivity','quote','independent'])
    ap.add_argument('--case',required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--step2',type=Path)
    ap.add_argument('--http-snapshot',type=Path)
    ap.add_argument('--campaign',type=Path)
    args=ap.parse_args()
    runmeta.refuse_eval_cases([args.case],'Step 3 isolated experiment')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists():
        raise FileExistsError('completed experiment must not be overwritten')
    case=runmeta.find_case(args.case)
    if args.mode=='independent':
        if args.campaign is None or args.http_snapshot is None:
            raise ValueError('independent execution requires fixed campaign inputs')
        campaign=args.campaign.resolve()
        frozen=json.loads((campaign/'manifest.json').read_text())
        if runmeta.code_fingerprint()!=frozen['code_fingerprint']:
            raise ValueError('frozen production code changed')
        for name,sha in frozen['fixed_file_sha256'].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:
                raise ValueError('frozen input changed: '+name)
        http.CACHE_DIR=campaign/'http'
        def fixed_dataset(name,**kw):
            item=D._load_meta(Path(frozen['dataset_meta_dirs'][name]))
            if item is None:
                raise FileNotFoundError(name)
            return item
        D.ensure=fixed_dataset
        def fixed_post(url,body,*,headers=None,**kw):
            payload=json.dumps(body,sort_keys=True)
            path=http._key(url+'#'+hashlib.sha256(payload.encode()).hexdigest(),headers)
            if not path.exists():
                raise FixedInputMissing('fixed POST response missing: '+url)
            d=json.loads(path.read_text())
            return http.Fetched(d['url'],d['text'],d['accessed_at'],True)
        http.post_json=fixed_post
    original_path=runmeta.path
    sandbox=out/'upstream'
    runmeta.path=lambda step,cid,out=sandbox:original_path(step,cid,out)
    for k in [1,2]:
        src=(campaign/'upstream'/f'step{k}'/(args.case+'.json')) if args.mode=='independent' else (args.step2 if k==2 and args.step2 else original_path(k,args.case))
        dest=runmeta.path(k,args.case);dest.parent.mkdir(parents=True,exist_ok=True)
        if k==2 and args.step2:
            r=json.loads(src.read_text())
            if '_meta' not in r:
                r['_meta']={'created_at':int(src.stat().st_mtime),'input_fingerprint':runmeta.fingerprint(case),
                            'experiment_source':str(src.resolve()),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
            dump(dest,r)
        else:
            shutil.copyfile(src,dest)
    s1,s2=[json.loads(runmeta.path(k,args.case).read_text()) for k in [1,2]]
    if args.mode in ('refresh','independent'):
        peak.guard()
        if args.mode=='independent':
            os.environ.pop('AITX_LLM_CACHE_ONLY',None)
            X.CACHE_DIR=out/'llm'
            X.CACHE_DIR.mkdir(exist_ok=False)
            spend=install_campaign_guard(campaign,frozen['budget_usd'])
        else:
            spend=install_campaign_guard(out,.06)
    else:
        os.environ['AITX_LLM_CACHE_ONLY']='1'
        spend=lambda:0.0
    responses=fixed_http(out,args.http_snapshot)
    sid=session.start(['step3_stability',args.mode,args.case,str(out)],runmeta.code_fingerprint())
    dump(out/'session.json',{'id':sid,'path':str(session.base()/sid)})
    inventory=[];cached=X._cached_chat
    def traced(messages,k,use_cache,*a,**kw):
        cfg=llm.config();pv=kw['prompt_version'] if 'prompt_version' in kw else None
        params=kw['call_params'] if 'call_params' in kw else X.CALL_PARAMS
        inventory.append({'key':X.cache_key(messages,k,cfg,pv),'sample':k,'prompt_version':pv,
                          'messages':messages,'params':params,
                          'reservation':llm_cost.request_reservation(messages,params['max_tokens'],time.time())})
        return cached(messages,k,False if args.mode=='independent' else use_cache,*a,**kw)
    X._cached_chat=traced
    unmeasured=[]
    if args.mode=='sensitivity':
        ask=CC.ask;decide=CC.decide_3a
        def partial_ask(header,passage,patient,questions,**kw):
            try:
                return ask(header,passage,patient,questions,**kw)
            except llm.CacheOnly:
                if any(q['id'] in ('disease','gene','purpose','harm','direction') for q in questions):
                    raise
                unmeasured.append({'header':header,'passage':passage,'patient':patient,'questions':questions,
                                   'reason':'not tested: response cache missing'})
                return {'questions':[dict(q,final='not_tested',answers=[],quotes=[],reasons=['not tested: cache missing']) for q in questions],
                        'n_checks':0,'call_ids':[],'llm':None,'not_tested':True}
        def partial_decide(res,lines,*a,**kw):
            if res.get('not_tested'):
                return lines,['not tested: context response cache missing; provisional deterministic requirements only']
            return decide(res,lines,*a,**kw)
        CC.ask=partial_ask;CC.decide_3a=partial_decide
    branches,dropped=build_branches(s2);led=LG.Ledger(args.case,branches)
    led.patient_context,led.missing_information=patient_context(s1,s2)
    apply_rules(led,load_rules(),s1,s2)
    P.background(led,args.case,s1,s2,runmeta.path(1,args.case).read_text(),runmeta.path(2,args.case).read_text())
    P.record_sex_inference(led,args.case,s1,runmeta.path(1,args.case).read_text())
    stages=[]
    for name,func in [('3a',lambda:P.add_established(led,s1,s2)),('3b',lambda:P.add_trials(led,case,s1,s2)),
                      ('3c',lambda:P.add_offlabel(led,case,s1,s2)),('3d',lambda:P.add_bespoke(led,case,s1,s2)),
                      ('3e',lambda:P.add_repurposing(led,case,s1,s2))]:
        t=session.step_started(args.case,3)
        try:
            func()
        except llm.CacheOnly as e:
            if args.mode!='sensitivity':
                dump(out/'inventory.json',inventory)
                raise
            stages.append({'stage':name,'status':'not_tested','reason':str(e)})
        else:
            stages.append({'stage':name,'status':'done'})
        finally:
            dump(out/'inventory.json',inventory)
            dump(out/'checkpoint.json',led.to_dict())
        session.step_finished(args.case,3,t,stages[-1]['status'])
        dump(out/'checkpoint.json',led.to_dict())
        dump(out/'inventory.json',inventory)
        print(args.case,name,stages[-1]['status'],'accounted',spend(),flush=True)
    led.possible_duplicates+=LG.possible_duplicates(led.actions,led.evidence)
    from aitx.report.sources import record_context
    report_context=record_context(led)
    result=led.to_dict();result.update(report_context=report_context,branches_dropped=dropped)
    result['ok']=all(c['status']!='fail' for c in result['checks'])
    result['stability_experiment']={'stages':stages,'unmeasured_checks':unmeasured,'mode':args.mode}
    # Preserve provisional deterministic states separately; never present missing checks as an assessment.
    def not_tested(value):
        if isinstance(value,dict):
            return value.get('final')=='not_tested' or any(not_tested(v) for v in value.values())
        return isinstance(value,list) and any(not_tested(v) for v in value)
    for action in result['actions']:
        if not_tested(action):
            action['stability_provisional_status_by_branch']=action['status_by_branch']
            action['status_by_branch']={b:{'status':'not_tested','reason':'not tested: changed context lacks cached check; provisional deterministic result is stored separately'} for b in action['status_by_branch']}
    result['_meta']={'code_commit':runmeta.code_commit(),'input_fingerprint':runmeta.fingerprint(case),
                     'code_fingerprint':runmeta.code_fingerprint(),'created_at':int(time.time()),'experiment_only':True}
    dump(out/'result.json',result);dump(out/'fixed_http.json',responses);dump(out/'inventory.json',inventory)
    dump(out/'summary.json',{'mode':args.mode,'case':args.case,'stages':stages,'requests_including_cache':len(inventory),
                             'unmeasured_groups':len(unmeasured),'accounted_usd':spend(),'checks':result['checks']})
    print('FINISHED',args.mode,args.case,'actions',len(result['actions']),'unmeasured',len(unmeasured),flush=True)

if __name__=='__main__':
    main()

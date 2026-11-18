"""Replay saved 3a responses, isolate free public GET fills, never call a model."""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import threading
import re
import urllib.parse
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx import http,llm,runmeta
from aitx.disease import extract as X,datasets as D
from aitx.evidence import pipeline as P,ledger as LG,context_check as CC,established as E
from aitx.evidence.branches import build_branches,patient_context
from aitx.evidence.rules import apply_rules,load_rules
from scripts.step2_stability import dump
from scripts import llm_cost


def mark_pending(result,missing_assembly):
    def not_tested(v):
        if isinstance(v,dict):return v.get('final')=='not_tested' or any(not_tested(x) for x in v.values())
        return isinstance(v,list) and any(not_tested(x) for x in v)
    for action in result['actions']:
        if action['action_key'] and (not_tested(action) or missing_assembly):
            action['replay_deterministic_status_by_branch']=action['status_by_branch']
            action['status_by_branch']={b:{'status':'not_tested','reason':'pending: context check or assembly requires uncached model response'} for b in action['status_by_branch']}


def run(cid,n,out,public_cache=None,offline=False,raw_dir=None):
    if out.exists():raise FileExistsError(str(out))
    out.mkdir(parents=True)
    original_http=http.get
    source=raw_dir if raw_dir is not None else ROOT/'runs/step3-offline-audit-v2-20261118'/cid/str(n)/'raw_extractions'
    campaign=ROOT/'runs/step3-staged-050-v3-20261118'
    frozen=json.loads((campaign/'manifest.json').read_text())
    raw={p.stem:json.loads(p.read_text()) for p in source.glob('*.json')}
    if not raw:raise FileNotFoundError(str(source))
    responses={Path(k).name:v for k,v in json.loads((campaign/(cid+'.http.json')).read_text()).items()}
    pending={};used=[];traffic=[];trace_lock=threading.Lock()
    def no_model(*a,**kw):raise AssertionError('MODEL CALL FORBIDDEN')
    def get(url,*,headers=None,**kw):
        key=http._key(url,headers).name
        p=campaign/'http'/key
        if key in responses:d=responses[key]
        elif p.exists():d=json.loads(p.read_text())
        elif public_cache is not None and (public_cache/key).exists():
            d=json.loads((public_cache/key).read_text());dump(http._key(url,headers),d)
        else:
            if offline:raise LookupError('offline replay response missing: '+url)
            host=urllib.parse.urlsplit(url).hostname
            if urllib.parse.urlsplit(url).scheme!='https' or host not in {'api.fda.gov','rxnav.nlm.nih.gov','www.ebi.ac.uk','eutils.ncbi.nlm.nih.gov','www.ncbi.nlm.nih.gov','www.ema.europa.eu','dailymed.nlm.nih.gov'}:
                raise LookupError('public GET not approved for replay: '+url)
            local=http._key(url,headers)
            if local.exists():d=json.loads(local.read_text())
            else:
                try:
                    original_http(url,headers=headers,timeout=30,retries=2)
                except RuntimeError as e:
                    d={'url':url,'error':str(e),'accessed_at':int(time.time()),
                       'response_status':re.search(r'HTTP (\d{3})',str(e)).group(1) if re.search(r'HTTP (\d{3})',str(e)) else 'transport_failed_no_response'};dump(local,d)
                else:d=json.loads(local.read_text())
                traffic.append({'url':url,'cache_key':key,'response':d});dump(out/'public_requests.json',traffic)
        responses[key]=d
        if 'error' in d:raise RuntimeError(d['error'])
        return http.Fetched(d['url'],d['text'],d['accessed_at'],True)
    def post(url,body,*,headers=None,**kw):
        payload=json.dumps(body,sort_keys=True)
        return get(url+'#'+hashlib.sha256(payload.encode()).hexdigest(),headers=headers)
    def dataset(name,**kw):
        item=D._load_meta(Path(frozen['dataset_meta_dirs'][name]))
        if item is None:raise FileNotFoundError(name)
        return item
    cfg={'model':'deepseek-flash','base_url':'https://api.deepseek.com','api_key':'','expect_model_prefix':''}
    def cached(messages,k,use_cache,*a,**kw):
        pv=kw['prompt_version'];params=kw['call_params'] if 'call_params' in kw else X.CALL_PARAMS
        key=X.cache_key(messages,k,cfg,pv)
        if key in raw:
            answer=raw[key]['response'];origin='saved independent raw'
        else:
            entry=X.cache_lookup(messages,k,cfg,pv,params)
            if entry is None:
                with trace_lock:
                    pending[key]={'key':key,'sample':k,'prompt_version':pv,'messages':messages,'params':params,
                                  'reservation_offpeak_usd':llm_cost.request_reservation(messages,params['max_tokens'],1795014000)}
                    dump(out/'pending.json',list(pending.values()))
                raise llm.CacheOnly('pending '+key)
            answer=entry;origin='historical cache'
        with trace_lock:
            used.append({'key':key,'prompt_version':pv,'origin':origin});dump(out/'used.json',used)
        return dict(answer,call_id=key)
    ask=CC.ask;decide=CC.decide_3a
    def partial_ask(header,passage,patient,questions,**kw):
        try:return ask(header,passage,patient,questions,**kw)
        except llm.CacheOnly:
            # Inventory all three votes, including ones the thread pool did not start.
            messages=CC.messages(header,passage,patient,questions)
            for k in range(CC.N_CHECKS):
                try:cached(messages,k,True,prompt_version=CC.PROMPT_VERSION,call_params=CC.CALL_PARAMS)
                except llm.CacheOnly:pass
            return {'questions':[dict(q,final='not_tested',answers=[],quotes=[],reasons=['pending: no cached check']) for q in questions],
                    'n_checks':0,'call_ids':[],'llm':None,'not_tested':True}
    def partial_decide(res,lines,*a,**kw):
        if res.get('not_tested'):return lines,['pending: no cached context check; deterministic requirements only']
        return decide(res,lines,*a,**kw)
    # Preserve missing non-check work explicitly; never supply a fabricated model response.
    repair=E._repaired_item;synonyms=E.merge_synonyms
    missing_assembly=[]
    def partial_repair(it,name,path,text,use_cache,nbk):
        try:return repair(it,name,path,text,use_cache,nbk)
        except llm.CacheOnly:
            missing_assembly.append({'kind':'quote repair','name':name,'source':path,'raw_item':it})
            return None
    def partial_synonyms(found,use_cache):
        try:return synonyms(found,use_cache)
        except llm.CacheOnly:
            missing_assembly.append({'kind':'synonym merge','keys':list(found)})
            return [] # only provisional unmerged inventory; no completed diagnosis/clinical claim
    s1,s2=[json.loads((campaign/'upstream'/f'step{k}'/(cid+'.json')).read_text()) for k in [1,2]]
    branches,dropped=build_branches(s2);led=LG.Ledger(cid,branches)
    led.patient_context,led.missing_information=patient_context(s1,s2)
    finished=False
    with ExitStack() as stack:
        for obj,attr,value in [(http,'CACHE_DIR',out/'http'),(http,'get',get),(http,'post_json',post),
                               (llm,'chat',no_model),(llm,'config',lambda:cfg),(D,'ensure',dataset),(X,'CONCURRENCY',1),
                               (X,'_cached_chat',cached),(CC,'ask',partial_ask),(CC,'decide_3a',partial_decide),
                               (E,'_repaired_item',partial_repair),(E,'merge_synonyms',partial_synonyms)]:
            stack.enter_context(patch.object(obj,attr,value))
        try:
            apply_rules(led,load_rules(),s1,s2)
            P.background(led,cid,s1,s2,(campaign/'upstream/step1'/(cid+'.json')).read_text(),(campaign/'upstream/step2'/(cid+'.json')).read_text())
            P.record_sex_inference(led,cid,s1,(campaign/'upstream/step1'/(cid+'.json')).read_text())
            P.add_established(led,s1,s2)
            finished=True
        finally:
            result=led.to_dict()
            result['replay']={'assembly_reached_end':finished,'complete':False,'model_calls':0,'pending':list(pending.values()),'missing_assembly':missing_assembly}
            mark_pending(result,missing_assembly)
            dump(out/'replay.json',result);dump(out/'pending.json',list(pending.values()));dump(out/'public_requests.json',traffic);dump(out/'used.json',used)
    print(cid,n,'actions',len(result['actions']),'pending',len(pending),'missing_assembly',len(missing_assembly),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);ap.add_argument('--round',type=int,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--public-cache',type=Path);ap.add_argument('--offline',action='store_true');ap.add_argument('--raw-dir',type=Path)
    a=ap.parse_args();runmeta.refuse_eval_cases([a.case],'3a replay');run(a.case,a.round,a.out.resolve(),a.public_cache,a.offline,a.raw_dir)

"""Offline dependency audit of saved Step 3 extractions. Never invokes a model."""
from __future__ import annotations
import argparse
from contextlib import contextmanager, ExitStack
import hashlib
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx import http,llm
from aitx.evidence import actions as A
from scripts.step2_stability import dump
from scripts.step3_stability import FixedInputMissing


def save_raw(out,key,messages,answer):
    # Save the exact answer first, even if parsing fails; never manufacture classifications.
    value={'complete':False,'safety_validation':'incomplete','messages':messages,'response':answer,
           'classification_scope':'model fields only; downstream clinical classification not generated'}
    path=out/'raw_extractions'/(key+'.json')
    dump(path,value)
    value['parsed']=json.loads(answer['content'])
    dump(path,value)


@contextmanager
def frozen_io(cache,snapshot):
    """Replay only explicit fixtures; block even accidental urllib/socket/model escape paths."""
    records={Path(k).name:v for k,v in snapshot.items()}
    trace=[]
    def blocked(*a,**kw):
        raise FixedInputMissing('offline preflight: network/model access forbidden')
    def get(url,*,headers=None,**kw):
        key=http._key(url,headers).name
        entry={'url':url,'cache_key':key,'status':'missing'}
        trace.append(entry)
        if key in records:
            d=records[key];entry['fixture']='snapshot'
        elif (cache/key).exists():
            d=json.loads((cache/key).read_text());entry['fixture']='campaign/http'
        else:
            raise FixedInputMissing('fixed database cache missing: '+url)
        entry['status']='cached'
        if 'error' in d:
            entry['recorded_error']=d['error']
            raise RuntimeError(d['error'])
        if '/rxcui.json?' in url:
            body=json.loads(d['text'])
            group=body['idGroup']
            entry['rxcuIs']=group['rxnormId'] if 'rxnormId' in group else []
        return http.Fetched(d['url'],d['text'],d['accessed_at'],True)
    def post(url,body,*,headers=None,**kw):
        payload=json.dumps(body,sort_keys=True)
        return get(url+'#'+hashlib.sha256(payload.encode()).hexdigest(),headers=headers)
    with ExitStack() as stack:
        for obj,attr,value in [(http,'get',get),(http,'post_json',post),(llm,'chat',blocked)]:
            stack.enter_context(patch.object(obj,attr,value))
        for name in ['urllib.request.urlopen','socket.create_connection','socket.socket.connect','socket.socket.connect_ex']:
            stack.enter_context(patch(name,blocked))
        yield trace


def probe_name(name,trace):
    start=len(trace)
    try:
        result=A.drug_key(name)
    except FixedInputMissing as e:
        return {'status':'incomplete','reason':str(e),'requests':trace[start:]}
    return {'status':'dependencies_available','normalization':result,'requests':trace[start:]}


def audit(campaign,out):
    if out.exists():
        raise FileExistsError('audit directory must be new: '+str(out))
    out.mkdir(parents=True)
    report={'scope':'saved raw extraction names only; not complete Step 3 acceptance',
            'network_calls':0,'llm_calls':0,'complete':False,'runs':[]}
    for run in sorted((campaign/'executions').glob('*/*')):
        cid=run.parent.name
        snapshot=json.loads((campaign/(cid+'.http.json')).read_text())
        inventory=json.loads((run/'inventory.json').read_text())
        target=out/cid/run.name
        rows=[]
        with frozen_io(campaign/'http',snapshot) as trace:
            for call in inventory:
                p=run/'llm'/(call['key']+'.json')
                if not p.exists():
                    continue # retry inventory can have no accepted response
                answer=json.loads(p.read_text())
                save_raw(target,call['key'],call['messages'],answer)
                parsed=json.loads(answer['content'])
                if 'items' not in parsed:
                    continue # chapter selection is not an action extraction
                for index,item in enumerate(parsed['items']):
                    row={'request_key':call['key'],'item_index':index,'raw_item':item,
                         'source_prompt':call['messages'][-1]['content'].splitlines()[0]}
                    # Superset of drug/avoid candidates; no clinical decisions or filtering changed.
                    if item['kind']=='drug' or (item['kind']=='avoid' and 'avoid' in row['source_prompt'].lower()):
                        row['dependency_probe']=probe_name(item['name'],trace)
                        row['clinical_collection_filters']='not evaluated: quote repair/source-scope and downstream checks may discard candidate'
                    else:
                        row['dependency_probe']={'status':'not_a_drug_normalization_candidate'}
                    rows.append(row)
        text=(run/'execution.log').read_text()
        hits=re.findall(r'fixed database cache missing: (https://[^\s]+)',text)
        stop_url=hits[-1] if hits else None
        failed=[dict(raw_name=r['raw_item']['name'],raw_kind=r['raw_item']['kind'],source_prompt=r['source_prompt'],
                     llm_cache_key=r['request_key'],**r['dependency_probe']) for r in rows if r['dependency_probe']['status']=='incomplete']
        record={'case':cid,'round':run.name,'status':'incomplete','historical_stop_url':stop_url,
                'historical_stop_cache_key':http._key(stop_url).name if stop_url else None,
                'raw_actions':rows,'dependency_gaps':failed,'http_trace':trace,
                'original_call_chain':text[text.index('Traceback (most recent call last):'):] if 'Traceback (most recent call last):' in text else None}
        historical=[]
        for call in inventory:
            prior=ROOT/'.cache/llm'/(call['key']+'.json')
            fresh=run/'llm'/(call['key']+'.json')
            if prior.exists() and fresh.exists():
                old=json.loads(json.loads(prior.read_text())['content'])
                new=json.loads(json.loads(fresh.read_text())['content'])
                if 'items' in old and 'items' in new:
                    historical.append({'key':call['key'],'reference_file':str(prior),'old_items':old['items'],'new_items':new['items']})
        record['historical_same_prompt_extractions']=historical
        dump(target/'preflight.json',record)
        report['runs'].append(record)
    report['known_dependency_gaps']=sum(len(r['dependency_gaps']) for r in report['runs'])
    report['status']='blocked' if report['known_dependency_gaps'] else 'observed dependencies available; future model outputs unbounded'
    dump(out/'summary.json',report)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--campaign',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    result=audit(args.campaign.resolve(),args.out.resolve())
    print(json.dumps({k:v for k,v in result.items() if k!='runs'},indent=2))
    raise SystemExit(2 if result['known_dependency_gaps'] else 0)

if __name__=='__main__':
    main()

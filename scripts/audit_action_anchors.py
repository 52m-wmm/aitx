"""Read-only 3a key proposals. Never switches keys, Evidence IDs, or baselines."""
from __future__ import annotations
import argparse
import copy
from collections import Counter,defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx import http
from aitx.disease import datasets as D
from aitx.evidence import genereviews as GR,ledger as L
from scripts import status_diff as SD
from scripts.step2_stability import dump
from scripts.step3_preflight import frozen_io

SECTIONS={'existing_targeted_therapies','supportive_management','contraindications_precautions'}


def anchor_id(source_id,path,sentence):
    # Separate identity namespace; intentionally independent of Ledger.evidence_id.
    payload=[source_id,path,L._norm(sentence)]
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def sentence_units(text):
    """Conservative punctuation boundaries, including adjacent table sentences; no paraphrasing."""
    start=0
    for m in re.finditer(r'[.!?](?=\s|[A-Z]|$)',text):
        prefix=text[:m.end()].lower()
        if any(prefix.endswith(a) for a in ['e.g.','i.e.','et al.','dr.','vs.','fig.','no.']):continue
        yield text[start:m.end()].strip(),True
        start=m.end()
    tail=text[start:].strip()
    if tail:yield tail,False


def name_key(prefix,label):
    from urllib.parse import quote
    return prefix+':name:'+quote(L._norm(label),safe='')


def locate(source_id,path,label,quote,blocks):
    """Return cited source units in document order, including complete cells/list items."""
    out=[];name=L._norm(label);q=L._norm(quote)
    if not name or not q:raise ValueError('label and quote must be nonempty')
    for block_index,b in enumerate(blocks):
        if isinstance(b,str):b={'text':b,'kind':'paragraph','document_position':block_index}
        units=[(b['text'],True)] if b['kind'] in ('table_cell','list_item') else sentence_units(b['text'])
        offset_in_block=0
        for text,complete in units:
            position=b['text'].find(text,offset_in_block)
            offset_in_block=position+len(text)
            n=L._norm(text)
            if not complete or not (q in n or n in q):continue
            match=re.search(r"\s+".join(re.escape(v) for v in label.split()),text,re.I)
            c={'source_id':source_id,'section_path':path,'sentence':text,'normalized_sentence':n,
               'unit_kind':b['kind'],'document_position':[b['document_position'],position],
               'anchor_id':anchor_id(source_id,path,text)}
            if match is not None and name in n:
                c.update(offset=match.start(),normalized_offset=n.index(name),name_dependent=False)
                c['candidate_key']='source_sentence:'+c['anchor_id']+':p'+str(match.start())
            else:
                c.update(offset=None,name_dependent=True)
                c['candidate_key']=name_key('source_sentence:'+c['anchor_id'],label)
            out.append(c)
    return sorted(out,key=lambda c:c['document_position']),[]


@lru_cache(maxsize=64)
def blocks_by_section(nbk):
    paths=GR.extract_chapters([nbk])
    if nbk not in paths:raise FileNotFoundError('frozen chapter absent: '+nbk)
    root=ET.parse(paths[nbk]).getroot();out=defaultdict(list)
    positions={id(el):i for i,el in enumerate(root.iter())}
    def atomic(el):
        if el.tag=='sec':return
        if el.tag in ('td','th','list-item','p'):
            yield {'text':GR._text(el),'kind':'table_cell' if el.tag in ('td','th') else 'list_item' if el.tag=='list-item' else 'paragraph',
                   'document_position':positions[id(el)]}
            return
        for child in el:yield from atomic(child)
    def walk(sec,trail):
        title=GR._text(sec.find('title')) if sec.find('title') is not None else ''
        here=trail+[title] if title else trail;path=' / '.join(here)
        for child in sec:
            if child.tag not in ('sec','title'):out[path].extend(b for b in atomic(child) if b['text'])
        for sub in sec.findall('sec'):walk(sub,here)
    nested={sub for sec in root.iter('sec') for sub in sec.findall('sec')}
    for sec in root.iter('sec'):
        if sec not in nested:walk(sec,[])
    return dict(out)


def propose(cid,action,evidence):
    old=action['action_key'];row={'case_id':cid,'old_key':old,'label':action['label'],'section':action['section'],
         'branches':action['applies_to'],'evidence_ids':action['evidence_ids'],'status_by_branch':action['status_by_branch'],
         'proposed_key':None,'candidates':[],'normalization':'unconfirmed' if old.startswith('drug:') and not old.startswith('drug:rxcui:') else 'not a drug key'}
    if old.startswith('drug:rxcui:'):
        row.update(status='RxCUI',proposed_key=old,name_dependent=False,normalization='RxCUI retained');return row
    candidates=[];issues=[];uncovered=set()
    pregnancy=set(action['pregnancy_note_evidence_ids']) if 'pregnancy_note_evidence_ids' in action else set()
    for eid in action['evidence_ids']:
        e=evidence[eid]
        if eid in pregnancy or e['kind']!='sourced' or e['status']!='verified':continue
        src=e['source'];sid=src['type']+':'+src['id']
        if src['type']!='nbk' or 'section' not in src:
            uncovered.add(sid);issues.append({'evidence_id':eid,'source':src,'reason':'source text/path not covered'});continue
        sections=blocks_by_section(src['id']);path=src['section']
        if path not in sections:
            uncovered.add(sid);issues.append({'evidence_id':eid,'source':src,'reason':'path not found'});continue
        got,_=locate(src['id'],path,action['label'],e['quote'],sections[path])
        for c in got:candidates.append(dict(c,evidence_id=eid))
    row.update(candidates=sorted(candidates,key=lambda c:(c['source_id'],c['document_position'])),source_issues=issues)
    documents={c['source_id'] for c in candidates}
    if len(documents)==1:
        chosen=min(candidates,key=lambda c:c['document_position'])
        row.update(selected=chosen,proposed_key=chosen['candidate_key'],
                   status='name_dependent' if chosen['name_dependent'] else 'anchor_offset',name_dependent=chosen['name_dependent'])
    elif len(documents)>1:
        row.update(status='retained_old',reason='cited matches span different documents; no global document order specified')
    elif len(uncovered)==1:
        row.update(status='name_dependent',name_dependent=True,source_id=next(iter(uncovered)),
                   proposed_key=name_key('source:'+next(iter(uncovered)),action['label']),reason='source text/path not covered')
    else:
        row.update(status='retained_old',reason='cannot locate a cited text unit or select one uncovered source ID')
    if row['proposed_key'] is None:row['proposed_key']=old
    return row


def reject_collisions(rows):
    groups=defaultdict(list)
    for r in rows:
        if r['proposed_key'] is not None:groups[r['case_id'],r['proposed_key']].append(r)
    for group in groups.values():
        if len({r['old_key'] for r in group})>1:
            for r in group:
                r.update(status='retained_old',reason='different old keys collide at the same sentence/offset',
                         colliding_old_keys=sorted({v['old_key'] for v in group}),colliding_candidate_key=r['proposed_key'],proposed_key=r['old_key'])


    reverse=defaultdict(list)
    for r in rows:
        if r['proposed_key'] is not None:reverse[r['case_id'],r['old_key']].append(r)
    for group in reverse.values():
        if len({r['proposed_key'] for r in group})>1:
            for r in group:
                r.update(status='retained_old',reason='one old key has multiple proposed source identities',
                         colliding_candidate_key=r['proposed_key'],proposed_key=r['old_key'])


def audit(out):
    if out.exists():raise FileExistsError(str(out))
    out.mkdir(parents=True)
    before=SD.build_snapshot(ROOT/'out/step3',SD.case_ids(),'before anchor audit',detailed=True)
    accepted=SD.load_snapshot(ROOT/'baselines/current/snapshot.json')
    approved={(r['case_id'],r['action_id']) for r in accepted['rows']}
    manifest=json.loads((ROOT/'runs/step3-staged-050-v3-20261118/manifest.json').read_text())
    def dataset(name,**kw):
        item=D._load_meta(Path(manifest['dataset_meta_dirs'][name]))
        if item is None:raise FileNotFoundError(name)
        return item
    protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['out/step1','out/step2','out/step3','out/step4','baselines'] for p in (ROOT/folder).rglob('*') if p.is_file()}
    rows=[]
    with frozen_io(http.CACHE_DIR,{}),patch.object(D,'ensure',dataset):
        for cid in SD.case_ids():
            led=json.loads((ROOT/'out/step3'/(cid+'.json')).read_text());ev={e['id']:e for e in led['evidence']}
            for a in led['actions']:
                if a['section'] not in SECTIONS or not a['action_key']:continue
                row=propose(cid,a,ev);row['has_accepted_row']=(cid,a['action_key']) in approved;rows.append(row)
    reject_collisions(rows)
    # Display rank only; the key uses the fixed character offset so a newly found earlier action cannot renumber it.
    groups=defaultdict(list)
    for r in rows:
        if r['status']=='anchor_offset':groups[r['case_id'],r['selected']['anchor_id']].append(r)
    for group in groups.values():
        offsets=sorted({r['selected']['offset'] for r in group})
        for r in group:r['display_order_in_sentence']=offsets.index(r['selected']['offset'])+1
    after=SD.build_snapshot(ROOT/'out/step3',SD.case_ids(),'after read-only anchor audit',detailed=True)
    for label,ref in [('since-before',before),('current',accepted)]:
        diff=SD.compare(ref,after);target=ROOT/'out/status_diff'/out.name/label
        dump(target/'snapshot.json',after);dump(target/'diff.json',diff);(target/'diff.md').write_text(SD.markdown(diff))
        if label=='since-before':assert not diff['changes']
    # Snapshot-only simulation on Accepted current: official keys and ledgers remain untouched.
    keymap={(r['case_id'],r['old_key']):r['proposed_key'] for r in rows}
    proposed=copy.deepcopy(accepted);proposed['label']='proposed key-only simulation of current'
    inverse={};key_changes=[]
    for row in proposed['rows']:
        old=row['action_id'];new=keymap[(row['case_id'],old)] if (row['case_id'],old) in keymap else old
        identity=(row['case_id'],new)
        if identity in inverse and inverse[identity]!=old:raise ValueError('Accepted key mapping collision')
        inverse[identity]=old
        row['action_id']=new
        if old!=new:key_changes.append({'case':row['case_id'],'branch':row['branch'],'section':row['section'],'old_key':old,'new_key':new})
    restored=copy.deepcopy(proposed)
    for row in restored['rows']:row['action_id']=inverse[row['case_id'],row['action_id']]
    assert restored['rows']==accepted['rows']
    normalized=SD.compare(accepted,restored)
    assert normalized['changes']==[]
    target=ROOT/'out/status_diff'/out.name/'key-only-current-simulation'
    dump(target/'snapshot.json',proposed);dump(target/'raw-diff.json',SD.compare(accepted,proposed))
    dump(target/'key-normalized-diff.json',normalized);dump(target/'key-changes.json',key_changes)
    (target/'key-normalized-diff.md').write_text(SD.markdown(normalized))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items())
    dump(out/'protected_sha256.json',protected);dump(out/'mapping.json',rows)
    unresolved=[r for r in rows if r['status']=='retained_old'];dump(out/'unable_to_locate.json',unresolved)
    dump(out/'summary.json',{'records':len(rows),'counts':{k:sum(r['status']==k for r in rows) for k in ['RxCUI','anchor_offset','name_dependent','retained_old']},
                             'approved_counts':dict(Counter(r['status'] for r in rows if r['has_accepted_row'])),
                             'protected_files_unchanged':len(protected),'model_calls':0,'network_calls':0,'keys_switched':0,'simulated_current_key_changes':len(key_changes),'non_key_changes_to_current':0})
    header='Case\tOld key\tProposed key\tLabel\tStatus\tReason\tAccepted row\tNormalization\tEvidence IDs'
    lines=[header]
    for r in rows:lines.append('\t'.join([r['case_id'],r['old_key'],r['proposed_key'] or 'UNRESOLVED',r['label'],r['status'],r['reason'] if 'reason' in r else '',str(r['has_accepted_row']),r['normalization'],','.join(r['evidence_ids'])]))
    (out/'mapping.tsv').write_text('\n'.join(lines)+'\n')
    print((out/'summary.json').read_text())

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();audit(a.out.resolve())

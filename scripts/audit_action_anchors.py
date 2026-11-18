"""Read-only 3a key proposals. Never switches keys, Evidence IDs, or baselines."""
from __future__ import annotations
import argparse
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


def locate(source_id,path,label,quote,blocks):
    """Only literal normalized matches. No aliases, stemming, dose removal, or fuzzy matching."""
    candidates={};fragments=[];name=L._norm(label);q=L._norm(quote)
    if not name or not q:raise ValueError('label and source quote must be nonempty')
    for block in blocks:
        for sentence,terminated in sentence_units(block):
            n=L._norm(sentence)
            if not (q in n or n in q) or name not in n:continue
            match=re.search(r"\s+".join(re.escape(part) for part in label.split()),sentence,re.I)
            if match is None:continue
            offset=match.start()
            candidate={'source_id':source_id,'section_path':path,'sentence':sentence,
                       'normalized_sentence':n,'offset':offset,'normalized_offset':n.index(name),
                       'anchor_id':anchor_id(source_id,path,sentence)}
            candidate['candidate_key']='source_sentence:'+candidate['anchor_id']+':p'+str(offset)
            if not terminated:
                fragments.append(candidate)
            else:
                candidates[candidate['candidate_key']]=candidate
    return list(candidates.values()),fragments


@lru_cache(maxsize=64)
def blocks_by_section(nbk):
    paths=GR.extract_chapters([nbk])
    if nbk not in paths:raise FileNotFoundError('frozen chapter absent: '+nbk)
    root=ET.parse(paths[nbk]).getroot();out=defaultdict(list)
    def atomic(el):
        if el.tag=='sec':return
        if el.tag=='p':
            yield GR._text(el);return
        if el.tag in ('td','th','list-item') and not el.findall('.//p'):
            yield GR._text(el);return
        for child in el:yield from atomic(child)
    def walk(sec,trail):
        title=GR._text(sec.find('title')) if sec.find('title') is not None else ''
        here=trail+[title] if title else trail;path=' / '.join(here)
        for child in sec:
            if child.tag not in ('sec','title'):out[path].extend(t for t in atomic(child) if t)
        for sub in sec.findall('sec'):walk(sub,here)
    nested={sub for sec in root.iter('sec') for sub in sec.findall('sec')}
    for sec in root.iter('sec'):
        if sec not in nested:walk(sec,[])
    return dict(out)


def propose(cid,action,evidence):
    old=action['action_key'];row={'case_id':cid,'old_key':old,'label':action['label'],'section':action['section'],
         'branches':action['applies_to'],'evidence_ids':action['evidence_ids'],
         'status_by_branch':action['status_by_branch'],'proposed_key':None,'candidates':[],
         'normalization':'unconfirmed' if old.startswith('drug:') and not old.startswith('drug:rxcui:') else 'not a drug key'}
    if old.startswith('drug:rxcui:'):
        row.update(status='unchanged_rxcui',proposed_key=old,normalization='RxCUI retained');return row
    candidates={};issues=[];fragments=[]
    pregnancy=set(action['pregnancy_note_evidence_ids']) if 'pregnancy_note_evidence_ids' in action else set()
    for eid in action['evidence_ids']:
        e=evidence[eid]
        if eid in pregnancy:continue
        if e['kind']!='sourced' or e['status']!='verified':continue
        src=e['source']
        if src['type']!='nbk':
            issues.append({'evidence_id':eid,'reason':'original full sentence/path not available in frozen GeneReviews reader','source':src});continue
        if 'section' not in src:
            issues.append({'evidence_id':eid,'reason':'source record has no chapter path'});continue
        path=src['section'];sections=blocks_by_section(src['id'])
        if path not in sections:
            issues.append({'evidence_id':eid,'reason':'chapter path not present in frozen source','section_path':path});continue
        got,frag=locate(src['id'],path,action['label'],e['quote'],sections[path]);fragments.extend(frag)
        for c in got:
            key=c['candidate_key']
            if key not in candidates:candidates[key]=dict(c,evidence_ids=[])
            candidates[key]['evidence_ids'].append(eid)
    row.update(candidates=list(candidates.values()),source_issues=issues,unterminated_source_fragments=fragments)
    if len(candidates)==1:
        row.update(status='proposed_anchor',proposed_key=next(iter(candidates)))
    else:
        row.update(status='unable_to_locate_uniquely',reason='multiple source sentences/paths match literally' if candidates else
                   'no literal match in a uniquely located complete source sentence')
    return row


def reject_collisions(rows):
    groups=defaultdict(list)
    for r in rows:
        if r['proposed_key'] is not None:groups[r['case_id'],r['proposed_key']].append(r)
    for group in groups.values():
        if len({r['old_key'] for r in group})>1:
            for r in group:
                r.update(status='unable_to_locate_uniquely',reason='different old keys collide at the same sentence/offset',
                         colliding_old_keys=sorted({v['old_key'] for v in group}),colliding_candidate_key=r['proposed_key'],proposed_key=None)


    reverse=defaultdict(list)
    for r in rows:
        if r['proposed_key'] is not None:reverse[r['case_id'],r['old_key']].append(r)
    for group in reverse.values():
        if len({r['proposed_key'] for r in group})>1:
            for r in group:
                r.update(status='unable_to_locate_uniquely',reason='one old key has multiple proposed source identities',
                         colliding_candidate_key=r['proposed_key'],proposed_key=None)


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
        if r['status']=='proposed_anchor':groups[r['case_id'],r['candidates'][0]['anchor_id']].append(r)
    for group in groups.values():
        offsets=sorted({r['candidates'][0]['offset'] for r in group})
        for r in group:r['display_order_in_sentence']=offsets.index(r['candidates'][0]['offset'])+1
    after=SD.build_snapshot(ROOT/'out/step3',SD.case_ids(),'after read-only anchor audit',detailed=True)
    for label,ref in [('since-before',before),('current',accepted)]:
        diff=SD.compare(ref,after);target=ROOT/'out/status_diff/action-anchor-audit-20261118'/label
        dump(target/'snapshot.json',after);dump(target/'diff.json',diff);(target/'diff.md').write_text(SD.markdown(diff))
        if label=='since-before':assert not diff['changes']
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items())
    dump(out/'protected_sha256.json',protected);dump(out/'mapping.json',rows)
    unresolved=[r for r in rows if r['status']=='unable_to_locate_uniquely'];dump(out/'unable_to_locate.json',unresolved)
    dump(out/'summary.json',{'records':len(rows),'counts':dict(Counter(r['status'] for r in rows)),
                             'approved_counts':dict(Counter(r['status'] for r in rows if r['has_accepted_row'])),
                             'protected_files_unchanged':len(protected),'model_calls':0,'network_calls':0,'keys_switched':0})
    header='Case\tOld key\tProposed key\tLabel\tStatus\tReason\tAccepted row\tNormalization\tEvidence IDs'
    lines=[header]
    for r in rows:lines.append('\t'.join([r['case_id'],r['old_key'],r['proposed_key'] or 'UNRESOLVED',r['label'],r['status'],r['reason'] if 'reason' in r else '',str(r['has_accepted_row']),r['normalization'],','.join(r['evidence_ids'])]))
    (out/'mapping.tsv').write_text('\n'.join(lines)+'\n')
    print((out/'summary.json').read_text())

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();audit(a.out.resolve())

"""Conflict-only initial screening: complete case + complete registry text, Python verdict.

Missing facts and unverified proposed conflicts retain the study for professional screening.
"""
from __future__ import annotations
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re

from aitx.disease import extract as X, live as L
from aitx.evidence import ledger as LG, patient_matching as E, trials as T
from aitx.step3.b import criteria as C

PROMPT = Path(__file__).with_name('screening_prompt.txt').read_text()
VERSION = '3b-conflict-screen-v1'
PARAMS = {'temperature':0, 'max_tokens':4096, 'response_format':{'type':'json_object'}, 'thinking':{'type':'disabled'}}
REVIEW_DIR = Path(__file__).resolve().parents[3]/'.cache/trial-conflict-reviews'


def sample(case, study):
    protocol = study['protocolSection'];eligibility = protocol['eligibilityModule']
    shared = {'title':study['title'], 'status':study['status'],
              'eligibility_metadata':{k:v for k,v in eligibility.items() if k not in ('eligibilityCriteria','studyPopulation')}}
    if 'studyPopulation' in eligibility:shared['studyPopulation']=eligibility['studyPopulation']
    if 'armsInterventionsModule' in protocol:shared['armsInterventionsModule']=protocol['armsInterventionsModule']
    return {'case_id':case['id'], 'nct_id':study['nct'],
            'patient_text':json.dumps(case,ensure_ascii=False,indent=2),
            'trial_text':'Registry context (verbatim field values):\n'+json.dumps(shared,ensure_ascii=False,indent=2)+'\n\nEligibilityCriteria (verbatim):\n'+eligibility['eligibilityCriteria']}


def messages(payload):
    return [{'role':'system','content':PROMPT},
            {'role':'user','content':json.dumps(payload,ensure_ascii=False,indent=2)+'\nReturn strictly valid JSON.'}]


def review_key(payload, conflict):
    return hashlib.sha256(json.dumps([payload,conflict],ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def quote_checks(payload, conflict):
    norm=lambda t:' '.join(t.split()).casefold()
    return {'patient_quote_valid':bool(norm(conflict['patient_fact_quote'])) and norm(conflict['patient_fact_quote']) in norm(payload['patient_text']),
            'trial_quote_valid':bool(conflict['trial_rule_quote'].strip()) and conflict['trial_rule_quote'] in payload['trial_text']}


def verify(payload, conflict, study, pf, diagnosed_genes):
    proof=quote_checks(payload,conflict)
    if conflict['axis'] not in ('preamble_or_cohort','age_sex','molecular','clinical_history') or type(conflict['other_cohort_applicable']) is not bool:
        raise ValueError('Invalid conflict schema')
    accepted=False;basis='证据或适用范围尚不能独立确认，保留人工复核'
    if all(proof.values()) and not conflict['other_cohort_applicable']:
        if conflict['axis']=='molecular':
            target=C.single_target_conflict(study,diagnosed_genes)
            accepted=target is not None and conflict['trial_rule_quote'] in target['trial_rule_quote'] and re.search(rf"\b{re.escape(target['target_gene'])}\b",conflict['trial_rule_quote']) is not None
            if accepted:basis=target['reason']
        elif conflict['axis'] in ('age_sex','preamble_or_cohort'):
            pre=prefilter(study,pf['age_months'],pf['sex'])
            accepted=any(c['result']=='fail' and c['field'] in ('age','sex') for c in pre['checks'])
            accepted=accepted or any((n['kind']=='inclusion' and n['patient_status']=='does_not_satisfy') or (n['kind']=='exclusion' and n['patient_status']=='satisfies') for n in C.enrollment_note_lines(study,pf))
            # A simple global body age criterion is comparable; cohort/compound text is not flattened.
            if not accepted and pf['age_months'] is not None and not re.search(r'\bcohort|\b(?:part|group)\s*[A-Z0-9]\b',study['criteria'],re.I):
                for item in T.split_criteria(study['criteria']):
                    if item['kind']!='inclusion' or item['parent'] or conflict['trial_rule_quote'] not in item['text']:continue
                    text=re.sub(r'^[\W_]*(?:patients?|participants?|subjects?)?\s*','',T.unescape(item['text']),flags=re.I)
                    text=re.sub(r'\bage of\b','age',text,flags=re.I)
                    note={'criteria':'Note: Currently, the study is only enrolling '+text}
                    rows=C.enrollment_note_lines(note,pf)
                    accepted=any(r['patient_status']=='does_not_satisfy' for r in rows)
                    if accepted:break
            if accepted:basis='已知年龄/性别与完整适用范围内的强制要求冲突'
        cached=REVIEW_DIR/(review_key(payload,conflict)+'.json')
        if not accepted and cached.exists():
            reviewed=json.loads(cached.read_text())
            if reviewed['payload']!=payload or reviewed['conflict']!=conflict:raise ValueError('Review binding mismatch')
            accepted=reviewed['accepted'];basis=reviewed['basis']
    return {**proof,'conflict':conflict,'accepted':accepted,'basis':basis}


def prefilter(study, age, sex):
    """Conflicting textual age ranges require review rather than an API-only exclusion."""
    pre=T.prefilter(study,age,sex)
    if age is not None:
        spans=[(T.age_months(f"{m['lo']} {m['unit']}"),T.age_months(f"{m['hi']} {m['unit']}"))
               for m in C._NOTE_RANGE.finditer(T.unescape(study['criteria']))]
        if any(lo<=age<=hi for lo,hi in spans):
            for check in pre['checks']:
                if check['field']=='age' and check['result']=='fail':
                    check.update(result='unknown',note='API年龄范围与正文可能适用的年龄范围不一致，需核实队列')
    results=[c['result'] for c in pre['checks']]
    pre['result']='fail' if 'fail' in results else 'unknown' if 'unknown' in results else 'pass'
    return pre


def plan(names, family, age, sex, genes, *, use_cache=True):
    query_names=list(dict.fromkeys([names[0]]+family))
    searches=[T.search({'query.cond':name,'filter.overallStatus':'RECRUITING,NOT_YET_RECRUITING,ENROLLING_BY_INVITATION'},use_cache=use_cache) for name in query_names]
    seen={s['nct']:s for response in reversed(searches) for s in response['studies']}
    analysed=[];ineligible=[];excluded=[]
    for study in seen.values():
        if study['status'] not in ('RECRUITING','NOT_YET_RECRUITING','ENROLLING_BY_INVITATION'):
            excluded.append(T._ex(study,'status',study['status']));continue
        pre=prefilter(study,age,sex)
        notes=C.enrollment_note_lines(study,{'age_months':age,'age_quote':None,'sex':None})
        bad_note=any((n['kind']=='inclusion' and n['patient_status']=='does_not_satisfy') or (n['kind']=='exclusion' and n['patient_status']=='satisfies') for n in notes)
        target=C.single_target_conflict(study,genes)
        record={**study,'prefilter':pre,'code_molecular_conflict':target,
                'relevance':{'by':'disease_or_family_query','name':query_names},'specific':T.specific(study,names,genes[0] if genes else '')}
        (ineligible if pre['result']=='fail' or bad_note or target else analysed).append(record)
    analysed.sort(key=lambda s:T.rank_key(s,names,genes[0] if genes else ''))
    return {'names':query_names,'gene':genes[0] if genes else None,'searches':[{k:v for k,v in s.items() if k!='studies'} for s in searches],
            'n_unique':len(seen),'analysed':analysed,'ineligible':ineligible,'excluded':excluded,'over_cap':[],
            'n_closed_relevant':0,'closed_listed':[],'parent_names':family,'screening_method':VERSION}


def record(led, study, branch, pf, case, answer, provenance, audits):
    nct=study['nct'];src={'type':'nct','id':nct,'url':T.study_url(nct)}
    payload=sample(case,study);requirements=[]
    def add(text,kind,status,fact,note,source_text,produced='code'):
        evidence=led.add(LG.sourced(f'{nct}: screening criterion {text[:100]}','clinical_trial_eligibility',[branch],src,text,source_text,study['_accessed_at'],produced_by=produced,retrieved_by='3b conflict-only screening',action={'key':f'trial:{nct}'}))
        req=LG.requirement(f'r{len(requirements)+1}',kind,text,evidence['id'],fact,status,[branch],note)
        req['fact']=fact['field']
        requirements.append(req)
        if req['result']=='unknown':led.note_missing(fact['field'],nct,text[:120],'3b')
    for r in C.registry_lines(study,pf):
        note=next(c['note'] for c in study['prefilter']['checks'] if c['field']==r['patient_fact']['field'] and 'note' in c) if any(c['field']==r['patient_fact']['field'] and 'note' in c for c in study['prefilter']['checks']) else r['note']
        add(r['text'],r['kind'],r['patient_status'],r['patient_fact'],note,C.registry_source(study))
    for r in C.enrollment_note_lines(study,pf):add(r['text'],r['kind'],r['patient_status'],r['patient_fact'],r['note'],T.unescape(study['criteria']))
    target=study['code_molecular_conflict']
    if target:
        own=next(v for v in pf['variants'] if v['gene'] in target['patient_genes'])
        add(target['trial_rule_quote'],'inclusion','does_not_satisfy',{'field':'molecular target','value':own['gene'],'quote':own['quote'],'step':1},target['reason'],study['title'] if target['quote_source']=='title' else study['criteria'])
    for audit in audits:
        if audit['accepted']:
            c=audit['conflict'];add(c['trial_rule_quote'],'exclusion','satisfies',{'field':c['axis'],'value':c['patient_fact_quote'],'quote':c['patient_fact_quote'],'step':'3b'},audit['basis'],payload['trial_text'],provenance)
    # No conflict proves only that the study remains worth screening, not full eligibility.
    if not any(r['result']=='fail' for r in requirements):
        add(study['criteria'],'other','unknown',{'field':'other trial criteria','value':None,'quote':None,'step':None},'尚未证实完整入组资格，需研究团队逐项核实',study['criteria'])
    ids=list(dict.fromkeys(r['requirement_evidence'] for r in requirements))
    failures=[r for r in requirements if r['result']=='fail']
    reason=('年龄条件与病例不符' if failures[0]['fact']=='age' else '性别条件与病例不符' if failures[0]['fact']=='sex' else failures[0]['note']) if failures else '未发现已证实硬冲突；仍有资格条件待核实'
    action=LG.action_record(f'trial:{nct}','clinical_trial_eligibility',f"{study['acronym'] or study['title']} ({nct})",[branch],requirements,ids,{branch:reason})
    classification=T.classify_pathway(study['protocolSection'])
    action.update(nct=nct,title=study['title'],url=T.study_url(nct),study_type=study['study_type'],overall_status=study['status'],phases=study['phases'],interventions=study['interventions'],specific=study['specific'],relevance=study['relevance'],protocolSection=study['protocolSection'],
                  screening={'method':VERSION,'raw_answer':answer,'conflict_audits':audits,'provenance':provenance},
                  pathway={**classification,'known_conditions':[r['requirement'] for r in requirements if r['result']=='pass'],'pending_prerequisites':[r['requirement'] for r in requirements if r['result']=='unknown'],
                           'status':'治疗性干预研究；需核实队列和完整资格' if classification['therapeutic'] else '测定或观察性研究；非治疗入组结论','target_path_supported':False,'cohort_note':'完整病例与招募原文已用于初筛，剩余条件须研究团队核实'})
    existing=next((a for a in led.actions if a['action_key']==action['action_key']),None)
    if existing is None:
        led.actions.append(action)
    else:
        for req in requirements:
            req['id']=f"r{len(existing['requirements'])+1}"
            existing['requirements'].append(req)
        existing['applies_to']=sorted(set(existing['applies_to']+[branch]))
        existing['evidence_ids']=sorted(set(existing['evidence_ids']+ids))
        existing['status_by_branch'].update(action['status_by_branch'])
        existing['screening'].setdefault('other_branch_audits',{})[branch]=action['screening']


def add_trials(led,case,step1,step2,use_cache=True):
    from aitx.step3.b.records import confirmed_target_gene
    pf=E.facts(step1,step2);plans={}
    for b in [b for b in led.branches if b['diagnosis']]:
        names=E.disease_names(b,step2)
        parents=L.mondo_parents(b['id'],use_cache=use_cache) if b['id'].startswith('MONDO:') else []
        family=list(dict.fromkeys(label.split(' or ')[0] for _,label in parents[:1]))
        genes=[b['gene']] if confirmed_target_gene(b,case,step1,step2) else []
        p=plan(names,family,pf['age_months'],pf['sex'],genes,use_cache=use_cache)
        when=min(s['queried_at'] for s in p['searches'])
        def fetch(study):
            return X._cached_chat(messages(sample(case,study)),0,use_cache,prompt_version=VERSION,call_params=PARAMS)
        with ThreadPoolExecutor(max_workers=4) as pool:
            answers=dict(zip((s['nct'] for s in p['analysed']),pool.map(fetch,p['analysed'])))
        for study, needs_model in [(s,True) for s in p['analysed']]+[(s,False) for s in p['ineligible']]:
            study=dict(study,_accessed_at=when)
            answer={'hard_conflicts':[]};pb='code';audits=[]
            if needs_model:
                payload=sample(case,study);entry=answers[study['nct']]
                answer=X._parse(entry)['parsed']
                pb={'llm':X.llm.config()['model'],'served_model':entry['served_model'],'call_id':entry['call_id'],'prompt_version':VERSION}
                audits=[verify(payload,c,study,pf,genes) for c in answer['hard_conflicts']]
            record(led,study,b['id'],pf,case,answer,pb,audits)
        if not p['analysed'] and not p['ineligible']:
            neg=led.add(LG.negative('clinical_trial_eligibility',[b['id']],database='clinicaltrials.gov',endpoint=T.API,
                query='; '.join(str(r['query']) for r in p['searches']),queried_at=when,
                n_results=p['n_unique'],response_count=p['n_unique'],
                excluded=[{'id':r['nct'],'reason':r['reason']+': '+r['detail']} for r in p['excluded']]))
            led.actions.append(LG.action_record(None,'clinical_trial_eligibility','None found',[b['id']],[],[neg['id']],
                {b['id']:'未检索到开放研究'},searched_none=True))
        plans[b['id']]={**{k:v for k,v in p.items() if k not in ('analysed','ineligible')},'analysed':[s['nct'] for s in p['analysed']],'ineligible':[s['nct'] for s in p['ineligible']]}
    led.trial_searches=plans;led.mark_searched('clinical_trial_eligibility')

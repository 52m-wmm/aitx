"""Zero-model-cost semantic audit of saved votes. No clinical status is applied."""
import json,re
from collections import Counter,defaultdict
from pathlib import Path
from aitx.evidence import action_identity as I
from scripts import kmt2b_shadow_votes as S,status_diff as SD
from scripts.step2_stability import dump

OUT=S.ROOT/'runs/kmt2b-condition-recount-20261119'
def canonical(req):
    text=S.norm(req['text']);field=req['field']
    age=re.fullmatch(r'ages?\s+(\d+)\s*[-–]\s*(\d+)\s+years?\.?',text)
    if field=='age' and age:
        lower,upper=age.groups()
        if (req['op']=='in' or (req['op']=='>=' and str(req['value'])==lower) or (req['op']=='<=' and str(req['value'])==upper)):
            return ('age_interval_closed',lower,upper,'year')
        return ('age',text,req['op'],str(req['value']),req['unit'])
    # Grammatical patient wrappers only; never remove degree, negation, timing or scope.
    text=re.sub(r'^(?:assuming that the individual is|individuals with|with)\s+','',text)
    if text.startswith('a confirmed diagnosis'):text=text[2:]
    if field=='situation' and (not req['value'] or S.norm(str(req['value'])) in text or text in S.norm(str(req['value']))):
        return (field,text,req['op'],req['unit'])
    return (field,text,req['op'] if 'op' in req else '',str(req['value']) if 'value' in req else '',req['unit'] if 'unit' in req else '')

def risk_rationale(text,quote):
    return bool(re.search(r'(?:because of (?:the )?(?:increased )?risk of|to prevent)\s+[^.;]*'+re.escape(S.norm(text)),S.norm(quote)))

def run():
    S.shadow(S.DIRS,OUT/'original')
    old=json.loads((OUT/'original/shadow.json').read_text());semantic=[];before_age=0
    ledgers=[json.loads((d/('first-vote-reassembled/replay.json' if i==0 else 'assembled/replay.json')).read_text()) for i,d in enumerate(S.DIRS)]
    for action in old['actions']:
        groups=defaultdict(list)
        for condition in action['conditions']:
            for obs in condition['observations']:
                # Full original requirement fields retained beside the canonical group.
                groups[canonical(obs['requirement'])].append(obs)
        conditions=[]
        before_age+=len(groups)
        for key,observations in groups.items():
            votes=sorted({o['vote'] for o in observations});eids=set()
            for o in observations:
                led=ledgers[o['vote']-1]
                candidates=[a for a in led['actions'] if S.norm(a['label'])==action['name']]
                o['evidence_ids']=sorted({e for a in candidates for e in a['evidence_ids']}|{r['requirement_evidence'] for a in candidates for r in a['requirements'] if S.norm(r['requirement'])==S.norm(o['requirement']['text'])})
                o['evidence_ids']=sorted(set(o['evidence_ids'])|{e['id'] for e in led['evidence'] if e['kind']=='sourced' and S.norm(e['quote'])==S.norm(o['quote'])})
                o['evidence_id_scope']='candidate action or exact source quote provenance; not a new semantic support verdict'
                eids.update(o['evidence_ids'])
            rationale=any(risk_rationale(o['requirement']['text'],o['quote']) for o in observations)
            minority=len(votes)<3
            # All unresolved restrictions conservatively treated as potentially safety/eligibility relevant.
            critical=rationale or (minority and (key[0]!='manifestation' or any(re.search(r'\b(risk|safe|infection|delay|children|dysfunction|dystonia)\b',S.norm(o['requirement']['text'])) for o in observations)))
            conditions.append({'canonical':key,'votes':votes,'majority_consensus':len(votes)>=2,'review_status':'needs_review' if minority or rationale else 'consensus','purpose_or_risk_rationale':rationale,
                'unresolved_safety_critical':bool(critical),'blocks_unconditional_applicability':bool(critical),'effective':False,
                'evidence_ids':sorted(eids),'evidence_id_status':'existing candidate provenance' if eids else 'not assigned in historical Ledger; raw source retained; needs_review','observations':observations})
        semantic.append({'name':action['name'],'votes':action['votes'],'conditions':conditions,'status':'shadow_only','kind_votes':action['kind_votes']})
    age_reductions=sum(sum(any(o['requirement']['field']=='age' and re.fullmatch(r'ages?\s+\d+\s*[-–]\s*\d+\s+years?\.?',S.norm(o['requirement']['text'])) for o in c['observations']) for c in a['conditions']) for a in old['actions'])-sum(c['canonical'][0]=='age_interval_closed' for a in semantic for c in a['conditions'])
    stats={'original_variants':sum(len(a['conditions']) for a in old['actions']),'original_single_vote':sum(len(c['votes'])==1 for a in old['actions'] for c in a['conditions']),
        'normalized_conditions':sum(len(a['conditions']) for a in semantic),'single_vote_conditions':sum(len(c['votes'])==1 for a in semantic for c in a['conditions']),
        'pure_wording_variants_collapsed':86-before_age-age_reductions,'equivalent_age_variants_collapsed':age_reductions,'wording_or_duplicate_variants_collapsed':sum(len(a['conditions']) for a in old['actions'])-sum(len(a['conditions']) for a in semantic),
        'semantic_presence_disagreements':sum(len(c['votes'])<3 for a in semantic for c in a['conditions']),
        'unresolved_safety_critical':sum(c['unresolved_safety_critical'] for a in semantic for c in a['conditions'])}
    dump(OUT/'semantic_shadow.json',{'statistics':stats,'actions':semantic,'effective':False})
    current=json.loads((S.ROOT/'out/step3/PRAC-KMT2B.json').read_text());diff=[]
    for a in semantic:
        hits=[x for x in current['actions'] if S.norm(x['label'])==a['name']]
        diff.append({'name':a['name'],'current_matches':[x['action_key'] for x in hits],'current_conditions':[x['requirements'] for x in hits],
            'shadow_conditions':a['conditions'],'unconditional_applicable_allowed':False,'meaning':'candidate presence/meaning review, no status mutation'})
    dump(OUT/'current_semantic_diff.json',diff)
    directory=OUT/'current-ledgers'
    for cid in SD.case_ids():
        can=json.loads((S.ROOT/'out/step3'/(cid+'.json')).read_text());dump(directory/(cid+'.json'),I.rewrite(can,I.case_map(cid,reverse=True)))
    snapshot=SD.build_snapshot(directory,SD.case_ids(),'current unchanged',detailed=True)
    for name,ref,cand in [('current-vs-accepted',SD.load_snapshot(S.ROOT/'baselines/current/snapshot.json'),snapshot),('shadow-vs-current',snapshot,SD.load_snapshot(OUT/'original/status_diff/vote4-vs-accepted/snapshot.json'))]:
        d=SD.compare(ref,cand);dump(OUT/name/'diff.json',d);(OUT/name/'diff.md').write_text(SD.markdown(d));dump(OUT/name/'snapshot.json',cand)
    print(json.dumps(stats))
if __name__=='__main__':run()

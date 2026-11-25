"""STOP PEDS NOT v2: one full-context request, offline comparison, no production writes."""
from __future__ import annotations
import argparse
import difflib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from aitx import budget,llm,peak
from scripts.experiments import stop_peds_full_context as base
from scripts import llm_cost

OUT=ROOT/'out/step3b-stop-peds-not-v2-20261124'
PREVIOUS=ROOT/'out/step3b-stop-peds-full-context-20261123'
ADDITION='''
VERSION 2: explicit negation and scoped time windows.
Numeric 0/1 MUST NEVER encode true/false, presence/absence, eligibility/ineligibility, or plans/no plans.
For boolean atoms (eligibility, plan, medication), use comparison="unspecified", value=null, unit="".
Use positive predicates inside explicit op="not" nodes; AND is all, OR is any. Do not hide negation in name.
Genuine source quantities such as one year are numeric durations, not boolean values.
For non-HEMT retain BOTH OR branches and every predicate, including positive genotype-based eligibility in
the second branch. A duration predicate must not silently stand in for that positive eligibility condition.
Retain the scope of the final 'and also' clause. Expand the two named combination therapies into independent
negative predicates, each with its own time window; do not put the drug disjunction into a single name.
Never express at least three months of no use as NOT(use duration >=3 months). That would admit shorter use.
Instead apply NOT to occurrence of positive treatment use ANYWHERE IN a complete lookback window.
The window belongs to the NOT node, so it is NOT(EXISTS use during window), not NOT(current use) plus an
unrelated duration atom. Unknown treatment history remains unknown even under NOT.
Attach this object to a NOT node when it has temporal scope:
"window":{"quote":"exact source words establishing the time range","anchor":"enrollment",
          "direction":"lookback|future","comparison":">=|within","value":number,"unit":"months|year"}.
Window.quote must be a substring of that NOT node's quote. A lookback 'for at least 3 months' has >=3 months;
'in the next year' is a future window within1 year. This 1 is a real interval, never a boolean encoding.
For no future plan, NOT encloses a positive plan-to-start predicate, with the next-year window on NOT.
Each separately negated therapy may cite the same complete compound source span; do not fabricate separate
verbatim sentences absent from the original. Positive atom quotes may be short literal source spans; their
name identifies the predicate and drug. Preserve source context in parent quotes.
Do not conflate genotype-based HEMT eligibility with presence of CFTR variants. Do not infer any patient facts.
Keep every condition's literal whitespace and list numbering in its source span; do not concatenate nested
CF diagnosis paragraphs into a new quote. Return the same full-trial JSON schema, now with window objects.
'''
SYSTEM=base.SYSTEM+ADDITION
ORIGINAL_VERIFY=base.verify_expression


def verify_expression(node,source):
    ORIGINAL_VERIFY(node,source)
    if node['op']=='atom' and node['fact'] in ('eligibility','plan','medication'):
        if node['value'] is not None or node['comparison']!='unspecified':
            raise ValueError('boolean predicate must not use numeric encoding')
    if 'window' in node:
        w=node['window']
        if node['op']!='not' or not w['quote'] or w['quote'] not in node['quote'] or w['anchor']!='enrollment':
            raise ValueError('window is not attached to a quoted NOT predicate')
        lookback=(w['direction']=='lookback' and w['comparison']=='>=' and w['value']==3 and w['unit']=='months'
                  and 'at least 3 months' in w['quote'])
        future=(w['direction']=='future' and w['comparison']=='within' and w['value']==1 and w['unit']=='year'
                and 'next year' in w['quote'])
        if not (lookback or future):raise ValueError('window does not match this reviewed source time expression')


def configure():
    # Only experiment-module globals change in this process; old files and production modules stay intact.
    base.OUT=OUT; base.SYSTEM=SYSTEM; base.verify_expression=verify_expression


def load_key():
    if not os.environ.get('DEEPSEEK_API_KEY'):
        for line in Path('/Users/a00/.zshrc').read_text().splitlines():
            if re.match(r'\s*(?:export\s+)?DEEPSEEK_API_KEY=',line):
                tokens=shlex.split(line,comments=True);assignment=tokens[1] if tokens[0]=='export' else tokens[0]
                name,value=assignment.split('=',1)
                if not value or '$' in value or '`' in value:raise ValueError('key must be a local literal assignment')
                os.environ[name]=value
    if not llm.config()['api_key']:raise RuntimeError('DEEPSEEK_API_KEY missing')


def walk(node):
    yield node
    for child in node.get('children',[]):yield from walk(child)


def compare():
    result=base.analyse(base.read(OUT/'parsed.json'))
    old=base.read(PREVIOUS/'comparison.json')
    source=next(c['text'] for c in base.read('config/reviewed_trial_cohorts.json')[0]['clauses'] if c['item']=='inc10')
    current,=[c for c in result['conditions'] if source in c['quote']]
    previous=next(c for c in old['conditions'] if c['id']=='inc_nonhemt_hemt_status')
    nodes=list(walk(current['expression']));oldnodes=list(walk(previous['expression']))
    audit={'old_nonhemt':previous,'new_nonhemt':current,
           'old_not_nodes':sum(n['op']=='not' for n in oldnodes),'new_not_nodes':sum(n['op']=='not' for n in nodes),
           'old_boolean_numeric_atoms':[n for n in oldnodes if n['op']=='atom' and n['fact'] in ('eligibility','plan','medication') and n['value'] is not None],
           'new_boolean_numeric_atoms':[n for n in nodes if n['op']=='atom' and n['fact'] in ('eligibility','plan','medication') and n['value'] is not None],
           'negated_windows':[{'quote':n['quote'],'window':n.get('window'),'children':n['children']} for n in nodes if n['op']=='not'],
           'cohort_scope_comparison':[{'source_item':c['item'],'expected':c['cohorts'],
                                       'model_scopes':[n['scope'] for n in result['conditions'] if c['text'] in base.T.unescape(n['quote'])]}
                                      for c in base.read('config/reviewed_trial_cohorts.json')[0]['clauses']],
           'condition_comparison':[{'old_id':c['id'],'old_kind':c['kind'],'old_scope':c['scope'],'old_quote':c['quote'],
                                   'new_matches':[n for n in result['conditions'] if n['quote']==c['quote'] or c['quote'] in n['quote'] or n['quote'] in c['quote']]}
                                   for c in old['conditions']]}
    base.save('nonhemt-comparison.json',audit)
    (OUT/'previous-vs-v2.diff').write_text(''.join(difflib.unified_diff(json.dumps(base.read(PREVIOUS/'parsed.json'),ensure_ascii=False,indent=2).splitlines(True),json.dumps(base.read(OUT/'parsed.json'),ensure_ascii=False,indent=2).splitlines(True),fromfile='previous-model.json',tofile='not-v2-model.json')))
    return audit


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true');ap.add_argument('--analyse',action='store_true');a=ap.parse_args()
    configure();OUT.mkdir(exist_ok=True);msgs=base.messages();base.save('messages.json',msgs)
    params={'temperature':0,'max_tokens':8192,'response_format':{'type':'json_object'},'thinking':{'type':'disabled'}}
    base.save('plan.json',{'trial':'NCT06654752','prompt_version':'stop-peds-full-context-not-v2','calls_authorized':1,'automatic_retries':0,'params':params,
                           'reservation_usd':llm_cost.request_reservation(msgs,8192,time.time()),'patient_sent':False})
    if a.run:
        if (OUT/'started.json').exists() or (OUT/'response.json').exists():raise FileExistsError('one attempt already started')
        load_key();peak.guard();budget.check_before_call()
        reservation=llm_cost.request_reservation(msgs,8192,time.time())
        if reservation>.1 or (budget.cap() is not None and budget.spent_today()+reservation>budget.cap()):raise budget.OverBudget('request exceeds authorized budget')
        base.save('started.json',{'at':time.time(),'reservation_usd':reservation,'offpeak':True})
        response=llm.chat(msgs,**params);base.save('response.json',response)
        if response['choices'][0]['finish_reason']!='stop':raise ValueError('incomplete response saved; no retry')
        base.save('parsed.json',json.loads(response['choices'][0]['message']['content']))
        print(json.dumps({'model':response['model'],'usage':response['usage']},ensure_ascii=False),flush=True)
    if a.analyse or a.run:
        audit=compare();print(json.dumps({'nonhemt_verification':audit['new_nonhemt']['verification_status'],'not_nodes':audit['new_not_nodes']},ensure_ascii=False))


if __name__=='__main__':main()

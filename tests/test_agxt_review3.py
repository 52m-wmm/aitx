"""Third report review: stored code verdicts, conservative trial criteria and readable provenance."""
import json
from pathlib import Path
import re

import pytest

from aitx.evidence import trials as T, ledger as LG
from aitx.step3.b import criteria as C
from aitx.report import assemble as A, validate as V
from tests.test_report import act, build, ev, ledger, unk, variant_evidence, CASE
from tests.test_criteria import PF, BR

FIXTURE=json.loads((Path(__file__).parent/'fixtures/agxt_trial_criteria_review.json').read_text())
PATIENT=dict(PF,age_months=84,age_quote='7-year-old')


def criteria_rows(nct,pf=PATIENT):
    f=FIXTURE[nct]
    return C.lines_for({'nct':nct,'criteria':f['criteria']},f['mapped'],pf,{'facts':[]},BR,[])


def test_bilirubin_gilbert_and_inr_warfarin_allowances_are_not_independent_exclusions():
    rows=criteria_rows('NCT06511349')
    assert len(rows)==2
    raw=T.unescape(FIXTURE['NCT06511349']['criteria'])
    assert all(r['patient_status']=='unknown' and r['text'] in raw for r in rows)
    assert any("Gilbert's syndrome" in r['text'] and 'it is eligible' in r['text'] for r in rows)
    assert any('warfarin' in r['text'] and 'will be allowed' in r['text'] for r in rows)
    assert all(r['text'] not in ('the total bilirubin < 2 x ULN','with INR < 3.5') for r in rows)


def test_mapping_fragments_regain_their_full_original_subject_and_object():
    rows=criteria_rows('NCT06839235')
    raw=T.unescape(FIXTURE['NCT06839235']['criteria'])
    assert all(r['text'] in raw for r in rows)
    assert all('Female participants' in r['text'] for r in rows if r.get('fact')=='pregnancy')
    assert all('RNA interference' in r['text'] for r in rows if r.get('fact') in ('current_medication','prior_therapy'))


@pytest.mark.parametrize('age,want',[(84,'satisfies'),(None,'unknown')])
def test_cohort_age_is_an_or_of_complete_ranges(age,want):
    rows=criteria_rows('NCT04580420',dict(PATIENT,age_months=age,age_quote='7-year-old' if age is not None else None))
    notes=[r for r in rows if r.get('details',{}).get('enrollment_note')]
    assert len(notes)==1 and notes[0]['patient_status']==('does_not_satisfy' if age is not None else 'unknown')
    rows=[r for r in rows if r not in notes]
    assert len(rows)==1 and rows[0]['patient_status']==want
    if age is not None:
        assert [o['requirement'] for o in rows[0]['any_of'] if o['patient_status']=='satisfies']==['children 6 to 11 years of age']


@pytest.mark.parametrize('months,want',[(84,'satisfies'),(60,'does_not_satisfy'),(None,'unknown')])
def test_a_verified_text_age_comparison_uses_the_patients_age(months,want):
    m={'fact':'age','quote':'Age ≥ 6 years','op':'>=','value':6,'unit':'years'}
    assert C.evaluate(m,dict(PATIENT,age_months=months),{'facts':[]},BR,[])[0]==want


@pytest.mark.parametrize('nct,months,matched,unmatched',[
    ('NCT06839235',84,'inc4','inc3'),
    ('NCT06654752',180,'inc2','inc3'),
])
def test_age_cohorts_within_registry_range_never_exclude(nct,months,matched,unmatched):
    pf=dict(PATIENT,age_months=months,age_quote=f'{months//12}-year-old')
    rows=[r for r in criteria_rows(nct,pf) if r.get('fact')=='age']
    assert all(LG.requirement_result(r['kind'],r['patient_status'])!='fail' for r in rows)
    assert all(r['patient_status']=='satisfies' for r in rows if r['item']==matched)
    assert all(r['patient_status']=='unknown' for r in rows if r['item']==unmatched)
    assert all(r['text'] in T.unescape(FIXTURE[nct]['criteria']) for r in rows)


@pytest.mark.parametrize('months,want',[(60,'does_not_satisfy'),(84,'satisfies'),(None,'unknown')])
def test_only_the_structured_total_age_range_can_exclude(months,want):
    nct='NCT06839235'; f=FIXTURE[nct]
    study={'nct':nct,'criteria':f['criteria'],'min_age':f['min_age'],'max_age':f['max_age'],
           'sex':'ALL','healthy_volunteers':False,'conditions':['PH1']}
    pf=dict(PATIENT,age_months=months)
    registry=C.registry_lines(study,pf)
    assert next(r for r in registry if r['item']=='registry:age')['patient_status']==want
    assert all(LG.requirement_result(r['kind'],r['patient_status'])!='fail'
               for r in criteria_rows(nct,pf) if r.get('fact')=='age')


def test_recognized_age_group_cannot_turn_nonmatching_cohorts_into_exclusion():
    f=FIXTURE['NCT04580420']; ids={'inc1','inc3','inc4'}
    mapped={'items':[it for it in f['mapped']['items'] if it['id'] in ids],
            'mappings':[m for m in f['mapped']['mappings'] if m['id'] in ids]}
    rows=C.lines_for({'criteria':f['criteria']},mapped,dict(PATIENT,age_months=180),{'facts':[]},BR,[])
    assert any(r['patient_status']=='does_not_satisfy' for r in rows if r.get('details',{}).get('enrollment_note'))
    rows=[r for r in rows if not r.get('details',{}).get('enrollment_note')]
    assert len(rows)==1 and rows[0]['patient_status']=='unknown'


def test_bespoke_restores_stored_classification_reasons_exceptions_and_unassessed_items():
    methods=[{'section':'bespoke_therapies','label':'AAV','modality':'gene_replacement','classification':'theoretically_possible',
              'conclusion':'AAV: theoretically possible on molecular grounds alone.','criteria_met':['CDS is 1176 nt'],
              'failed_criterion':None,'exceptions':[],'unassessable_reason':['vector design not assessed'],
              'applies_to':['B'],'evidence_ids':[]},
             {'section':'bespoke_therapies','label':'exon skipping','modality':'aso_exon_skipping','classification':'not_eligible',
              'conclusion':'Not eligible.','failed_criterion':'first coding exon: skipping removes the start codon',
              'exceptions':['nearby in-frame start codon exception'],'unassessable_reason':[], 'applies_to':['B'],'evidence_ids':[]}]
    led=ledger(methods);led['evidence'].append(variant_evidence());md,_=build(led)
    body=md.split('### Bespoke Therapies')[1].split('### Drug Repurposing')[0]
    for text in ('theoretically possible','not eligible','first coding exon: skipping removes the start codon',
                 'nearby in-frame start codon exception','vector design not assessed'):
        assert text in body
    pre=md.split('**Preclinical validation**:')[1].split('**Safety**:')[0]
    assert 'AAV' in pre and 'exon skipping' not in pre


def test_trial_columns_keep_exclusions_out_of_inclusion_met():
    r=dict(unk('pregnant'),kind='exclusion',result='pass')
    a=act('trial:T','clinical_trial_eligibility','Trial T','conditional',[r,dict(unk('renal function'),kind='inclusion')],
          study_type='interventional',nct='NCT00000001',url='https://clinicaltrials.gov/study/NCT00000001')
    md,_=build(ledger([a]));part=md.split('### Clinical Trial Eligibility')[1].split('### Off-label')[0]
    assert '| Trial | Inclusion met | Exclusion ruled out | Unable to assess | Known exclusions | Status & verified date |' in part
    row=next(l for l in part.splitlines() if l.startswith('| **'))
    cells=re.split(r'(?<!\\)\|',row)
    assert 'pregnant' not in cells[2] and 'pregnant' in cells[3]
    assert '&quot;' not in md and '[Trial T]' not in part


def test_ranking_includes_all_tiers_in_the_requested_order():
    good={'section':'bespoke_therapies','label':'AAV','modality':'gene_replacement','classification':'theoretically_possible',
          'conclusion':'Theoretical.','failed_criterion':None,'exceptions':[],'unassessable_reason':[],
          'applies_to':['B'],'evidence_ids':[]}
    led=ledger([act('drug:L','existing_targeted_therapies','Tier1 yes','applicable'),
                act('drug:N','existing_targeted_therapies','Tier1 if','conditional',[unk('renal function')]),
                act('trial:T','clinical_trial_eligibility','Tier2 trial','conditional',study_type='interventional'),good])
    led['evidence'].append(variant_evidence());md,_=build(led);rank=md.split('**Ranking**:')[1].split('**Evidence table**')[0]
    assert rank.index('Tier1 yes')<rank.index('Tier1 if')<rank.index('Tier2 trial')<rank.index('AAV')


def test_evidence_is_compact_with_complete_mappings_and_exact_template_headings():
    led=ledger([act('drug:L','existing_targeted_therapies','drug L','applicable',evs=tuple(f'e{i}' for i in range(7)))])
    led['evidence']=[ev(f'e{i}',f'Source passage {i}.') for i in range(7)]
    md,_=build(led)
    assert all(len(V.REF.findall(line))<=3 for line in md.splitlines())
    assert '**Evidence table**' in md and '#### Evidence table' not in md
    assert not V.check_report(md,led,'P')
    assert V.check_report(md+'\n#### Extra heading\n',led,'P')
    assert V.check_report(md+'\n未检查\n',led,'P')


def test_same_source_outcome_sentence_is_not_repeated_and_a_repeat_is_rejected():
    led=ledger([]);led['report_context']={'outcomes':[{'kind':'safety','label':'T','evidence_id':'e1'}]*2}
    led['evidence'][0]['quote']='Incidence of adverse events.'
    md,_=build(led);body=md.split('**Safety**:')[1].split('**Efficacy measures**:')[0]
    assert body.count('Incidence of adverse events.')==1
    line=next(l for l in body.splitlines() if 'Incidence' in l)
    assert V.check_report(md.replace(line,line+'\n'+line),led,'P')


def test_trial_full_clause_hides_its_duplicate_fragment_with_the_same_result():
    full='2. Receiving standard care. Patients not receiving lumasiran need screening.'
    fragment='Patients not receiving lumasiran need screening.'
    rs=[dict(unk(full),item='inc2'),dict(unk(fragment),item='inc2')]
    a=act('trial:T','clinical_trial_eligibility','Trial T','conditional',rs,
          study_type='interventional',nct='NCT00000001')
    led=ledger([a]);led['evidence'][0]['quote']=full
    md,_=build(led);part=md.split('### Clinical Trial Eligibility')[1].split('### Off-label')[0]
    assert part.count(fragment)==1
    assert not V.check_report(md,led,'P')
    assert V.sentences('2. First clause. 2. Second clause.')==['First clause.','Second clause.']


def test_stiripentol_is_a_reported_fact_without_a_recommendation():
    a=act('drug:S','off_label_expanded_access','Stiripentol','conditional',efficacy_direction='reported_ineffective')
    led=ledger([a]);led['evidence'][0]['quote']='No decrease in plasma oxalate was observed.'
    md,_=build(led);part=md.split('### Off-label')[1].split('## Tier 3')[0]
    assert 'No decrease in plasma oxalate was observed.' in part and 'not recommended' not in part

"""Report-only regressions; retired 3b mapping tests are in the rebuild snapshot."""
import re
from aitx.report import assemble as A, validate as V
from tests.test_report import act, build, ev, ledger, unk, variant_evidence, CASE


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

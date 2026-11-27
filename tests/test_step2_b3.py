import copy,csv
import pytest
from tests.test_disease import ont
from aitx.disease import hpo as H,sources as S
from aitx.disease.datasets import LocalFile


def test_b1_zero_frequency_is_not_positive_match(ont):
    out=H.score(ont,['HP:0001250'],[],[S.Annotation('HP:0001250',0,False,1),S.Annotation('HP:0000478',1,False,2)])
    assert out['score']==0 and out['matches'][0]['ic']==0


def test_b1_unknown_frequency_is_retained(ont):
    out=H.score(ont,['HP:0001250'],[],[S.Annotation('HP:0001250',None,False,1)])
    assert out['score']>0 and out['matches'][0]['common_ancestor']=='HP:0001250'


def test_b2_siblings_share_mica_but_contribute_zero(ont):
    o=H.Ontology(LocalFile("hpo_ontology",ont.test_path,"","test",0,0,"",0))
    o.build_ic(ont.test_ann)
    o.terms['HP:9999999']=H.Term('HP:9999999','Other seizure',[],False,None)
    o.parents['HP:9999999']={'HP:0001250'}
    assert o.mica('HP:9999999','HP:0007359')[1]>0
    out=H.score(o,['HP:9999999'],[],[S.Annotation('HP:0007359',1,False,1)])
    assert out['score']==0 and out['matches'][0]['disease_term'] is None


@pytest.mark.parametrize('patient,disease',[('HP:0001250','HP:0007359'),('HP:0007359','HP:0001250'),('HP:0007359','HP:0007359')])
def test_b2_keeps_exact_and_ancestor_descendant(ont,patient,disease):
    assert H.score(ont,[patient],[],[S.Annotation(disease,1,False,1)])['score']>0


def test_g2p_keeps_inferred_mechanism_as_disease_evidence(tmp_path):
    fields=['g2p id','gene symbol','disease MONDO','disease mim','disease name','allelic requirement','confidence',
        'molecular mechanism','molecular mechanism support','variant consequence','variant types','cross cutting modifier',
        'molecular mechanism evidence','publications','date of last review']
    row=dict.fromkeys(fields,'');row.update({'g2p id':'G2P00088','gene symbol':'OTC','disease mim':'311250',
        'disease name':'OTC deficiency','allelic requirement':'monoallelic_X_hemizygous','confidence':'definitive',
        'molecular mechanism':'loss of function','molecular mechanism support':'inferred'})
    p=tmp_path/'g.csv'
    with p.open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow(row)
    lf=LocalFile('g2p',p,'','test',0,0,'',1)
    r=S.load_g2p(lf,{'OTC'})[0]
    assert r['mechanism_support']=='inferred' and r['patient_variant_mechanism']=='unknown'
    assert r['allelic_requirement']=='monoallelic_X_hemizygous'
    assert r['disease_ids']==['OMIM:311250'] and r['cite']['line']==2 and r['raw_record']==row
    assert S.load_g2p(lf,{'OTHER'})==[]


def test_native_uncertain_general_and_unmapped_never_reach_mica():
    from aitx.disease.pipeline import patient_phenotype_terms
    terms=[dict(hpo_id='HP:'+str(i),scope=scope,status=status,valid=valid) for i,(scope,status,valid) in enumerate([
        ('patient','present',True),('patient','absent',True),('patient','possible',True),
        ('patient','unknown',True),('general','present',True),('unknown','present',True),('patient','present',False)])]
    assert patient_phenotype_terms({'patient_facts':{'clinical':{'phenotypes':terms}},'phenotypes':[]})==(['HP:0'],['HP:1'])


def test_legacy_possible_is_not_positive():
    from aitx.disease.pipeline import patient_phenotype_terms
    assert patient_phenotype_terms({'patient_facts':{},'phenotypes':[dict(hpo_id='HP:1',valid=True,status='possible')]})==([],[])


def test_mica_lead_is_not_final_diagnosis_but_explicit_diagnosis_stays():
    from aitx.disease.pipeline import auxiliary_selection
    cs=[dict(key=k,excluded=False,compete=True,clinvar=[],inheritance={'result':'consistent'}) for k in ['a','b']]
    sel=dict(status='resolved',basis='phenotype',id='a',lead=.9,tied=[],reasons=['highest score'])
    r=auxiliary_selection(sel,cs)
    assert r['status']=='ambiguous' and r['id']=='a' and r['tied']==['a','b']
    assert auxiliary_selection(dict(sel,basis='explicit'),cs)['status']=='resolved'
    assert auxiliary_selection(dict(sel,basis='only_candidate'),cs)['status']=='resolved'


def test_clinvar_lower_star_candidate_not_promoted_by_auxiliary_gate():
    from aitx.disease.pipeline import auxiliary_selection
    cs=[dict(key=k,excluded=False,compete=True,clinvar=[{'stars':stars}]) for k,stars in [('a',2),('b',1)]]
    sel=dict(status='resolved',basis='clinvar',id='a',lead=.9,tied=[],reasons=[])
    assert auxiliary_selection(sel,cs)==sel
    cs[1]['clinvar'][0]['stars']=2
    assert auxiliary_selection(sel,cs)['status']=='ambiguous'


def test_b1_does_not_drop_unknown_record_sharing_id_with_zero(ont):
    rows=[S.Annotation('HP:0001250',0,False,1),S.Annotation('HP:0001250',None,False,2)]
    assert H.score(ont,['HP:0001250'],[],rows)['score']>0


def test_b1_all_zero_is_zero_match_not_missing_annotations(ont):
    out=H.score(ont,['HP:0001250'],[],[S.Annotation('HP:0001250',0,False,1)])
    assert out['score']==0 and out['annotated_terms']==1

"""ENACT frozen source/mappings: reviewed clinical clauses must remain active unknowns."""
import copy
import socket

import pytest

from aitx.evidence import ledger as LG
from aitx.step3.b import criteria as C
from tests.test_criteria import _PF, _conf_branch

SOURCE = 'Inclusion Criteria:\n\n* documentation of CF diagnosis per CFF diagnostic criteria and known CFTR genotype\n* age 2 years and older\n* ability to provide written informed consent and/or assent (by subject and/or legal guardian)\n* on a stable dose of triple combination CFTR modulator therapy for at least two weeks prior to Visit 1\n* clinically stable lung disease, defined as no documented acute decrease in FEV1 \\> 10%, OR use of additional antibiotics (intravenous \\[IV\\] or oral \\[PO\\]) within 4 weeks prior to screening\n\nExclusion Criteria:\n\n* recent significant unintentional weight loss, as determined by the investigator, in the 4 weeks prior to screening\n* pregnant or breastfeeding female\n* history of alcohol or substance abuse in the 6 months prior to screening\n* participation in a study involving an investigational intervention within 28 days (or 5 half-lives, whichever is longer) prior to screening\n* in the opinion of the Investigator, medical or psychiatric illness, or other conditions that would interfere with participation'
RAW = {'criteria': [{'id': 'inc1',
               'quote': 'documentation of CF diagnosis per CFF diagnostic criteria',
               'fact': 'diagnosis',
               'op': '',
               'value': '',
               'unit': '',
               'name': '',
               'group': ''},
              {'id': 'inc1',
               'quote': 'known CFTR genotype',
               'fact': 'genetic_confirmation',
               'op': '',
               'value': '',
               'unit': '',
               'name': 'CFTR',
               'group': ''},
              {'id': 'inc2',
               'quote': 'age 2 years and older',
               'fact': 'age',
               'op': '>=',
               'value': 2,
               'unit': 'years',
               'name': '',
               'group': ''},
              {'id': 'inc3',
               'quote': 'ability to provide written informed consent and/or assent (by subject and/or legal '
                        'guardian)',
               'fact': 'administrative',
               'op': '',
               'value': '',
               'unit': '',
               'name': '',
               'group': ''},
              {'id': 'inc4',
               'quote': 'on a stable dose of triple combination CFTR modulator therapy for at least two '
                        'weeks prior to Visit 1',
               'fact': 'current_medication',
               'op': '>=',
               'value': 2,
               'unit': 'weeks',
               'name': 'triple combination CFTR modulator therapy',
               'group': ''},
              {'id': 'inc5',
               'quote': 'clinically stable lung disease, defined as no documented acute decrease in FEV1 > '
                        '10%',
               'fact': 'lab',
               'op': '>',
               'value': 10,
               'unit': '%',
               'name': 'FEV1',
               'group': ''},
              {'id': 'inc5',
               'quote': 'use of additional antibiotics (intravenous [IV] or oral [PO]) within 4 weeks prior '
                        'to screening',
               'fact': 'current_medication',
               'op': '<=',
               'value': 4,
               'unit': 'weeks',
               'name': 'additional antibiotics',
               'group': ''},
              {'id': 'exc1',
               'quote': 'recent significant unintentional weight loss, as determined by the investigator, in '
                        'the 4 weeks prior to screening',
               'fact': 'weight',
               'op': '<=',
               'value': 4,
               'unit': 'weeks',
               'name': 'unintentional weight loss',
               'group': ''},
              {'id': 'exc2',
               'quote': 'pregnant',
               'fact': 'pregnancy',
               'op': '',
               'value': '',
               'unit': '',
               'name': 'pregnancy',
               'group': ''},
              {'id': 'exc2',
               'quote': 'breastfeeding female',
               'fact': 'pregnancy',
               'op': '',
               'value': '',
               'unit': '',
               'name': 'breastfeeding',
               'group': ''},
              {'id': 'exc3',
               'quote': 'history of alcohol or substance abuse in the 6 months prior to screening',
               'fact': 'diagnosis',
               'op': '<=',
               'value': 6,
               'unit': 'months',
               'name': 'alcohol or substance abuse',
               'group': ''},
              {'id': 'exc4',
               'quote': 'participation in a study involving an investigational intervention within 28 days '
                        '(or 5 half-lives, whichever is longer) prior to screening',
               'fact': 'other_trial',
               'op': '<=',
               'value': 28,
               'unit': 'days',
               'name': '',
               'group': ''},
              {'id': 'exc5',
               'quote': 'in the opinion of the Investigator, medical or psychiatric illness, or other '
                        'conditions that would interfere with participation',
               'fact': 'other',
               'op': '',
               'value': '',
               'unit': '',
               'name': '',
               'group': ''}]}


@pytest.fixture
def frozen(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('network/model calls forbidden')
    monkeypatch.setattr(socket,'socket',forbidden)
    monkeypatch.setattr('aitx.llm.chat',forbidden)
    monkeypatch.setattr(C,'_llm',lambda *a,**kw: (copy.deepcopy(RAW),'code'))
    study={'nct':'NCT07148739','criteria':SOURCE}
    return study,C.map_study(study)


def rows(study,mapped,extra=None):
    branch=dict(_conf_branch(),gene='CFTR',diagnosis={'label':'cystic fibrosis'},parent_names=[])
    pf=dict(_PF,age_months=180,age_quote='15-year-old',sex='male',sex_quote='male',
            variants=[{'gene':'CFTR','protein':'p.Phe508del','quote':'CFTR p.Phe508del homozygous'}])
    return C.lines_for(study,mapped,pf,extra or {'facts':[]},branch,['cystic fibrosis','CF'])


def test_reviewed_five_clauses_remain_unknown_in_place(frozen):
    study,mapped=frozen
    assert len(mapped['mappings'])==8
    assert [r['rejected'] for r in mapped['rejected']]==[
        'threshold 2 not in the quote', *["comparison '<=' not as written"]*4]
    result=rows(study,mapped)
    assert len(result)==12  # registry age is added separately by _record
    for iid in ('inc4','inc5','exc1','exc3','exc4'):
        line,=[r for r in result if r['item']==iid]
        original=next(it for it in mapped['items'] if it['id']==iid)
        assert line['text']==C.T.unescape(original['text'])
        assert line['patient_status']=='unknown' and line['patient_fact']['value'] is None
        assert line['details']['reviewed_rejections']
    assert [r['patient_status'] for r in result if r['item']=='inc1']==['satisfies','satisfies']
    assert next(r for r in result if r['item']=='inc3')['patient_status']=='not_assessed'


def test_other_unknowns_resolved_do_not_hide_these_clauses(frozen):
    study,mapped=frozen
    result=rows(study,mapped)
    reqs=[LG.requirement(str(i),r['kind'],r['text'],'e',r['patient_fact'],r['patient_status'],['b'])
          for i,r in enumerate(result)]
    for r,line in zip(reqs,result):
        if line['item'] not in ('inc4','inc5','exc1','exc3','exc4') and r['result']=='unknown':
            r.update(result='pass',patient_status='does_not_satisfy' if r['kind']=='exclusion' else 'satisfies')
    assert LG.status_of(reqs,'b')[0]=='conditional'


def test_medication_presence_and_duplicate_rejections_do_not_bypass_review(frozen):
    study,mapped=frozen
    mapped['rejected']+=copy.deepcopy(mapped['rejected'])
    extra={'facts':[{'kind':'current_medication','name':'triple combination CFTR modulator therapy',
                     'status':'present','quote':'Taking triple combination CFTR modulator therapy'}]}
    result=rows(study,mapped,extra)
    line,=[r for r in result if r['item']=='inc4']
    assert line['patient_status']=='unknown' and len(result)==12
    line,=[r for r in result if r['item']=='inc5']
    assert 'OR use of additional antibiotics' in line['text'] and 'within 4 weeks' in line['text']
    assert len(line['details']['reviewed_rejections'])==1


@pytest.mark.parametrize('change',['nct','source','rejection'])
def test_override_only_applies_to_exact_reviewed_enact_clause(frozen,change):
    study,mapped=frozen
    if change=='nct':study['nct']='NCT00000001'
    elif change=='source':
        next(it for it in mapped['items'] if it['id']=='inc4')['text']+=' Additional criterion.'
    else:
        next(r for r in mapped['rejected'] if r['id']=='inc4')['quote']='Invented condition'
    line,=[r for r in rows(study,mapped) if r['item']=='inc4']
    assert line['patient_status']=='not_assessed'

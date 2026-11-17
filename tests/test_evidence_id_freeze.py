"""Frozen evidence identity: repeated source text and identity context must retain the same ID."""
import json
from pathlib import Path

from aitx.evidence import ledger as L


def source_record(**metadata):
    values=dict(produced_by='code',retrieved_by='first retrieval',action={'key':'procedure:x'})
    values.update(metadata)
    return L.sourced('Source describes measure X.','supportive_management',['B'],
                     {'type':'url','id':'https://example.org/source','url':'https://example.org/source'},
                     'Measure X is described.','Measure X is described.',1,**values)


def test_frozen_source_id_is_independent_of_retrieval_producer_and_time():
    first=source_record()
    again=source_record(produced_by={'llm':'another provider'},retrieved_by='later cached retrieval')
    assert first['id']==again['id']=='f7c92f93375f'
    later=L.sourced(first['claim'],first['section'],first['applies_to'],first['source'],first['quote'],
                    first['quote'],987654321,action=first['action'])
    assert later['id']==first['id']


def test_frozen_reasoning_and_negative_id_golden_vectors():
    source=source_record()
    reasoning=L.reasoning('Computed premise.','bespoke_therapies',['B'],[source['id']])
    negative=L.negative('supportive_management',['B'],database='registry',endpoint='https://example.org',
                        query='gene X',queried_at=1,n_results=0,response_count=0)
    assert reasoning['id']=='cf3113ba138d'
    assert negative['id']=='bdfb658c0319'


def test_identity_context_remains_part_of_the_frozen_source_key():
    assert source_record(action={'key':'procedure:other'})['id']!=source_record()['id']


def test_stability_observations_record_cached_disagreement_without_overrides():
    data=json.loads((Path(__file__).resolve().parents[1]/'data/eval/context_check_stability.json').read_text())
    cases=data['cases']
    assert len(cases)==6 and len({c['id'] for c in cases})==6
    kmt=[c for c in cases if c['case']=='PRAC-KMT2B']
    ataxia=[c for c in cases if c['case']=='PRAC-ANO10']
    assert len(kmt)==4 and all(c['cached_answer']['final']=='split' for c in kmt)
    assert {c['cached_answer']['final'] for c in ataxia}=={'this_disease_patients','other_gene_or_subtype_patients'}
    assert all(len(c['cached_answer']['answers'])==3 and 'override' not in c for c in cases)

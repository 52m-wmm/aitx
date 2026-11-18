from scripts.quote_step3a_votes import counts


def test_duplicate_source_inputs_share_new_votes_but_not_patient_independence():
    rows=[{'call_id':'A','extract_kind':'GR section'},{'call_id':'A','extract_kind':'GR section'},
          {'call_id':'B','extract_kind':'FDA conditions'}]
    result=counts(rows)
    assert result['extra_votes_shared']==4
    assert result['extra_votes_independent_cases']==6
    assert result['full_triple_cold_shared']==6
    assert result['by_type_per_case']=={'GR section':2,'FDA conditions':1}

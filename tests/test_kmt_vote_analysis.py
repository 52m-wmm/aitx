from scripts.analyze_kmt2b_one_vote import raw_groups,conditions,context_unmeasured


def test_raw_grouping_keeps_multiple_mentions_and_does_not_expand_generics():
    groups=raw_groups([{'name':'Walkers','quote':'q1'},{'name':'walkers','quote':'q2'},{'name':'adaptive aids','quote':'q3'}])
    assert len(groups['walkers'])==2
    assert set(groups)=={'walkers','adaptive aids'}


def test_unmeasured_context_is_separate_from_extracted_conditions():
    action={'requirements':[{'kind':'other','requirement':'age','result':'unknown'},
                            {'kind':'other','requirement':'source scope','result':'unknown','context_check':'scope'}],
            'context_check':{'answers':{'limit':{'final':'not_tested','answers':[]}}}}
    assert context_unmeasured(action)
    assert len(conditions(action))==2 and len(conditions(action,True))==1

from scripts.compare_kmt2b_low import missing_actions

def test_incidental_iep_and_504_mentions_do_not_pass_action_recall_gate():
    items=[{'name':'physical therapy','quote':'PT in the IEP.'},{'name':'assistive technology devices','quote':'A 504 plan includes devices.'}]
    assert missing_actions(items,['individualized education plan (IEP)','504 plan'])==['individualized education plan (IEP)','504 plan']

def test_source_named_abbreviations_and_controlled_therapy_labels_match():
    items=[{'name':'IEP'},{'name':'speech services'},{'name':'physical therapy (PT)'}]
    assert not missing_actions(items,['individualized education plan (IEP)','Speech-language therapy','physical therapy'])

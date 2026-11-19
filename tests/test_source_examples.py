from aitx.evidence.examples import group_items,source_groups

def item(name,quote,requirements=None):return {'name':name,'quote':quote,'kind':'device','requirements':requirements or [],'manifestation':''}

def test_eg_parent_members_full_quote_and_no_member_promotion():
    q='Adaptive aids (e.g., ankle-foot orthoses, walkers) can support and maintain ambulation.'
    old=[item('walkers',q,[{'text':'adults'}]),item('Adaptive aids',q)]
    out=group_items(old)
    assert {x['name'] for x in out}=={'Adaptive aids'}
    assert all(x['examples']==['ankle-foot orthoses','walkers'] and x['quote']==q for x in out)
    assert out[0]['example_member']['requirements']==[{'text':'adults'}]
    assert out[0]['example_review_pending'] and out[0]['kind']=='device'
    assert old[0]['name']=='walkers'

def test_such_as_and_no_group_for_ordinary_actions_or_unrelated_quote():
    q='Adaptive aids such as walkers and orthoses can help.'
    assert source_groups(q)[0]['examples']==['walkers','orthoses']
    assert group_items([item('DBS','DBS and physiotherapy are used.')])[0]['name']=='DBS'
    assert group_items([item('PT',q)])[0]['name']=='PT'

def test_example_drugs_are_members_not_rxcui_synonyms():
    q='Use of levodopa and other agents (e.g., baclofen, gabapentin) is reported.'
    out=group_items([item('baclofen',q),item('levodopa',q)])
    assert [x['name'] for x in out]==['other agents','levodopa']


def test_report_quotes_source_examples_not_separate_actions():
    from tests.test_report import ev,act,ledger,build
    q='Adaptive aids (e.g., ankle-foot orthoses, walkers) can help.'
    a=act('aids','supportive_management','Adaptive aids','conditional',examples=['ankle-foot orthoses','walkers'],example_evidence_ids=['e1'])
    led=ledger([a]);led['evidence']=[ev('e1',q)]
    report=build(led)
    text=report[0] if isinstance(report,tuple) else report
    if isinstance(text,dict):text=text['report_markdown']
    assert q in text and 'Examples from source:' in text
    assert '**walkers**' not in text and '**ankle-foot orthoses**' not in text


def test_no_loss_of_parent_qualifier_or_oxford_comma_alias():
    q='Adaptive aids (e.g., orthoses, walkers, and braces) can help.'
    g=source_groups(q,['aids'])[0]
    assert g['parent']=='Adaptive aids'
    assert g['examples']==['orthoses','walkers','braces']

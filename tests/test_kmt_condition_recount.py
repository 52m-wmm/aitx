from scripts.kmt2b_condition_recount import canonical

def req(text,field='situation',op='',value='',unit=''):
    return dict(text=text,field=field,op=op,value=value,unit=unit)
def test_only_grammatical_wrappers_equivalent():
    assert canonical(req('with a confirmed diagnosis'))==canonical(req('confirmed diagnosis'))
    assert canonical(req('safe to eat by mouth'))==canonical(req('Assuming that the individual is safe to eat by mouth'))
    assert canonical(req('severe dystonia'))!=canonical(req('dystonia'))
    assert canonical(req('no dystonia'))!=canonical(req('dystonia'))
    assert canonical(req('during winter'))!=canonical(req('during pregnancy'))
def test_age_op_and_values_do_not_collide():
    assert canonical(req('Ages 0-3 years','age','>=',0,'year'))==canonical(req('Ages 0-3 years','age','<=',3,'year'))
    assert canonical(req('Ages 0-3 years','age','<',3,'year'))!=canonical(req('Ages 0-3 years','age','<=',3,'year'))

def test_prevention_rationale_is_not_established_disease():
    from scripts.kmt2b_condition_recount import risk_rationale
    assert risk_rationale('pulmonary infections','Immunizations because of the increased risk of pulmonary infections.')
    assert risk_rationale('infection','Use this to prevent infection.')
    assert not risk_rationale('infection','For patients with infection, treat infection.')
    assert not risk_rationale('low GFR','For patients with low GFR, use this to prevent infection.')

from scripts.audit_action_anchors import anchor_id,locate,reject_collisions


def test_anchor_ignores_model_fields_and_offsets_use_source_not_list_order():
    sentence='Use walkers and ankle-foot orthoses.'
    a,_=locate('NBK1','Management','walkers','Use walkers and ankle-foot orthoses.',[sentence])
    b,_=locate('NBK1','Management','ankle-foot orthoses',sentence,[sentence])
    assert a[0]['anchor_id']==b[0]['anchor_id']
    assert a[0]['offset']==4 and b[0]['offset']==16
    assert a[0]['candidate_key']!=b[0]['candidate_key']
    assert anchor_id('NBK1','Management',sentence)==anchor_id('NBK1','Management','USE walkers  and ankle-foot orthoses.')
    assert anchor_id('NBK1','Other',sentence)!=a[0]['anchor_id']
    assert anchor_id('NBK1','management',sentence)!=a[0]['anchor_id']


def test_paraphrase_and_general_category_do_not_get_forced_slots():
    changed,_=locate('NBK1','Management','adaptive aids','Use walkers and braces.',['Use walkers and braces.'])
    assert changed[0]['name_dependent'] and ':name:adaptive%20aids' in changed[0]['candidate_key']
    found,fragments=locate('NBK1','Management','walkers','walkers',['walkers'])
    assert not found and not fragments
    cells=[{'text':'walkers','kind':'table_cell','document_position':7}]
    found,_=locate('NBK1','Management','walkers','walkers',cells)
    assert found[0]['offset']==0 and not found[0]['name_dependent']


def test_first_literal_offset_and_ambiguous_sentence_collision():
    found,_=locate('NBK1','Management','fluids','Use fluids; increase fluids.',['Use fluids; increase fluids.'])
    assert found[0]['offset']==4
    rows=[{'case_id':'C','old_key':k,'proposed_key':found[0]['candidate_key'],'status':'proposed_anchor'} for k in ['x','y']]
    reject_collisions(rows)
    assert all(r['proposed_key']==r['old_key'] and r['status']=='retained_old' for r in rows)


def test_character_slot_is_first_offset_in_original_sentence_text():
    sentence='Use  walkers and walkers.'
    found,_=locate('NBK1','Management','walkers',sentence,[sentence])
    assert found[0]['offset']==5
    assert found[0]['normalized_offset']==4
    assert found[0]['candidate_key'].endswith(':p5')


def test_one_old_key_cannot_split_into_two_new_keys():
    rows=[{'case_id':'C','old_key':'old','proposed_key':k,'status':'proposed_anchor'} for k in ['new1','new2']]
    reject_collisions(rows)
    assert all(r['proposed_key']==r['old_key'] and r['status']=='retained_old' for r in rows)


def test_only_cited_unit_is_eligible_and_units_follow_document_order():
    blocks=[{'text':'Use walkers.','kind':'paragraph','document_position':1},
            {'text':'Use walkers after assessment.','kind':'list_item','document_position':5}]
    found,_=locate('NBK1','Management','walkers','Use walkers after assessment.',list(reversed(blocks)))
    assert len(found)==1 and found[0]['document_position']==[5,0]


def test_uncovered_source_uses_source_id_plus_normalized_name():
    from scripts.audit_action_anchors import propose
    action={'action_key':'drug:name:benzodiazepines','label':'Benzodiazepines','section':'supportive_management',
            'applies_to':['B'],'evidence_ids':['E'],'status_by_branch':{'B':{'status':'conditional','reason':'unknown'}}}
    evidence={'E':{'kind':'sourced','status':'verified','source':{'type':'pmid','id':'123'},'quote':'Benzodiazepines were used.'}}
    row=propose('C',action,evidence)
    assert row['status']=='name_dependent'
    assert row['proposed_key']=='source:pmid:123:name:benzodiazepines'
    assert row['normalization']=='unconfirmed'

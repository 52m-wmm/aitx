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
    assert locate('NBK1','Management','adaptive aids','Use walkers and braces.',['Use walkers and braces.'])==([],[])
    found,fragments=locate('NBK1','Management','walkers','walkers',['walkers'])
    assert not found and fragments  # original table/list fragment needs review, not an invented sentence


def test_first_literal_offset_and_ambiguous_sentence_collision():
    found,_=locate('NBK1','Management','fluids','Use fluids; increase fluids.',['Use fluids; increase fluids.'])
    assert found[0]['offset']==4
    rows=[{'case_id':'C','old_key':k,'proposed_key':found[0]['candidate_key'],'status':'proposed_anchor'} for k in ['x','y']]
    reject_collisions(rows)
    assert all(r['proposed_key'] is None and r['status']=='unable_to_locate_uniquely' for r in rows)


def test_character_slot_is_first_offset_in_original_sentence_text():
    sentence='Use  walkers and walkers.'
    found,_=locate('NBK1','Management','walkers',sentence,[sentence])
    assert found[0]['offset']==5
    assert found[0]['normalized_offset']==4
    assert found[0]['candidate_key'].endswith(':p5')


def test_one_old_key_cannot_split_into_two_new_keys():
    rows=[{'case_id':'C','old_key':'old','proposed_key':k,'status':'proposed_anchor'} for k in ['new1','new2']]
    reject_collisions(rows)
    assert all(r['proposed_key'] is None for r in rows)

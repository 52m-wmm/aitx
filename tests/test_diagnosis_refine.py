"""Fix plan D1 (decision 2026-11-11): a disease group named in the text gives way to the more specific disease ClinVar
links the variant to, when MONDO places that disease within the group; otherwise the named disease stands."""
from aitx.disease import resolve as R

LEIGH, LSFC, OTHER = "MONDO:0009723", "MONDO:0009069", "MONDO:0000001"
CMT, CMT1B = "MONDO:0015626", "MONDO:0007307"
TREE = {LSFC: {LEIGH}, CMT1B: {CMT}}            # specific -> its ancestors (as OLS returns them)


def contains(group, specific):
    return group in TREE.get(specific, set())


def cand(key, label, stars=None, score=0.5):
    return {"key": key, "label": label, "excluded": False, "specific": True, "grouping": [],
            "phenotype": {"score": score}, "inheritance": {"result": "consistent"},
            "clinvar": [{"vcv": "VCV1", "stars": stars, "clinical_significance": "Pathogenic"}] if stars is not None else []}


def test_leigh_named_but_clinvar_links_the_french_canadian_type():
    sel = R.select([cand(LEIGH, "Leigh syndrome"), cand(LSFC, "LSFC", stars=2)], [], [], [LEIGH], contains)
    assert sel["id"] == LSFC and sel["refined_from"] == LEIGH and sel["basis"] == "explicit"
    assert "MONDO places within it" in sel["reasons"][0]


def test_cmt_named_but_clinvar_links_cmt1b():
    sel = R.select([cand(CMT, "Charcot-Marie-Tooth disease"), cand(CMT1B, "CMT1B", stars=1)], [], [], [CMT], contains)
    assert sel["id"] == CMT1B


def test_reverse_no_hierarchy_relation_keeps_the_named_disease():
    sel = R.select([cand(LEIGH, "Leigh syndrome"), cand(OTHER, "other", stars=2)], [], [], [LEIGH], contains)
    assert sel["id"] == LEIGH and "refined_from" not in sel


def test_reverse_named_disease_more_specific_than_the_clinvar_one_stands():
    sel = R.select([cand(LSFC, "LSFC"), cand(LEIGH, "Leigh syndrome", stars=2)], [], [], [LSFC], contains)
    assert sel["id"] == LSFC


def test_reverse_no_clinvar_link_keeps_the_named_disease():
    sel = R.select([cand(LEIGH, "Leigh syndrome"), cand(LSFC, "LSFC")], [], [], [LEIGH], contains)
    assert sel["id"] == LEIGH


def test_reverse_without_a_hierarchy_nothing_changes():
    sel = R.select([cand(LEIGH, "Leigh syndrome"), cand(LSFC, "LSFC", stars=2)], [], [], [LEIGH])
    assert sel["id"] == LEIGH


def test_the_best_clinvar_star_level_wins_among_contained_diseases():
    a, b = "MONDO:A", "MONDO:B"
    tree = {a: {LEIGH}, b: {LEIGH}}
    sel = R.select([cand(LEIGH, "Leigh"), cand(a, "A", stars=1, score=0.9), cand(b, "B", stars=2, score=0.1)], [], [],
                   [LEIGH], lambda g, s: g in tree.get(s, set()))
    assert sel["id"] == b

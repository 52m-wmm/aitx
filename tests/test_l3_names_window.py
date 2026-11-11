"""Fix plan N2 + O2 (2026-11-11): L3 searches with the literature's names for the gene's disorder, and the text window
puts this disease's sections first."""
from aitx.evidence import fallback as F


def test_thra_query_carries_the_orphanet_name_and_gene_related(monkeypatch):
    monkeypatch.setitem(F._GENE_NAMES, "THRA", ["Resistance to thyroid hormone due to a mutation in thyroid hormone "
                                                "receptor alpha", "congenital nongoitrous hypothyroidism 6", "THRA-related"])
    q = F.literature_query("THRA", ["congenital nongoitrous hypothyroidism 6", "CHNG6"])
    assert '"Resistance to thyroid hormone due to a mutation in thyroid hormone receptor alpha"[tiab]' in q
    assert '"THRA-related"[tiab]' in q and q.startswith("((THRA[tiab]) AND")      # the gene stays required
    assert q.count('"congenital nongoitrous hypothyroidism 6"[tiab]') == 1         # no duplicate names


def test_reverse_without_a_disease_name_there_is_still_no_search(monkeypatch):
    monkeypatch.setitem(F._GENE_NAMES, "LRPPRC", ["Leigh syndrome", "LRPPRC-related"])
    assert F.literature_query("LRPPRC", []) is None and F.literature_query("LRPPRC", ["LS"]) is None


REVIEW = "\n".join([
    "## INTRODUCTION", "Neonatal respiratory failure is common. " * 50,
    "## Management of respiratory distress", "Surfactant and ventilation are standard. " * 50,
    "## Alveolar Capillary Dysplasia with Misalignment of the Pulmonary Veins (FOXF1)",
    "ACDMPV is lethal; ECMO may bridge to lung transplantation evaluation. " * 10,
    "## Primary Ciliary Dyskinesia", "PCD needs airway clearance. " * 50])


def test_the_window_puts_this_diseases_section_first():
    focus = ["alveolar capillary dysplasia with misalignment of pulmonary veins", "ACDMPV", "FOXF1"]
    shown = F.text_for_llm("Abstract.", REVIEW, limit=1500, focus=focus)
    assert "ECMO may bridge" in shown and F.focus_hits(shown, focus) > 0
    old = F.text_for_llm("Abstract.", REVIEW, limit=1500)                  # without focus: management first, as before
    assert "ECMO may bridge" not in old and F.focus_hits(old, focus) == 0


def test_reverse_a_single_disease_article_keeps_the_old_order():
    """Every section names the disease: the order is the old one - management sections first."""
    art = "## Background\nGRIN2B disorder.\n## Treatment\nMemantine was tried in GRIN2B patients."
    assert F.text_for_llm("A.", art, focus=["GRIN2B"]) == F.text_for_llm("A.", art)

"""A gene symbol counts only as the patient's genetic condition (decision 2026-11-10, blind test).

3b admitted two colorectal-cancer trials for a Leigh-syndrome patient because "LRPPRC Positive" named the gene;
3c had the same fault on 2026-11-05. And a gene-family overview offered an LRPPRC patient biotin, thiamine,
coenzyme Q10 and the ketogenic diet from table rows for other disorders.
"""
import pytest

from aitx.evidence import established as E
from aitx.evidence import fallback as F
from aitx.evidence import genecontext as GC
from aitx.evidence import trials as T


def _study(title, conditions, keywords=()):
    return {"title": title, "conditions": list(conditions), "keywords": list(keywords)}


# --- 3b relevance

def test_cancer_trials_are_not_relevant_by_gene():
    crc = _study("Gossypol Acetate + FOLFIRI + Bev in mCRC With TP53-Mutant and LRPPRC Positive",
                 ["Colorectal Cancer", "LRPPRC Positive"])
    assert T.relevance(crc, ["congenital lactic acidosis, Saguenay-Lac-Saint-Jean type"], "LRPPRC") is None
    crc2 = _study("Sintilimab Plus Gossypol Acetate in Advanced Colorectal Cancer",
                  ["Advanced Colorectal Cancer"], ["LRPPRC"])
    assert T.relevance(crc2, ["Leigh syndrome"], "LRPPRC") is None


def test_a_marker_use_is_not_the_patients_condition_even_outside_a_cancer_study():
    s = _study("Assay study", ["LRPPRC Positive"])
    assert T.relevance(s, ["Leigh syndrome"], "LRPPRC") is None


@pytest.mark.parametrize("study,names,gene", [
    (_study("Quinidine in KCNT1 epilepsy", ["Epilepsy"], ["KCNT1"]), ["KCNT1-related epilepsy"], "KCNT1"),
    (_study("Open-label study", ["GRIN2B-related Neurodevelopmental Disorder"]), ["intellectual disability"], "GRIN2B"),
    (_study("Gene therapy", ["OTC Deficiency"]), ["ornithine transcarbamylase deficiency"], "OTC"),
])
def test_rare_disease_trials_still_match_by_gene(study, names, gene):
    """Reverse: the gene path still admits a rare-disease trial whose entries name the gene."""
    got = T.relevance(study, names, gene)
    assert got is not None and got["by"] in ("gene", "disease")


def test_a_disease_name_match_is_unaffected():
    s = _study("Lung carcinoma screening in cystic fibrosis", ["Cystic Fibrosis", "Lung Cancer"])
    assert T.relevance(s, ["cystic fibrosis"], "CFTR")["by"] == "disease"   # named by its disease, not by the gene


def test_specific_uses_the_same_rule():
    crc = _study("x", ["LRPPRC Positive", "Colorectal Cancer"])
    assert T.specific(crc, ["Leigh syndrome"], "LRPPRC") is False


@pytest.mark.parametrize("text,want", [
    ("LRPPRC Positive", True), ("KRAS-mutant", True), ("EGFR expression", True), ("ALK fusion", True),
    ("KCNT1-related epilepsy", False), ("GRIN2B", False), ("OTC deficiency", False),
])
def test_biomarker_use(text, want):
    gene = text.split()[0].split("-")[0]
    assert GC.biomarker_use(gene, text) is want


def test_3c_and_3b_share_one_cancer_pattern():
    from aitx.evidence import offlabel as O
    assert O._CANCER is GC.CANCER
    assert GC.cancer_context("metastatic colorectal cancer (mCRC)") and not GC.cancer_context("Leigh syndrome")


# --- L3: no gene-only query

def test_literature_query_needs_a_disease_name():
    assert F.literature_query("LRPPRC", []) is None
    assert F.literature_query("LRPPRC", ["LS"]) is None                    # too short to be a usable name
    q = F.literature_query("LRPPRC", ["Leigh syndrome"])
    assert "LRPPRC[tiab]" in q and '"Leigh syndrome"[tiab]' in q


def test_search_literature_skips_without_a_name(monkeypatch):
    monkeypatch.setattr(F, "_get_json", lambda url: pytest.fail("must not search"))
    got = F.search_literature("LRPPRC", [])
    assert got["papers"] == [] and got["skipped"] == F.NO_DISEASE_NAME


# --- overview table rows for another disorder

TABLE = "\n".join([
    "Table 7. Leigh Syndrome Spectrum Disorders with Targeted Therapies",
    "Row 1: [Disorder: Biotin-thiamine-responsive basal ganglia disease (thiamine transporter-2 deficiency)] "
    "[Treatment: Biotin & thiamine supplementation] [Comments: Manifestations typically resolve within days.]",
    "Row 2: [Disorder: Primary coenzyme Q10 deficiency] [Treatment: Coenzyme Q10 supplementation] [Comments: early]",
    "Row 3: [Disorder: LRPPRC-related Leigh syndrome] [Treatment: Avoid fasting] [Comments: none]",
    "Row 4: [Disorder: Congenital lactic acidosis, Saguenay-Lac-Saint-Jean type] [Treatment: Bicarbonate] [Comments: -]",
])
SUPPORT = "Row 1: [Manifestation/Concern: Feeding/Nutrition] [Treatment: Caloric supplementation] [Considerations/Other: x]"


def test_other_disorder_rows_are_dropped():
    names = ["congenital lactic acidosis, Saguenay-Lac-Saint-Jean type", "Leigh syndrome, French-Canadian type"]
    assert E.row_for_other_disorder(TABLE, "Biotin & thiamine supplementation", {"LRPPRC"}, names)
    assert E.row_for_other_disorder(TABLE, "Coenzyme Q10 supplementation", {"LRPPRC"}, names)


def test_rows_for_this_gene_or_disease_are_kept():
    names = ["congenital lactic acidosis, Saguenay-Lac-Saint-Jean type"]
    assert E.row_for_other_disorder(TABLE, "Avoid fasting", {"LRPPRC"}, names) is None      # names the gene
    assert E.row_for_other_disorder(TABLE, "Bicarbonate", {"LRPPRC"}, names) is None         # names the disease


def test_rows_without_a_disorder_column_are_left_to_the_existing_filter():
    """Reverse: a manifestation-organised table has no disorder column, so this rule says nothing about it."""
    assert E.row_for_other_disorder(SUPPORT, "Caloric supplementation", {"LRPPRC"}, ["Leigh syndrome"]) is None
    assert E.row_for_other_disorder("Some prose. Caloric supplementation.", "Caloric supplementation",
                                    {"LRPPRC"}, ["Leigh syndrome"]) is None


def test_a_patient_with_that_other_disorder_keeps_the_row():
    """Reverse: the same row stays for the patient who does have primary CoQ10 deficiency (gene COQ4)."""
    assert E.row_for_other_disorder(TABLE, "Coenzyme Q10 supplementation", {"COQ4"},
                                    ["Primary coenzyme Q10 deficiency"]) is None


def test_a_one_word_quote_inside_the_disorder_cell_is_still_dropped():
    """The quote "Thiamine" also appears in its row's disorder cell ("Biotin-thiamine-responsive basal ganglia
    disease"); the disorder cell must still be checked (2026-11-10 regression)."""
    names = ["congenital lactic acidosis, Saguenay-Lac-Saint-Jean type"]
    assert E.row_for_other_disorder(TABLE, "Thiamine", {"LRPPRC"}, names)
    assert E.row_for_other_disorder(TABLE, "Biotin", {"LRPPRC"}, names)
    # and the patient whose disorder that row is for keeps it
    assert E.row_for_other_disorder(TABLE, "Thiamine", {"SLC19A3"},
                                    ["Biotin-thiamine-responsive basal ganglia disease"]) is None

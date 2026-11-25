import pytest

from aitx.evidence import patient_matching as E

from aitx.evidence import fallback as F

from aitx.evidence import genecontext as GC

from aitx.evidence import trials as T

def _study(title, conditions, keywords=()):
    return {"title": title, "conditions": list(conditions), "keywords": list(keywords)}

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

def test_literature_query_needs_a_disease_name():
    assert F.literature_query("LRPPRC", []) is None
    assert F.literature_query("LRPPRC", ["LS"]) is None                    # too short to be a usable name
    q = F.literature_query("LRPPRC", ["Leigh syndrome"])
    assert "LRPPRC[tiab]" in q and '"Leigh syndrome"[tiab]' in q

def test_search_literature_skips_without_a_name(monkeypatch):
    monkeypatch.setattr(F, "_get_json", lambda url: pytest.fail("must not search"))
    got = F.search_literature("LRPPRC", [])
    assert got["papers"] == [] and got["skipped"] == F.NO_DISEASE_NAME

def test_the_exclusion_reason_names_the_rule_that_excluded_the_study():
    """O3 (2026-11-11): cancer studies excluded by the gene-as-condition rule had the old 'no entry names the gene'."""
    crc = _study("Gossypol in mCRC With LRPPRC Positive", ["Colorectal Cancer", "LRPPRC Positive"])
    assert "cancer study or as a marker" in T.exclusion_reason(crc, ["Leigh syndrome"], "LRPPRC")
    other = _study("Asthma study", ["Asthma"])
    assert T.exclusion_reason(other, ["Leigh syndrome"], "LRPPRC") == "no Condition or Keyword entry names the disease or gene"
    lung = _study("SHARP", ["Small Cell Lung Cancer"], ["LS-SCLC"])
    assert T.exclusion_reason(lung, ["Leigh syndrome", "LS"], "LRPPRC").startswith("only the short abbreviation 'LS'")

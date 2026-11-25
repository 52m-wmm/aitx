import hashlib

import json

import pytest

from aitx.evidence import patient_matching as E

from aitx.evidence import fallback as F

from aitx.evidence import ledger as LG

S2 = {"genereviews": {"AGXT": [{"nbk": "NBK1283", "scope": "single_gene"}],
                      "ANO10": [{"nbk": "NBK1138", "scope": "multi_gene"}]}}

BRS = [{"id": "b1", "gene": "AGXT", "diagnosis": {"label": "primary hyperoxaluria type 1"}},
       {"id": "b2", "gene": "ANO10", "diagnosis": {"label": "spinocerebellar ataxia 10"}},
       {"id": "b3", "gene": "SLC35A2", "diagnosis": {"label": "SLC35A2-CDG"}}]

TITLES = {"NBK1283": "Primary Hyperoxaluria Type 1", "NBK1138": "Hereditary Ataxia Overview",
          "NBK1244": "Classic Ehlers-Danlos Syndrome"}

def test_branch_tiers_chapter_overview_none_per_branch():
    use, rec = F.branch_tiers({"b1": ["NBK1283", "NBK1138"], "b2": ["NBK1138"], "b3": []}, S2, BRS, TITLES.get)
    assert use == {"b1": ["NBK1283"], "b2": ["NBK1138"], "b3": []}         # one case, three different tiers
    assert rec["b1"]["tier"] == "chapter" and rec["b1"]["not_used"][0]["nbk"] == "NBK1138"   # decision 3: no overview
    assert rec["b2"]["tier"] == "overview" and "disease-group" in rec["b2"]["label"]
    assert rec["b3"]["tier"] is None

def test_overview_advice_about_another_gene_is_not_used():
    genes = ["ANO10", "ATXN1", "SETX", "FXN"]
    assert F.other_gene_named("In FXN-related ataxia, omaveloxolone is approved.", genes, "ANO10") == "FXN"
    assert F.other_gene_named("Physical therapy for all hereditary ataxias.", genes, "ANO10") is None
    assert F.other_gene_named("ANO10 ataxia: coenzyme Q10 has been tried.", genes, "ANO10") is None   # its own gene
    assert F.other_gene_named("FXNA is not a gene here", genes, "ANO10") is None                      # whole symbols only

def test_best_tier():
    sp = lambda t, typ="nbk": {"tier_source": t, "src": {"type": typ}}
    assert F.best_tier([sp("overview"), sp("chapter")]) == "chapter"
    assert F.best_tier([sp("symptomatic"), sp("literature")]) == "literature"
    assert F.best_tier([{"src": {"type": "spl_setid"}}]) == "label"

def test_literature_query_has_gene_names_and_publication_types():
    q = F.literature_query("SLC35A2", ["SLC35A2-congenital disorder of glycosylation", "CDG"])
    assert "SLC35A2[tiab]" in q and '"SLC35A2-congenital disorder of glycosylation"[tiab]' in q and '"CDG"' not in q
    assert '"Review"[pt]' in q and '"Practice Guideline"[pt]' in q and "Case Reports" not in q

XML = ("<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID Version='1'>111</PMID><Article><Abstract>"
       "<AbstractText Label='A'>We recommend early physical therapy.</AbstractText><AbstractText>Ketogenic diet "
       "<i>reduced</i> seizures.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle>"
       "<PubmedArticle><MedlineCitation><PMID>222</PMID></MedlineCitation></PubmedArticle></PubmedArticleSet>")

def test_abstracts_parsed_per_pmid():
    assert F.abstracts_by_pmid(XML) == {"111": "We recommend early physical therapy. Ketogenic diet reduced seizures.", "222": ""}

def test_search_fetches_open_access_full_text_only_and_drops_case_reports(monkeypatch):
    fetched = []

    class R:
        def __init__(self, text):
            self.text = text

    def get(url, timeout=30, **k):
        fetched.append(url)
        if "esearch" in url:
            return R(json.dumps({"esearchresult": {"count": "3", "idlist": ["111", "222", "333"]}}))
        if "esummary" in url:
            return R(json.dumps({"result": {
                "111": {"title": "Review", "pubdate": "2024", "pubtype": ["Review"], "articleids": [{"idtype": "pmc", "value": "PMC1"}]},
                "222": {"title": "Case", "pubdate": "2023", "pubtype": ["Case Reports"], "articleids": [{"idtype": "pmc", "value": "PMC2"}]},
                "333": {"title": "Cohort", "pubdate": "2022", "pubtype": ["Observational Study"], "articleids": [{"idtype": "pmc", "value": "PMC3"}]}}}))
        if "efetch.fcgi?db=pubmed" in url:
            return R(XML)
        if "db=pmc" in url and url.endswith("id=1"):
            return R('<article><front><permissions><license license-type="open-access" xlink:href="https://creativecommons.org/licenses/by/4.0/">'
                     "CC BY</license></permissions></front><body><p>Full text recommends speech therapy.</p></body></article>")
        if "db=pmc" in url:                       # not open access: no body, no open license
            return R("<article><front><abstract><p>Abstract only.</p></abstract></front></article>")
        raise AssertionError(url)
    monkeypatch.setattr(F.http, "get", get)
    rec = F.search_literature("SLC35A2", ["SLC35A2-CDG"])
    p = {x["pmid"]: x for x in rec["papers"]}
    assert p["111"]["oa"] is True and "speech therapy" in p["111"]["full_text"]
    assert p["222"]["excluded"] == "case report" and not any("PMC2" in u for u in fetched)       # never fetched
    assert p["333"]["oa"] is False and p["333"]["full_text"] == ""                               # not OA: abstract only
    assert p["111"]["license"].startswith("[open-access license]") and "CC BY" in p["111"]["license"]

def test_tier_checks_catch_violations():
    act = lambda t, sym=None: {"action_key": f"k:{t}", "section": "supportive_management", "applies_to": ["b1"],
                               "tier_source": t, **({"for_symptom": sym} if sym else {})}
    ok = {"b1": {"tier": "chapter", "results_above": True, "gap_filled": [{"hpo_id": "HP:1"}]}}
    assert F.tier_problems(ok, [act("chapter"), act("symptomatic", {"hpo_id": "HP:1"})], {"HP:1"}) == []
    assert F.tier_problems(ok, [act(None)], set())                                          # no tier_source
    assert F.tier_problems(ok, [act("symptomatic", {"hpo_id": "HP:2"})], {"HP:1", "HP:2"})  # symptom already covered
    assert F.tier_problems(ok, [act("symptomatic", {"hpo_id": "HP:9"})], {"HP:1"})          # symptom not present
    bad = {"b1": {"tier": "chapter", "results_above": True, "literature": {"query": "q"}}}
    assert F.tier_problems(bad, [], set())                                                  # literature despite a chapter

AGXT_MGMT = ("Supportive Care. Maintain high oral fluid intake. Nephrocalcinosis and stones are managed by a urologist. "
             "Targeted therapy is effective in persons with chronic kidney disease (CKD).")

def test_chapter_text_names_the_symptom():
    assert F.names_symptom(AGXT_MGMT, ["Nephrocalcinosis", "Too much calcium deposited in kidneys"]) == "Nephrocalcinosis"
    assert F.names_symptom(AGXT_MGMT, ["Chronic kidney disease", "CKD"]) == "Chronic kidney disease"
    assert F.names_symptom("in persons with CKD", ["Chronic renal failure", "CKD"]) == "CKD"
    # reverse: not named -> not covered; short abbreviations only in upper case; whole words only
    assert F.names_symptom(AGXT_MGMT, ["Seizure", "Seizures", "Epilepsy"]) is None
    assert F.names_symptom("ckd is lower case here", ["CKD"]) is None
    assert F.names_symptom("nephrocalcinosis-like", ["calcinosis"]) is None

def test_multi_gene_disease_chapter_is_a_chapter_not_an_overview():
    # 2026-11-05: Classic Ehlers-Danlos Syndrome (3 genes) had been labelled "disease-group advice"
    s2 = {"genereviews": {"COL1A1": [{"nbk": "NBK1244", "scope": "multi_gene"}]}}
    assert F.chapter_tier("NBK1244", s2, TITLES.get) == "chapter"
    assert F.chapter_tier("NBK1138", S2, TITLES.get) == "overview"
    assert F.chapter_tier("NBK9999", s2, lambda n: None) == "chapter"            # no title, no metadata: a chapter
    assert F.chapter_tier("NBK1244", s2, lambda n: None) == "overview"           # no title: the gene count decides

def test_one_papers_open_access_failure_does_not_stop_the_layer(monkeypatch):
    class R:
        def __init__(self, text):
            self.text = text

    def get(url, timeout=30, **k):
        if "esearch" in url:
            return R(json.dumps({"esearchresult": {"count": "1", "idlist": ["111"]}}))
        if "esummary" in url:
            return R(json.dumps({"result": {"111": {"pubdate": "2024", "pubtype": ["Review"], "articleids": [{"idtype": "pmc", "value": "PMC1"}]}}}))
        if "efetch.fcgi?db=pubmed" in url:
            return R(XML)
        raise RuntimeError("HTTP 404 for " + url)
    monkeypatch.setattr(F.http, "get", get)
    rec = F.search_literature("SLC35A2", ["SLC35A2-CDG"])
    p = rec["papers"][0]
    assert p["oa"] is None and "404" in p["oa_error"] and p["full_text"] == "" and p["abstract"]

def test_long_full_text_puts_management_sections_first():
    full = "## Introduction\n" + "intro " * 3000 + "\n## Genetics\n" + "gene " * 3000 + "\n## Treatment and Management\nWe recommend a ketogenic diet."
    out = F.text_for_llm("Abstract text.", full, limit=2000)
    assert out.startswith("Abstract text.") and "We recommend a ketogenic diet." in out and len(out) <= 2000
    assert F.text_for_llm("A.", "") == "A."

def test_author_manuscript_is_usable_and_plain_abstract_record_is_not(monkeypatch):
    # decision 2026-11-05: PMC author manuscripts may be text-mined (PMC copyright notice); basis recorded
    class R:
        def __init__(self, t):
            self.text = t
    am = ('<article><front><custom-meta><meta-name>pmc-prop-manuscript</meta-name><meta-value>yes</meta-value></custom-meta>'
          '<permissions><license><license-p>Users may view, print, copy, and download text and data-mine the content</license-p>'
          "</license></permissions></front><body><p>non-blinded observational pilot study</p></body></article>")
    closed = ('<article><front><custom-meta><meta-name>pmc-prop-manuscript</meta-name><meta-value>no</meta-value></custom-meta>'
              "</front><body><p>text</p></body></article>")
    monkeypatch.setattr(F.http, "get", lambda url, timeout=30, **k: R(am if url.endswith("id=1") else closed))
    ok, text, lic = F.pmc_open_access_text("PMC1")
    assert ok and "non-blinded observational pilot study" in text and lic.startswith("[PMC author manuscript]")
    ok, text, lic = F.pmc_open_access_text("PMC2")                       # reverse: no license, no flag -> not used
    assert not ok and text == ""

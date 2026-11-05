"""Supportive fallback chain (contract docs/supportive_fallback_contract.md v2): offline, network and LLM stubbed."""
import hashlib
import json

import pytest

from aitx.evidence import established as E
from aitx.evidence import fallback as F
from aitx.evidence import ledger as LG

S2 = {"genereviews": {"AGXT": [{"nbk": "NBK1283", "scope": "single_gene"}],
                      "ANO10": [{"nbk": "NBK1138", "scope": "multi_gene"}]}}
BRS = [{"id": "b1", "gene": "AGXT", "diagnosis": {"label": "primary hyperoxaluria type 1"}},
       {"id": "b2", "gene": "ANO10", "diagnosis": {"label": "spinocerebellar ataxia 10"}},
       {"id": "b3", "gene": "SLC35A2", "diagnosis": {"label": "SLC35A2-CDG"}}]


# --- L1 / L2

def test_branch_tiers_chapter_overview_none_per_branch():
    use, rec = F.branch_tiers({"b1": ["NBK1283", "NBK1138"], "b2": ["NBK1138"], "b3": []}, S2, BRS)
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


# --- L3

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
        if "oa.fcgi" in url:
            return R('<OA><records><record id="PMC1"/></records></OA>' if "PMC1" in url else
                     '<OA><error code="idIsNotOpenAccess">not OA</error></OA>')
        if "db=pmc" in url:
            return R("<article><body><p>Full text recommends speech therapy.</p></body></article>")
        raise AssertionError(url)
    monkeypatch.setattr(F.http, "get", get)
    rec = F.search_literature("SLC35A2", ["SLC35A2-CDG"])
    p = {x["pmid"]: x for x in rec["papers"]}
    assert p["111"]["oa"] is True and "speech therapy" in p["111"]["full_text"]
    assert p["222"]["excluded"] == "case report" and not any("PMC2" in u for u in fetched)       # never fetched
    assert p["333"]["oa"] is False and p["333"]["full_text"] == ""                               # not OA: abstract only
    assert not any("db=pmc&retmode=xml&id=3" in u for u in fetched)


def _stub_common(monkeypatch, *, lit=None, llm_items=(), support="supported", table=None):
    monkeypatch.setattr(E, "ontology", lambda: type("O", (), {
        "exact_lookup": lambda self, t: ["HP:0001250"] if "seiz" in t.lower() else [],
        "search": lambda self, t, k: [], "ancestors": lambda self, h: ["HP:0001250"] if h == "HP:0002373" else []})())
    monkeypatch.setattr(E, "_llm", lambda system, user, uc, what="": ({"items": list(llm_items)}, {"m": "lit"}))
    monkeypatch.setattr(E.SC, "check_support", lambda *a, **k: {"overall": support})
    monkeypatch.setattr(E, "disease_names", lambda b, s2: [b["diagnosis"]["label"]])
    calls = []

    def search(gene, names):
        calls.append(gene)
        if lit is None:
            raise RuntimeError("HTTP 500 Search is temporarily unavailable")
        return lit
    monkeypatch.setattr(F, "search_literature", search)
    monkeypatch.setattr(F, "load_guidelines", lambda: table or {"categories": {}})
    return calls


LIT = {"query": "q", "url": "u", "queried_at": 5, "count": 1, "papers": [
    {"pmid": "111", "title": "Review", "year": "2024", "pub_types": ["Review"], "pmc": None, "oa": None,
     "abstract": "We recommend early physical therapy. Ketogenic diet reduced seizures.", "full_text": ""}]}
PF = {"age_months": 24, "age_quote": "2 years", "sex": "female", "sex_quote": "girl", "variants": [],
      "present": [{"hpo_id": "HP:0002373", "label": "Febrile seizure", "quote": "seizures"},
                  {"hpo_id": "HP:0001263", "label": "Global developmental delay", "quote": "delay"}], "excluded": []}


def _run_fallback(found):
    led = LG.Ledger("P", [BRS[2]])

    def put(key, section, label, bids, spec, reqs, why, pregnancy=False, source="gr_new"):
        E.place(found, key, section, label, bids, spec, reqs, why, pregnancy, source)
    E.supportive_fallback(led, found, {}, PF, {}, put, True)
    return led


def test_literature_layer_when_no_chapter_or_overview(monkeypatch):
    calls = _stub_common(monkeypatch, lit=LIT, llm_items=[
        {"name": "physical therapy", "kind": "therapy", "quote": "We recommend early physical therapy."},
        {"name": "ketogenic diet", "kind": "diet", "quote": "Ketogenic diet lowered seizures."}])        # not verbatim: dropped
    found = {}
    led = _run_fallback(found)
    assert calls == ["SLC35A2"] and set(found) == {"therapy:physical_therapy"}
    sp = found["therapy:physical_therapy"]["specs"][0]
    assert sp["tier_source"] == "literature" and sp["src"]["type"] == "pmid" and sp["literature"]["pub_types"] == ["Review"]
    assert led.supportive_tiers["b3"]["tier"] == "literature"


def test_unsupported_literature_item_not_used(monkeypatch):
    _stub_common(monkeypatch, lit=LIT, llm_items=[
        {"name": "physical therapy", "kind": "therapy", "quote": "We recommend early physical therapy."}], support="partially_supported")
    found = {}
    _run_fallback(found)
    assert found == {}


def test_literature_not_searched_when_a_chapter_gave_results(monkeypatch):
    calls = _stub_common(monkeypatch, lit=LIT)
    found = {"therapy:physical_therapy": {"key": {"key": "therapy:physical_therapy"}, "section": "supportive_management",
                                          "label": "PT", "branches": {"b3"}, "specs": [{"tier_source": "chapter", "src": {"type": "nbk"}}],
                                          "reqs": [{"field": "manifestation", "text": "seizures"}], "why": "", "pregnancy_only": False,
                                          "source": "gr_new"}}
    led = _run_fallback(found)
    assert calls == [] and led.supportive_tiers["b3"]["results_above"]


def test_search_service_error_recorded_not_assumed(monkeypatch):
    _stub_common(monkeypatch, lit=None)
    found = {}
    led = _run_fallback(found)
    assert "Search is temporarily unavailable" in led.supportive_tiers["b3"]["literature"]["error"]
    assert led.supportive_tiers["b3"]["tier"] == "none" and found == {}


# --- L4

def _table(tmp_path, monkeypatch, passages, sha_ok=True):
    monkeypatch.setattr(F, "ROOT", tmp_path)
    f = tmp_path / ".cache" / "guidelines" / "g1" / "verified.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"url": "https://example.org/g1", "date": "2026-11-05", "passages": [{"text": t} for t in passages]}))
    sha = hashlib.sha256(f.read_bytes()).hexdigest() if sha_ok else "0" * 64
    return {"categories": {"epilepsy": {"hpo": ["HP:0001250"], "guidelines": [{
        "id": "g1", "title": "Guideline One", "url": "https://example.org/g1", "version": "2025",
        "verified": {"file": ".cache/guidelines/g1/verified.json", "sha256": sha, "date": "2026-11-05"},
        "recommendations": [{"name": "individualised antiseizure medication plan",
                             "quote": "Develop an individualised antiseizure medication treatment strategy"}]}]}}}


def test_symptomatic_when_nothing_above(monkeypatch, tmp_path):
    table = _table(tmp_path, monkeypatch, ["Develop an individualised antiseizure medication treatment strategy with the person."])
    _stub_common(monkeypatch, lit={**LIT, "papers": []}, table=table)
    found = {}
    led = _run_fallback(found)
    acts = [a for a in found.values() if a.get("for_symptom")]
    assert len(acts) == 1 and acts[0]["for_symptom"]["label"] == "Febrile seizure"
    assert acts[0]["specs"][0]["tier_source"] == "symptomatic" and acts[0]["specs"][0]["verified_manually"] == "2026-11-05"
    assert led.supportive_tiers["b3"]["tier"] == "symptomatic"
    assert [x["label"] for x in led.supportive_tiers["b3"]["symptoms"]] == ["Febrile seizure", "Global developmental delay"]


def test_gap_fill_only_for_symptoms_not_covered_above(monkeypatch, tmp_path):
    table = _table(tmp_path, monkeypatch, ["Develop an individualised antiseizure medication treatment strategy with the person."])
    _stub_common(monkeypatch, lit=LIT, table=table)
    covered = {"drug:x": {"key": {"key": "drug:x"}, "section": "supportive_management", "label": "levetiracetam",
                          "branches": {"b3"}, "specs": [{"tier_source": "chapter", "src": {"type": "nbk"}}],
                          "reqs": [{"field": "manifestation", "text": "Seizures"}], "why": "", "pregnancy_only": False, "source": "gr_new"}}
    led = _run_fallback(dict(covered))
    assert [x["label"] for x in led.supportive_tiers["b3"]["gap_filled"]] == ["Global developmental delay"]   # seizures covered
    found = {}
    uncovered = dict(covered)
    uncovered["drug:x"] = {**covered["drug:x"], "reqs": [{"field": "manifestation", "text": "kidney stones"}]}
    led = _run_fallback(uncovered)
    assert any(a.get("for_symptom", {}).get("label") == "Febrile seizure" for a in uncovered.values())
    assert {x["label"] for x in led.supportive_tiers["b3"]["gap_filled"]} == {"Febrile seizure", "Global developmental delay"}


def test_guideline_without_a_matching_verified_record_is_not_used(monkeypatch, tmp_path):
    table = _table(tmp_path, monkeypatch, ["Develop an individualised antiseizure medication treatment strategy."], sha_ok=False)
    _stub_common(monkeypatch, lit={**LIT, "papers": []}, table=table)
    found = {}
    led = _run_fallback(found)
    assert found == {} and led.supportive_tiers["b3"]["symptomatic"]["not_verified"] == ["g1"]


# --- checks

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

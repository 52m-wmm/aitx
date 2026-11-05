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


# --- coverage (2026-11-05): HPO up / down, and symptoms the chapter's management sections name

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


def test_agxt_like_symptoms_covered_by_the_chapter_and_seizure_is_not(monkeypatch, tmp_path):
    table = _table(tmp_path, monkeypatch, ["Develop an individualised antiseizure medication treatment strategy with the person."])
    _stub_common(monkeypatch, lit=LIT, table=table)
    names = {"HP:0000121": ["Nephrocalcinosis"], "HP:0012622": ["Chronic kidney disease", "CKD"], "HP:0002373": ["Febrile seizure"]}
    monkeypatch.setattr(E, "ontology", lambda: type("O", (), {
        "exact_lookup": lambda self, t: [], "search": lambda self, t, k: [],
        "ancestors": lambda self, h: ["HP:0001250"] if h == "HP:0002373" else [], "names": lambda self, h: names.get(h, [])})())
    monkeypatch.setattr(E, "mgmt_sections", lambda nbk: [("Management / Treatment of Manifestations / Supportive Care", AGXT_MGMT)])
    pf = dict(PF, present=[{"hpo_id": "HP:0000121", "label": "Nephrocalcinosis", "quote": "nephrocalcinosis"},
                           {"hpo_id": "HP:0012622", "label": "Chronic kidney disease", "quote": "chronic kidney disease"},
                           {"hpo_id": "HP:0002373", "label": "Febrile seizure", "quote": "seizures"}])
    found = {"diet:fluids": {"key": {"key": "diet:fluids"}, "section": "supportive_management", "label": "high oral fluid intake",
                             "branches": {"b1"}, "specs": [{"tier_source": "chapter", "src": {"type": "nbk"}}],
                             "reqs": [{"field": "manifestation", "text": "Prevent crystal injury to kidneys"}], "why": "",
                             "pregnancy_only": False, "source": "gr_new"}}
    led = LG.Ledger("P", [BRS[0]])

    def put(key, section, label, bids, spec, reqs, why, pregnancy=False, source="gr_new"):
        E.place(found, key, section, label, bids, spec, reqs, why, pregnancy, source)
    E.supportive_fallback(led, found, {"b1": {"tier": "chapter", "chapters": ["NBK1283"]}}, pf, {}, put, True)
    rec = led.supportive_tiers["b1"]
    assert {x["label"] for x in rec["covered_by_chapter_text"]} == {"Nephrocalcinosis", "Chronic kidney disease"}
    assert [x["label"] for x in rec["gap_filled"]] == ["Febrile seizure"]               # reverse: not named -> still a gap


def test_hpo_up_and_down_matching(monkeypatch):
    calls = _stub_common(monkeypatch, lit=LIT)
    # action treats "Seizure" (broader) -> covers a present "Febrile seizure"; action treats "Febrile seizure" (narrower)
    # -> covers a present "Seizure"
    anc = {"HP:0002373": ["HP:0001250"]}
    monkeypatch.setattr(E, "ontology", lambda: type("O", (), {
        "exact_lookup": lambda self, t: ["HP:0001250"] if t == "Seizure" else ["HP:0002373"] if t == "Febrile seizure" else [],
        "search": lambda self, t, k: [], "ancestors": lambda self, h: anc.get(h, []), "names": lambda self, h: []})())
    for treats, present in (("Seizure", "HP:0002373"), ("Febrile seizure", "HP:0001250")):
        found = {"drug:x": {"key": {"key": "drug:x"}, "section": "supportive_management", "label": "x", "branches": {"b3"},
                            "specs": [{"tier_source": "chapter", "src": {"type": "nbk"}}],
                            "reqs": [{"field": "manifestation", "text": treats}], "why": "", "pregnancy_only": False, "source": "gr_new"}}
        led = LG.Ledger("P", [BRS[2]])

        def put(*a, **k):
            pass
        E.supportive_fallback(led, found, {}, dict(PF, present=[{"hpo_id": present, "label": "s", "quote": "q"}]), {}, put, True)
        assert led.supportive_tiers["b3"]["gap_filled"] == []


# --- the approved table and the new L4 options (2026-11-05)

def test_config_is_well_formed_and_every_quote_is_in_its_verified_record():
    t = F.load_guidelines()
    cats = t["categories"]
    assert set(cats) == {"epilepsy", "developmental_delay_intellectual_disability", "feeding_difficulties"}
    assert cats["developmental_delay_intellectual_disability"]["enabled"] is False          # AAP 2013 not verified yet
    nice = next(g for g in cats["epilepsy"]["guidelines"] if g["id"] == "nice_ng217")
    assert nice["level"] == 3 and nice["reason_level_3"]
    for c in cats.values():
        for g in c.get("guidelines") or []:
            text = F.verified_text(g)
            if text is None:                       # records live in .cache (not committed): skip where absent
                continue
            for r in g["recommendations"]:
                assert E.LG.quote_in(r["quote"], text), (g["id"], r["name"])
                assert all(E.LG.quote_in(w, r["quote"]) for w in r.get("requires") or [])


def test_disabled_category_and_seizure_type_restriction(monkeypatch, tmp_path):
    table = _table(tmp_path, monkeypatch, ["Ethosuximide should be considered before LTG for absence seizures. Benzodiazepines stop seizures lasting at least 5 minutes."])
    g = table["categories"]["epilepsy"]["guidelines"][0]
    g["recommendations"] = [
        {"name": "ethosuximide before lamotrigine", "quote": "Ethosuximide should be considered before LTG for absence seizures", "hpo": ["HP:0002121"]},
        {"name": "benzodiazepine rescue", "quote": "Benzodiazepines stop seizures lasting at least 5 minutes",
         "requires": ["seizures lasting at least 5 minutes"]}]
    table["categories"]["dd"] = {"hpo": ["HP:0001263"], "enabled": False, "guidelines": []}
    _stub_common(monkeypatch, lit={**LIT, "papers": []}, table=table)
    found = {}
    led = _run_fallback(found)                     # PF: febrile seizure (not an absence seizure) and developmental delay
    labels = {a["label"]: a for a in found.values()}
    assert "ethosuximide before lamotrigine" not in labels                                   # seizure type not stated
    assert labels["benzodiazepine rescue"]["reqs"][0]["field"] == "situation"                # conditional on the situation
    assert led.supportive_tiers["b3"]["symptomatic"]["disabled"] == ["dd"]                   # no stand-in guideline


def test_multi_gene_disease_chapter_is_a_chapter_not_an_overview():
    # 2026-11-05: Classic Ehlers-Danlos Syndrome (3 genes) had been labelled "disease-group advice"
    s2 = {"genereviews": {"COL1A1": [{"nbk": "NBK1244", "scope": "multi_gene"}]}}
    assert F.chapter_tier("NBK1244", s2, TITLES.get) == "chapter"
    assert F.chapter_tier("NBK1138", S2, TITLES.get) == "overview"
    assert F.chapter_tier("NBK9999", s2, lambda n: None) == "chapter"            # no title, no metadata: a chapter
    assert F.chapter_tier("NBK1244", s2, lambda n: None) == "overview"           # no title: the gene count decides

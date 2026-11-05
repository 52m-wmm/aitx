"""Step 3c (off-label / expanded access): offline, network and LLM stubbed."""
import json

import pytest

from aitx.evidence import ledger as LG
from aitx.evidence import offlabel as O


# --- efficacy aggregation (decision 2026-11-05, fixed order)

@pytest.mark.parametrize("dirs,want", [
    (["positive", "negative"], "inconsistent"),
    (["mixed"], "inconsistent"),
    (["negative"], "reported_ineffective"),
    (["negative", "combined_unattributable"], "reported_ineffective"),      # stiripentol in PH1
    (["negative", "not_reported"], "reported_ineffective"),
    (["positive"], "reported_improvement"),
    (["positive", "combined_unattributable", "not_reported"], "reported_improvement"),
    (["combined_unattributable"], "insufficient"),
    (["not_reported", "combined_unattributable"], "insufficient"),
    ([], "insufficient"),
])
def test_aggregate_order(dirs, want):
    assert O.aggregate(dirs) == want


def test_conclusions_never_stronger_than_the_sources():
    assert O.conclusion("reported_ineffective", ["negative", "combined_unattributable"]).startswith(
        "Reported ineffective; not recommended.")
    assert "1 negative, 1 combined unattributable" in O.conclusion("reported_ineffective", ["negative", "combined_unattributable"])
    assert "not proof of efficacy" in O.conclusion("reported_improvement", ["positive"])
    assert "no evidence that it is effective" in O.conclusion("insufficient", ["combined_unattributable"])


# --- design and counts from PubMed fields

@pytest.mark.parametrize("types,quote,want", [
    (["Journal Article", "Randomized Controlled Trial"], "", "controlled"),
    (["Journal Article", "Clinical Trial, Phase II"], "", "open_label"),
    (["Observational Study", "Journal Article"], "", "case_series"),
    (["Case Reports", "Journal Article"], "", "case_report"),
    (["Journal Article"], "", None),                                             # PMID 32103184: not stated
    (["Journal Article"], "a non-randomized, open-label, single-arm trial", "open_label"),
    (["Journal Article"], "a randomized placebo-controlled study", "controlled"),
])
def test_design(types, quote, want):
    assert O.design(types, quote) == want


def test_counts_in_words_or_digits():
    assert O.number_in(10, "Ten patients with SLC35A2-CDG were supplemented")
    assert O.number_in(12, "GRIN2B, GRIN1 and GRIN2A variants (12, 6 and 5 cases, respectively)")
    assert not O.number_in(11, "Ten patients")


# --- precedent checks (code)

TEXT = ("Clinical and biochemical improvement with galactose supplementation in SLC35A2-CDG.\n"
        "Ten patients with SLC35A2-CDG were supplemented with oral D-galactose for 18 weeks in escalating doses up to 1.5 g/kg/day. "
        "Oral galactose is well tolerated and shows promise as dietary therapy. "
        "We administered Stiripentol as compassionate use in an anuric infant with dialysis-dependent PH1.")
GOOD = {"name": "D-galactose", "use_quote": "Ten patients with SLC35A2-CDG were supplemented with oral D-galactose",
        "n_quote": "Ten patients with SLC35A2-CDG", "n_disease": 10, "n_total": 10,
        "outcome_quote": "Oral galactose is well tolerated and shows promise as dietary therapy.", "direction": "positive",
        "dose_quote": "escalating doses up to 1.5 g/kg/day"}
NAMES = ["SLC35A2-congenital disorder of glycosylation", "SLC35A2-CDG"]


def test_valid_precedent_and_reverse_cases():
    assert O.check_item(GOOD, TEXT, NAMES, "SLC35A2") is None
    assert O.check_item({**GOOD, "use_quote": "Oral galactose is well tolerated"}, TEXT, NAMES, "SLC35A2") == \
        "use quote names neither the disease nor the gene"
    assert O.check_item({**GOOD, "use_quote": "Ten patients were given D-galactose"}, TEXT, NAMES, "SLC35A2") == \
        "use quote not verbatim in the article"
    assert O.check_item({**GOOD, "name": "uridine"}, TEXT, NAMES, "SLC35A2") == "use quote does not name the product"
    assert O.check_item({**GOOD, "n_disease": 12}, TEXT, NAMES, "SLC35A2") == "n_disease 12 not in the count quote"


def test_short_abbreviation_matches_case_sensitively():
    it = {"name": "stiripentol", "use_quote": "We administered Stiripentol as compassionate use in an anuric infant with dialysis-dependent PH1"}
    assert O.check_item(it, TEXT, ["primary hyperoxaluria type 1", "PH1"], "AGXT") is None
    assert O.names_in("ph1 in lower case", ["PH1"], None) is None


def test_direction_needs_the_support_check_and_co_treatment_is_not_attributable(monkeypatch):
    monkeypatch.setattr(O.SC, "check_support", lambda *a, **k: {"overall": "supported"})
    assert O.direction(GOOD, "D-galactose", "SLC35A2-CDG", True) == "positive"
    assert O.direction({**GOOD, "co_treatment_quote": "lumasiran"}, "stiripentol", "PH1", True) == "combined_unattributable"
    assert O.direction({**GOOD, "outcome_quote": ""}, "x", "y", True) == "not_reported"
    monkeypatch.setattr(O.SC, "check_support", lambda *a, **k: {"overall": "partially_supported"})
    assert O.direction(GOOD, "D-galactose", "SLC35A2-CDG", True) == "not_reported"          # LLM proposal not upheld


# --- variant function (three tiers)

def _s1(cls, nmd):
    return {"variants": [{"gene": "GRIN2B", "variant_cdna": "c.2755C>T", "variant_protein": "p.Gln919Ter",
                          "variant_class": cls, "nmd": {"prediction": nmd}}]}


@pytest.mark.parametrize("cls,nmd,req,want", [
    ("nonsense", "likely_triggers", "GRIN loss-of-function variants", "satisfies"),       # tier 1, reasoning evidence
    ("nonsense", "likely_escapes", "GRIN loss-of-function variants", "unknown"),          # tier 2: p.Gln919Ter, last exon
    ("missense", "not_applicable", "loss-of-function variants", "unknown"),               # tier 2
    ("nonsense", "likely_triggers", "gain-of-function variants", "unknown"),              # tier 3 awaits review
])
def test_function_tiers(cls, nmd, req, want):
    st, fact, note = O.function_status(req, _s1(cls, nmd), "GRIN2B")
    assert st == want
    if want == "satisfies":
        assert note.startswith("reasoning")


# --- search: retracted, no accessible text, truncation

class R:
    def __init__(self, text):
        self.text = text


XML = ("<PubmedArticleSet>"
       "<PubmedArticle><MedlineCitation><PMID>1</PMID><Article><ArticleTitle>D-serine in GRIN2B</ArticleTitle><Abstract><AbstractText>"
       "A GRIN2B patient received D-serine.</AbstractText></Abstract></Article><CommentsCorrectionsList><CommentsCorrections RefType=\"RetractionIn\">"
       "<RefSource>Biol Psychiatry. 2018</RefSource></CommentsCorrections></CommentsCorrectionsList></MedlineCitation></PubmedArticle>"
       "<PubmedArticle><MedlineCitation><PMID>2</PMID><Article><ArticleTitle>A comment</ArticleTitle></Article></MedlineCitation></PubmedArticle>"
       "<PubmedArticle><MedlineCitation><PMID>3</PMID><Article><ArticleTitle>L-serine in GRIN2B</ArticleTitle><Abstract><AbstractText>"
       "GRIN2B patients were treated with L-serine.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>")


def _http(monkeypatch, count=25):
    def get(url, timeout=30, **k):
        if "esearch" in url:
            return R(json.dumps({"esearchresult": {"count": str(count), "idlist": ["1", "2", "3"]}}))
        if "esummary" in url:
            return R(json.dumps({"result": {"1": {"pubtype": ["Journal Article"], "pubdate": "2018"},
                                            "2": {"pubtype": ["Comment"], "pubdate": "2019"},
                                            "3": {"pubtype": ["Case Reports"], "pubdate": "2019"}}}))
        if "efetch.fcgi?db=pubmed" in url:
            return R(XML)
        raise AssertionError(url)
    monkeypatch.setattr(O.http, "get", get)


def test_search_excludes_retracted_and_textless_and_marks_truncation(monkeypatch):
    _http(monkeypatch)
    rec = O.search("GRIN2B", ["GRIN2B-related neurodevelopmental disorder"])
    p = {x["pmid"]: x for x in rec["papers"]}
    assert p["1"]["excluded"].startswith("retracted (Biol Psychiatry")
    assert p["2"]["excluded"].startswith("no accessible text")
    assert "excluded" not in p["3"] and rec["truncated"] and rec["count"] == 25
    assert "[pt]" not in rec["query"]                                   # no publication-type filter (contract)


# --- end to end with stubs

BR = {"id": "b1", "gene": "GRIN2B", "diagnosis": {"label": "GRIN2B-related neurodevelopmental disorder"}}
PF = {"age_months": 60, "age_quote": "5-year-old", "sex": "female", "sex_quote": "girl", "variants": [], "present": [], "excluded": []}


def _run(monkeypatch, items, *, fda=False, supplement=None, trials=(), earlier=()):
    _http(monkeypatch, count=3)
    monkeypatch.setattr(O, "_llm", lambda user, uc, what: ({"items": items if "PMID 3" in user else []}, {"llm": "m", "served_model": "m", "prompt_version": "3c-v1"}))
    monkeypatch.setattr(O.SC, "check_support", lambda *a, **k: {"overall": "supported"})
    monkeypatch.setattr(O.E, "facts", lambda s1, s2: PF)
    monkeypatch.setattr(O.E, "disease_names", lambda b, s2: ["GRIN2B-related neurodevelopmental disorder"])
    monkeypatch.setattr(O.A, "drug_key", lambda n: {"key": f"drug:{n.lower()}", "normalized": False})
    monkeypatch.setattr(O, "fda_status", lambda d: {"approved": fda})
    monkeypatch.setattr(O, "load_supplements", lambda: {"supplements": [supplement] if supplement else []})
    monkeypatch.setattr(O, "expanded_access", lambda d, n, g: [])
    led = LG.Ledger("P", [BR])
    for a in list(earlier) + list(trials):
        led.actions.append(a)
    O.add_offlabel(led, {}, _s1("nonsense", "likely_escapes"), {}, use_cache=True)
    return led


LSER = {"name": "L-serine", "use_quote": "GRIN2B patients were treated with L-serine", "direction": "positive",
        "outcome_quote": "GRIN2B patients were treated with L-serine", "conditions": [{"text": "GRIN2B patients", "field": "variant_function"}]}


def test_supplement_with_a_precedent_goes_to_3c_conditional(monkeypatch):
    led = _run(monkeypatch, [LSER], supplement={"name": "L-serine", "dsld": ["254751"]})
    a = next(x for x in led.actions if x["section"] == O.SECTION and x.get("action_key"))
    assert a["product_class"] == "dietary_supplement" and a["supplement_note"] == O.SUPPLEMENT_NOTE
    assert a["precedents"][0]["design"] == "case_report" and a["efficacy_direction"] == "reported_improvement"
    assert a["status_by_branch"]["b1"]["status"] == "conditional"        # variant function unknown (escapes NMD)
    assert not [c for c in led.checks() if c["status"] == "fail"], led.checks()
    p = {x["pmid"]: x for x in led.offlabel_searches["b1"]["papers"]}
    assert p["1"]["excluded"].startswith("retracted")                    # D-serine report never used


def test_not_approved_not_supplement_no_expanded_access_is_not_listed(monkeypatch):
    led = _run(monkeypatch, [LSER])
    assert not [x for x in led.actions if x["section"] == O.SECTION and x.get("action_key")]
    none = next(x for x in led.actions if x["section"] == O.SECTION)
    assert none["status_by_branch"]["b1"]["status"] == "searched_none"
    assert led.offlabel_searches["b1"]["drug_decisions"][0]["decision"].startswith("not listed")


def test_already_in_tier_1_is_not_repeated(monkeypatch):
    t1 = {"action_key": "drug:l-serine", "section": "supportive_management", "applies_to": ["b1"], "requirements": [],
          "status_by_branch": {"b1": {"status": "applicable", "reason": ""}}, "evidence_ids": [], "label": "L-serine"}
    led = _run(monkeypatch, [LSER], fda=True, earlier=[t1])
    assert not [x for x in led.actions if x["section"] == O.SECTION and x.get("action_key")]


def _trial():
    return {"action_key": "trial:NCT04646447", "nct": "NCT04646447", "section": "clinical_trial_eligibility", "label": "L-serine trial",
            "applies_to": ["b1"], "interventions": ["L-serine"], "requirements": [], "evidence_ids": [],
            "status_by_branch": {"b1": {"status": "conditional", "reason": ""}}}


def test_trial_only_keeps_precedents_on_the_trial(monkeypatch):
    tr = _trial()
    led = _run(monkeypatch, [LSER], trials=[tr])
    assert not [x for x in led.actions if x["section"] == O.SECTION and x.get("action_key")]
    assert tr["supporting_precedents"][0]["pmid"] == "3"


def test_reachable_outside_the_trial_is_listed_in_both_with_cross_references(monkeypatch):
    tr = _trial()
    led = _run(monkeypatch, [LSER], trials=[tr], supplement={"name": "L-serine"})
    a = next(x for x in led.actions if x["section"] == O.SECTION and x.get("action_key"))
    assert a["see_also"] == [{"section": "clinical_trial_eligibility", "nct": "NCT04646447"}]
    assert tr["see_also"] == [{"section": O.SECTION, "action_key": "drug:l-serine"}]
    assert not O.problems(led.actions)


def test_problems_catch_violations():
    base = {"action_key": "drug:x", "section": O.SECTION, "precedents": [{"pmid": "1", "direction": "negative"}],
            "efficacy_direction": "reported_ineffective", "conclusion": "Reported ineffective; not recommended. (1 negative)",
            "product_class": "approved_off_label"}
    assert O.problems([base]) == []
    assert O.problems([{**base, "efficacy_direction": "inconsistent"}])                     # summary not by the rule
    assert O.problems([{**base, "conclusion": "Stiripentol is effective."}])                # stronger than the sources
    assert O.problems([{**base, "product_class": "dietary_supplement"}])                    # supplement without the note
    assert O.problems([{**base, "precedents": [{"pmid": "1", "direction": "negative", "retracted": True}]}])
    assert O.problems([base, {**base, "section": "existing_targeted_therapies"}])           # duplicate across sections

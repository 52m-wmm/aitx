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
    untitled = "An untitled note.\n" + TEXT.split("\n", 1)[1]
    assert O.check_item({**GOOD, "use_quote": "Oral galactose is well tolerated", "n_quote": ""}, untitled, NAMES, "SLC35A2") == \
        "use quote names neither the disease nor the gene"
    assert O.check_item({**GOOD, "use_quote": "Ten patients were given D-galactose"}, TEXT, NAMES, "SLC35A2") == \
        "use quote not verbatim in the article"
    assert O.check_item({**GOOD, "name": "uridine"}, TEXT, NAMES, "SLC35A2") == "use quote does not name the product"
    assert O.check_item({**GOOD, "n_disease": 12}, TEXT, NAMES, "SLC35A2") is None          # count: not stated, not a rejection
    assert O.checked_counts({**GOOD, "n_disease": 12})["n_disease"] is None


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


def test_direction_claim_does_not_require_several_patients():
    for d in ("positive", "negative", "mixed"):
        c = O.direction_claim(d, "stiripentol", "PH1")
        assert "patient or patients" in c and " in patients with" not in c and "patients with PH1 improved" not in c
    assert O.direction_claim("negative", "stiripentol", "PH1").startswith("stiripentol did not achieve")


def test_outcome_measure_is_kept_only_inside_the_outcome_quote():
    q = "a drastic decrease of plasma oxalate was observed after lanthanum carbonate"
    assert O.outcome_measure({"outcome_quote": q, "outcome_measure": "Plasma oxalate"}) == "Plasma oxalate"
    assert O.outcome_measure({"outcome_quote": q, "outcome_measure": "kidney function"}) is None     # not in the quote
    assert O.outcome_measure({"outcome_quote": q, "outcome_measure": ""}) is None


def test_positive_claim_is_about_the_measure_not_the_patient():
    c = O.direction_claim("positive", "lanthanum carbonate", "PH1", "plasma oxalate")
    assert c == "After receiving lanthanum carbonate, plasma oxalate improved in the patient or patients with PH1 described in this report."
    assert "an outcome measured or observed" in O.direction_claim("positive", "x", "PH1")
    assert O.direction_claim("negative", "x", "PH1", "plasma oxalate") == O.direction_claim("negative", "x", "PH1")  # unchanged


def test_improvement_conclusion_names_what_improved():
    c = O.conclusion("reported_improvement", ["positive", "not_reported"], ["plasma oxalate", "eyes"])
    assert c.startswith("Improvement has been reported in plasma oxalate;") and "eyes" not in c
    assert "an outcome the source does not name" in O.conclusion("reported_improvement", ["positive"], [None])
    assert "patient improved" not in c and "patients improved" not in c


def test_target_quote_must_be_verbatim():
    it = {"name": "stiripentol", "use_quote": "We administered Stiripentol as compassionate use in an anuric infant with "
          "dialysis-dependent PH1", "target_quote": "retinal oxalate deposits"}
    assert O.check_item(it, TEXT, ["PH1"], "AGXT") == "target_quote not verbatim"


def _pf():
    return {"present": [{"hpo_id": "HP:0000505", "label": "Visual impairment", "quote": "poor vision"}], "excluded": []}


@pytest.mark.parametrize("ms,want_status,want_note", [
    (("satisfies", {"field": "manifestation", "value": "Visual impairment", "quote": "poor vision", "step": 2}), "satisfies", ""),
    (("unknown", None), "unknown", O.TARGET_NOTE),                     # not reported -> conditional
    (("does_not_satisfy", {"field": "manifestation", "value": "NOT x", "quote": "no eye findings", "step": 2}),
     "unknown", O.ABSENT_NOTE),                                         # reverse: never a new 'not applicable'
])
def test_target_status_never_not_applicable(monkeypatch, ms, want_status, want_note):
    monkeypatch.setattr(O.E, "manifestation_status", lambda t, pf: ms)
    st, fact, note = O.target_status("ocular findings", _pf())
    assert (st, note) == (want_status, want_note) and fact["field"] == "manifestation"


class _Led:
    def __init__(self):
        self.missing = []
    def add(self, ev):
        return {"id": "e1", **ev}
    def note_missing(self, var, action, detail, by):
        self.missing.append((var, action))
        return var


def _prec(pmid, target):
    return {"pmid": pmid, "url": "u", "target_quote": target, "_text": f"t {target or ''}", "_llm": {}}


def test_target_lines(monkeypatch):
    monkeypatch.setattr(O.LG, "sourced", lambda *a, **k: {"status": "verified"})
    monkeypatch.setattr(O.E, "manifestation_status", lambda t, pf: ("unknown", None))
    led = _Led()
    lines = O.target_lines(led, [_prec("1", "ocular complication")], "bevacizumab", _pf(), "B",
                           src_of=lambda x: {}, key={}, start=0)
    assert len(lines) == 1 and lines[0]["result"] == "unknown" and lines[0]["target_symptom"] and "alternative" not in lines[0]
    assert led.missing and led.missing[0][1] == "bevacizumab"
    # one precedent treated the disease itself -> no target condition
    assert O.target_lines(_Led(), [_prec("1", "ocular complication"), _prec("2", None)], "x", _pf(), "B",
                          src_of=lambda x: {}, key={}, start=0) == []
    # two different targets -> alternatives (any one present is enough)
    two = O.target_lines(_Led(), [_prec("1", "ocular complication"), _prec("2", "skin calcification")], "x", _pf(), "B",
                         src_of=lambda x: {}, key={}, start=3)
    assert [l["alternative"] for l in two] == ["target1", "target2"] and two[0]["id"] == "r4"
    assert all(l["result"] != "fail" for l in two)


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


# --- search: two steps, reviews as clues, retracted, no accessible text (2026-11-05)

class R:
    def __init__(self, text):
        self.text = text


def _art(pmid, title, abstract, types=("Journal Article",), retracted=None, pmc=None):
    rt = (f'<CommentsCorrectionsList><CommentsCorrections RefType="RetractionIn"><RefSource>{retracted}</RefSource>'
          "</CommentsCorrections></CommentsCorrectionsList>") if retracted else ""
    pc = f'<ArticleIdList><ArticleId IdType="pmc">{pmc}</ArticleId></ArticleIdList>' if pmc else ""
    ab = f"<Abstract><AbstractText>{abstract}</AbstractText></Abstract>" if abstract else ""
    pt = "".join(f"<PublicationType>{t}</PublicationType>" for t in types)
    return (f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article><ArticleTitle>{title}</ArticleTitle>{ab}"
            f"<PublicationTypeList>{pt}</PublicationTypeList></Article>{rt}</MedlineCitation><PubmedData>{pc}</PubmedData></PubmedArticle>")


ARTS = {"1": _art("1", "D-serine in GRIN2B", "A GRIN2B patient received D-serine.", retracted="Biol Psychiatry. 2018"),
        "2": _art("2", "A GRIN2B comment", ""),
        "3": _art("3", "L-serine in GRIN2B", "GRIN2B patients were treated with L-serine.", ("Case Reports",)),
        "4": _art("4", "GRIN2B genetics", "GRIN2B variants cause intellectual disability."),           # no drug: screened out
        "5": _art("5", "GRIN2B therapies: a review", "Memantine was used in GRIN2B patients.", ("Review",)),
        "6": _art("6", "Memantine in a GRIN2B child", "A GRIN2B child was treated with memantine.", ("Case Reports",))}


def _http(monkeypatch, count=250, refs=("6",)):
    lex = {"memantine", "l-serine", "d-serine", "stiripentol"}
    monkeypatch.setattr(O, "drug_lexicon", lambda: lex)

    def get(url, timeout=30, **k):
        if "esearch" in url:
            return R(json.dumps({"esearchresult": {"count": str(count), "idlist": ["1", "2", "3", "4", "5"]}}))
        if "elink" in url:
            return R(json.dumps({"linksets": [{"linksetdbs": [{"links": list(refs)}]}]}))
        if "efetch.fcgi?db=pubmed" in url:
            ids = url.split("id=")[1].split(",")
            return R("<PubmedArticleSet>" + "".join(ARTS[i] for i in ids if i in ARTS) + "</PubmedArticleSet>")
        raise AssertionError(url)
    monkeypatch.setattr(O.http, "get", get)


def test_two_step_search_counts_and_exclusions(monkeypatch):
    _http(monkeypatch)
    rec = O.search("GRIN2B", ["GRIN2B-related neurodevelopmental disorder"])
    p = {x["pmid"]: x for x in rec["papers"]}
    st = {k: v for k, v in rec["steps"].items() if k != "context_terms_ignored"}
    assert st == {"found": 250, "found_primary_designs": 250, "screened": 5, "with_drug": 2, "from_review_references": 1,
                  "unreadable": 0, "to_llm_cap": 3}
    assert set(p) == {"1", "3", "6"}                                      # 2 (no abstract, no drug) and 4 (no drug) screened out
    assert p["1"]["excluded"].startswith("retracted (Biol Psychiatry")
    assert p["6"]["via_review"] and "5" not in p                           # the review is background, its cited report is the lead
    assert rec["reviews"] == [{"pmid": "5", "title": "GRIN2B therapies: a review", "role": "background", "references": 1}]
    assert rec["truncated"] and "[pt]" not in rec["query"]


def test_only_a_review_mentions_the_drug_no_precedent(monkeypatch):
    # reverse: the review's cited reports are unavailable -> memantine has no precedent at all
    _http(monkeypatch, refs=("99",))
    rec = O.search("GRIN2B", ["GRIN2B-related neurodevelopmental disorder"])
    assert not any("memantine" in (x.get("drugs_in_abstract") or []) for x in rec["papers"])
    assert rec["reviews"][0]["role"] == "background"


def test_new_drugs_come_before_tier_1_drugs(monkeypatch):
    _http(monkeypatch)
    monkeypatch.setattr(O, "product_ingredients", lambda: {"memantine", "l-serine"})
    monkeypatch.setattr(O, "COMMON_SHARE", 1.0)                              # a 5-article pool: nothing is context
    rec = O.search("GRIN2B", ["GRIN2B-related neurodevelopmental disorder"], exclude_drugs={"l-serine"})
    order = [x["pmid"] for x in rec["papers"]]
    assert order.index("6") < order.index("3")                              # memantine (new) before L-serine (Tier 1)


# --- end to end with stubs

BR = {"id": "b1", "gene": "GRIN2B", "diagnosis": {"label": "GRIN2B-related neurodevelopmental disorder"}}
PF = {"age_months": 60, "age_quote": "5-year-old", "sex": "female", "sex_quote": "girl", "variants": [], "present": [], "excluded": []}


def _run(monkeypatch, items, *, fda=False, supplement=None, trials=(), earlier=()):
    _http(monkeypatch, count=5)
    monkeypatch.setattr(O, "_llm", lambda user, uc, what: ({"items": items if "PMID 3" in user else []}, {"llm": "m", "served_model": "m", "prompt_version": "3c-v1"}))
    monkeypatch.setattr(O.SC, "check_support", lambda *a, **k: {"overall": "supported"})
    monkeypatch.setattr(O.E, "facts", lambda s1, s2: PF)
    monkeypatch.setattr(O.E, "disease_names", lambda b, s2: ["GRIN2B-related neurodevelopmental disorder"])
    monkeypatch.setattr(O.A, "drug_key", lambda n: {"key": f"drug:{n.lower()}", "normalized": False})
    monkeypatch.setattr(O, "fda_status", lambda d: {"approved": fda})
    monkeypatch.setattr(O, "load_supplements", lambda: {"supplements": [supplement] if supplement else []})
    monkeypatch.setattr(O, "expanded_access", lambda d, n, g: [])
    monkeypatch.setattr(O, "gras_table", lambda: {"file": None, "substances": {}})
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
    assert a["access_route"] == "dietary_supplement" and a["supplement_note"] == O.SUPPLEMENT_NOTE
    assert a["precedents"][0]["design"] == "case_report" and a["efficacy_direction"] == "reported_improvement"
    assert a["status_by_branch"]["b1"]["status"] == "conditional"        # variant function unknown (escapes NMD)
    assert not [c for c in led.checks() if c["status"] == "fail"], led.checks()
    p = {x["pmid"]: x for x in led.offlabel_searches["b1"]["papers"]}
    assert p["1"]["excluded"].startswith("retracted")                    # D-serine report never used


def test_precedent_alone_admits_and_an_unknown_route_is_noted(monkeypatch):
    # decision 2026-11-05: admission is the human precedent; the access route only describes availability
    led = _run(monkeypatch, [LSER])
    a = next(x for x in led.actions if x["section"] == O.SECTION and x.get("action_key"))
    assert a["access_route"] == "unconfirmed" and a["access_note"] == O.UNCONFIRMED_NOTE
    assert not O.problems(led.actions)


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
            "access_route": "fda_approved"}
    assert O.problems([base]) == []
    assert O.problems([{**base, "efficacy_direction": "inconsistent"}])                     # summary not by the rule
    assert O.problems([{**base, "conclusion": "Stiripentol is effective."}])                # stronger than the sources
    assert O.problems([{**base, "access_route": "dietary_supplement"}])                     # supplement without the note
    assert O.problems([{**base, "access_route": "unconfirmed"}])                            # unconfirmed without the note
    assert O.problems([{**base, "access_route": "trial_only"}])                             # trial-only belongs in 3b
    assert O.problems([{**base, "precedents": [{"pmid": "1", "direction": "negative", "retracted": True}]}])
    assert O.problems([base, {**base, "section": "existing_targeted_therapies"}])           # duplicate across sections


# --- access route details (2026-11-05)

def test_gras_lookup_exact_substance(tmp_path):
    d = tmp_path / "fda_gras"
    d.mkdir()
    (d / "gras_notices_2026-11-05.xls").write_text(
        "Downloaded from FDA GRAS Notices; Last updated 11/2/2026; downloaded 11/5/2026.\n\n"
        "GRAS Notice (GRN) No.,Substance,Intended Use\n"
        '"=T(""285"")", Galacto-oligosaccharides,food\n'
        '"=T(""817"")", Serine endopeptidase from <I>Malbranchea</I>,enzyme\n', encoding="latin-1")
    t = O.gras_table(d)
    assert O.gras_entry("galacto-oligosaccharides", t)["grn"] == ["285"]
    assert O.gras_entry("L-serine", t) is None                                  # "serine endopeptidase" is not L-serine
    assert O.gras_entry("D-galactose", t) is None
    assert O.gras_table(tmp_path / "missing")["substances"] == {}


def test_unverifiable_count_is_not_stated_and_the_precedent_stays():
    it = {**GOOD, "n_quote": "Ten patients with SLC35A2-CDG", "n_disease": 3}
    assert O.check_item(it, TEXT, NAMES, "SLC35A2") is None
    assert O.checked_counts(it) == {"n_disease": None, "n_total": 10}
    assert O.checked_counts(GOOD) == {"n_disease": 10, "n_total": 10}


def test_source_alias_dedupes_against_tier_1():
    # 2026-11-05: "vitamin B6" (RxNorm 42954) entered 3c although 3a had pyridoxine (684879); the GeneReviews row says
    # "Pyridoxine (vitamin B6 analog)"
    earlier = {"drug:rxcui:684879": {"label": "pyridoxine", "section": "existing_targeted_therapies", "evidence_ids": ["e1"]}}
    ev = {"e1": {"quote": "Small molecule therapy Pyridoxine (vitamin B6 analog) Persons w/missense AGXT variants"}}
    assert O.source_alias("vitamin B6", earlier, ev)["action_key"] == "drug:rxcui:684879"
    # reverse: another name elsewhere in the sentence is not an alias
    ev2 = {"e1": {"quote": "Pyridoxine (vitamin B6 analog) is used; lumasiran is also available"}}
    assert O.source_alias("lumasiran", earlier, ev2) is None
    assert O.source_alias("vitamin B12", earlier, ev) is None


def test_one_precedent_per_article(monkeypatch):
    led = _run(monkeypatch, [LSER, {**LSER, "use_quote": "GRIN2B patients were treated with L-serine"}], supplement={"name": "L-serine"})
    a = next(x for x in led.actions if x["section"] == O.SECTION and x.get("action_key"))
    assert [p["pmid"] for p in a["precedents"]] == ["3"]


def test_gene_may_be_named_in_the_patient_count_quote():
    text = ("A phase 2A trial.\nPatients aged 2-18 years with GRIN loss-of-function pathogenic variants received L-serine for 52 weeks. "
            "Patients had GRIN2B, GRIN1 and GRIN2A variants (12, 6 and 5 cases, respectively).")
    it = {"name": "L-serine", "use_quote": "with GRIN loss-of-function pathogenic variants received L-serine for 52 weeks",
          "n_quote": "Patients had GRIN2B, GRIN1 and GRIN2A variants (12, 6 and 5 cases, respectively)", "n_disease": 12}
    assert O.check_item(it, text, ["GRIN2B-related neurodevelopmental disorder"], "GRIN2B") is None
    assert O.checked_counts(it)["n_disease"] == 12
    # reverse: neither quote names GRIN2B -> not a precedent for this gene
    it2 = {**it, "n_quote": "Patients aged 2-18 years"}
    assert O.check_item(it2, text, ["GRIN2B-related neurodevelopmental disorder"], "GRIN2B") == \
        "use quote names neither the disease nor the gene"


def test_pool_common_terms_are_context_not_new_drugs(monkeypatch):
    # 2026-11-05: glycolate / alanine in PH1 abstracts had pushed stiripentol out of the 20
    _http(monkeypatch)
    monkeypatch.setattr(O, "product_ingredients", lambda: {"memantine", "l-serine"})
    monkeypatch.setattr(O, "COMMON_SHARE", 0.3)
    rec = O.search("GRIN2B", ["GRIN2B-related neurodevelopmental disorder"])
    assert rec["steps"]["context_terms_ignored"] == []


# --- 2026-11-05 run: cancer papers naming the gene; title naming drug and disease; support check sees both quotes

@pytest.mark.parametrize("quote,gene,want", [
    ("patients with GRIN2B-NDD were treated with l-serine", "GRIN2B", "GRIN2B"),
    ("children with AGXT variants received stiripentol", "AGXT", "AGXT"),
    ("previously reported as a possible therapy in ANO10 -related ataxia", "ANO10", "ANO10"),
    ("Patients had GRIN2B, GRIN1 and GRIN2A variants (12, 6 and 5 cases)", "GRIN2B", "GRIN2B"),
    ("A GRIN2B child was treated with memantine.", "GRIN2B", "GRIN2B"),
    ("AGXT expression predicted response to bevacizumab and oxaliplatin", "AGXT", None),          # bare symbol
    ("patients with AGXT mutations in colorectal cancer received cetuximab", "AGXT", None),       # cancer context
])
def test_gene_must_name_the_patients_genetic_condition(quote, gene, want):
    assert O.names_in(quote, ["primary hyperoxaluria type 1"], gene) == want


def test_title_naming_drug_and_disease_accepts_a_bare_use_quote():
    text = ("Evidence for effect of l-serine, a novel therapy for GRIN2B-related neurodevelopmental disorder.\n"
            "the patients were treated experimentally according to an approved protocol with oral l-serine")
    it = {"name": "l-serine", "use_quote": "the patients were treated experimentally according to an approved protocol with oral l-serine"}
    assert O.check_item(it, text, ["GRIN2B-related neurodevelopmental disorder"], "GRIN2B") is None
    other = "A study of sleep in children.\nthe patients were treated experimentally according to an approved protocol with oral l-serine"
    assert O.check_item(it, other, ["GRIN2B-related neurodevelopmental disorder"], "GRIN2B") == \
        "use quote names neither the disease nor the gene"


def test_support_check_sees_use_and_outcome_quotes(monkeypatch):
    seen = []
    monkeypatch.setattr(O.SC, "check_support", lambda t, c, q, use_cache=True: seen.append(q) or {"overall": "supported"})
    O.direction(GOOD, "D-galactose", "SLC35A2-CDG", True)
    assert seen[0] == [GOOD["use_quote"], GOOD["outcome_quote"]]


def test_anaesthesia_or_procedural_use_is_not_a_precedent():
    text = "Anaesthetic management in primary hyperoxaluria type 1.\nIn a child with primary hyperoxaluria type 1, anesthesia was induced and maintained with sevoflurane."
    it = {"name": "sevoflurane", "use_quote": "In a child with primary hyperoxaluria type 1, anesthesia was induced and maintained with sevoflurane"}
    assert O.check_item(it, text, ["primary hyperoxaluria type 1"], "AGXT").startswith("not a treatment")
    ok = {"name": "stiripentol", "use_quote": "In a child with primary hyperoxaluria type 1, stiripentol was given for 4 months"}
    assert O.check_item(ok, "t.\nIn a child with primary hyperoxaluria type 1, stiripentol was given for 4 months.",
                        ["primary hyperoxaluria type 1"], "AGXT") is None


def test_enzyme_names_are_not_drugs():
    lex = {"glycolate", "alanine", "stiripentol"}
    assert O.drugs_named("Glycolate oxidase as a target; alanine:glyoxylate aminotransferase", lex) == []
    assert O.drugs_named("Stiripentol was given; plasma glycolate fell", lex) == ["glycolate", "stiripentol"]


def test_round_robin_covers_many_drugs_before_repeating_one():
    def r(pmid, drugs, title=""):
        return {"pmid": pmid, "title": title, "new_drugs": drugs}
    pool = [r("1", ["a"]), r("2", ["a"]), r("3", ["a"]), r("4", ["b"], "b in the title"), r("5", []), r("6", ["c"])]
    assert [x["pmid"] for x in O.pick(pool, 4)] == ["4", "1", "6", "2"]       # b (title) first, then a, c, then a again
    assert [x["pmid"] for x in O.pick(pool, 10)][-1] == "5"                 # no new drug: last

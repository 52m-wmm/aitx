"""Step 2 offline tests: tiny synthetic ontology/candidates, no network, no LLM."""
import json
from pathlib import Path

import pytest

from aitx.disease import extract as X
from aitx.disease import hpo as H
from aitx.disease import live as L
from aitx.disease import resolve as R
from aitx.disease import sources as S
from aitx.disease.datasets import LocalFile

OBO = "http://purl.obolibrary.org/obo/HP_"


def node(i, lbl, syn=(), alt=(), deprecated=False, repl=None):
    meta = {"synonyms": [{"pred": "hasExactSynonym", "val": s} for s in syn],
            "basicPropertyValues": [{"pred": "http://www.geneontology.org/formats/oboInOwl#hasAlternativeId",
                                     "val": f"HP:{a}"} for a in alt]}
    if deprecated:
        meta["deprecated"] = True
    if repl:
        meta["basicPropertyValues"].append({"pred": "http://purl.obolibrary.org/obo/IAO_0100001", "val": f"HP:{repl}"})
    return {"id": OBO + i, "lbl": lbl, "type": "CLASS", "meta": meta}


@pytest.fixture(scope="module")
def ont(tmp_path_factory):
    # 0000118 Phenotypic abnormality
    #   ├─ 0001250 Seizure ── 0007359 Focal-onset seizure
    #   ├─ 0001263 Global developmental delay
    #   ├─ 0001987 Hyperammonemia
    #   └─ 0000478 Abnormality of the eye
    # 0000005 Mode of inheritance (not a phenotype)
    nodes = [node("0000001", "All"), node("0000118", "Phenotypic abnormality"),
             node("0001250", "Seizure", syn=["Seizures", "Epileptic seizure"], alt=["0001275"]),
             node("0007359", "Focal-onset seizure", syn=["Focal seizures"]),
             node("0001263", "Global developmental delay", syn=["Developmental delay"]),
             node("0001987", "Hyperammonemia"), node("0000478", "Abnormality of the eye", syn=["Eye abnormality"]),
             node("0012873", "Absent vas deferens", syn=["Congenital absence of the vas deferens"]),
             node("0000365", "Hearing impairment", syn=["Hearing loss", "Deafness"]),
             node("0000005", "Mode of inheritance"),
             node("0000057", "obsolete Clitoromegaly", deprecated=True),
             node("0003674", "Onset"), node("0410280", "Pediatric onset"), node("0003593", "Infantile onset"),
             node("0011463", "Childhood onset"), node("0003581", "Adult onset"), node("0003596", "Middle age onset"),
             node("0099999", "Some new onset subterm"),
             node("0009999", "obsolete Old seizure term", deprecated=True, repl="0001250")]
    edges = [("0012873", "0000118"), ("0000365", "0000118"), ("0000118", "0000001"), ("0001250", "0000118"), ("0007359", "0001250"), ("0001263", "0000118"),
             ("0001987", "0000118"), ("0000478", "0000118"), ("0000005", "0000001"),
             ("0003674", "0000001"), ("0410280", "0003674"), ("0003593", "0410280"), ("0011463", "0410280"),
             ("0003581", "0003674"), ("0003596", "0003581"), ("0099999", "0003596")]
    g = {"graphs": [{"nodes": nodes, "edges": [{"sub": OBO + a, "pred": "is_a", "obj": OBO + b} for a, b in edges],
                     "meta": {"version": "test"}}]}
    p = tmp_path_factory.mktemp("hpo") / "hp.json"
    p.write_text(json.dumps(g))
    o = H.Ontology(LocalFile("hpo_ontology", p, "", "2026-10-28", 0, 0, "", len(nodes)))
    ann = S.HpoAnnotations({
        "OMIM:1": [S.Annotation("HP:0007359", 0.9, False, 1), S.Annotation("HP:0001263", None, False, 2)],
        "OMIM:2": [S.Annotation("HP:0001987", 1.0, False, 3)],
        "OMIM:3": [S.Annotation("HP:0001263", None, False, 4)],
        "OMIM:4": [S.Annotation("HP:0001263", None, False, 5), S.Annotation("HP:0001250", 0.9, False, 6)],
    }, {}, {}, "2026-10-28")
    o.build_ic(ann)
    o.test_ann = ann
    o.test_path = p
    return o


# ------------------------------------------------------------------ ontology

def test_resolve_alt_obsolete_and_unknown(ont):
    assert ont.resolve("HP:0001275")[0] == "HP:0001250"
    assert ont.resolve("HP:0000057")[0] is None
    assert ont.resolve("HP:0009999")[0] == "HP:0001250"
    assert ont.resolve("HP:1234567")[0] is None
    assert ont.is_phenotype("HP:0007359") and not ont.is_phenotype("HP:0000005")


def test_ic_rare_terms_weigh_more(ont):
    assert ont.term_ic("HP:0001987") > ont.term_ic("HP:0001263") > 0
    assert ont.term_ic("HP:0000118") == 0


def test_score_ancestor_match_and_null_without_annotations(ont):
    ann = ont.test_ann.phenotypes
    # patient "Seizure" matches disease "Focal-onset seizure" through the ancestor
    s = H.score(ont, ["HP:0001250"], [], ann["OMIM:1"])
    assert s["score"] > 0 and s["matches"][0]["common_ancestor"] == "HP:0001250"
    assert H.score(ont, ["HP:0001250"], [], [])["score"] is None


def test_score_penalises_explicitly_absent_frequent_feature(ont):
    ann = ont.test_ann.phenotypes
    with_seizure = H.score(ont, ["HP:0001263"], ["HP:0001250"], ann["OMIM:4"])
    without = H.score(ont, ["HP:0001263"], ["HP:0001250"], ann["OMIM:3"])
    assert with_seizure["penalties"] and not without["penalties"]
    assert with_seizure["score"] < without["score"]


def test_former_names_from_older_release(ont, tmp_path):
    o = H.Ontology(LocalFile("hpo_ontology", ont.test_path, "", "x", 0, 0, "", 0))
    # the obsolete "Old seizure term" was replaced by Seizure: its name points there already
    assert o.exact_lookup("Old seizure term") == ["HP:0001250"]
    legacy = {"graphs": [{"nodes": [node("0001263", "Developmental retardation", syn=["Global developmental delay"]),
                                     node("0001275", "Seizure disorder")], "edges": []}]}
    lp = tmp_path / "old.json"
    lp.write_text(json.dumps(legacy))
    added = o.add_former_names(LocalFile("hpo_ontology_2022", lp, "", "x", 0, 0, "", 0))
    assert added == 2                                         # current names are not duplicated
    assert o.exact_lookup("developmental retardation") == ["HP:0001263"]
    assert o.exact_lookup("Seizure disorder") == ["HP:0001250"]   # alt id followed to the current term


def test_exact_lookup_accepts_plural(ont):
    assert ont.exact_lookup("Seizures") == ["HP:0001250"]
    assert ont.exact_lookup("global developmental delays") == ["HP:0001263"]
    assert ont.exact_lookup("Mode of inheritance") == []          # not a phenotype term


def test_search_returns_phenotype_terms_only(ont):
    hits = [h["hpo_id"] for h in ont.search("focal seizures in infancy", 5)]
    assert hits[0] == "HP:0007359" and "HP:0001250" in hits
    assert all(ont.is_phenotype(h) for h in hits)


# ---------------------------------------------------------------- extraction

CTX = "18-month-old female with hypotonia, developmental delay, EEG abnormalities (without overt seizures) and a de novo variant."


def item(quote, desc="", status="present", **kw):
    return {"quote": quote, "description": desc, "status": status, **kw}


def test_quote_must_be_verbatim():
    r = X.check_item(item("developmental delays"), CTX)
    assert not r.get("checked") and "verbatim" in r["reasons"][0]


def test_negation():
    assert X.check_item(item("without overt seizures", "Seizure", "excluded"), CTX).get("checked")
    assert not X.check_item(item("developmental delay", "Global developmental delay", "excluded"), CTX).get("checked")
    # a negated 'present' quote is no longer rejected here: the decision waits for the mapped term
    r = X.check_item(item("without overt seizures", "Seizure", "present"), CTX)
    assert r.get("checked") and r["negated_quote"] == "without"


@pytest.mark.parametrize("quote", ["never broken a bone", "hearing is normal", "MRI unremarkable", "sepsis ruled out"])
def test_new_negation_cues_allow_excluded(quote):
    assert X.check_item(item(quote, "x", "excluded"), f"Notes: {quote}.").get("checked")


@pytest.mark.parametrize("quote", ["joints bend much further than normal", "head size above normal",
                                   "tone below normal"])
def test_comparison_with_normal_is_not_a_negation(quote):
    r = X.check_item(item(quote, "x", "present"), f"Exam: {quote}.")
    assert r.get("checked") and "negated_quote" not in r
    assert not X.check_item(item(quote, "x", "excluded"), f"Exam: {quote}.").get("checked")


def test_absence_term_keeps_negated_present_quote(ont, monkeypatch):
    monkeypatch.setattr(X, "_cached_chat", lambda *a, **k: pytest.fail("no LLM call expected"))
    ctx = "He was born without the vas deferens on both sides. There were no seizures."
    its = [X.check_item(item("born without the vas deferens", "Absent vas deferens"), ctx),
           X.check_item(item("no seizures", "Seizure", "excluded"), ctx)]
    out = X.map_items(its, ctx, ont, 0, True)
    assert (out[0]["valid"], out[0]["status"], out[0]["hpo_id"]) == (True, "present", "HP:0012873")
    assert "denotes an absence" in out[0]["negation_note"]
    # the other direction: an explicit negation stays excluded, the new rule does not turn it into 'present'
    assert (out[1]["valid"], out[1]["status"], out[1]["hpo_id"]) == (True, "excluded", "HP:0001250")


def test_negated_feature_marked_present_is_still_rejected(ont, monkeypatch):
    monkeypatch.setattr(X, "_cached_chat", lambda *a, **k: pytest.fail("no LLM call expected"))
    ctx = "There were no seizures and hearing is normal."
    out = X.map_items([X.check_item(item("no seizures", "Seizure", "present"), ctx),
                       X.check_item(item("hearing is normal", "Hearing impairment", "present"), ctx)], ctx, ont, 0, True)
    assert [o["valid"] for o in out] == [False, False]          # Seizure / Hearing impairment are not absences
    assert all("not an absence" in o["reasons"][-1] for o in out)


def test_presenting_needs_a_cue():
    ctx = "Presented at 8 months of age with hypotonia. Later developed seizures."
    assert X.check_item(item("hypotonia", presenting=True), ctx)["presenting"] is True
    r = X.check_item(item("seizures", presenting=True), ctx)
    assert r["presenting"] is False and "no 'presented with'" in r["reasons"][0]


def test_code_assigns_ids_by_exact_name(ont, monkeypatch):
    monkeypatch.setattr(X, "_cached_chat", lambda *a, **k: pytest.fail("no LLM call expected"))
    ctx = "Child with focal seizures, hypotonia, developmental delay and eye trouble."
    its = [X.check_item(item("focal seizures", "Seizure"), ctx),                 # verbatim quote is tried first
           X.check_item(item("developmental delay", "Global developmental delay"), ctx),
           X.check_item(item("eye trouble", "Ocular problem", alternatives=["Eye abnormality"]), ctx)]
    out = X.map_items(its, ctx, ont, 0, True)
    assert [o["hpo_id"] for o in out] == ["HP:0007359", "HP:0001263", "HP:0000478"]
    assert out[0]["mapping"].endswith("quote") and out[2]["mapping"].endswith("alternative name")


def test_alternatives_widen_retrieval(ont):
    plain = X.candidates_for({"quote": "odd look", "description": "Ocular oddity", "alternatives": []}, ont)[1]
    wide = X.candidates_for({"quote": "odd look", "description": "Ocular oddity",
                             "alternatives": ["Abnormality of the eye region"]}, ont)[1]
    assert "HP:0000478" not in [c["hpo_id"] for c in plain]
    assert "HP:0000478" in [c["hpo_id"] for c in wide]


def test_llm_only_picks_from_code_listed_candidates(ont, monkeypatch):
    seen = {}

    def fake_chat(messages, k, use_cache):
        seen["prompt"] = messages[1]["content"]
        return {"content": json.dumps({"choices": [{"feature": 1, "candidate": 1}, {"feature": 2, "candidate": 99}]}),
                "served_model": "fake"}
    monkeypatch.setattr(X, "_cached_chat", fake_chat)
    ctx = "Child with focal seizures in infancy and eye findings."
    its = [X.check_item(item("focal seizures in infancy", "Focal seizures in infancy"), ctx),
           X.check_item(item("eye findings", "Ocular finding"), ctx)]
    out = X.map_items(its, ctx, ont, 0, True)
    assert out[0]["valid"] and out[0]["hpo_id"] == out[0]["candidates"][0]["hpo_id"]
    assert out[0]["mapping"] == "LLM pick from retrieved candidates"
    assert not out[1]["valid"]                         # candidate 99 is not on the list -> rejected
    assert "HP:" not in seen["prompt"]                  # ids are never shown to (or taken from) the LLM


def test_llm_can_answer_none(ont, monkeypatch):
    monkeypatch.setattr(X, "_cached_chat", lambda *a, **k: {
        "content": json.dumps({"choices": [{"feature": 1, "candidate": None}]}), "served_model": "fake"})
    ctx = "Child with focal seizures in infancy."
    out = X.map_items([X.check_item(item("focal seizures in infancy", "Focal seizures in infancy"), ctx)], ctx, ont, 0, True)
    assert not out[0]["valid"] and "none of the candidates" in out[0]["reasons"][-1]


def V(tid, status="present"):
    return {"hpo_id": tid, "status": status, "valid": True, "quote": tid}


def test_vote_merges_along_hierarchy(ont):
    # Seizure / Focal-onset seizure / Seizure: the majority level is Seizure
    kept, unstable = X.vote_terms([[V("HP:0001250")], [V("HP:0007359")], [V("HP:0001250")]], ont, 3)
    assert [k["hpo_id"] for k in kept] == ["HP:0001250"] and kept[0]["merged_from"] == ["HP:0007359"]
    assert unstable == []


def test_vote_keeps_specific_level_when_majority_agrees(ont):
    kept, _ = X.vote_terms([[V("HP:0007359")], [V("HP:0007359")], [V("HP:0001250")]], ont, 3)
    assert [k["hpo_id"] for k in kept] == ["HP:0007359"]


def test_vote_drops_minority_and_separates_status(ont):
    kept, unstable = X.vote_terms([[V("HP:0001987"), V("HP:0001250", "excluded")],
                                   [V("HP:0001250", "excluded")], [V("HP:0001263")]], ont, 3)
    assert [(k["hpo_id"], k["status"]) for k in kept] == [("HP:0001250", "excluded")]
    assert {u["hpo_id"] for u in unstable} == {"HP:0001987", "HP:0001263"}


def test_presenting_symptom_onset_becomes_overall_onset():
    ctx = "A 3-year-old who presented with seizure onset in the first months of life and developmental delay."
    seiz = X.check_item(item("seizure onset", "Seizure", presenting=True, onset={"quote": "first months of life"}), ctx)
    seiz.update(valid=True, hpo_id="HP:0001250")
    po = X.presenting_onset([seiz])
    assert (po["months_min"], po["months_max"], po["source"]) == (1, 12, "presenting symptom")   # Infantile onset
    # a dated symptom that is not the presenting one does not set the overall onset
    seiz["presenting"] = False
    assert X.presenting_onset([seiz]) is None


@pytest.mark.parametrize("v,u,m", [(3, "year", 36), (18, "month", 18), (3, "months", 3), (2, "week", 0.5),
                                   (14, "years", 168), (None, "year", None), (3, "fortnight", None)])
def test_age_conversion(v, u, m):
    assert X.to_months(v, u) == m


def test_facts_verified():
    f = X.verify_facts({"age": {"value": 18, "unit": "month", "quote": "18-month-old"},
                        "sex": {"value": "female", "quote": "female"},
                        "variant_origin": {"value": "de_novo", "quote": "de novo"},
                        "onset": {"quote": "at 8 months"},
                        "family_history": {"statement": None, "quote": None}}, CTX)
    assert f["age"]["months"] == 18 and f["sex"]["value"] == "female" and f["variant_origin"]["value"] == "de_novo"
    assert f["onset"]["months_min"] is None   # quote not in text -> unknown
    assert f["family_history"]["statement"] == "unknown"


CTX2 = ("The individual is a 14 year old male with slowly progressive loss of sensation in their lower extremities. "
        "They initially had good growth but around 10 years of age began losing weight.")


def test_symptom_specific_timing_stays_on_the_symptom():
    # the LLM is told to attach this timing to the symptom, not to facts.onset
    f = X.verify_facts({"onset": None}, CTX2)
    assert f["onset"]["months_min"] is None                       # no overall onset
    from aitx.disease.pipeline import patient_onset
    assert patient_onset(f) == {}                                   # nothing to compare -> onset neutral
    # symptom timing is verified and converted like any other age
    o = X.verify_onset({"quote": "around 10 years of age"}, CTX2)
    assert o["stated_months"] == [120, 120] and o["approximate"]
    assert [t["id"] for t in o["hpo_onset"]] == ["HP:0003621"] and (o["months_min"], o["months_max"]) == (60, 192)


def test_phenotype_onset_quote_must_be_verbatim():
    p = X.check_item(item("developmental delay", onset={"quote": "at 9 months"}), CTX)
    assert p["checked"] and p["onset"]["months_min"] is None and not p["onset"]["verified"]


@pytest.mark.parametrize("quote,terms,interval,stated", [
    ("at 8 months", ["HP:0003593"], (1, 12), [8, 8]),                    # Infantile onset
    ("around age 6", ["HP:0003621"], (60, 192), [72, 72]),               # Juvenile onset, 5-15 y
    ("at age 12 months", ["HP:0011463"], (12, 60), [12, 12]),            # [low, high): 1 y is childhood
    ("between 2 and 4 years", ["HP:0011463"], (12, 60), [24, 48]),
    ("first 6 months of life", ["HP:0003623", "HP:0003593"], (0, 12), [0, 6]),   # a range takes every term it touches
    ("on day 3", ["HP:0003623"], (0, 1), [0.1, 0.1]),
    ("since birth", ["HP:0003577"], (0, 1), None),                       # named period
    ("in early childhood", ["HP:0011463"], (12, 60), None),
    ("in adulthood", ["HP:0003581"], (192, None), None),
])
def test_onset_quote_mapped_to_hpo_interval(quote, terms, interval, stated):
    o = X.map_onset(quote)
    assert [t["id"] for t in o["hpo_onset"]] == terms
    assert (o["months_min"], o["months_max"]) == interval and o["stated_months"] == stated


def test_unmappable_onset_is_unknown():
    o = X.map_onset("presented")
    assert o["hpo_onset"] == [] and o["months_min"] is None and "could not be mapped" in o["reasons"][0]


def test_onset_tables_agree_with_hpo_intervals():
    for tid, _, lo, hi in H.ONSET_LEAVES:
        assert H.ONSET_MONTHS[tid] == (lo, hi)
    assert all(tid in H.ONSET_MONTHS for _, tid, _ in H.ONSET_WORDS)


CFG = {"model": "deepseek-flash", "base_url": "https://api.deepseek.com", "expect_model_prefix": ""}
MSG = [{"role": "system", "content": "prompt A"}, {"role": "user", "content": "text"}]


def test_cache_key_changes_with_model_prompt_version_params(monkeypatch):
    base = X.cache_key(MSG, 0, CFG)
    assert X.cache_key(MSG, 0, CFG) == base                                            # deterministic
    assert X.cache_key(MSG, 0, dict(CFG, model="deepseek/deepseek-v4-flash-0423")) != base
    assert X.cache_key(MSG, 0, dict(CFG, base_url="https://openrouter.ai/api/v1")) != base
    assert X.cache_key([dict(MSG[0], content="prompt B"), MSG[1]], 0, CFG) != base     # prompt text edited
    assert X.cache_key(MSG, 1, CFG) != base                                            # another sample
    monkeypatch.setattr(X, "PROMPT_VERSION", "step2-extract-v999")
    assert X.cache_key(MSG, 0, CFG) != base


def test_cache_entry_with_other_call_params_not_reused():
    entry = {"served_model": "deepseek-flash", "call_params": dict(X.CALL_PARAMS)}
    assert X._cache_usable(entry, CFG)
    assert not X._cache_usable(dict(entry, call_params=dict(X.CALL_PARAMS, temperature=0.7)), CFG)
    assert not X._cache_usable({"served_model": "deepseek-flash"}, CFG)        # parameters unknown


def test_cache_entry_from_other_served_model_not_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(X, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(X.llm, "config", lambda: dict(CFG, expect_model_prefix="deepseek-v4.1"))
    (tmp_path / f"{X.cache_key(MSG, 0, dict(CFG, expect_model_prefix='deepseek-v4.1'))}.json").write_text(
        json.dumps({"served_model": "deepseek-v4-flash-0423", "content": "{}", "call_params": X.CALL_PARAMS}))
    calls = []
    monkeypatch.setattr(X.llm, "chat", lambda m, **kw: calls.append(1) or {
        "model": "deepseek-v4.1-flash-1017", "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]})
    out = X._cached_chat(MSG, 0, True)
    assert calls and out["served_model"] == "deepseek-v4.1-flash-1017"
    assert X._cached_chat(MSG, 0, True)["served_model"] == "deepseek-v4.1-flash-1017" and len(calls) == 1


def test_prompt_never_asks_for_ids():
    assert "Do not give any ontology identifiers" in X.SYSTEM and "hpo_id" not in X.SYSTEM
    assert "filled ONLY when the text explicitly" in X.SYSTEM
    assert "Give the quote only; do not convert it to numbers." in X.SYSTEM     # onset numbers come from code


def test_facts_age_number_must_match_quote():
    f = X.verify_facts({"age": {"value": 1, "unit": "year", "quote": "18-month-old"}}, CTX)
    assert f["age"]["months"] is None


def test_sex_contradiction_becomes_unknown():
    f = X.verify_facts({"sex": {"value": "male", "quote": "male"}}, "A female; he was seen")
    assert f["sex"]["value"] == "unknown"


# ------------------------------------------------------------------- ClinVar

def test_normalize_cdna():
    assert L.normalize_cdna("c.8079delC") == "c.8079del"
    assert L.normalize_cdna("c.1521_1523delCTT") == "c.1521_1523del"
    assert L.normalize_cdna("c.33dupA") == "c.33dup"
    assert L.normalize_cdna("c.100G>A") == "c.100G>A"


def _summary(uid, name, sig="Likely pathogenic", rs="criteria provided, single submitter", traits=(), extra_vs=0):
    vs = [{"variation_name": name}] + [{"variation_name": "NM_X.1(G):c.1A>G"}] * extra_vs
    return {"uid": uid, "accession": f"VCV{int(uid):09d}", "title": name, "variation_set": vs,
            "germline_classification": {"description": sig, "review_status": rs, "last_evaluated": "2019/04/01 00:00",
                                        "trait_set": [{"trait_name": n, "trait_xrefs": x} for n, x in traits]}}


def test_clinvar_exact_match_rejects_neighbour_and_haplotype(monkeypatch):
    recs = [_summary("2662739", "NM_001378452.1(ITPR1):c.101A>G (p.Asp34Gly)", "Uncertain significance"),
            _summary("809404", "NM_001378452.1(ITPR1):c.100G>A (p.Asp34Asn)",
                     traits=[("not provided", [{"db_source": "MedGen", "db_id": "C3661900"}])]),
            _summary("5", "NM_001378452.1(ITPR1):c.[100G>A;300C>T]", extra_vs=1)]

    def fake_get(url, **kw):
        if "esearch" in url:
            body = {"esearchresult": {"idlist": [r["uid"] for r in recs]}}
        else:
            body = {"result": {"uids": [r["uid"] for r in recs], **{r["uid"]: r for r in recs}}}
        return L.http.Fetched(url, json.dumps(body), 1, True)
    monkeypatch.setattr(L.http, "get", fake_get)
    r = L.clinvar_lookup("NM_001378452.1", "c.100G>A")
    assert r.status == "found" and [x.vcv for x in r.records] == ["VCV000809404"]
    assert r.records[0].stars == 1 and r.records[0].traits[0]["generic"]
    assert len(r.rejected) == 2


def test_clinvar_star_table():
    assert L.STARS["practice guideline"] == 4 and L.STARS["reviewed by expert panel"] == 3
    assert L.STARS["criteria provided, multiple submitters, no conflicts"] == 2
    assert L.STARS.get("no assertion criteria provided", 0) == 0


# --------------------------------------------------------------- inheritance

@pytest.mark.parametrize("moi,zyg,n,sex,want", [
    ("AR", "homozygous", 1, "male", "consistent"),
    ("AR", "heterozygous", 1, "male", "conditional"),
    ("AR", "heterozygous", 2, "male", "conditional"),
    ("AD", "heterozygous", 1, "female", "consistent"),
    ("AD", "homozygous", 1, "male", "conditional"),
    ("SD", "homozygous", 1, "male", "consistent"),
    ("XLR", "hemizygous", 1, "male", "consistent"),
    ("XL", "hemizygous", 1, "female", "inconsistent"),
    ("XLD", "heterozygous", 1, "female", "consistent"),
    ("XLR", "heterozygous", 1, "female", "conditional"),
    ("MT", "homozygous", 1, "male", "unknown"),
])
def test_moi_fit(moi, zyg, n, sex, want):
    assert R.moi_fit(moi, zyg, n, sex)[0] == want


# --------------------------------------------------------------------- onset

def test_onset_range_uses_nearest_listed_ancestor(ont):
    assert H.onset_range(ont, "HP:0003593") == (1, 12)
    assert H.onset_range(ont, "HP:0099999") == (480, 720)   # unlisted subterm -> Middle age onset
    assert H.onset_range(ont, "HP:0001250") is None          # not an onset term


def test_onset_is_penalty_only(ont):
    infant = {"min": 0, "max": 6, "kind": "onset"}
    m = H.onset_fit(ont, infant, [("HP:0003593", 1)])
    assert m["result"] == "match" and m["adjustment"] == 0      # a match earns nothing
    # so a disease with a matching onset annotation scores the same as one without any
    assert m["adjustment"] == H.onset_fit(ont, infant, [])["adjustment"]
    mm = H.onset_fit(ont, infant, [("HP:0003596", 2)])
    assert mm["result"] == "mismatch" and mm["adjustment"] == -H.ONSET_PENALTY
    # any one overlapping annotation is enough
    assert H.onset_fit(ont, infant, [("HP:0003596", 2), ("HP:0003593", 3)])["result"] == "match"


def test_onset_unknown_is_neutral(ont):
    assert H.onset_fit(ont, {}, [("HP:0003593", 1)])["adjustment"] == 0
    assert H.onset_fit(ont, {"min": 0, "max": 6, "kind": "onset"}, [])["adjustment"] == 0
    # course terms in aspect C (e.g. "Progressive") are not onset terms
    assert H.onset_fit(ont, {"min": 0, "max": 6, "kind": "onset"}, [("HP:0001250", 1)])["result"] == "unknown"


def test_onset_tolerance_at_category_edges(ont):
    # 13 months is just past "infantile" (< 12 months): within tolerance, still a match
    assert H.onset_fit(ont, {"min": 13, "max": 13, "kind": "onset"}, [("HP:0003593", 1)])["result"] == "match"


def test_age_upper_bound_only_penalises_clear_mismatch(ont):
    child = {"min": None, "max": 84, "kind": "age_upper_bound"}      # 7-year-old, onset not stated
    assert H.onset_fit(ont, child, [("HP:0003593", 1)])["adjustment"] == 0          # compatible, no bonus
    r = H.onset_fit(ont, child, [("HP:0003596", 1)])                                  # middle-age onset
    assert r["result"] == "mismatch" and r["adjustment"] == -H.ONSET_PENALTY


def test_patient_onset_from_facts():
    from aitx.disease.pipeline import patient_onset
    assert patient_onset({"onset": {"months_min": 0, "months_max": 6}, "age": {"months": 36}})["kind"] == "onset"
    assert patient_onset({"onset": {}, "age": {"months": 36}}) == {"min": None, "max": 36, "kind": "age_upper_bound",
                                                                    "quote": None}
    assert patient_onset({"onset": {}, "age": {}}) == {}


def test_onset_is_not_a_veto():
    # a candidate with an onset mismatch still wins when its phenotype lead is large enough
    s = R.select([cand("A", 5.0 - H.ONSET_PENALTY), cand("B", 1.0)], ["HP:1"], [], [])
    assert (s["status"], s["id"]) == ("resolved", "A")


# ----------------------------------------------------------------- selection

def cand(key, score, moi="consistent", clinvar=(), specific=True, label=None):
    return {"key": key, "label": label or key, "excluded": False, "specific": specific,
            "phenotype": {"score": score}, "inheritance": {"result": moi},
            "clinvar": [{"vcv": "VCV1", "stars": s, "clinical_significance": "Pathogenic"} for s in clinvar],
            "validity": {"summary": "Definitive"}}


def test_explicit_beats_clinvar_and_phenotype():
    s = R.select([cand("A", 5.0, clinvar=[3]), cand("B", 1.0)], ["HP:1"], [], ["B"])
    assert (s["status"], s["id"], s["basis"]) == ("resolved", "B", "explicit")


def test_clinvar_more_stars_wins():
    s = R.select([cand("A", 5.0, clinvar=[1]), cand("B", 1.0, clinvar=[2])], ["HP:1"], [], [])
    assert (s["status"], s["id"], s["basis"]) == ("resolved", "B", "clinvar")


def test_clinvar_tie_broken_by_phenotype_or_ambiguous():
    s = R.select([cand("A", 5.0, clinvar=[2]), cand("B", 1.0, clinvar=[2])], ["HP:1"], [], [])
    assert (s["status"], s["id"]) == ("resolved", "A")
    s = R.select([cand("A", 5.0, clinvar=[2]), cand("B", 4.5, clinvar=[2])], ["HP:1"], [], [])
    assert s["status"] == "ambiguous" and set(s["tied"]) == {"A", "B"}


def test_grouping_term_does_not_block():
    s = R.select([cand("A", 3.0, clinvar=[2]), cand("G", None, clinvar=[2], specific=False)], ["HP:1"], [], [])
    assert (s["status"], s["id"]) == ("resolved", "A")


def test_inheritance_tier_before_phenotype():
    s = R.select([cand("AD", 9.0, moi="conditional"), cand("AR", 1.0)], ["HP:1"], [], [])
    assert (s["status"], s["id"], s["basis"]) == ("resolved", "AR", "inheritance")


def test_phenotype_gap_threshold():
    assert R.select([cand("A", 5.0), cand("B", 3.0)], ["HP:1"], [], [])["status"] == "resolved"
    assert R.select([cand("A", 5.0), cand("B", 4.2)], ["HP:1"], [], [])["status"] == "ambiguous"


def test_unscored_specific_candidate_makes_ambiguous():
    s = R.select([cand("A", 5.0), cand("B", None)], ["HP:1"], [], [])
    assert s["status"] == "ambiguous" and "B" in s["tied"]


def test_excluded_never_selected():
    c = cand("A", 9.0)
    c["excluded"] = True
    s = R.select([c, cand("B", 1.0)], ["HP:1"], [], [])
    assert s["id"] == "B" and s["basis"] == "only_candidate"


def test_confidence_rules():
    sel = {"basis": "phenotype", "lead": 0.5}
    assert R.confidence(sel, cand("A", 5.0), 5.0)[0] == "high"
    c = cand("A", 5.0, moi="conditional")
    assert R.confidence(sel, c, 5.0)[0] == "low"
    c = cand("A", None)
    assert R.confidence({"basis": "only_candidate"}, c, None)[0] == "moderate"
    c = cand("A", 1.0, clinvar=[2])
    assert R.confidence({"basis": "clinvar"}, c, 5.0)[0] == "moderate"   # conflict with phenotype


# ------------------------------------------------------- merging candidates

def test_merge_nested_and_equivalent():
    cs = [C("MONDO:HSAN1", "SPTLC1", orpha=["Orphanet:36386"]),                    # broader, no annotations
          C("MONDO:HSAN1A", "SPTLC1", omim=["OMIM:162400"], anc=["MONDO:HSAN1"]),
          C("MONDO:ALS27", "SPTLC1", omim=["OMIM:620285"]),
          C("Orphanet:36386", "SPTLC1", orpha=["Orphanet:36386"])]                  # same disease, other id
    g = R.merge_groups(cs, {c.key for c in cs}, {"MONDO:HSAN1A", "MONDO:ALS27"})
    assert g["MONDO:HSAN1"]["role"] == "broader" and g["MONDO:HSAN1"]["group"] == "MONDO:HSAN1A"
    assert g["Orphanet:36386"]["role"] == "equivalent"
    assert g["MONDO:HSAN1A"]["role"] == g["MONDO:ALS27"]["role"] == "representative"


def test_merge_keeps_siblings_apart():
    cs = [C("MONDO:OI", "COL1A1", orpha=["Orphanet:666"]), C("MONDO:OI1", "COL1A1", omim=["OMIM:166200"], anc=["MONDO:OI"]),
          C("MONDO:OI3", "COL1A1", omim=["OMIM:259420"], anc=["MONDO:OI"])]
    g = R.merge_groups(cs, {c.key for c in cs}, {"MONDO:OI1", "MONDO:OI3"})       # umbrella OI without annotations
    assert g["MONDO:OI"]["role"] == "broader" and g["MONDO:OI"]["narrower"] == ["MONDO:OI1", "MONDO:OI3"]
    assert g["MONDO:OI1"]["group"] != g["MONDO:OI3"]["group"]


def test_annotated_parent_competes_with_children():
    cs = [C("MONDO:NF1", "NF1", omim=["OMIM:162200"]),
          C("MONDO:SPINAL", "NF1", omim=["OMIM:162210"], anc=["MONDO:NF1"]),
          C("MONDO:NF1sub", "NF1", orpha=["Orphanet:363700"], anc=["MONDO:NF1"])]
    for annotated in ({"MONDO:NF1"}, {"MONDO:NF1", "MONDO:SPINAL"}):   # children with or without annotations
        g = R.merge_groups(cs, {c.key for c in cs}, annotated)
        assert g["MONDO:NF1"]["role"] == "representative"
        assert g["MONDO:NF1"]["narrower_competing"] == ["MONDO:NF1sub", "MONDO:SPINAL"]
        assert all(g[k]["role"] == "representative" for k in ("MONDO:SPINAL", "MONDO:NF1sub"))


def test_annotated_parent_and_child_compete_in_selection():
    s = R.select([cand("NF1", 7.0), cand("SPINAL", 2.0)], ["HP:1"], [], [])
    assert (s["status"], s["id"]) == ("resolved", "NF1")


def test_broader_term_not_folded_into_excluded_child():
    cs = [C("MONDO:P", "G", orpha=["Orphanet:1"]), C("MONDO:K", "G", omim=["OMIM:1"], anc=["MONDO:P"])]
    g = R.merge_groups(cs, {"MONDO:P"}, set())
    assert g["MONDO:P"]["role"] == "representative"


def test_unannotated_broader_term_cannot_make_ambiguity():
    broad = dict(cand("BROAD", None), compete=False)       # has an Orphanet id, so "specific", but merged
    s = R.select([cand("A", 5.0), broad], ["HP:1"], [], [])
    assert (s["status"], s["id"]) == ("resolved", "A")
    s = R.select([cand("A", 5.0), cand("BROAD", None)], ["HP:1"], [], [])    # without merging it would
    assert s["status"] == "ambiguous"


def test_broader_term_absorbed_in_clinvar_pool_too():
    s = R.select([cand("A", 3.0, clinvar=[2]), dict(cand("P", 3.2, clinvar=[2]), compete=False)], ["HP:1"], [], [])
    assert (s["status"], s["id"]) == ("resolved", "A")


# ------------------------------------------------- unknown-inheritance net

def test_unknown_much_higher_score_makes_ambiguous():
    s = R.select([cand("C", 2.0), cand("U", 5.0, moi="unknown")], ["HP:1"], [], [])
    assert s["status"] == "ambiguous" and set(s["tied"]) == {"C", "U"} and s["id"] == "C"


def test_unknown_slightly_higher_score_stays_behind():
    s = R.select([cand("C", 4.5), cand("U", 5.0, moi="unknown")], ["HP:1"], [], [])   # 10% < gap
    assert (s["status"], s["id"]) == ("resolved", "C")


def test_conditional_candidate_not_covered_by_unknown_net():
    s = R.select([cand("C", 2.0), cand("X", 9.0, moi="conditional")], ["HP:1"], [], [])
    assert (s["status"], s["id"]) == ("resolved", "C")


# ------------------------------------------------------- explicit / mapping

def C(key, gene="SYT1", label="", omim=(), orpha=(), syn=(), anc=()):
    c = R.Candidate(key, gene, label, list(omim), list(orpha))
    c.synonyms, c.ancestors = list(syn), list(anc)
    return c


def test_explicit_by_omim_number_and_name(ont):
    cs = [C("MONDO:1", label="Baker-Gordon syndrome", omim=["OMIM:618218"], syn=["BAGOS"]), C("MONDO:2", label="other")]
    e = R.explicit_diagnosis("girl with Baker Gordon Syndrome (BAGOS) (OMIM #618218)", cs, {"SYT1"}, set(), ont)
    assert e["adopted"] == ["MONDO:1"] and not e["alerts"]


def test_explicit_outside_candidates_alerts(ont):
    e = R.explicit_diagnosis("history of OMIM #999999", [C("MONDO:1", omim=["OMIM:618218"])], {"SYT1"}, set(), ont)
    assert e["adopted"] == [] and "not in the candidate set" in e["alerts"][0]


def test_phenotype_names_and_gene_symbols_not_diagnoses(ont):
    cs = [C("MONDO:1", label="hyperammonemia"), C("MONDO:2", label="SYT1", syn=["P65 disorder"])]
    e = R.explicit_diagnosis("infant with hyperammonemia and an SYT1 variant", cs, {"SYT1"}, set(), ont)
    assert e["adopted"] == [] and e["skipped_names"][0]["candidate"] == "MONDO:1"


def test_explicit_number_wins_even_if_name_is_hpo_term(ont):
    # label "Hyperammonemia" is an HPO term, so the name alone is skipped as a symptom ...
    cs = [C("MONDO:1", "OTC", label="hyperammonemia", omim=["OMIM:311250"], orpha=["Orphanet:664"]),
          C("MONDO:2", "OTC", label="hyperammonemia type 2 something")]
    e = R.explicit_diagnosis("infant with hyperammonemia", cs, {"OTC"}, set(), ont)
    assert e["adopted"] == []
    # ... but an explicit number always counts, OMIM or ORPHA
    for text in ("infant with hyperammonemia (OMIM #311250)", "infant with hyperammonemia, ORPHA:664"):
        e = R.explicit_diagnosis(text, cs, {"OTC"}, set(), ont)
        assert e["adopted"] == ["MONDO:1"], text
        assert any(h["how"] == "id_number" for m in e["matches"] for h in m["evidence"])


def test_number_beats_longer_name_match(ont):
    cs = [C("MONDO:1", label="Baker-Gordon syndrome", omim=["OMIM:618218"]),
          C("MONDO:2", label="a much longer named syndrome of something")]
    e = R.explicit_diagnosis("has a much longer named syndrome of something, OMIM 618218", cs, {"SYT1"}, set(), ont)
    assert e["adopted"] == ["MONDO:1"]


def test_unknown_inheritance_is_not_inconsistent():
    c = R.Candidate("MONDO:1", "G")
    inh = R.inheritance(c, [], "heterozygous", 1, "male", False)
    assert inh["result"] == "unknown"
    inh = R.inheritance(c, [{"moi": "MT", "sources": []}], "homozygous", 1, "male", False)
    assert inh["result"] == "unknown"
    # an unknown-inheritance candidate stays eligible and can be selected
    s2 = R.select([cand("U", 3.0, moi="unknown")], ["HP:1"], [], [])
    assert s2["id"] == "U" and s2["status"] == "resolved"
    # it is ranked after a consistent candidate, never dropped
    s3 = R.select([cand("U", 9.0, moi="unknown"), cand("C", 1.0)], ["HP:1"], [], [])
    assert s3["id"] == "C" and s3["basis"] == "inheritance"


def test_trait_mapping_via_hierarchy():
    cs = [C("MONDO:EDS1", "COL1A1", anc=["MONDO:0020066"]), C("MONDO:OI1", "COL1A1", anc=["MONDO:OI"]),
          C("MONDO:OI", "COL1A1")]
    m = S.Mondo()
    assert R.map_trait(["MONDO:0020066", "Orphanet:98249"], cs, m)[0] == ["MONDO:EDS1"]
    # a trait's MONDO id is used alone: the umbrella Orphanet xref must not add the umbrella candidate
    cs[2].orphanet = ["Orphanet:666"]
    assert R.map_trait(["MONDO:OI1", "Orphanet:666"], cs, m)[0] == ["MONDO:OI1"]


def test_trait_covering_every_candidate_not_mapped():
    cs = [C("MONDO:A", "G", anc=["MONDO:ROOT"]), C("MONDO:B", "G", anc=["MONDO:ROOT"])]
    assert R.map_trait(["MONDO:ROOT"], cs, S.Mondo())[0] == []


# ------------------------------------------------------------------- parsers

def test_frequency_parsing():
    assert S.parse_frequency("HP:0040281") == 0.9
    assert S.parse_frequency("3/4") == 0.75
    assert S.parse_frequency("25%") == 0.25
    assert S.parse_frequency("") is None


def test_id_normalisation_and_moi():
    assert S.norm_id("ORPHA:287") == "Orphanet:287"
    assert S.moi_code("Autosomal recessive inheritance") == "AR"
    assert S.moi_code("X-linked recessive") == "XLR"
    assert S.moi_code("Unknown") == "unknown"


def test_genereviews_scope(tmp_path: Path):
    p = tmp_path / "gr.txt"
    p.write_text("ataxia|NBK1138|ITPR1|Hereditary Ataxia\nataxia|NBK1138|ATXN1|Hereditary Ataxia\n"
                 "hsan1|NBK1390|SPTLC1|HSAN1\n")
    by = S.load_genereviews(LocalFile("genereviews", p, "", "2026-10-28", 0, 0, "", 3))
    assert by["ITPR1"][0].to_dict("x")["scope"] == "multi_gene"
    assert by["SPTLC1"][0].to_dict("x")["scope"] == "single_gene"


# --------------------------------------------------------------- concurrency

def test_llm_requests_capped_by_semaphore(tmp_path, monkeypatch):
    import threading
    import time as _t
    monkeypatch.setattr(X, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(X, "_SLOTS", threading.BoundedSemaphore(2))
    active, peak, lock = [0], [0], threading.Lock()

    def slow_chat(messages, **kw):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        _t.sleep(0.05)
        with lock:
            active[0] -= 1
        return {"model": "fake", "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}
    monkeypatch.setattr(X.llm, "chat", slow_chat)
    monkeypatch.setattr(X.llm, "config", lambda: CFG)
    ts = [threading.Thread(target=X._cached_chat, args=([{"role": "user", "content": str(i)}], 0, False)) for i in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert peak[0] == 2                                   # parallel, but never more than the cap


def test_samples_run_in_parallel_and_keep_sample_order(ont, monkeypatch):
    import threading
    import time as _t
    running, peak, lock = [0], [0], threading.Lock()
    ctx = "Child with focal seizures and hyperammonemia."
    by_k = {0: "focal seizures", 1: "hyperammonemia", 2: "focal seizures"}

    def fake_chat(messages, k, use_cache):
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        _t.sleep(0.05 * (3 - k))                          # sample 0 finishes last
        with lock:
            running[0] -= 1
        q = by_k[k]
        return {"content": json.dumps({"phenotypes": [{"quote": q, "description": q, "status": "present"}],
                                       "facts": {}}), "served_model": f"m{k}"}
    monkeypatch.setattr(X, "_cached_chat", fake_chat)
    out = X.extract(ctx, ont)
    assert peak[0] == 3
    assert [s["served_model"] for s in out["samples"]] == ["m0", "m1", "m2"]          # order = sample number
    assert [s["terms"] for s in out["samples"]] == [[("HP:0007359", "present")], [("HP:0001987", "present")],
                                                     [("HP:0007359", "present")]]
    assert [p["hpo_id"] for p in out["phenotypes"]] == ["HP:0007359"]                  # 2 of 3 votes


# ------------------------------------------- step 2 to-dos (2026-11-03): grouping, ranked-above count

def test_database_classified_group_never_competes_even_if_annotated():
    # like "undetermined early-onset EE" if a database called it a group: it has annotations and a high score
    grp = dict(cand("GROUP", 9.0, specific=False), grouping=["Orphanet DisorderGroup 'Group of disorders' (Orphanet:1)"])
    s = R.select([grp, cand("A", 2.0), cand("B", 1.0)], ["HP:1"], [], [])
    assert s["id"] == "A" and "GROUP" not in [s["id"]] + s["tied"]
    # without the database flag the same candidate would compete (annotation alone does not decide)
    s2 = R.select([cand("GROUP", 9.0, specific=False), cand("A", 2.0)], ["HP:1"], [], [])
    assert s2["id"] == "GROUP"


def test_specific_property_respects_grouping_flag():
    c = R.Candidate("MONDO:1", "G", orphanet=["Orphanet:1"])
    assert c.specific
    c.grouping = ["MONDO subset ordo_group_of_disorders"]
    assert not c.specific


def test_ranked_above_counts_only_compared_candidates():
    merged = dict(cand("M", 1.0, moi="unknown"), compete=False)        # merged into another candidate
    lower = cand("L", 1.0, moi="unknown")
    s = R.select([cand("A", 3.0), merged, lower], ["HP:1"], [], [])
    line = next(r for r in s["reasons"] if "ranked above" in r)
    assert "ranked above 1 candidate(s)" in line                        # L only, not the merged M

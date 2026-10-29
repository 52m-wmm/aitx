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
             node("0000005", "Mode of inheritance"),
             node("0000057", "obsolete Clitoromegaly", deprecated=True),
             node("0009999", "obsolete Old seizure term", deprecated=True, repl="0001250")]
    edges = [("0000118", "0000001"), ("0001250", "0000118"), ("0007359", "0001250"), ("0001263", "0000118"),
             ("0001987", "0000118"), ("0000478", "0000118"), ("0000005", "0000001")]
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


def test_lexical_overlap():
    assert H.lexical_overlap("ophthalmic abnormalities", ["Abnormality of the eye"]) == ["ophthalmic"]
    assert H.lexical_overlap("positive Gower sign", ["Gowers sign"]) == ["gower"]
    assert H.lexical_overlap("very thin", ["Fetal akinesia sequence"]) == []
    assert H.lexical_overlap("caloric intake is poor", ["Small for gestational age", "Birth weight < 10th"]) == []


# ---------------------------------------------------------------- extraction

CTX = "18-month-old female with hypotonia, developmental delay, EEG abnormalities (without overt seizures) and a de novo variant."


def test_quote_must_be_verbatim(ont):
    r = X.verify_phenotype({"quote": "developmental delays", "hpo_id": "HP:0001263", "status": "present"}, CTX, ont)
    assert not r["valid"] and "verbatim" in r["reasons"][0]


def test_wrong_id_falls_back_to_label(ont):
    r = X.verify_phenotype({"quote": "developmental delay", "hpo_id": "HP:0001987",
                            "hpo_label": "Global developmental delay", "status": "present"}, CTX, ont)
    assert r["valid"] and r["hpo_id"] == "HP:0001263"


def test_wrong_id_without_overlap_dropped(ont):
    r = X.verify_phenotype({"quote": "hypotonia", "hpo_id": "HP:0001987",
                            "hpo_label": "Hyperammonemia", "status": "present"}, CTX, ont)
    assert not r["valid"]
    # but a quote that is itself an exact HPO name is recovered
    r = X.verify_phenotype({"quote": "developmental delay", "hpo_id": "HP:0001987",
                            "hpo_label": "Hyperammonemia", "status": "present"}, CTX, ont)
    assert r["valid"] and r["hpo_id"] == "HP:0001263"


def test_negation(ont):
    ok = X.verify_phenotype({"quote": "without overt seizures", "hpo_id": "HP:0001250", "status": "excluded"}, CTX, ont)
    assert ok["valid"] and ok["status"] == "excluded"
    bad = X.verify_phenotype({"quote": "without overt seizures", "hpo_id": "HP:0001250", "status": "present"}, CTX, ont)
    assert not bad["valid"]
    bad2 = X.verify_phenotype({"quote": "developmental delay", "hpo_id": "HP:0001263", "status": "excluded"}, CTX, ont)
    assert not bad2["valid"]


def test_non_phenotype_term_rejected(ont):
    r = X.verify_phenotype({"quote": "de novo", "hpo_id": "HP:0000005", "status": "present"}, CTX, ont)
    assert not r["valid"]


@pytest.mark.parametrize("v,u,m", [(3, "year", 36), (18, "month", 18), (3, "months", 3), (2, "week", 0.5),
                                   (14, "years", 168), (None, "year", None), (3, "fortnight", None)])
def test_age_conversion(v, u, m):
    assert X.to_months(v, u) == m


def test_facts_verified():
    f = X.verify_facts({"age": {"value": 18, "unit": "month", "quote": "18-month-old"},
                        "sex": {"value": "female", "quote": "female"},
                        "variant_origin": {"value": "de_novo", "quote": "de novo"},
                        "onset": {"min": 8, "max": 8, "unit": "month", "quote": "at 8 months"},
                        "family_history": {"statement": None, "quote": None}}, CTX)
    assert f["age"]["months"] == 18 and f["sex"]["value"] == "female" and f["variant_origin"]["value"] == "de_novo"
    assert f["onset"]["months_min"] is None   # quote not in text -> unknown
    assert f["family_history"]["statement"] == "unknown"


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

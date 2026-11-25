"""Step 3b code-only parts (aitx/evidence/trials.py): no network, no LLM."""
import json

from aitx.evidence import trials as T


def study(nct, status="RECRUITING", conditions=("Primary Hyperoxaluria Type 1",), keywords=(), study_type="interventional",
          phases=("PHASE2",), min_age=None, max_age=None, sex="ALL", healthy=False, updated="2026-01-01", criteria=""):
    return {"nct": nct, "title": f"Study {nct}", "acronym": None, "status": status, "last_update": updated,
            "study_type": study_type, "phases": list(phases), "conditions": list(conditions), "keywords": list(keywords),
            "interventions": [], "min_age": min_age, "max_age": max_age, "sex": sex, "healthy_volunteers": healthy,
            "criteria": criteria}


def test_name_matching_ignores_word_order_and_needs_whole_abbreviations():
    assert T.name_matches("primary hyperoxaluria type 1", "Type 1 Primary Hyperoxaluria")
    assert T.name_matches("primary hyperoxaluria type 1", "Primary Hyperoxaluria Type I")       # roman numeral
    assert not T.name_matches("primary hyperoxaluria type 1", "Primary Hyperoxaluria Type 2")
    assert T.name_matches("PH1", "PH1 (primary hyperoxaluria)") and not T.name_matches("PH1", "ph1 levels")
    assert not T.name_matches("PH1", "PH12")


def test_gene_matching_needs_gene_context_for_short_symbols():
    for text in ("OTC deficiency", "Deficiency of OTC", "Ornithine Transcarbamylase (OTC) Deficiency"):
        assert T.gene_matches("OTC", text), text
    for text in ("OTC", "Hearing Aid OTC", "Outside the Cage (OTC)", "OTC-Pre Pub", "otc deficiency"):
        assert not T.gene_matches("OTC", text), text
    assert T.gene_matches("CFTR", "Mutation in CFTR") and T.gene_matches("CFTR", "CFTR-related disorder")
    assert not T.gene_matches("CFTR", "CFTR")
    assert T.gene_matches("SLC35A2", "SLC35A2") and T.gene_matches("SLC35A2", "SLC35A2-CDG")   # digit: unambiguous


def test_relevance_and_specificity():
    names = ["primary hyperoxaluria type 1"]
    assert T.relevance(study("NCT1"), names, "AGXT")["by"] == "disease"
    assert T.relevance(study("NCT2", conditions=("Esophageal Cancer",), keywords=("OTC",)), ["ornithine transcarbamylase deficiency"], "OTC") is None
    assert T.relevance(study("NCT3", conditions=("Kidney Stones",), keywords=("AGXT mutation",)), names, "AGXT")["by"] == "gene"
    assert T.specific(study("NCT1"), names, "AGXT")
    assert not T.specific(study("NCT4", conditions=("Primary Hyperoxaluria Type 1", "End Stage Renal Disease")), names, "AGXT")


def test_age_parsing_and_prefilter():
    assert T.age_months("18 Years") == 216 and T.age_months("1 Month") == 1 and T.age_months(None) is None
    assert abs(T.age_months("6 Weeks") - 1.38) < 0.01
    s = study("NCT1", min_age="12 Years")
    assert T.prefilter(s, 3, "male")["result"] == "fail"                          # 3-month-old, trial from 12 years
    assert T.prefilter(s, None, "male")["result"] == "unknown"                    # age unknown -> kept, conditional
    assert T.prefilter(study("NCT1", min_age="6 Years", max_age="64 Years"), 84, None)["result"] == "pass"
    assert T.prefilter(study("NCT1", sex="FEMALE"), 84, "male")["result"] == "fail"
    assert T.prefilter(study("NCT1", sex="FEMALE"), 84, None)["result"] == "unknown"
    hv = study("NCT1", conditions=("Healthy Volunteers",), healthy=True)
    assert T.prefilter(hv, 84, None)["result"] == "fail"
    assert T.prefilter(study("NCT1", healthy=True), 84, None)["result"] == "pass"  # accepts healthy people, not only them


def test_ranking_interventional_specific_phase_date():
    names, g = ["primary hyperoxaluria type 1"], "AGXT"
    obs = study("NCT_OBS", study_type="observational", phases=())
    broad = study("NCT_BROAD", conditions=("Primary Hyperoxaluria Type 1", "Kidney Stones"), phases=("PHASE3",))
    p3 = study("NCT_P3", phases=("PHASE3",), updated="2025-01-01")
    p2new = study("NCT_P2", phases=("PHASE2",), updated="2026-06-01")
    p3new = study("NCT_P3NEW", phases=("PHASE3",), updated="2026-02-01")
    order = sorted([obs, broad, p2new, p3, p3new], key=lambda s: T.rank_key(s, names, g))
    assert [s["nct"] for s in order] == ["NCT_P3NEW", "NCT_P3", "NCT_P2", "NCT_BROAD", "NCT_OBS"]


CRIT = """Patients with PH1.

Inclusion Criteria:

* Age 2 to 18 years
* One of the following:

  * eGFR \\>= 30
  * on dialysis
* Signed informed consent

Exclusion Criteria:

1. Hemoglobin \\< 7 mg/dL
2. Prior liver transplantation
"""


def test_split_criteria_verbatim_with_parents():
    items = T.split_criteria(CRIT)
    assert all(i["text"] in CRIT for i in items)
    assert [(i["id"], i["kind"]) for i in items] == [("pre1", "enrollment_note"), ("inc1", "inclusion"), ("inc2", "inclusion"),
                                                    ("inc3", "inclusion"), ("inc4", "inclusion"), ("inc5", "inclusion"),
                                                    ("exc1", "exclusion"), ("exc2", "exclusion")]
    assert items[0]["preamble"] and items[3]["parent"] == "inc2" and items[4]["parent"] == "inc2" and items[5]["parent"] is None
    assert items[6]["text"] == "Hemoglobin \\< 7 mg/dL" and T.unescape(items[6]["text"]) == "Hemoglobin < 7 mg/dL"


def test_split_inline_header():
    items = T.split_criteria("Inclusion Criteria: Age 2 to 18 years.\nExclusion criteria: none")
    assert [(i["kind"], i["text"]) for i in items] == [("inclusion", "Age 2 to 18 years."), ("exclusion", "none")]


def test_search_pages_and_counts(monkeypatch):
    pages = {None: {"totalCount": 3, "studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT00000001"}}}] * 2,
                    "nextPageToken": "t2"},
             "t2": {"totalCount": 3, "studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT00000003"}}}]}}

    class F:
        def __init__(self, url):
            tok = dict(x.split("=", 1) for x in url.split("?", 1)[1].split("&")).get("pageToken")
            self.text, self.accessed_at = json.dumps(pages[tok]), 100 if tok else 90

    monkeypatch.setattr(T.http, "get", lambda url, **k: F(url))
    s = T.search({"query.cond": "x"})
    assert s["total_count"] == 3 and s["n_retrieved"] == 3 and s["complete"] and len(s["page_urls"]) == 2
    assert s["queried_at"] == 90 and "countTotal=true" in s["url"]


def test_plan_branch_groups_every_study_once(monkeypatch):
    studies = [study("NCT_A", min_age="2 Years"),                                   # analysed
               study("NCT_B", min_age="12 Years"),                                  # ineligible (age)
               study("NCT_C", status="ACTIVE_NOT_RECRUITING"),                      # excluded: status
               study("NCT_D", conditions=("Esophageal Cancer",), keywords=("OTC",)),   # excluded: relevance
               study("NCT_E", status="NOT_YET_RECRUITING", study_type="observational", phases=())]
    studies += [study(f"NCT_K{i}", updated=f"2025-01-{i + 1:02d}") for i in range(T.K)]   # fill beyond the cap
    monkeypatch.setattr(T, "search", lambda params, **k: {"query": params, "url": "u", "page_urls": ["u"], "queried_at": 1,
                                                          "total_count": len(studies), "n_retrieved": len(studies),
                                                          "studies": studies, "complete": True, "database": "d", "endpoint": "e"})
    p = T.plan_branch(["primary hyperoxaluria type 1"], "AGXT", 84, "male")
    groups = ([s["nct"] for s in p["analysed"]], [s["nct"] for s in p["over_cap"]], [s["nct"] for s in p["ineligible"]],
              [x["nct"] for x in p["excluded"]])
    flat = [n for g in groups for n in g]
    assert sorted(flat) == sorted(s["nct"] for s in studies) and len(flat) == len(set(flat))
    assert len(p["analysed"]) == T.K and "NCT_E" in groups[1]                      # observational ranks last -> over cap
    assert groups[2] == ["NCT_B"]
    assert {x["nct"]: x["reason"] for x in p["excluded"]} == {"NCT_C": "status", "NCT_D": "relevance"}
    assert len(p["searches"]) == 2 and "studies" not in p["searches"][0]

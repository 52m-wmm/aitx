"""Fix plan N1 (2026-11-11): a short upper-case abbreviation never makes a trial relevant on its own.

Blind test, LRPPRC with names "Leigh syndrome / LS / LSS": 9 of 10 trials came in through "LS" or "LSS" -
limited-stage small cell lung cancer, HIV antibodies "...-LS", lumbar spinal stenosis. Reading rule R10.
"""
import pytest

from aitx.evidence import trials as T

LEIGH = ["Leigh syndrome", "LS", "LSS"]


def _study(title, conditions, keywords=()):
    return {"title": title, "conditions": list(conditions), "keywords": list(keywords)}


@pytest.mark.parametrize("name,want", [
    ("LS", True), ("LSS", True), ("CMT", True), ("PH1", True), ("CHNG6", True), ("STISS", True), ("CF", True),
    ("ACDMPV", False),                 # 6 letters: distinctive enough to stand alone
    ("Leigh syndrome", False), ("CMT/HMSN", False), ("RTHα", False), ("Cystic Fibrosis", False), ("", False),
])
def test_what_counts_as_a_short_abbreviation(name, want):
    assert T.is_abbrev(name) is want


@pytest.mark.parametrize("study", [
    _study("Toripalimab with or without Tifcemalimab", ["Limited-stage Small Cell Lung Cancer (LS-SCLC)"]),
    _study("SHARP SCLC", ["Small Cell Lung Cancer"], ["LS-SCLC"]),
    _study("ENABLE 1", ["HIV"], ["ePGT121v1-LS"]),
    _study("IDUNN", ["HIV-1"], ["3BNC117-LS"]),
    _study("ASSET", ["Spinal Surgery for Lumbar Spinal Stenosis (LSS)"]),
])
def test_the_blind_test_trials_are_no_longer_relevant(study):
    assert T.relevance(study, LEIGH, "LRPPRC") is None
    assert T.abbrev_only(study, LEIGH) in ("LS", "LSS")


def test_the_real_leigh_trial_still_matches():
    s = _study("A Dose-ranging Study of TTI-0102 in Adults and Children With Leigh Syndrome Spectrum", ["Leigh Syndrome"])
    assert T.relevance(s, LEIGH, "LRPPRC")["name"] == "Leigh syndrome"


def test_an_abbreviation_counts_when_the_record_also_has_the_full_name():
    s = _study("Natural history of Leigh syndrome", ["LS"])
    rel = T.relevance(s, LEIGH, "LRPPRC")
    assert rel["name"] == "LS" and rel["corroborated_by"] == "Leigh syndrome"


def test_an_abbreviation_counts_when_the_record_names_the_gene_as_the_condition():
    s = _study("Registry", ["CMT"], ["MPZ-related neuropathy"])
    rel = T.relevance(s, ["Charcot-Marie-Tooth disease type 1B", "CMT"], "MPZ")
    assert rel is not None


def test_a_gene_used_as_a_cancer_marker_does_not_corroborate():
    s = _study("LS-SCLC with LRPPRC Positive tumours", ["LS-SCLC", "LRPPRC Positive"])
    assert T.relevance(s, LEIGH, "LRPPRC") is None


def test_a_specific_study_needs_corroboration_too():
    assert not T.specific(_study("x", ["LS-SCLC"]), LEIGH, "LRPPRC")
    assert T.specific(_study("x", ["Leigh Syndrome"]), LEIGH, "LRPPRC")


def test_abbreviations_are_never_search_terms(monkeypatch):
    seen = []

    def fake_search(params, use_cache=True):
        seen.append(params)
        return {"studies": [], "query": params}
    monkeypatch.setattr(T, "search", fake_search)
    T.plan_branch(["LS", "Leigh syndrome", "LSS", "subacute necrotizing encephalomyelopathy"], "LRPPRC", None, None)
    conds = [p["query.cond"] for p in seen if "query.cond" in p]
    assert conds == ["Leigh syndrome", "subacute necrotizing encephalomyelopathy"]

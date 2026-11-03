"""Step 3.0: branches (contract 2), patient context (3), rule layer (4)."""
import json

import pytest

from aitx import http
from aitx.evidence import ledger as LG
from aitx.evidence import rules as RU
from aitx.evidence.branches import build_branches, patient_context


def cand(key, label, omim=(), score=1.0, narrower=None, specific=True, excluded=False):
    return {"key": key, "label": label, "omim": [{"id": o} for o in omim], "specific": specific, "excluded": excluded,
            "phenotype": {"score": score}, "merge": {"narrower_competing": narrower} if narrower else {},
            "orphanet": [], "mondo_url": f"https://monarchinitiative.org/{key}"}


def step2(status, primary, alts=(), cands=()):
    return {"primary": {"status": status, "id": primary, "reasons": ["why"], "alternatives": [{"id": a} for a in alts]},
            "candidates": list(cands), "not_supported": [],
            "inheritance_evidence": {"variants": [{"gene": "G1"}]}}


def test_resolved_is_one_branch():
    b, d = build_branches(step2("resolved", "M:1", cands=[cand("M:1", "D1", ["OMIM:100001"])]))
    assert [(x["id"], x["role"]) for x in b] == [("M:1", "primary")] and d == []


def test_umbrella_expanded_and_deduplicated():
    # like AITX-40003: HSAN1 (no OMIM) -> HSAN1A (already listed); juvenile ALS (no OMIM) -> ALS27
    cs = [cand("M:HSAN1", "HSAN1", score=1.9, narrower=["M:HSAN1A"]), cand("M:HSAN1A", "HSAN1A", ["OMIM:162400"], 1.6),
          cand("M:JALS", "juvenile ALS", score=2.5, narrower=["M:ALS27"]), cand("M:ALS27", "ALS27", ["OMIM:620285"], 1.4)]
    b, d = build_branches(step2("ambiguous", "M:HSAN1", ["M:HSAN1A", "M:JALS"], cs))
    assert [x["id"] for x in b] == ["M:HSAN1A", "M:ALS27"] and d == []
    assert b[0]["expanded_from"] == "M:HSAN1" and b[1]["expanded_from"] == "M:JALS"
    assert [x["role"] for x in b] == ["ambiguous_1", "ambiguous_2"]


def test_umbrella_without_children_kept_and_marked():
    b, _ = build_branches(step2("ambiguous", "M:1", ["M:2"], [cand("M:1", "D1", ["OMIM:100001"]), cand("M:2", "XLID")]))
    assert b[1]["umbrella"] and "no more specific disease" in b[1]["not_expandable"]


def test_more_than_three_branches_keep_top_scores():
    cs = [cand("M:A", "A", ["OMIM:100001"], 4.0), cand("M:B", "B", ["OMIM:100002"], 4.0),
          cand("M:OI", "OI", score=3.7, narrower=["M:OI1", "M:OI2"]), cand("M:OI1", "OI1", ["OMIM:166200"], 2.8),
          cand("M:OI2", "OI2", ["OMIM:166210"], 1.3)]
    b, d = build_branches(step2("ambiguous", "M:A", ["M:B", "M:OI"], cs))
    assert [x["id"] for x in b] == ["M:A", "M:B", "M:OI1"]
    assert [x["id"] for x in d] == ["M:OI2"] and "more than 3" in d[0]["dropped_reason"]


def test_unresolved_gets_gene_level_branch():
    b, _ = build_branches(step2("unresolved", None))
    assert b[0]["id"] == "gene:G1" and b[0]["role"] == "gene_level" and b[0]["diagnosis"] is None


def test_patient_context_registers_missing_age_and_sex():
    s2 = {"patient_facts": {"age": {"months": None}, "sex": {"value": "unknown"}, "variant_origin": {"value": "unknown"},
                            "family_history": {"statement": "unknown"}}, "phenotypes": [], "patient_onset": None}
    ctx, missing = patient_context({"variants": []}, s2)
    assert [m["variable"] for m in missing] == ["age", "sex"]


# ------------------------------------------------------------------ rules

ABSTRACT = "Most in-frame deletions in the DMD gene result in the milder Becker muscular dystrophy phenotype."
TEXT_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=1&rettype=abstract&retmode=text"


@pytest.fixture
def pubmed(monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, **kw: http.Fetched(url, ABSTRACT, 1793700000, True))


def rule(**over):
    r = {"id": "DMD-frame-1", "gene": "DMD", "version": 1, "applies_when": {"variant_class": ["inframe_deletion"]},
         "statement": "In-frame DMD deletions usually cause Becker rather than Duchenne muscular dystrophy.",
         "effect": {"type": "diagnosis", "supports": ["OMIM:300376"], "argues_against": ["OMIM:310200"]},
         "sources": [{"type": "pmid", "id": "1", "text_url": TEXT_URL, "quote": "Most in-frame deletions in the DMD gene",
                      "accessed_at": 1793700000}],
         "strength": "established", "status": "verified", "review": {"decision": "not_reviewed"}}
    r.update(over)
    r["content_sha256"] = RU.content_hash(r)
    return r


def test_valid_rule_loads(pubmed):
    assert RU.validate(rule()) == []


def test_vetoed_rule_not_loaded_and_reason_required(pubmed):
    r = rule()
    r["review"] = {"decision": "vetoed", "by": "reviewer", "at": "2026-11-03", "reason": "abstract is about mice"}
    assert RU.validate(r) == ["vetoed: abstract is about mice"]
    r["review"] = {"decision": "vetoed"}
    assert "NO REASON GIVEN" in RU.validate(r)[0]


def test_hand_edited_rule_not_loaded(pubmed):
    r = rule()
    r["statement"] = "In-frame DMD deletions always cause Becker."          # edited after drafting
    assert any("hand edit" in x for x in RU.validate(r))


def test_rule_conditions_only_from_step1(pubmed):
    assert any("non-step-1" in x for x in RU.validate(rule(applies_when={"patient_age": [0, 5]})))


def test_rule_quote_must_be_in_fetched_source(pubmed):
    r = rule(sources=[{"type": "pmid", "id": "1", "text_url": TEXT_URL, "quote": "always Duchenne", "accessed_at": 1}])
    assert any("quote not verified" in x for x in RU.validate(r))


def test_rule_application_reorders_but_keeps_branches(pubmed):
    branches = [{"id": "M:DMD", "diagnosis": {"omim": ["OMIM:310200"]}}, {"id": "M:BMD", "diagnosis": {"omim": ["OMIM:300376"]}},
                {"id": "M:XLID", "diagnosis": {"omim": []}}]
    led = LG.Ledger("P", branches)
    RU.apply_rules(led, {"loaded": [rule()], "skipped": []},
                   {"variants": [{"gene": "DMD", "variant_cdna": "c.1_3del", "variant_class": "inframe_deletion"}]})
    assert led.branch_order == ["M:BMD", "M:XLID", "M:DMD"]                  # nothing removed
    assert {(a["branch"], a["effect"]) for a in led.branch_assessment} == {("M:BMD", "supports"), ("M:DMD", "argues_against")}
    ev = [e for e in led.evidence.values() if e["retrieved_by"] == "rule DMD-frame-1"]
    assert ev and ev[0]["status"] == "verified" and ev[0]["section"] == "background"


def test_rule_for_a_diagnosis_that_is_not_a_branch_is_reported(pubmed):
    led = LG.Ledger("P", [{"id": "M:DMD", "diagnosis": {"omim": ["OMIM:310200"]}}])
    RU.apply_rules(led, {"loaded": [rule()], "skipped": []},
                   {"variants": [{"gene": "DMD", "variant_cdna": "c.1_3del", "variant_class": "inframe_deletion"}]})
    assert led.rules_applied[0]["branches_not_present"] == ["OMIM:300376"]   # Becker is not a step 2 branch


def test_rule_not_matching_variant_is_ignored(pubmed):
    led = LG.Ledger("P", [{"id": "M:DMD", "diagnosis": {"omim": ["OMIM:310200"]}}])
    RU.apply_rules(led, {"loaded": [rule()], "skipped": []},
                   {"variants": [{"gene": "DMD", "variant_cdna": "c.1del", "variant_class": "frameshift"}]})
    assert led.rules_applied == [] and led.branch_order == ["M:DMD"]


def test_load_rules_reads_files_and_reports_skipped(tmp_path, pubmed):
    vetoed = rule(id="DMD-frame-2")
    vetoed["review"] = {"decision": "vetoed", "reason": "duplicate"}
    (tmp_path / "DMD.json").write_text(json.dumps({"gene": "DMD", "rules": [rule(), vetoed]}))
    got = RU.load_rules(tmp_path)
    assert [r["id"] for r in got["loaded"]] == ["DMD-frame-1"]
    assert got["skipped"] == [{"rule_id": "DMD-frame-2", "file": "DMD.json", "reasons": ["vetoed: duplicate"]}]


# ------------------------------------------------- rule promotion (contract section 2)

def _s2(*cands):
    return {"candidates": [cand(*c) for c in cands]}


def _dmd_branches():
    return [{"id": "M:DMD", "role": "ambiguous_1", "gene": "DMD", "diagnosis": {"omim": ["OMIM:310200"]}},
            {"id": "M:XLID", "role": "ambiguous_2", "gene": "DMD", "diagnosis": {"omim": []}}]


INFRAME = {"variants": [{"gene": "DMD", "variant_cdna": "c.1_3del", "variant_class": "inframe_deletion"}]}


def test_rule_promotes_step2_candidate_to_branch(pubmed):
    led = LG.Ledger("P", _dmd_branches())
    s2 = _s2(("M:DMD", "Duchenne", ["OMIM:310200"], 5.4), ("M:BMD", "Becker", ["OMIM:300376"], 3.0))
    RU.apply_rules(led, {"loaded": [rule()], "skipped": []}, INFRAME, s2)
    ids = [b["id"] for b in led.branches]
    assert ids == ["M:DMD", "M:XLID", "M:BMD"]                                  # Duchenne kept, Becker added
    bmd = led.branches[2]
    assert bmd["promoted_by"] == "DMD-frame-1" and "promoted by rule DMD-frame-1" in bmd["why"][0]
    assert [b["role"] for b in led.branches] == ["ambiguous_1", "ambiguous_2", "ambiguous_3"]
    assert led.rules_applied[0]["promotions"] == [{"omim": "OMIM:300376", "candidate": "M:BMD", "promoted": True}]
    assert led.branch_order[0] == "M:BMD" and led.branch_order[-1] == "M:DMD"   # reordered, nothing removed


def test_promotion_blocked_at_branch_limit(pubmed):
    led = LG.Ledger("P", _dmd_branches() + [{"id": "M:X", "role": "ambiguous_3", "gene": "DMD",
                                             "diagnosis": {"omim": ["OMIM:100001"]}}])
    s2 = _s2(("M:BMD", "Becker", ["OMIM:300376"], 3.0))
    RU.apply_rules(led, {"loaded": [rule()], "skipped": []}, INFRAME, s2)
    assert len(led.branches) == 3 and "M:BMD" not in [b["id"] for b in led.branches]
    p = led.rules_applied[0]["promotions"][0]
    assert not p["promoted"] and "branch limit" in p["reason"]


def test_only_step2_candidates_can_be_promoted(pubmed):
    led = LG.Ledger("P", _dmd_branches())
    RU.apply_rules(led, {"loaded": [rule()], "skipped": []}, INFRAME, _s2(("M:DMD", "Duchenne", ["OMIM:310200"])))
    assert [b["id"] for b in led.branches] == ["M:DMD", "M:XLID"]
    assert led.rules_applied[0]["promotions"][0]["reason"] == "not a step 2 candidate"
    # an excluded step 2 candidate is not eligible either
    led2 = LG.Ledger("P", _dmd_branches())
    s2 = {"candidates": [dict(cand("M:BMD", "Becker", ["OMIM:300376"]), excluded=True)]}
    RU.apply_rules(led2, {"loaded": [rule()], "skipped": []}, INFRAME, s2)
    assert "M:BMD" not in [b["id"] for b in led2.branches]


def test_matching_rule_without_promotion_keeps_resolved_role(pubmed):
    led = LG.Ledger("P", [{"id": "M:BMD", "role": "primary", "gene": "DMD", "diagnosis": {"omim": ["OMIM:300376"]}}])
    RU.apply_rules(led, {"loaded": [rule()], "skipped": []}, INFRAME, _s2(("M:BMD", "Becker", ["OMIM:300376"])))
    assert led.branches[0]["role"] == "primary"


def test_unloaded_rule_promotes_nothing(pubmed):
    led = LG.Ledger("P", _dmd_branches())
    RU.apply_rules(led, {"loaded": [], "skipped": [{"rule_id": "x", "reasons": ["vetoed: y"]}]}, INFRAME,
                   _s2(("M:BMD", "Becker", ["OMIM:300376"])))
    assert [b["id"] for b in led.branches] == ["M:DMD", "M:XLID"]


def test_weak_rule_is_background_only(pubmed):
    led = LG.Ledger("P", _dmd_branches())
    s2 = _s2(("M:DMD", "Duchenne", ["OMIM:310200"], 5.4), ("M:BMD", "Becker", ["OMIM:300376"], 3.0))
    RU.apply_rules(led, {"loaded": [rule(strength="weak")], "skipped": []}, INFRAME, s2)
    assert [b["id"] for b in led.branches] == ["M:DMD", "M:XLID"]          # no promotion
    assert led.branch_assessment == [] and led.branch_order == ["M:DMD", "M:XLID"]
    applied = led.rules_applied[0]
    assert applied["affects_branches"] is False and applied["promotions"] == []
    assert any(e["retrieved_by"] == "rule DMD-frame-1" for e in led.evidence.values())   # still background evidence


def test_pending_rule_needs_reviewer_acceptance(pubmed):
    r = rule(status="pending_review", support_check={"overall": "partially_supported"})
    assert any("pending review" in x for x in RU.validate(r))
    r["review"] = {"decision": "accepted", "by": "reviewer", "at": "2026-11-03"}          # no reason -> not enough
    assert any("pending review" in x for x in RU.validate(r))
    r["review"]["reason"] = "quotes state the reading-frame rule"
    assert RU.validate(r) == []                                                          # accepted -> loads


def test_verified_rule_must_have_passed_support_check(pubmed):
    r = rule(support_check={"overall": "not_supported"})                                 # status verified by hand
    assert any("did not find it supported" in x for x in RU.validate(r))


def test_review_identity_ignores_status_and_checks():
    a, b = rule(), rule(status="pending_review", support_check={"overall": "partially_supported"})
    assert RU.identity(a) == RU.identity(b) and RU.content_hash(a) != RU.content_hash(b)

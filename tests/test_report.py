"""Step 4 report assembly (contract docs/step4_contract.md v1.0). Offline: a synthetic ledger, no network."""
import datetime as dt
import json

import pytest

from aitx.report import assemble as A
from aitx.report import safety as S
from aitx.report import validate as V

CASE = {"id": "P", "patient": {"genotype": [{"gene": "G", "variant_cdna": "c.1A>G", "variant_protein": "p.Met1?",
                                             "zygosity": "homozygous"}]}}
SRC = {"type": "nbk", "id": "NBK1", "url": "https://www.ncbi.nlm.nih.gov/books/NBK1/", "section": "Management"}


def ev(i, quote="Drug X for persons with disease D.", src=SRC, kind="sourced"):
    return {"id": i, "kind": kind, "quote": quote, "source": src, "claim": "c", "status": "verified"}


def act(key, section, label, status, reqs=(), evs=("e1",), branches=("B",), **kw):
    return {"action_key": key, "section": section, "label": label, "applies_to": list(branches),
            "status_by_branch": {b: {"status": status, "reason": "r"} for b in branches},
            "requirements": list(reqs), "evidence_ids": list(evs), **kw}


def unk(text, field="kidney function"):
    return {"id": "r1", "requirement": text, "result": "unknown", "patient_status": "unknown", "applies_to": ["B"],
            "patient_fact": {"field": field}}


def ledger(actions, **kw):
    return {"branches": [{"id": "B", "diagnosis": {"label": "disease D"}}], "evidence": [ev("e1")],
            "actions": actions, "missing_information": kw.get("missing", []),
            "offlabel_searches": kw.get("offlabel", {})}


def build(led, safety=None):
    return A.assemble(led, CASE, lambda src, e=None: "2024-08-15", safety, today=dt.date(2026, 11, 15))


@pytest.mark.parametrize("text", ["enzymeactivity" * 10, "during " + "enzymeactivity" * 10])
def test_review_report_clips_quotes_and_conditions_only_between_words(text):
    clipped = A.clean(text, 20)
    assert all(word in text.split() for word in clipped.split() if word != "…")


def test_the_report_has_every_template_section_in_order():
    md, _ = build(ledger([act("drug:1", "existing_targeted_therapies", "drug X", "applicable")]))
    assert V.check_markdown(md) == []
    pos = [md.index(h + "\n") for h in V.HEADINGS]
    assert pos == sorted(pos)


def test_reverse_the_validator_rejects_a_missing_or_misordered_heading():
    md, _ = build(ledger([]))
    assert V.check_markdown(md.replace("### Drug Repurposing\n", ""))
    swapped = md.replace("### Bespoke Therapies", "@@").replace("### Drug Repurposing", "### Bespoke Therapies") \
        .replace("@@", "### Drug Repurposing")
    assert "headings out of the template order" in V.check_markdown(swapped)


def test_the_submission_is_a_json_array_of_id_and_markdown():
    md, _ = build(ledger([]))
    assert V.check_submission(json.dumps([{"id": "P", "report_markdown": md}])) == []
    assert V.check_submission("{not json") and V.check_submission(json.dumps({"id": "P"}))
    assert V.check_submission(json.dumps([{"id": "P", "report_markdown": md, "extra": 1}]))


def test_not_applicable_non_recommended_and_report_false_entries_are_left_out():
    rec = dict(unk("the source recommends this measure"), result="fail", context_check="recommendation")
    md, _ = build(ledger([act("drug:1", "supportive_management", "kept drug", "applicable"),
                          act("drug:2", "supportive_management", "ruled out", "not_applicable"),
                          act("drug:3", "supportive_management", "only described", "not_applicable", [rec]),
                          act("drug:4", "supportive_management", "pregnancy only", "conditional", report=False)]))
    assert "kept drug" in md
    for lab in ("ruled out", "only described", "pregnancy only"):
        assert lab not in md


def test_a_conditional_entry_names_what_it_depends_on_and_cites_the_source_with_its_date():
    md, _ = build(ledger([act("drug:1", "existing_targeted_therapies", "drug X", "conditional", [unk("eGFR >= 30")])]))
    assert "Depends on kidney function (eGFR >= 30)" in md
    assert "[GeneReviews NBK1, Management; updated 2024-08-15]" in md and '"Drug X for persons with disease D."' in md


def test_an_old_product_source_is_flagged_as_possibly_out_of_date():
    led = ledger([act("device:1", "supportive_management", "retinal prosthesis system", "applicable")])
    md, _ = A.assemble(led, CASE, lambda s, e=None: "2019-01-01", today=dt.date(2026, 11, 15))
    assert "may be out of date" in md
    md, _ = A.assemble(led, CASE, lambda s, e=None: "2025-01-01", today=dt.date(2026, 11, 15))
    assert "may be out of date" not in md                     # reverse: a recent source is not flagged


def test_caps_leave_the_rest_in_the_ledger_with_a_count():
    trials = [act(f"trial:{i}", "clinical_trial_eligibility", f"Trial {i}", "conditional", [unk(f"x{i}")] * (i % 3),
                  study_type="interventional") for i in range(8)]
    md, _ = build(ledger(trials))
    assert md.count("- **Trial") == 5 and "3 further trials are recorded in the evidence ledger" in md
    md, _ = build(ledger([act(f"drug:{i}", "existing_targeted_therapies", f"T{i}", "applicable") for i in range(12)]))
    assert md.count("- **T") == 12                            # reverse: targeted therapies are not capped


def test_trials_with_fewer_unknowns_come_first():
    md, _ = build(ledger([act("trial:a", "clinical_trial_eligibility", "Many unknowns", "conditional",
                              [unk("a"), unk("b"), unk("c")], study_type="interventional"),
                          act("trial:b", "clinical_trial_eligibility", "One unknown", "conditional", [unk("a")],
                              study_type="interventional")]))
    assert md.index("One unknown") < md.index("Many unknowns")


def test_contraindications_not_applicable_are_counted_not_listed():
    md, _ = build(ledger([act("x:1", "contraindications_precautions", "avoid fasting", "applicable"),
                          act("x:2", "contraindications_precautions", "pregnancy drug", "not_applicable")]))
    assert "avoid fasting" in md and "pregnancy drug" not in md
    assert "1 further entries do not apply to this patient" in md


def test_ineffective_only_drugs_close_the_offlabel_section_and_adverse_reports_go_to_precautions():
    off = {"B": {"precaution_candidates": [{"drug": "drug W", "pmid": "1", "url": "u", "quote": "worsened after W",
                                            "note": "reported to worsen after use (not a contraindication)"}]}}
    md, _ = build(ledger([act("drug:5", "off_label_expanded_access", "drug Y", "conditional",
                              efficacy_direction="reported_improvement", conclusion="Improvement has been reported."),
                          act("drug:6", "off_label_expanded_access", "drug Z", "conditional",
                              efficacy_direction="reported_ineffective")], offlabel=off))
    off_part = md[md.index("### Off-label"):md.index("## Tier 3")]
    assert off_part.index("drug Y") < off_part.index("**drug Z** — reported ineffective; not recommended.")
    pre = md[md.index("### Contraindications"):md.index("## Tier 2")]
    assert "drug W" in pre and "worsened after W" in pre


def test_an_empty_section_says_what_was_searched():
    neg = {"id": "n1", "kind": "negative", "claim": "c", "search": {"database": "open targets", "query": "target T",
                                                                     "queried_at": 1794736156, "n_results": 0,
                                                                     "n_excluded": 0}}
    led = ledger([act(None, "drug_repurposing", "None found", "searched_none", evs=("n1",))])
    led["evidence"].append(neg)
    md, _ = build(led)
    part = md[md.index("### Drug Repurposing"):md.index("### Outcome")]
    assert "Searched open targets (query: target T" in part and "nothing qualified" in part


def test_shared_entries_name_the_diagnoses_they_apply_to():
    led = ledger([act("drug:1", "existing_targeted_therapies", "shared", "applicable", branches=("B", "C")),
                  act("drug:2", "existing_targeted_therapies", "only C", "applicable", branches=("C",))])
    led["branches"].append({"id": "C", "diagnosis": {"label": "disease E"}})
    md, _ = build(led)
    assert "shared** — applicable. Applies to: disease D, disease E." in md
    assert "only C** — applicable. Applies to: disease E." in md


def test_the_summary_lists_the_most_important_missing_information():
    miss = [{"variable": "kidney function", "affects": ["a", "b", "c"]}, {"variable": "age", "affects": ["a"]},
            {"variable": "sex", "affects": []}]
    md, _ = build(ledger([], missing=miss))
    s = md[:md.index("## Tier 1")]
    assert s.index("kidney function: 3 entries") < s.index("age: 1 entry") and "sex" not in s


def test_ranking_follows_the_fixed_order_with_a_reason():
    led = ledger([act("trial:1", "clinical_trial_eligibility", "Trial T", "conditional", [unk("a")],
                      study_type="interventional"),
                  act("drug:5", "off_label_expanded_access", "drug Y", "conditional",
                      efficacy_direction="reported_improvement"),
                  {"section": "bespoke_therapies", "label": "gene replacement", "classification": "theoretically_possible",
                   "conclusion": "theoretically possible", "premises_complete": True, "applies_to": ["B"]}])
    md, _ = build(led)
    r = md[md.index("### Outcome"):]
    assert r.index("drug Y") < r.index("Trial T") < r.index("gene replacement")
    assert "human precedent with reported improvement" in r


def test_safety_check_quotes_label_interactions_between_written_drugs():
    labels = {"s1": {"set_id": "s1", "effective_time": "20250101",
                     "drug_interactions": ["Avoid use with drug B. Other text."],
                     "contraindications": ["Hypersensitivity to drug A."]}}
    out = S.check([{"label": "drug A", "names": ["drug A"], "set_ids": ["s1"]},
                   {"label": "drug B", "names": ["drug B"], "set_ids": []}], fetch=labels.get)
    assert out["interactions"][0]["quote"] == "Avoid use with drug B." and out["interactions"][0]["other"] == "drug B"
    assert out["contraindications"][0]["quote"] == "Hypersensitivity to drug A." and not out["contraindications"][0]["none"]
    assert out["not_checked"] == ["drug B"]
    md, _ = build(ledger([]), safety=out)
    assert "Check before use" in md and "Avoid use with drug B." in md


def test_reverse_no_interaction_is_reported_when_the_label_does_not_name_the_other_drug():
    labels = {"s1": {"set_id": "s1", "drug_interactions": ["No clinical interaction studies."], "contraindications": []}}
    out = S.check([{"label": "drug A", "names": ["drug A"], "set_ids": ["s1"]},
                   {"label": "drug B", "names": ["drug B"], "set_ids": ["s1"]}], fetch=labels.get)
    assert out["interactions"] == []


def test_a_label_with_no_contraindications_is_one_line_not_fragments():
    labels = {"s1": {"set_id": "s1", "drug_interactions": [], "contraindications": ["4 CONTRAINDICATIONS None. None. ( 4 )"]}}
    out = S.check([{"label": "drug A", "names": ["drug A"], "set_ids": ["s1"]}], fetch=labels.get)
    assert len(out["contraindications"]) == 1 and out["contraindications"][0]["none"]
    md, _ = build(ledger([]), safety=out)
    assert "drug A: the label lists no contraindications" in md and '"( 4 )"' not in md


def test_the_supplement_notice_only_for_supplements_and_access_route_is_shown():
    reg_drug = {"fda": {"approved": True}, "supplement": None}
    reg_supp = {"fda": None, "supplement": {"dsld": "x"}}
    md, _ = build(ledger([act("drug:1", "off_label_expanded_access", "approved drug", "conditional",
                              regulatory=reg_drug, access_route_label="FDA-approved drug (off-label use for this disease)"),
                          act("drug:2", "off_label_expanded_access", "herb", "conditional", regulatory=reg_supp)]))
    assert "approved drug: not an FDA-approved drug" not in md and "herb: not an FDA-approved drug" in md
    assert "Access: FDA-approved drug (off-label use for this disease)." in md


def test_an_old_article_is_flagged_without_the_product_wording():
    led = ledger([act("drug:1", "existing_targeted_therapies", "drug X", "applicable")])
    md, _ = A.assemble(led, CASE, lambda s, e=None: "2019", today=dt.date(2026, 11, 15))
    assert "more than 5 years old: may be out of date)" in md and "still available" not in md


# --- review of the first AGXT report (user, 2026-11-15)

def test_the_summary_opens_with_priority_actions():
    md, _ = build(ledger([act("drug:1", "existing_targeted_therapies", "drug L", "applicable"),
                          act("drug:2", "existing_targeted_therapies", "drug N", "conditional", [unk("eGFR >= 30")])]))
    s = md[:md.index("## Tier 1")]
    assert s.index("**Priority actions**") < s.index("**Diagnosis**")
    assert "drug L (existing targeted therapy; applicable)" in s and "If eGFR >= 30: drug N" in s


def test_an_entry_waiting_on_an_unreported_manifestation_ranks_after_the_others():
    led = ledger([act("drug:5", "off_label_expanded_access", "eye drug", "conditional",
                      [unk("choroidal neovascularization", field="manifestation")],
                      efficacy_direction="reported_improvement"),
                  act("trial:1", "clinical_trial_eligibility", "Trial T", "conditional", [unk("a"), unk("b")],
                      study_type="interventional")])
    md, _ = build(led)
    r = md[md.index("**Ranking**"):]
    assert r.index("Trial T") < r.index("eye drug") and "ranked after the others" in r


def test_outcome_measures_come_from_trial_primary_outcomes_and_surveillance():
    led = ledger([act("trial:1", "clinical_trial_eligibility", "Trial T", "conditional", [unk("a")],
                      study_type="interventional", nct="NCT00000001", url="https://clinicaltrials.gov/study/NCT00000001"),
                  act("drug:1", "existing_targeted_therapies", "drug L", "applicable")])
    md, _ = A.assemble(led, CASE, lambda s, e=None: "2024-08-15", today=dt.date(2026, 11, 15),
                       outcomes_of=lambda nct: ["Percent change in urinary oxalate (6 months)"],
                       surveillance_of=lambda nbk: ["Serum creatinine for eGFR at least annually."])
    om = md[md.index("**Outcome measures**"):md.index("**Ranking**")]
    assert "Percent change in urinary oxalate (6 months) [NCT00000001 primary outcome]" in om
    assert '"Serum creatinine for eGFR at least annually." [GeneReviews NBK1, Management / Surveillance; updated 2024-08-15]' in om


def test_a_caution_kept_from_the_same_source_is_shown_under_the_entry():
    md, _ = build(ledger([act("procedure:1", "supportive_management", "lithotripsy", "conditional", [unk("stones")],
                              cautions=["Hard stones are resistant to lithotripsy."])]))
    assert 'Caution (same source): "Hard stones are resistant to lithotripsy."' in md


def test_no_contraindication_is_one_sentence_without_the_label_fragments():
    md, _ = build(ledger([]), safety={"contraindications": [{"drug": "drug A", "none": True, "quote": "4 CONTRAINDICATIONS None. ( 4 )",
                                                             "set_id": "s1", "effective_date": "20250101", "url": "u"}]})
    assert "drug A: the label lists no contraindications [FDA label s1" in md and "( 4 )" not in md


def test_only_efficacy_outcomes_of_interventional_trials_are_listed():
    led = ledger([act("trial:1", "clinical_trial_eligibility", "Trial T", "conditional", [unk("a")],
                      study_type="interventional", nct="NCT1", url="u"),
                  act("trial:2", "clinical_trial_eligibility", "Registry R", "conditional", [unk("a")],
                      study_type="observational", nct="NCT2", url="u")])
    outs = {"NCT1": ["Incidence of treatment-emergent adverse events (6 months)", "Percent change in urinary oxalate"],
            "NCT2": ["Number of samples stored in tissue bank"]}
    md, _ = A.assemble(led, CASE, lambda s, e=None: None, today=dt.date(2026, 11, 15), outcomes_of=lambda n: outs[n])
    om = md[md.index("**Outcome measures**"):md.index("**Ranking**")]
    assert "urinary oxalate" in om and "adverse events" not in om and "samples" not in om


def test_a_caution_sentence_is_not_also_cited_as_support():
    led = ledger([act("procedure:1", "supportive_management", "lithotripsy", "conditional", [unk("stones")],
                      evs=("e1", "e2"), cautions=["Hard stones resist it."])])
    led["evidence"].append(ev("e2", quote="Hard stones resist it."))
    md, _ = build(led)
    assert md.count("Hard stones resist it.") == 1 and "Caution (same source)" in md

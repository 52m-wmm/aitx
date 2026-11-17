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
    return {"id": "r1", "kind":"inclusion", "requirement": text, "result": "unknown", "patient_status": "unknown", "applies_to": ["B"],
            "patient_fact": {"field": field}}


def ledger(actions, **kw):
    return {"branches": [{"id": "B", "diagnosis": {"label": "disease D"}}], "evidence": [ev("e1")],
            "actions": actions, "missing_information": kw.get("missing", []),
            "offlabel_searches": kw.get("offlabel", {})}


def build(led, safety=None):
    return A.assemble(led, CASE, lambda src, e=None: "2024-08-15", safety, today=dt.date(2026, 11, 15))


def variant_evidence():
    return dict(ev("v1", '"frameshift"', {"type": "pipeline_fact", "id": "step1:P:variants[0].variant_class",
        "url": "https://www.ncbi.nlm.nih.gov/nuccore/NM_000030.3", "upstream": {"type": "refseq", "id": "NM_000030.3"}}),
        section="background")


def safety_evidence(led, safety):
    """Mock label findings with ledger evidence, as required by the user's additional review."""
    for kind in ("interactions", "contraindications", "warnings"):
        for row in safety.get(kind, []):
            eid = f"s{len(led['evidence'])}"
            led["evidence"].append(ev(eid, row["quote"], {"type": "spl_setid", "id": row["set_id"], "url": row["url"]}))
            row["evidence_ids"] = [eid]
    for row in safety.get("coverage", []):
        row["evidence_ids"] = [led["evidence"][0]["id"]]
    return led


def test_all_interventional_trials_are_listed_before_the_observational_summary():
    obs = [act(f"trial:o{i}", "clinical_trial_eligibility", f"Registry {i}", "conditional", study_type="observational") for i in range(3)]
    trials = [act(f"trial:i{i}", "clinical_trial_eligibility", f"Intervention {i}", "conditional",
                  [unk(f"q{x}") for x in range(i+1)], study_type="interventional", nct=f"NCT0000000{i}") for i in range(6)]
    md, _ = build(ledger(obs + list(reversed(trials))))
    part = md.split("### Clinical Trial Eligibility")[1].split("### Off-label")[0]
    assert all(f"**Intervention {i}**" in part for i in range(5))
    assert "**Intervention 5**" in part and "**Registry" not in part and "Observational studies (3)" in part
    assert part.index("Intervention 0") < part.index("Intervention 4")


def test_review3_observational_trials_follow_interventions_then_sort_by_unknowns():
    acts = [act("trial:o1", "clinical_trial_eligibility", "Registry one", "conditional", [unk("x")], study_type="observational"),
            act("trial:i", "clinical_trial_eligibility", "Intervention", "conditional", [unk("x")]*4, study_type="interventional"),
            act("trial:o0", "clinical_trial_eligibility", "Registry zero", "applicable", study_type="observational")]
    md, _ = build(ledger(acts)); part=md.split("### Clinical Trial Eligibility")[1].split("### Off-label")[0]
    assert part.index("**Intervention**") < part.index("Registry zero") < part.index("Registry one")


def test_code_rule_verdicts_are_restored_as_code_outputs():
    acts = [{"section":"bespoke_therapies", "modality":"gene_replacement", "label":"gene replacement (AAV)",
             "classification":"theoretically_possible", "conclusion":"AAV is theoretically possible.",
             "criteria_met":["coding sequence 1176 nt is within 4.7 kb"], "facts":{"target_organ":"liver"},
             "note":"promoter and polyA are not sized", "applies_to":["B"],"evidence_ids":[]},
            {"section":"bespoke_therapies", "modality":"base_or_prime_editing", "label":"base or prime editing",
             "classification":"theoretically_possible", "conclusion":"Prime editing is theoretically possible.",
             "facts":{"reason":"an insertion cannot be corrected by base editors"},"provenance":{"code_only":True},
             "unassessable_reason":["PAM and editing window not assessed"],"applies_to":["B"],"evidence_ids":[]},
            {"section":"bespoke_therapies", "modality":"aso_exon_skipping", "label":"ASO exon skipping",
             "classification":"not_eligible", "conclusion":"Not eligible.","failed_criterion":"first coding exon removes the start codon",
             "applies_to":["B"],"evidence_ids":[]}]
    led=ledger(acts); led["evidence"].append(variant_evidence())
    md, _ = build(led);part=md.split("### Bespoke Therapies")[1].split("### Drug Repurposing")[0]
    for reason in ("1176 nt", "4.7 kb", "promoter and polyA", "insertion cannot", "PAM and editing window not assessed", "first coding exon"):
        assert reason in part
    assert "Target tissue: liver" not in part and "[E:v1]" in part


def test_review3_a_missing_target_organ_is_unknown_not_inferred():
    a={"section":"bespoke_therapies","modality":"gene_replacement","label":"AAV", "classification":"theoretically_possible",
       "conclusion":"Theoretically possible.","facts":{},"applies_to":["B"],"evidence_ids":[]}
    led=ledger([a]); led["evidence"].append(variant_evidence())
    md,_=build(led); assert "Target tissue: liver" not in md and "theoretically_possible" in md


def test_review3_met_alternative_hides_other_options_but_keeps_common_unknowns():
    rs=[dict(unk("met option"), result="pass",patient_status="satisfies",alternative="A"),
        dict(unk("unused option"),alternative="B"),unk("current medication",field="current medication")]
    a=act("drug:x","existing_targeted_therapies","drug X","conditional",rs)
    assert [r["requirement"] for r in A.unknown_lines(a)]==["current medication"]
    a["requirements"][0].update(result="unknown",patient_status="unknown")
    assert {r["requirement"] for r in A.unknown_lines(a)}=={"met option","unused option","current medication"}


def test_review3_a_met_option_for_one_branch_does_not_hide_another_branchs_unknowns():
    a=act("drug:x","existing_targeted_therapies","drug X","conditional",
          [dict(unk("met B"),result="pass",alternative="A"),
           dict(unk("unknown C"),applies_to=["C"],alternative="Z")],branches=("B","C"))
    assert [r["requirement"] for r in A.unknown_lines(a)]==["unknown C"]


def test_review3_ineffective_drug_cites_the_result_sentence_in_full():
    outcome="After drug X, "+"a long verified clinical observation "*10+"there was no decrease in plasma oxalate."
    a=act("drug:x","off_label_expanded_access","drug X","conditional",evs=("use","out"),efficacy_direction="reported_ineffective",
          precedents=[{"pmid":"1","direction":"negative","outcome_quote":outcome}])
    led=ledger([a]);led["evidence"]=[ev("use","Drug X was administered."),ev("out",outcome)]
    md,_=build(led);part=md.split("### Off-label")[1].split("### Bespoke")[0]
    assert outcome in part and "there was no decrease" in part


def test_review3_repurposing_uses_negative_evidence_even_without_an_action_row():
    led=ledger([]);led["evidence"]=[{"id":"n1","kind":"negative","section":"drug_repurposing","status":"verified",
       "claim":"No candidate for AGXT: 0 drugs returned.","search":{"database":"Open Targets","query":"AGXT",
       "endpoint":"https://example.org/graphql","queried_at":1794736156,"n_results":0,"n_excluded":0}}]
    md,_=build(led);part=md.split("### Drug Repurposing")[1].split("### Outcome")[0]
    assert "Open Targets" in part and "0 results" in part and "AGXT" in part and "No entry" not in part


def test_review3_summary_merges_kidney_function_and_egfr_with_unique_affected_entries():
    missing=[{"variable":"kidney function","affects":["A","B"]},{"variable":"eGFR","affects":["B","C"]},
             {"variable":"age","affects":["A"]}]
    led=ledger([],missing=missing);md,_=build(led);summary=md.split("## Tier 1")[0]
    assert "kidney function: 3 entries" in summary and "  - eGFR:" not in summary
    assert len(led["missing_information"])==3 and missing[0]["affects"]==["A","B"]


def test_review_summary_ranks_concrete_patient_variables_after_excluding_generic_categories():
    missing = [{"variable": v, "affects": [f"action {i}" for i in range(n)]} for v, n in
               [("other", 20), ("diagnosis", 19), ("source scope", 18), ("lab", 17),
                ("kidney function", 4), ("age", 3), ("current medication", 2)]]
    md, _ = build(ledger([], missing=missing))
    summary = md.split("## Tier 1")[0]
    for v in ("kidney function", "age", "current medication"):
        assert f"  - {v}:" in summary
    for v in ("other trial criteria", "diagnosis", "source scope", "lab"):
        assert f"  - {v}:" not in summary


def test_review_summary_does_not_invent_a_patient_variable_for_a_generic_bucket():
    md, _ = build(ledger([], missing=[{"variable": "other", "affects": ["trial"]},
                                     {"variable": "usage situation", "affects": ["procedure"]}]))
    assert "Most important missing information" not in md


def test_review_targeted_drug_cites_the_full_label_indication_before_genereviews():
    indication = ("RIVFLOZA is indicated in children 2 years of age and older and adults with primary hyperoxaluria "
                  "type 1. " + " ".join(f"Indication context {i}." for i in range(10)) + " " + "Relatively preserved kidney function, eGFR ≥30 mL/min/1.73 m2.")
    a = act("drug:1", "existing_targeted_therapies", "nedosiran", "conditional", evs=("g1", "g2", "g3", "f"))
    led = ledger([a])
    led["evidence"] = [ev("g1", "GeneReviews primary advice."), ev("g2", "GeneReviews dose table."),
                       ev("g3", "GeneReviews other table."),
                       ev("f", indication, {"type": "spl_setid", "id": "label1", "brand": "RIVFLOZA", "url": "https://example.org/label"})]
    md, _ = build(led)
    assert md.index(indication) < md.index('"GeneReviews primary advice."')
    assert "eGFR ≥30 mL/min/1.73 m2" in md
    assert '"GeneReviews dose table."' not in md


def test_review_a_targeted_drug_without_a_label_keeps_its_original_citation():
    md, _ = build(ledger([act("drug:1", "existing_targeted_therapies", "drug X", "applicable")]))
    assert '"Drug X for persons with disease D."' in md and "[FDA label" not in md


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
    part=md.split("### Clinical Trial Eligibility")[1].split("### Off-label")[0]
    assert part.count("| **Trial") == 8 and "further trials" not in part
    md, _ = build(ledger([act(f"drug:{i}", "existing_targeted_therapies", f"T{i}", "applicable") for i in range(12)]))
    assert md.split('### Existing Targeted Therapies')[1].split('### Supportive Management')[0].count("- **T") == 12


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
    assert off_part.index("drug Y") < off_part.index("**drug Z** — reported outcome.")
    pre = md[md.index("### Contraindications"):md.index("## Tier 2")]
    assert "drug W" not in pre and "worsened after W" not in pre  # no evidence record for this passage


def test_an_empty_section_says_what_was_searched():
    neg = {"id": "n1", "kind": "negative", "status": "verified", "claim": "c", "search": {"database": "open targets", "query": "target T", "endpoint":"https://example.org/graphql",
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
    rank=r.split("**Ranking**:")[1].split("**Evidence table**")[0]
    assert rank.index("Trial T") < rank.index("drug Y") < rank.index("gene replacement")
    assert "reported_improvement" in r


def test_safety_check_quotes_label_interactions_between_written_drugs():
    labels = {"s1": {"set_id": "s1", "effective_time": "20250101",
                     "drug_interactions": ["Avoid use with drug B. Other text."],
                     "contraindications": ["Hypersensitivity to drug A."]}}
    out = S.check([{"label": "drug A", "names": ["drug A"], "set_ids": ["s1"]},
                   {"label": "drug B", "names": ["drug B"], "set_ids": []}], fetch=labels.get)
    assert out["interactions"][0]["quote"] == "Avoid use with drug B." and out["interactions"][0]["other"] == "drug B"
    assert out["contraindications"][0]["quote"] == "Hypersensitivity to drug A." and not out["contraindications"][0]["none"]
    assert out["not_checked"] == ["drug B"]
    md, _ = build(safety_evidence(ledger([]),out), safety=out)
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
    md, _ = build(safety_evidence(ledger([]),out), safety=out)
    assert "drug A: the label lists no contraindications" in md and '"( 4 )"' not in md


def test_the_supplement_notice_only_for_supplements_and_access_route_is_shown():
    reg_drug = {"fda": {"approved": True}, "supplement": None}
    reg_supp = {"fda": None, "supplement": {"dsld": "x"}}
    md, _ = build(ledger([act("drug:1", "off_label_expanded_access", "approved drug", "conditional",
                              regulatory=reg_drug, access_route_label="FDA-approved drug (off-label use for this disease)"),
                          act("drug:2", "off_label_expanded_access", "herb", "conditional", regulatory=reg_supp)]))
    assert "not an FDA-approved drug" not in md  # no source-backed evidence for the regulatory notice
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
    assert s.index("**Priority actions**") < s.index("**Tier 1:**")
    assert "drug L (applicable)" in s and "If eGFR >= 30: drug N" in s


def test_an_entry_waiting_on_an_unreported_manifestation_ranks_after_the_others():
    led = ledger([act("drug:5", "off_label_expanded_access", "eye drug", "conditional",
                      [unk("choroidal neovascularization", field="manifestation")],
                      efficacy_direction="reported_improvement"),
                  act("trial:1", "clinical_trial_eligibility", "Trial T", "conditional", [unk("a"), unk("b")],
                      study_type="interventional")])
    md, _ = build(led)
    r = md[md.index("**Ranking**"):]
    assert r.index("Trial T") < r.index("eye drug") and "conditional" in r


def test_outcome_measures_come_from_trial_primary_outcomes_and_surveillance():
    led=ledger([])
    led["evidence"] += [ev("out1","Percent change in urinary oxalate (6 months)"), ev("out2","Serum creatinine for eGFR at least annually.")]
    led["report_context"]={"outcomes":[{"kind":"efficacy","label":"NCT00000001 primary outcome","evidence_id":"out1"},
                                     {"kind":"efficacy","label":"GeneReviews NBK1 surveillance","evidence_id":"out2"}]}
    md,_=build(led); om=md.split("**Efficacy measures**:")[1].split("**Ranking**:")[0]
    assert "Percent change in urinary oxalate (6 months)" in om and "[E:out1]" in om
    assert '"Serum creatinine for eGFR at least annually."' in om and "[E:out2]" in om


def test_a_caution_kept_from_the_same_source_is_shown_under_the_entry():
    led=ledger([act("procedure:1","supportive_management","lithotripsy","conditional",[unk("stones")],
                   cautions=["Hard stones are resistant to lithotripsy."])])
    led["evidence"][0]["quote"]="Hard stones are resistant to lithotripsy."
    md,_=build(led)
    assert 'Caution (same source): "Hard stones are resistant to lithotripsy."' in md


def test_no_contraindication_is_one_sentence_without_the_label_fragments():
    safety={"contraindications":[{"drug":"drug A","none":True,"quote":"4 CONTRAINDICATIONS None. ( 4 )",
                                  "set_id":"s1","effective_date":"20250101","url":"u"}]}
    md,_=build(safety_evidence(ledger([]),safety), safety=safety)
    safety_part=md.split("**Safety**:")[1].split("**Efficacy measures**:")[0]
    assert "drug A: the label lists no contraindications" in safety_part and "( 4 )" not in safety_part


def test_safety_outcomes_and_efficacy_outcomes_are_separate():
    led=ledger([])
    led["evidence"] += [ev("out1","Incidence of treatment-emergent adverse events (6 months)"), ev("out2","Percent change in urinary oxalate")]
    led["report_context"]={"outcomes":[{"kind":"safety","label":"NCT1 primary outcome","evidence_id":"out1"},
                                     {"kind":"efficacy","label":"NCT1 primary outcome","evidence_id":"out2"}]}
    md,_=build(led)
    safety=md.split("**Safety**:")[1].split("**Efficacy measures**:")[0]
    efficacy=md.split("**Efficacy measures**:")[1].split("**Ranking**:")[0]
    assert "urinary oxalate" in efficacy and "adverse events" not in efficacy and "adverse events" in safety


def test_a_caution_sentence_is_not_also_cited_as_support():
    led = ledger([act("procedure:1", "supportive_management", "lithotripsy", "conditional", [unk("stones")],
                      evs=("e1", "e2"), cautions=["Hard stones resist it."])])
    led["evidence"].append(ev("e2", quote="Hard stones resist it."))
    md, _ = build(led)
    assert md.count("Hard stones resist it.") == 1 and "Caution (same source)" in md

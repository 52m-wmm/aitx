"""Evidence ledger (step 3.0 contract sections 1, 1.2, 1.3, 8)."""
import pytest

from aitx.evidence import ledger as LG
from aitx.evidence.actions import strategy_key

SRC = "Lumasiran is indicated for the treatment of primary hyperoxaluria type 1 (PH1) to lower urinary and plasma oxalate levels in pediatric and adult patients."
B = [{"id": "b1", "role": "primary"}, {"id": "b2", "role": "ambiguous_2"}]


def drug(key="drug:rxcui:2467140", normalized=True, implements=None):
    a = {"key": key, "normalized": normalized}
    if implements:
        a["implements"] = implements
    return a


def label_ev(section="existing_targeted_therapies", applies=("b1", "b2"), action=None, quote="indicated for the treatment of primary hyperoxaluria type 1"):
    return LG.sourced("Lumasiran is approved for PH1 at all ages.", section, list(applies),
                      {"type": "spl_setid", "id": "16985a31-f5e4-4557-9266-fc78d4bc5055",
                       "url": "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=16985a31-f5e4-4557-9266-fc78d4bc5055"},
                      quote, SRC, 1793700000, action=action or drug())


def check(led, name):
    return next(c for c in led.checks() if c["name"] == name)


def test_sourced_quote_must_be_verbatim():
    assert label_ev()["status"] == "verified"
    bad = label_ev(quote="approved for every disease")
    assert bad["status"] == "rejected" and "verbatim" in bad["reasons"][0]
    # case and whitespace do not matter, wording does
    assert label_ev(quote="INDICATED  for the treatment\nof primary hyperoxaluria")["status"] == "verified"


def test_source_id_format_is_checked():
    e = LG.sourced("x", "background", ["b1"], {"type": "pmid", "id": "PMID:123"}, "Lumasiran", SRC, 1)
    assert e["status"] == "rejected" and "not a valid 'pmid' id" in e["reasons"][0]


def test_ids_are_stable():
    assert label_ev()["id"] == label_ev()["id"]
    assert label_ev()["id"] != label_ev(applies=("b1",))["id"]
    # the same claim from the same source in two sections is two items (otherwise one would overwrite the other)
    assert label_ev()["id"] != label_ev("off_label_expanded_access")["id"]


def test_reasoning_needs_verified_premises():
    led = LG.Ledger("P", B)
    ok = led.add(label_ev())
    bad = led.add(LG.sourced("x", "background", ["b1"], {"type": "pmid", "id": "1"}, "not there", SRC, 1))
    r1 = led.add(LG.reasoning("so it applies", "background", ["b1"], [ok["id"]]))
    r2 = led.add(LG.reasoning("so what", "background", ["b1"], [ok["id"], bad["id"]]))
    r3 = led.add(LG.reasoning("from nothing", "background", ["b1"], []))
    assert (r1["status"], r2["status"], r3["status"]) == ("verified", "rejected", "rejected")


def test_negative_evidence_counts_come_from_the_response():
    ok = LG.negative("clinical_trial_eligibility", ["b1"], database="clinicaltrials.gov", endpoint="https://clinicaltrials.gov/api/v2/studies?query.cond=x",
                     query="SPTLC1", queried_at=1793700000, n_results=0, response_count=0)
    assert ok["status"] == "verified" and ok["search"]["n_results"] == 0
    lie = LG.negative("clinical_trial_eligibility", ["b1"], database="clinicaltrials.gov", endpoint="u",
                      query="SPTLC1", queried_at=1793700000, n_results=0, response_count=3)
    assert lie["status"] == "rejected"
    # found 2, both excluded with reasons -> still a valid 'nothing applicable' record
    found = LG.negative("clinical_trial_eligibility", ["b1"], database="clinicaltrials.gov", endpoint="u", query="q",
                        queried_at=1, n_results=2, response_count=2,
                        excluded=[{"id": "NCT00000001", "reason": "age"}, {"id": "NCT00000002", "reason": "sex"}])
    assert found["status"] == "verified" and found["search"]["n_excluded"] == 2
    partial = LG.negative("clinical_trial_eligibility", ["b1"], database="d", endpoint="u", query="q",
                          queried_at=1, n_results=2, response_count=2, excluded=[{"id": "NCT00000001", "reason": "age"}])
    assert partial["status"] == "rejected"


def test_searched_empty_section_needs_negative_evidence():
    led = LG.Ledger("P", B)
    led.mark_searched("clinical_trial_eligibility")
    assert check(led, "empty_section_has_negative_evidence")["status"] == "fail"
    led.add(LG.negative("clinical_trial_eligibility", ["b1", "b2"], database="clinicaltrials.gov", endpoint="u",
                        query="q", queried_at=1, n_results=0, response_count=0))
    assert check(led, "empty_section_has_negative_evidence")["status"] == "pass"
    # sections not searched yet (all of them in 3.0) are not required to have anything
    assert LG.Ledger("P", B).checks()


def test_case8_same_trial_in_two_sections_fails():
    led = LG.Ledger("P", B)
    t = {"key": "trial:NCT01234567"}
    led.add(label_ev("clinical_trial_eligibility", action=t))
    led.add(LG.sourced("Trial NCT01234567 also lists off-label use", "off_label_expanded_access", ["b1"],
                       {"type": "nct", "id": "NCT01234567"}, "Lumasiran", SRC, 1, action=t))
    assert check(led, "one_action_one_section")["status"] == "fail"


def test_case9_approved_aso_and_bespoke_strategy_clash():
    led = LG.Ledger("P", B)
    ex51 = strategy_key("aso_exon_skipping", "DMD", "exon51")
    led.add(label_ev(action=drug("drug:rxcui:1810569", implements=ex51)))
    led.add(LG.sourced("An exon 51 skipping ASO could be designed", "bespoke_therapies", ["b1"],
                       {"type": "pmid", "id": "1"}, "Lumasiran", SRC, 1, action={"key": ex51}))
    assert check(led, "one_action_one_section")["status"] == "fail"


def test_case13c_fallback_keys_take_part_in_uniqueness():
    led = LG.Ledger("P", B)
    k = drug("drug:name:kaftrio", normalized=False)
    led.add(label_ev(action=k))
    led.add(label_ev("off_label_expanded_access", action=k))
    assert check(led, "one_action_one_section")["status"] == "fail"


def test_case13d_fallback_drug_allowed_but_flagged():
    led = LG.Ledger("P", B)
    e = led.add(label_ev(action=drug("drug:name:kaftrio", normalized=False)))
    assert e["status"] == "verified" and e["id"] in led.to_dict()["sections"]["existing_targeted_therapies"]
    assert check(led, "drug_keys_normalized")["status"] == "warn"


def test_case14_same_action_twice_in_one_section_is_fine():
    led = LG.Ledger("P", B)
    led.add(label_ev())
    led.add(LG.sourced("PH1 guideline recommends lumasiran", "existing_targeted_therapies", ["b1"],
                       {"type": "pmid", "id": "2"}, "Lumasiran", SRC, 1, action=drug()))
    assert check(led, "one_action_one_section")["status"] == "pass"


def test_applies_to_must_name_branches():
    led = LG.Ledger("P", B)
    led.add(label_ev(applies=("b1", "b9")))
    assert check(led, "applies_to_subset_of_branches")["status"] == "fail"


def test_unknown_condition_must_be_listed_as_missing():
    led = LG.Ledger("P", B)
    e = label_ev()
    e["conditions"] = [{"variable": "age_years", "op": ">=", "value": 9, "known": False}]
    led.add(e)
    assert check(led, "unknown_conditions_listed_as_missing")["status"] == "fail"
    led.missing_information.append({"variable": "age_years", "why_it_matters": "label age limit"})
    assert check(led, "unknown_conditions_listed_as_missing")["status"] == "pass"


def test_llm_items_record_model():
    led = LG.Ledger("P", B)
    e = label_ev()
    e["produced_by"] = {"llm": "deepseek-flash"}
    led.add(e)
    assert check(led, "llm_output_records_model")["status"] == "fail"


def test_unknown_section_rejected():
    with pytest.raises(ValueError):
        LG.reasoning("x", "summary", ["b1"], [])


# ------------------------------------------------------ action records (contract 1.4)

NEDO = ("Examplimab is indicated to lower urinary oxalate levels in children 9 years of age and older and adults "
        "with primary hyperoxaluria type 1.")       # fictional label text (real labels are checked in 3a acceptance)
TRIAL = ("Inclusion Criteria: Age 2 to 18 years. Exclusion Criteria: Prior liver transplantation. Estimated GFR below 30.")


def _ev(led, text, quote, key, section="existing_targeted_therapies"):
    return led.add(LG.sourced(quote, section, ["b1", "b2"], {"type": "url", "id": "https://example.org/x", "url": "u"},
                              quote, text, 1, action={"key": key}))


AGE7 = {"field": "age", "value": "7 years", "quote": "7-year-old", "step": 2}


def test_requirement_results_invert_exclusion():
    assert LG.requirement_result("inclusion", "satisfies") == "pass"
    assert LG.requirement_result("label_condition", "does_not_satisfy") == "fail"
    assert LG.requirement_result("exclusion", "satisfies") == "fail"        # meets an exclusion -> not eligible
    assert LG.requirement_result("exclusion", "does_not_satisfy") == "pass"
    assert LG.requirement_result("exclusion", "unknown") == "unknown"
    assert LG.requirement_result("inclusion", "not_assessed") == "not_assessed"
    assert LG.requirement_result("exclusion", "not_assessed") == "not_assessed"


def test_schema_version_v2():
    assert LG.SCHEMA_VERSION == "evidence-ledger-v2"
    assert LG.Ledger("P", B).to_dict()["schema_version"] == "evidence-ledger-v2"


def test_status_from_ignores_not_assessed():
    assert LG.status_from(["pass", "not_assessed"]) == "applicable"
    assert LG.status_from(["not_assessed"]) == "applicable"
    assert LG.status_from(["unknown", "not_assessed"]) == "conditional"
    assert LG.status_from(["fail", "not_assessed"]) == "not_applicable"


def test_administrative_criterion_not_assessed_and_not_missing():
    text = "Inclusion Criteria: Age 2 to 18 years. Signed informed consent."
    led = LG.Ledger("P", B)
    ev = _ev(led, text, text, "trial:NCT01234567", "clinical_trial_eligibility")
    reqs = [LG.requirement("inc1", "inclusion", "Age 2 to 18 years", ev["id"], AGE7, "satisfies", ["b1"]),
            LG.requirement("inc2", "inclusion", "Signed informed consent", ev["id"], None, "not_assessed", ["b1"],
                           note=LG.NOT_ASSESSED_NOTE)]
    a = LG.action_record("trial:NCT01234567", "clinical_trial_eligibility", "Trial X", ["b1"], reqs, [ev["id"]],
                         {"b1": "age criterion met"})
    led.actions.append(a)
    assert a["status_by_branch"]["b1"]["status"] == "applicable"
    assert check(led, "action_records_consistent")["status"] == "pass"     # not required in missing_information
    assert led.missing_information == []


def test_not_assessed_misuse_is_caught():
    text = "Inclusion Criteria: Signed informed consent."
    for kind, note, fact in (("label_condition", LG.NOT_ASSESSED_NOTE, None),   # only trial criteria
                             ("inclusion", "", None),                           # must be noted
                             ("inclusion", LG.NOT_ASSESSED_NOTE, AGE7)):        # no patient fact
        led = LG.Ledger("P", B)
        ev = _ev(led, text, text, "trial:NCT01234567", "clinical_trial_eligibility")
        req = LG.requirement("inc1", kind, "Signed informed consent", ev["id"], fact, "not_assessed", ["b1"], note=note)
        led.actions.append(LG.action_record("trial:NCT01234567", "clinical_trial_eligibility", "Trial X", ["b1"], [req],
                                            [ev["id"]], {"b1": "x"}))
        assert "not_assessed must be" in check(led, "action_records_consistent")["detail"], kind


def test_label_age_limit_makes_action_not_applicable():
    led = LG.Ledger("P", B)
    ev = _ev(led, NEDO, "children 9 years of age and older", "drug:rxcui:2675287")
    req = LG.requirement("r1", "label_condition", "9 years of age and older", ev["id"], AGE7, "does_not_satisfy", ["b1", "b2"])
    a = LG.action_record("drug:rxcui:2675287", "existing_targeted_therapies", "Examplimab", ["b1", "b2"], [req], [ev["id"]],
                         {"b1": "approved only for age ≥ 9", "b2": "approved only for age ≥ 9"})
    led.actions.append(a)
    assert a["status_by_branch"]["b1"]["status"] == "not_applicable"
    assert check(led, "action_records_consistent")["status"] == "pass"


def test_trial_criteria_line_by_line_and_unknown_is_conditional():
    led = LG.Ledger("P", B)
    ev = _ev(led, TRIAL, "Inclusion Criteria: Age 2 to 18 years. Exclusion Criteria: Prior liver transplantation. Estimated GFR below 30.",
             "trial:NCT01234567", "clinical_trial_eligibility")
    reqs = [LG.requirement("inc1", "inclusion", "Age 2 to 18 years", ev["id"], AGE7, "satisfies", ["b1", "b2"]),
            LG.requirement("exc1", "exclusion", "Prior liver transplantation", ev["id"], None, "unknown", ["b1", "b2"]),
            LG.requirement("exc2", "exclusion", "Estimated GFR below 30", ev["id"], None, "unknown", ["b1"])]
    a = LG.action_record("trial:NCT01234567", "clinical_trial_eligibility", "Trial X", ["b1", "b2"], reqs, [ev["id"]],
                         {"b1": "eligible if no prior transplant and eGFR ≥ 30", "b2": "eligible if no prior transplant"})
    led.actions.append(a)
    assert [a["status_by_branch"][b]["status"] for b in ("b1", "b2")] == ["conditional", "conditional"]
    # unknown facts must be listed as missing information
    assert check(led, "action_records_consistent")["status"] == "fail"
    led.missing_information.append({"variable": "exc1", "why_it_matters": "trial exclusion"})
    led.missing_information.append({"variable": "exc2", "why_it_matters": "trial exclusion"})
    assert check(led, "action_records_consistent")["status"] == "pass"


def test_status_can_differ_between_branches():
    led = LG.Ledger("P", B)
    ev = _ev(led, NEDO, "with primary hyperoxaluria type 1", "drug:rxcui:2675287")
    req = LG.requirement("r1", "label_condition", "with primary hyperoxaluria type 1", ev["id"],
                         {"field": "diagnosis", "value": "PH1", "quote": "PH1", "step": 2}, "satisfies", ["b1"])
    req2 = LG.requirement("r2", "label_condition", "with primary hyperoxaluria type 1", ev["id"],
                          {"field": "diagnosis", "value": "PH2", "quote": "PH2", "step": 2}, "does_not_satisfy", ["b2"])
    a = LG.action_record("drug:rxcui:2675287", "existing_targeted_therapies", "Examplimab", ["b1", "b2"], [req, req2],
                         [ev["id"]], {"b1": "labelled for PH1", "b2": "not labelled for PH2"})
    assert (a["status_by_branch"]["b1"]["status"], a["status_by_branch"]["b2"]["status"]) == ("applicable", "not_applicable")


def test_requirement_must_be_verbatim_and_result_untampered():
    led = LG.Ledger("P", B)
    ev = _ev(led, NEDO, "children 9 years of age and older", "drug:rxcui:2675287")
    req = LG.requirement("r1", "label_condition", "patients aged 12 and over", ev["id"], AGE7, "does_not_satisfy", ["b1"])
    led.actions.append(LG.action_record("drug:rxcui:2675287", "existing_targeted_therapies", "Examplimab", ["b1"], [req],
                                        [ev["id"]], {"b1": "age"}))
    assert "not verbatim" in check(led, "action_records_consistent")["detail"]
    led2 = LG.Ledger("P", B)
    ev2 = _ev(led2, NEDO, "children 9 years of age and older", "drug:rxcui:2675287")
    req2 = LG.requirement("r1", "label_condition", "9 years of age and older", ev2["id"], AGE7, "does_not_satisfy", ["b1"])
    a = LG.action_record("drug:rxcui:2675287", "existing_targeted_therapies", "Examplimab", ["b1"], [req2], [ev2["id"]], {"b1": "age"})
    a["status_by_branch"]["b1"]["status"] = "applicable"                     # hand-set status against its requirements
    led2.actions.append(a)
    assert "does not follow" in check(led2, "action_records_consistent")["detail"]


def test_searched_none_row_needs_negative_evidence():
    led = LG.Ledger("P", B)
    neg = led.add(LG.negative("clinical_trial_eligibility", ["b1", "b2"], database="clinicaltrials.gov", endpoint="u",
                              query="SPTLC1", queried_at=1, n_results=0, response_count=0))
    led.actions.append(LG.action_record(None, "clinical_trial_eligibility", "No recruiting trials", ["b1", "b2"], [],
                                        [neg["id"]], {"b1": "none found", "b2": "none found"}, searched_none=True))
    assert check(led, "action_records_consistent")["status"] == "pass"
    led.actions.append(LG.action_record(None, "drug_repurposing", "None", ["b1"], [], [], {"b1": "x"}, searched_none=True))
    assert check(led, "action_records_consistent")["status"] == "fail"

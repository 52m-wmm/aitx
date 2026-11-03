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

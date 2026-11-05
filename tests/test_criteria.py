"""3b criterion mapping: verification, code comparison, groups, trial records (offline; LLM and search stubbed)."""
import pytest

from aitx.evidence import criteria as C
from aitx.evidence import labs as LABS
from aitx.evidence import ledger as LG
from aitx.evidence import patient_facts as PFX
from aitx.evidence import trial_records as TR
from aitx.evidence import trials as T

ITEMS = {"inc1": {"id": "inc1", "kind": "inclusion", "text": "Age ≥ 2 years", "parent": None},
         "inc2": {"id": "inc2", "kind": "inclusion", "text": "Estimated GFR \\>30 mL/min/1.73m2", "parent": None},
         "exc1": {"id": "exc1", "kind": "exclusion", "text": "Hemoglobin \\< 7 mg/dL", "parent": None}}


@pytest.mark.parametrize("m,why", [
    ({"id": "inc1", "quote": "Age ≥ 2 years", "fact": "age", "op": ">=", "value": 2, "unit": "years"}, None),
    ({"id": "inc1", "quote": "Age ≥ 2 years", "fact": "age", "op": ">", "value": 2}, "comparison '>' not as written"),
    ({"id": "inc1", "quote": "Age ≥ 2 years", "fact": "age", "op": ">=", "value": 12}, "threshold 12 not in the quote"),
    ({"id": "inc1", "quote": "Age ≥ 12 years", "fact": "age", "op": ">=", "value": 12}, "quote not verbatim in the criterion"),
    ({"id": "inc2", "quote": "Estimated GFR >30 mL/min/1.73m2", "fact": "egfr", "op": ">", "value": 30}, None),
    ({"id": "inc2", "quote": "Estimated GFR >30 mL/min/1.73m2", "fact": "egfr", "op": ">=", "value": 30}, "comparison '>=' not as written"),
    ({"id": "exc1", "quote": "Hemoglobin < 7 mg/dL", "fact": "lab", "op": "<", "value": 7, "unit": "g/dL", "name": "hemoglobin"},
     "unit not in the quote"),                                     # "g/dL" is not the unit written ("mg/dL")
    ({"id": "exc1", "quote": "Hemoglobin < 7 mg/dL", "fact": "lab", "op": "<", "value": 7, "unit": "mg/dL", "name": "hemoglobin"}, None),
    ({"id": "exc9", "quote": "x", "fact": "lab"}, "unknown criterion id"),
    ({"id": "inc1", "quote": "Age ≥ 2 years", "fact": "mood"}, "unknown fact type 'mood'"),
])
def test_check_mapping(m, why):
    assert C.check_mapping(m, ITEMS) == why


def test_sign_cues():
    assert C.sign_ok(">=", "aged 6 years or older") and not C.sign_ok(">", "aged 6 years or older")
    assert C.sign_ok("<", "Hemoglobin < 7") and not C.sign_ok("<=", "Hemoglobin < 7")
    assert C.sign_ok("<=", "≤ 64 years") and C.sign_ok(">", "older than 6 years")


PF = {"age_months": 2, "age_quote": "Age 2 months", "sex": None, "sex_quote": None,
      "variants": [{"gene": "SLC35A2", "protein": "p.Met1Ile", "class": "start_lost", "zygosity": "heterozygous",
                    "quote": "SLC35A2 c.3G>A p.Met1Ile (heterozygous)"}], "present": [], "excluded": []}
BR = {"id": "b1", "gene": "SLC35A2", "diagnosis": {"label": "SLC35A2-CDG"}}
TEXT = "seizures and global developmental delay. Age 2 months, Hemoglobin 5, Normal liver labs, Not enrolled in other trials"


@pytest.fixture
def extra():
    kept, _ = PFX.verify([{"kind": "lab", "name": "Hemoglobin", "value": 5, "unit": "", "quote": "Hemoglobin 5"},
                          {"kind": "organ_function", "name": "liver", "status": "normal", "quote": "Normal liver labs"},
                          {"kind": "other_trial", "name": "other trials", "status": "absent", "quote": "Not enrolled in other trials"}],
                         TEXT, LABS.load())
    return {"facts": kept}


def test_hemoglobin_without_unit_is_unknown_with_both_scenarios(extra):
    m = {"quote": "Hemoglobin < 7 mg/dL", "fact": "lab", "op": "<", "value": 7, "unit": "mg/dL", "name": "hemoglobin"}
    st, fact, note, det = C.evaluate(m, PF, extra, BR, ["SLC35A2-CDG"])
    assert st == "unknown" and "interpreted as 7 g/dL" in note                  # registry unit slip read in g/dL, written out
    sc = {s["unit"]: s["result"] for s in det["lab"]["scenarios"]}
    assert sc["g/dL"] == "satisfies"                                            # 5 g/dL < 7: meets the exclusion
    assert "mmol/L" in sc                                                       # factor pending -> unknown, never assumed


def test_stated_normal_absent_and_unmentioned(extra):
    liver = {"quote": "Adequate hepatic function", "fact": "organ_function", "name": "normal", "op": "", "value": ""}
    assert C.evaluate(liver, PF, extra, BR, [])[0] == "satisfies"
    trial = {"quote": "Participation in another interventional trial", "fact": "other_trial", "op": "", "value": ""}
    assert C.evaluate(trial, PF, extra, BR, [])[0] == "does_not_satisfy"        # exclusion not met -> pass
    med = {"quote": "Current use of valproate", "fact": "current_medication", "name": "valproate", "op": "", "value": ""}
    st, fact, _, _ = C.evaluate(med, PF, extra, BR, [])
    assert st == "unknown" and fact["field"].startswith("current medication")   # not mentioned -> unknown, never "none"
    kidney = {"quote": "Adequate renal function", "fact": "organ_function", "name": "normal", "op": "", "value": ""}
    assert C.evaluate(kidney, PF, extra, BR, [])[0] == "unknown"


def test_egfr_never_derived_without_all_inputs(extra):
    m = {"quote": "eGFR > 30", "fact": "egfr", "op": ">", "value": 30}
    st, fact, note, _ = C.evaluate(m, PF, extra, BR, [])
    assert st == "unknown" and "creatinine" in note


def test_administrative_and_contraception_for_an_infant(extra):
    assert C.evaluate({"quote": "Parent able to provide consent", "fact": "administrative"}, PF, extra, BR, [])[0] == "not_assessed"
    pf = dict(PF, sex="male")
    st, _, note, _ = C.evaluate({"quote": "must use contraception", "fact": "pregnancy", "name": "contraception"}, pf, extra, BR, [])
    assert st == "satisfies"


def _mapped(items, mappings):
    return {"items": items, "mappings": mappings, "rejected": [], "produced_by": "code"}


def test_one_of_the_following_any_option_met():
    items = [{"id": "inc1", "kind": "inclusion", "text": "Meet one of the following:", "level": 0, "parent": None},
             {"id": "inc2", "kind": "inclusion", "text": "Genetic diagnosis of SLC35A2-CDG", "level": 1, "parent": "inc1"},
             {"id": "inc3", "kind": "inclusion", "text": "Weight above 5 kg", "level": 1, "parent": "inc1"}]
    ms = [{"id": "inc2", "quote": "Genetic diagnosis of SLC35A2-CDG", "fact": "genetic_confirmation", "group": "inc1"},
          {"id": "inc3", "quote": "Weight above 5 kg", "fact": "weight", "op": ">", "value": 5, "group": "inc1"}]
    lines = C.lines_for({"nct": "NCT00000001"}, _mapped(items, ms), PF, {"facts": []}, BR, ["SLC35A2-CDG"])
    assert len(lines) == 1 and lines[0]["patient_status"] == "satisfies" and len(lines[0]["any_of"]) == 2


def test_group_ignored_unless_the_parent_says_one_of(monkeypatch):
    items_text = "Inclusion Criteria:\n* Adequate organ function:\n  * Weight above 5 kg\n  * Genetic diagnosis of SLC35A2-CDG\n"
    monkeypatch.setattr(C, "_llm", lambda *a, **k: ({"criteria": [
        {"id": "inc2", "quote": "Weight above 5 kg", "fact": "weight", "op": ">", "value": 5, "group": "inc1"},
        {"id": "inc3", "quote": "Genetic diagnosis of SLC35A2-CDG", "fact": "genetic_confirmation", "group": "inc1"}]}, {}))
    mp = C.map_study({"nct": "NCT00000001", "criteria": items_text})
    assert all(m["group"] == "" and m["group_ignored"] == "inc1" for m in mp["mappings"])


def test_unmapped_criterion_is_not_assessed_and_shown_verbatim():
    items = [{"id": "exc1", "kind": "exclusion", "text": "Any condition that in the opinion of the investigator interferes", "level": 0,
              "parent": None}]
    lines = C.lines_for({"nct": "NCT00000001"}, _mapped(items, []), PF, {"facts": []}, BR, [])
    assert lines[0]["patient_status"] == "not_assessed" and lines[0]["note"] == LG.UNMAPPED_NOTE
    assert lines[0]["text"] == items[0]["text"]


# --- trial records end to end (search and LLM stubbed)

STUDY = {"nct": "NCT05402384", "title": "AVTX-801 in SLC35A2-CDG", "acronym": "AVTX-801", "status": "NOT_YET_RECRUITING",
         "study_type": "interventional", "phases": ["PHASE2"], "conditions": ["SLC35A2-CDG"], "keywords": [],
         "min_age": "1 Month", "max_age": None, "sex": "ALL", "healthy_volunteers": False, "last_update": "2026-01-01",
         "criteria": "Inclusion Criteria:\n* Genetic diagnosis of SLC35A2-CDG\n* Parent able to give informed consent\n\n"
                     "Exclusion Criteria:\n* Hemoglobin \\< 7 mg/dL\n* Any condition the investigator considers unsafe\n"}


def _plan(study, how="analysed"):
    pre = T.prefilter(study, PF["age_months"], PF["sex"])
    st = {**study, "relevance": {"by": "disease"}, "prefilter": pre, "specific": True}
    return {"names": ["SLC35A2-CDG"], "gene": "SLC35A2", "n_unique": 3,
            "searches": [{"query": {"query.cond": "SLC35A2-CDG"}, "queried_at": 1, "total_count": 3, "url": "u"}],
            "analysed": [st] if how == "analysed" else [], "ineligible": [st] if how == "ineligible" else [],
            "over_cap": [], "n_closed_relevant": 1, "closed_listed": ["NCT05345171"],
            "excluded": [{"nct": "NCT05345171", "reason": "status", "detail": "overall status ACTIVE_NOT_RECRUITING"},
                         {"nct": "NCT09999999", "reason": "relevance", "detail": "no Condition names the disease"}]}


def _run(monkeypatch, plan, extra_facts):
    monkeypatch.setattr(T, "plan_branch", lambda *a, **k: plan)
    monkeypatch.setattr(C, "_llm", lambda *a, **k: ({"criteria": [
        {"id": "inc1", "quote": "Genetic diagnosis of SLC35A2-CDG", "fact": "genetic_confirmation"},
        {"id": "inc2", "quote": "Parent able to give informed consent", "fact": "administrative"},
        {"id": "exc1", "quote": "Hemoglobin < 7 mg/dL", "fact": "lab", "op": "<", "value": 7, "unit": "mg/dL", "name": "hemoglobin"}]},
        {"llm": "m", "served_model": "m", "prompt_version": C.PROMPT_VERSION}))
    monkeypatch.setattr(TR.E, "disease_names", lambda b, s2: ["SLC35A2-CDG"])
    monkeypatch.setattr(TR.E, "facts", lambda s1, s2: PF)
    led = LG.Ledger("P", [BR])
    led.patient_context["extra_facts"] = extra_facts
    TR.add_trials(led, {"patient": {"clinical_context": TEXT}}, {}, {})
    return led


def test_trial_record_conditional_with_lab_unknown_and_verbatim_evidence(monkeypatch, extra):
    led = _run(monkeypatch, _plan(STUDY), extra)
    rec = next(a for a in led.actions if a["action_key"] == "trial:NCT05402384")
    assert rec["status_by_branch"]["b1"]["status"] == "conditional"
    res = {l["requirement"]: l["result"] for l in rec["requirements"]}
    assert res["minimumAge: 1 Month; maximumAge: none"] == "pass"
    assert res["Genetic diagnosis of SLC35A2-CDG"] == "pass"
    assert res["Parent able to give informed consent"] == "not_assessed"
    assert res["Hemoglobin < 7 mg/dL"] == "unknown"
    assert res["Any condition the investigator considers unsafe"] == "not_assessed"       # unmapped, shown verbatim
    assert "hemoglobin" in {m["variable"] for m in led.missing_information}
    bad = [c for c in led.checks() if c["status"] == "fail"]
    assert not bad, bad
    ts = led.trial_searches["b1"]
    assert "NCT05345171" in ts["closed_listed"] and ts["analysed"] == ["NCT05402384"]


def test_registry_age_rules_out_without_llm(monkeypatch, extra):
    older = {**STUDY, "nct": "NCT06488313", "min_age": "12 Years"}
    led = _run(monkeypatch, _plan(older, "ineligible"), extra)
    rec = next(a for a in led.actions if a["action_key"] == "trial:NCT06488313")
    assert rec["status_by_branch"]["b1"]["status"] == "not_applicable" and rec["analysed_in"] == []


def test_branch_without_trials_gets_negative_evidence(monkeypatch, extra):
    plan = _plan(STUDY)
    plan.update(analysed=[], n_unique=2)
    led = _run(monkeypatch, plan, extra)
    none = [a for a in led.actions if a["section"] == "clinical_trial_eligibility"]
    assert len(none) == 1 and none[0]["status_by_branch"]["b1"]["status"] == "searched_none"
    neg = led.evidence[none[0]["evidence_ids"][0]]
    assert neg["status"] == "verified" and neg["search"]["n_excluded"] == 2


def test_any_sex_is_met_when_sex_is_unknown_and_unknown_age_names_its_variable(extra):
    # 2026-11-04 run: "Male or Female" was unknown, and unknown age / sex lines had no variable for missing information
    assert C.evaluate({"quote": "Male or Female", "fact": "sex", "value": ["male", "female"]}, PF, extra, BR, [])[0] == "satisfies"
    assert C.evaluate({"quote": "Female", "fact": "sex", "value": "female"}, PF, extra, BR, [])[0] == "unknown"
    st, fact, _, _ = C.evaluate({"quote": "Female", "fact": "sex", "value": "female"}, dict(PF, sex=None), extra, BR, [])
    assert st == "unknown" and fact["field"] == "sex"


# --- 2026-11-04 run: false "not applicable" verdicts (regressions)

BOY = dict(PF, age_months=84, age_quote="7-year-old", sex="male", sex_quote="boy")


@pytest.mark.parametrize("kind,quote,name,want", [
    ("exclusion", "Unwilling to comply with contraceptive requirements", "contraception", "does_not_satisfy"),
    ("inclusion", "Pubescent and adult female patients must have a negative pregnancy test", "", "satisfies"),
    ("exclusion", "Pregnant or breastfeeding", "", "does_not_satisfy"),
    ("inclusion", "Agree to use contraception", "contraception", "satisfies"),
])
def test_pregnancy_criteria_never_rule_out_a_boy(kind, quote, name, want, extra):
    st, _, _, _ = C.evaluate({"quote": quote, "fact": "pregnancy", "name": name}, BOY, extra, BR, [], kind)
    assert st == want
    line = LG.requirement("r1", kind, quote, "e", {"field": "sex", "value": "male", "quote": "boy", "step": 2}, st, ["b1"])
    assert line["result"] == "pass"


@pytest.mark.parametrize("quote", ["All genders", "males and females", "Male or Female", "regardless of gender", "both sexes"])
def test_any_sex_wordings(quote, extra):
    assert C.evaluate({"quote": quote, "fact": "sex"}, BOY, extra, BR, [])[0] == "satisfies"


def test_text_age_clauses_are_left_to_the_registry_fields(extra):
    # NCT04580420: cohorts ">= 12", "6 to 11", "2 to 5" had failed a 7-year-old one by one
    st, fact, note, _ = C.evaluate({"quote": "adults and adolescents (aged ≥ 12 years)", "fact": "age", "op": ">=", "value": 12},
                                   BOY, extra, BR, [])
    assert st == "not_assessed" and fact is None and note == LG.AGE_BY_REGISTRY_NOTE


def test_branch_disease_named_in_an_exclusion_is_context(extra):
    cf = {"id": "b1", "gene": "CFTR", "diagnosis": {"label": "cystic fibrosis"}}
    for q in ("Chronic lung or liver or pancreatic disease not related to cystic fibrosis",
              "Cystic fibrosis pulmonary exacerbation requiring hospitalization"):
        assert C.evaluate({"quote": q, "fact": "diagnosis"}, BOY, extra, cf, ["cystic fibrosis", "CF"], "exclusion")[0] == "unknown"
    assert C.evaluate({"quote": "Diagnosis of cystic fibrosis", "fact": "diagnosis"}, BOY, extra, cf,
                      ["cystic fibrosis", "CF"], "inclusion")[0] == "satisfies"
    assert C.evaluate({"quote": "Diagnosis of CF", "fact": "diagnosis"}, BOY, extra, cf, ["cystic fibrosis", "CF"])[0] == "unknown"


def test_ranges_and_and_older_are_sign_cues():
    assert C.sign_ok(">=", "Patients aged 10 to 17 years") and C.sign_ok("<=", "Patients aged 10 to 17 years")
    assert C.sign_ok("<=", "Age 0-90 years old") and C.sign_ok(">=", "Aged 12 years and above")
    assert not C.sign_ok(">", "Aged 12 years and above")


def test_thousands_separator_and_none_item():
    items = {"exc1": {"id": "exc1", "kind": "exclusion", "text": "Severe thrombocytopenia (platelet count ≤ 100,000/µL)", "parent": None}}
    assert C.check_mapping({"id": "exc1", "quote": "platelet count ≤ 100,000/µL", "fact": "lab", "op": "<=", "value": 100000}, items) is None
    none = [{"id": "exc1", "kind": "exclusion", "text": "None", "level": 0, "parent": None}]
    assert C.lines_for({"nct": "NCT00000001"}, _mapped(none, []), PF, {"facts": []}, BR, []) == []

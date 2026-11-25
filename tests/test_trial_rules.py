"""Current deterministic guards, retained unchanged from old regressions."""
import pytest
from aitx.step3.b import rules as C

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



def test_ranges_and_and_older_are_sign_cues():
    assert C.sign_ok(">=", "Patients aged 10 to 17 years") and C.sign_ok("<=", "Patients aged 10 to 17 years")
    assert C.sign_ok("<=", "Age 0-90 years old") and C.sign_ok(">=", "Aged 12 years and above")
    assert not C.sign_ok(">", "Aged 12 years and above")



def test_a_healthy_only_study_quotes_the_patients_variant():
    # 2026-11-13: RETEST-PFN1 NCT04667013 (conditions: Healthy) failed the ledger check - no quoted patient fact
    from aitx.step3.b import rules as CR
    study = {"healthy_volunteers": True, "conditions": ["Healthy"], "min_age": None, "max_age": None, "sex": "ALL"}
    pf = {"age_months": None, "age_quote": None, "sex": None, "sex_quote": None,
          "variants": [{"gene": "PFN1", "quote": "PFN1 c.211T>G p.Cys71Gly (heterozygous)"}]}
    (line,) = [l for l in CR.registry_lines(study, pf) if l["item"] == "registry:healthy_volunteers"]
    assert line["patient_status"] == "does_not_satisfy" and line["patient_fact"]["quote"].startswith("PFN1")



def test_confirmed_requires_resolved_primary_gene_and_a_pathogenic_record():
    from aitx.step3.b import rules as TR
    s1 = {"variants": [{"gene": "AGXT"}]}
    s2 = {"primary": {"status": "resolved", "id": "MONDO:0009823"},
          "clinvar": [{"records": [{"used_for_ranking": True, "clinical_significance": "Pathogenic"}]}]}
    b = {"id": "MONDO:0009823", "gene": "AGXT"}
    assert TR.confirmed(b, s1, s2)
    assert not TR.confirmed(b, s1, dict(s2, primary={"status": "ambiguous", "id": "MONDO:0009823"}))
    assert not TR.confirmed(dict(b, gene="GRHPR"), s1, s2)
    assert not TR.confirmed(b, s1, dict(s2, clinvar=[{"records": [{"used_for_ranking": True,
                                                                    "clinical_significance": "Uncertain significance"}]}]))

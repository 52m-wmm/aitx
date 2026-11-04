"""Step 3a: code-side comparisons (contract docs/step3a_contract.md). Offline."""
import pytest

from aitx.evidence import established as E
from aitx.evidence import variants as V

PF = {"age_months": 84, "age_quote": "7-year-old", "sex": "male", "sex_quote": "boy",
      "variants": [{"gene": "AGXT", "protein": "p.(Lys12GlnfsTer156)", "class": "frameshift", "zygosity": "homozygous",
                    "quote": "AGXT c.33dup"}], "present": [], "excluded": []}
BR = {"id": "M:PH1", "gene": "AGXT", "diagnosis": {"label": "primary hyperoxaluria type 1"}, "synonyms": ["PH1"]}


@pytest.mark.parametrize("op,value,unit,want", [
    (">=", 2, "year", "satisfies"),          # Rivfloza: "children 2 years of age and older"
    (">=", 9, "year", "does_not_satisfy"),
    ("<", 18, "year", "satisfies"),
    (">=", 6, "month", "satisfies"),
])
def test_age_requirements(op, value, unit, want):
    st, fact, _ = E.evaluate({"field": "age", "op": op, "value": value, "unit": unit, "text": "x"}, PF, BR)
    assert st == want and fact["quote"] == "7-year-old"


def test_unknown_age_and_lab_values_are_unknown():
    pf = dict(PF, age_months=None)
    assert E.evaluate({"field": "age", "op": ">=", "value": 2, "unit": "year", "text": "x"}, pf, BR)[0] == "unknown"
    assert E.evaluate({"field": "kidney_function", "op": ">=", "value": 30, "text": "eGFR ≥30"}, PF, BR)[0] == "unknown"


def test_variant_class_requirement_frameshift_is_not_missense():
    # GeneReviews PH1 table 7: pyridoxine for "Persons w/missense AGXT variants"
    st, _, _ = E.evaluate({"field": "variant_class", "op": "in", "value": ["missense"], "text": "missense AGXT variants"}, PF, BR)
    assert st == "does_not_satisfy"
    pf = dict(PF, variants=[dict(PF["variants"][0], protein="p.(Gly170Arg)", **{"class": "missense"})])
    assert E.evaluate({"field": "variant_class", "op": "in", "value": ["missense"], "text": "missense"}, pf, BR)[0] == "satisfies"


def test_variant_named_in_label_text():
    pf = dict(PF, variants=[{"gene": "CFTR", "protein": "p.Phe508del", "class": "inframe_deletion",
                             "zygosity": "homozygous", "quote": "CFTR c.1521_1523del"}])
    br = dict(BR, gene="CFTR")
    req = {"field": "variant", "text": "at least one variant ... responsive (see Table 6)",
           "_label_text": "Table 6: CFTR Gene Mutations Responsive: ... F508del ... G551D"}
    st, _, note = E.evaluate(req, pf, br)
    assert st == "satisfies" and "F508del" in note
    req["_label_text"] = "Table 6: G551D R117H"
    assert E.evaluate(req, pf, br)[0] == "unknown"           # not listed -> unknown, never a guess


def test_diagnosis_requirement_by_name_or_synonym():
    assert E.evaluate({"field": "diagnosis", "text": "patients with PH1 and preserved kidney function"}, PF, BR)[0] == "satisfies"


@pytest.mark.parametrize("protein,text,hit", [
    ("p.Phe508del", "homozygous for the F508del mutation", "F508del"),
    ("p.(Gly170Arg)", "esp homozygotes for p.Phe152Ile, p.Gly170Arg, & p.Ile244Thr", "p.Gly170Arg"),
    ("p.Gly170Arg", "G170R carriers", "G170R"),
    ("p.Gly170Arg", "G170RX", None),
])
def test_variant_aliases(protein, text, hit):
    assert V.mentioned(protein, text) == hit


@pytest.mark.parametrize("sex,age_months,want", [
    ("male", 300, "does_not_satisfy"),          # male -> not applicable
    ("female", 84, "does_not_satisfy"),         # under 12 -> not applicable
    ("unknown", 84, "does_not_satisfy"),
    ("female", 180, "unknown"),                 # female 12 or older -> conditional (pregnancy status unknown)
    ("unknown", 200, "unknown"),                # sex unknown and older than 12 -> conditional
    ("unknown", None, "unknown"),
])
def test_pregnancy_items(sex, age_months, want):
    st, fact = E.pregnancy_status(dict(PF, sex=sex, age_months=age_months))
    assert st == want and (fact["field"] == "pregnancy status") == (want == "unknown")


def test_requirements_keep_only_patient_fields():
    raw = [{"text": "children 2 years of age and older", "field": "age", "op": ">=", "value": 2, "unit": "year"},
           {"text": "throughout pregnancy", "field": "other"},
           {"text": "not in the quote", "field": "age", "op": ">=", "value": 2}]
    got = E._reqs(raw, None, "indicated in children 2 years of age and older and adults")
    assert [r["text"] for r in got] == ["children 2 years of age and older"]


# ------------------------------------------------ label matching, one section per action, dedupe, merged lines

from aitx.evidence import ledger as LG  # noqa: E402


def label(generic, indication):
    return {"generic": generic, "sections": {"indications_and_usage": indication}}


def test_generic_label_must_be_the_drug_and_name_the_disease():
    names = ["primary hyperoxaluria type 1", "PH1"]
    assert E.label_matches_drug(label("LUMASIRAN", "treatment of primary hyperoxaluria type 1 (PH1)"), "lumasiran", names) \
        == "primary hyperoxaluria type 1"
    # a prenatal multivitamin that contains pyridoxine is not the pyridoxine label
    multi = label("ALPHA-TOCOPHEROL, ASCORBIC ACID, PYRIDOXINE, FOLIC ACID", "nutritional supplement in pregnancy")
    assert E.label_matches_drug(multi, "pyridoxine", names) is None
    # pyridoxine alone, but not labelled for PH1: not used
    assert E.label_matches_drug(label("PYRIDOXINE HYDROCHLORIDE", "vitamin B6 deficiency"), "pyridoxine", names) is None


def _found(section, *, reqs=(), specs=None, pregnancy=False, label="pyridoxine", key="drug:rxcui:684879"):
    text = "Pyridoxine (vitamin B6) for persons w/missense AGXT variants. Also given throughout pregnancy."
    src = {"type": "nbk", "id": "NBK1283", "url": "u", "section": "Management / x", "credit": "c"}
    spec = E._spec("GeneReviews lists pyridoxine", src, "Pyridoxine (vitamin B6) for persons w/missense AGXT variants.",
                   text, 1)
    return {key: {"key": {"key": key, "normalized": True}, "section": section, "label": label, "branches": {"b1"},
                  "specs": specs or [spec], "reqs": [dict(r, spec=spec) for r in reqs], "why": "Management / x",
                  "pregnancy_only": pregnancy}}


PF_FS = dict(PF)


def test_evidence_created_in_the_actions_final_section():
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("existing_targeted_therapies"), PF_FS, [])
    ev = [e for e in led.evidence.values() if (e.get("action") or {}).get("key") == "drug:rxcui:684879"]
    assert ev and all(e["section"] == "existing_targeted_therapies" for e in ev)
    assert next(c for c in led.checks() if c["name"] == "one_action_one_section")["status"] == "pass"


def test_duplicate_requirements_kept_once_and_frameshift_fails_missense():
    r = {"kind": "label_condition", "text": "missense AGXT variants", "field": "variant_class", "op": "in", "value": ["missense"]}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("existing_targeted_therapies", reqs=[r, dict(r)]), PF_FS, [])
    a = next(a for a in led.actions if a["action_key"] == "drug:rxcui:684879")
    assert len(a["requirements"]) == 1 and a["status_by_branch"]["b1"]["status"] == "not_applicable"


def test_unreported_manifestations_merged_into_one_missing_line(monkeypatch):
    monkeypatch.setattr(E, "manifestation_status", lambda text, pf: ("unknown", None))
    reqs = [{"kind": "other", "text": "stones", "field": "manifestation"},
            {"kind": "other", "text": "oxalosis", "field": "manifestation"}]
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("supportive_management", reqs=reqs, key="procedure:ureteroscopy", label="ureteroscopy")
    found["procedure:ureteroscopy"]["specs"][0]["quote"] = "Pyridoxine (vitamin B6)"
    E._records(led, found, PF_FS, [])
    rows = [m for m in led.missing_information if m["variable"] == E.MISSING_MANIFESTATIONS]
    assert len(rows) == 1 and "stones; oxalosis" in rows[0]["why_it_matters"]
    a = next(a for a in led.actions if a["action_key"] == "procedure:ureteroscopy")
    assert a["status_by_branch"]["b1"]["status"] == "conditional"


def test_pregnancy_item_for_a_boy_kept_but_not_reported():
    req = {"kind": "other", "text": "Pregnancy Management", "field": "pregnancy"}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("supportive_management", pregnancy=True, key="procedure:iv_fluids", label="IV fluids")
    src = found["procedure:iv_fluids"]["specs"][0]["src"]
    found["procedure:iv_fluids"]["reqs"] = [dict(req, spec=E._spec("section", src, "Pregnancy Management",
                                                                  "Management / Pregnancy Management", 1))]
    E._records(led, found, PF_FS, [])                       # PF: 7-year-old boy
    a = next(a for a in led.actions if a["action_key"] == "procedure:iv_fluids")
    assert a["status_by_branch"]["b1"]["status"] == "not_applicable" and a["report"] is False

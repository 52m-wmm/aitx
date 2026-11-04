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

"""Lab unit inference (aitx/evidence/labs.py) on a synthetic, verified table; the shipped table gates use."""
from aitx.evidence import labs as LB

HB = {"hemoglobin": {"aliases": ["hemoglobin", "hb"], "canonical_unit": "g/dL", "status": "verified",
                     "units": {"g/dL": {"factor": 1}, "g/L": {"factor": 0.1}, "mg/dL": {"factor": 0.001}},
                     "plausible": {"low": 1, "high": 25}}}
HB_MMOL = {"hemoglobin": {**HB["hemoglobin"], "units": {**HB["hemoglobin"]["units"], "mmol/L": {"factor": 1.6114}}}}


def test_unitless_value_takes_the_only_plausible_unit_with_assumption():
    r = LB.interpret("Hemoglobin", 5, None, table=HB, who="in the case")
    assert r["status"] == "assumed" and r["used_unit"] == "g/dL" and r["value"] == 5
    assert "interpreted as 5 g/dL" in r["assumption"] and "no unit stated" in r["assumption"]


def test_implausible_registry_unit_is_reinterpreted():
    r = LB.interpret("hemoglobin", 7, "mg/dL", table=HB, who="threshold")
    assert r["status"] == "assumed" and r["used_unit"] == "g/dL" and "implausible" in r["assumption"]
    p = LB.interpret("Hb", 5, None, table=HB)
    assert LB.compare(p, "<", r) == "satisfies"                      # 5 g/dL < 7 g/dL: meets the exclusion


def test_two_plausible_units_is_unknown():
    r = LB.interpret("hemoglobin", 5, None, table=HB_MMOL)
    assert r["status"] == "unknown" and set(r["candidates"]) == {"g/dL", "mmol/L"}
    assert LB.compare(r, "<", LB.interpret("hemoglobin", 7, "g/dL", table=HB_MMOL)) == "unknown"


def test_stated_plausible_unit_and_conversion():
    r = LB.interpret("hemoglobin", 120, "g/l", table=HB)
    assert r["status"] == "ok" and r["value"] == 12 and r["assumption"] is None


def test_unverified_or_unknown_analyte_gives_unknown():
    assert LB.interpret("hemoglobin", 5, "g/dL")["status"] == "unknown"      # shipped table: pending sources
    assert LB.interpret("unobtainium", 5, "g/dL", table=HB)["status"] == "unknown"
    assert LB.interpret("hemoglobin", 5, "furlongs", table=HB)["status"] == "unknown"


def test_shipped_table_factors_have_sources():
    for k, a in LB.load().items():
        for u, f in a["units"].items():
            assert f.get("source"), (k, u)
        if a["status"] == "verified":
            assert LB.usable(a) and "PENDING" not in a["plausible"]["source"]


def test_ambiguous_unit_gives_one_scenario_per_unit():
    p = LB.interpret("hemoglobin", 5, None, table=HB_MMOL)
    th = LB.interpret("hemoglobin", 7, "mg/dL", table=HB_MMOL, who="threshold")    # registry unit implausible -> g/dL
    assert th["status"] == "assumed" and LB.compare(p, "<", th) == "unknown"
    sc = {s["unit"]: s for s in LB.scenarios(p, "<", th)}
    assert sc["g/dL"]["result"] == "satisfies" and sc["mmol/L"]["result"] == "does_not_satisfy"
    assert abs(sc["mmol/L"]["value"] - 8.057) < 0.01
    assert LB.scenarios(LB.interpret("hemoglobin", 5, None, table=HB), "<", th) == []

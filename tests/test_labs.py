"""Lab unit inference (aitx/evidence/labs.py): plausible range = ABIM reference /10 .. x10; a stated unit is
reread only as a >= 100x unit slip; unverified factors are never assumed and never ruled out."""
import copy

from aitx.evidence import labs as LB

TABLE = LB.load()


def with_hb_mmol(factor):
    t = copy.deepcopy(TABLE)
    t["hemoglobin"]["units"]["mmol/L"]["factor"] = factor
    return t


def test_plausible_range_from_reference():
    hb = TABLE["hemoglobin"]["plausible"]
    assert (hb["low"], hb["high"]) == (1.2, 180)                         # ABIM 12-18 g/dL
    nh3 = TABLE["ammonia"]["plausible"]                                   # ABIM 40-70 ug/dL, canonical umol/L
    assert abs(nh3["low"] - 40 * 0.58717 / 10) < 1e-9 and abs(nh3["high"] - 70 * 0.58717 * 10) < 1e-9
    for k, a in TABLE.items():
        assert a["reference"]["version"] == "January 2026" and a["reference"]["page"], k


def test_ex8_unitless_hemoglobin_is_ambiguous_while_mmol_factor_unverified():
    p = LB.interpret("Hemoglobin", 5, None, who="in the case")
    assert p["status"] == "unknown" and p["candidates"] == {"g/dL": 5, "mmol/L": None}
    th = LB.interpret("hemoglobin", 7, "mg/dL", who="threshold")         # 0.007 g/dL implausible; mg -> g is 1000x
    assert th["status"] == "assumed" and th["used_unit"] == "g/dL" and "implausible" in th["assumption"]
    assert LB.compare(p, "<", th) == "unknown"
    sc = {s["unit"]: s["result"] for s in LB.scenarios(p, "<", th)}
    assert sc == {"g/dL": "satisfies", "mmol/L": "unknown"}


def test_ex8_with_a_verified_mmol_factor_gives_both_outcomes():
    t = with_hb_mmol(1 / 0.6206)
    p = LB.interpret("hemoglobin", 5, None, table=t)
    th = LB.interpret("hemoglobin", 7, "mg/dL", table=t)
    sc = {s["unit"]: s for s in LB.scenarios(p, "<", th)}
    assert sc["g/dL"]["result"] == "satisfies" and sc["mmol/L"]["result"] == "does_not_satisfy"
    assert abs(sc["mmol/L"]["value"] - 8.057) < 0.01


def test_unitless_single_plausible_unit_is_assumed():
    r = LB.interpret("albumin", 3.2, None)                               # 3.2 g/dL plausible; 0.32 g/dL (g/L) not
    assert r["status"] == "assumed" and r["used_unit"] == "g/dL" and "only unit" in r["assumption"]
    r = LB.interpret("albumin", 32, None)                                # 32 g/L = 3.2 g/dL; 32 g/dL also within x10
    assert r["status"] == "unknown" and set(r["candidates"]) == {"g/dL", "g/L"}


def test_stated_plausible_unit_and_conversion():
    r = LB.interpret("hemoglobin", 120, "g/l")
    assert r["status"] == "ok" and r["value"] == 12 and r["assumption"] is None
    r = LB.interpret("creatinine", 88.4, "µmol/L")
    assert r["status"] == "ok" and abs(r["value"] - 1.0) < 0.001


def test_beyond_x10_is_unknown_not_reread():
    # dialysis creatinine above 13 mg/dL: umol/L is only 88x away -> no reread, unknown (never "0.17 mg/dL")
    r = LB.interpret("creatinine", 15, "mg/dL")
    assert r["status"] == "unknown" and "no single unit-slip" in r["why"]
    # hyperammonaemic crisis beyond 70 ug/dL x10 (about 411 umol/L) -> unknown
    assert LB.interpret("ammonia", 2000, "umol/L")["status"] == "unknown"
    # 10x slip (g/dL vs g/L) is not reread either
    assert LB.interpret("hemoglobin", 0.5, "g/dL")["status"] == "unknown"


def test_unverified_unit_never_assumed():
    assert "not verified" in LB.interpret("hemoglobin", 8, "mmol/L")["why"]


def test_unknown_analyte_unit_or_unverified_entry():
    assert LB.interpret("unobtainium", 5, "g/dL")["status"] == "unknown"
    assert LB.interpret("hemoglobin", 5, "furlongs")["status"] == "unknown"
    t = copy.deepcopy(TABLE)
    t["hemoglobin"]["status"] = "pending"
    assert LB.interpret("hemoglobin", 12, "g/dL", table=t)["status"] == "unknown"


def test_shipped_table_factors_have_sources():
    for k, a in TABLE.items():
        for u, f in a["units"].items():
            assert f.get("source"), (k, u)
            assert (f["factor"] is None) == f["source"].startswith("PENDING"), (k, u)

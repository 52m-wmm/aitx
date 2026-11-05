"""Derived patient values (contract docs/step3b_contract.md, 派生值): computed only by a published formula and only
when every input is stated in the case. A missing input -> None (unknown); nothing is filled in (no height, weight,
race or default age). Code only.

  eGFR, age >= 18    CKD-EPI 2021 creatinine equation (race-free): Inker LA et al., N Engl J Med 2021;385:1737-1749
                     eGFR = 142 x min(Scr/k, 1)^a x max(Scr/k, 1)^-1.200 x 0.9938^age [x 1.012 if female]
                     k = 0.7 (female) / 0.9 (male); a = -0.241 (female) / -0.302 (male); Scr in mg/dL
  eGFR, age < 18     bedside Schwartz: Schwartz GJ et al., J Am Soc Nephrol 2009;20:629-637
                     eGFR = 0.413 x height (cm) / Scr (mg/dL); needs a stated height
"""
from __future__ import annotations


def egfr(creatinine_mg_dl: float | None, age_years: float | None, sex: str | None,
         height_cm: float | None = None) -> dict:
    """{value, unit, formula, inputs} or {value: None, missing: [...]} (mL/min/1.73 m2)."""
    missing = [n for n, v in (("creatinine (mg/dL)", creatinine_mg_dl), ("age", age_years)) if v is None]
    if age_years is not None and age_years >= 18 and sex not in ("male", "female"):
        missing.append("sex")
    if age_years is not None and age_years < 18 and height_cm is None:
        missing.append("height")
    if missing:
        return {"value": None, "missing": missing}
    scr = creatinine_mg_dl
    if age_years >= 18:
        f = sex == "female"
        k, a = (0.7, -0.241) if f else (0.9, -0.302)
        v = 142 * min(scr / k, 1) ** a * max(scr / k, 1) ** -1.200 * 0.9938 ** age_years * (1.012 if f else 1)
        formula = "CKD-EPI 2021 creatinine (Inker et al., NEJM 2021)"
    else:
        v = 0.413 * height_cm / scr
        formula = "bedside Schwartz (Schwartz et al., JASN 2009)"
    return {"value": round(v, 1), "unit": "mL/min/1.73 m2", "formula": formula,
            "inputs": {"creatinine_mg_dl": scr, "age_years": age_years, "sex": sex, "height_cm": height_cm}}

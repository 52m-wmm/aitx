"""Lab values with units (3b contract, step 5 and decision 3). Code only.

interpret(analyte, value, unit) -> the value in the analyte's canonical unit, or unknown, with any unit
assumption spelled out so the evidence and the report can state it:
  - unit stated and plausible               -> use it, no assumption
  - unit stated but implausible             -> the only unit of the same dimension (mass or molar) giving a
                                               plausible value, with the assumption
                                               ("Hemoglobin < 7 mg/dL interpreted as g/dL: ..."), else unknown
  - no unit                                 -> the only plausible unit, with the assumption; 2+ plausible -> unknown
Analytes whose table entry is not 'verified' (config/lab_plausible_ranges.json) always give unknown.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TABLE = Path(__file__).resolve().parents[2] / "config" / "lab_plausible_ranges.json"
_UNIT_NORM = {"µ": "u", "μ": "u", " ": "", "/l": "/L", "/dl": "/dL"}


def load(path: Path = TABLE) -> dict:
    return json.loads(path.read_text())["analytes"]


def norm_unit(u: str | None) -> str | None:
    if not u:
        return None
    s = u.strip()
    for a, b in _UNIT_NORM.items():
        s = s.replace(a, b)
    s = re.sub(r"(?i)^(m|u|n|)g/dl$", lambda m: m.group(1).lower() + "g/dL", s)
    s = re.sub(r"(?i)^(m|u|n|)(mol|g)/l$", lambda m: m.group(1).lower() + m.group(2).lower() + "/L", s)
    return s


def analyte_of(name: str, table: dict) -> str | None:
    n = name.strip().lower()
    return next((k for k, a in table.items() if n == k or n in a["aliases"]), None)


def _dim(unit: str) -> str:
    return "molar" if "mol" in unit else "mass"


def usable(entry: dict) -> bool:
    p = entry.get("plausible") or {}
    return entry.get("status") == "verified" and p.get("low") is not None and p.get("high") is not None


def _plausible(entry: dict, value: float, unit: str) -> float | None:
    f = (entry["units"].get(unit) or {}).get("factor")
    if f is None:
        return None
    v = value * f
    return v if entry["plausible"]["low"] <= v <= entry["plausible"]["high"] else None


def interpret(analyte: str, value: float, unit: str | None, *, table: dict | None = None, who: str = "value") -> dict:
    """{status: ok | assumed | unknown, value (canonical), unit (canonical), used_unit, assumption, why}."""
    table = table if table is not None else load()
    key = analyte_of(analyte, table)
    if key is None:
        return {"status": "unknown", "why": f"{analyte}: not in the lab unit table"}
    entry = table[key]
    canon = entry["canonical_unit"]
    if not usable(entry):
        return {"status": "unknown", "why": f"{key}: unit table entry not verified yet"}
    u = norm_unit(unit)
    if u and u not in entry["units"]:
        return {"status": "unknown", "why": f"{key}: unit {unit!r} not in the table"}
    if u:
        v = _plausible(entry, value, u)
        if v is not None:
            return {"status": "ok", "value": v, "unit": canon, "used_unit": u, "assumption": None}
    # a stated but implausible unit is reread only within its dimension (mass <-> mass, molar <-> molar):
    # "7 mg/dL" for hemoglobin is a g/dL slip, not a molar value
    same = [x for x in entry["units"] if not u or _dim(x) == _dim(u)]
    fits = {x: _plausible(entry, value, x) for x in same}
    fits = {x: v for x, v in fits.items() if v is not None}
    stated = f"{value:g} {unit}" if u else f"{value:g} (no unit)"
    if len(fits) == 1:
        x, v = next(iter(fits.items()))
        why = ("the stated unit gives a physiologically implausible value" if u else "no unit stated")
        return {"status": "assumed", "value": v, "unit": canon, "used_unit": x,
                "assumption": f"{key} {who} {stated} interpreted as {value:g} {x}: {why}; {x} is the only unit giving a "
                              f"physiologically plausible value ({entry['plausible']['low']:g}-{entry['plausible']['high']:g} {canon})"}
    if not fits:
        return {"status": "unknown", "why": f"{key} {stated}: no unit gives a plausible value"}
    return {"status": "unknown", "why": f"{key} {stated}: more than one unit gives a plausible value ({', '.join(sorted(fits))})",
            "unit": canon, "candidates": {x: round(v, 3) for x, v in fits.items()}}


def compare(patient: dict, op: str, threshold: dict) -> str:
    """patient / threshold: interpret() results. -> satisfies / does_not_satisfy / unknown."""
    if patient.get("status") == "unknown" or threshold.get("status") == "unknown" or op not in ("<", "<=", ">", ">=", "="):
        return "unknown"
    a, b = patient["value"], threshold["value"]
    ok = {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "=": abs(a - b) < 1e-9}[op]
    return "satisfies" if ok else "does_not_satisfy"


def scenarios(patient: dict, op: str, threshold: dict) -> list[dict]:
    """When the patient's unit is ambiguous, the outcome under each plausible unit, for the report
    ("if g/dL: meets the exclusion; if mmol/L (= 8.1 g/dL): does not"). Empty when there is nothing to split."""
    if threshold.get("status") == "unknown" or not patient.get("candidates"):
        return []
    return [{"unit": u, "value": v, "canonical_unit": patient.get("unit"),
             "result": compare({"status": "ok", "value": v}, op, threshold)} for u, v in sorted(patient["candidates"].items())]

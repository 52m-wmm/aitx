"""Lab values with units (3b contract, step 5 and decision 3). Code only.

interpret(analyte, value, unit) -> the value in the analyte's canonical unit, or unknown, with any unit
assumption spelled out so the evidence and the report can state it:
  - unit stated and plausible               -> use it, no assumption
  - unit stated but implausible             -> the only unit of the same dimension whose factor differs by
                                               >= 100x (a unit slip) and gives a plausible value; else unknown
                                               ("Hemoglobin < 7 mg/dL interpreted as g/dL: ..."), else unknown
  - no unit                                 -> the only plausible unit, with the assumption; 2+ plausible, or a
                                               unit with an unverified factor that cannot be ruled out -> unknown
Plausible range = checked reference interval low / 10 .. high x 10 (pathological values are usually within
a few times the normal range; unit slips are usually >= 100x). Values beyond it give unknown, never a guess.
Analytes whose table entry is not 'verified' (config/lab_plausible_ranges.json) always give unknown.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TABLE = Path(__file__).resolve().parents[2] / "config" / "lab_plausible_ranges.json"
_UNIT_NORM = {"µ": "u", "μ": "u", " ": "", "/l": "/L", "/dl": "/dL"}


WIDEN = 10           # plausible range = reference low / 10 .. reference high x 10 (decided 2026-11-03)
MIN_REREAD = 100     # a stated unit is reread only as a unit whose factor differs by at least this much


def load(path: Path = TABLE) -> dict:
    """Analytes with the plausible range derived from the checked reference interval (canonical unit)."""
    out = json.loads(path.read_text())["analytes"]
    for a in out.values():
        r = a.get("reference") or {}
        f = (a["units"].get(r.get("unit")) or {}).get("factor")
        if r and f is not None:
            a["plausible"] = {"low": r["low"] * f / WIDEN, "high": r["high"] * f * WIDEN,
                              "rule": f"reference {r['low']:g}-{r['high']:g} {r['unit']} (/{WIDEN}, x{WIDEN})"}
    return out


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
    return entry.get("status") == "verified" and bool(entry.get("plausible"))


def _value(entry: dict, value: float, unit: str) -> float | None:
    f = (entry["units"].get(unit) or {}).get("factor")
    return None if f is None else value * f


def _ok(entry: dict, v: float | None) -> bool:
    return v is not None and entry["plausible"]["low"] <= v <= entry["plausible"]["high"]


def interpret(analyte: str, value: float, unit: str | None, *, table: dict | None = None, who: str = "value") -> dict:
    """{status: ok | assumed | unknown, value (canonical), unit (canonical), used_unit, assumption, why, candidates}."""
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
    pl = entry["plausible"]
    rng = f"{pl['low']:g}-{pl['high']:g} {canon}, {pl['rule']}"
    if u:
        fs = entry["units"][u]["factor"]
        if fs is None:
            return {"status": "unknown", "why": f"{key}: conversion factor for {u} not verified"}
        if _ok(entry, value * fs):
            return {"status": "ok", "value": value * fs, "unit": canon, "used_unit": u, "assumption": None}
        alts = {x: _value(entry, value, x) for x, d in entry["units"].items()
                if d.get("factor") is not None and _dim(x) == _dim(u)
                and max(d["factor"] / fs, fs / d["factor"]) >= MIN_REREAD}
        fits = {x: v for x, v in alts.items() if _ok(entry, v)}
        if len(fits) == 1:
            x, v = next(iter(fits.items()))
            return {"status": "assumed", "value": v, "unit": canon, "used_unit": x,
                    "assumption": f"{key} {who} {value:g} {unit} interpreted as {value:g} {x}: the stated unit gives a "
                                  f"physiologically implausible value; {x} is the only unit-slip reading (factor >= {MIN_REREAD}x) "
                                  f"in the plausible range ({rng})"}
        return {"status": "unknown", "why": f"{key} {value:g} {unit}: implausible ({rng}) and no single unit-slip reading"}
    fits = {x: _value(entry, value, x) for x in entry["units"]}
    pending = sorted(x for x, v in fits.items() if v is None)          # cannot be ruled out
    fits = {x: v for x, v in fits.items() if _ok(entry, v)}
    if len(fits) == 1 and not pending:
        x, v = next(iter(fits.items()))
        return {"status": "assumed", "value": v, "unit": canon, "used_unit": x,
                "assumption": f"{key} {who} {value:g} (no unit) interpreted as {value:g} {x}: {x} is the only unit giving a "
                              f"physiologically plausible value ({rng})"}
    cands = {x: round(v, 3) for x, v in fits.items()} | {x: None for x in pending}
    if not cands:
        return {"status": "unknown", "why": f"{key} {value:g} (no unit): no unit gives a plausible value ({rng})"}
    why = (f"{key} {value:g} (no unit): more than one unit is possible ({', '.join(sorted(cands))}"
           + (f"; {', '.join(pending)} conversion not verified" if pending else "") + ")")
    return {"status": "unknown", "why": why, "unit": canon, "candidates": cands}


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
             "result": "unknown" if v is None else compare({"status": "ok", "value": v}, op, threshold)}
            for u, v in sorted(patient["candidates"].items())]

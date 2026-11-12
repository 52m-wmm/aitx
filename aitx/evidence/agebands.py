"""Age-band limits decided by code (user decision 2026-11-12). Never asked of the LLM.

When the context check finds a limit that is an age band ("Newborns", "Infants", "Children", "Adolescents", "Adults",
"Pediatric ..."), and the case states the patient's age explicitly (a quoted age, step 2), code compares:
    age certainly inside the band  -> satisfies      (only when the limit says nothing but the band)
    age certainly outside the band -> does_not_satisfy (the entry becomes not applicable; it stays in the ledger and
                                                        is not written in the report, as pregnancy-only entries)
    otherwise (age not stated, or in a zone where authoritative definitions differ) -> unknown (conditional)

Band boundaries: ICH E11 (2000) "Clinical Investigation of Medicinal Products in the Pediatric Population", section 2.5
"Age classification of paediatric patients": term newborn infants 0-27 days; infants and toddlers 28 days-23 months;
children 2-11 years; adolescents 12 to 16-18 years (dependent on region). Where other authoritative or common
definitions differ - WHO adolescence 10-19 years; "infant" in common clinical use under 12 months; "children" often
used for all minors (under 18); US FDA pediatric devices up to 21 years (21 CFR 814.3(s)) - those ages are left
unknown, so a limit never decides on a boundary the sources disagree about.
"""
from __future__ import annotations

import re

SOURCE = ("ICH E11 (2000) section 2.5, https://database.ich.org/sites/default/files/E11_Guideline.pdf; "
          "zones where WHO (adolescence 10-19 y), common clinical use or 21 CFR 814.3(s) differ are left unknown")

M = 1.0                     # one month
Y = 12.0                    # one year, in months
# band -> (pattern, inside [lo, hi) months, outside: list of [lo, hi) months); anything else is unknown
BANDS = {
    "newborn":    (r"newborns?|new-borns?|neonates?|neonatal", (0, 0.92), [(1 * M, 1e9)]),
    "infant":     (r"infants?|infancy", (1 * M, 12 * M), [(24 * M, 1e9)]),
    "child":      (r"child|children|childhood", (2 * Y, 12 * Y), [(18 * Y, 1e9)]),
    "adolescent": (r"adolescents?|adolescence|teenagers?|teens?", (12 * Y, 16 * Y), [(0, 10 * Y), (20 * Y, 1e9)]),
    "adult":      (r"adults?|adulthood", (18 * Y, 1e9), [(0, 16 * Y)]),
    "pediatric":  (r"pa?ediatrics?", (0, 16 * Y), [(21 * Y, 1e9)]),
}
_ANY = re.compile(r"\b(" + "|".join(p for p, _, _ in BANDS.values()) + r")\b", re.I)
# words that turn a band into something else ("after the newborn period", "older than infants") - never decided here
_RELATION = re.compile(r"\b(after|before|beyond|older|younger|than|until|up to|under|over|aged?|from|through|"
                       r"except|not|non|post|pre|period|onset|born)\b", re.I)
_FILLER = {"with", "and", "the", "a", "an", "in", "for", "of", "management", "persons", "people", "patients",
           "individuals", "those", "who", "have", "has", "all", "only", "s"}


def bands_in(text: str) -> list[str]:
    found = []
    for m in _ANY.finditer(text or ""):
        for name, (pat, _, _) in BANDS.items():
            if re.fullmatch(pat, m.group(1), re.I) and name not in found:
                found.append(name)
    return found


def _pure(text: str, disease: str) -> bool:
    """The limit names nothing but age bands (and the disease itself, and filler words)."""
    rest = _ANY.sub(" ", text)
    dis = {w.lower() for w in re.findall(r"[A-Za-z0-9]+", disease or "")}
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", rest)]
    return all(w in _FILLER or w in dis for w in words)


def limit_status(text: str, pf: dict, disease: str = "") -> tuple[str, dict, str] | None:
    """(patient_status, patient_fact, note) for an age-band limit, or None when the limit is not one (code leaves it
    to the context check's ordinary handling)."""
    names = bands_in(text)
    if not names or _RELATION.search(text):
        return None
    age, quote = pf.get("age_months"), pf.get("age_quote")
    note = f"age band {', '.join(names)} decided by code ({SOURCE})"
    if age is None or not quote:
        return "unknown", {"field": "age", "value": None, "quote": None, "step": None}, note + "; age not stated"
    fact = {"field": "age", "value": f"{age / 12:g} years" if age >= 12 else f"{age:g} months", "quote": quote,
            "step": 2}
    inside = any(BANDS[n][1][0] <= age < BANDS[n][1][1] for n in names)
    outside = all(any(lo <= age < hi for lo, hi in BANDS[n][2]) for n in names)
    alternatives = re.search(r"\bor\b", text, re.I) is not None
    if outside and not alternatives:
        return "does_not_satisfy", fact, note + "; the patient's stated age is outside the band"
    if inside and _pure(text, disease):
        return "satisfies", fact, note + "; the patient's stated age is inside the band"
    return "unknown", fact, note + "; the stated age does not settle the band (definitions differ, or the limit says more)"

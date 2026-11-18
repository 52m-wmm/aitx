"""Action keys: when are two recommendations "the same action"? (step 3.0 contract, section 1.3)

Every action in the ledger gets a normalized key; equal keys = same action, whatever the spelling,
brand, salt or dose. The ledger check then forbids one action in two report sections.

  drug     drug:rxcui:<ingredient RxCUIs, sorted, '+'>   RxNorm ingredient(s) (TTY IN)
           drug:chembl:<parent ChEMBL ids, sorted, '+'>  no RxNorm entry (investigational compounds)
           drug:name:<normalized name>                   fallback, normalized=False (allowed, flagged)
  trial    trial:NCT01234567
  other    <type>:<target>[|<qualifier>]                 type from STRATEGY_TYPES

Drug names resolve in this order: (1) RxNav by exact name, expanded to ingredients (brand, salt,
product and multi-ingredient concepts all lead to their ingredients); (2) openFDA label: US brand
name -> generic name -> (1) per ingredient; (3) ChEMBL, exact name or synonym only, parent molecule;
(4) fallback key from the normalized name. All requests go through aitx.http (cached, access time kept).
"""
from __future__ import annotations

import json
import re
import urllib.parse

from aitx import http

RXNAV = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_LABEL = "https://api.fda.gov/drug/label.json"
CHEMBL_SEARCH = "https://www.ebi.ac.uk/chembl/api/data/molecule/search.json"

STRATEGY_TYPES = {
    "aso_splice_modulation", "aso_exon_skipping", "aso_knockdown_allele_specific", "aso_knockdown_total", "sirna",
    "gene_replacement", "base_editing", "prime_editing", "gene_editing_other", "cell_therapy", "organ_transplant",
    "diet", "procedure", "supportive_measure", "therapy",
}

# therapy:<type> - controlled vocabulary (supportive fallback contract, 2026-11-04); code decides, the LLM only gives the
# name as written. A therapy name that matches none of these is not collected.
THERAPY_TYPES = (
    ("early_intervention", r"\bearly\s+intervention\b"),
    ("feeding_therapy", r"\bfeeding\s+(?:therapy|therapist|intervention)\b|\bswallow(?:ing)?\s+therapy\b"),
    ("speech_language_therapy", r"\bspeech(?:[\s/-]+(?:and\s+)?language)?\s+(?:therapy|therapist|services|intervention)s?\b|"
                                r"\blanguage\s+therapy\b"),
    ("occupational_therapy", r"\boccupational\s+therap(?:y|ist)\b"),
    ("physical_therapy", r"\bphysi(?:cal\s+therap(?:y|ist)|otherap(?:y|ist))\b"),
    ("other_rehabilitation", r"\brehabilitation\b|\bdevelopmental\s+preschool\b|\bspecial\s+education\b"),
)
THERAPY_ABBREVIATIONS = {"PT": "physical_therapy", "OT": "occupational_therapy", "SLP": "speech_language_therapy"}  # upper case only
# referrals to be evaluated, counselled or followed up are never a therapy (excluded even when a word above matches)
NOT_THERAPY = r"\b(?:evaluat\w*|assess\w*|consult\w*|counsel\w*|follow[\s-]?up|genetic|surveillance|screening)\b"


AIRWAY_CLEARANCE = re.compile(r"\bchest\s+(?:physical\s+therap\w*|physiotherap\w*|PT)\b|\bairway\s+clearance\b", re.I)


def therapy_type(name: str) -> str | None:
    """Controlled therapy type of a name as written, or None (not a therapy, or an evaluation / counselling referral)."""
    n = name or ""
    if re.search(NOT_THERAPY, n, re.I) or AIRWAY_CLEARANCE.search(n):
        return None
    for t, rx in THERAPY_TYPES:
        if re.search(rx, n, re.I):
            return t
    for abbr, t in THERAPY_ABBREVIATIONS.items():
        if re.search(rf"(?<![A-Za-z]){abbr}(?![A-Za-z])", n):
            return t
    return None
    for t, rx in THERAPY_TYPES:
        if re.search(rx, n, 0 if t in () else re.I) if rx.find("\\b(?:") < 0 else re.search(rx, n, re.I):
            return t
    return None
ORGANS = {"liver", "kidney", "heart", "lung", "pancreas", "intestine", "bone_marrow", "cornea", "skin"}
SALTS = {"hydrochloride", "hcl", "dihydrochloride", "sodium", "disodium", "potassium", "calcium", "magnesium",
         "sulfate", "sulphate", "mesylate", "mesilate", "maleate", "acetate", "citrate", "tartrate", "phosphate",
         "succinate", "besylate", "besilate", "fumarate", "bromide", "chloride", "hydrobromide", "monohydrate",
         "dihydrate", "trihydrate"}
_SPLIT = re.compile(r"\s*(?:/|\+|,|\band\b)\s*", re.I)
# dose, route, form and schedule words are not part of the action (contract 1.3: dose lives in the claim)
_DOSE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|µg|ug|ml|iu|units?|mmol)(?:\s*/\s*(?:kg|m2|day|d|dose|ml))*\b"
                   r"|\b(?:once|twice|thrice|daily|weekly|monthly|quarterly|yearly|bid|tid|qid|qd|q\d+[hdw]|"
                   r"every\s+\d*\s*(?:hours?|days?|weeks?|months?)|per\s+(?:day|week|month)|orally|oral|"
                   r"intravenous(?:ly)?|iv|subcutaneous(?:ly)?|sc|intrathecal(?:ly)?|tablets?|capsules?|"
                   r"injections?|solution|infusions?)\b", re.I)
_NCT = re.compile(r"^NCT\d{8}$")


# ------------------------------------------------------------------ names

def strip_dose(name: str) -> str:
    """'lumasiran 3 mg/kg monthly' -> 'lumasiran'."""
    return re.sub(r"\s+", " ", _DOSE.sub(" ", name)).strip()


_PAREN = re.compile(r"\s*\(([^)]*)\)")


def strip_abbrev(name: str) -> str:
    """Drop a parenthesised abbreviation: "potassium bromide (KBr)" -> "potassium bromide".

    Only a short, mostly upper-case parenthetical is dropped, because that is what an abbreviation looks like.
    A spelled-out synonym or qualifier is kept ("vitamin B6 (pyridoxine)", "insulin (human)"), since dropping
    it could throw away the only real drug name.

    Reason (2026-11-09, found in the blind test): with the abbreviation in the label, RxNorm finds nothing and
    the fallback key is built from the abbreviation itself, so one drug gets two action keys and the "no action
    twice" rule fails. Seen three times: "sodium thiosulfate (STS)", "potassium bromide (KBr)" and
    "anti-seizure medication (ASM)" - the last two wrote the same drug twice in one report, with conflicting
    conclusions.
    """
    def drop(m: re.Match) -> str:
        inner = m.group(1).strip()
        letters = re.sub(r"[^A-Za-z]", "", inner)
        if not letters or len(inner) > 8:
            return m.group(0)
        return " " if sum(c.isupper() for c in letters) >= max(1, len(letters) // 2) else m.group(0)

    out = re.sub(r"\s+", " ", _PAREN.sub(drop, name or "")).strip()
    return out or (name or "").strip()


def components(name: str) -> list[str]:
    """Ingredient names of a (possibly combined) drug name: 'Foo sodium / Bar' -> ['bar', 'foo']."""
    out = []
    for part in _SPLIT.split(strip_abbrev(strip_dose(name)).lower()):
        all_words = re.sub(r"[^a-z0-9\- ]+", " ", part).split()
        words = [w for w in all_words if w not in SALTS]
        # every word was a salt word ("potassium bromide", "potassium chloride"): keep them, or the name
        # collapses to nothing and two different drugs share the empty fallback key drug:name:
        # (2026-11-09, found by the reverse test for the abbreviation fix)
        if not words:
            words = all_words
        if words:
            out.append(" ".join(words))
    return sorted(set(out))


def fallback_key(name: str) -> str:
    return "drug:name:" + "+".join(components(name))


# --------------------------------------------------------------- sources

def _json(url: str) -> dict | None:
    try:
        return json.loads(http.get(url).text)
    except (RuntimeError, ValueError):          # 4xx (e.g. openFDA "no matches" is a 404) or bad JSON
        return None


def rxnorm_ingredients(name: str) -> list[dict]:
    """[{rxcui, name}] of the RxNorm ingredient(s) for an exact drug name; [] if RxNorm has no such name."""
    d = _json(f"{RXNAV}/rxcui.json?" + urllib.parse.urlencode({"name": name, "search": 2}))
    ids = ((d or {}).get("idGroup") or {}).get("rxnormId") or []
    if not ids:
        return []
    rel = _json(f"{RXNAV}/rxcui/{ids[0]}/related.json?tty=IN")
    groups = ((rel or {}).get("relatedGroup") or {}).get("conceptGroup") or []
    return sorted(({"rxcui": c["rxcui"], "name": c["name"]} for g in groups for c in g.get("conceptProperties") or []),
                  key=lambda c: int(c["rxcui"]))


def openfda_generic(brand: str) -> str | None:
    """US brand name -> generic name from the FDA label (openFDA); None if not a US label brand name."""
    q = urllib.parse.urlencode({"search": f'openfda.brand_name:"{brand.upper()}"', "limit": 1})
    d = _json(f"{OPENFDA_LABEL}?{q}")
    names = (((d or {}).get("results") or [{}])[0].get("openfda") or {}).get("generic_name") or []
    return names[0] if names else None


def chembl_parent(name: str) -> dict | None:
    """Parent ChEMBL molecule whose preferred name or a synonym equals `name` (no fuzzy hits)."""
    d = _json(f"{CHEMBL_SEARCH}?" + urllib.parse.urlencode({"q": name, "limit": 10}))
    want = name.strip().lower()
    for m in (d or {}).get("molecules") or []:
        names = [m.get("pref_name") or ""] + [s.get("molecule_synonym") or "" for s in m.get("molecule_synonyms") or []]
        if any(n.strip().lower() == want for n in names):
            parent = (m.get("molecule_hierarchy") or {}).get("parent_chembl_id") or m["molecule_chembl_id"]
            return {"chembl_id": parent, "name": m.get("pref_name")}
    return None


# ------------------------------------------------------------------ keys

def drug_key(name: str) -> dict:
    """{key, normalized, method, ingredients, input}"""
    out = {"input": name}
    name = strip_abbrev(strip_dose(name)) or name
    ing = rxnorm_ingredients(name)
    if ing:
        return {**out, "key": "drug:rxcui:" + "+".join(c["rxcui"] for c in ing), "normalized": True,
                "method": "rxnorm", "ingredients": ing}
    generic = openfda_generic(name)
    if generic:
        parts = [rxnorm_ingredients(p) for p in components(generic)]
        if parts and all(parts):
            ing = sorted({c["rxcui"]: c for p in parts for c in p}.values(), key=lambda c: int(c["rxcui"]))
            return {**out, "key": "drug:rxcui:" + "+".join(c["rxcui"] for c in ing), "normalized": True,
                    "method": f"openfda brand -> generic '{generic}' -> rxnorm", "ingredients": ing}
    comps = components(name)
    if len(comps) > 1:
        parts = [rxnorm_ingredients(p) for p in comps]
        if all(parts):
            ing = sorted({c["rxcui"]: c for p in parts for c in p}.values(), key=lambda c: int(c["rxcui"]))
            return {**out, "key": "drug:rxcui:" + "+".join(c["rxcui"] for c in ing), "normalized": True,
                    "method": "rxnorm per ingredient", "ingredients": ing}
    chem = [chembl_parent(p) for p in comps]
    if chem and all(chem):
        ids = sorted({c["chembl_id"] for c in chem})
        return {**out, "key": "drug:chembl:" + "+".join(ids), "normalized": True, "method": "chembl parent",
                "ingredients": chem}
    return {**out, "key": fallback_key(name), "normalized": False,
            "method": "fallback: normalized name (no RxNorm, openFDA or ChEMBL match)", "ingredients": []}


def trial_key(nct: str) -> str:
    n = nct.strip().upper()
    if not _NCT.match(n):
        raise ValueError(f"not an NCT number: {nct!r}")
    return f"trial:{n}"


def strategy_key(kind: str, target: str | list[str], qualifier: str | None = None) -> str:
    """Non-drug action: type from STRATEGY_TYPES; target = HGNC symbol, organ(s) or a controlled regimen name."""
    if kind not in STRATEGY_TYPES:
        raise ValueError(f"unknown strategy type {kind!r}")
    targets = [target] if isinstance(target, str) else list(target)
    if kind == "organ_transplant":
        bad = [t for t in targets if t.lower() not in ORGANS]
        if bad:
            raise ValueError(f"unknown organ(s) {bad}")
        tgt = "+".join(sorted(t.lower() for t in targets))
    elif kind == "therapy":
        if any(t not in [x for x, _ in THERAPY_TYPES] for t in targets):
            raise ValueError(f"unknown therapy type(s) {targets}")
        tgt = "+".join(sorted(targets))
    elif kind in ("diet", "procedure", "supportive_measure"):
        tgt = "+".join(sorted(re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_") for t in targets))
    else:
        tgt = "+".join(sorted(t.upper() for t in targets))            # gene symbols
    return f"{kind}:{tgt}" + (f"|{qualifier.strip().lower()}" if qualifier else "")


def same_action(a: dict, b: dict) -> bool:
    """Two ledger actions are the same if their keys or 'implements' keys meet."""
    ka = {a.get("key")} | ({a["implements"]} if a.get("implements") else set())
    kb = {b.get("key")} | ({b["implements"]} if b.get("implements") else set())
    return bool(ka & kb - {None})


def resolve_kind(name: str, kind: str) -> tuple[str, bool]:
    """Retain out-of-vocabulary extractions; never mistake an unknown type for no action."""
    if not isinstance(kind, str) or not kind or not isinstance(name, str) or not name:
        raise ValueError('action name and kind must be nonempty strings')
    if kind in ('drug', 'procedure', 'diet', 'device', 'avoid'):
        return kind, False
    if kind == 'therapy' and therapy_type(name):
        return kind, False
    if AIRWAY_CLEARANCE.search(name):
        return 'procedure', False
    if re.search(r'\b(?:intravenous|iv)\s+fluids?\b|\b(?:surgery|transplant(?:ation)?|dialysis|lithotripsy|ureteroscopy)\b', name, re.I):
        return 'procedure', False
    if re.search(r'\b(?:fluid|water|oral)\s+intake\b|\b(?:hydration|diet|dietary)\b', name, re.I):
        return 'diet', False
    if re.search(r'\b(?:orthoses|orthosis|braces?|splints?|walkers?|wheelchairs?)\b', name, re.I):
        return 'device', False
    if kind in ('medication', 'medicine', 'pharmacotherapy'):
        return 'drug', False
    return 'other', True

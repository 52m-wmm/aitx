"""Shared patient matching retained unchanged for Steps 3b–3e; no Step 3a extraction."""
from __future__ import annotations
import re
from aitx.disease import datasets as D
from aitx.disease.hpo import Ontology
from aitx.evidence import agebands as AB
from aitx.evidence import variants as V
from aitx.evidence.branches import sex_fact

CHILD_YEARS = 12                      # pregnancy items: male or under 12 -> not applicable (decision 2026-11-03)

_ONT = None

def ontology() -> Ontology:
    global _ONT
    if _ONT is None:
        _ONT = Ontology(D.ensure("hpo_ontology"))
        for legacy in ("hpo_ontology_2022", "hpo_ontology_2024"):
            _ONT.add_former_names(D.ensure(legacy))
    return _ONT

def facts(step1: dict, step2: dict) -> dict:
    f = step2["patient_facts"]
    sex = sex_fact(step1, step2)
    return {"age_months": f["age"].get("months"), "age_quote": f["age"].get("quote"),
            "sex": sex["value"], "sex_quote": sex["quote"], "sex_inferred": sex["inferred"],
            "variants": [{"gene": v["gene"], "protein": v["variant_protein"], "class": v["variant_class"],
                          "zygosity": v["zygosity"], "quote": f"{v['gene']} {v['variant_cdna']} {v['variant_protein']} ({v['zygosity']})"}
                         for v in step1["variants"]],
            "present": [x for x in step2["phenotypes"] if x["status"] == "present"],
            "possible": [x for x in step2["phenotypes"] if x["status"] == "possible"],
            "excluded": [x for x in step2["phenotypes"] if x["status"] == "excluded"]}

VARIANT_CLASS_WORDS = ("missense", "nonsense", "frameshift", "synonymous", "splice", "inframe", "in-frame", "in_frame",
                       "start_loss", "start loss", "stop_gain", "stop gain", "deletion", "duplication", "insertion", "delins")

ZYGOSITY_WORDS = ("homozygous", "heterozygous", "hemizygous", "compound")

SECOND_ALLELE = re.compile(r"&|\+|\b(?:and|plus)\s+(?:a|an|one|another|1)\b", re.I)

_OR = re.compile(r"(?<!\d)(?<!\bone)(?<!\btwo)(?<!\bthree)\s+or\s+(?!older\b|younger\b|more\b|less\b|greater\b|above\b|"
                 r"below\b|over\b|under\b|\d|one\b|two\b|three\b|four\b)", re.I)   # "1 or 2 missense variants" is one requirement

def or_parts(text: str) -> list[str]:
    """Alternatives joined by "or" in one requirement ("... & a minimal function variant or other known responsive
    PV"); "2 years or older" is one requirement."""
    return [t.strip(" ,;") for t in _OR.split(text or "") if t.strip(" ,;")]

CLASS_GUARD = re.compile(r"\b(?:not|no|without|except|excluding|exclude[sd]?|other\s+than|unless|lacking)\b|\bnon[\s-]", re.I)

def zygosity_words(text: str) -> list[str]:
    low = (text or "").lower()
    return [w for w in ZYGOSITY_WORDS if re.search(rf"\b{w}", low)]

def _years(value, unit) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v / 12 if unit == "month" else v

def evaluate(req: dict, pf: dict, branch: dict) -> tuple[str, dict | None, str]:
    """(patient_status, patient_fact, note) for one requirement; code only."""
    field, op, value = req.get("field"), req.get("op"), req.get("value")
    if field == "age_band":
        return AB.limit_status(value, pf)
    if field == "age":
        need = _years(value, req.get("unit") or "year")
        if pf["age_months"] is None or need is None or op not in (">=", ">", "<=", "<"):
            return "unknown", None, "age not stated" if pf["age_months"] is None else "requirement not comparable"
        age = pf["age_months"] / 12
        ok = {">=": age >= need, ">": age > need, "<=": age <= need, "<": age < need}[op]
        return ("satisfies" if ok else "does_not_satisfy"), {"field": "age", "value": f"{age:g} years",
                                                            "quote": pf["age_quote"], "step": 2}, ""
    if field in ("variant", "variant_class", "zygosity"):
        vs = [v for v in pf["variants"] if v["gene"] == branch["gene"]] or pf["variants"]
        if not vs:
            return "unknown", None, "no variant"
        v = vs[0]
        fact = {"field": field, "value": v["protein"], "quote": v["quote"], "step": 1}
        zyg = zygosity_words(req["text"])
        if field == "variant_class":
            vals = [str(x).lower() for x in (value if isinstance(value, list) else [value]) if x]
            if not (vals and all(any(k in w for k in VARIANT_CLASS_WORDS) for w in vals)):
                low = req["text"].lower()        # the text's class words decide: guard the whole text before any split
                words = {k.replace("-", "").replace("_", "") for k in VARIANT_CLASS_WORDS if re.search(rf"(?<![a-z]){re.escape(k)}", low)}
                if len(words) != 1 or CLASS_GUARD.search(low):
                    return "unknown", fact, "requirement not comparable"
        parts = or_parts(req["text"])
        if len(parts) > 1:                   # "A or B": any part met is enough; a part that cannot be judged -> unknown
            got = [evaluate(dict(req, text=t), pf, branch) for t in parts]
            for want_st in ("satisfies", "unknown"):
                hit_ = next((g for g in got if g[0] == want_st), None)
                if hit_:
                    return hit_[0], hit_[1], f"one of {len(parts)} alternatives ('or'): {hit_[2]}"
            return got[0][0], got[0][1], f"none of {len(parts)} alternatives ('or') met"
        if field == "variant" or (field == "zygosity" and zyg and V.mentioned(v["protein"], req["text"])):
            # only the requirement's own words and the label tables it cites ("see Table 6"); never the whole label
            # (2026-11-04: Kalydeco mentions F508del in its trial descriptions; F508del is not ivacaftor-responsive)
            hit = V.mentioned(v["protein"], req["text"])
            where = ""
            if not hit:
                for n, table in (req.get("_label_tables") or {}).items():
                    hit = V.mentioned(v["protein"], table)
                    if hit:
                        where = f" in label Table {n}"
                        break
            if not hit:
                return "unknown", fact, "patient's variant not named in the requirement or the tables it cites"
            if not zyg:
                return "satisfies", fact, f"named as {hit}{where}"
            # the requirement states a zygosity (2026-11-04: "heterozygous for p.Phe508del & a minimal function
            # variant" had passed for a homozygous patient because only the variant name was compared)
            have = str(v.get("zygosity") or "").lower()
            if not have:
                return "unknown", dict(fact, field="zygosity"), "patient's zygosity not stated"
            fact = dict(fact, field="zygosity", value=f"{v['protein']} {have}")
            if not any(w in have for w in zyg):
                return "does_not_satisfy", fact, f"zygosity differs: requires {'/'.join(zyg)}"
            if SECOND_ALLELE.search(req["text"]) and "homozygous" not in zyg:
                return "unknown", fact, "second allele requirement not compared"
            return "satisfies", fact, f"named as {hit}{where}, {have}"
        want = [str(x).lower() for x in (value if isinstance(value, list) else [value]) if x]
        have = v["class"] if field == "variant_class" else v["zygosity"]
        if field == "zygosity" and (not have or have == "unknown"):
            return "unknown", fact, "patient's zygosity not stated"
        known = VARIANT_CLASS_WORDS if field == "variant_class" else ZYGOSITY_WORDS
        if field == "zygosity" and zyg and not all(any(k in w for k in known) for w in want):
            want = zyg                       # the value held something else (a variant name): use the requirement's words
        if field == "variant_class" and not (want and all(any(k in w for k in known) for w in want)):
            # empty or other value: the class word of the requirement's own text - only when there is exactly one and
            # no negating or narrowing word ("without missense", "non-missense", "missense or nonsense" stay unknown)
            low = req["text"].lower()
            words = {k.replace("-", "").replace("_", "") for k in known if re.search(rf"(?<![a-z]){re.escape(k)}", low)}
            if len(words) == 1 and not CLASS_GUARD.search(low):
                want = [next(k for k in known if re.search(rf"(?<![a-z]){re.escape(k)}", low))]
        if not want or not all(any(k in w for k in known) for w in want):
            return "unknown", fact, "requirement not comparable"
        return ("satisfies" if any(w.replace(" ", "_") in have or have in w for w in want) else "does_not_satisfy"), fact, ""
    if field == "sex" and pf["sex"] in ("male", "female"):
        want = str(value).lower()
        return ("satisfies" if want.startswith(pf["sex"][0]) else "does_not_satisfy"), \
            sex_evidence(pf), "sex inferred from X-chromosomal hemizygosity" if pf.get("sex_inferred") else ""
    if field == "diagnosis":
        d = branch.get("diagnosis") or {}
        names = [d.get("label", "")] + list(branch.get("synonyms") or [])
        ok = any(n and n.lower() in req["text"].lower() for n in names)
        return ("satisfies" if ok else "unknown"), {"field": "diagnosis", "value": d.get("label"),
                                                    "quote": d.get("label"), "step": 2}, ""
    return "unknown", None, f"{field or 'requirement'} not stated in the case"

POSSIBLE_FINDING = "finding stated only as possible"

_MSTOP = {"the", "and", "with", "of", "in", "to", "for", "or", "a", "an", "by", "due", "from", "on", "at", "as", "its",
          "their", "patients", "individuals", "persons", "signs", "symptoms", "management", "related", "associated"}

def _stem(w: str) -> str:
    w = w.lower()
    for suf, rep in (("ies", "y"), ("es", ""), ("s", "")):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + rep
    return w

def _covered(word: str, names: set[str]) -> bool:
    s = _stem(word)
    return any(s == n or (len(s) >= 5 and len(n) >= 5 and (s.startswith(n) or n.startswith(s))) for n in names)

def hpo_targets(text: str) -> tuple[set[str], str]:
    """The HPO terms a manifestation condition names, and the basis (user decision 2026-11-15): an exact HPO name or
    synonym; otherwise a retrieved term whose names contain every content word of the condition; otherwise none
    (the old rule took the top lexical hit, which made "crystal injury to kidneys" acute kidney injury)."""
    ont = ontology()
    ex = set(ont.exact_lookup(text))
    if ex:
        return ex, "exact HPO name or synonym"
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9-]+", text or "") if w.lower() not in _MSTOP]
    if words:
        for c in ont.search(text, 5):
            names = {_stem(w) for n in ont.names(c["hpo_id"]) for w in re.findall(r"[A-Za-z][A-Za-z0-9-]+", n)}
            if all(_covered(w, names) for w in words):
                return {c["hpo_id"]}, f"every word of the condition is in an HPO name of {c['hpo_id']}"
    return set(), "no HPO term covers every word of the condition"

def manifestation_match(text: str, pf: dict) -> tuple[str, dict | None, str]:
    """(status, patient fact, basis) for a manifestation condition; basis says how the HPO match was made."""
    ont = ontology()
    ids, basis = hpo_targets(text)
    for x in pf["present"]:
        if x["hpo_id"] in ids:
            return "satisfies", {"field": "manifestation", "value": x["label"], "quote": x["quote"], "step": 2,
                                 "match": {"hpo": x["hpo_id"], "relation": "same term", "basis": basis}}, basis
        hit = ids & set(ont.ancestors(x["hpo_id"]))
        if hit:
            return "satisfies", {"field": "manifestation", "value": x["label"], "quote": x["quote"], "step": 2,
                                 "match": {"hpo": x["hpo_id"], "relation": f"more specific than {sorted(hit)[0]}",
                                           "basis": basis}}, basis
    for x in pf["excluded"]:
        if x["hpo_id"] in ids:
            return "does_not_satisfy", {"field": "manifestation", "value": f"NOT {x['label']}", "quote": x["quote"],
                                        "step": 2}, basis
    for x in pf.get("possible") or []:      # stated only as one possibility: unknown, and said why (2026-11-12)
        if x["hpo_id"] in ids or ids & set(ont.ancestors(x["hpo_id"])):
            return "unknown", {"field": POSSIBLE_FINDING, "value": x["label"], "quote": x.get("possible_because") or x["quote"],
                               "step": 2}, basis
    return "unknown", None, basis

def manifestation_status(text: str, pf: dict) -> tuple[str, dict | None]:
    """Does the patient have the manifestation a supportive measure treats? HPO match by code."""
    st, fact, _ = manifestation_match(text, pf)
    return st, fact

def disease_names(branch: dict, step2: dict) -> list[str]:
    c = next((c for c in step2["candidates"] if c["key"] == branch["id"]), {})
    return [n for n in [c.get("label")] + list(c.get("synonyms") or []) if n]

def label_names(names: list[str]) -> list[str]:
    """Diagnosis names for label searches: OMIM titles join aliases with ";" ("epileptic encephalopathy, early
    infantile, 22; EIEE22"), which openFDA rejects (HTTP 400); each alias is its own name. Quotes are dropped."""
    out = [part.replace('"', "").strip() for n in names for part in str(n or "").split(";")]
    return [n for n in dict.fromkeys(out) if searchable_name(n)]

def searchable_name(name: str) -> bool:
    """Names used to search and match labels: not shorter than 4 characters, not a one-word abbreviation."""
    n = (name or "").strip()
    return len(n) >= 4 and not (" " not in n and n.upper() == n and len(n) <= 6)

def name_in(name: str, text: str) -> int | None:
    """Position of the diagnosis name in `text` as whole words (case-insensitive); "<X> deficiency" also matches
    "deficiency/deficiencies of ... <X>" in the same clause. None when absent."""
    low = re.sub(r"\s+", " ", text.lower())
    n = re.sub(r"\s+", " ", name.lower().strip())
    m = re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", low)
    if m:
        return m.start()
    core = re.fullmatch(r"(.+?) deficiency", n)
    if core:
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(core.group(1))}(?![a-z0-9])", low):
            if re.search(r"deficienc(?:y|ies) of\b[^.;•]{0,160}$", low[:m.start()]):
                return m.start()
    return None

_VAR_NAMES = {"kidney_function": "kidney function", "liver_function": "liver function", "variant_class": "variant type",
              "situation": "usage situation"}

def variable_type(field: str) -> str:
    """Missing-information row name for a patient fact field ("current medication: valproate" -> "current medication")."""
    f = str(field or "other").split(":")[0].strip()
    return _VAR_NAMES.get(f, f.replace("_", " "))

def sex_evidence(pf: dict) -> dict:
    return {"field": "sex", "value": pf["sex"], "quote": pf["sex_quote"],
            "step": 3 if pf.get("sex_inferred") else 2, **({"inferred": True} if pf.get("sex_inferred") else {})}

def pregnancy_status(pf: dict) -> tuple[str, dict | None]:
    """Pregnancy-specific management (decision 2026-11-03): male or under 12 -> not applicable;
    female 12 or older, or sex unknown and older than 12 -> conditional (pregnancy status unknown)."""
    age = pf["age_months"] / 12 if pf["age_months"] is not None else None
    if pf["sex"] == "male":
        return "does_not_satisfy", sex_evidence(pf)
    if age is not None and age < CHILD_YEARS:
        return "does_not_satisfy", {"field": "age", "value": f"{age:g} years", "quote": pf["age_quote"], "step": 2}
    return "unknown", {"field": "pregnancy status", "value": None, "quote": None, "step": None}

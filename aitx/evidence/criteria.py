"""Step 3b: trial criteria, one by one (contract docs/step3b_contract.md, step 5).

  code  splits EligibilityCriteria into items (trials.split_criteria; inclusion / exclusion comes from the headings)
  LLM   maps each item to {fact, op, value, unit} with an exact quote from that item; never judges the patient
  code  verifies every mapping (quote verbatim in its item, every threshold number in the quote, comparison sign as
        written: >= vs >), compares it with the patient facts, and groups "one of the following" items

Results (decision 2026-11-04): inclusion not met -> not applicable; exclusion met -> not applicable; any unknown ->
conditional, with what is missing; administrative -> not_assessed ("screening assessment", no effect); a criterion
that cannot be mapped and verified -> not_assessed ("not mapped; shown verbatim"), shown as written.
"""
from __future__ import annotations

import json
import re
import time

from aitx.disease import extract as X
from aitx.evidence import derived as DV
from aitx.evidence import established as E
from aitx.evidence import labs as LABS
from aitx.evidence import ledger as LG
from aitx.evidence import patient_facts as PFX
from aitx.evidence import trials as T

PROMPT_VERSION = "3b-criteria-v1"
FACTS = ("age", "sex", "diagnosis", "genetic_confirmation", "variant", "variant_class", "zygosity", "lab", "egfr",
         "organ_function", "weight", "gestational_age", "current_medication", "prior_therapy", "other_trial",
         "pregnancy", "administrative", "header", "other")
OPS = (">=", ">", "<=", "<", "==", "")

SYSTEM = """You map the eligibility criteria of one clinical trial to structured fields. Each criterion has an id.
Do not judge any patient. For each criterion return one or more items (one per separate condition in it):
{"id": "<criterion id>", "quote": "<the exact words of this condition, copied character for character from that criterion>",
 "fact": "age" | "sex" | "diagnosis" | "genetic_confirmation" | "variant" | "variant_class" | "zygosity" | "lab" | "egfr" |
         "organ_function" | "weight" | "gestational_age" | "current_medication" | "prior_therapy" | "other_trial" |
         "pregnancy" | "administrative" | "header" | "other",
 "op": ">=" | ">" | "<=" | "<" | "==" | "",
 "value": <the threshold number exactly as written, a list of strings, or "">,
 "unit": "<unit exactly as written, or empty>",
 "name": "<lab analyte, organ, drug or therapy, gene, or 'normal' / 'abnormal' for organ function; or empty>",
 "group": "<id of the criterion that says 'one of the following' when this condition is one of its options; else empty>"}
fact: lab = a lab value with a threshold; egfr = estimated GFR or creatinine clearance; organ_function = adequate or
impaired liver / kidney / heart function without a number (name "normal" or "abnormal"); other_trial = participation
in another clinical trial; pregnancy = pregnancy, breastfeeding or contraception (name "contraception" when it asks
for contraception); administrative = consent, assent, willingness or ability to comply, travel or attend visits;
header = a line that only introduces the items below it. Keep the comparison exactly as written (">=" only for
"greater than or equal", "at least", "or older"; ">" for "greater than", "more than", "older than"). Return only JSON:
{"criteria": [...]}"""


# ------------------------------------------------------------------ LLM mapping and its verification

def _llm(user: str, use_cache: bool, what: str) -> tuple[dict, dict]:
    t = time.time()
    r = X._cached_chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], 0, use_cache,
                       prompt_version=PROMPT_VERSION)
    if time.time() - t > 1:
        print(f"[3b] LLM criteria {what}: {time.time() - t:.0f}s, prompt {len(user)} chars", flush=True)
    return X._parse(r)["parsed"], {"llm": X.llm.config()["model"], "served_model": r.get("served_model"),
                                   "prompt_version": PROMPT_VERSION}


def items_for_llm(items: list[dict]) -> str:
    return "\n".join(f"[{it['id']}] ({it['kind']}) {T.unescape(it['text'])}" for it in items if not it.get("preamble"))


_RANGE = re.compile(r"\d\s*(?:-|–|—|to|through)\s*\d", re.I)       # "10 to 17", "0-90": inclusive on both ends
_GE = re.compile(r"≥|>=|\bat least\b|\b(?:or|and)\s+(?:older|above|over)\b|\bor more\b|\bor greater\b|\bminimum\b|\binclusive\b", re.I)
_LE = re.compile(r"≤|<=|\bat most\b|\b(?:or|and)\s+(?:younger|under|below)\b|\bor less\b|\bup to\b|\bmaximum\b|\bno more than\b|\bnot exceeding\b|\binclusive\b", re.I)
_GT = re.compile(r"(?<![<≤])>(?!=)|\bgreater than\b|\bmore than\b|\bover\b|\babove\b|\bolder than\b|\bexceed", re.I)
_LT = re.compile(r"(?<![>≥])<(?!=)|\bless than\b|\bunder\b|\bbelow\b|\byounger than\b|\blower than\b", re.I)


def sign_ok(op: str, quote: str) -> bool:
    """The comparison sign must be the one written (>= vs >): a sign is accepted when the quote has its cue and
    no cue of a different strictness in the same direction."""
    if op in ("", "=="):
        return True
    rng = bool(_RANGE.search(quote))
    ge, le = bool(_GE.search(quote)) or rng, bool(_LE.search(quote)) or rng
    gt = bool(_GT.search(_GE.sub(" ", quote)))
    lt = bool(_LT.search(_LE.sub(" ", quote)))
    return {">=": ge, ">": gt and not ge, "<=": le, "<": lt and not le}[op]


def _numbers(value) -> list[float]:
    vals = value if isinstance(value, list) else [value]
    out = []
    for v in vals:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(float(v))
        elif isinstance(v, str) and re.fullmatch(r"\s*-?\d+(?:\.\d+)?\s*", v):
            out.append(float(v))
    return out


def check_mapping(m: dict, items: dict[str, dict]) -> str | None:
    """Why a mapping is rejected, or None. Code only."""
    it = items.get(str(m.get("id")))
    if not it or it.get("preamble"):
        return "unknown criterion id"
    fact, quote = m.get("fact"), str(m.get("quote") or "")
    if fact not in FACTS:
        return f"unknown fact type {fact!r}"
    if m.get("op", "") not in OPS:
        return f"unknown comparison {m.get('op')!r}"
    if not LG.quote_in(quote, T.unescape(it["text"])):
        return "quote not verbatim in the criterion"
    in_quote = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", quote)]
    for n in _numbers(m.get("value")):
        if not any(abs(n - q) < 1e-9 for q in in_quote):
            return f"threshold {n:g} not in the quote"
    if m.get("op") in ("<", "<=", ">", ">=") and not _numbers(m.get("value")) and fact not in ("variant", "variant_class", "zygosity"):
        return "comparison without a threshold"
    if not sign_ok(m.get("op", ""), quote):
        return f"comparison {m.get('op')!r} not as written"
    if m.get("unit") and not re.search(rf"(?<![A-Za-zµμ]){re.escape(str(m['unit']).strip())}(?![A-Za-z])", quote):
        return "unit not in the quote"              # whole unit: "g/dL" is not in "mg/dL"
    return None


_ANY_OF = re.compile(r"\b(?:one|any|either|at least one|1)\s+(?:or more\s+)?of\s+the\s+following\b|\beither\b", re.I)


def map_study(study: dict, *, use_cache: bool = True) -> dict:
    """{items, mappings (verified), rejected, produced_by} for one study."""
    items = T.split_criteria(study.get("criteria") or "")
    by_id = {it["id"]: it for it in items}
    if not [i for i in items if not i.get("preamble")]:
        return {"items": items, "mappings": [], "rejected": [], "produced_by": "code"}
    parsed, pb = _llm(f"Trial {study['nct']} eligibility criteria:\n{items_for_llm(items)}", use_cache, study["nct"])
    ok, rejected = [], []
    for m in parsed.get("criteria") or []:
        if not isinstance(m, dict):
            continue
        why = check_mapping(m, by_id)
        (rejected if why else ok).append({**m, **({"rejected": why} if why else {})})
    for m in ok:                         # a group is kept only if the code's tree agrees and the parent says "one of"
        g = str(m.get("group") or "")
        it = by_id[str(m["id"])]
        if g and not (g == it.get("parent") and g in by_id and _ANY_OF.search(T.unescape(by_id[g]["text"]))):
            m["group_ignored"] = g
            m["group"] = ""
    return {"items": items, "mappings": ok, "rejected": rejected, "produced_by": pb}


# ------------------------------------------------------------------ comparison (code only)

def _cmp(a: float, op: str, b: float) -> bool:
    return {">=": a >= b, ">": a > b, "<=": a <= b, "<": a < b, "==": abs(a - b) < 1e-9}[op]


def _unk(var: str, note: str) -> tuple[str, dict, str, dict]:
    return "unknown", {"field": var, "value": None, "quote": None, "step": None}, note, {}


AGE_BY_REGISTRY = LG.AGE_BY_REGISTRY_NOTE
_ANY_SEX = re.compile(r"\b(?:all|both|any)\s+(?:genders?|sexes)\b|\bmales?\s*(?:and|or|/|&)\s*females?\b|"
                      r"\bfemales?\s*(?:and|or|/|&)\s*males?\b|\bregardless\s+of\s+(?:gender|sex)\b", re.I)


def evaluate(m: dict, pf: dict, extra: dict, branch: dict, names: list[str], kind: str = "inclusion"
             ) -> tuple[str, dict | None, str, dict]:
    """(patient_status, patient_fact, note, details) for one verified mapping; kind = inclusion / exclusion."""
    fact, op, quote = m["fact"], m.get("op", ""), m["quote"]
    nums = _numbers(m.get("value"))
    if fact == "administrative":
        return "not_assessed", None, LG.NOT_ASSESSED_NOTE, {}
    if fact == "sex" and _ANY_SEX.search(quote):
        return "satisfies", {"field": "sex", "value": pf["sex"] or "any", "quote": quote, "step": "3b"}, "any sex", {}
    if fact == "age":
        # cohorts ("adolescents >= 12", "children 6 to 11", "children 2 to 5") make text age clauses alternatives the
        # item tree does not show; age is decided by the registry minimumAge / maximumAge lines (decision 2026-11-04)
        return "not_assessed", None, AGE_BY_REGISTRY, {}
    if fact in ("sex", "variant", "variant_class", "zygosity"):
        req = {"field": fact, "op": op, "value": nums[0] if fact == "age" and nums else m.get("value"),
               "unit": _age_unit(m.get("unit") or quote), "text": quote}
        st, fct, note = E.evaluate(req, pf, branch)
        if st == "unknown" and not (fct or {}).get("field"):
            fct = {"field": fact, "value": None, "quote": None, "step": None}     # the variable that is missing
        return st, fct, note, {}
    if fact == "diagnosis":
        hit = next((n for n in E.label_names(names) if E.name_in(n, quote) is not None), None)
        if hit and kind == "exclusion":       # the branch disease named in an exclusion is context ("not related to CF",
            return _unk("diagnosis", "exclusion mentions the branch disease as context; not compared")   # "CF exacerbation")
        return ("satisfies", {"field": "diagnosis", "value": hit, "quote": hit, "step": 2}, "diagnosis named", {}) if hit \
            else _unk("diagnosis", "the criterion names another diagnosis or none of the branch names")
    if fact == "genetic_confirmation":
        gene = branch.get("gene") or ""
        vs = [v for v in pf["variants"] if v["gene"] == gene]
        named = (gene and re.search(rf"(?<![A-Za-z0-9]){re.escape(gene)}(?![A-Za-z0-9])", quote)) or \
            any(E.name_in(n, quote) is not None for n in names)
        if vs and named:
            return "satisfies", {"field": "variant", "value": vs[0]["protein"], "quote": vs[0]["quote"], "step": 1}, \
                f"{gene} variant reported", {}
        return _unk("genetic confirmation", "gene or diagnosis in the criterion not matched to the reported variants")
    if fact == "lab":
        return _lab(m, nums, extra)
    if fact == "egfr":
        return _egfr(m, nums, pf, extra)
    if fact == "organ_function":
        organ = next((o for o in ("liver", "hepatic", "kidney", "renal", "cardiac", "heart") if o in quote.lower()), None)
        organ = {"hepatic": "liver", "renal": "kidney", "heart": "cardiac"}.get(organ, organ)
        if not organ:
            return _unk("organ function", "organ not named")
        fs = [f for f in PFX.find(extra, "organ_function") if organ in (f["name"] + " " + f["quote"]).lower()
              or (organ == "liver" and "hepat" in f["quote"].lower()) or (organ == "kidney" and "renal" in f["quote"].lower())]
        want = (m.get("name") or "").lower()
        if not fs or want not in ("normal", "abnormal") or fs[0]["status"] not in ("normal", "abnormal"):
            return _unk(f"{organ} function", "not stated in the case" if not fs else "criterion not comparable")
        f = fs[0]
        return ("satisfies" if f["status"] == want else "does_not_satisfy"), \
            {"field": f"{organ} function", "value": f["status"], "quote": f["quote"], "step": "3b"}, "", {}
    if fact == "gestational_age":
        fs = [f for f in PFX.find(extra, "gestational_age") if f["value"] is not None]
        if not fs or not nums or not op:
            return _unk("gestational age", "not stated in the case" if not fs else "criterion not comparable")
        v = float(fs[0]["value"])
        return ("satisfies" if _cmp(v, op, nums[0]) else "does_not_satisfy"), \
            {"field": "gestational age", "value": f"{v:g} weeks", "quote": fs[0]["quote"], "step": "3b"}, "", {}
    if fact in ("current_medication", "prior_therapy"):
        name = (m.get("name") or "").strip()
        fs = [f for f in PFX.find(extra, fact) if name and (name.lower() in f["name"].lower() or f["name"].lower() in name.lower())]
        if not fs:
            return _unk(fact.replace("_", " ") + (f": {name}" if name else ""), "not stated in the case")
        f = fs[0]
        return ("does_not_satisfy" if f["status"] == "absent" else "satisfies"), \
            {"field": fact.replace("_", " "), "value": f"{f['name']} ({f['status'] or 'present'})", "quote": f["quote"], "step": "3b"}, "", {}
    if fact == "other_trial":
        fs = PFX.find(extra, "other_trial")
        if not fs or fs[0]["status"] not in ("absent", "present"):
            return _unk("participation in other trials", "not stated in the case")
        f = fs[0]
        return ("does_not_satisfy" if f["status"] == "absent" else "satisfies"), \
            {"field": "other trials", "value": f["status"], "quote": f["quote"], "step": "3b"}, "", {}
    if fact == "pregnancy":
        # male or under 12: a pregnancy / contraception criterion does not apply - it never excludes the patient and
        # never fails an inclusion (2026-11-04: "unwilling to use contraception" had excluded a 7-year-old boy)
        st, fct = E.pregnancy_status(pf)
        if st == "does_not_satisfy":
            return ("does_not_satisfy" if kind == "exclusion" else "satisfies"), fct, \
                "pregnancy / contraception criterion does not apply (male or under 12)", {}
        return _unk("pregnancy status", "pregnancy status unknown")
    if fact == "weight":
        return _unk("weight", "not stated in the case")
    return _unk(f"other: {quote[:60]}", "no patient fact of this kind")


def _age_unit(text: str) -> str:
    low = str(text).lower()
    return "month" if "month" in low else "week" if "week" in low else "day" if "day" in low else "year"


def _lab(m: dict, nums: list[float], extra: dict) -> tuple[str, dict | None, str, dict]:
    table = LABS.load()
    analyte = LABS.analyte_of(m.get("name") or "", table) or LABS.analyte_of(m["quote"], table)
    if not analyte or not nums or not m.get("op"):
        return _unk(f"lab: {m.get('name') or m['quote'][:40]}", "analyte or threshold not comparable")
    fs = [f for f in PFX.find(extra, "lab") if f.get("analyte") == analyte and f["value"] is not None]
    if not fs:
        return _unk(analyte, "not stated in the case")
    f = fs[0]
    thr = LABS.interpret(analyte, nums[0], m.get("unit") or None, table=table, who="threshold")
    pat = f["interpretation"]
    st = LABS.compare(pat, m["op"], thr)
    sc = LABS.scenarios(pat, m["op"], thr)
    notes = [x for x in (thr.get("assumption"), pat.get("assumption"), thr.get("why") if thr["status"] == "unknown" else None,
                         pat.get("why") if pat["status"] == "unknown" else None) if x]
    fact = {"field": analyte, "value": f"{f['value']}{(' ' + f['unit']) if f['unit'] else ''}", "quote": f["quote"], "step": "3b"}
    return st, fact, "; ".join(notes), {"lab": {"patient": pat, "threshold": thr, "scenarios": sc}}


def _egfr(m: dict, nums: list[float], pf: dict, extra: dict) -> tuple[str, dict | None, str, dict]:
    if not nums or not m.get("op"):
        return _unk("eGFR", "threshold not comparable")
    cr = [f for f in PFX.find(extra, "lab") if f.get("analyte") == "creatinine" and f["interpretation"]["status"] in ("ok", "assumed")]
    if not cr:
        return _unk("eGFR", "no creatinine stated in the case")
    scr = cr[0]["interpretation"]["value"]                     # canonical mg/dL
    age = pf["age_months"] / 12 if pf["age_months"] is not None else None
    d = DV.egfr(scr, age, pf["sex"], None)                     # height is never assumed
    if d["value"] is None:
        return _unk("eGFR", "cannot be derived: missing " + ", ".join(d["missing"]))
    st = "satisfies" if _cmp(d["value"], m["op"], nums[0]) else "does_not_satisfy"
    return st, {"field": "eGFR (derived)", "value": f"{d['value']} {d['unit']}", "quote": cr[0]["quote"], "step": "3b"}, \
        f"derived by {d['formula']}", {"derived": d}


# ------------------------------------------------------------------ requirement lines

def combine(statuses: list[str]) -> str:
    """'One of the following': any option met -> met; else any unknown -> unknown; else not met."""
    if "satisfies" in statuses:
        return "satisfies"
    if "unknown" in statuses:
        return "unknown"
    return "does_not_satisfy" if statuses else "unknown"


def lines_for(study: dict, mapped: dict, pf: dict, extra: dict, branch: dict, names: list[str]) -> list[dict]:
    """Per-criterion results for one branch, before evidence ids are attached:
    [{kind, text, patient_status, patient_fact, note, details, any_of?, item}]."""
    items = {it["id"]: it for it in mapped["items"]}
    by_item: dict[str, list[dict]] = {}
    for m in mapped["mappings"]:
        by_item.setdefault(str(m["id"]), []).append(m)
    out, groups = [], {}
    for it in mapped["items"]:
        if it.get("preamble") or it["kind"] not in ("inclusion", "exclusion"):
            continue
        ms = [m for m in by_item.get(it["id"], []) if m["fact"] != "header"]
        if not ms:
            has_children = any(x.get("parent") == it["id"] for x in mapped["items"])
            if any(m["fact"] == "header" for m in by_item.get(it["id"], [])) or (has_children and not by_item.get(it["id"])
                                                                                 and _ANY_OF.search(T.unescape(it["text"]))):
                continue                                         # a heading; its sub-items carry the conditions
            out.append({"kind": it["kind"], "text": T.unescape(it["text"]), "patient_status": "not_assessed",
                        "patient_fact": None, "note": LG.UNMAPPED_NOTE, "details": {}, "item": it["id"]})
            continue
        for m in ms:
            st, fct, note, det = evaluate(m, pf, extra, branch, names, it["kind"])
            line = {"kind": it["kind"], "text": m["quote"], "patient_status": st,
                    "patient_fact": None if st == "not_assessed" else fct, "note": note, "details": det,
                    "item": it["id"], "fact": m["fact"]}
            if m.get("group"):
                groups.setdefault(m["group"], []).append(line)
            else:
                out.append(line)
    for g, opts in groups.items():
        parent = items[g]
        sts = [o["patient_status"] for o in opts if o["patient_status"] != "not_assessed"]
        st = combine(sts) if sts else "not_assessed"
        unk = [o for o in opts if o["patient_status"] == "unknown"]
        out.append({"kind": parent["kind"], "text": T.unescape(parent["text"]), "patient_status": st,
                    "patient_fact": None if st == "not_assessed" else (unk[0]["patient_fact"] if st == "unknown" and unk else
                                                                        next((o["patient_fact"] for o in opts if o["patient_status"] == st), None)),
                    "note": LG.UNMAPPED_NOTE if st == "not_assessed" else f"one of {len(opts)} options",
                    "details": {}, "item": g,
                    "any_of": [{"requirement": o["text"], "patient_status": o["patient_status"], "note": o["note"]} for o in opts]})
    return out


def registry_lines(study: dict, pf: dict) -> list[dict]:
    """Registry age / sex / healthy-volunteer fields (structured) as inclusion lines."""
    pre = study.get("prefilter") or T.prefilter(study, pf["age_months"], pf["sex"])
    out = []
    for c in pre["checks"]:
        st = {"pass": "satisfies", "fail": "does_not_satisfy", "unknown": "unknown"}[c["result"]]
        text = registry_text(study, c["field"])
        fact = ({"field": "age", "value": f"{pf['age_months'] / 12:g} years", "quote": pf["age_quote"], "step": 2}
                if c["field"] == "age" and pf["age_months"] is not None else
                {"field": "sex", "value": pf["sex"], "quote": pf["sex_quote"], "step": 2}
                if c["field"] == "sex" and pf["sex"] else
                {"field": c["field"], "value": None, "quote": None, "step": None})
        out.append({"kind": "inclusion", "text": text, "patient_status": st, "patient_fact": fact,
                    "note": "registry field", "details": {}, "item": f"registry:{c['field']}"})
    return out


def registry_source(study: dict) -> str:
    return (f"minimumAge: {study.get('min_age') or 'none'}; maximumAge: {study.get('max_age') or 'none'}; "
            f"sex: {study.get('sex') or 'ALL'}; healthyVolunteers: {json.dumps(study.get('healthy_volunteers'))}; "
            f"conditions: {'; '.join(study.get('conditions') or [])}")


def registry_text(study: dict, field: str) -> str:
    return {"age": f"minimumAge: {study.get('min_age') or 'none'}; maximumAge: {study.get('max_age') or 'none'}",
            "sex": f"sex: {study.get('sex') or 'ALL'}",
            "healthy_volunteers": f"conditions: {'; '.join(study.get('conditions') or [])}"}[field]

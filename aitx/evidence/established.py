"""Step 3a: established tier (contract docs/step3a_contract.md).

Existing Targeted Therapies, Supportive Management, Contraindications & Precautions, per diagnosis branch.

  sources     GeneReviews Management sections (local archive; never Surveillance or Therapies Under
              Investigation) and FDA labels (openFDA: by indication, by drug name, by contraindication)
  LLM         only picks chapters for a diagnosis from a numbered list, and lifts therapies and requirement
              sentences verbatim from texts code supplies; it never writes ids, sources or verdicts
  code        verifies every quote, normalizes actions (3.0 action keys), places them in sections by the
              contract rules, compares requirements with the patient facts (age, variant, zygosity, phenotype),
              derives each branch's status, writes action records and negative evidence
"""
from __future__ import annotations

import difflib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor

from aitx.disease import datasets as D
from aitx.disease import extract as X
from aitx.disease.hpo import Ontology
from aitx.evidence import actions as A
from aitx.evidence import agebands as AB
from aitx.evidence import context_check as CC
from aitx.evidence import fallback as F
from aitx.evidence import genereviews as GR
from aitx.evidence import labels as LB
from aitx.evidence import ledger as LG
from aitx.evidence import support_check as SC
from aitx.evidence import variants as V
from aitx.evidence.branches import sex_fact

PROMPT_VERSION = "3a-v6"          # v3: table rows with headers, usage situations, purpose clauses; v4: therapy programs; v5: paragraph context, row coverage (2026-11-04)
SECTIONS_3A = ("existing_targeted_therapies", "supportive_management", "contraindications_precautions")
SKIP_SECTIONS = ("surveillance", "therapies under investigation", "evaluations following initial diagnosis",
                 "evaluation of relatives at risk")
TARGETED_TITLES = ("targeted therapies", "targeted therapy")
REQ_FIELDS = ("age", "sex", "variant", "variant_class", "zygosity", "kidney_function", "liver_function", "weight", "situation")
SITUATION_NOTE = "usage situation; not compared with the patient"
NOT_A_THERAPY = {"supportive care", "targeted therapies", "targeted therapy", "treatment", "management",
                 "treatment of manifestations", "therapy", "care"}
CHILD_YEARS = 12                      # pregnancy items: male or under 12 -> not applicable (decision 2026-11-03)
MISSING_MANIFESTATIONS = "manifestations not reported"

CHAPTERS_SYSTEM = """You match diagnoses to GeneReviews chapters. For each numbered diagnosis, list the numbers of the
chapters whose subject is that diagnosis or a broader disorder group that includes it. A chapter about a different
disorder caused by the same gene does not count. Return only JSON:
{"links": [{"diagnosis": <number>, "chapters": [<chapter numbers>]}]}"""

_REQ_SHAPE = """{"text": "<exact words>", "field": "age" | "sex" | "variant" | "variant_class" | "zygosity" |
 "kidney_function" | "liver_function" | "weight" | "situation", "op": ">=" | "<=" | ">" | "<" | "==" | "in" | "",
 "value": <number or list of strings or "">, "unit": "year" | "month" | ""}"""

EXTRACT_SYSTEM = """You list the management actions in one GeneReviews Management section. Use only the text given.
List only specific treatments: a named drug, a procedure, a diet, a device, a therapy or intervention program
(early intervention, physical / occupational / speech / feeding therapy, developmental preschool, special education
services) - or, in a section about agents or circumstances to avoid, each agent or circumstance to avoid. A referral
to RECEIVE a therapy or intervention program is listed with kind "therapy" and the program's name as written
("Referral to an early intervention program" -> "early intervention program"). Do not list section headings,
symptoms, conditions, tests, surveillance, follow-up, or referrals for evaluation, consultation or counseling
(specialist evaluation, genetic counseling). For each, return one item:
{"name": "<generic drug name or short procedure / program name, no brand names, no doses>",
 "kind": "drug" | "procedure" | "diet" | "device" | "therapy" | "avoid",
 "quote": "<the exact sentence or table row that names it, copied character for character>",
 "manifestation": "<the exact words naming the symptom or complication it treats, or empty>",
 "requirements": [<restrictions on WHICH PATIENTS should get it, by a patient characteristic; each """ + _REQ_SHAPE + """>],
 "mechanism_quote": "<exact words saying it acts on the defective gene product or disease mechanism, or empty>"}
Requirements describe the PATIENT: age, sex, variant / genotype, variant type, zygosity, kidney or liver function,
weight - or the situation in which it is used ("situation": "as needed", "if needed", "during acute episodes", "in
kidney failure", "after transplantation"). Copy their words exactly from the item's table row or sentence. A purpose or
mechanism clause ("to reduce oxalate", "to inhibit ...", "which lowers ...") is never a requirement.
Paragraphs may be annotated with chapter or subheading context. Do not infer requirements or manifestations
from those annotations, section titles, or other paragraphs. Code adds population headings independently.
Extract only patient restrictions explicitly stated in the complete sentence naming this action (or its own
complete table row). A reason such as "because of the risk of X", or a purpose such as "to prevent X", does
not mean the patient already has X. Do not copy a prevention target or risk rationale into manifestation.
Tables are shown one row per line, each cell labelled with its column header: "Row 3: [Manifestation: Kidney stones]
[Treatment: ...] [Considerations/Other: ...]". The requirements of an item may be in any cell of its row, including the
row's first column (the manifestation or concern it treats); the quote is the text of the cell that names the item,
copied without the bracket labels. Return only JSON: {"items": [...]}. Do not invent items or words."""

REQ_SYSTEM = """You list the requirements in an FDA drug label that restrict who may receive the drug for the given
disease. Use only the label text given; copy each requirement's words exactly. Requirements are restrictions by age,
sex, required variants or genotypes, variant type, zygosity, kidney or liver function, or weight. "Pediatric and adult
patients" with no number is not an age restriction; the disease itself is not a requirement. Return only JSON:
{"requirements": [""" + _REQ_SHAPE + """]}"""


def _llm(system: str, user: str, use_cache: bool, what: str = "") -> tuple[dict, dict]:
    t = time.time()
    r = X._cached_chat([{"role": "system", "content": system}, {"role": "user", "content": user}], 0, use_cache,
                       prompt_version=PROMPT_VERSION)
    if time.time() - t > 1:                     # only real calls are logged (cache hits are instant)
        print(f"[3a] LLM {what or 'call'}: {time.time() - t:.0f}s, prompt {len(user)} chars", flush=True)
    return X._parse(r)["parsed"], {"llm": X.llm.config()["model"], "served_model": r.get("served_model"), "call_id": r.get("call_id"),
                                   "prompt_version": PROMPT_VERSION}


_ONT = None


def ontology() -> Ontology:
    global _ONT
    if _ONT is None:
        _ONT = Ontology(D.ensure("hpo_ontology"))
        for legacy in ("hpo_ontology_2022", "hpo_ontology_2024"):
            _ONT.add_former_names(D.ensure(legacy))
    return _ONT


# ------------------------------------------------------------------ patient facts

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


# values a variant_class / zygosity requirement can be compared on; anything else is unknown, never "not met"
VARIANT_CLASS_WORDS = ("missense", "nonsense", "frameshift", "synonymous", "splice", "inframe", "in-frame", "in_frame",
                       "start_loss", "start loss", "stop_gain", "stop gain", "deletion", "duplication", "insertion", "delins")
ZYGOSITY_WORDS = ("homozygous", "heterozygous", "hemizygous", "compound")


# a precaution describes whom to avoid; only then does "the patient has it" make the action not applicable
PRECAUTION_AVOID = re.compile(r"\b(?:not|avoid|contraindicated|should\s+not|must\s+not|do\s+not)\b", re.I)
SECOND_ALLELE = re.compile(r"&|\+|\b(?:and|plus)\s+(?:a|an|one|another|1)\b", re.I)


_OR = re.compile(r"(?<!\d)(?<!\bone)(?<!\btwo)(?<!\bthree)\s+or\s+(?!older\b|younger\b|more\b|less\b|greater\b|above\b|"
                 r"below\b|over\b|under\b|\d|one\b|two\b|three\b|four\b)", re.I)   # "1 or 2 missense variants" is one requirement


def or_parts(text: str) -> list[str]:
    """Alternatives joined by "or" in one requirement ("... & a minimal function variant or other known responsive
    PV"); "2 years or older" is one requirement."""
    return [t.strip(" ,;") for t in _OR.split(text or "") if t.strip(" ,;")]


def label_tables(full_text: str, text: str) -> dict[str, str]:
    """The label tables a requirement cites ("see Table 6"): from the table's caption ("Table 6:") to the next caption."""
    out = {}
    for n in dict.fromkeys(re.findall(r"\bTable\s+(\d+)\b", text or "")):
        m = re.search(rf"\bTable\s+{n}\s*:", full_text or "")
        if m:
            nxt = re.search(r"\bTable\s+(?!" + n + r"\b)\d+\s*:", full_text[m.end():])
            out[n] = full_text[m.start(): m.end() + (nxt.start() if nxt else 8000)][:12000]
    return out


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


# preventive wording (user decision 2026-11-15): a condition that is what the measure prevents or reduces is its
# purpose, not something the patient must have; "Treat / Manage / Control X" keeps X as a condition
PREVENTIVE = re.compile(r"^\W*(?:context:\s*|Objective:\s*)?(prevent|prevention of|reduce|decrease|inhibit|minimi[sz]e|"
                        r"lower|limit)\b", re.I)


PREVENTIVE_BEFORE = re.compile(r"\b(prevent|prevention of|reduce|reduction of|decrease|inhibit|inhibition of|"
                               r"minimi[sz]e|lower|limit)\s+(?:the\s+)?$", re.I)


ROW_CONCERN = re.compile(r"\[(?:Manifestation|Concern|Problem)[^:\]]*:\s*([^\]]+)\]", re.I)
SITUATION = re.compile(r"\b(?:during|when|whenever|while|in periods of|in case of|in the event of)\b[^.;:,\]\[]{3,}",
                       re.I)
HEDGE = re.compile(r"^(?:when|if)\s+(?:possible|appropriate|feasible|available|practical|tolerated)\b", re.I)
MECHANISM_WHEN = re.compile(r"^when\b.*\breplaces?\b", re.I)
TREATMENT_CELL = re.compile(r"\[(?:Treatment|Intervention|Management)[^:\]]*:\s*([^\]]+)\]", re.I)


def situational_phrases(spec: dict, label: str | None = None) -> list[str]:
    """"during / when / in periods of ..." phrases in the treatment cell (table row) or the sentence (paragraph) that
    holds the entry's quote - deterministic, verbatim."""
    out = []
    passages = context_passages(spec)
    # A treatment-cell quote identifies its row; prose that merely names the action is not its source paragraph.
    rows = [(h, p) for h, p in passages if any(LG.quote_in(spec["quote"], m.group(1))
                                             for m in TREATMENT_CELL.finditer(p))]
    for _, p in rows or passages:
        if not LG.quote_in(spec["quote"], p):
            continue
        cell = None
        for m in TREATMENT_CELL.finditer(p):
            if LG.quote_in(spec["quote"], m.group(1)):
                cell = m.group(1)
        if cell is None:          # a paragraph: the clause (between semicolons) of the quote's own sentence
            body = p.split("]: ", 1)[-1] if "]: " in p else p.split(": ", 1)[-1]
            sent = next((s for s in re.split(r"(?<=[.!?])\s+", body) if LG.quote_in(spec["quote"][:60], s)), "")
            clause = sent if ";" in spec["quote"] else \
                next((c for c in sent.split(";") if LG.quote_in(spec["quote"][:40], c)), "")
            # only the entry's own list item: the item holding its name (or the quote), up to the next comma
            i = clause.lower().find(spec["quote"][:40].lower())
            j = clause.lower().find((label or "").lower(), max(i, 0)) if label else -1
            if i < 0:
                cell = ""
            elif j >= 0:
                start = max(clause.rfind(c, 0, j) for c in ",;(") + 1
                nxt = re.search(r"[,;)]", clause[j + len(label):])
                cell = clause[start:j + len(label) + (nxt.start() if nxt else len(clause))]
            else:
                end = i + len(spec["quote"])
                nxt = re.search(r"[,;]", clause[end:])
                cell = clause[i:end + (nxt.start() if nxt else len(clause) - end)]
        for m in SITUATION.finditer(cell or ""):
            ph = m.group(0).strip()
            if HEDGE.search(ph) or MECHANISM_WHEN.search(ph) or LG.quote_in(spec["quote"], ph):
                continue                  # "when possible" is not a situation; the quote itself is not its own condition
            if ph not in out:
                out.append(ph)
    return out


def is_purpose(text: str, passage) -> bool:
    """The condition text sits right after a preventive word in its passage(s) ("Objective: Prevent crystal injury to
    kidneys", "aims to prevent crystal injury to kidneys", "[context: Reduce calcium oxalate crystallization ...]") or
    is a preventive phrase itself - and no passage presents it as a manifestation that is treated
    ("Manifestation/Concern: X", "Treat X")."""
    if PREVENTIVE.search(text or ""):
        return True
    passages = [passage] if isinstance(passage, str) else list(passage or [])
    low = (text or "").lower()
    preventive = treated = False
    for p in passages:
        i = (p or "").lower().find(low)
        while i >= 0:
            before = p[max(0, i - 80):i]
            seg = re.split(r"[\[\]]|(?<=[.;])\s", before)[-1]
            if re.search(r"Manifestation|Concern|\b(treat|manage|control)\w*\s+(?:the\s+)?$", seg, re.I):
                treated = True
            elif PREVENTIVE_BEFORE.search(before) or PREVENTIVE.search(seg.strip()):
                preventive = True
            i = p.lower().find(low, i + 1)
    return preventive and not treated


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


# ------------------------------------------------------------------ branches -> chapters

def disease_names(branch: dict, step2: dict) -> list[str]:
    c = next((c for c in step2["candidates"] if c["key"] == branch["id"]), {})
    return [n for n in [c.get("label")] + list(c.get("synonyms") or []) if n]


def chapters_for(led: LG.Ledger, step2: dict, use_cache: bool) -> dict[str, list[str]]:
    gene_chapters = [ch for chs in (step2.get("genereviews") or {}).values() for ch in chs]
    branches = [b for b in led.branches if b.get("diagnosis")]
    if not gene_chapters or not branches:
        return {b["id"]: [] for b in led.branches}
    # one chapter is also checked: a gene with two diseases and one chapter must not give that chapter to both
    # (2026-11-04 review: the single-chapter shortcut assigned it to every branch)
    user = "Diagnoses:\n" + "\n".join(f"  {i}. {b['diagnosis']['label']}" for i, b in enumerate(branches, 1))
    user += "\n\nGeneReviews chapters:\n" + "\n".join(f"  {j}. {ch['title']}" for j, ch in enumerate(gene_chapters, 1))
    parsed, _ = _llm(CHAPTERS_SYSTEM, user, use_cache, "chapter selection")
    out = {b["id"]: [] for b in led.branches}
    for link in parsed.get("links") or []:
        i = link.get("diagnosis")
        if isinstance(i, int) and 1 <= i <= len(branches):
            out[branches[i - 1]["id"]] = [gene_chapters[j - 1]["nbk"] for j in link.get("chapters") or []
                                          if isinstance(j, int) and 1 <= j <= len(gene_chapters)]
    return out


# ------------------------------------------------------------------ main

def mgmt_sections(nbk: str) -> list[tuple[str, str]]:
    return [(p, t) for p, t in GR.sections(nbk).items() if p.startswith("Management")
            and not any(s in p.lower() for s in SKIP_SECTIONS)]


def _spec(claim, src, quote, source_text, accessed_at, produced_by="code", retrieved_by=""):
    """Evidence to be created once the action's final section is known (one action, one section)."""
    return {"claim": claim, "src": src, "quote": quote, "source_text": source_text, "accessed_at": accessed_at,
            "produced_by": produced_by, "retrieved_by": retrieved_by}


PURPOSE_CLAUSE = re.compile(r"^\W*(?:in order\s+)?to\s+(?:reduce|lower|inhibit|decrease|increase|prevent|improve|"
                            r"enhance|block|limit|control|maintain|promote|minimize|slow)\b|^\W*(?:which|that)\s+"
                            r"(?:reduces?|lowers?|inhibits?|decreases?|increases?|prevents?|improves?|enhances?)\b", re.I)


ROW_SYSTEM = EXTRACT_SYSTEM + """
Only ONE table row is given here, with its table caption. List the management actions in this row as above. If the
row names no treatment (only surveillance, evaluation, monitoring or information), return
{"items": [], "no_treatment": true, "reason": "<a few words>"}."""


def uncovered_rows(shown: str, text: str, items: list) -> list[dict]:
    """Table rows (in the LLM view) none of whose cells holds the verbatim quote of an extracted item.
    -> [{row, line, caption}]"""
    quotes = [str(it.get("quote") or "") for it in items if isinstance(it, dict) and LG.quote_in(str(it.get("quote") or ""), text)]
    out, caption = [], ""
    for line in (shown or "").splitlines():
        if line.startswith("Table "):
            caption = line
        elif line.startswith("Row "):
            cells = [m.group(2) for m in _CELL.finditer(line.split(": ", 1)[1] if ": " in line else line)]
            if not any(LG.quote_in(q, c) or LG.quote_in(c, q) for q in quotes for c in cells if c and q):
                out.append({"row": line.split(":", 1)[0], "line": line, "caption": caption})
    return out


_CELL = re.compile(r"\[([^:\]]+): ((?:[^\[\]]|\[[^\]]*\])*?)\](?= \[|$)")


def row_cells(shown: str, quote: str) -> list[str] | None:
    """The cell texts (with the column header as context) of the table row whose cell holds `quote`; None when the
    quote is not in a table row (prose: its own sentence is the context)."""
    for line in (shown or "").splitlines():
        if line.startswith("Row ") and LG.quote_in(quote, line):
            cells = [m.group(2) for m in _CELL.finditer(line.split(": ", 1)[1] if ": " in line else line)]
            if any(LG.quote_in(quote, c) for c in cells):
                return cells
    return None


# A column header that says which disorder (or gene, or subtype) a row is for. Kept narrow on purpose: a
# "Manifestation/Concern" or "Condition" column is about the patient's problem, not about which disorder.
_DISORDER_HEADER = re.compile(r"\b(?:disorders?|genes?|gene\(s\)|subtypes?|diseases?|genetic\s+cause)\b", re.I)
OTHER_DISORDER_ROW = ("overview table row is for another disorder (its disorder column names neither this "
                      "patient's gene nor this disease; fallback-chain contract: overview advice aimed at another "
                      "specific disease is not used for this one; decision 2026-11-10)")


def row_pairs(shown: str, quote: str) -> list[tuple[str, str]] | None:
    """(header, cell) pairs of the table row whose cell holds `quote`; None when the quote is not in a row."""
    for line in (shown or "").splitlines():
        if line.startswith("Row ") and LG.quote_in(quote, line):
            body = line.split(": ", 1)[1] if ": " in line else line
            pairs = [(m.group(1).strip(), m.group(2)) for m in _CELL.finditer(body)]
            if any(LG.quote_in(quote, c) for _, c in pairs):
                return pairs
    return None


def row_for_other_disorder(shown: str, quote: str, genes: set[str], names: list[str]) -> str | None:
    """The disorder a gene-family overview's table row is for, when that is not this patient's; else None.

    Overview tables are often laid out one row per disorder, with the disorder (or gene, or subtype) in its own
    column: Table 7 of the Leigh syndrome overview gives biotin and thiamine for "Biotin-thiamine-responsive
    basal ganglia disease", coenzyme Q10 for "Primary coenzyme Q10 deficiency", the ketogenic diet for primary
    PDH deficiency. The existing filter only looked for another gene SYMBOL, so a row naming another disorder by
    its name passed and was offered to an LRPPRC patient, conditional on a disorder he cannot have (blind test,
    2026-11-10). A row with no such column is left to the existing filter.
    """
    pairs = row_pairs(shown, quote)
    if not pairs:
        return None
    # every disorder-column cell is checked, even when the item's quote also appears in it: a one-word quote
    # such as "Thiamine" is inside "Biotin-thiamine-responsive basal ganglia disease", and skipping that cell
    # let thiamine through as applicable (2026-11-10, caught by the batch-1 cache rerun)
    cells = [c for h, c in pairs if _DISORDER_HEADER.search(h)]
    if not cells:
        return None
    cell = " ".join(cells)
    for g in genes:
        if g and re.search(rf"(?<![A-Za-z0-9]){re.escape(g)}(?![A-Za-z0-9])", cell):
            return None
    low = cell.lower()
    for n in names:
        if n and len(n) >= 4 and n.lower() in low:
            return None
    return cells[0][:120]


PURPOSE_RULE = "purpose or mechanism clause is not a requirement (a requirement describes the patient; decision 2026-11-04)"
BROADENING_RULE = ("broadening clause right after 'including / even in / also in / regardless of' widens who may receive it; "
                   "it is not a requirement (decision 2026-11-05)")
BROADENING_ALARM = "broadening clause is the item's only condition: kept as written (decision 2026-11-05)"
# only the clause right after a broadening word; narrowing words (excluding, except, other than, unless) stay conditions
_BROADEN = re.compile(r"(?:\bincl(?:uding|uded|\.)?|\beven\s+(?:in|for|with|if|when)|\balso\s+(?:in|for|with)|\bregardless\s+of)"
                      r"\s+(?:all\s+)?(?:those|persons|individuals|people|patients|children|adults)?\s*(?:w/|with|who\s+(?:have|are))?\s*$", re.I)


def broadening_word(text: str, where: str) -> str | None:
    """The broadening words right before `text` in `where` ("incl those w/" before "advanced CKD or kidney failure"),
    or None. Narrowing words never match, so "except those w/ kidney failure" stays a requirement."""
    low, t = re.sub(r"\s+", " ", where or "").lower(), re.sub(r"\s+", " ", text or "").lower().strip()
    i = low.find(t) if t else -1
    while i >= 0:
        m = _BROADEN.search(low[max(0, i - 40):i])
        if m:
            return m.group(0).strip()
        i = low.find(t, i + 1)
    return None


def _reqs(raw: list, spec: dict, where: str, dropped: list | None = None, context: dict | None = None) -> list[dict]:
    """Structured requirements whose words are in `where`; other kinds of sentences are dropped, and so is a purpose
    or mechanism clause ("to reduce hepatic oxalate production") - a requirement describes the patient (2026-11-04).
    Every dropped purpose clause is appended to `dropped` (text, rule, context) so it can be reviewed in the ledger."""
    out = []
    for r in raw or []:
        if not (isinstance(r, dict) and r.get("field") in REQ_FIELDS and LG.quote_in(str(r.get("text") or ""), where)):
            continue
        if PURPOSE_CLAUSE.search(str(r.get("text") or "")):
            if dropped is not None:
                dropped.append({"text": r.get("text"), "field": r.get("field"), "rule": PURPOSE_RULE,
                                "pattern": PURPOSE_CLAUSE.pattern, **(context or {})})
            continue
        word = broadening_word(str(r.get("text") or ""), where)
        out.append({**r, "kind": "label_condition", "spec": spec, **({"_broadening": word} if word else {})})
    return out


def drop_broadening(reqs: list[dict], dropped: list, context: dict) -> list[dict]:
    """Drop the broadening clauses of one item, provided a main condition remains; otherwise keep them as written
    and raise an alarm in the ledger. Every decision is logged (text, rule, the broadening words)."""
    broad = [r for r in reqs if r.get("_broadening")]
    if not broad:
        return reqs
    main = [r for r in reqs if not r.get("_broadening") and r.get("field") not in ("manifestation", "pregnancy")]
    for r in broad:
        dropped.append({"text": r["text"], "field": r.get("field"), "after": r["_broadening"],
                        "rule": BROADENING_RULE if main else BROADENING_ALARM, "kept": not main,
                        **({"warning": True} if not main else {}), **context})
    if not main:
        return [{k: v for k, v in r.items() if k != "_broadening"} for r in reqs]
    return [r for r in reqs if not r.get("_broadening")]


# --- quote repair (decision 2026-11-04) ---------------------------------------------------------------------
# An LLM quote that is not verbatim is dropped unless the closest span of the source differs from it only in
# letters: similarity >= REPAIR_MIN_RATIO, the item's name verbatim in the span, and the same numbers,
# comparison signs and negation words in the same order ("≥ 2" vs "≥ 12" and "indicated" vs "not indicated"
# are never repaired). The source span then replaces the quote and the conditions are extracted again from it.
REPAIR_MIN_RATIO = 0.95
_CRITICAL = re.compile(r"\d+(?:[.,]\d+)*|[≥≤<>=±%]|\b(?:not|no|non|without|never|none|nor|neither|cannot|unless|except)\b|n't",
                       re.I)


def critical_tokens(text: str) -> list[str]:
    return [t.lower() for t in _CRITICAL.findall(text)]


def _words_at(text: str, i: int, j: int) -> tuple[int, int]:
    """Widen [i, j) to whole words."""
    while i > 0 and text[i - 1].isalnum():
        i -= 1
    while j < len(text) and text[j].isalnum():
        j += 1
    return i, j


def repair_quote(quote: str, source_text: str, name: str) -> tuple[str | None, str]:
    """(source span, reason) when `quote` is a letter-level miscopy of one span of `source_text`; (None, reason) otherwise."""
    src = re.sub(r"\s+", " ", source_text).strip()
    q = re.sub(r"\s+", " ", quote or "").strip()
    if not q or not src:
        return None, "empty quote or source"
    sl, ql = src.lower(), q.lower()
    sm = difflib.SequenceMatcher(None, sl, ql, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= 8]
    if not blocks:
        return None, "no matching span"
    anchor = max(blocks, key=lambda b: b.size)
    start0 = anchor.a - anchor.b
    best = (0.0, 0, 0)
    for ds in range(-8, 9):
        for de in range(-8, 9):
            i, j = max(0, start0 + ds), min(len(src), start0 + len(q) + de)
            if j - i < 1:
                continue
            r = difflib.SequenceMatcher(None, sl[i:j], ql, autojunk=False).ratio()
            if r > best[0]:
                best = (r, i, j)
    ratio, i, j = best
    i, j = _words_at(src, i, j)
    span = src[i:j].strip()
    if ratio < REPAIR_MIN_RATIO:
        return None, f"similarity {ratio:.3f} below {REPAIR_MIN_RATIO}"
    if not re.search(rf"(?<![a-z0-9]){re.escape(name.lower())}(?![a-z0-9])", span.lower()):
        return None, f"name {name!r} not verbatim in the source span"
    if critical_tokens(span) != critical_tokens(q):
        return None, f"numbers, signs or negations differ: {critical_tokens(q)} vs source {critical_tokens(span)}"
    return span, f"similarity {ratio:.3f}"


# --- label indications, sentence by sentence (decision 2026-11-04) ------------------------------------------
# A label names the diagnosis as the condition it treats ("indicated for the treatment of <disease>") -> targeted;
# as the setting of a complication or symptom ("symptoms in <disease>", "secondary to <disease>") -> supportive;
# outside an "indicated" sentence (limitations of use, warnings) or after "not indicated" -> not used.
_ANCHOR = re.compile(r"\bindicated(?:\s+(?:for|in|as))?\b|\b(?:treatment|management|therapy|prophylaxis|prevention)\s+of\b", re.I)
_CONTEXT = re.compile(r"\b(?:in|secondary\s+to|due\s+to|caused\s+by|associated\s+with|from|during|following|because\s+of)\b", re.I)
# "... patients with <disease> to improve pulmonary function": the purpose is a symptom or function -> supportive
_PURPOSE = re.compile(r"^[^.;•]{0,80}?\bto\s+(?:improve|reduce|relieve|prevent|control|decrease|increase|maintain)\b", re.I)
_NEGATED = re.compile(r"\b(?:not|never)\s+(?:be\s+)?(?:indicated|recommended|approved)\b", re.I)


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


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.])\s+(?=[A-Z0-9•])", re.sub(r"\s+", " ", text or "")) if s.strip()]


def indication_role(indications: str, names: list[str]) -> tuple[str, str, str] | None:
    """(role, sentence, name) for the first diagnosis name an indication sentence treats; role is "targeted" or
    "supportive". None when no "indicated" sentence names a diagnosis."""
    found = None
    for sent in _sentences(indications):
        if "indicated" not in sent.lower() or "limitation" in sent.lower():
            continue
        for name in label_names(names):
            pos = name_in(name, sent)
            if pos is None:
                continue
            before = re.sub(r"\s+", " ", sent)[:pos]
            if _NEGATED.search(before):
                continue
            anchors = list(_ANCHOR.finditer(before))
            if not anchors:
                continue
            gap = before[anchors[-1].end():]
            gap = re.split(r"[•;]", gap)[-1]          # in a list, the item that names the diagnosis decides
            after = re.sub(r"\s+", " ", sent)[pos + len(name):]
            role = "supportive" if _CONTEXT.search(gap) or _PURPOSE.search(after) else "targeted"
            if role == "targeted":
                return role, sent, name
            found = found or (role, sent, name)
    return found


def _repaired_item(it: dict, name: str, path: str, text: str, use_cache: bool, nbk: str) -> dict | None:
    """The item with its quote replaced by the source span it miscopied, and its conditions extracted again from that
    span (the miscopied sentence is not reused). None when the quote cannot be repaired, the second extraction does
    not list the item, or any of its requirement words are not verbatim in the span (a dropped condition would make
    the action look unconditionally applicable)."""
    span, why = repair_quote(str(it.get("quote") or ""), text, name)
    if span is None:
        print(f"[3a] quote not verbatim, not repaired ({name}, {nbk}): {why}", flush=True)
        return None
    parsed, llm = _llm(EXTRACT_SYSTEM, f"Section: {path}\n{span}", use_cache, f"GeneReviews {nbk} repaired quote")
    items = [x for x in parsed.get("items") or [] if isinstance(x, dict)]
    again = next((x for x in items if A.components(str(x.get("name") or "")) == A.components(name)), None) \
        or (items[0] if len(items) == 1 else None)
    if again is None:
        print(f"[3a] repaired quote for {name} ({nbk}): second extraction does not list it", flush=True)
        return None
    reqs = [r for r in again.get("requirements") or [] if isinstance(r, dict)]
    if any(not LG.quote_in(str(r.get("text") or ""), span) for r in reqs):
        print(f"[3a] repaired quote for {name} ({nbk}): requirement words not verbatim in the span", flush=True)
        return None
    return {"name": name, "kind": it.get("kind"), "quote": span, "requirements": reqs,
            "manifestation": again.get("manifestation") or "", "mechanism_quote": again.get("mechanism_quote") or "",
            "quote_repaired": {"llm_quote": it.get("quote"), "check": why}, "_llm": llm}


def population_requirements(headings: list[str], spec: dict) -> list[dict]:
    """Named populations in a heading condition every item below it (user approval 2026-11-15).
    Compare only explicit sex / age / zygosity; any remaining population qualifier stays unknown."""
    out = []
    sex_word = re.compile(r"\b(males?|females?|men|women|boys?|girls?)\b", re.I)
    for heading in headings:
        sexes = list(sex_word.finditer(heading))
        bands = AB.bands_in(heading)
        if not sexes and not bands:
            continue
        # Compound alternatives and negated / relative populations need semantic reading by the context check.
        if re.search(r"\b(or|not|except|after|before|older|younger|than|under|over|onset)\b", heading, re.I):
            continue
        rows = []
        wants = {"female" if m.group().lower().startswith(("f", "w", "g")) else "male" for m in sexes}
        if len(wants) == 1:
            rows.append({"field": "sex", "value": next(iter(wants))})
        if bands:
            # Use the existing conservative age-band boundaries; preserve the complete heading as the evidence.
            rows.append({"field": "age_band", "value": " and ".join(bands)})
        zyg = zygosity_words(heading)
        if len(zyg) == 1:
            rows.append({"field": "zygosity", "value": zyg})
        rest = sex_word.sub(" ", heading)
        for pat, _, _ in AB.BANDS.values():
            rest = re.sub(r"\b(?:" + pat + r")\b", " ", rest, flags=re.I)
        rest = re.sub(r"\b(?:affected|patients?|individuals?|persons?|people|all|only|and|in|for|management|"
                      r"homozygous|heterozygous|hemizygous|compound)\b", " ", rest, flags=re.I)
        if re.search(r"[A-Za-z0-9]", rest) or len(wants) > 1:
            rows.append({"field": "population", "value": ""})
        src = dict(spec, quote=heading, source_text=spec["src"]["section"] + "\n" + spec["source_text"],
                   claim=f"{spec['claim']} Population heading: {heading}", produced_by="code",
                   retrieved_by=spec["retrieved_by"] + "; population heading")
        out += [dict(r, kind="other", text=heading, spec=src) for r in rows]
    return out


def place(found: dict, key: dict, section: str, label: str, branch_ids: list[str], spec: dict, reqs: list[dict],
          why: str, pregnancy: bool = False, source: str = "gr_new") -> None:
    """Add one finding to its action. source: "gr_new" (a GeneReviews chapter with a Targeted Therapies section),
    "gr_old" (a chapter without one) or "label".
    The section (decision 2026-11-04, corrected the same day):
      - a new-version chapter decides for the actions it lists: sections follow the mechanism, which is the GeneReviews
        experts' classification; a label supplies conditions, not the section;
      - otherwise (old-version chapter, or a label only) the old rules: a label whose indication treats the diagnosis
        (rule i) or a supported mechanism sentence (rule ii) -> targeted; targeted before supportive before precautions."""
    a = found.setdefault(key["key"], {"key": key, "section": section, "label": label, "branches": set(), "specs": [],
                                      "reqs": [], "why": why, "pregnancy_only": pregnancy, "source": source})
    if source == "gr_new" and a["source"] != "gr_new":
        a["section"], a["why"], a["source"] = section, why, "gr_new"
    elif (source == "gr_new" or a["source"] != "gr_new") and SECTIONS_3A.index(section) < SECTIONS_3A.index(a["section"]):
        a["section"], a["why"] = section, why
    a["pregnancy_only"] = a["pregnancy_only"] and pregnancy
    a["branches"].update(branch_ids)
    a["specs"].append(spec)
    a["reqs"] += reqs


def add_established(led: LG.Ledger, step1: dict, step2: dict, *, use_cache: bool = True) -> None:
    pf = facts(step1, step2)
    for b in led.branches:
        b["synonyms"] = disease_names(b, step2)[1:]
    # supportive fallback chain (contract docs/supportive_fallback_contract.md): per branch, a single-gene chapter (L1)
    # or else a multi-gene overview that lists the gene (L2); L3 / L4 below
    ch_map, tier_rec = F.branch_tiers(chapters_for(led, step2, use_cache), step2, led.branches)
    acc_book = D.ensure("genereviews_book").downloaded_at
    found: dict[str, dict] = {}          # action key -> {key, section, label, branches, specs, reqs, why}
    dropped_conditions: list[dict] = []  # requirements code refused (purpose clauses), kept for review
    searches: list[dict] = []

    def put(key: dict, section: str, label: str, branch_ids: list[str], spec: dict, reqs: list[dict], why: str,
            pregnancy: bool = False, source: str = "gr_new"):
        place(found, key, section, label, branch_ids, spec, reqs, why, pregnancy, source)

    # GeneReviews: one LLM call per section (a whole chapter at once is too long for the API), in parallel
    for book_index, nbk in enumerate(sorted({n for ns in ch_map.values() for n in ns})):
        secs = mgmt_sections(nbk)
        section_positions = {path:i for i,(path,_) in enumerate(secs)}
        branch_ids = [b for b, ns in ch_map.items() if nbk in ns]
        tier = F.chapter_tier(nbk, step2)
        own_genes = {b.get("gene") for b in led.branches if b["id"] in branch_ids}
        ch_genes = GR.chapter_genes(nbk) if tier == "overview" else []
        branch_names = [n for b in led.branches if b["id"] in branch_ids for n in disease_names(b, step2)]
        searches.append({"database": "genereviews", "endpoint": GR.BOOK_URL.format(nbk=nbk),
                         "query": f"{nbk} Management sections", "queried_at": acc_book, "n_results": len(secs)})
        if not secs:
            continue
        has_targeted = any(any(t in p.lower() for t in TARGETED_TITLES) for p, _ in secs)
        shown = GR.sections_for_llm(nbk)      # tables row by row with their headers; quotes are checked on `secs`
        with ThreadPoolExecutor(max_workers=X.CONCURRENCY) as pool:
            per_sec = list(pool.map(lambda pt: _llm(EXTRACT_SYSTEM, f"Section: {pt[0]}\n{shown.get(pt[0], pt[1])[:9000]}",
                                                   use_cache, f"GeneReviews {nbk} '{pt[0]}'"), secs))
        # row coverage (decision 2026-11-04): every table row of a Management section must yield at least one
        # action or be judged "no treatment content"; an uncovered row is extracted again on its own
        extra_secs, extra_res = [], []
        for (path, text), (parsed, llm) in zip(secs, per_sec):
            for row in uncovered_rows(shown.get(path, ""), text, parsed.get("items") or []):
                r_parsed, r_llm = _llm(ROW_SYSTEM, f"Section: {path}\n{row['caption']}\n{row['line']}", use_cache,
                                       f"GeneReviews {nbk} row {row['row']}")
                items = [x for x in r_parsed.get("items") or [] if isinstance(x, dict)]
                led.reextracted_rows.append({"nbk": nbk, "section": path, "row": row["row"], "row_text": row["line"][:300],
                                             "n_items": len(items), "no_treatment": bool(r_parsed.get("no_treatment")) and not items,
                                             "reason": r_parsed.get("reason") or "", "produced_by": r_llm})
                if items:
                    extra_secs.append((path, text))
                    extra_res.append(({"items": items}, r_llm))
        for (path, text), (parsed, llm) in zip(secs + extra_secs, per_sec + extra_res):
            low = path.lower()
            avoid, pregnancy = "avoid" in low, "pregnancy" in low
            for it in parsed.get("items") or []:
                name = str(it.get("name") or "").strip()
                kind, kind_pending = A.resolve_kind(name, it["kind"])
                if not name or name.lower() in NOT_A_THERAPY:
                    continue
                if not LG.quote_in(str(it.get("quote") or ""), text):
                    it = _repaired_item(it, name, path, text, use_cache, nbk)
                    if it is None:
                        continue
                    llm = it.pop("_llm")
                if not avoid and kind not in ("drug", "procedure", "diet", "device", "therapy", "other"):
                    continue
                if avoid:
                    section = "contraindications_precautions"
                elif any(t in low for t in TARGETED_TITLES):
                    section = "existing_targeted_therapies"
                else:
                    section = "supportive_management"
                # therapy programs: the code's controlled vocabulary decides (the LLM gives only the name as written);
                # a "therapy" that matches no type, or an evaluation / counselling referral, is not collected
                if A.AIRWAY_CLEARANCE.search(name):
                    kind = "procedure"         # chest physiotherapy is airway clearance, not a rehabilitation program
                ttype = A.therapy_type(name) if not avoid and kind in ("therapy", "procedure", "device") else None
                if ttype:
                    key = {"key": A.strategy_key("therapy", ttype), "normalized": True, "therapy_type": ttype}
                else:
                    key = A.drug_key(name) if kind == "drug" or (avoid and kind == "avoid" and A.drug_key(name)["normalized"]) \
                    else {"key": A.strategy_key({"procedure": "procedure", "diet": "diet"}.get(kind, "supportive_measure"), name),
                          "normalized": True}
                src = {"type": "nbk", "id": nbk, "url": GR.BOOK_URL.format(nbk=nbk), "section": path, "credit": GR.CREDIT}
                claim = f"GeneReviews ({path}) lists {name}" + (f" for {it['manifestation']}" if it.get("manifestation") else "") + "."
                spec = _spec(claim, src, it["quote"], text, acc_book, llm, f"3a genereviews {nbk}")
                spec["extraction_kind"] = {"original": it["kind"], "resolved": kind, "pending": kind_pending}
                position = LG._norm(text).find(LG._norm(name))
                spec["source_order"] = [book_index,section_positions[path],position if position >= 0 else LG._norm(text).index(LG._norm(it['quote']))]
                spec["presentation_quotes"] = management_quotes(shown.get(path, ""), name, it["quote"])
                spec["tier_source"] = tier
                if tier == "overview":            # a row of an overview table that is for another disorder
                    other_row = row_for_other_disorder(shown.get(path, ""), it["quote"], own_genes, branch_names)
                    if other_row:
                        dropped_conditions.append({"text": it["quote"][:200], "action": name, "source": f"{nbk} {path}",
                                                   "rule": f"{OTHER_DISORDER_ROW}: {other_row}"})
                        continue
                if tier == "overview":            # overview advice about another gene of the chapter is not for this one
                    sc = " | ".join(row_cells(shown.get(path, ""), it["quote"]) or []) or \
                        (GR.paragraph_scope(shown.get(path, ""), it["quote"]) or it["quote"])
                    other = next((g for g in [F.other_gene_named(sc, ch_genes, own) for own in own_genes] if g), None) \
                        if len(own_genes) == 1 else F.other_gene_named(sc, ch_genes, next(iter(own_genes), None))
                    if other:
                        dropped_conditions.append({"text": it["quote"][:200], "action": name, "source": f"{nbk} {path}",
                                                   "rule": f"overview advice names another gene of the chapter ({other})"})
                        continue
                if it.get("quote_repaired"):
                    spec["quote_repaired"] = it["quote_repaired"]
                # a table item's conditions may sit in other cells of its row (the manifestation it treats, the
                # persons it is for): each such condition is checked against that row and quoted on its own
                # ...and a paragraph item's conditions may sit in the paragraph's lead-in or subheading ("Ages 0-3
                # years."): checked only within that paragraph (its line in the LLM view), never across paragraphs
                cells = row_cells(shown.get(path, ""), it["quote"])
                para = None if cells else GR.paragraph_scope(shown.get(path, ""), it["quote"])
                scope = " | ".join(cells) if cells else (para or "")
                ctx = {"source": f"{nbk} {path}", "action": name, "item_quote": it["quote"][:200]}
                reqs = _reqs(it.get("requirements"), spec, it["quote"], dropped_conditions, ctx)
                for r in _reqs(it.get("requirements"), None, scope, dropped_conditions if scope else None, ctx):
                    if not LG.quote_in(r["text"], it["quote"]):
                        r["spec"] = _spec(f"GeneReviews ({path}) row condition for {name}: {r['text'][:80]}", src, r["text"],
                                          text, acc_book, llm, f"3a genereviews {nbk}")
                        reqs.append(r)
                    elif scope and not r.get("_broadening"):         # same words seen in the wider scope: broadening there?
                        w = broadening_word(r["text"], scope)
                        for x in reqs:
                            if w and x["text"] == r["text"]:
                                x["_broadening"] = w
                reqs = drop_broadening(reqs, dropped_conditions, ctx)
                headings = GR.heading_context(path, shown[path], it["quote"])
                population = population_requirements(headings, spec)
                reqs = [r for r in reqs if not any(r["field"] == ("age" if p["field"] == "age_band" else p["field"])
                                                 and LG.quote_in(r["text"], p["text"])
                                                 for p in population)] + population
                if section == "supportive_management" and it.get("manifestation") and LG.quote_in(it["manifestation"], text):
                    reqs.append({"kind": "other", "text": it["manifestation"], "field": "manifestation",
                                 "spec": _spec(claim, src, it["manifestation"], text, acc_book, llm, f"3a genereviews {nbk}")})
                if pregnancy:
                    for r in reqs:
                        r["pregnancy_passage"] = True       # applies to the pregnancy recommendation only
                    title = path.split(" / ")[-1]
                    reqs.append({"kind": "other", "text": title, "field": "pregnancy", "pregnancy_passage": True,
                                 "spec": _spec(f"GeneReviews section '{title}'", src, title, path, acc_book, "code",
                                               f"3a genereviews {nbk}")})
                why = path
                if section == "supportive_management" and not has_targeted and kind == "drug":
                    why += " (older chapter without Targeted Therapies)"
                    if it.get("mechanism_quote") and LG.quote_in(it["mechanism_quote"], text):
                        disease = next(((b.get("diagnosis") or {}).get("label", "") for b in led.branches if b["id"] in branch_ids), "")
                        sc = SC.check_support(f"{name} acts on the disease mechanism",
                                              [f"{name} acts on the defective gene product or the disease mechanism of {disease}."],
                                              [it["mechanism_quote"]], use_cache=use_cache)
                        if sc["overall"] == "supported":
                            section, why = "existing_targeted_therapies", path + " (older chapter; mechanism stated and supported)"
                row = f"{nbk} {path}: {it['quote']}"            # one table row or sentence = one alternative
                for r in reqs:
                    r["alternative"] = row
                put(key, section, name, branch_ids, spec, reqs, why, pregnancy, "gr_new" if has_targeted else "gr_old")

    # FDA labels: by indication and contraindication for every diagnosis name (names shorter than 4 characters and
    # one-word abbreviations skipped), and by exact generic name for drugs GeneReviews lists in Targeted or Supportive
    tasks = []
    for b in [b for b in led.branches if b.get("diagnosis")]:
        for name in label_names(disease_names(b, step2)):
            tasks.append(("indications_and_usage", name, 10, [b["id"]], None, "label indication names the diagnosis", name))
            tasks.append(("contraindications", name, 5, [b["id"]], "contraindications_precautions", "label contraindication names the diagnosis", name))
    for k, a in list(found.items()):
        if a["key"].get("normalized") and k.startswith("drug:") and a["section"] in ("existing_targeted_therapies", "supportive_management"):
            comps = A.components(a["label"])   # a combination is searched by one ingredient, then matched on all of them
            if comps:                          # ("Elexacaftor/tezacaftor/ivacaftor" as a phrase finds nothing)
                tasks.append(("openfda.generic_name", comps[0], 10 if len(comps) > 1 else 5, sorted(a["branches"]), None,
                              "label for a drug GeneReviews lists", a["label"]))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda t: LB.search(t[0], t[1], limit=t[2]), tasks))
    jobs, seen = [], set()               # (label, text, disease, branch ids, section, why, quote)
    for (field, _, _, bids, section, why, name), (labels, rec) in zip(tasks, results):
        searches.append(rec)
        for lb in LB.latest(labels)[:5]:
            ind = lb["sections"].get("indications_and_usage", "")
            job = None
            if field == "contraindications":
                m = re.search(rf"[^.]*(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])[^.]*\.", lb["sections"].get("contraindications", ""), re.I)
                if m:
                    job = (lb, lb["sections"].get("contraindications", ""), name, bids, section, why, m.group(0).strip())
            else:
                # an indication sentence that names the diagnosis: its label supplies the conditions (any wording); its
                # wording places the action only when GeneReviews does not list it (place()). By drug name, only a label
                # of exactly that drug counts (not a combination product)
                names = [n for b in led.branches if b["id"] in bids for n in disease_names(b, step2)]
                if field == "openfda.generic_name" and A.components(lb.get("generic") or "") != A.components(name):
                    continue
                role = indication_role(ind, names)
                if role:
                    sec = "existing_targeted_therapies" if role[0] == "targeted" else "supportive_management"
                    why_ = why + ("" if role[0] == "targeted" else " (complication or symptom of the diagnosis)")
                    job = (lb, ind, role[2], bids, sec, why_, role[1])
            if job and (lb["set_id"], job[4]) not in seen:
                seen.add((lb["set_id"], job[4]))
                jobs.append(job)
    with ThreadPoolExecutor(max_workers=X.CONCURRENCY) as pool:
        parsed = list(pool.map(lambda j: _label_requirements(j[0], j[2], use_cache)
                               if j[4] != "contraindications_precautions" else None, jobs))
    for (lb, text, name, bids, section, why, quote), reqs in zip(jobs, parsed):
        _label_action(put, lb, text, name, bids, section, why, reqs, quote=quote)

    supportive_fallback(led, found, tier_rec, pf, step2, put, use_cache)
    led.patient_context["action_synonyms"] = merge_synonyms(found, use_cache)
    seen_drop = set()                  # the same clause can be refused twice (item quote, then its row)
    led.dropped_conditions = [d for d in dropped_conditions
                              if (k := (d["text"], d["source"], d["action"])) not in seen_drop and not seen_drop.add(k)]
    _records(led, found, pf, searches, use_cache)


def _label_text(lb: dict) -> str:
    return " ".join(lb["sections"].get(s, "") for s in ("indications_and_usage", "dosage_and_administration", "pediatric_use"))


def _label_requirements(lb: dict, disease: str, use_cache: bool) -> list[dict]:
    parsed, _ = _llm(REQ_SYSTEM, f"Disease: {disease}\n\nLabel text:\n{_label_text(lb)[:9000]}", use_cache,
                     f"label requirements {lb['brand'] or lb['generic']}")
    return parsed.get("requirements") or []


def _label_action(put, lb: dict, text: str, disease: str, branch_ids: list[str], section: str, why: str,
                  raw_reqs: list[dict] | None, quote: str | None = None) -> None:
    key = A.drug_key(lb["generic"] or lb["brand"])
    q = quote or text[:300]
    src = {"type": "spl_setid", "id": lb["set_id"], "url": lb["url"], "version": lb["version"],
           "effective_date": lb["effective_date"], "brand": lb["brand"]}
    name = lb["brand"] or lb["generic"]
    claim = (f"{name} label (version {lb['version']}, effective {lb['effective_date']}): "
             + {"existing_targeted_therapies": f"indicated for {disease}.",
                "supportive_management": f"indicated in patients with {disease}."}.get(
                 section, f"contraindicated or cautioned in {disease}."))
    spec = _spec(claim, src, q, text, lb["accessed_at"], "code", f"3a openfda {why}")
    spec["label_section"] = section          # only a label that treats the diagnosis itself decides the conditions
    lt = _label_text(lb)
    reqs = []
    for r in _reqs(raw_reqs, None, lt):
        r["spec"] = _spec(f"{name} label requirement: {r['text']}", src, r["text"], lt, lb["accessed_at"], "code",
                          "3a openfda requirement")
        r["_label_tables"] = label_tables(lb["full_text"], r["text"])
        # Indications and Usage: eligibility; any other part (dosage, warnings, specific populations): safety precaution
        r["label_part"] = next((sec for sec in ("indications_and_usage", "dosage_and_administration", "pediatric_use")
                                if LG.quote_in(r["text"], lb["sections"].get(sec, ""))), "")
        reqs.append(r)
    for r in reqs:
        r["alternative"] = f"{name} label version {lb['version']}"
    put(key, section, name, branch_ids, spec, reqs, why, source="label")


_VAR_NAMES = {"kidney_function": "kidney function", "liver_function": "liver function", "variant_class": "variant type",
              "situation": "usage situation"}


def variable_type(field: str) -> str:
    """Missing-information row name for a patient fact field ("current medication: valproate" -> "current medication")."""
    f = str(field or "other").split(":")[0].strip()
    return _VAR_NAMES.get(f, f.replace("_", " "))


SYNONYM_SYSTEM = """You compare the names of non-drug management actions taken from one GeneReviews chapter. Each has a
number and the section it comes from. Return groups of numbers that name the SAME action in different words
("same": e.g. "high fluid intake" and "hyperhydration"), and pairs where the first is a broader action that includes
the second ("broader": e.g. "dialysis" includes "hemodialysis"). Do not group actions that are only related.
Return only JSON: {"same": [[<numbers>]], "broader": [[<broader number>, <narrower number>]]}"""


def _topic(spec: dict) -> tuple:
    src = spec.get("src") or {}
    return (src.get("type"), src.get("id"), src.get("section"))


def merge_synonyms(found: dict, use_cache: bool) -> list[dict]:
    """Non-drug actions named differently (decision 2026-11-04): the LLM proposes groups; code merges a group only
    when every member's GeneReviews quotes come from the same chapter section (topic); broader / narrower pairs
    (dialysis > hemodialysis) are not merged, only related (the narrower is written once, under the broader).
    Returns the log of what was merged or related and why proposals were refused."""
    keys = [k for k, a in sorted(found.items()) if not k.startswith(("drug:", "trial:"))
            and any(sp["src"]["type"] == "nbk" for sp in a["specs"])]
    if len(keys) < 2:
        return []
    listing = "\n".join(f"{i}. {found[k]['label']} (section: {found[k]['specs'][0]['src'].get('section')})"
                        for i, k in enumerate(keys, 1))
    parsed, pb = _llm(SYNONYM_SYSTEM, listing, use_cache, "synonym groups")
    log = []

    def pick(nums):
        return [keys[n - 1] for n in nums if isinstance(n, int) and 1 <= n <= len(keys)]

    for group in parsed.get("same") or []:
        ks = [k for k in dict.fromkeys(pick(group if isinstance(group, list) else [])) if k in found]
        if len(ks) < 2:
            continue
        topics = [{_topic(sp) for sp in found[k]["specs"] if sp["src"]["type"] == "nbk"} for k in ks]
        shared = set.intersection(*topics)
        if not shared or len({found[k]["section"] for k in ks}) > 1:
            log.append({"kind": "same", "refused": [found[k]["label"] for k in ks],
                        "why": "not from the same chapter section" if not shared else "placed in different report sections"})
            continue
        keep = ks[0]
        for k in ks[1:]:
            b = found.pop(k)
            a = found[keep]
            a["branches"] |= b["branches"]
            a["specs"] += b["specs"]
            a["reqs"] += b["reqs"]
            a.setdefault("merged_from", []).append({"key": k, "label": b["label"]})
        log.append({"kind": "same", "merged_into": found[keep]["label"], "labels": [found[keep]["label"]] +
                    [m["label"] for m in found[keep]["merged_from"]], "topic": sorted(map(str, shared))[0], "produced_by": pb})
    for pair in parsed.get("broader") or []:
        ks = pick(pair if isinstance(pair, list) else [])
        if len(ks) == 2 and all(k in found for k in ks) and ks[0] != ks[1]:
            wide, narrow = ks
            found[narrow]["narrower_than"] = {"key": wide, "label": found[wide]["label"]}
            found[wide].setdefault("includes", []).append({"key": narrow, "label": found[narrow]["label"]})
            log.append({"kind": "broader", "broader": found[wide]["label"], "narrower": found[narrow]["label"], "produced_by": pb})
    return log


def supportive_fallback(led: LG.Ledger, found: dict, tier_rec: dict, pf: dict, step2: dict, put, use_cache: bool) -> None:
    """L3 and L4 of the fallback chain, per branch (contract v2). Records every tier decision in led.supportive_tiers."""
    def results(bid, tiers):
        return [a for a in found.values() if a["section"] == "supportive_management" and bid in a["branches"]
                and any(sp.get("tier_source") in tiers for sp in a["specs"])]

    table = F.load_guidelines()
    ont = ontology()
    # findings stated only as possible are symptoms too for the tier record (their entries depend on them, 2026-11-13)
    present_ids = {x["hpo_id"] for x in pf["present"] + (pf.get("possible") or [])}

    def matches(text, symptom):
        """HPO up / down: the action treats the symptom, a broader term of it, or a narrower one (2026-11-05)."""
        ids = set(ont.exact_lookup(text)) or {c["hpo_id"] for c in ont.search(text, 1)}
        h = symptom["hpo_id"]
        return h in ids or bool(ids & set(ont.ancestors(h))) or any(h in ont.ancestors(i) for i in ids)

    for b in [b for b in led.branches if b.get("diagnosis")]:
        rec = tier_rec.setdefault(b["id"], {"tier": None, "chapters": []})
        rec["present_ids"] = sorted(present_ids)
        above = results(b["id"], ("chapter", "overview"))
        if not above:                                       # L3 only when L1 and L2 give nothing (contract)
            _literature(led, b, rec, put, step2, use_cache)
            above = results(b["id"], ("chapter", "overview", "literature"))
            if above:
                rec["tier"] = "literature"
        rec["results_above"] = bool(above)
        texts = [r["text"] for a in above for r in a["reqs"] if r.get("field") == "manifestation"]
        # findings stated only as possible get their entries too, each depending on that finding (2026-11-12)
        stated = pf["present"] + (pf.get("possible") or [])
        targets = stated if not above else F.uncovered_symptoms(stated, texts, matches)
        if above and rec.get("chapters"):     # a symptom the chapter's management sections name is covered (2026-11-05)
            mgmt = " ".join(t for nbk in rec["chapters"] for _, t in mgmt_sections(nbk))
            named = [x for x in targets if F.names_symptom(mgmt, list(ont.names(x["hpo_id"])))]
            rec["covered_by_chapter_text"] = [{"hpo_id": x["hpo_id"], "label": x["label"]} for x in named]
            targets = [x for x in targets if x not in named]
        rec["gap_filled" if above else "symptoms"] = [{"hpo_id": x["hpo_id"], "label": x["label"]} for x in targets]
        cats = F.symptom_categories(targets, table, ont.ancestors)
        rec["symptomatic"] = {"configured": bool(table.get("categories")), "categories": sorted(cats)}
        for cat, symptoms in cats.items():
            if table["categories"][cat].get("enabled") is False:      # e.g. not yet verified: never a stand-in
                rec["symptomatic"].setdefault("disabled", []).append(cat)
                continue
            for g in table["categories"][cat].get("guidelines") or []:
                text = F.verified_text(g)
                if text is None:
                    rec["symptomatic"].setdefault("not_verified", []).append(g.get("id"))
                    continue
                for rec_ in g.get("recommendations") or []:
                    if not LG.quote_in(rec_.get("quote", ""), text) or \
                            any(not LG.quote_in(w, rec_["quote"]) for w in rec_.get("requires") or []):
                        continue
                    src = {"type": "url", "id": g["url"], "url": g["url"], "guideline": g.get("title"), "version": g.get("version")}
                    # a recommendation for one seizure type (or other narrower symptom) only when the case states it
                    only = set(rec_.get("hpo") or [])
                    for x in [x for x in symptoms if not only or x["hpo_id"] in only or only & set(ont.ancestors(x["hpo_id"]))]:
                        name = rec_["name"]
                        tt = A.therapy_type(name)
                        key = {"key": A.strategy_key("therapy", tt) if tt else A.strategy_key("supportive_measure", f"{cat} {name}"),
                               "normalized": True}
                        spec = _spec(f"{g.get('title')} recommends {name} for {x['label']} (symptomatic management).", src,
                                     rec_["quote"], text, int(time.time()), "code", f"3a symptomatic {g.get('id')}")
                        spec.update(tier_source="symptomatic", verified_manually=g["verified"].get("date"))
                        reqs = [{"kind": "other", "text": w, "field": "situation",
                                 "spec": _spec(f"{g.get('title')}: used only {w}", src, w, text, int(time.time()), "code",
                                               f"3a symptomatic {g.get('id')}")} for w in rec_.get("requires") or []]
                        if x.get("status") == "possible":
                            reqs.append({"kind": "other", "text": rec_["quote"], "field": "possible_manifestation",
                                         "finding": x, "spec": spec})
                        put(key, "supportive_management", name, [b["id"]], spec, reqs, f"symptomatic: {x['label']}", source="symptomatic")
                        found[key["key"]]["for_symptom"] = {"hpo_id": x["hpo_id"], "label": x["label"], "quote": x["quote"]}
        if not rec.get("tier") and not above:
            rec["tier"] = "symptomatic" if any(a.get("for_symptom") for a in found.values() if b["id"] in a["branches"]) else "none"
    led.supportive_tiers = tier_rec


def _literature(led, b, rec, put, step2, use_cache) -> None:
    """L3 for one branch: PubMed abstracts and PMC open-access full text; LLM lifts verbatim recommendations, code
    checks the quote, the publication type and the support check."""
    names = disease_names(b, step2)
    try:
        lit = F.search_literature(b.get("gene"), names)
    except (RuntimeError, ValueError, KeyError) as e:     # e.g. NCBI search unavailable: recorded, nothing assumed
        rec["literature"] = {"error": f"{type(e).__name__}: {e}"[:300]}
        return
    rec["literature"] = {k: v for k, v in lit.items() if k != "papers"} | {
        "papers": [{k: v for k, v in p.items() if k not in ("abstract", "full_text")} for p in lit["papers"]]}
    for p in lit["papers"]:
        if p.get("excluded"):
            continue
        text = " ".join(x for x in (p["abstract"], p["full_text"]) if x)
        if not text:
            continue
        focus = names + [b.get("gene") or ""]
        shown = F.text_for_llm(p["abstract"], p["full_text"], focus=focus)   # this disease's sections first (O2)
        for rp in rec["literature"]["papers"]:     # 0 = the model never saw this disease in the article: visible
            if rp.get("pmid") == p["pmid"]:
                rp["window_focus_hits"] = F.focus_hits(shown, focus)
        parsed, llm = _llm(F.LIT_SYSTEM, f"Disease: {b['diagnosis']['label']}\nArticle PMID {p['pmid']}:\n{shown}",
                           use_cache, f"literature PMID {p['pmid']}")
        for it in parsed.get("items") or []:
            name, q = str(it.get("name") or "").strip(), str(it.get("quote") or "")
            if not name or not LG.quote_in(q, text):
                continue
            # "for some or all patients" (fix plan S6, 2026-11-11): a recommendation limited to some patients ("in a
            # milder form ... lung transplantation may be an option") is kept; its limit is taken by the context check
            sc = SC.check_support(f"{name} for {b['diagnosis']['label']}",
                                  [f"The article recommends or presents {name} as an option for some or all patients "
                                   f"with {b['diagnosis']['label']}."], [q], use_cache=use_cache)
            if sc["overall"] != "supported":
                continue
            tt = A.therapy_type(name)
            kind, kind_pending = A.resolve_kind(name, it["kind"])
            key = {"key": A.strategy_key("therapy", tt), "normalized": True} if tt else \
                A.drug_key(name) if kind == "drug" else \
                {"key": A.strategy_key({"procedure": "procedure", "diet": "diet"}.get(kind, "supportive_measure"), name), "normalized": True}
            src = {"type": "pmid", "id": p["pmid"], "url": f"https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/"}
            spec = _spec(f"PMID {p['pmid']} ({', '.join(p['pub_types'][:2])}, {p['year']}) recommends {name}.", src, q, text,
                         rec["literature"]["queried_at"], llm, "3a literature")
            spec["extraction_kind"] = {"original": it["kind"], "resolved": kind, "pending": kind_pending}
            spec.update(tier_source="literature", literature={"pub_types": p["pub_types"], "year": p["year"],
                                                              "open_access_full_text": bool(p["full_text"])})
            reqs = []
            if it.get("manifestation") and LG.quote_in(it["manifestation"], text):
                reqs.append({"kind": "other", "text": it["manifestation"], "field": "manifestation",
                             "spec": _spec(spec["claim"], src, it["manifestation"], text, spec["accessed_at"], llm, "3a literature")})
            put(key, "supportive_management", name, [b["id"]], spec, reqs, f"literature PMID {p['pmid']}", source="literature")


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


_SHOWN: dict[str, dict] = {}
CONTEXT_SOURCES = ("nbk", "pmid", "spl_setid")      # L4 guidelines are human-verified: not checked


def context_passage(spec: dict) -> tuple[str, str]:
    """(header, passage) the context check reads for one Tier 1 item: a GeneReviews table row with its table title,
    or the paragraph, under the chapter title and section path; for an article or a label, the text around the quote.
    The first place the quote occurs; context_passages() gives every place."""
    return context_passages(spec)[0]


def context_passages(spec: dict) -> list[tuple[str, str]]:
    """Every (header, passage) holding the item's quote, in section order (user decision 2026-11-12: the same row text
    in a newborn table and in a table for all individuals - CFTR "Salt supplementationExtra salt & water ..." - is
    two passages, each checked on its own; only the first had been read)."""
    src, quote = spec["src"], spec["quote"]
    if src["type"] == "nbk":
        nbk, path = src["id"], src.get("section") or ""
        if nbk not in _SHOWN:
            try:
                _SHOWN[nbk] = GR.sections_for_llm(nbk)
            except (OSError, KeyError, ValueError, RuntimeError):
                _SHOWN[nbk] = {}
        lines = (_SHOWN[nbk].get(path) or "").splitlines()
        found = []
        for i, ln in enumerate(lines):
            if LG.quote_in(quote, ln):
                if ln.startswith("Row "):
                    title = next((lines[j] for j in range(i - 1, -1, -1) if not lines[j].startswith("Row ")), "")
                    ln = f"{title}\n{ln}" if title else ln
                found.append((f"GeneReviews {nbk} ({F.GR_title(nbk) or nbk}), section: {path}", ln))
        if found:
            return found
    text = spec.get("source_text") or ""
    i = text.find(quote[:60]) if quote else -1
    lo, hi = (max(0, i - 1200), i + len(quote) + 1200) if i >= 0 else (0, 2400)
    head = text[:300] if lo > 300 else ""
    kind = {"pmid": "PubMed", "spl_setid": "FDA drug label", "nbk": "GeneReviews"}.get(src["type"], src["type"])
    return [(f"{kind} {src.get('id')}", (head + "\n...\n" if head else "") + text[lo:hi])]


def management_quotes(shown: str, label: str, quote: str) -> list[str]:
    """Presentation only: a named quantitative paragraph and a transplant's own table comment.

    These spans supplement the citation after adjudication; they never become conditions or LLM inputs.
    The caller supplies only the item's source section, so no neighbouring section can supply a qualifier.
    """
    out = []
    for line in shown.splitlines():
        if line.startswith("Paragraph "):
            body = line.split("]: ", 1)[-1] if "]: " in line else line.split(": ", 1)[1]
            if body.casefold().startswith(label.casefold() + ".") and re.search(r"\d", body):
                out.append(body)
        elif line.startswith("Row ") and "transplant" in label.casefold() and LG.quote_in(quote, line):
            out += [m.group(2) for m in _CELL.finditer(line) if m.group(1) == "Comment"]
    return list(dict.fromkeys(out))


def _records(led: LG.Ledger, found: dict, pf: dict, searches: list[dict], use_cache: bool = True) -> None:
    by_id = {b["id"]: b for b in led.branches}
    placed: dict[str, set[str]] = {s: set() for s in SECTIONS_3A}
    unreported: list[str] = []
    collected_order = {k:i for i,k in enumerate(found)}
    for k, a in sorted(found.items()):
        # Keep collection/synonym prompts unchanged. Pregnancy passages become notes only after collection;
        # they cannot create an action, patient requirement, context-check question or missing variable.
        pregnancy_specs = [sp for sp in a["specs"] if sp["src"]["type"] == "nbk" and
                           "pregnancy management" in sp["src"]["section"].lower()]
        clinical_specs = [sp for sp in a["specs"] if sp not in pregnancy_specs]
        if a["pregnancy_only"] or not clinical_specs:
            continue
        why = a["why"]
        if "pregnancy management" in why.lower():
            first = clinical_specs[0]
            why = first["src"]["section"] if first["src"]["type"] == "nbk" else first["claim"]
        a = dict(a, specs=clinical_specs, reqs=[r for r in a["reqs"] if not r.get("pregnancy_passage")], why=why)
        section, branches = a["section"], sorted(a["branches"])

        def make(spec):                                # evidence in the action's final section
            ev = LG.sourced(spec["claim"], section, branches, spec["src"], spec["quote"], spec["source_text"],
                            spec["accessed_at"], produced_by=spec["produced_by"], retrieved_by=spec["retrieved_by"],
                            action=a["key"])
            if spec.get("quote_repaired"):
                ev["quote_repaired"] = spec["quote_repaired"]      # quote is the source span; marked for review
            for fld in ("tier_source", "literature", "verified_manually"):
                if spec.get(fld):
                    ev[fld] = spec[fld]
            return led.add(ev)
        evs = [make(sp) for sp in a["specs"]]
        if not any(e["status"] == "verified" for e in evs):
            continue
        lines, reasons, dedupe = [], {}, set()
        preg_notes = list(dict.fromkeys(sp["quote"] for sp in pregnancy_specs))
        # a targeted drug with an FDA label: the label's conditions decide; GeneReviews conditions are kept as notes
        # (decision 2026-11-04: the GeneReviews ETI row "heterozygous for p.Phe508del & a minimal function variant"
        # would otherwise have overruled the label's "at least one F508del" for a homozygous patient)
        # any label whose indication sentence names the diagnosis decides, whatever its wording or the action's section
        # (decision 2026-11-04: Rivfloza "indicated to lower urinary oxalate levels in ... PH1" gives nedosiran's
        # conditions, age >= 2 and eGFR >= 30; contraindication labels supply no conditions)
        label_rules = section != "contraindications_precautions" and any(
            sp["src"]["type"] == "spl_setid" and sp.get("label_section") in ("existing_targeted_therapies", "supportive_management")
            for sp in a["specs"])
        gr_notes = [r["text"] for r in a["reqs"] if label_rules and r["spec"]["src"]["type"] != "spl_setid"
                    and not r.get("pregnancy_passage") and r.get("field") != "manifestation"]
        use = [r for r in a["reqs"] if (a["pregnancy_only"] or not r.get("pregnancy_passage"))
               and not (label_rules and r["spec"]["src"]["type"] != "spl_setid" and r.get("field") != "manifestation")]
        if label_rules:                      # the label's conditions are the alternatives; the symptom treated applies to all
            use = [dict(r, alternative=None) if r["spec"]["src"]["type"] != "spl_setid" else r for r in use]
        # a supportive action found only in a label: the indication sentence names the complication or symptom it is for
        # (decision 2026-11-04: phytonadione "hypoprothrombinemia secondary to ... cystic fibrosis" was unconditional)
        if section == "supportive_management" and all(sp["src"]["type"] == "spl_setid" for sp in a["specs"]) \
                and not any(r.get("field") == "manifestation" for r in use):
            sp = next(sp for sp in a["specs"] if sp.get("label_section") == "supportive_management") if any(
                sp.get("label_section") == "supportive_management" for sp in a["specs"]) else a["specs"][0]
            use.append({"kind": "other", "text": sp["quote"], "field": "manifestation", "spec": sp})
        precautions, purposes = [], []
        kept = []
        for r in use:                # what the measure prevents is its purpose, not a condition (2026-11-15)
            if r.get("field") == "manifestation" and r.get("spec") and r["spec"]["src"]["type"] == "nbk" \
                    and is_purpose(r["text"], [p for _, p in context_passages(r["spec"])
                                               if any(LG.quote_in(sp["quote"], p) for sp in a["specs"])
                                               or len(context_passages(r["spec"])) == 1]):
                purposes.append(r["text"])
                # removing the purpose removes only the purpose: a table row's manifestation / problem column stays a
                # condition (user decision 2026-11-15: "[Manifestation/Concern: Bone health] [Treatment: Bisphosphonates
                # ... to prevent fractures]")
                for p in context_passages(r["spec"]):
                    m = ROW_CONCERN.search(p[1])
                    if m and any(LG.quote_in(sp["quote"], p[1]) for sp in a["specs"]):
                        col = m.group(1).strip()
                        if col and LG.quote_in(col, r["spec"].get("source_text") or "") and \
                                not any(LG._norm(col) == LG._norm(x["text"]) for x in use + kept):
                            kept.append({"kind": "other", "text": col, "field": "manifestation",
                                         "spec": dict(r["spec"], claim=f"{a['label']}: row concern", quote=col)})
                        break
            else:
                kept.append(r)
        use = kept
        # situational qualifiers next to the treatment are usage-situation conditions (user decision 2026-11-15,
        # dialysis: "Monitor plasma oxalate concentration during transient or permanent periods of low GFR.
        # Initiate dialysis promptly ...") - in the same table cell, or the same sentence of a paragraph
        if section in ("existing_targeted_therapies", "supportive_management"):
            have = [LG._norm(x["text"]) for x in use]
            for sp in a["specs"]:
                if sp["src"]["type"] != "nbk" or a.get("pregnancy_only"):
                    continue
                for phrase in situational_phrases(sp, a["label"]):
                    n = LG._norm(phrase)
                    if any(n in h or h in n for h in have) or not LG.quote_in(phrase, sp.get("source_text") or ""):
                        continue
                    have.append(n)
                    use.append({"kind": "other", "text": phrase, "field": "situation",
                                "spec": dict(sp, claim=f"{a['label']}: used {phrase[:60]}", quote=phrase)})
        for r in use:
            sig = (r.get("field"), r.get("op"), json.dumps(r.get("value"), sort_keys=True), LG._norm(r["text"]),
                   r.get("alternative"))
            if sig in dedupe:
                continue
            dedupe.add(sig)
            rb = branches
            # label conditions outside Indications and Usage are safety precautions (decision 2026-11-04): shown on the
            # card, no effect on the status and no missing information - unless the case states the patient has it
            if "label_part" in r and r["label_part"] != "indications_and_usage":
                st, fact, note = evaluate(r, pf, by_id[rb[0]])
                if st == "satisfies" and PRECAUTION_AVOID.search(r["text"]):
                    ev = make(r["spec"])
                    lines.append(LG.requirement(f"r{len(lines) + 1}", "exclusion", r["text"], ev["id"], fact, "satisfies", rb,
                                                "safety precaution: the case states the patient has this condition"))
                elif r["text"] not in precautions:
                    precautions.append(r["text"])
                continue
            ev = make(r["spec"])
            if r.get("field") == "manifestation":
                st, fact, basis = manifestation_match(r["text"], pf)
                note = f"HPO match: {basis}"
                if st == "unknown" and fact:       # stated only as possible: say so, as missing information
                    note = f"the case states {fact['value']} only as one possibility"
                elif st == "unknown":
                    fact = {"field": MISSING_MANIFESTATIONS, "value": None, "quote": None, "step": None}
                    if (a["label"], r["text"]) not in unreported:
                        unreported.append((a["label"], r["text"]))
            elif r.get("field") == "possible_manifestation":   # the symptom it treats is stated only as possible
                x = r["finding"]
                st, note = "unknown", f"the case states {x['label']} only as one possibility"
                fact = {"field": POSSIBLE_FINDING, "value": x["label"], "quote": x.get("possible_because") or x["quote"],
                        "step": 2}
            elif r.get("field") == "situation":            # used only in that situation: conditional, not compared
                st, fact, note = "unknown", {"field": "usage situation", "value": None, "quote": None, "step": None}, SITUATION_NOTE
            elif r.get("field") == "pregnancy":
                st, fact = pregnancy_status(pf)
                note = "pregnancy-specific management"
            else:
                st, fact, note = evaluate(r, pf, by_id[rb[0]])
            line = LG.requirement(f"r{len(lines) + 1}", r["kind"], r["text"], ev["id"], fact, st, rb, note,
                                  alternative=r.get("alternative"))
            if line["result"] == "unknown" and (fact or {}).get("field") != MISSING_MANIFESTATIONS:
                # one row per variable type (kidney function, age, usage situation, ...), listing the actions
                var = variable_type((fact or {}).get("field") or r.get("field") or "other")
                line["patient_fact"] = dict(fact or {"value": None, "quote": None, "step": None}, field=var)
                led.note_missing(var, a["label"], r["text"][:120], "3a")
            lines.append(line)
        cc, cautions = None, []
        ctx = [i for i, sp in enumerate(a["specs"]) if sp["src"]["type"] in CONTEXT_SOURCES
               and evs[i]["status"] == "verified"]
        if CC.ENABLED and ctx:                           # context check (fix plan, 2026-11-11): answers -> lines
            br = by_id[branches[0]]
            patient = CC.patient_text(pf, br)
            disease = (br.get("diagnosis") or {}).get("label") or ""
            # one check per passage (user decision 2026-11-12): an action merged from several passages (a newborn table
            # and a table for all individuals) is checked on each; a limit belongs to its own passage only
            groups: list[tuple[str, str, list[int]]] = []
            for i in ctx:
                for h, psg in context_passages(a["specs"][i]):
                    g = next((g for g in groups if g[1] == psg), None)
                    if g:
                        g[2].append(i)
                    else:
                        groups.append((h, psg, [i]))
            if label_rules:
                # the FDA label decides this drug's conditions (3a rule of 2026-11-04) and code has already matched its
                # indication to the diagnosis: only the first passage is checked, as before per-passage checking
                # (2026-11-12: checking the label passage too gave a split "is this about the disease?" and made
                # lumasiran conditional for PH1); findings in the other passages would be notes only anyway
                groups = groups[:1]
            ev_spec = {evs[i]["id"]: i for i in range(len(evs))}
            runs = []
            for gi, (header, passage, idx) in enumerate(groups):
                # the first passage is asked about every condition (its questions, and their cached answers, are the
                # ones of the one-passage check); each other passage about the conditions taken from it
                own = lines if gi == 0 else [l for l in lines if ev_spec.get(l["requirement_evidence"]) in idx]
                res = CC.ask(header, passage, patient,
                             CC.questions_3a(section, a["label"], disease, own, a["specs"][idx[0]]["quote"]),
                             use_cache=use_cache)
                # a drug whose FDA label decides its conditions (the 3a rule of 2026-11-04): what the check finds in
                # another source's passage is kept as notes and changes nothing (fix 2026-11-12: a GeneReviews table
                # row of another genotype had made ETI conditional for a F508del homozygous patient the label covers)
                decides = label_rules and a["specs"][idx[0]]["src"]["type"] != "spl_setid"
                followups = {}

                def followup(q, header=header, passage=passage, followups=followups):
                    r = CC.ask(header, passage, patient, CC.questions_limit(a["label"], q), use_cache=use_cache)
                    followups[q] = CC.summary(r)
                    return r["questions"][0]["final"]
                checked, notes = CC.decide_3a(res, own, evs[idx[0]]["id"], passage, branches,
                                              limit_followup=None if decides else followup)
                part = dict(CC.summary(res), notes=notes, header=header, passage=passage)
                if followups:
                    part["limit_followup"] = followups
                added = [l for l in checked if l.get("context_check") in ("scope", "limit")]
                changed = {l["id"]: l for l in checked if l.get("context_check") in ("exemption", "degree")}
                if decides:
                    part["label_decides"] = True
                    part["not_applied"] = [l["requirement"] for l in checked if l.get("context_check")]
                    if part["not_applied"]:
                        part["notes"] = notes + ["not applied: the FDA label decides this drug's conditions"]
                non_rec = False
                if section in CC.RECOMMEND_SECTIONS and not decides:
                    # is this passage recommending it at all? (user decision 2026-11-12, reading rule R15)
                    rq = CC.ask(header, passage, patient, CC.questions_recommendation(a["label"], disease),
                                use_cache=use_cache)
                    part["recommendation"] = CC.summary(rq)
                    non_rec = CC.not_recommended(rq)
                    if non_rec:
                        part["recommendation"]["reason"] = CC.not_recommended_reason(rq, passage)
                runs.append({"part": part, "added": [] if decides else added, "changed": {} if decides else changed,
                             "applied": not decides, "not_recommended": non_rec})
            changed = {}
            for r in runs:                       # an exemption / degree answer changes the line it was asked about
                for lid, l in r["changed"].items():
                    changed.setdefault(lid, l)
            base = [dict(changed[l["id"]]) if l["id"] in changed else l for l in lines]
            applied = [r for r in runs if r["applied"]]
            if len(groups) == 1 or len(applied) <= 1:
                decision = "one passage"
                extra = [l for r in applied for l in r["added"]]
            elif any(not r["added"] for r in applied):
                decision = "a passage with no limit supports the action; other passages' limits kept as notes"
                extra = []
                for r in applied:
                    if r["added"]:
                        r["part"]["not_applied"] = [l["requirement"] for l in r["added"]]
            elif any(l.get("alternative") for l in base):
                decision = "every passage limited; table-row alternatives present, limits kept for all"
                extra = [l for r in applied for l in r["added"]]
            else:
                decision = "every passage limited; each passage is an alternative (any one met decides)"
                extra = [dict(l, alternative=f"passage {gi + 1}") for gi, r in enumerate(runs) if r["applied"]
                         for l in r["added"]]
            for j, l in enumerate(extra, len(base) + 1):
                l["id"] = f"r{j}"
            lines = base + extra
            asked = [r for r in applied if "recommendation" in r["part"]]
            if asked and all(r["not_recommended"] for r in asked):
                # reported no benefit only when every passage says so; otherwise described use (2026-11-15)
                reason = "reports_ineffective" if all(r["part"]["recommendation"].get("reason") == "reports_ineffective"
                                                      for r in asked) else "describes_use"
                # Source wording is not a patient mismatch. Preserve uncertainty rather than excluding.
                wording = ("source describes use; no explicit recommendation" if reason == "describes_use" else
                           "source reports no observed benefit; no explicit recommendation")
                line = LG.requirement(f"r{len(lines) + 1}", "other", wording,
                                      evs[groups[0][2][0]]["id"],
                                      {"field": "source scope", "value": None, "quote": None, "step": None},
                                      "unknown", branches, "context check: " + wording)
                line["recommendation_reason"] = reason
                line["context_check"] = "recommendation"
                lines = lines + [line]
            # the entry's own words are a limitation, the recommending words are elsewhere in the paragraph (user
            # decision 2026-11-15, shockwave lithotripsy: "... the hardest stones, ... resistant to SWL" next to
            # "Although a reasonable option"): cite the recommending sentence, keep the entry's sentence as a caution
            cautions = []
            r0 = runs[0]
            rec_q = ((r0["part"].get("recommendation") or {}).get("answers") or {}).get("recommendation") or {}
            spec0 = a["specs"][groups[0][2][0]]
            if r0["applied"] and not r0["not_recommended"] and rec_q.get("final") == "recommends" \
                    and str(groups[0][1]).startswith("Paragraph") and rec_q.get("quote") \
                    and LG.quote_in(rec_q["quote"], groups[0][1]) and not LG.quote_in(rec_q["quote"], spec0["quote"]):
                body = groups[0][1].split("]: ", 1)[-1] if "]: " in groups[0][1] else groups[0][1].split(": ", 1)[-1]
                sent = next((s for s in re.split(r"(?<=[.!?])\s+", body) if LG.quote_in(rec_q["quote"], s)), None)
                if sent and LG.quote_in(sent, spec0.get("source_text") or ""):
                    new = make(dict(spec0, claim=f"{spec0['claim']} (recommending sentence)", quote=sent))
                    if new["status"] == "verified":
                        evs.insert(0, new)
                        cautions.append(spec0["quote"])
            cc = dict(runs[0]["part"])
            cc_notes = cc["notes"] = list(cc["notes"])
            if len(groups) > 1:
                cc["other_passages"] = [r["part"] for r in runs[1:]]
                cc["passage_decision"] = decision
            # an age-band limit is decided by code against the stated age (user decision 2026-11-12, ICH E11)
            for l in lines:
                if l.get("context_check") != "limit":
                    continue
                got = AB.limit_status(l["requirement"], pf, disease)
                if got is None:
                    continue
                st, fact, why = got
                l.update(patient_status=st, result=LG.requirement_result(l["kind"], st), patient_fact=fact,
                         note=f"{l['note']} | {why}")
                cc_notes.append(why)
                if st == "unknown" and not fact.get("quote"):
                    led.note_missing(variable_type("age"), a["label"], l["requirement"][:120], "3a")
            for l in lines:                # a degree the patient was not shown to reach is ordinary missing information
                if l.get("context_check") == "degree":
                    var = variable_type((l.get("patient_fact") or {}).get("field") or "other")
                    l["patient_fact"] = dict(l.get("patient_fact") or {}, field=var)
                    led.note_missing(var, a["label"], l["requirement"][:120], "3a")
        for b in branches:
            st, alt = LG.status_of(lines, b)
            mine = [l for l in lines if b in l["applies_to"] and l.get("alternative") in (None, alt)]
            bad = [l["requirement"] for l in mine if l["result"] == "fail"]
            unk = [l["requirement"] for l in mine if l["result"] == "unknown"]
            met = [l["requirement"] for l in mine if l["result"] == "pass" and l.get("alternative")]
            split = any(l.get("check_votes_disagreed") for l in mine if l["result"] == "unknown")
            reasons[b] = (f"not met: {bad[0][:80]}" if bad else "check votes disagreed; unknown" if split else f"depends on: {unk[0][:80]}" if unk
                          else f"met: {'; '.join(met)[:80]}" if met else a["why"][:90])
            if preg_notes and not bad and not split and unk:
                unknown = next(l for l in mine if l["result"] == "unknown")
                if unknown.get("context_check") == "scope":
                    src = led.evidence[unknown["requirement_evidence"]]["source"]
                    if src["type"] == "nbk":
                        reasons[b] = (f"unconfirmed: whether GeneReviews {src['id']} ({src['section']}) applies to "
                                      f"{by_id[b]['diagnosis']['label']}; source-scope check unknown")
        kinds = [sp["extraction_kind"] for sp in a["specs"] if "extraction_kind" in sp]
        if any(kind["pending"] for kind in kinds):
            pending_line = LG.requirement(f"r{len(lines) + 1}", "other", "intervention type requires verification",
                                          next(e["id"] for e in evs if e["status"] == "verified"),
                                          {"field": "source scope", "value": None, "quote": None, "step": None},
                                          "unknown", branches, "context check: intervention type unresolved by code; not a model verdict")
            pending_line["context_check"] = "scope"
            pending_line["kind_resolution_pending"] = True
            lines.append(pending_line)
        rec = LG.action_record(k, section, a["label"], branches, lines, [e["id"] for e in evs if e["status"] == "verified"],
                               reasons)
        positions = [sp['source_order'] for sp in a['specs'] if 'source_order' in sp]
        rec['source_order'] = min(positions) if positions else [1000000,collected_order[k],0]
        if not positions:
            rec['source_order_note'] = 'source position not recorded; collection order retained'
        presentation = []
        for sp in a["specs"]:
            for q in sp.get("presentation_quotes", []):
                extra = make(dict(sp, quote=q, claim=f"{a['label']}: full source management passage",
                                  produced_by="code", retrieved_by="3a verbatim presentation context"))
                presentation.append(extra["id"])
        if presentation:
            rec["presentation_evidence_ids"] = list(dict.fromkeys(presentation))
            rec["evidence_ids"] += [i for i in rec["presentation_evidence_ids"] if i not in rec["evidence_ids"]]
        if cc is not None:
            rec["context_check"] = cc
            if cautions:
                rec["cautions"] = cautions
        if purposes:
            rec["purposes"] = sorted(set(purposes))
        if section == "supportive_management":
            rec["tier_source"] = F.best_tier(a["specs"])
            if a.get("for_symptom"):
                rec["for_symptom"] = a["for_symptom"]
        if preg_notes:
            rec["pregnancy_notes"] = sorted(set(preg_notes))
            note_evidence = [make(sp) for sp in pregnancy_specs]
            rec["pregnancy_note_evidence_ids"] = [e["id"] for e in note_evidence if e["status"] == "verified"]
            rec["evidence_ids"] = sorted(set(rec["evidence_ids"] + rec["pregnancy_note_evidence_ids"]))
        if gr_notes:
            rec["genereviews_notes"] = sorted(set(gr_notes))
        if precautions:
            rec["precautions"] = precautions
        for fld in ("merged_from", "includes", "narrower_than"):
            if a.get(fld):
                rec[fld] = a[fld]
        if a.get("narrower_than"):                # written once, under the broader action
            rec["report"] = False
            rec["report_note"] = f"included in the broader action '{a['narrower_than']['label']}'"
        if a["pregnancy_only"] and all(v["status"] == "not_applicable" for v in rec["status_by_branch"].values()):
            rec["report"] = False            # kept in the ledger, not written to the report (Step 4 decides the rules)
            rec["report_note"] = "pregnancy-specific management; patient is male or under 12"
        if kinds:
            rec["extraction_kinds"] = kinds
        if any(k["pending"] for k in kinds):
            rec["kind_review_pending"] = True
        led.actions.append(rec)
        for b in branches:
            placed[section].add(b)
    present = {rec["action_key"] for rec in led.actions if rec.get("action_key")}
    for rec in led.actions:
        if rec.get("narrower_than") and rec["narrower_than"]["key"] not in present:
            # A removed pregnancy-only parent cannot stand in for this clinical action.
            rec.pop("narrower_than")
            rec.pop("report", None)
            rec.pop("report_note", None)
    for a_label, text in unreported:
        led.note_missing(MISSING_MANIFESTATIONS, a_label, text, "3a")
    for s in SECTIONS_3A:
        led.mark_searched(s)
        empty = [b["id"] for b in led.branches if b["id"] not in placed[s]]
        if empty:
            neg = led.add(LG.negative(s, empty, database="genereviews + openfda drug label",
                                      endpoint="; ".join(x["endpoint"] for x in searches)[:2000],
                                      query=f"{s.replace('_', ' ')} for: " + ", ".join((by_id[b].get('diagnosis') or {}).get('label', b) for b in empty),
                                      queried_at=max([x["queried_at"] for x in searches] or [0]) or 1,
                                      n_results=0, response_count=0,
                                      claim=f"No {s.replace('_', ' ')} found in the GeneReviews Management sections or FDA labels searched "
                                            f"({len(searches)} searches)."))
            led.actions.append(LG.action_record(None, s, "None found", empty, [], [neg["id"]],
                                                {b: "searched GeneReviews and FDA labels; none found" for b in empty},
                                                searched_none=True))

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
from aitx.evidence import genereviews as GR
from aitx.evidence import labels as LB
from aitx.evidence import ledger as LG
from aitx.evidence import support_check as SC
from aitx.evidence import variants as V

PROMPT_VERSION = "3a-v2"          # prompts unchanged on 2026-11-04 (rules in code only)
SECTIONS_3A = ("existing_targeted_therapies", "supportive_management", "contraindications_precautions")
SKIP_SECTIONS = ("surveillance", "therapies under investigation", "evaluations following initial diagnosis",
                 "evaluation of relatives at risk")
TARGETED_TITLES = ("targeted therapies", "targeted therapy")
REQ_FIELDS = ("age", "sex", "variant", "variant_class", "zygosity", "kidney_function", "liver_function", "weight")
NOT_A_THERAPY = {"supportive care", "targeted therapies", "targeted therapy", "treatment", "management",
                 "treatment of manifestations", "therapy", "care"}
CHILD_YEARS = 12                      # pregnancy items: male or under 12 -> not applicable (decision 2026-11-03)
MISSING_MANIFESTATIONS = "manifestations not reported"

CHAPTERS_SYSTEM = """You match diagnoses to GeneReviews chapters. For each numbered diagnosis, list the numbers of the
chapters whose subject is that diagnosis or a broader disorder group that includes it. A chapter about a different
disorder caused by the same gene does not count. Return only JSON:
{"links": [{"diagnosis": <number>, "chapters": [<chapter numbers>]}]}"""

_REQ_SHAPE = """{"text": "<exact words>", "field": "age" | "sex" | "variant" | "variant_class" | "zygosity" |
 "kidney_function" | "liver_function" | "weight", "op": ">=" | "<=" | ">" | "<" | "==" | "in" | "",
 "value": <number or list of strings or "">, "unit": "year" | "month" | ""}"""

EXTRACT_SYSTEM = """You list the management actions in one GeneReviews Management section. Use only the text given.
List only specific treatments: a named drug, a procedure, a diet, a device - or, in a section about agents or
circumstances to avoid, each agent or circumstance to avoid. Do not list section headings, symptoms, conditions,
tests, surveillance, follow-up or referrals. For each, return one item:
{"name": "<generic drug name or short procedure name, no brand names, no doses>",
 "kind": "drug" | "procedure" | "diet" | "device" | "avoid",
 "quote": "<the exact sentence or table row that names it, copied character for character>",
 "manifestation": "<the exact words naming the symptom or complication it treats, or empty>",
 "requirements": [<restrictions on WHICH PATIENTS should get it, by a patient characteristic; each """ + _REQ_SHAPE + """>],
 "mechanism_quote": "<exact words saying it acts on the defective gene product or disease mechanism, or empty>"}
Requirements are only restrictions by age, sex, variant / genotype, variant type, zygosity, kidney or liver function or
weight, with their words copied exactly from the quote. Timing, settings, "if needed" and statements about effect are not
requirements. Return only JSON: {"items": [...]}. Do not invent items or words."""

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
    return X._parse(r)["parsed"], {"llm": X.llm.config()["model"], "served_model": r.get("served_model"),
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
    return {"age_months": f["age"].get("months"), "age_quote": f["age"].get("quote"),
            "sex": f["sex"].get("value"), "sex_quote": f["sex"].get("quote"),
            "variants": [{"gene": v["gene"], "protein": v["variant_protein"], "class": v["variant_class"],
                          "zygosity": v["zygosity"], "quote": f"{v['gene']} {v['variant_cdna']} {v['variant_protein']} ({v['zygosity']})"}
                         for v in step1["variants"]],
            "present": [x for x in step2["phenotypes"] if x["status"] == "present"],
            "excluded": [x for x in step2["phenotypes"] if x["status"] == "excluded"]}


# values a variant_class / zygosity requirement can be compared on; anything else is unknown, never "not met"
VARIANT_CLASS_WORDS = ("missense", "nonsense", "frameshift", "synonymous", "splice", "inframe", "in-frame", "in_frame",
                       "start_loss", "start loss", "stop_gain", "stop gain", "deletion", "duplication", "insertion", "delins")
ZYGOSITY_WORDS = ("homozygous", "heterozygous", "hemizygous", "compound")


def _years(value, unit) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v / 12 if unit == "month" else v


def evaluate(req: dict, pf: dict, branch: dict) -> tuple[str, dict | None, str]:
    """(patient_status, patient_fact, note) for one requirement; code only."""
    field, op, value = req.get("field"), req.get("op"), req.get("value")
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
        if field == "variant":
            hit = V.mentioned(v["protein"], req.get("_label_text") or req["text"])
            return ("satisfies" if hit else "unknown"), fact, (f"named as {hit}" if hit else "patient's variant not found in the text")
        want = [str(x).lower() for x in (value if isinstance(value, list) else [value]) if x]
        have = v["class"] if field == "variant_class" else v["zygosity"]
        known = VARIANT_CLASS_WORDS if field == "variant_class" else ZYGOSITY_WORDS
        if not want or not all(any(k in w for k in known) for w in want):
            return "unknown", fact, "requirement not comparable"
        return ("satisfies" if any(w.replace(" ", "_") in have or have in w for w in want) else "does_not_satisfy"), fact, ""
    if field == "sex" and pf["sex"] in ("male", "female"):
        want = str(value).lower()
        return ("satisfies" if want.startswith(pf["sex"][0]) else "does_not_satisfy"), \
            {"field": "sex", "value": pf["sex"], "quote": pf["sex_quote"], "step": 2}, ""
    if field == "diagnosis":
        d = branch.get("diagnosis") or {}
        names = [d.get("label", "")] + list(branch.get("synonyms") or [])
        ok = any(n and n.lower() in req["text"].lower() for n in names)
        return ("satisfies" if ok else "unknown"), {"field": "diagnosis", "value": d.get("label"),
                                                    "quote": d.get("label"), "step": 2}, ""
    return "unknown", None, f"{field or 'requirement'} not stated in the case"


def manifestation_status(text: str, pf: dict) -> tuple[str, dict | None]:
    """Does the patient have the manifestation a supportive measure treats? HPO match by code."""
    ont = ontology()
    ids = set(ont.exact_lookup(text)) or {c["hpo_id"] for c in ont.search(text, 1)}
    for x in pf["present"]:
        if x["hpo_id"] in ids or ids & set(ont.ancestors(x["hpo_id"])):
            return "satisfies", {"field": "manifestation", "value": x["label"], "quote": x["quote"], "step": 2}
    for x in pf["excluded"]:
        if x["hpo_id"] in ids:
            return "does_not_satisfy", {"field": "manifestation", "value": f"NOT {x['label']}", "quote": x["quote"], "step": 2}
    return "unknown", None


# ------------------------------------------------------------------ branches -> chapters

def disease_names(branch: dict, step2: dict) -> list[str]:
    c = next((c for c in step2["candidates"] if c["key"] == branch["id"]), {})
    return [n for n in [c.get("label")] + list(c.get("synonyms") or []) if n]


def chapters_for(led: LG.Ledger, step2: dict, use_cache: bool) -> dict[str, list[str]]:
    gene_chapters = [ch for chs in (step2.get("genereviews") or {}).values() for ch in chs]
    branches = [b for b in led.branches if b.get("diagnosis")]
    if not gene_chapters or not branches:
        return {b["id"]: [] for b in led.branches}
    if len(gene_chapters) == 1:
        return {b["id"]: [gene_chapters[0]["nbk"]] for b in led.branches}
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


def _reqs(raw: list, spec: dict, where: str) -> list[dict]:
    """Structured requirements whose words are in `where`; other kinds of sentences are dropped."""
    out = []
    for r in raw or []:
        if isinstance(r, dict) and r.get("field") in REQ_FIELDS and LG.quote_in(str(r.get("text") or ""), where):
            out.append({**r, "kind": "label_condition", "spec": spec})
    return out


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
        for name in [n for n in names if searchable_name(n)]:
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


def add_established(led: LG.Ledger, step1: dict, step2: dict, *, use_cache: bool = True) -> None:
    pf = facts(step1, step2)
    for b in led.branches:
        b["synonyms"] = disease_names(b, step2)[1:]
    ch_map = chapters_for(led, step2, use_cache)
    acc_book = D.ensure("genereviews_book").downloaded_at
    found: dict[str, dict] = {}          # action key -> {key, section, label, branches, specs, reqs, why}
    searches: list[dict] = []

    def put(key: dict, section: str, label: str, branch_ids: list[str], spec: dict, reqs: list[dict], why: str,
            pregnancy: bool = False):
        a = found.setdefault(key["key"], {"key": key, "section": section, "label": label, "branches": set(),
                                          "specs": [], "reqs": [], "why": why, "pregnancy_only": pregnancy})
        if SECTIONS_3A.index(section) < SECTIONS_3A.index(a["section"]):
            a["section"], a["why"] = section, why          # targeted before supportive before precautions
        a["pregnancy_only"] = a["pregnancy_only"] and pregnancy
        a["branches"].update(branch_ids)
        a["specs"].append(spec)
        a["reqs"] += reqs

    # GeneReviews: one LLM call per section (a whole chapter at once is too long for the API), in parallel
    for nbk in sorted({n for ns in ch_map.values() for n in ns}):
        secs = mgmt_sections(nbk)
        branch_ids = [b for b, ns in ch_map.items() if nbk in ns]
        searches.append({"database": "genereviews", "endpoint": GR.BOOK_URL.format(nbk=nbk),
                         "query": f"{nbk} Management sections", "queried_at": acc_book, "n_results": len(secs)})
        if not secs:
            continue
        has_targeted = any(any(t in p.lower() for t in TARGETED_TITLES) for p, _ in secs)
        with ThreadPoolExecutor(max_workers=X.CONCURRENCY) as pool:
            per_sec = list(pool.map(lambda pt: _llm(EXTRACT_SYSTEM, f"Section: {pt[0]}\n{pt[1][:6000]}", use_cache,
                                                   f"GeneReviews {nbk} '{pt[0]}'"), secs))
        for (path, text), (parsed, llm) in zip(secs, per_sec):
            low = path.lower()
            avoid, pregnancy = "avoid" in low, "pregnancy" in low
            for it in parsed.get("items") or []:
                name = str(it.get("name") or "").strip()
                kind = it.get("kind")
                if not name or name.lower() in NOT_A_THERAPY:
                    continue
                if not LG.quote_in(str(it.get("quote") or ""), text):
                    it = _repaired_item(it, name, path, text, use_cache, nbk)
                    if it is None:
                        continue
                    llm = it.pop("_llm")
                if not avoid and kind not in ("drug", "procedure", "diet", "device"):
                    continue
                if avoid:
                    section = "contraindications_precautions"
                elif any(t in low for t in TARGETED_TITLES):
                    section = "existing_targeted_therapies"
                else:
                    section = "supportive_management"
                key = A.drug_key(name) if kind == "drug" or (avoid and kind == "avoid" and A.drug_key(name)["normalized"]) \
                    else {"key": A.strategy_key({"procedure": "procedure", "diet": "diet"}.get(kind, "supportive_measure"), name),
                          "normalized": True}
                src = {"type": "nbk", "id": nbk, "url": GR.BOOK_URL.format(nbk=nbk), "section": path, "credit": GR.CREDIT}
                claim = f"GeneReviews ({path}) lists {name}" + (f" for {it['manifestation']}" if it.get("manifestation") else "") + "."
                spec = _spec(claim, src, it["quote"], text, acc_book, llm, f"3a genereviews {nbk}")
                if it.get("quote_repaired"):
                    spec["quote_repaired"] = it["quote_repaired"]
                reqs = _reqs(it.get("requirements"), spec, it["quote"])
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
                put(key, section, name, branch_ids, spec, reqs, why, pregnancy)

    # FDA labels: by indication and contraindication for every diagnosis name (names shorter than 4 characters and
    # one-word abbreviations skipped), and by exact generic name for drugs GeneReviews lists in Targeted or Supportive
    tasks = []
    for b in [b for b in led.branches if b.get("diagnosis")]:
        for name in dict.fromkeys(n for n in disease_names(b, step2) if searchable_name(n)):
            tasks.append(("indications_and_usage", name, 10, [b["id"]], None, "label indication names the diagnosis"))
            tasks.append(("contraindications", name, 5, [b["id"]], "contraindications_precautions", "label contraindication names the diagnosis"))
    for k, a in list(found.items()):
        if a["key"].get("normalized") and k.startswith("drug:") and a["section"] in ("existing_targeted_therapies", "supportive_management"):
            tasks.append(("openfda.generic_name", a["label"], 5, sorted(a["branches"]), None, "label for a drug GeneReviews lists"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda t: LB.search(t[0], t[1], limit=t[2]), tasks))
    jobs, seen = [], set()               # (label, text, disease, branch ids, section, why, quote)
    for (field, name, _, bids, section, why), (labels, rec) in zip(tasks, results):
        searches.append(rec)
        for lb in LB.latest(labels)[:5]:
            ind = lb["sections"].get("indications_and_usage", "")
            job = None
            if field == "contraindications":
                m = re.search(rf"[^.]*(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])[^.]*\.", lb["sections"].get("contraindications", ""), re.I)
                if m:
                    job = (lb, lb["sections"].get("contraindications", ""), name, bids, section, why, m.group(0).strip())
            else:
                # the indication sentence decides: the diagnosis as the condition treated -> targeted; as the setting of
                # a complication or symptom -> supportive; a drug GeneReviews lists is promoted only to targeted, and only
                # by a label of exactly that drug (not a combination product); otherwise it keeps its GeneReviews evidence
                names = [n for b in led.branches if b["id"] in bids for n in disease_names(b, step2)]
                if field == "openfda.generic_name" and A.components(lb.get("generic") or "") != A.components(name):
                    continue
                role = indication_role(ind, names)
                if role and (field == "indications_and_usage" or role[0] == "targeted"):
                    sec = "existing_targeted_therapies" if role[0] == "targeted" else "supportive_management"
                    why_ = why + ("" if role[0] == "targeted" else " (complication or symptom of the diagnosis)")
                    job = (lb, ind, role[2], bids, sec, why_, role[1])
            if job and (lb["set_id"], job[4]) not in seen:
                seen.add((lb["set_id"], job[4]))
                jobs.append(job)
    with ThreadPoolExecutor(max_workers=X.CONCURRENCY) as pool:
        parsed = list(pool.map(lambda j: _label_requirements(j[0], j[2], use_cache)
                               if j[4] == "existing_targeted_therapies" else None, jobs))
    for (lb, text, name, bids, section, why, quote), reqs in zip(jobs, parsed):
        _label_action(put, lb, text, name, bids, section, why, reqs, quote=quote)

    _records(led, found, pf, searches)


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
             + ("indicated" if section == "existing_targeted_therapies" else "contraindicated or cautioned") + f" in {disease}.")
    spec = _spec(claim, src, q, text, lb["accessed_at"], "code", f"3a openfda {why}")
    lt = _label_text(lb)
    reqs = []
    for r in _reqs(raw_reqs, None, lt):
        r["spec"] = _spec(f"{name} label requirement: {r['text']}", src, r["text"], lt, lb["accessed_at"], "code",
                          "3a openfda requirement")
        r["_label_text"] = lb["full_text"]
        reqs.append(r)
    put(key, section, name, branch_ids, spec, reqs, why)


def pregnancy_status(pf: dict) -> tuple[str, dict | None]:
    """Pregnancy-specific management (decision 2026-11-03): male or under 12 -> not applicable;
    female 12 or older, or sex unknown and older than 12 -> conditional (pregnancy status unknown)."""
    age = pf["age_months"] / 12 if pf["age_months"] is not None else None
    if pf["sex"] == "male":
        return "does_not_satisfy", {"field": "sex", "value": "male", "quote": pf["sex_quote"], "step": 2}
    if age is not None and age < CHILD_YEARS:
        return "does_not_satisfy", {"field": "age", "value": f"{age:g} years", "quote": pf["age_quote"], "step": 2}
    return "unknown", {"field": "pregnancy status", "value": None, "quote": None, "step": None}


def _records(led: LG.Ledger, found: dict, pf: dict, searches: list[dict]) -> None:
    by_id = {b["id"]: b for b in led.branches}
    placed: dict[str, set[str]] = {s: set() for s in SECTIONS_3A}
    unreported: list[str] = []
    for k, a in sorted(found.items()):
        section, branches = a["section"], sorted(a["branches"])

        def make(spec):                                # evidence in the action's final section
            ev = LG.sourced(spec["claim"], section, branches, spec["src"], spec["quote"], spec["source_text"],
                            spec["accessed_at"], produced_by=spec["produced_by"], retrieved_by=spec["retrieved_by"],
                            action=a["key"])
            if spec.get("quote_repaired"):
                ev["quote_repaired"] = spec["quote_repaired"]      # quote is the source span; marked for review
            return led.add(ev)
        evs = [make(sp) for sp in a["specs"]]
        if not any(e["status"] == "verified" for e in evs):
            continue
        lines, reasons, dedupe = [], {}, set()
        # conditions written for pregnancy decide only pregnancy-only actions; a drug that also has a general
        # recommendation keeps them as notes (2026-11-04: "known to be pyridoxine responsive" from Pregnancy
        # Management had made pyridoxine not applicable for a homozygous p.Gly170Arg patient)
        preg_notes = [r["text"] for r in a["reqs"] if r.get("pregnancy_passage") and not a["pregnancy_only"]]
        # a targeted drug with an FDA label: the label's conditions decide; GeneReviews conditions are kept as notes
        # (decision 2026-11-04: the GeneReviews ETI row "heterozygous for p.Phe508del & a minimal function variant"
        # would otherwise have overruled the label's "at least one F508del" for a homozygous patient)
        label_rules = section == "existing_targeted_therapies" and any(sp["src"]["type"] == "spl_setid" for sp in a["specs"])
        gr_notes = [r["text"] for r in a["reqs"] if label_rules and r["spec"]["src"]["type"] != "spl_setid"
                    and not r.get("pregnancy_passage")]
        for r in [r for r in a["reqs"] if (a["pregnancy_only"] or not r.get("pregnancy_passage"))
                  and not (label_rules and r["spec"]["src"]["type"] != "spl_setid")]:
            sig = (r.get("field"), r.get("op"), json.dumps(r.get("value"), sort_keys=True), LG._norm(r["text"]))
            if sig in dedupe:
                continue
            dedupe.add(sig)
            ev = make(r["spec"])
            rb = branches
            if r.get("field") == "manifestation":
                st, fact = manifestation_status(r["text"], pf)
                note = ""
                if st == "unknown":
                    fact = {"field": MISSING_MANIFESTATIONS, "value": None, "quote": None, "step": None}
                    if r["text"] not in unreported:
                        unreported.append(r["text"])
            elif r.get("field") == "pregnancy":
                st, fact = pregnancy_status(pf)
                note = "pregnancy-specific management"
            else:
                st, fact, note = evaluate(r, pf, by_id[rb[0]])
            line = LG.requirement(f"r{len(lines) + 1}", r["kind"], r["text"], ev["id"], fact, st, rb, note)
            if line["result"] == "unknown" and (fact or {}).get("field") != MISSING_MANIFESTATIONS:
                var = (fact or {}).get("field") or f"{r.get('field')}: {r['text'][:60]}"
                line["patient_fact"] = fact or {"field": var, "value": None, "quote": None, "step": None}
                if var not in {m["variable"] for m in led.missing_information}:
                    led.missing_information.append({"variable": var, "why_it_matters": f"{a['label']}: {r['text'][:120]}",
                                                    "affects": [], "asked_by": "3a"})
            lines.append(line)
        for b in branches:
            bad = [l["requirement"] for l in lines if b in l["applies_to"] and l["result"] == "fail"]
            unk = [l["requirement"] for l in lines if b in l["applies_to"] and l["result"] == "unknown"]
            reasons[b] = (f"not met: {bad[0][:80]}" if bad else f"depends on: {unk[0][:80]}" if unk else a["why"][:90])
        rec = LG.action_record(k, section, a["label"], branches, lines, [e["id"] for e in evs if e["status"] == "verified"],
                               reasons)
        if preg_notes:
            rec["pregnancy_notes"] = sorted(set(preg_notes))
        if gr_notes:
            rec["genereviews_notes"] = sorted(set(gr_notes))
        if a["pregnancy_only"] and all(v["status"] == "not_applicable" for v in rec["status_by_branch"].values()):
            rec["report"] = False            # kept in the ledger, not written to the report (Step 4 decides the rules)
            rec["report_note"] = "pregnancy-specific management; patient is male or under 12"
        led.actions.append(rec)
        for b in branches:
            placed[section].add(b)
    if unreported:
        led.missing_information.append({"variable": MISSING_MANIFESTATIONS, "affects": [], "asked_by": "3a",
                                        "why_it_matters": "supportive measures apply if these occur: " + "; ".join(unreported)})
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

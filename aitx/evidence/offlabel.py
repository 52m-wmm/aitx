"""Step 3c: Off-label or Expanded-Access Therapies (contract docs/step3c_contract.md, draft v2 approved 2026-11-05).

A therapy belongs here when at least one patient with this disease (or gene) received it - a resolvable, not retracted
PMID whose quote names both the drug and the disease or gene - and it is not approved for this disease (3a) and not
only reachable through a recruiting trial (3b).

  code  searches PubMed (abstracts + PMC open-access full text, shared with the fallback chain's L3), drops retracted
        papers and papers without accessible text, decides the study design from PubMed fields, checks every quote,
        decides the efficacy direction through the 3.0 support check, aggregates per drug in a fixed order, decides the
        US status (FDA label / supplement list / expanded access), dedupes against 3a and 3b, compares conditions
  LLM   only lifts verbatim quotes (use, patient count, outcome, co-treatment, dose, design words, conditions)
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path

from aitx import http
from aitx.evidence import actions as A
from aitx.evidence import established as E
from aitx.evidence import fallback as F
from aitx.evidence import labels as LB
from aitx.evidence import ledger as LG
from aitx.evidence import support_check as SC
from aitx.evidence import trials as T

ROOT = Path(__file__).resolve().parents[2]
SECTION = "off_label_expanded_access"
PROMPT_VERSION = "3c-v1"
N_PAPERS = 20                                     # decision 4
SUPPLEMENTS = ROOT / "config" / "supplements.json"
SUPPLEMENT_NOTE = "Not an FDA-approved drug; product quality and dosing are not regulated."
UNCONFIRMED_NOTE = "Access route not confirmed; confirm with the treating physician."
GRAS_DIR = ROOT / ".cache" / "fda_gras"               # FDA GRAS Notice Inventory export (not committed; date in the file)
ROUTES = ("fda_approved", "dietary_supplement", "food_substance_gras", "expanded_access", "trial_only", "unconfirmed")
DIRECTIONS = ("positive", "negative", "mixed", "not_reported", "combined_unattributable")
TREAT_TERMS = ('treatment[tiab] OR therapy[tiab] OR treated[tiab] OR supplementation[tiab] OR "off-label"[tiab] OR '
               'compassionate[tiab] OR administered[tiab] OR received[tiab]')
_NUM_WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                         "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}


# ------------------------------------------------------------------ search (no publication-type filter: contract)

def query(gene: str | None, names: list[str]) -> str:
    dz = " OR ".join(f'"{n}"[tiab]' for n in E.label_names(names))
    subject = " OR ".join(x for x in ((f"{gene}[tiab]" if gene else ""), dz) if x)
    return f"({subject}) AND ({TREAT_TERMS})"


def _json(url: str) -> dict:
    return json.loads(http.get(url, timeout=60).text)


def search(gene: str | None, names: list[str]) -> dict:
    """{query, url, queried_at, count, truncated, papers}. Retracted papers and papers without accessible text are kept
    in the record with the reason; they never become precedents."""
    q = query(gene, names)
    url = f"{F.EUTILS}/esearch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "sort": "relevance",
                                                               "retmax": N_PAPERS, "term": q})
    d = _json(url)["esearchresult"]
    ids, count = d.get("idlist") or [], int(d.get("count") or 0)
    rec = {"query": q, "url": url, "queried_at": int(time.time()), "count": count, "truncated": count > N_PAPERS, "papers": []}
    if not ids:
        return rec
    summ = _json(f"{F.EUTILS}/esummary.fcgi?db=pubmed&retmode=json&id={','.join(ids)}")["result"]
    xml = http.get(f"{F.EUTILS}/efetch.fcgi?db=pubmed&retmode=xml&id={','.join(ids)}", timeout=60).text
    abstracts, titles, retracted = F.abstracts_by_pmid(xml), titles_by_pmid(xml), retraction_notices(xml)
    for pmid in ids:
        s = summ.get(pmid) or {}
        types = list(s.get("pubtype") or [])
        pmc = next((a["value"] for a in s.get("articleids") or [] if a.get("idtype") == "pmc"), None)
        p = {"pmid": pmid, "title": titles.get(pmid) or s.get("title") or "", "year": (s.get("pubdate") or "")[:4],
             "pub_types": types, "pmc": pmc, "oa": None, "abstract": abstracts.get(pmid, ""), "full_text": ""}
        if "Retracted Publication" in types or retracted.get(pmid):
            p["excluded"] = f"retracted ({retracted.get(pmid) or 'PubMed publication type'})"
        elif pmc:
            try:
                p["oa"], p["full_text"], p["license"] = F.pmc_open_access_text(pmc)
            except (RuntimeError, ValueError, OSError) as e:
                p["oa"], p["oa_error"] = None, f"{type(e).__name__}: {e}"[:200]
        if not p.get("excluded") and not (p["abstract"] or p["full_text"]):
            p["excluded"] = "no accessible text (no abstract, no open-access full text)"
        rec["papers"].append(p)
    return rec


def titles_by_pmid(xml: str) -> dict[str, str]:
    out = {}
    for art in re.findall(r"<PubmedArticle>.*?</PubmedArticle>", xml or "", re.S):
        m, t = re.search(r"<PMID[^>]*>(\d+)</PMID>", art), re.search(r"<ArticleTitle>(.*?)</ArticleTitle>", art, re.S)
        if m and t:
            out[m.group(1)] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t.group(1))).strip()
    return out


def retraction_notices(xml: str) -> dict[str, str]:
    out = {}
    for art in re.findall(r"<PubmedArticle>.*?</PubmedArticle>", xml or "", re.S):
        m = re.search(r"<PMID[^>]*>(\d+)</PMID>", art)
        r = re.search(r'<CommentsCorrections RefType="RetractionIn">.*?<RefSource>(.*?)</RefSource>', art, re.S)
        if m and r:
            out[m.group(1)] = re.sub(r"\s+", " ", r.group(1)).strip()
    return out


def paper_text(p: dict) -> str:
    """The text quotes are checked against: title, abstract, open-access full text."""
    return "\n".join(x for x in (p.get("title"), p.get("abstract"), p.get("full_text")) if x)


# ------------------------------------------------------------------ study design and counts (code)

def design(pub_types: list[str], design_quote: str = "") -> str | None:
    """From PubMed publication types first; design words verbatim in the article second; else None ("not stated")."""
    t = set(pub_types or [])
    if t & {"Randomized Controlled Trial", "Controlled Clinical Trial"}:
        return "controlled"
    if any(x.startswith("Clinical Trial") for x in t):
        return "open_label"
    if "Observational Study" in t:
        return "case_series"
    if "Case Reports" in t:
        return "case_report"
    q = (design_quote or "").lower()
    if re.search(r"\brandomi[sz]ed\b|\bplacebo\b|\bdouble[- ]blind", q) and not re.search(r"\bnon[- ]?randomi[sz]ed\b", q):
        return "controlled"
    if re.search(r"\bopen[- ]label\b|\bsingle[- ]arm\b|\bnon[- ]?randomi[sz]ed\b|\bpilot\b", q):
        return "open_label"
    if re.search(r"\bcase series\b|\bretrospective\b|\bcohort\b", q):
        return "case_series"
    return None


def number_in(n, quote: str) -> bool:
    if n is None:
        return True
    low = (quote or "").lower()
    nums = [int(x) for x in re.findall(r"\b\d+\b", low)] + [v for w, v in _NUM_WORDS.items() if re.search(rf"\b{w}\b", low)]
    try:
        return int(n) in nums
    except (TypeError, ValueError):
        return False


# ------------------------------------------------------------------ precedent extraction and checks

SYSTEM = """You read one article about patients with a genetic disease and list every drug, supplement or other medicinal
product that patients with this disease (or with variants in this gene) actually received in the work reported.
Do not list products only proposed, only tested in cells or animals, or given for another disease. Copy every quote
character for character from the text. For each product return one item:
{"name": "<product name>",
 "use_quote": "<the sentence saying patients with this disease or gene received it>",
 "n_quote": "<the words giving how many patients received it, or empty>", "n_disease": <number with this disease or gene, or null>,
 "n_total": <number of all treated patients, or null>,
 "outcome_quote": "<the sentence stating the result for these patients, or empty>",
 "direction": "positive" | "negative" | "mixed" | "not_reported",
 "co_treatment_quote": "<the words naming another treatment given at the same time, or empty>",
 "dose_quote": "<the words giving the dose used, or empty>",
 "design_quote": "<the words describing the study design (open-label, randomized, case series...), or empty>",
 "conditions": [{"text": "<exact words of a patient characteristic the use was restricted to>",
                 "field": "age" | "variant_function" | "variant" | "variant_class" | "kidney_function" | "liver_function" | "other"}]}
Return only JSON: {"items": [...]}"""


def _llm(user: str, use_cache: bool, what: str):
    from aitx.disease import extract as X
    t = time.time()
    r = X._cached_chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], 0, use_cache,
                       prompt_version=PROMPT_VERSION)
    if time.time() - t > 1:
        print(f"[3c] LLM {what}: {time.time() - t:.0f}s", flush=True)
    return X._parse(r)["parsed"], {"llm": X.llm.config()["model"], "served_model": r.get("served_model"),
                                   "prompt_version": PROMPT_VERSION}


def names_in(quote: str, names: list[str], gene: str | None) -> str | None:
    """A disease name (case-insensitive) or the gene / a short abbreviation (case-sensitive) named in the quote."""
    for n in [x for x in names if x]:
        short = " " not in n.strip() and n.strip().upper() == n.strip() and len(n.strip()) <= 6
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(n.strip())}(?![A-Za-z0-9])", quote or "", 0 if short else re.I):
            return n
    if gene and re.search(rf"(?<![A-Za-z0-9]){re.escape(gene)}(?![A-Za-z0-9])", quote or ""):
        return gene
    return None


def drug_in(quote: str, drug: str) -> bool:
    words = [w for w in re.split(r"[\s/,()-]+", (drug or "").lower()) if len(w) >= 4]
    low = (quote or "").lower()
    return bool(words) and any(re.search(rf"(?<![a-z]){re.escape(w)}", low) for w in words)


def check_item(it: dict, text: str, names: list[str], gene: str | None) -> str | None:
    """Why a lifted item is not a valid precedent, or None (code only)."""
    name, use = str(it.get("name") or "").strip(), str(it.get("use_quote") or "")
    if not name or not use:
        return "no product name or use quote"
    if not LG.quote_in(use, text):
        return "use quote not verbatim in the article"
    if not drug_in(use, name):
        return "use quote does not name the product"
    if not names_in(use, names, gene):
        return "use quote names neither the disease nor the gene"
    for k in ("n_quote", "outcome_quote", "co_treatment_quote", "dose_quote", "design_quote"):
        if it.get(k) and not LG.quote_in(str(it[k]), text):
            return f"{k} not verbatim"
    return None


def checked_counts(it: dict) -> dict:
    """Patient counts kept only when the number is in the count quote; otherwise "not stated" (None) - a count that
    cannot be verified never removes the precedent itself (2026-11-05: PMID 30838263 had been dropped)."""
    q = str(it.get("n_quote") or "")
    return {k: (it.get(k) if it.get(k) is not None and number_in(it.get(k), q) else None) for k in ("n_disease", "n_total")}


def direction(it: dict, drug: str, disease: str, use_cache: bool) -> str:
    """Efficacy direction of one paper: the LLM's proposal stands only if the support check finds the outcome quote
    supports it; positive with a verified co-treatment is "combined_unattributable"."""
    d, q = it.get("direction"), str(it.get("outcome_quote") or "")
    if d not in ("positive", "negative", "mixed") or not q:
        return "not_reported"
    claim = {"positive": f"In this report, patients with {disease} improved after receiving {drug}.",
             "negative": f"In this report, {drug} did not achieve the intended effect in patients with {disease}.",
             "mixed": f"In this report, {drug} had both beneficial and absent or adverse effects in patients with {disease}."}[d]
    sc = SC.check_support(f"{drug} effect in {disease}", [claim], [q], use_cache=use_cache)
    if sc["overall"] != "supported":
        return "not_reported"
    if d == "positive" and it.get("co_treatment_quote"):
        return "combined_unattributable"
    return d


def aggregate(directions: list[str]) -> str:
    """Drug-level efficacy (decision 2026-11-05, in this order): positive and negative -> inconsistent; negative without
    positive -> reported_ineffective; positive without negative -> reported_improvement; otherwise insufficient."""
    pos = any(d in ("positive", "mixed") for d in directions)
    neg = any(d in ("negative", "mixed") for d in directions)
    if pos and neg:
        return "inconsistent"
    if neg:
        return "reported_ineffective"
    if pos:
        return "reported_improvement"
    return "insufficient"


CONCLUSION = {
    "inconsistent": "Reports conflict: improvement and no benefit have both been reported.",
    "reported_ineffective": "Reported ineffective; not recommended.",
    "reported_improvement": "Improvement has been reported; this is not proof of efficacy.",
    "insufficient": "Use has been reported, but there is no evidence that it is effective.",
}


def conclusion(agg: str, directions: list[str]) -> str:
    """Code-made sentence, never stronger than the sources; counts what it rests on."""
    n = {d: directions.count(d) for d in DIRECTIONS if directions.count(d)}
    parts = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in n.items())
    return f"{CONCLUSION[agg]} ({parts})"


# ------------------------------------------------------------------ US status

def load_supplements(path: Path = SUPPLEMENTS) -> dict:
    """Controlled list (source: NIH ODS DSLD; decision 2026-11-05); absent until the list is approved."""
    return json.loads(path.read_text()) if path.exists() else {"supplements": []}


def supplement_entry(drug: str, table: dict) -> dict | None:
    for s in table.get("supplements") or []:
        if any(re.fullmatch(rf"{re.escape(a.lower())}", drug.lower().strip()) for a in [s["name"]] + list(s.get("aliases") or [])):
            return s
    return None


def gras_table(directory: Path = GRAS_DIR) -> dict:
    """{substance (lower case): [GRN numbers]} from the newest local GRAS inventory export, with its dates."""
    import csv
    import io
    files = sorted(directory.glob("gras_notices_*.xls")) if directory.exists() else []
    if not files:
        return {"file": None, "substances": {}}
    raw = files[-1].read_text(encoding="latin-1")
    lines = raw.splitlines()
    head = next(i for i, l in enumerate(lines) if l.startswith("GRAS Notice (GRN) No."))
    subs: dict[str, list[str]] = {}
    for r in csv.DictReader(io.StringIO("\n".join(lines[head:]))):
        name = re.sub(r"<[^>]+>", "", r.get("Substance") or "").strip().lower()
        grn = re.sub(r'[^0-9]', "", r.get("GRAS Notice (GRN) No.") or "")
        if name:
            subs.setdefault(name, []).append(grn)
    return {"file": files[-1].name, "header": lines[0][:200], "substances": subs}


def gras_entry(drug: str, table: dict) -> dict | None:
    """A GRAS notice whose substance is exactly this product (case-insensitive, optional D-/L- prefix); never a
    substance that merely contains the word ("serine protease" is not L-serine)."""
    core = re.sub(r"^[dl]-", "", drug.lower().strip())
    for name, grns in (table.get("substances") or {}).items():
        if re.sub(r"^[dl]-", "", name) == core:
            return {"substance": name, "grn": grns, "file": table.get("file")}
    return None


def fda_status(drug: str) -> dict:
    """Approved in the US for any indication? A label whose generic name is exactly this drug (not a combination)."""
    comps = A.components(drug)
    if not comps:
        return {"approved": False}
    labels, rec = LB.search("openfda.generic_name", comps[0], limit=10)
    for lb in LB.latest(labels):
        if A.components(lb.get("generic") or "") == comps:
            return {"approved": True, "set_id": lb["set_id"], "url": lb["url"], "version": lb["version"],
                    "brand": lb["brand"], "indication": lb["sections"].get("indications_and_usage", "")[:400],
                    "search": rec}
    return {"approved": False, "search": rec}


def expanded_access(drug: str, names: list[str], gene: str | None) -> list[dict]:
    """ClinicalTrials.gov expanded-access records naming the drug and the disease or gene."""
    out = []
    for term in [n for n in E.label_names(names)][:2] + ([gene] if gene else []):
        res = T.search({"query.term": f"{term} {drug}", "filter.advanced": "AREA[StudyType]EXPANDED_ACCESS"})
        for st in res["studies"]:
            if drug_in(" ".join(st.get("interventions") or []) + " " + (st.get("title") or ""), drug):
                out.append({"nct": st["nct"], "status": st["status"], "title": st["title"], "url": T.study_url(st["nct"])})
    return list({x["nct"]: x for x in out}.values())


# ------------------------------------------------------------------ variant function (contract: three tiers)

def function_status(req_text: str, step1: dict, gene: str | None) -> tuple[str, dict, str]:
    """A loss-of-function requirement: a truncating variant predicted to trigger NMD -> met (reasoning evidence);
    missense, NMD-escaping truncation or anything else -> unknown unless the case states a functional result.
    A gain-of-function requirement is always unknown for now (a rule that makes "not applicable" needs review)."""
    vs = [v for v in step1.get("variants") or [] if v.get("gene") == gene]
    fact = {"field": "variant function", "value": None, "quote": None, "step": None}
    if not vs:
        return "unknown", fact, "no variant in this gene"
    v = vs[0]
    nmd = (v.get("nmd") or {}).get("prediction")
    fact = {"field": "variant function", "value": f"{v['variant_protein']} ({v.get('variant_class')}; NMD {nmd})",
            "quote": f"{v['gene']} {v['variant_cdna']} {v['variant_protein']}", "step": 1}
    low = (req_text or "").lower()
    if re.search(r"gain[- ]of[- ]function|\bgof\b", low):
        return "unknown", fact, "gain-of-function rules await review (decision 3)"
    if re.search(r"loss[- ]of[- ]function|\blof\b|null|haploinsufficien", low):
        if v.get("variant_class") in ("nonsense", "frameshift") and nmd == "likely_triggers":
            return "satisfies", fact, "reasoning: truncating variant predicted to trigger NMD (Step 1), not a functional study"
        return "unknown", fact, f"function not established ({v.get('variant_class')}, NMD {nmd})"
    return "unknown", fact, "variant function requirement not comparable"


# ------------------------------------------------------------------ ledger

ROUTE_LABEL = {"fda_approved": "FDA-approved drug (off-label use for this disease)",
               "dietary_supplement": "available as a dietary supplement (NIH ODS DSLD)",
               "food_substance_gras": "food substance (FDA GRAS notice)",
               "expanded_access": "available through expanded access",
               "trial_only": "only through a clinical trial",
               "unconfirmed": "access route not confirmed"}


def add_offlabel(led: LG.Ledger, case: dict, step1: dict, step2: dict, *, use_cache: bool = True) -> None:
    pf = E.facts(step1, step2)
    supplements = load_supplements()
    by_id = {b["id"]: b for b in led.branches}
    earlier = {a.get("action_key"): a for a in led.actions if a.get("action_key") and a["section"] in
               ("existing_targeted_therapies", "supportive_management", "contraindications_precautions")}
    trial_acts = [a for a in led.actions if a["section"] == "clinical_trial_eligibility" and a.get("action_key")]
    made_for: dict[str, set] = {}
    for b in [b for b in led.branches if b.get("diagnosis")]:
        names, gene = E.disease_names(b, step2), b.get("gene")
        try:
            rec = search(gene, names)
        except (RuntimeError, ValueError, KeyError) as e:
            led.offlabel_searches[b["id"]] = {"error": f"{type(e).__name__}: {e}"[:300]}
            continue
        groups, rejected = {}, []
        for p in rec["papers"]:
            text = paper_text(p)
            if p.get("excluded"):
                continue
            if not names_in(text, names, gene):
                p["excluded"] = "does not name the disease or gene"
                continue
            parsed, llm = _llm(f"Disease: {b['diagnosis']['label']} (gene {gene})\nArticle PMID {p['pmid']}:\n"
                               f"{p['title']}\n{F.text_for_llm(p['abstract'], p['full_text'])}", use_cache, f"PMID {p['pmid']}")
            got = 0
            for it in parsed.get("items") or []:
                if not isinstance(it, dict):
                    continue
                why = check_item(it, text, names, gene)
                if why:
                    rejected.append({"pmid": p["pmid"], "name": it.get("name"), "why": why})
                    continue
                key = A.drug_key(it["name"])
                groups.setdefault(key["key"], {"key": key, "name": it["name"], "items": []})["items"].append((p, it, llm))
                got += 1
            if not got:
                p["excluded"] = "no precedent: no product given to patients with this disease or gene"
        led.offlabel_searches[b["id"]] = {k: v for k, v in rec.items() if k != "papers"} | {
            "papers": [{k: v for k, v in p.items() if k not in ("abstract", "full_text")} for p in rec["papers"]],
            "rejected_items": rejected}
        for k, g in groups.items():
            _drug(led, b, g, names, gene, pf, step1, supplements, earlier, trial_acts, made_for, use_cache)
    led.mark_searched(SECTION)
    for b in [b for b in led.branches if b.get("diagnosis")]:
        if b["id"] in made_for or b["id"] not in led.offlabel_searches or led.offlabel_searches[b["id"]].get("error"):
            continue
        s = led.offlabel_searches[b["id"]]
        papers = s.get("papers") or []
        excluded = [{"id": f"PMID {p['pmid']}", "reason": p.get("excluded") or "precedent not placed in 3c (see the "
                     "drug decisions)"} for p in papers]
        neg = led.add(LG.negative(SECTION, [b["id"]], database="pubmed", endpoint=F.EUTILS, query=s["query"],
                                  queried_at=s["queried_at"], n_results=len(papers), response_count=len(papers),
                                  excluded=excluded, filters={"retmax": N_PAPERS, "total": s["count"], "truncated": s["truncated"]},
                                  claim=f"No human precedent for an unapproved therapy in {by_id[b['id']]['diagnosis']['label']} was "
                                        f"placed in this section ({len(papers)} articles read of {s['count']})."))
        led.actions.append(LG.action_record(None, SECTION, "None found", [b["id"]], [], [neg["id"]],
                                            {b["id"]: "searched PubMed and expanded-access records; no qualifying precedent"},
                                            searched_none=True))


def source_alias(drug: str, earlier: dict, evidence: dict) -> dict | None:
    """A Tier 1 action whose own source names this product as its alias right after the action's name - "Pyridoxine
    (vitamin B6 analog)" makes "vitamin B6" the same action as pyridoxine (2026-11-05: RxNorm codes the two apart).
    Only the parenthesis right after the name counts, never any other mention in the sentence."""
    d = re.sub(r"\s+", " ", drug.lower().strip())
    for k, a in earlier.items():
        lab = re.escape(re.sub(r"\s+", " ", a["label"].lower().strip()))
        for eid in a.get("evidence_ids") or []:
            q = re.sub(r"\s+", " ", str((evidence.get(eid) or {}).get("quote") or "").lower())
            for m in re.finditer(rf"\b{lab}\s*\(([^)]*)\)", q):
                if re.search(rf"(?<![a-z0-9]){re.escape(d)}(?![a-z0-9])", m.group(1)):
                    return {"action_key": k, "section": a["section"], "quote": m.group(0)}
    return None


def _drug(led, b, g, names, gene, pf, step1, supplements, earlier, trial_acts, made_for, use_cache) -> None:
    key, drug, bid = g["key"]["key"], g["name"], b["id"]
    decisions = led.offlabel_searches[bid].setdefault("drug_decisions", [])
    if key in earlier:                                             # approved for this disease or already in Tier 1
        decisions.append({"drug": drug, "key": key, "decision": f"already in {earlier[key]['section']}"})
        return
    alias = source_alias(drug, earlier, led.evidence)
    if alias:
        decisions.append({"drug": drug, "key": key, "decision": f"already in {alias['section']} as {alias['action_key']} "
                          f"(source names it: '{alias['quote']}')"})
        return
    fda = fda_status(drug)
    sup = supplement_entry(drug, supplements)
    gras = gras_entry(drug, gras_table())
    ea = [x for x in expanded_access(drug, names, gene) if x["status"] == "AVAILABLE"]
    trials = [a for a in trial_acts if drug_in(" ".join(a.get("interventions") or []), drug) and bid in a["applies_to"]]
    # admission is the human precedent alone; the access route only describes how it can be obtained (decision 2026-11-05)
    route = ("fda_approved" if fda["approved"] else "dietary_supplement" if sup else "food_substance_gras" if gras
             else "expanded_access" if ea else "trial_only" if trials else "unconfirmed")
    prec, seen_pmid = [], set()
    for p, it, llm in g["items"]:
        if p["pmid"] in seen_pmid:                                 # one precedent per article
            continue
        seen_pmid.add(p["pmid"])
        d = direction(it, drug, b["diagnosis"]["label"], use_cache)
        n = checked_counts(it)
        prec.append({"pmid": p["pmid"], "url": f"https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/", "year": p["year"],
                     "pub_types": p["pub_types"], "design": design(p["pub_types"], it.get("design_quote") or ""),
                     "n_disease": n["n_disease"], "n_total": n["n_total"], "n_quote": it.get("n_quote") or None,
                     "use_quote": it["use_quote"], "outcome_quote": it.get("outcome_quote") or None, "direction": d,
                     "co_treatment_quote": it.get("co_treatment_quote") or None, "dose_quote": it.get("dose_quote") or None,
                     "open_access_full_text": bool(p.get("full_text")), "retracted": False,
                     "_text": paper_text(p), "_conditions": it.get("conditions") or [], "_llm": llm})
    if route == "trial_only":                                     # only through the trial: 3b, precedents attached
        for a in trials:
            have = {x["pmid"] for x in a.setdefault("supporting_precedents", [])}
            a["supporting_precedents"].extend({k: v for k, v in x.items() if not k.startswith("_")} for x in prec
                                              if x["pmid"] not in have)
        decisions.append({"drug": drug, "key": key, "decision": "only through a recruiting trial: kept in 3b with its precedents",
                          "trials": [a["nct"] for a in trials]})
        return
    directions = [x["direction"] for x in prec]
    agg = aggregate(directions)
    evs, lines = [], []
    for x in prec:
        src = {"type": "pmid", "id": x["pmid"], "url": x["url"]}
        claim = f"PMID {x['pmid']}: patients with {b['diagnosis']['label']} received {drug} ({x['design'] or 'design not stated'})."
        evs.append(led.add(LG.sourced(claim, SECTION, [bid], src, x["use_quote"], x["_text"], led_time(),
                                      produced_by=x["_llm"], retrieved_by="3c pubmed", action=g["key"])))
        for c in x["_conditions"]:
            t = str((c or {}).get("text") or "")
            if not t or not LG.quote_in(t, x["_text"]):
                continue
            ev = led.add(LG.sourced(f"PMID {x['pmid']} condition: {t[:80]}", SECTION, [bid], src, t, x["_text"], led_time(),
                                    produced_by=x["_llm"], retrieved_by="3c pubmed", action=g["key"]))
            if c.get("field") == "variant_function":
                st, fact, note = function_status(t, step1, gene)
            else:
                st, fact, note = E.evaluate({"field": c.get("field"), "op": "", "value": "", "text": t}, pf, b)
                if st == "unknown" and not (fact or {}).get("field"):
                    fact = {"field": c.get("field") or "other", "value": None, "quote": None, "step": None}
            line = LG.requirement(f"r{len(lines) + 1}", "label_condition", t, ev["id"], fact, st, [bid], note)
            if line["result"] == "unknown":
                var = E.variable_type(fact["field"])
                line["patient_fact"] = dict(fact, field=var)
                led.note_missing(var, drug, t[:120], "3c")
            lines.append(line)
    res = [l["result"] for l in lines]
    reason = ("not met: " + next(l["requirement"] for l in lines if l["result"] == "fail")[:80] if "fail" in res else
              "depends on: " + "; ".join(sorted({l["patient_fact"]["field"] for l in lines if l["result"] == "unknown"}))[:100]
              if "unknown" in res else CONCLUSION[agg])
    rec = LG.action_record(key, SECTION, drug, [bid], lines, [e["id"] for e in evs if e["status"] == "verified"], {bid: reason})
    rec.update(precedents=[{k: v for k, v in x.items() if not k.startswith("_")} for x in prec], efficacy_direction=agg,
               conclusion=conclusion(agg, directions), access_route=route, access_route_label=ROUTE_LABEL[route],
               regulatory={"fda": {k: v for k, v in fda.items() if k != "search"}, "supplement": sup, "gras": gras,
                           "expanded_access": ea},
               strength=strongest(prec))
    if route in ("dietary_supplement", "food_substance_gras"):
        rec["supplement_note"] = SUPPLEMENT_NOTE
    if route == "unconfirmed":
        rec["access_note"] = UNCONFIRMED_NOTE
    if trials:                                                    # reachable outside the trial too: both, cross-referenced
        rec["see_also"] = [{"section": "clinical_trial_eligibility", "nct": a["nct"]} for a in trials]
        for a in trials:
            a.setdefault("see_also", []).append({"section": SECTION, "action_key": key})
    led.actions.append(rec)
    made_for.setdefault(bid, set()).add(key)
    decisions.append({"drug": drug, "key": key, "decision": f"3c (access: {route})"})


def led_time() -> int:
    return int(time.time())


_STRENGTH = ("controlled", "open_label", "case_series", "case_report", None)


def strongest(prec: list[dict]) -> dict:
    best = min(prec, key=lambda x: (_STRENGTH.index(x["design"]), -(x["n_disease"] or 0)))
    return {"design": best["design"], "n_disease": best["n_disease"], "pmid": best["pmid"]}


# ------------------------------------------------------------------ checks (contract)

_STRONG_WORDS = re.compile(r"\b(effective|efficacious|proven|cures?|recommended)\b", re.I)


def problems(actions: list[dict]) -> list[str]:
    bad = []
    keys = {}
    for a in actions:
        if a.get("action_key"):
            keys.setdefault(a["action_key"], set()).add(a["section"])
    for a in [a for a in actions if a["section"] == SECTION and a.get("action_key")]:
        k = a["action_key"]
        if keys[k] - {SECTION, "clinical_trial_eligibility"}:
            bad.append(f"{k}: also in {sorted(keys[k] - {SECTION})}")
        pr = a.get("precedents") or []
        if not pr or any(p.get("retracted") or not re.fullmatch(r"\d+", str(p.get("pmid"))) for p in pr):
            bad.append(f"{k}: no valid precedent")
        if any(p.get("direction") not in DIRECTIONS for p in pr):
            bad.append(f"{k}: precedent without efficacy direction")
        if a.get("efficacy_direction") != aggregate([p.get("direction") for p in pr]):
            bad.append(f"{k}: efficacy summary does not follow the aggregation rule")
        c = a.get("conclusion") or ""
        if a.get("efficacy_direction") == "reported_ineffective" and "not recommended" not in c:
            bad.append(f"{k}: reported ineffective without 'not recommended'")
        if _STRONG_WORDS.search(c.replace("Reported ineffective; not recommended", "").replace("not proof of efficacy", "")
                                .replace("no evidence that it is effective", "")):
            bad.append(f"{k}: conclusion stronger than the sources")
        if any(p.get("dose_quote") and p["dose_quote"] in c for p in pr):
            bad.append(f"{k}: dose in the conclusion")
        if a.get("access_route") not in ROUTE_LABEL or a.get("access_route") == "trial_only":
            bad.append(f"{k}: access route {a.get('access_route')} (trial-only belongs in 3b)")
        if a.get("access_route") in ("dietary_supplement", "food_substance_gras") and a.get("supplement_note") != SUPPLEMENT_NOTE:
            bad.append(f"{k}: supplement / food substance without the note")
        if a.get("access_route") == "unconfirmed" and a.get("access_note") != UNCONFIRMED_NOTE:
            bad.append(f"{k}: unconfirmed access without the note")
        for s in a.get("see_also") or []:
            t = next((x for x in actions if x.get("nct") == s.get("nct")), None)
            if not t or not any(y.get("action_key") == k for y in t.get("see_also") or []):
                bad.append(f"{k}: cross-reference to {s.get('nct')} not returned")
    return bad

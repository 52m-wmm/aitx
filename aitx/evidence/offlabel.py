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
PROMPT_VERSION = "3c-v3"          # v2 (2026-11-05): anaesthesia / sedation / procedural / diagnostic uses excluded
                                  # v3 (2026-11-05): outcome_measure (what improved) and target_quote (complication treated)
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


N_SCREEN = 200                                    # step 1: abstracts screened by code (decision 2026-11-05)
COMMON_SHARE = 0.15                               # a substance named in more of the screened abstracts is context
REVIEW_TYPES = {"Review", "Systematic Review", "Meta-Analysis"}
PRIMARY_DESIGNS = '("Case Reports"[pt] OR "Clinical Trial"[pt] OR "Observational Study"[pt] OR "Case series"[tiab])'
# ubiquitous substances that are RxNorm ingredients but never "a specific drug" in an abstract
_NOT_A_DRUG = {"water", "oxygen", "sodium", "potassium", "calcium", "chloride", "glucose", "alcohol", "ethanol", "protein",
               "nitrogen", "carbon", "hydrogen", "iron", "zinc", "magnesium", "phosphate", "lactate", "urea", "creatinine",
               "oxalate", "glycine", "albumin", "insulin glargine"}


def drug_lexicon(path: Path = ROOT / ".cache" / "rxnorm" / "ingredients.json") -> set[str]:
    """RxNorm ingredient names (RxNav allconcepts, tty=IN; cached locally) plus the approved supplement list."""
    names = set()
    if path.exists():
        for c in json.loads(path.read_text())["minConceptGroup"]["minConcept"]:
            n = c["name"].lower().strip()
            if len(n) >= 5 and n not in _NOT_A_DRUG:
                names.add(n)
    for sup in load_supplements().get("supplements") or []:
        names |= {sup["name"].lower()} | {a.lower() for a in sup.get("aliases") or []}
    return names


def product_ingredients(path: Path = ROOT / ".cache" / "rxnorm" / "products.json") -> set[str]:
    """Ingredients named in at least one prescribable RxNorm product (SCD / SBD; RxNav allconcepts, cached) plus the
    supplement list: used only to rank articles naming a new drug first (metabolites such as adenine or calcium oxalate
    are RxNorm ingredients but name no product)."""
    lex = drug_lexicon()
    if not path.exists():
        return lex
    prods = " | ".join(c["name"].lower() for c in json.loads(path.read_text())["minConceptGroup"]["minConcept"])
    words = set(re.findall(r"[a-z][a-z0-9-]+", prods))
    keep = {n for n in lex if (n in words if " " not in n else n in prods)}
    for sup in load_supplements().get("supplements") or []:
        keep |= {sup["name"].lower()} | {a.lower() for a in sup.get("aliases") or []}
    return keep


_PROTEIN_AFTER = re.compile(r"^[\s:-]*(?:oxidase|dehydrogenase|aminotransferase|transaminase|reductase|synthase|synthetase|"
                            r"kinase|transporter|receptor|carrier|hydroxylase|decarboxylase|transferase|isomerase|mutase|"
                            r"lyase|ligase|glyoxylate aminotransferase|:glyoxylate)", re.I)


def drugs_named(text: str, lexicon: set[str]) -> list[str]:
    # a substance name that is part of an enzyme or protein name ("glycolate oxidase", "alanine:glyoxylate
    # aminotransferase") is not a drug (2026-11-05)
    text = re.sub(r"\b([a-z][a-z0-9-]*)(?=[\s:-]*(?:oxidase|dehydrogenase|aminotransferase|transaminase|reductase|synthase|"
                  r"synthetase|kinase|transporter|receptor|hydroxylase|decarboxylase|transferase|:glyoxylate)\b)", " ", text or "",
                  flags=re.I)
    low = (text or "").lower()
    words = set(re.findall(r"[a-z][a-z0-9-]{4,}", low))
    hits = {n for n in lexicon if " " not in n and n in words}
    hits |= {n for n in lexicon if " " in n and n in low and re.search(rf"(?<![a-z]){re.escape(n)}(?![a-z])", low)}
    return sorted(hits)


def _fetch_records(ids: list[str]) -> dict[str, dict]:
    """PubMed records (title, abstract, publication types, retraction notice, PMC id) via efetch, 100 per call."""
    out = {}
    for i in range(0, len(ids), 100):
        xml = http.get(f"{F.EUTILS}/efetch.fcgi?db=pubmed&retmode=xml&id={','.join(ids[i:i + 100])}", timeout=90).text
        ab, ti, rt = F.abstracts_by_pmid(xml), titles_by_pmid(xml), retraction_notices(xml)
        for art in re.findall(r"<PubmedArticle>.*?</PubmedArticle>", xml, re.S):
            m = re.search(r"<PMID[^>]*>(\d+)</PMID>", art)
            if not m:
                continue
            pmid = m.group(1)
            pmc = re.search(r'<ArticleId IdType="pmc">(PMC\d+)</ArticleId>', art)
            year = re.search(r"<PubDate>.*?<Year>(\d{4})</Year>", art, re.S)
            out[pmid] = {"pmid": pmid, "title": ti.get(pmid, ""), "abstract": ab.get(pmid, ""),
                         "pub_types": [re.sub(r"<[^>]+>", "", t) for t in re.findall(r"<PublicationType[^>]*>(.*?)</PublicationType>", art)],
                         "retraction": rt.get(pmid), "pmc": pmc.group(1) if pmc else None, "year": year.group(1) if year else ""}
    return out


def pick(pool: list[dict], cap: int) -> list[dict]:
    """Round robin over the new drugs (2026-11-05): each drug gets one article per round - one naming it in the title
    first - so the cap covers as many candidate drugs as possible; articles naming only Tier 1 drugs or context terms
    come last, by relevance. A drug that is rare in the pool is not favoured over a common one."""
    def in_title(r, n):
        return re.search(rf"(?<![a-z]){re.escape(n)}(?![a-z])", r["title"].lower()) is not None
    queues: dict[str, list[dict]] = {}
    for r in pool:
        for n in r["new_drugs"]:
            queues.setdefault(n, []).append(r)
    for n in queues:
        queues[n].sort(key=lambda r: not in_title(r, n))
    order = sorted(queues, key=lambda n: (not any(in_title(r, n) for r in queues[n]), pool.index(queues[n][0])))
    out, seen = [], set()
    while len(out) < cap and any(queues[n] for n in order):
        for n in order:
            while queues[n] and queues[n][0]["pmid"] in seen:
                queues[n].pop(0)
            if queues[n] and len(out) < cap:
                r = queues[n].pop(0)
                out.append(r)
                seen.add(r["pmid"])
    out += [r for r in pool if r["pmid"] not in seen][: cap - len(out)]
    return out


def review_references(pmid: str) -> list[str]:
    """PMIDs a review cites (E-utilities elink pubmed_pubmed_refs)."""
    d = _json(f"{F.EUTILS}/elink.fcgi?dbfrom=pubmed&linkname=pubmed_pubmed_refs&retmode=json&id={pmid}")
    return [str(x) for ls in d.get("linksets") or [] for db in ls.get("linksetdbs") or [] for x in db.get("links") or []]


def search(gene: str | None, names: list[str], exclude_drugs: set[str] | None = None) -> dict:
    """Two steps (decision 2026-11-05). Step 1: the first 200 articles by relevance - abstracts only, no LLM; code keeps
    those whose title or abstract names a specific drug (RxNorm ingredient lexicon). Reviews are never precedents: they
    are kept as background and their cited original reports enter the pool (decision 2026-11-05). Step 2: at most 20
    articles - those naming a drug not already in Tier 1 first - go to the LLM. Every count is recorded."""
    q = query(gene, names)
    url = f"{F.EUTILS}/esearch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "sort": "relevance",
                                                               "retmax": N_SCREEN, "term": q})
    d = _json(url)["esearchresult"]
    ids, count = d.get("idlist") or [], int(d.get("count") or 0)
    # a second recall path: the same query limited to primary designs (added, never a filter: 2026-11-05, PH1 stiripentol
    # case reports ranked below 200 in the main query)
    q2 = f"{q} AND {PRIMARY_DESIGNS}"
    url2 = f"{F.EUTILS}/esearch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "sort": "relevance",
                                                                "retmax": N_SCREEN, "term": q2})
    d2 = _json(url2)["esearchresult"]
    ids2 = [i for i in d2.get("idlist") or [] if i not in set(ids)]
    ids = ids + ids2
    rec = {"query": q, "url": url, "query_primary_designs": q2, "queried_at": int(time.time()), "count": count,
           "papers": [], "reviews": [],
           "steps": {"found": count, "found_primary_designs": int(d2.get("count") or 0), "screened": len(ids)}}
    if not ids:
        rec.update(truncated=False)
        return rec
    lex, prod, excl = drug_lexicon(), product_ingredients(), {x.lower() for x in exclude_drugs or set()}
    recs = _fetch_records(ids)
    pool, reviews = [], []
    for pmid in ids:
        r = recs.get(pmid)
        if not r:
            continue
        r["drugs"] = drugs_named(f"{r['title']} {r['abstract']}", lex)
        if set(r["pub_types"]) & REVIEW_TYPES:
            reviews.append(r)
        elif r["drugs"]:
            pool.append(r)
    rec["steps"]["with_drug"] = len(pool)
    # reviews: background only; their cited original reports naming the disease or gene and a drug join the pool
    cited = []
    for rv in [r for r in reviews if r["drugs"]][:10]:
        try:
            refs = review_references(rv["pmid"])
        except (RuntimeError, ValueError, KeyError):
            refs = []
        rec["reviews"].append({"pmid": rv["pmid"], "title": rv["title"], "role": "background", "references": len(refs)})
        cited += [x for x in refs if x not in recs]
    have = {r["pmid"] for r in pool}
    if cited:
        crecs = _fetch_records(list(dict.fromkeys(cited))[:N_SCREEN])
        for pmid, r in crecs.items():
            text = f"{r['title']} {r['abstract']}"
            r["drugs"] = drugs_named(text, lex)
            if pmid not in have and r["drugs"] and not set(r["pub_types"]) & REVIEW_TYPES and names_in(text, names, gene):
                r["via_review"] = True
                pool.append(r)
    rec["steps"]["from_review_references"] = sum(1 for r in pool if r.get("via_review"))
    # a "new drug" is a product ingredient not in Tier 1 and not common in this pool: a name in more than 15% of the
    # screened abstracts is part of the disease's context (glycolate, alanine in PH1), not a treatment tried in it
    freq: dict[str, int] = {}
    for r in pool:
        for n in set(r["drugs"]):
            freq[n] = freq.get(n, 0) + 1
    common = {n for n, k in freq.items() if k > COMMON_SHARE * max(len(ids), 1)}
    for r in pool:
        r["new_drugs"] = sorted((set(r["drugs"]) & prod) - excl - common)
    rec["steps"]["context_terms_ignored"] = sorted(common)[:20]
    # a new drug in the title first (case reports name the drug there; metabolites appear in the abstract), then a new
    # drug in the abstract, then relevance (2026-11-05: PH1 glycolate / alanine abstracts had pushed stiripentol out)
    # an article with neither an abstract nor a PMC record can never be read: it takes no slot (recorded)
    unreadable = [r for r in pool if not r["abstract"] and not r["pmc"]]
    rec["unreadable"] = [{"pmid": r["pmid"], "title": r["title"], "excluded": "no accessible text (no abstract, no PMC record)"}
                         for r in unreadable]
    rec["steps"]["unreadable"] = len(unreadable)
    chosen = pick([r for r in pool if r not in unreadable], N_PAPERS)
    rec["steps"]["to_llm_cap"] = len(chosen)
    rec["truncated"] = count > N_SCREEN or len(pool) > N_PAPERS
    for r in chosen:
        p = {"pmid": r["pmid"], "title": r["title"], "year": r["year"], "pub_types": r["pub_types"], "pmc": r["pmc"],
             "oa": None, "abstract": r["abstract"], "full_text": "", "drugs_in_abstract": r["drugs"][:12],
             **({"via_review": True} if r.get("via_review") else {})}
        if "Retracted Publication" in r["pub_types"] or r.get("retraction"):
            p["excluded"] = f"retracted ({r.get('retraction') or 'PubMed publication type'})"
        elif r["pmc"]:
            try:
                p["oa"], p["full_text"], p["license"] = F.pmc_open_access_text(r["pmc"])
            except (RuntimeError, ValueError, OSError) as e:
                p["oa"], p["oa_error"] = None, f"{type(e).__name__}: {e}"[:200]
        if not p.get("excluded") and not (p["abstract"] or p["full_text"]):
            p["excluded"] = "no accessible text (no abstract, no open-access or author-manuscript full text)"
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
    if re.search(r"\bopen[- ]label\b|\bsingle[- ]arm\b|\bnon[- ]?randomi[sz]ed\b|\bnon[- ]?blinded\b|\bunblinded\b|\bpilot\b", q):
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
Do not list products only proposed, only tested in cells or animals, given for another disease, or used for
anaesthesia, sedation, a procedure or a diagnostic test. Copy every quote
character for character from the text. For each product return one item:
{"name": "<product name>",
 "use_quote": "<the sentence saying patients with this disease or gene received it>",
 "n_quote": "<the words giving how many patients received it, or empty>", "n_disease": <number with this disease or gene, or null>,
 "n_total": <number of all treated patients, or null>,
 "outcome_quote": "<the sentence stating the result for these patients, or empty>",
 "outcome_measure": "<the words inside outcome_quote naming what was measured or observed to change (for example \"plasma oxalate\", \"ocular findings\", \"seizure frequency\"), copied exactly, or empty>",
 "target_quote": "<if the product was given for one complication or symptom of the disease rather than for the disease itself, the exact words naming that complication or symptom; otherwise empty>",
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


_GENE_AFTER = (r"(?:\s*-\s*|\s+)(?:variants?|mutations?|pathogenic|deficien\w*|related|associated|ndd|cdg|encephalopath\w*|"
               r"disorders?|disease|patients?|carriers?|individuals?|syndrome|child(?:ren)?|infants?|girls?|boys?|siblings?|famil\w*)\b"
               r"|(?:\s*,\s*[A-Z][A-Z0-9]+)*,?\s+(?:and|or)\s+[A-Z][A-Z0-9]+\s+(?:variants?|mutations?)\b")   # "GRIN2B, GRIN1 and GRIN2A variants"
_GENE_BEFORE = r"\b(?:variants?|mutations?|carriers?|pathogenic variants?|patients?|individuals?|children)\s+(?:with\s+|in\s+|of\s+)?(?:a\s+|an\s+|the\s+)?(?:\w+\s+){0,2}"
_CANCER = re.compile(r"\b(?:cancer|carcinoma|tumou?rs?|neoplas\w*|malignan\w*|leuka?emi\w*|lymphoma|metasta\w*|chemotherapy)\b", re.I)


def names_in(quote: str, names: list[str], gene: str | None) -> str | None:
    """A disease name (case-insensitive; a short abbreviation case-sensitive) named in the quote, or the gene named as
    the patients' genetic condition ("GRIN2B-NDD", "AGXT variants", "patients with ANO10 mutations"). A bare gene symbol
    is not enough, and a cancer context without the disease name never counts (2026-11-05: "AGXT expression" in
    colorectal-cancer papers had admitted bevacizumab, oxaliplatin, cetuximab and 5-fluorouracil)."""
    for n in [x for x in names if x]:
        short = " " not in n.strip() and n.strip().upper() == n.strip() and len(n.strip()) <= 6
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(n.strip())}(?![A-Za-z0-9])", quote or "", 0 if short else re.I):
            return n
    if gene and not _CANCER.search(quote or ""):
        g = re.escape(gene)
        if re.search(rf"(?<![A-Za-z0-9]){g}{_GENE_AFTER}", quote or "", re.I) or \
                re.search(rf"{_GENE_BEFORE}{g}(?![A-Za-z0-9])", quote or "", re.I):
            return gene
    return None


def drug_in(quote: str, drug: str) -> bool:
    words = [w for w in re.split(r"[\s/,()-]+", (drug or "").lower()) if len(w) >= 4]
    low = (quote or "").lower()
    return bool(words) and any(re.search(rf"(?<![a-z]){re.escape(w)}", low) for w in words)


_NOT_TREATMENT = re.compile(r"\b(?:anaesthe\w*|anesthe\w*|sedat\w*|premedicat\w*|perioperative|intraoperative|"
                            r"intubat\w*|induction of anesthesia|contrast agent|diagnostic)\b", re.I)


def check_item(it: dict, text: str, names: list[str], gene: str | None) -> str | None:
    """Why a lifted item is not a valid precedent, or None (code only)."""
    name, use = str(it.get("name") or "").strip(), str(it.get("use_quote") or "")
    if not name or not use:
        return "no product name or use quote"
    if _NOT_TREATMENT.search(use):          # 2026-11-05: "Anesthesia was induced and maintained with sevoflurane"
        return "not a treatment of the disease (anaesthesia, sedation, procedure or diagnostic use)"
    if not LG.quote_in(use, text):
        return "use quote not verbatim in the article"
    if not drug_in(use, name):
        return "use quote does not name the product"
    # the treated patients' disease or gene may be named in the use quote or in the patient-count quote (both verbatim;
    # 2026-11-05: "received L-serine" + "Patients had GRIN2B, GRIN1 and GRIN2A variants (12, 6 and 5 cases)")
    nq = str(it.get("n_quote") or "")
    title = (text or "").split("\n", 1)[0]
    if not names_in(use, names, gene) and not (nq and LG.quote_in(nq, text) and names_in(nq, names, gene)) \
            and not (names_in(title, names, gene) and drug_in(title, name)):
        return "use quote names neither the disease nor the gene"
    for k in ("n_quote", "outcome_quote", "co_treatment_quote", "dose_quote", "design_quote", "target_quote"):
        if it.get(k) and not LG.quote_in(str(it[k]), text):
            return f"{k} not verbatim"
    return None


def checked_counts(it: dict) -> dict:
    """Patient counts kept only when the number is in the count quote; otherwise "not stated" (None) - a count that
    cannot be verified never removes the precedent itself (2026-11-05: PMID 30838263 had been dropped)."""
    q = str(it.get("n_quote") or "")
    return {k: (it.get(k) if it.get(k) is not None and number_in(it.get(k), q) else None) for k in ("n_disease", "n_total")}


def outcome_measure(it: dict) -> str | None:
    """What the source says changed: the LLM's words, kept only when they are inside the outcome quote."""
    m, q = str(it.get("outcome_measure") or "").strip(), str(it.get("outcome_quote") or "")
    return m if m and len(m) >= 3 and m.lower() in q.lower() else None


def direction_claim(d: str, drug: str, disease: str, measure: str | None = None) -> str:
    """Claim the support check judges. Number-neutral (2026-11-05): with "patients" the judges answered
    "partially supported - one infant, not patients generally" for every single-case report, so no case report could
    ever carry a direction. How many patients is recorded separately (n_disease), not inside this claim.
    Positive is about the measured outcome, not the patient as a whole (decision 2026-11-05): "plasma oxalate fell"
    supports "plasma oxalate improved", never "the patient improved"."""
    who = f"the patient or patients with {disease} described in this report"
    pos = (f"After receiving {drug}, {measure} improved in {who}." if measure else
           f"After receiving {drug}, an outcome measured or observed improved in {who}.")
    return {"positive": pos,
            "negative": f"{drug} did not achieve the intended effect in {who}.",
            "mixed": f"{drug} had both beneficial and absent or adverse effects in {who}."}[d]


def direction(it: dict, drug: str, disease: str, use_cache: bool) -> str:
    """Efficacy direction of one paper: the LLM's proposal stands only if the support check finds the outcome quote
    supports it; positive with a verified co-treatment is "combined_unattributable"."""
    d, q = it.get("direction"), str(it.get("outcome_quote") or "")
    if d not in ("positive", "negative", "mixed") or not q:
        return "not_reported"
    claim = direction_claim(d, drug, disease, outcome_measure(it))
    # both quotes from the same article: who received the drug, and what happened (2026-11-05: the outcome sentence
    # alone - "SLC35A2-CDG patients demonstrated improvements" - does not name the drug)
    sc = SC.check_support(f"{drug} effect in {disease}", [claim], [str(it.get("use_quote") or ""), q], use_cache=use_cache)
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
    "reported_improvement": "Improvement has been reported in {measures}; this is not proof of efficacy.",
    "insufficient": "Use has been reported, but there is no evidence that it is effective.",
}


def conclusion(agg: str, directions: list[str], measures: list[str | None] | None = None) -> str:
    """Code-made sentence, never stronger than the sources; counts what it rests on. An improvement names what
    improved (the measure from the positive precedents), never "the patient" (decision 2026-11-05)."""
    n = {d: directions.count(d) for d in DIRECTIONS if directions.count(d)}
    parts = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in n.items())
    ms = measures or [None] * len(directions)
    named = list(dict.fromkeys(m for d, m in zip(directions, ms) if d in ("positive", "mixed") and m))
    what = ", ".join(named) if named else "an outcome the source does not name"
    return f"{CONCLUSION[agg].format(measures=what)} ({parts})"


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
        tier1 = {a["label"] for a in earlier.values()}
        try:
            rec = search(gene, names, tier1)
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
                     "design_quote": it.get("design_quote") or None, "via_review": bool(p.get("via_review")),
                     "n_disease": n["n_disease"], "n_total": n["n_total"], "n_quote": it.get("n_quote") or None,
                     "use_quote": it["use_quote"], "outcome_quote": it.get("outcome_quote") or None, "direction": d,
                     "outcome_measure": outcome_measure(it), "target_quote": it.get("target_quote") or None,
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
    lines += target_lines(led, prec, drug, pf, bid, src_of=lambda x: {"type": "pmid", "id": x["pmid"], "url": x["url"]},
                          key=g["key"], start=len(lines))
    res = [l["result"] for l in lines]
    reason = ("not met: " + next(l["requirement"] for l in lines if l["result"] == "fail")[:80] if "fail" in res else
              "depends on: " + "; ".join(sorted({l["patient_fact"]["field"] for l in lines if l["result"] == "unknown"}))[:100]
              if "unknown" in res else CONCLUSION[agg])
    rec = LG.action_record(key, SECTION, drug, [bid], lines, [e["id"] for e in evs if e["status"] == "verified"], {bid: reason})
    rec.update(precedents=[{k: v for k, v in x.items() if not k.startswith("_")} for x in prec], efficacy_direction=agg,
               conclusion=conclusion(agg, directions, [x["outcome_measure"] for x in prec]), access_route=route, access_route_label=ROUTE_LABEL[route],
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


TARGET_NOTE = "used for this complication in the source; the case does not report it"
ABSENT_NOTE = "the case states this complication is absent (kept conditional: a 'not applicable' needs review)"


def target_status(text: str, pf: dict) -> tuple[str, dict | None, str]:
    """Does the patient have the complication the precedent treated? Same HPO matching as 3a's manifestation
    conditions. Never a 'not applicable' (approval rule 2026-11-05): absent or not reported -> unknown (conditional)."""
    st, fact = E.manifestation_status(text, pf)
    if st == "satisfies":
        return st, fact, ""
    fact = fact or {"field": "manifestation", "value": None, "quote": None, "step": None}
    return "unknown", dict(fact, field="manifestation"), ABSENT_NOTE if st == "does_not_satisfy" else TARGET_NOTE


def target_lines(led, prec: list[dict], drug: str, pf: dict, bid: str, *, src_of, key, start: int) -> list[dict]:
    """A drug the sources used only for one complication (every precedent names a target) carries that complication
    as a condition (decision 2026-11-05). Several different targets are alternatives: any one present is enough.
    If any precedent treated the disease itself, there is no target condition."""
    if not prec or not all(x.get("target_quote") for x in prec):
        return []
    out, seen = [], {}
    for x in prec:
        t = x["target_quote"]
        if t.lower() in seen:
            continue
        seen[t.lower()] = True
        ev = led.add(LG.sourced(f"PMID {x['pmid']} used {drug} for: {t[:80]}", SECTION, [bid], src_of(x), t, x["_text"],
                                led_time(), produced_by=x["_llm"], retrieved_by="3c pubmed", action=key))
        st, fact, note = target_status(t, pf)
        out.append((t, ev, st, fact, note))
    alt = len(out) > 1
    lines = []
    for i, (t, ev, st, fact, note) in enumerate(out):
        line = LG.requirement(f"r{start + i + 1}", "label_condition", t, ev["id"], fact, st, [bid], note,
                              alternative=f"target{i + 1}" if alt else None)
        line["target_symptom"] = True
        if line["result"] == "unknown":
            var = E.variable_type("manifestation")
            line["patient_fact"] = dict(fact, field=var)
            led.note_missing(var, drug, t[:120], "3c")
        lines.append(line)
    return lines


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

"""System drafting of gene-specific rules (step 3.0 contract, section 4, rule 5).

Same procedure for every gene that appears in a step 2 result, not only evaluation genes:
  1. sources: GeneReviews sections (Genotype-Phenotype Correlations, Genetically Related (Allelic)
     Disorders, Molecular Genetics) from the local archive, and PubMed abstracts found by one query per
     step 2 candidate disease: <gene>[tiab] AND <words of the disease name>[tiab] (+ a genotype-phenotype query);
  2. the LLM reads only these numbered texts and proposes rules; it picks diseases by number from the
     step 2 candidate list and must quote the texts verbatim (it never writes ids, PMIDs or URLs);
  3. code checks every draft: quotes verbatim in the fetched text, condition fields from step 1 only,
     condition values allowed, every number in a position / exon condition appears in a quote,
     diseases from the list; passing drafts become `verified` rules, the rest are kept as rejected drafts.
Each run records its searches (database, query, time, number of results) and the LLM's served model.
A human reviewer may only veto a rule (with a reason) in the written file; content is hash-protected.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse

from aitx import http
from aitx.disease import datasets as D
from aitx.disease import extract as X
from aitx.evidence import genereviews as GR
from aitx.evidence import ledger as LG
from aitx.evidence.rules import CONDITION_FIELDS, content_hash

PROMPT_VERSION = "rules-draft-v1"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
GR_SECTIONS = ("Genotype-Phenotype Correlations", "Genetically Related (Allelic) Disorders", "Molecular Genetics")
PER_QUERY = 5
MAX_PUBMED = 15
MAX_SOURCE_CHARS = 6000
VALUES = {
    "variant_class": {"frameshift", "nonsense", "missense", "start_lost", "inframe_deletion", "inframe_insertion",
                      "inframe_indel", "synonymous", "splice"},
    "nmd_prediction": {"likely_triggers", "likely_escapes", "uncertain", "not_applicable"},
    "zygosity": {"heterozygous", "homozygous", "hemizygous"},
}
STOP = {"type", "and", "or", "of", "the", "due", "to", "with", "syndrome", "disease", "disorder", "autosomal",
        "dominant", "recessive", "x-linked", "juvenile", "infantile", "childhood", "adult", "onset", "form"}

SYSTEM = """You draft gene-specific genotype-phenotype rules for a rare-disease pipeline.
You get: a gene, a numbered list of candidate diseases for that gene, a numbered list of source texts, and the
variant properties a rule may use. Propose a rule ONLY when a source text explicitly states that a variant
property (variant type, protein position range, exon range, NMD outcome or zygosity) is associated with one
candidate disease rather than another. Do not infer, generalize or use outside knowledge.
Return only JSON:
{"rules": [{"statement": "<one English sentence, faithful to the quotes>",
            "applies_when": {"variant_class": [...], "nmd_prediction": [...], "zygosity": [...],
                             "protein_position": [first, last], "exon": [first, last]},   // only the keys you need
            "supports": [<candidate numbers the property points to>],
            "argues_against": [<candidate numbers it points away from>],
            "strength": "established" | "reported" | "weak",
            "exceptions": "<exceptions the texts state, or empty>",
            "evidence": [{"source": <source number>, "quote": "<exact sentence(s) copied from that source>"}]}],
 "no_rule_reason": "<if no rule: what the texts do and do not say>"}
Allowed values: variant_class: frameshift, nonsense, missense, start_lost, inframe_deletion, inframe_insertion,
inframe_indel, synonymous, splice. nmd_prediction: likely_triggers, likely_escapes, uncertain, not_applicable.
zygosity: heterozygous, homozygous, hemizygous. Positions and exons are numbers that must appear in your quotes.
Quotes must be copied character for character. Use only the candidate and source numbers given; never write
identifiers, PMIDs or URLs."""


# ---------------------------------------------------------------- sources

def _search(term: str) -> dict:
    url = f"{EUTILS}/esearch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "term": term, "retmax": PER_QUERY,
                                                              "sort": "relevance", "retmode": "json"})
    f = http.get(url)
    r = json.loads(f.text).get("esearchresult", {})
    return {"database": "pubmed", "endpoint": url, "query": term, "queried_at": f.accessed_at,
            "n_results": int(r.get("count", 0)), "ids": r.get("idlist", [])}


def abstract(pmid: str) -> dict:
    url = f"{EUTILS}/efetch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "id": pmid, "rettype": "abstract",
                                                             "retmode": "text"})
    f = http.get(url)
    return {"type": "pmid", "id": pmid, "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "text_url": url,
            "text": f.text, "accessed_at": f.accessed_at}


def disease_words(label: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z][a-z\-]+", label.lower()) if w not in STOP and len(w) > 2]
    return list(dict.fromkeys(words))[:5]


def gather(gene: str, candidates: list[dict], nbks: list[str]) -> tuple[list[dict], list[dict]]:
    """(sources, searches) for one gene."""
    sources, searches = [], []
    for nbk in nbks:
        for title in GR_SECTIONS:
            hit = GR.find_section(nbk, title)
            if hit:
                sources.append({"type": "nbk", "id": nbk, "section": hit[0], "url": GR.BOOK_URL.format(nbk=nbk),
                                "text": hit[1], "credit": GR.CREDIT,
                                "accessed_at": D.ensure("genereviews_book").downloaded_at})   # archive download time
    terms = [f'{gene}[tiab] AND ("genotype-phenotype"[tiab] OR "genotype phenotype"[tiab] OR "phenotypic spectrum"[tiab])']
    for c in candidates:
        w = disease_words(c["label"])
        if w:
            terms.append(f"{gene}[tiab] AND " + " AND ".join(f"{x}[tiab]" for x in w))
    pmids: list[str] = []
    for t in dict.fromkeys(terms):
        s = _search(t)
        searches.append({k: v for k, v in s.items() if k != "ids"} | {"returned_ids": s["ids"]})
        pmids += [p for p in s["ids"] if p not in pmids]
    for p in pmids[:MAX_PUBMED]:
        a = abstract(p)
        if a["text"].strip():
            sources.append(a)
    return sources, searches


# ------------------------------------------------------------------ drafts

def prompt(gene: str, candidates: list[dict], sources: list[dict]) -> list[dict]:
    lines = [f"Gene: {gene}", "", "Candidate diseases:"]
    lines += [f"  {i}. {c['label']}" for i, c in enumerate(candidates, 1)]
    lines += ["", "Variant properties a rule may use: variant_class, nmd_prediction, zygosity, protein_position, exon", "",
              "Sources:"]
    for i, s in enumerate(sources, 1):
        head = f"GeneReviews section '{s['section']}'" if s["type"] == "nbk" else "PubMed abstract"
        lines += [f"[{i}] {head}:", s["text"][:MAX_SOURCE_CHARS], ""]
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}]


def check_draft(d: dict, candidates: list[dict], sources: list[dict]) -> tuple[dict | None, list[str]]:
    """Turn one LLM draft into a rule, or return the reasons it is rejected."""
    bad = []
    cond = d.get("applies_when") or {}
    if not isinstance(cond, dict) or not cond:
        bad.append("no conditions")
        cond = {}
    for k, v in cond.items():
        if k not in CONDITION_FIELDS:
            bad.append(f"condition field {k!r} is not a step 1 field")
        elif k in VALUES and (not isinstance(v, list) or set(v) - VALUES[k]):
            bad.append(f"{k} values {v!r} not allowed")
        elif k in ("protein_position", "exon") and not (isinstance(v, list) and len(v) == 2
                                                         and all(isinstance(x, int) for x in v) and v[0] <= v[1]):
            bad.append(f"{k} must be [first, last] integers")
    def pick(nums):
        return [candidates[n - 1] for n in nums if isinstance(n, int) and 1 <= n <= len(candidates)]
    sup, ag = pick(d.get("supports") or []), pick(d.get("argues_against") or [])
    if len(sup) != len(d.get("supports") or []) or len(ag) != len(d.get("argues_against") or []):
        bad.append("disease number not in the candidate list")
    if not sup and not ag:
        bad.append("rule supports or argues against no candidate")
    if any(not c["omim"] for c in sup + ag):
        bad.append("rule names a candidate without an OMIM number")
    if d.get("strength") not in ("established", "reported", "weak"):
        bad.append(f"strength {d.get('strength')!r} not allowed")
    srcs, quotes = [], []
    for ev in d.get("evidence") or []:
        n = ev.get("source")
        if not isinstance(n, int) or not 1 <= n <= len(sources):
            bad.append(f"source number {n!r} not in the list")
            continue
        s, q = sources[n - 1], str(ev.get("quote") or "")
        if not LG.quote_in(q, s["text"]):
            bad.append(f"quote not verbatim in source [{n}]: {q[:80]!r}")
            continue
        quotes.append(q)
        srcs.append({k: s[k] for k in ("type", "id", "url", "accessed_at") if k in s}
                    | ({"section": s["section"], "credit": s["credit"]} if s["type"] == "nbk" else {"text_url": s["text_url"]})
                    | {"quote": q, "quote_verified": True})
    if not srcs:
        bad.append("no verified quote")
    for k in ("protein_position", "exon"):
        for x in (cond.get(k) or []) if isinstance(cond.get(k), list) else []:
            if not any(re.search(rf"(?<!\d){x}(?!\d)", q) for q in quotes):
                bad.append(f"{k} number {x} does not appear in any quote")
    if not str(d.get("statement") or "").strip():
        bad.append("empty statement")
    if bad:
        return None, bad
    return {"statement": d["statement"].strip(), "applies_when": cond,
            "effect": {"type": "diagnosis", "supports": sorted({o["id"] for c in sup for o in c["omim"]}),
                       "argues_against": sorted({o["id"] for c in ag for o in c["omim"]})},
            "exceptions": d.get("exceptions") or "", "sources": srcs, "strength": d["strength"]}, []


def draft_gene(gene: str, candidates: list[dict], nbks: list[str], *, use_cache: bool = True) -> dict:
    """The rule file content for one gene."""
    sources, searches = gather(gene, candidates, nbks)
    out = {"gene": gene, "drafted_at": int(time.time()), "prompt_version": PROMPT_VERSION,
           "candidates": [{"label": c["label"], "omim": [o["id"] for o in c["omim"]], "mondo": c["key"]} for c in candidates],
           "searches": searches,
           "sources": [{k: s[k] for k in ("type", "id", "url", "section", "credit", "accessed_at") if k in s} for s in sources],
           "rules": [], "rejected_drafts": []}
    if not sources:
        out["no_rule_reason"] = "no source text found"
        return out
    r = X._cached_chat(prompt(gene, candidates, sources), 0, use_cache, prompt_version=PROMPT_VERSION)
    parsed = X._parse(r)["parsed"]
    out["llm"] = {"llm": X.llm.config()["model"], "served_model": r.get("served_model"), "prompt_version": PROMPT_VERSION}
    out["no_rule_reason"] = parsed.get("no_rule_reason") or ""
    for i, d in enumerate(parsed.get("rules") or [], 1):
        rule, why = check_draft(d, candidates, sources)
        if rule is None:
            out["rejected_drafts"].append({"draft": d, "reasons": why})
            continue
        rule = {"id": f"{gene}-{i}", "gene": gene, "version": 1, **rule, "status": "verified",
                "drafted": {"llm": out["llm"], "prompt_version": PROMPT_VERSION}}
        rule["review"] = {"decision": "not_reviewed"}
        rule["content_sha256"] = content_hash(rule)
        out["rules"].append(rule)
    return out

"""Supportive Management fallback chain (contract docs/supportive_fallback_contract.md, v2 approved 2026-11-04).

Per diagnosis branch, strongest source first:
  L1 chapter      a single-gene GeneReviews chapter                       (tier_source "chapter")
  L2 overview     a multi-gene GeneReviews chapter that lists the gene    (tier_source "overview"; "disease-group advice")
  L3 literature   PubMed abstracts and PMC open-access full text           (tier_source "literature"; only when L1 and L2 give nothing)
  L4 symptomatic  configured, manually verified symptom guidelines        (tier_source "symptomatic"; when L1-L3 give nothing,
                  for every present symptom; otherwise only for present symptoms no higher-tier action covers)
Code decides every tier, coverage and check; the LLM only lifts verbatim recommendations from texts code supplies.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
from pathlib import Path

from aitx import http
from aitx.evidence import ledger as LG

ROOT = Path(__file__).resolve().parents[2]
TIERS = ("chapter", "overview", "literature", "symptomatic")
GUIDELINES = ROOT / "config" / "symptom_guidelines.json"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OA_SERVICE = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
N_PAPERS = 10                                    # decision 2026-11-04
PUB_TYPES = ("Review", "Systematic Review", "Practice Guideline", "Guideline", "Consensus Development Conference",
             "Observational Study", "Multicenter Study")
CASE_ONLY = {"Case Reports"}                    # a single-patient report is never a management source


# ------------------------------------------------------------------ L1 / L2: chapters per branch

def is_overview(nbk: str, step2: dict, title_of=None) -> bool:
    """An overview is a chapter whose own title says "Overview" (contract L2: "Hereditary Ataxia Overview"); a
    multi-gene chapter on one disease ("Classic Ehlers-Danlos Syndrome", 3 genes) is a chapter. Without the title
    (chapter not in the local archive), the Step 2 gene count decides."""
    title = (title_of or GR_title)(nbk)
    if title:
        return "overview" in title.lower()
    meta = {ch["nbk"]: ch for chs in (step2.get("genereviews") or {}).values() for ch in chs}
    return (meta.get(nbk) or {}).get("scope") == "multi_gene"


def GR_title(nbk: str) -> str | None:
    from aitx.evidence import genereviews as GR
    try:
        return GR.chapter_title(nbk)
    except (OSError, KeyError, ValueError, AttributeError, RuntimeError):   # chapter not available locally
        return None


def branch_tiers(ch_map: dict[str, list[str]], step2: dict, branches: list[dict], title_of=None) -> tuple[dict, dict]:
    """(chapters to use per branch, tier record per branch). A branch with a disease chapter uses only those (L1; an
    overview is not added - decision 3); otherwise its overview chapters that list the branch gene (L2)."""
    by_id = {b["id"]: b for b in branches}
    use, record = {}, {}
    for bid, nbks in ch_map.items():
        single = [n for n in nbks if not is_overview(n, step2, title_of)]
        multi = [n for n in nbks if is_overview(n, step2, title_of)]
        if single:
            use[bid] = single
            record[bid] = {"tier": "chapter", "chapters": single, "not_used": [{"nbk": n, "why": "overview not used: the "
                           "branch has a disease chapter"} for n in multi]}
        elif multi:
            use[bid] = multi
            record[bid] = {"tier": "overview", "chapters": multi, "gene": by_id.get(bid, {}).get("gene"),
                           "label": "disease-group advice (GeneReviews overview, not a chapter on this disease)"}
        else:
            use[bid] = []
            record[bid] = {"tier": None, "chapters": [], "why": "no GeneReviews chapter or overview for this diagnosis"}
    return use, record


def chapter_tier(nbk: str, step2: dict, title_of=None) -> str:
    return "overview" if is_overview(nbk, step2, title_of) else "chapter"


def other_gene_named(scope: str, chapter_genes: list[str], own_gene: str | None) -> str | None:
    """In an overview, advice whose row or paragraph names ANOTHER gene of the chapter is about that disease, not
    this one (contract L2). Returns that gene symbol, or None. Whole-word, case-sensitive gene symbols."""
    for g in chapter_genes:
        if g and g != own_gene and re.search(rf"(?<![A-Za-z0-9]){re.escape(g)}(?![A-Za-z0-9])", scope or ""):
            return g
    return None


def best_tier(specs: list[dict]) -> str:
    tiers = [sp.get("tier_source") for sp in specs if sp.get("tier_source") in TIERS]
    return min(tiers, key=TIERS.index) if tiers else ("label" if any(sp["src"]["type"] == "spl_setid" for sp in specs) else "chapter")


# ------------------------------------------------------------------ L3: literature (PubMed abstracts + PMC OA)

def literature_query(gene: str | None, names: list[str]) -> str:
    dz = " OR ".join(f'"{n}"[tiab]' for n in names if n and len(n) >= 4)
    who = f"({gene}[tiab])" if gene else ""
    subject = " AND ".join(x for x in (who, f"({dz})" if dz else "") if x)
    types = " OR ".join(f'"{t}"[pt]' for t in PUB_TYPES)
    return f"({subject}) AND ({types})"


def _get_json(url: str) -> dict:
    return json.loads(http.get(url, timeout=60).text)


def search_literature(gene: str | None, names: list[str]) -> dict:
    """{query, url, queried_at, count, papers: [{pmid, title, year, pub_types, pmc, oa, abstract, full_text}]}.
    Only abstracts and PMC open-access full text are fetched; nothing behind an access restriction (contract L3)."""
    q = literature_query(gene, names)
    url = f"{EUTILS}/esearch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "sort": "relevance",
                                                               "retmax": N_PAPERS, "term": q})
    d = _get_json(url)["esearchresult"]
    ids = d.get("idlist") or []
    rec = {"query": q, "url": url, "queried_at": int(time.time()), "count": int(d.get("count") or 0), "papers": []}
    if not ids:
        return rec
    summ = _get_json(f"{EUTILS}/esummary.fcgi?db=pubmed&retmode=json&id={','.join(ids)}")["result"]
    abstracts = abstracts_by_pmid(http.get(f"{EUTILS}/efetch.fcgi?db=pubmed&retmode=xml&id={','.join(ids)}", timeout=60).text)
    for pmid in ids:
        s = summ.get(pmid) or {}
        types = list(s.get("pubtype") or [])
        pmc = next((a["value"] for a in s.get("articleids") or [] if a.get("idtype") == "pmc"), None)
        paper = {"pmid": pmid, "title": s.get("title"), "year": (s.get("pubdate") or "")[:4], "pub_types": types,
                 "pmc": pmc, "oa": None, "abstract": abstracts.get(pmid, ""), "full_text": ""}
        if set(types) <= CASE_ONLY:
            paper["excluded"] = "case report"
        elif pmc:
            paper["oa"] = is_open_access(pmc)
            if paper["oa"]:
                paper["full_text"] = pmc_text(pmc)
        rec["papers"].append(paper)
    return rec


def abstracts_by_pmid(xml: str) -> dict[str, str]:
    out = {}
    for art in re.findall(r"<PubmedArticle>.*?</PubmedArticle>", xml or "", re.S):
        m = re.search(r"<PMID[^>]*>(\d+)</PMID>", art)
        parts = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", art, re.S)
        if m:
            out[m.group(1)] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", " ".join(parts))).strip()
    return out


def is_open_access(pmc: str) -> bool:
    """PMC's OA service decides (a record without an error is in the open-access subset); the result is recorded."""
    t = http.get(f"{OA_SERVICE}?id={pmc}", timeout=60).text
    return "<record " in t and "<error" not in t


def pmc_text(pmc: str) -> str:
    x = http.get(f"{EUTILS}/efetch.fcgi?db=pmc&retmode=xml&id={pmc.replace('PMC', '')}", timeout=60).text
    body = re.search(r"<body>(.*)</body>", x, re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body.group(1) if body else "")).strip()


LIT_SYSTEM = """You list management recommendations stated in one article about a genetic disease. Use only the text
given. List only recommendations the text states explicitly for patients with this disease ("we recommend", "should be
treated with", "patients benefit from"), each with the exact sentence. Do not list findings, mechanisms, diagnostics,
surveillance or what was done to one patient. For each, return one item:
{"name": "<drug, procedure, diet, device or therapy name>", "kind": "drug" | "procedure" | "diet" | "device" | "therapy",
 "quote": "<the exact sentence, copied character for character>", "manifestation": "<exact words naming the symptom it
 treats, or empty>"}
Return only JSON: {"items": [...]}"""


# ------------------------------------------------------------------ L4: symptom guidelines (manually verified)

def load_guidelines(path: Path = GUIDELINES) -> dict:
    """The approved symptom guideline table; absent until the list is reviewed (decision 2026-11-04)."""
    return json.loads(path.read_text()) if path.exists() else {"categories": {}}


def verified_text(entry: dict) -> str | None:
    """The manually verified passages of a guideline whose site refuses automated fetching: the local record must
    exist and match the sha256 in the table (contract L4). None otherwise - such a guideline is not used."""
    v = entry.get("verified") or {}
    f = ROOT / v.get("file", "")
    if not v.get("file") or not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != v.get("sha256"):
        return None
    rec = json.loads(f.read_text())
    return " ".join(p["text"] for p in rec.get("passages") or [])


def symptom_categories(present: list[dict], table: dict, ancestors) -> dict[str, list[dict]]:
    """category -> present symptoms (Step 2 present HPO terms) under one of its HPO roots."""
    out: dict[str, list[dict]] = {}
    for cat, c in (table.get("categories") or {}).items():
        roots = set(c.get("hpo") or [])
        for x in present:
            if x["hpo_id"] in roots or roots & set(ancestors(x["hpo_id"])):
                out.setdefault(cat, []).append(x)
    return out


def names_symptom(text: str, names: list[str]) -> str | None:
    """The HPO name or synonym of a symptom that a chapter's management text names (whole words; a short upper-case
    abbreviation such as CKD only in that case), or None."""
    for n in names:
        n = (n or "").strip()
        if len(n) < 3:
            continue
        flags = 0 if (n.isupper() and len(n) <= 5) else re.I
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(n)}(?![A-Za-z0-9])", text or "", flags):
            return n
    return None


def uncovered_symptoms(present: list[dict], manifestation_texts: list[str], matches) -> list[dict]:
    """Present symptoms no higher-tier action covers. matches(text, symptom) -> bool is the same HPO matching that
    decides a supportive action's manifestation condition (same term or an ancestor)."""
    return [x for x in present if not any(matches(t, x) for t in manifestation_texts)]


# ------------------------------------------------------------------ checks

def tier_problems(supportive_tiers: dict, actions: list[dict], present_ids: set[str]) -> list[str]:
    """Contract checks: every supportive action has tier_source; no literature search in a branch that has a chapter
    or overview result; a symptomatic action belongs to a branch without results above or fills a present symptom
    that nothing above covered."""
    bad = []
    for a in actions:
        if a["section"] != "supportive_management" or not a.get("action_key"):
            continue
        t = a.get("tier_source")
        if t not in TIERS + ("label",):
            bad.append(f"{a['action_key']}: no tier_source")
        if t == "symptomatic":
            s = a.get("for_symptom") or {}
            if s.get("hpo_id") not in present_ids:
                bad.append(f"{a['action_key']}: symptomatic action for a symptom not reported as present")
            for b in a["applies_to"]:
                rec = supportive_tiers.get(b) or {}
                if rec.get("results_above") and s.get("hpo_id") not in {x["hpo_id"] for x in rec.get("gap_filled") or []}:
                    bad.append(f"{a['action_key']}: symptomatic action in {b} for a symptom already covered above")
    for b, rec in supportive_tiers.items():
        if rec.get("tier") in ("chapter", "overview") and rec.get("results_above") and rec.get("literature"):
            bad.append(f"{b}: literature searched although the {rec['tier']} gave results")
    return bad

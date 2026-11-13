"""Live record-level APIs for step 2: ClinVar (E-utilities), MONDO via OLS4, HGNC.

All requests go through aitx.http (cached, access time recorded).
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field

from aitx import http
from aitx.variant.transcript import fetch_transcript

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
OLS = "https://www.ebi.ac.uk/ols4/api/ontologies/mondo/terms?obo_id="
HGNC = "https://rest.genenames.org/fetch/symbol/"

STARS = {
    "practice guideline": 4,
    "reviewed by expert panel": 3,
    "criteria provided, multiple submitters, no conflicts": 2,
    "criteria provided, single submitter": 1,
    "criteria provided, conflicting classifications": 1,
    "criteria provided, conflicting interpretations": 1,
}
GENERIC_TRAITS = {"not provided", "not specified", "inborn genetic diseases", "see cases"}
PLP = {"pathogenic", "likely pathogenic", "pathogenic/likely pathogenic"}


def _polite_get(url: str, **kw) -> http.Fetched:
    f = http.get(url, **kw)
    if not f.from_cache and url.startswith(EUTILS):
        time.sleep(0.4)  # NCBI: max 3 requests/second without an API key
    return f


# --------------------------------------------------------------------- ClinVar

def normalize_cdna(c: str) -> str:
    """c.8079delC -> c.8079del, c.1521_1523delCTT -> c.1521_1523del, c.33dupA -> c.33dup."""
    return re.sub(r"(del|dup)[ACGT]+$", r"\1", c.strip())


_VNAME = re.compile(r"^(?P<acc>N[MR]_\d+)\.(?P<ver>\d+)\([^)]*\):(?P<c>c\.[^ ]+)")


@dataclass
class ClinVarRecord:
    vcv: str
    title: str
    match: str                  # exact | cds_identical_version | version_mismatch
    significance: str
    review_status: str
    stars: int
    last_evaluated: str
    traits: list[dict]          # {name, xrefs: [curie], generic: bool}
    accessed_at: int
    match_note: str = ""

    @property
    def url(self) -> str:
        return f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{int(self.vcv[3:])}/"

    @property
    def is_plp(self) -> bool:
        return self.significance.strip().lower() in PLP

    def to_dict(self) -> dict:
        return {"vcv": self.vcv, "url": self.url, "title": self.title, "match": self.match,
                "match_note": self.match_note,
                "clinical_significance": self.significance, "review_status": self.review_status,
                "stars": self.stars, "last_evaluated": self.last_evaluated, "traits": self.traits,
                "accessed_at": self.accessed_at}


@dataclass
class ClinVarResult:
    query: str
    status: str                        # found | version_mismatch | not_found
    records: list[ClinVarRecord] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)   # search hits that are other variants
    search_url: str = ""


def _xref_curie(db: str, i: str) -> str | None:
    return {"MONDO": i if i.startswith("MONDO:") else f"MONDO:{i}", "OMIM": f"OMIM:{i}",
            "Orphanet": f"Orphanet:{i}", "MedGen": f"UMLS:{i}"}.get(db)


def _cds(accession: str) -> str:
    t = fetch_transcript(accession)
    return t.seq[t.cds_start - 1:t.cds_end]


def cds_equivalent(ours: str, theirs: str, cdna: str) -> tuple[bool, str]:
    """True if a coding c. position means the same base on both transcript versions.

    Holds when the c. change lies inside the CDS (no c.-N / c.*N / intronic
    offsets) and the two versions have byte-identical CDS sequences.
    """
    if re.search(r"[-*+]", cdna[2:].split("del")[0].split("dup")[0].split("ins")[0]):
        return False, "change is outside the CDS or intronic; versions not compared"
    try:
        a, b = _cds(ours), _cds(theirs)
    except Exception as e:  # noqa: BLE001 - treat as not verifiable
        return False, f"could not compare CDS: {e}"
    if a == b:
        return True, f"{ours} and {theirs} have identical CDS ({len(a)} nt); c. coordinates are equivalent"
    return False, f"{ours} and {theirs} CDS differ ({len(a)} vs {len(b)} nt)"


def clinvar_lookup(transcript: str, cdna: str, *, use_cache: bool = True) -> ClinVarResult:
    acc, _, ver = transcript.partition(".")
    want = normalize_cdna(cdna)
    query = f"{transcript}:{cdna}"
    surl = EUTILS + "esearch.fcgi?db=clinvar&retmode=json&retmax=50&term=" + urllib.parse.quote(query)
    ids = json.loads(_polite_get(surl, use_cache=use_cache).text)["esearchresult"]["idlist"]
    res = ClinVarResult(query, "not_found", search_url=surl)
    if not ids:
        return res
    f = _polite_get(EUTILS + "esummary.fcgi?db=clinvar&retmode=json&id=" + ",".join(ids), use_cache=use_cache)
    summ = json.loads(f.text)["result"]
    for uid in summ.get("uids", []):
        d = summ[uid]
        vs = d.get("variation_set", [])
        names = [v.get("variation_name", "") for v in vs]
        m = _VNAME.match(names[0]) if len(vs) == 1 else None
        if not m or m["acc"] != acc or normalize_cdna(m["c"]) != want:
            why = "multi-variant record (haplotype/compound)" if len(vs) != 1 else "different variant or transcript"
            res.rejected.append({"vcv": d.get("accession"), "title": d.get("title"), "reason": why})
            continue
        gc = d.get("germline_classification") or {}
        traits = []
        for t in gc.get("trait_set", []):
            name = t.get("trait_name", "")
            xr = [c for c in (_xref_curie(x.get("db_source", ""), x.get("db_id", "")) for x in t.get("trait_xrefs", [])) if c]
            traits.append({"name": name, "xrefs": xr, "generic": name.strip().lower() in GENERIC_TRAITS})
        rs = gc.get("review_status", "")
        match, note = "exact", ""
        if m["ver"] != ver:
            ok, note = cds_equivalent(transcript, f"{acc}.{m['ver']}", want)
            match = "cds_identical_version" if ok else "version_mismatch"
        res.records.append(ClinVarRecord(
            d["accession"], d.get("title", ""), match,
            gc.get("description", ""), rs, STARS.get(rs, 0), (gc.get("last_evaluated") or "")[:10].replace("/", "-"),
            traits, f.accessed_at, note))
    if any(r.match != "version_mismatch" for r in res.records):
        res.status = "found"
    elif res.records:
        res.status = "version_mismatch"
    return res


# ------------------------------------------------------------------------ OLS4

def mondo_term(mondo_id: str, *, use_cache: bool = True) -> dict:
    """{label, synonyms, obsolete, url, accessed_at}; empty synonyms if OLS has no record."""
    url = OLS + urllib.parse.quote(mondo_id)
    try:
        f = http.get(url, use_cache=use_cache)
    except RuntimeError as e:
        return {"label": "", "synonyms": [], "obsolete": None, "url": url, "error": str(e)}
    terms = json.loads(f.text).get("_embedded", {}).get("terms", [])
    if not terms:
        return {"label": "", "synonyms": [], "obsolete": None, "url": url, "accessed_at": f.accessed_at}
    t = terms[0]
    return {"label": t.get("label", ""), "synonyms": sorted(set(t.get("synonyms") or [])),
            "obsolete": bool(t.get("is_obsolete")), "subsets": sorted(t.get("in_subset") or []),
            "url": url, "accessed_at": f.accessed_at}


def mondo_ancestors(mondo_id: str, *, use_cache: bool = True) -> list[str]:
    """All MONDO ancestors (is_a and part_of) of a term, via OLS4."""
    iri = urllib.parse.quote(urllib.parse.quote(
        "http://purl.obolibrary.org/obo/" + mondo_id.replace(":", "_"), safe=""), safe="")
    url = f"https://www.ebi.ac.uk/ols4/api/ontologies/mondo/terms/{iri}/hierarchicalAncestors?size=1000"
    try:
        terms = json.loads(http.get(url, use_cache=use_cache).text).get("_embedded", {}).get("terms", [])
    except RuntimeError:
        return []
    return sorted({t["obo_id"] for t in terms if str(t.get("obo_id", "")).startswith("MONDO:")})


def mondo_parents(mondo_id: str, *, use_cache: bool = True) -> list[tuple[str, str]]:
    """Direct MONDO parents (id, label) of a term, via OLS4 (3b parent-disease search, 2026-11-12)."""
    iri = urllib.parse.quote(urllib.parse.quote(
        "http://purl.obolibrary.org/obo/" + mondo_id.replace(":", "_"), safe=""), safe="")
    url = f"https://www.ebi.ac.uk/ols4/api/ontologies/mondo/terms/{iri}/parents?size=200"
    try:
        terms = json.loads(http.get(url, use_cache=use_cache).text).get("_embedded", {}).get("terms", [])
    except RuntimeError:
        return []
    return sorted((t["obo_id"], t.get("label") or "") for t in terms if str(t.get("obo_id", "")).startswith("MONDO:"))


# ------------------------------------------------------------------------ HGNC

def hgnc_gene(symbol: str, *, use_cache: bool = True) -> dict:
    url = HGNC + urllib.parse.quote(symbol)
    f = http.get(url, use_cache=use_cache, headers={"Accept": "application/json"})
    docs = json.loads(f.text).get("response", {}).get("docs", [])
    if not docs:
        return {"symbol": symbol, "found": False, "url": url}
    d = docs[0]
    return {"symbol": d.get("symbol", symbol), "found": True, "hgnc_id": d.get("hgnc_id"),
            "name": d.get("name"), "aliases": d.get("alias_symbol", []), "previous_symbols": d.get("prev_symbol", []),
            "ncbi_gene_id": d.get("entrez_id"), "omim_gene_ids": d.get("omim_id", []),
            "url": f"https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/{d.get('hgnc_id')}",
            "api_url": url, "accessed_at": f.accessed_at}

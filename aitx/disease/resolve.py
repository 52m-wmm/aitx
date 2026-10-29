"""Contract steps 1-6: candidates, validity, ClinVar, inheritance fit, scoring, selection.

Everything here is deterministic; the only LLM input is the verified
extraction from aitx.disease.extract.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from aitx.disease import datasets as D
from aitx.disease import live
from aitx.disease import sources as S
from aitx.disease.hpo import Ontology, normalize

SCHEMA = "disease-resolution-v1"
AMBIGUITY_GAP = 0.20          # contract 5.2.3; tune on practice cases only
STRENGTH = ["Definitive", "Strong", "Moderate", "Limited", "Disputed", "Refuted"]
RANKED = set(STRENGTH[:4])
MOI_ORDER = {"consistent": 0, "conditional": 1, "unknown": 2, "inconsistent": 3}
X_MOI = {"XL", "XLR", "XLD"}


# ------------------------------------------------------------------ resources

@dataclass
class Resources:
    files: dict[str, D.LocalFile]
    mondo: S.Mondo
    mim2gene: dict[str, tuple[str, int]]
    hpoa: S.HpoAnnotations
    ont: Ontology
    genereviews: dict[str, list[S.GeneReview]]
    assoc: dict[str, list[S.Assoc]]
    use_cache: bool = True


def load_resources(genes: set[str], *, use_cache: bool = True) -> Resources:
    files = D.ensure_all()
    ont = Ontology(files["hpo_ontology"])
    hpoa = S.load_hpoa(files["hpo_annotations"])
    ont.build_ic(hpoa)
    by_gene: dict[str, list[S.Assoc]] = defaultdict(list)
    for a in (S.load_gencc(files["gencc"], genes) + S.load_clingen(files["clingen"], genes)
              + S.load_hpo_genes(files["hpo_genes_to_disease"], genes) + S.load_orphanet(files["orphanet_genes"], genes)):
        by_gene[a.gene].append(a)
    return Resources(files, S.load_mondo(files["mondo_sssom"]), S.load_mim2gene(files["omim_mim2gene"]), hpoa, ont,
                     S.load_genereviews(files["genereviews"]), dict(by_gene), use_cache)


# ----------------------------------------------------------------- candidates

@dataclass
class Candidate:
    key: str                       # MONDO id when mappable, else the source id
    gene: str
    label: str = ""
    omim: list[str] = field(default_factory=list)
    orphanet: list[str] = field(default_factory=list)
    umls: list[str] = field(default_factory=list)
    ratings: list[S.Assoc] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    obsolete: bool = False
    ols: dict = field(default_factory=dict)
    ancestors: list[str] = field(default_factory=list)

    @property
    def ids(self) -> set[str]:
        return {self.key, *self.omim, *self.orphanet, *self.umls}

    @property
    def specific(self) -> bool:
        return bool(self.omim or self.orphanet)


def build_candidates(gene: str, res: Resources) -> list[Candidate]:
    m = res.mondo
    cands: dict[str, Candidate] = {}
    for a in res.assoc.get(gene, []):
        key = a.disease_id if a.disease_id.startswith("MONDO:") else m.to_mondo.get(a.disease_id, a.disease_id)
        c = cands.setdefault(key, Candidate(key, gene))
        c.ratings.append(a)
        if not c.label and a.disease_label:
            c.label = a.disease_label
        if key == a.disease_id and not key.startswith("MONDO:"):   # unmapped OMIM/Orphanet id
            (c.omim if key.startswith("OMIM:") else c.orphanet).append(key)
    for c in cands.values():
        if c.key.startswith("MONDO:"):
            c.label = m.label.get(c.key) or c.label
            for o in m.xref(c.key, "OMIM"):
                if o not in c.omim:
                    c.omim.append(o)
            for o in m.xref(c.key, "Orphanet"):
                if o not in c.orphanet:
                    c.orphanet.append(o)
            c.umls = m.xref(c.key, "UMLS")
            c.ols = live.mondo_term(c.key, use_cache=res.use_cache)
            c.synonyms = c.ols.get("synonyms", [])
            c.ancestors = live.mondo_ancestors(c.key, use_cache=res.use_cache)
            c.label = c.label or c.ols.get("label", "")
            c.obsolete = bool(c.ols.get("obsolete")) or c.label.lower().startswith("obsolete")
        if not c.label:
            c.label = next((res.hpoa.names[i] for i in c.omim + c.orphanet if i in res.hpoa.names), c.key)
    return sorted(cands.values(), key=lambda c: c.key)


def validity(c: Candidate) -> dict:
    rated = [a for a in c.ratings if a.classification in STRENGTH]
    clingen = [a for a in rated if a.source == "clingen"]
    pool = clingen or rated
    summary = min((a.classification for a in pool), key=STRENGTH.index) if pool else (
        "Supportive" if any(a.classification == "Supportive" for a in c.ratings) else "unrated")
    return {
        "summary": summary,
        "clingen": [{"classification": a.classification, "moi": a.moi, "report": a.report_url,
                     "cite": a.cite.to_dict()} for a in clingen],
        "submitters": [{"source": a.source, "submitter": a.submitter, "classification": a.classification,
                        "moi": a.moi, "submitted_as": a.original_id or a.disease_id, "cite": a.cite.to_dict()}
                       for a in c.ratings],
        "has_ranked_evidence": any(a.classification in RANKED for a in rated),
        "only_disputed_or_refuted": bool(rated) and not any(a.classification in RANKED for a in rated),
    }


def candidate_mois(c: Candidate, res: Resources) -> list[dict]:
    out: dict[str, list[dict]] = defaultdict(list)
    for a in c.ratings:
        if a.moi != "unknown":
            out[a.moi].append({"source": a.submitter, "cite": a.cite.to_dict()})
    for i in c.omim + c.orphanet:
        for moi, line in res.hpoa.inheritance.get(i, []):
            out[moi].append({"source": f"HPO ({i})", "cite": S.Cite("hpo_annotations", res.hpoa.snapshot, line).to_dict()})
    return [{"moi": k, "sources": v} for k, v in sorted(out.items())]


# ----------------------------------------------------------- inheritance fit

def moi_fit(moi: str, zygosity: str, n_variants: int, sex: str) -> tuple[str, str]:
    z = zygosity
    if moi == "AR":
        if z == "homozygous":
            return "consistent", "homozygous variant fits autosomal recessive inheritance"
        if z == "heterozygous" and n_variants >= 2:
            return "conditional", "two heterozygous variants: fits AR only if they are on different alleles (phase not reported)"
        if z == "heterozygous":
            return "conditional", "single heterozygous variant: AR disease requires a second pathogenic variant on the other allele, which is not reported"
        return "unknown", f"{z} call is not interpretable for an autosomal recessive disease"
    if moi in ("AD", "SD"):
        if z == "heterozygous":
            return "consistent", "heterozygous variant fits autosomal dominant inheritance"
        if z == "homozygous":
            return ("consistent", "homozygous variant fits semidominant inheritance") if moi == "SD" else (
                "conditional", "homozygous variant in an autosomal dominant disease is unusual; possible but flagged")
        return "unknown", f"{z} call is not interpretable for an autosomal disease"
    if moi in X_MOI:
        if z == "hemizygous":
            if sex == "female":
                return "inconsistent", "hemizygous call reported in a female"
            return "consistent", "hemizygous X-linked variant" + (" in a male" if sex == "male" else " (sex not stated)")
        if z == "homozygous":
            return ("consistent", "homozygous X-linked variant in a female") if sex == "female" else (
                "unknown", "homozygous call on the X chromosome without female sex stated")
        if z == "heterozygous":
            if sex == "male":
                return "unknown", "heterozygous call on the X chromosome in a male"
            if moi == "XLD":
                return "consistent", "heterozygous variant fits X-linked dominant inheritance"
            return "conditional", "heterozygous X-linked variant: disease expression in females is possible but not typical"
    if moi == "MT":
        return "unknown", "mitochondrial inheritance cannot be assessed from a nuclear genotype"
    return "unknown", "inheritance mode not recorded"


def inheritance(c: Candidate, mois: list[dict], zygosity: str, n_variants: int, sex: str, de_novo: bool) -> dict:
    if not mois:
        return {"result": "unknown", "per_moi": [], "reason": "no inheritance mode recorded for this disease"}
    per = []
    for m in mois:
        r, why = moi_fit(m["moi"], zygosity, n_variants, sex)
        if de_novo and m["moi"] in ("AD", "SD", "XLD") and r == "consistent":
            why += "; de novo occurrence supports a dominant mechanism"
        per.append({"moi": m["moi"], "result": r, "reason": why, "sources": m["sources"]})
    best = min(per, key=lambda p: MOI_ORDER[p["result"]])
    return {"result": best["result"], "per_moi": per, "reason": f"{best['moi']}: {best['reason']}"}


# --------------------------------------------------------------- explicit dx

_OMIM_RX = re.compile(r"(?:OMIM|MIM)\s*[#:%*+]?\s*#?\s*(\d{6})", re.I)


def explicit_diagnosis(context: str, cands: list[Candidate], genes: set[str], aliases: set[str],
                       ont: Ontology) -> dict | None:
    norm_ctx = f" {normalize(context)} "
    numbers = _OMIM_RX.findall(context)
    alerts, hits = [], defaultdict(list)
    for n in numbers:
        ms = [c for c in cands if f"OMIM:{n}" in c.omim]
        if ms:
            for c in ms:
                hits[c.key].append({"how": "omim_number", "text": f"OMIM {n}"})
        else:
            alerts.append(f"text names OMIM {n}, which is not in the candidate set for {', '.join(sorted(genes))}; not adopted")
    skipped = []
    blocked = {g.lower() for g in genes | aliases}
    for c in cands:
        for name in sorted({c.label, *c.synonyms}):
            n = normalize(name)
            if len(n) < 4 or n in blocked:
                continue
            if f" {n} " not in norm_ctx:
                continue
            if name.isupper() and not re.search(rf"\b{re.escape(name)}\b", context):
                continue
            if ont.exact_lookup(name):
                skipped.append({"candidate": c.key, "name": name,
                                "reason": "also an HPO phenotype term; treated as a symptom, not a diagnosis"})
                continue
            hits[c.key].append({"how": "name", "text": name})
    if not hits and not alerts and not numbers:
        return None if not skipped else {"adopted": [], "matches": [], "alerts": [], "skipped_names": skipped}
    # Prefer candidates named by OMIM number; otherwise the longest matching name wins.
    if hits:
        def strength(k):
            hs = hits[k]
            return (any(h["how"] == "omim_number" for h in hs), max(len(h["text"]) for h in hs))
        top = max(strength(k) for k in hits)
        adopted = sorted(k for k in hits if strength(k) == top)
    else:
        adopted = []
    return {"adopted": adopted, "matches": [{"candidate": k, "evidence": v} for k, v in sorted(hits.items())],
            "alerts": alerts, "skipped_names": skipped}


# -------------------------------------------------------------------- ClinVar

def map_trait(xrefs: list[str], cands: list[Candidate], mondo: S.Mondo) -> tuple[list[str], str]:
    """Candidate keys a ClinVar trait refers to, and how.

    A trait's MONDO xref is used alone when present (ClinVar often adds the
    umbrella Orphanet id to subtype traits). If that MONDO term is not a
    candidate itself, it is matched to candidates it is an ancestor of
    (e.g. trait "Ehlers-Danlos syndrome" MONDO:0020066 -> classic EDS), as
    long as it does not cover every candidate of the gene.
    """
    by_id = {i: c.key for c in cands for i in c.ids}
    mondos = [x for x in xrefs if x.startswith("MONDO:")]
    if mondos:
        direct = sorted({by_id[x] for x in mondos if x in by_id})
        if direct:
            return direct, "direct"
        below = sorted({c.key for c in cands if any(x in c.ancestors for x in mondos)})
        genes = {c.gene for c in cands if c.key in below}
        if below and len(below) < sum(1 for c in cands if c.gene in genes):
            return below, f"MONDO hierarchy: {', '.join(mondos)} is an ancestor"
        return [], "no candidate"
    keys = {by_id[x] for x in xrefs if x in by_id}
    keys |= {by_id[mondo.to_mondo[x]] for x in xrefs if mondo.to_mondo.get(x) in by_id}
    return sorted(keys), "direct" if keys else "no candidate"


def clinvar_links(results: list[dict], cands: list[Candidate], mondo: S.Mondo) -> dict[str, list[dict]]:
    """candidate key -> ClinVar records (P/LP, accepted match) whose traits map to it."""
    links: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        for rec in r["records"]:
            mapped: dict[str, str] = {}
            for t in rec["traits"]:
                if t["generic"]:
                    continue
                keys, how = map_trait(t["xrefs"], cands, mondo)
                t["mapped_candidates"], t["mapping"] = keys, how
                for k in keys:
                    mapped.setdefault(k, how)
            rec["mapped_candidates"] = sorted(mapped)
            ranks = rec["match"] != "version_mismatch" and rec["clinical_significance"].strip().lower() in live.PLP
            rec["used_for_ranking"] = bool(ranks and mapped)
            if rec["used_for_ranking"]:
                for k, how in sorted(mapped.items()):
                    links[k].append({"vcv": rec["vcv"], "url": rec["url"], "stars": rec["stars"],
                                     "clinical_significance": rec["clinical_significance"], "variant": r["query"],
                                     "mapping": how})
    return links


# ------------------------------------------------------------------ selection

def _gap(a: float, b: float) -> float:
    return (a - b) / a if a > 0 else 0.0


def _contenders(pool: list[dict]) -> list[dict]:
    """Drop grouping terms (no OMIM/Orphanet id, no annotations) when a specific disease is present."""
    return [c for c in pool if c["specific"] or c["phenotype"]["score"] is not None] or pool


def _ties(ranked: list[dict]) -> list[dict]:
    """Candidates after ranked[0] that it does not clearly beat on phenotype score."""
    s0 = ranked[0]["phenotype"]["score"]
    out = []
    for c in ranked[1:]:
        s = c["phenotype"]["score"]
        if s0 is None or s is None or s0 <= 0 or _gap(s0, s) < AMBIGUITY_GAP:
            out.append(c)
    return out


def _lead(ranked: list[dict]) -> float | None:
    if len(ranked) < 2 or ranked[0]["phenotype"]["score"] is None or ranked[1]["phenotype"]["score"] is None:
        return None
    return round(_gap(ranked[0]["phenotype"]["score"], ranked[1]["phenotype"]["score"]), 3)


def select(cands: list[dict], present: list[str], excluded: list[str], explicit: list[str]) -> dict:
    """Pick the primary disease from scored candidate dicts. Pure function of its inputs."""
    elig = [c for c in cands if not c["excluded"]]
    if not elig:
        return {"status": "unresolved", "id": None, "basis": None, "reasons": ["no eligible candidate"], "tied": []}
    reasons: list[str] = []

    def by_pheno(pool):
        return sorted(pool, key=lambda c: (-(c["phenotype"]["score"] if c["phenotype"]["score"] is not None else -1e9), c["key"]))

    exp = [c for c in elig if c["key"] in explicit]
    if exp:
        top = by_pheno(exp)
        reasons.append(f"named in the clinical text: {top[0]['label']}")
        return {"status": "resolved", "id": top[0]["key"], "basis": "explicit", "reasons": reasons,
                "tied": [c["key"] for c in top[1:]]}

    cv = [c for c in elig if c["clinvar"]]
    if cv:
        best = max(max(l["stars"] for l in c["clinvar"]) for c in cv)
        pool = _contenders([c for c in cv if max(l["stars"] for l in c["clinvar"]) == best])
        top = by_pheno(pool)
        rec = top[0]["clinvar"][0]
        reasons.append(f"ClinVar {rec['vcv']} ({rec['clinical_significance']}, {best} star) links this variant to "
                       + ", ".join(c["label"] for c in top[:6]) + (" ..." if len(top) > 6 else ""))
        tied = _ties(top)
        if tied:
            reasons.append("ClinVar supports several candidates and phenotype scores do not separate them: "
                           + ", ".join(f"{c['label']} {c['phenotype']['score']}" for c in [top[0], *tied]))
            return {"status": "ambiguous", "id": top[0]["key"], "basis": "clinvar", "reasons": reasons,
                    "tied": [c["key"] for c in [top[0], *tied]]}
        return {"status": "resolved", "id": top[0]["key"], "basis": "clinvar", "reasons": reasons, "tied": [],
                "lead": _lead(top)}

    tier_val = min(MOI_ORDER[c["inheritance"]["result"]] for c in elig)
    tier = [c for c in elig if MOI_ORDER[c["inheritance"]["result"]] == tier_val]
    lower = [c for c in elig if c not in tier]
    contenders = _contenders(tier)
    grouping = [c["key"] for c in tier if c not in contenders]
    if grouping:
        reasons.append(f"grouping terms without OMIM/Orphanet ids or annotations not compared: {', '.join(grouping)}")
    if lower:
        reasons.append(f"inheritance tier '{tier[0]['inheritance']['result']}' ranked above "
                       f"{len(lower)} candidate(s) with weaker inheritance fit")
    scored = by_pheno([c for c in contenders if c["phenotype"]["score"] is not None])
    unscored = [c for c in contenders if c["phenotype"]["score"] is None]

    if len(contenders) == 1:
        c = contenders[0]
        basis = "only_candidate" if len(elig) == 1 else "inheritance"
        reasons.append(f"only candidate {'left' if basis == 'only_candidate' else 'in the best inheritance tier'}: {c['label']}")
        return {"status": "resolved", "id": c["key"], "basis": basis, "reasons": reasons, "tied": []}
    if not scored:
        reasons.append("no phenotype annotation data to separate the candidates")
        return {"status": "ambiguous", "id": contenders[0]["key"], "basis": "phenotype", "reasons": reasons,
                "tied": [c["key"] for c in contenders]}
    if not present:
        reasons.append("no verified patient phenotype terms to compare candidates")
        return {"status": "ambiguous", "id": scored[0]["key"], "basis": "phenotype", "reasons": reasons,
                "tied": [c["key"] for c in contenders]}
    s0 = scored[0]["phenotype"]["score"]
    if s0 <= 0:
        reasons.append("no candidate's phenotype annotations match the patient's terms")
        return {"status": "unresolved", "id": None, "basis": "phenotype", "reasons": reasons,
                "tied": [c["key"] for c in contenders]}
    tied = [c for c in scored[1:] if _gap(s0, c["phenotype"]["score"]) < AMBIGUITY_GAP]
    if unscored:
        reasons.append(f"candidates without annotation data cannot be compared: {', '.join(c['key'] for c in unscored)}")
    if tied or unscored:
        reasons.append(f"phenotype scores within {int(AMBIGUITY_GAP * 100)}%: "
                       + ", ".join(f"{c['label']} {c['phenotype']['score']}" for c in [scored[0], *tied]))
        return {"status": "ambiguous", "id": scored[0]["key"], "basis": "phenotype", "reasons": reasons,
                "tied": [c["key"] for c in [scored[0], *tied, *unscored]]}
    nxt = scored[1]["phenotype"]["score"] if len(scored) > 1 else None
    reasons.append(f"highest phenotype score {s0}" + (f" vs next {nxt} ({_gap(s0, nxt):.0%} lead)" if nxt is not None else ""))
    return {"status": "resolved", "id": scored[0]["key"], "basis": "phenotype", "reasons": reasons, "tied": [],
            "lead": round(_gap(s0, nxt), 3) if nxt is not None else None}


_CONF = ["low", "moderate", "high"]


def confidence(sel: dict, chosen: dict, best_score: float | None) -> tuple[str, list[str]]:
    notes = []
    strong = chosen["validity"]["summary"] in ("Definitive", "Strong")
    moi_ok = chosen["inheritance"]["result"] == "consistent"
    stars = max((l["stars"] for l in chosen["clinvar"]), default=0)
    clear = sel["basis"] == "explicit" or (sel["basis"] == "clinvar" and stars >= 2) or (
        sel["basis"] == "phenotype" and (sel.get("lead") or 0) >= AMBIGUITY_GAP)
    missing = [n for n, ok in (("evidence strength Definitive/Strong", strong), ("inheritance consistent", moi_ok),
                               ("clear selection basis", clear)) if not ok]
    level = 2 if not missing else 1 if len(missing) == 1 else 0
    if chosen["inheritance"]["result"] == "conditional":
        level = 0
        notes.append("inheritance fit is only conditional")
    if missing:
        notes.append("missing: " + ", ".join(missing))
    if chosen["phenotype"]["score"] is None and level > 1:
        level = 1
        notes.append("no phenotype annotation data for the chosen disease")
    s = chosen["phenotype"]["score"]
    if sel["basis"] in ("explicit", "clinvar") and best_score and s is not None and _gap(best_score, s) >= AMBIGUITY_GAP:
        level = max(0, level - 1)
        notes.append(f"conflict: phenotype score {s} trails the best candidate ({best_score})")
    return _CONF[level], notes

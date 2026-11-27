"""Step 2 assembly: one patient case -> DiseaseResolution (schema disease-resolution-v1)."""
from __future__ import annotations

from aitx import caseinput
from aitx.disease import extract as X
from aitx.disease import live
from aitx.disease import resolve as R
from aitx.disease import sources as S
from aitx.disease.output import build_layers
from aitx.disease.hpo import onset_fit
from aitx.disease.hpo import score as pheno_score


def _annotations(c: R.Candidate, res: R.Resources) -> list[S.Annotation]:
    out = []
    for i in c.omim + c.orphanet:
        out += res.hpoa.phenotypes.get(i, [])
    return out


def _clinical(c: R.Candidate, res: R.Resources) -> list[tuple[str, int]]:
    out = []
    for i in c.omim + c.orphanet:
        out += res.hpoa.clinical.get(i, [])
    return out


def patient_onset(facts: dict) -> dict:
    """Months; from the verified onset fact, else the current age as an upper bound."""
    o, a = facts.get("onset") or {}, facts.get("age") or {}
    if o.get("months_min") is not None or o.get("months_max") is not None:
        lo = o.get("months_min") if o.get("months_min") is not None else o.get("months_max")
        hi = o.get("months_max") if o.get("months_max") is not None else lo
        return {"min": lo, "max": hi, "kind": "onset", "quote": o.get("quote"),
                "hpo_onset": o.get("hpo_onset") or [], "stated_months": o.get("stated_months")}
    if a.get("months") is not None:
        return {"min": None, "max": a["months"], "kind": "age_upper_bound", "quote": a.get("quote")}
    return {}


def _score(c: R.Candidate, res: R.Resources, present: list[str], excluded: list[str], onset: dict) -> dict:
    ph = pheno_score(res.ont, present, excluded, _annotations(c, res))
    ph["onset"] = onset_fit(res.ont, onset, _clinical(c, res))
    if ph["score"] is not None and ph["onset"]["adjustment"]:
        ph["score_before_onset"] = ph["score"]
        ph["score"] = round(ph["score"] + ph["onset"]["adjustment"], 4)
    return ph


def molecular_variants(genotype: list[dict], step1: dict | None, case_id: str) -> list[dict]:
    """Join exact transcript identities; sequence checks are not pathogenicity evidence."""
    if step1 is not None and step1["id"] != case_id:
        raise ValueError("Step 1 case identity does not match Step 2")
    out = []
    for v in genotype:
        identity = {k: v[k] for k in ("gene", "transcript", "variant_cdna", "variant_protein", "zygosity")}
        if step1 is None:
            out.append(dict(identity, from_step1=False, status="unknown", conflicts=[],
                            effective_zygosity=v["zygosity"], reason="Step 1 output not supplied"))
            continue
        matches = [(i, p) for i, p in enumerate(step1["variants"])
                   if all(p[k] == v[k] for k in ("gene", "transcript", "variant_cdna"))]
        if len(matches) != 1:
            raise ValueError(f"Expected one exact Step 1 profile for {identity}; found {len(matches)}")
        i, prof = matches[0]
        conflicts = [f"{k}: input={v[k]}, Step1={prof[k]}"
                     for k in ("variant_protein", "zygosity") if prof[k] != v[k]]
        usable = prof["ok"] and not conflicts
        out.append(dict(identity, from_step1=True, status="usable" if usable else "conflicting",
                        conflicts=conflicts, effective_zygosity=prof["zygosity"] if usable else "unknown",
                        reported_zygosity=prof["zygosity"], variant_class=prof["variant_class"],
                        nmd_prediction=prof["nmd"]["prediction"], nmd=prof["nmd"],
                        mechanism_hypothesis=prof["mechanism_hypothesis"],
                        checks=prof["checks"], sequence_checks_pass=prof["ok"],
                        pathogenicity_prediction={"status": "unknown", "reason": "not produced by Step 1"},
                        source={"step": 1, "case_id": case_id, "pointer": f"/variants/{i}",
                                "evidence": prof["evidence"]},
                        evidence_kind={"zygosity": "reported", "variant_class": "sequence_derived",
                                       "nmd": "predicted", "mechanism_hypothesis": "predicted"}))
    return out


def _omim_entries(c: R.Candidate, res: R.Resources) -> list[dict]:
    out = []
    for o in c.omim:
        n = o.split(":")[1]
        typ, line = res.mim2gene.get(n, (None, None))
        out.append({"id": o, "url": f"https://omim.org/entry/{n}", "mim2gene_type": typ,
                    "is_phenotype_entry": typ in S.OMIM_PHENOTYPE_TYPES,
                    "cite": S.Cite("omim_mim2gene", res.files["omim_mim2gene"].snapshot, line).to_dict() if line else None})
    return out


def auxiliary_selection(sel: dict, cands: list[dict]) -> dict:
    """Keep score ordering, but do not certify a diagnosis solely from a score gap."""
    if sel["status"] != "resolved" or not (sel["basis"] == "phenotype" or
                                           (sel["basis"] == "clinvar" and "lead" in sel)):
        return sel
    contenders = [c for c in cands if not c["excluded"] and c["compete"]]
    chosen = next(c for c in contenders if c["key"] == sel["id"])
    if sel["basis"] == "clinvar":
        stars = max(link["stars"] for link in chosen["clinvar"])
        contenders = [c for c in contenders if c["clinvar"]
                      and max(link["stars"] for link in c["clinvar"]) == stars]
    else:
        contenders = [c for c in contenders if c["inheritance"]["result"] == chosen["inheritance"]["result"]]
    if len(contenders) > 1:
        sel = dict(sel, status="ambiguous", tied=[c["key"] for c in contenders],
                   reasons=sel["reasons"] + ["MICA is auxiliary evidence; a phenotype score lead does not establish the diagnosis"])
    return sel


def patient_phenotype_terms(ext: dict) -> tuple[list[str], list[str]]:
    """Only definite, attributed patient findings reach MICA and negative penalties."""
    facts = ext["patient_facts"]
    native = "clinical" in facts
    terms = facts["clinical"]["phenotypes"] if native else ext["phenotypes"]
    patient = [p for p in terms if (p["scope"] == "patient" if native else True) and p["valid"]]
    return (sorted({p["hpo_id"] for p in patient if p["status"] == "present"}),
            sorted({p["hpo_id"] for p in patient if p["status"] in ("absent", "excluded")}))


def run_case(case: dict, res: R.Resources, *, use_cache: bool = True, extraction: dict | None = None,
             step1: dict | None = None) -> dict:
    """step1: the case's step-1 VariantProfile output, if available (used for molecular screening with G2P requirements)."""
    pid = case["id"]
    genotype = case["patient"]["genotype"]
    context = caseinput.clinical_context(case)          # missing or empty: input error, never "" (fix plan O1)
    genes = sorted({v["gene"] for v in genotype})

    ext = extraction or X.extract(context, res.ont, use_cache=use_cache)
    facts = ext["patient_facts"]
    sex = facts["sex"].get("value", "unknown")
    de_novo = facts["variant_origin"].get("value") == "de_novo"
    present, excluded = patient_phenotype_terms(ext)
    onset = patient_onset(facts)

    gene_info = {g: live.hgnc_gene(g, use_cache=use_cache) for g in genes}
    aliases = {a for g in gene_info.values() for a in g.get("aliases", []) + g.get("previous_symbols", [])}
    cv_results = []
    for v in genotype:
        r = live.clinvar_lookup(v["transcript"], v["variant_cdna"], gene=v["gene"], use_cache=use_cache)
        cv_results.append({"gene": v["gene"], "query": r.query, "status": r.status, "search_url": r.search_url, "searches": r.searches,
                           "records": [x.to_dict() for x in r.records], "rejected": r.rejected})

    molecular = molecular_variants(genotype, step1, pid)
    zyg = {g: [v["effective_zygosity"] for v in molecular if v["gene"] == g] for g in genes}
    raw: list[R.Candidate] = [c for g in genes for c in R.build_candidates(g, res)]
    links = R.clinvar_links(cv_results, raw, res.mondo)
    explicit = R.explicit_diagnosis(context, raw, set(genes), aliases, res.ont)
    explicit_keys = explicit["adopted"] if explicit else []

    cands = []
    for c in raw:
        z = zyg[c.gene]
        zygosity = z[0] if len(z) == 1 else "heterozygous" if all(x == "heterozygous" for x in z) else z[0]
        mois = R.candidate_mois(c, res)
        val = R.validity(c)
        inh = R.inheritance(c, mois, zygosity, len(z), sex, de_novo)
        ph = _score(c, res, present, excluded, onset)
        excl_reasons = []
        if c.obsolete:
            excl_reasons.append("obsolete MONDO term")
        if val["only_disputed_or_refuted"]:
            excl_reasons.append(f"only Disputed/Refuted gene-disease evidence ({val['summary']})")
        if inh["result"] == "inconsistent":
            excl_reasons.append(f"inheritance inconsistent: {inh['reason']}")
        mech = sorted({a.mechanism for a in c.ratings if a.source == "orphanet" and a.mechanism})
        g2p = [record for record in res.g2p if record["gene"] == c.gene
               and c.ids.intersection(record["disease_ids"])]
        mol = R.molecular_fit([v for v in molecular if v["gene"] == c.gene], g2p, sex)
        cands.append({
            "key": c.key, "gene": c.gene, "label": c.label,
            "mondo": c.key if c.key.startswith("MONDO:") else None,
            "mondo_url": f"https://monarchinitiative.org/{c.key}" if c.key.startswith("MONDO:") else None,
            "omim": _omim_entries(c, res), "orphanet": c.orphanet, "specific": c.specific,
            "grouping": c.grouping,
            "mondo_cite": S.Cite("mondo_sssom", res.mondo.snapshot, res.mondo.line[c.key]).to_dict() if c.key in res.mondo.line else None,
            "validity": val, "inheritance": inh, "clinvar": links.get(c.key, []),
            "clinvar_info": [{"vcv": rec["vcv"], "url": rec["url"], "clinical_significance": rec["clinical_significance"],
                              "stars": rec["stars"], "match": rec["match"], "variant": r["query"],
                              "why_not_ranked": "match is version_mismatch" if rec["match"] == "version_mismatch"
                              else f"clinical significance is '{rec['clinical_significance']}', not P/LP"}
                             for r in cv_results for rec in r["records"]
                             if not rec["used_for_ranking"] and c.key in rec.get("mapped_candidates", [])],
            "phenotype": ph,
            "g2p_evidence": g2p, "molecular_assessment": mol,
            "orphanet_mechanism_hint": [{"text": m, "source": "Orphanet product6 association type",
                                         "cite": next(a.cite.to_dict() for a in c.ratings if a.mechanism == m)} for m in mech],
            "synonyms": c.synonyms, "ols": {k: c.ols.get(k) for k in ("url", "accessed_at", "obsolete")} if c.ols else None,
            "excluded": bool(excl_reasons), "exclusion_reasons": excl_reasons,
        })

    eligible = {c["key"] for c in cands if not c["excluded"]}
    annotated = {rc.key for rc in raw if _annotations(rc, res)}
    groups = R.merge_groups(raw, eligible, annotated)
    for c in cands:
        c["merge"] = groups[c["key"]]
        c["compete"] = groups[c["key"]]["role"] == "representative"

    def contains(group: str, specific: str) -> bool:       # fix plan D1: MONDO places `specific` within `group`
        try:
            return group in live.mondo_ancestors(specific, use_cache=res.use_cache)
        except (OSError, ValueError, KeyError, RuntimeError):  # OLS unavailable: no refinement, the named disease stands
            return False

    sel = R.select(cands, present, excluded, explicit_keys, contains)
    sel = R.molecular_selection(auxiliary_selection(sel, cands), cands)

    # stability: the same selection on each LLM sample's own terms
    per_sample = []
    for s in ext["samples"]:
        sp = sorted(t for t, st in s["terms"] if st == "present" and t in present)
        sx = sorted(t for t, st in s["terms"] if st in ("excluded", "absent") and t in excluded)
        sc = [dict(c, phenotype=_score(rc, res, sp, sx, onset)) for c, rc in zip(cands, raw)]
        ss = R.molecular_selection(auxiliary_selection(R.select(sc, sp, sx, explicit_keys, contains), sc), sc)
        per_sample.append({"status": ss["status"], "id": ss["id"]})
    distinct = {(p["status"], p["id"]) for p in per_sample}
    if len(distinct) > 1 and sel["status"] == "resolved":
        sel["status"] = "ambiguous"
        sel["reasons"].append(f"unstable across {len(per_sample)} LLM samples: {sorted(distinct, key=str)}")
        sel["tied"] = sorted({p["id"] for p in per_sample if p["id"]} | {sel["id"]})

    by_key = {c["key"]: c for c in cands}
    primary = {"id": sel["id"], "label": by_key[sel["id"]]["label"] if sel["id"] else None,
               "omim": [o["id"] for o in by_key[sel["id"]]["omim"]] if sel["id"] else [],
               "status": sel["status"], "basis": sel["basis"], "reasons": sel["reasons"],
               "alternatives": [{"id": k, "label": by_key[k]["label"]} for k in sel.get("tied", []) if k != sel["id"]]}
    if sel["id"]:
        best = max((c["phenotype"]["score"] for c in cands
                    if not c["excluded"] and c["compete"] and c["phenotype"]["score"] is not None),
                   default=None)
        conf, notes = R.confidence(sel, by_key[sel["id"]], best)
        primary["confidence"] = conf if sel["status"] == "resolved" else "low"
        primary["confidence_notes"] = notes
        if by_key[sel["id"]]["validity"]["summary"] == "Limited":
            primary["confidence_notes"].append("gene-disease evidence is only Limited")
    else:
        primary["confidence"] = None
    primary["per_sample"] = per_sample
    # for review: the score a competitor must reach to be "within the ambiguity gap" of the primary
    ps = by_key[sel["id"]]["phenotype"]["score"] if sel["id"] else None
    primary["ambiguity_gap"] = R.AMBIGUITY_GAP
    primary["primary_score"] = ps
    primary["ambiguity_threshold_score"] = round(ps * (1 - R.AMBIGUITY_GAP), 4) if ps is not None and ps > 0 else None

    gr = {g: [ch.to_dict(res.files["genereviews"].snapshot) for ch in res.genereviews.get(g, [])] for g in genes}
    out = {
        "schema_version": R.SCHEMA,
        "patient_id": pid,
        "phenotypes": ext["phenotypes"],
        "phenotype_extraction": {k: ext[k] for k in ("unstable_phenotypes", "rejected_phenotypes",
                                                    "phenotype_conflicts", "samples", "prompt_version")},
        "explicit_diagnosis": explicit,
        "patient_facts": facts,
        "g2p_records": res.g2p,
        "g2p_role": "molecular condition screening and diagnostic uncertainty; not patient variant mechanism confirmation",
        "molecular_evidence": molecular,
        "patient_onset": onset or None,
        "inheritance_evidence": {"zygosity": zyg, "sex": sex, "variant_origin": facts["variant_origin"].get("value"),
                                 "variants": molecular},
        "clinvar": cv_results,
        "candidates": [c for c in cands if not c["excluded"]],
        "not_supported": [c for c in cands if c["excluded"]],
        "gene_aliases": gene_info,
        "genereviews": gr,
        "primary": primary,
        "sources_manifest": S.manifest(res.files),
        "hpo_version": res.ont.version,
    }
    out["checks"] = checks(out, case, res)
    out["evidence"] = evidence(out)
    out["ok"] = all(c["status"] == "pass" for c in out["checks"])
    out["layers"] = build_layers(case, step1, out)
    return out


# --------------------------------------------------------------------- checks

def _chk(name: str, ok: bool, detail: str = "", warn: bool = False) -> dict:
    return {"name": name, "status": "pass" if ok else ("warn" if warn else "fail"), "detail": detail}


def checks(out: dict, case: dict, res: R.Resources) -> list[dict]:
    ctx = caseinput.clinical_context(case)
    allc =out["candidates"] + out["not_supported"]
    keys = {c["key"] for c in allc}
    res_ = []
    res_.append(_chk("datasets_complete", len(out["sources_manifest"]) == len(R.D.STEP2_DATASETS),
                     f"{len(out['sources_manifest'])}/{len(R.D.STEP2_DATASETS)} datasets in manifest"))
    bad_omim = [o["id"] for c in allc for o in c["omim"] if not o["is_phenotype_entry"]]
    res_.append(_chk("omim_ids_are_phenotype_entries", not bad_omim, ", ".join(bad_omim)))
    bad_mondo = [c["key"] for c in allc if c["mondo"] and c["mondo_cite"] is None
                 and not (c["ols"] and c["ols"].get("obsolete") is not None)]
    res_.append(_chk("mondo_ids_exist", not bad_mondo, "not in SSSOM nor OLS: " + ", ".join(bad_mondo)))
    unmapped = [c["key"] for c in allc if not c["mondo"]]
    if unmapped:
        res_.append(_chk("candidates_without_mondo", False, ", ".join(unmapped), warn=True))
    bad_hpo = [p["hpo_id"] for p in out["phenotypes"]
               if res.ont.resolve(p["hpo_id"])[0] != p["hpo_id"] or p["quote"] not in ctx]
    res_.append(_chk("hpo_terms_valid_and_quoted", not bad_hpo, ", ".join(bad_hpo)))
    used = {out["primary"]["id"]} | {a["id"] for a in out["primary"]["alternatives"]}
    if out["explicit_diagnosis"]:
        used |= set(out["explicit_diagnosis"]["adopted"])
    used |= {k for r in out["clinvar"] for rec in r["records"] for k in rec.get("mapped_candidates", [])}
    used.discard(None)
    res_.append(_chk("no_outside_candidates", used <= keys, ", ".join(sorted(used - keys))))
    bad_cv = [rec["vcv"] for r in out["clinvar"] for rec in r["records"]
              if rec.get("used_for_ranking") and rec["match"] not in ("exact", "cds_identical_version")]
    res_.append(_chk("clinvar_exact_match", not bad_cv, ", ".join(bad_cv)))
    bad_q = [k for k, f in out["patient_facts"].items() if f.get("quote") and f["quote"] not in ctx and f.get("verified")]
    res_.append(_chk("patient_facts_quoted", not bad_q, ", ".join(bad_q)))
    if out["explicit_diagnosis"] and out["explicit_diagnosis"]["alerts"]:
        res_.append(_chk("explicit_diagnosis_in_candidates", False, "; ".join(out["explicit_diagnosis"]["alerts"]), warn=True))
    models = {s["served_model"] for s in out["phenotype_extraction"]["samples"]}
    res_.append(_chk("llm_model_recorded", all(models), ", ".join(sorted(models))))
    return res_


def evidence(out: dict) -> list[dict]:
    """Flat claim -> source list for the report's citation step."""
    ev = []
    p = out["primary"]
    for c in out["candidates"] + out["not_supported"]:
        for o in c["omim"]:
            ev.append({"claim": f"{c['label']} is OMIM {o['id']}", "source": o["url"], "cite": o["cite"]})
        if c["mondo_cite"]:
            ev.append({"claim": f"{c['label']} is {c['key']}", "source": c["mondo_url"], "cite": c["mondo_cite"]})
        for cg in c["validity"]["clingen"]:
            ev.append({"claim": f"ClinGen: {c['gene']} - {c['label']} {cg['classification']} ({cg['moi']})",
                       "source": cg["report"], "cite": cg["cite"]})
        for l in c["clinvar"]:
            ev.append({"claim": f"{l['variant']} is {l['clinical_significance']} for {c['label']} in ClinVar",
                       "source": l["url"]})
    for g, chapters in out["genereviews"].items():
        for ch in chapters:
            ev.append({"claim": f"GeneReviews chapter for {g}: {ch['title']}", "source": ch["url"], "cite": ch["cite"]})
    if p["id"]:
        ev.append({"claim": f"primary disease {p['label']} ({p['status']}, {p['basis']})", "source": "derived",
                   "reasons": p["reasons"]})
    return ev

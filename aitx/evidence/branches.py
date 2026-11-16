"""Diagnosis branches (step 3.0 contract, section 2) and patient context (section 3).

Branches come from the step 2 decision, never from new judgement:
  resolved    -> the primary diagnosis
  ambiguous   -> primary + alternatives (step 2 order), at most MAX_BRANCHES
  unresolved  -> one gene-level branch (gene and variant facts only)
An umbrella diagnosis (no OMIM number, or marked non-specific by step 2) is replaced by the more specific
diseases step 2 recorded under it for this gene (candidate.merge.narrower_competing); if there are none it
stays and is marked not expandable. Branches are never deleted by rules; rules only reorder (branch_order).
"""
from __future__ import annotations

import re
from aitx.disease import live

MAX_BRANCHES = 3


def _score(c: dict) -> float:
    s = (c.get("phenotype") or {}).get("score")
    return s if s is not None else float("-inf")


def make_branch(c: dict, gene: str, why: list[str], expanded_from: str | None = None) -> dict:
    umbrella = not c["omim"] or not c.get("specific", True)
    return {"id": c["key"], "diagnosis": {"mondo": c["key"], "label": c["label"], "omim": [o["id"] for o in c["omim"]],
                                          "orphanet": c.get("orphanet") or [], "mondo_url": c.get("mondo_url")},
            "gene": gene, "why": why, "step2_score": (c.get("phenotype") or {}).get("score"),
            "umbrella": umbrella, "expanded_from": expanded_from}


def build_branches(step2: dict) -> tuple[list[dict], list[dict]]:
    """(branches, dropped). Branch ids are MONDO ids (stable across runs); roles follow the final order."""
    p = step2["primary"]
    cands = {c["key"]: c for c in step2["candidates"] + step2.get("not_supported", [])}
    genes = sorted({v["gene"] for v in step2["inheritance_evidence"]["variants"]})
    gene = genes[0] if len(genes) == 1 else "+".join(genes)
    if p["status"] == "unresolved" or not p.get("id"):
        return [{"id": f"gene:{gene}", "role": "gene_level", "diagnosis": None, "gene": gene,
                 "why": ["step 2 found no eligible diagnosis; gene and variant facts only"], "step2_score": None,
                 "umbrella": False, "expanded_from": None}], []
    picked = [(p["id"], p["reasons"])] + [(a["id"], [f"tied with the primary diagnosis in step 2 ({p['status']})"])
                                          for a in p["alternatives"]] if p["status"] == "ambiguous" else [(p["id"], p["reasons"])]
    out: list[dict] = []
    seen: set[str] = set()
    for key, why in picked:
        c = cands[key]
        b = make_branch(c, gene, why)
        if b["umbrella"]:
            kids = [cands[k] for k in (c.get("merge") or {}).get("narrower_competing") or []
                    if k in cands and not cands[k].get("excluded")]
            if kids:
                for k in sorted(kids, key=lambda x: (-_score(x), x["key"])):
                    if k["key"] not in seen:
                        seen.add(k["key"])
                        out.append(make_branch(k, gene, why + [f"expanded from umbrella '{c['label']}' ({key})"],
                                           expanded_from=key))
                continue
            b["not_expandable"] = "no more specific disease for this gene recorded under it in step 2"
        if key not in seen:
            seen.add(key)
            out.append(b)
    dropped = []
    if len(out) > MAX_BRANCHES:
        ranked = sorted(range(len(out)), key=lambda i: (-_score_of(out[i]), i))   # score, ties by step 2 order
        keep = sorted(ranked[:MAX_BRANCHES])
        dropped = [dict(out[i], dropped_reason=f"more than {MAX_BRANCHES} branches; lower step 2 score")
                   for i in range(len(out)) if i not in keep]
        out = [out[i] for i in keep]
    set_roles(out, resolved=p["status"] == "resolved")
    return out, dropped


def set_roles(branches: list[dict], resolved: bool) -> None:
    """primary for a single resolved diagnosis, otherwise ambiguous_1..N in order."""
    for i, b in enumerate(branches):
        if b.get("role") == "gene_level":
            continue
        b["role"] = "primary" if (resolved and len(branches) == 1) else f"ambiguous_{i + 1}"


def _score_of(b: dict) -> float:
    return b["step2_score"] if b["step2_score"] is not None else float("-inf")


# ------------------------------------------------------------ patient context

MISSING_WHY = {
    "age": "age limits in drug labels and trial eligibility",
    "sex": "trial eligibility and interpretation of X-linked findings",
}


def sex_fact(step1: dict, step2: dict) -> dict:
    """Original text wins; otherwise X-chromosomal hemizygosity permits the approved male inference."""
    stated = step2["patient_facts"]["sex"]
    out = dict(stated, step=2, inferred=False)
    if stated["value"] in ("male", "female"):
        return out
    for i, v in enumerate(step1["variants"]):
        if v["zygosity"] != "hemizygous":
            continue
        gene = live.hgnc_gene(v["gene"])
        if not gene["found"] or not gene["location"] or not re.match(r"X(?:[pq]|$)", gene["location"], re.I):
            continue
        claim = f"Sex inferred as male: {v['gene']} is on chromosome X ({gene['location']}) and {v['variant_cdna']} is hemizygous."
        return dict(value="male", quote=claim, step=3, inferred=True, variant_index=i, gene_location=gene)
    return out


def patient_context(step1: dict, step2: dict) -> tuple[dict, list[dict]]:
    """Copied from step 1 / step 2 with their quotes; no new extraction. Returns (context, missing info)."""
    f = step2["patient_facts"]
    sex = sex_fact(step1, step2)
    ctx = {
        "age_months": f["age"].get("months"), "age_quote": f["age"].get("quote"),
        "sex": sex["value"], "sex_quote": sex["quote"],
        "onset": step2.get("patient_onset") or None,
        "variant_origin": f["variant_origin"].get("value"),
        "family_history": f["family_history"].get("statement"),
        "phenotypes": [{"hpo_id": x["hpo_id"], "label": x["label"], "status": x["status"], "quote": x["quote"]}
                       for x in step2["phenotypes"]],
        "variants": [{k: v.get(k) for k in ("gene", "transcript", "variant_cdna", "variant_protein", "zygosity",
                                            "variant_class", "ptc_aa_position", "fraction_of_protein_retained")}
                     | {"nmd": (v.get("nmd") or {}).get("prediction"), "exon": (v.get("exon") or {}).get("number"),
                        "exons_total": (v.get("exon") or {}).get("total")}
                     for v in step1["variants"]],
    }
    if sex["inferred"]:
        ctx["sex_inference"] = sex
    missing = []
    if ctx["age_months"] is None:
        missing.append({"variable": "age", "why_it_matters": MISSING_WHY["age"], "affects": [], "asked_by": "3.0"})
    if ctx["sex"] in (None, "unknown"):
        missing.append({"variable": "sex", "why_it_matters": MISSING_WHY["sex"], "affects": [], "asked_by": "3.0"})
    return ctx, missing

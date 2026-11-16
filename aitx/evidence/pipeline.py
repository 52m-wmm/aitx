"""Step 3.0: build the evidence ledger skeleton for one case (contract sections 2, 3, 6).

No section is searched here (3a-3e do that). This enters the deterministic facts later steps reason
from, each as `background` evidence whose source is the upstream result file (`pipeline_fact`): the
quote is the value as it appears in that file, and the check reads the file to confirm it. The upstream
record (ClinVar, RefSeq, GeneReviews, AlphaFold, MONDO) is kept in `source.url` / `source.upstream`.
"""
from __future__ import annotations

import json

from aitx import runmeta
from aitx.evidence import ledger as LG
from aitx.evidence.branches import build_branches, patient_context
from aitx.evidence.established import add_established
from aitx.evidence.trial_records import add_trials
from aitx.evidence.bespoke import add_bespoke
from aitx.evidence.offlabel import add_offlabel
from aitx.evidence.repurposing import add_repurposing
from aitx.evidence.rules import apply_rules, load_rules


def _fact(led: LG.Ledger, case_id: str, step: int, text: str, created: int, path: str, value, claim: str,
          applies: list[str], url: str | None = None, upstream: dict | None = None) -> dict:
    src = {"type": "pipeline_fact", "id": f"step{step}:{case_id}:{path}", "url": url}
    if upstream:
        src["upstream"] = upstream
    return led.add(LG.sourced(claim, "background", applies, src, json.dumps(value, ensure_ascii=False), text, created,
                              retrieved_by=f"3.0 from out/step{step}"))


def record_sex_inference(led: LG.Ledger, cid: str, step1: dict, text1: str) -> None:
    if "sex_inference" not in led.patient_context:
        return
    fact = led.patient_context["sex_inference"]
    i, gene = fact["variant_index"], fact["gene_location"]
    variant = step1["variants"][i]
    branches = [b["id"] for b in led.branches]
    zyg = _fact(led, cid, 1, text1, step1["_meta"]["created_at"],
                f"variants[{i}].zygosity", variant["zygosity"],
                f"{variant['gene']} {variant['variant_cdna']} is hemizygous.", branches)
    location = led.add(LG.sourced(f"HGNC places {variant['gene']} at {gene['location']}.", "background", branches,
                                  {"type": "url", "id": gene["api_url"], "url": gene["api_url"]},
                                  gene["location"], json.dumps(gene), gene["accessed_at"], retrieved_by="HGNC gene location"))
    derived = led.add(LG.reasoning(fact["quote"], "background", branches, [zyg["id"], location["id"]],
                                  retrieved_by="sex inference: chromosome X and hemizygous; original text takes precedence"))
    fact["evidence_id"] = derived["id"]


def background(led: LG.Ledger, case_id: str, step1: dict, step2: dict, text1: str, text2: str) -> None:
    all_b = [b["id"] for b in led.branches]
    t1 = (step1.get("_meta") or {}).get("created_at") or 0
    t2 = (step2.get("_meta") or {}).get("created_at") or 0
    cands = {c["key"]: c for c in step2["candidates"] + step2.get("not_supported", [])}
    # diagnosis branches
    for b in led.branches:
        d = b["diagnosis"]
        if not d:
            continue
        c = cands[b["id"]]
        _fact(led, case_id, 2, text2, t2, f"candidates[{b['id']}].label", c["label"],
              f"Diagnosis under consideration: {c['label']} ({', '.join(d['omim']) or 'no OMIM number'}; {b['id']}); "
              f"step 2 confidence {step2['primary'].get('confidence')}.", [b["id"]], d.get("mondo_url"),
              {"type": "mondo", "id": b["id"]})
        v = c.get("validity") or {}
        if v.get("summary"):
            _fact(led, case_id, 2, text2, t2, f"candidates[{b['id']}].validity.summary", v["summary"],
                  f"Gene-disease validity for {b['gene']} and {c['label']}: {v['summary']}.", [b["id"]],
                  next((x.get("report") for x in v.get("clingen") or [] if x.get("report")), None))
        for rec in c.get("clinvar_info") or []:
            _fact(led, case_id, 2, text2, t2, f"candidates[{b['id']}].clinvar_info.{rec.get('vcv')}",
                  rec.get("clinical_significance"),
                  f"ClinVar {rec.get('vcv')} (not used for ranking) lists {rec.get('clinical_significance')} for this variant "
                  f"in relation to {c['label']}.", [b["id"]], rec.get("url"), {"type": "clinvar_vcv", "id": rec.get("vcv")})
    # ClinVar exact-match records for the patient's variants
    for i, cv in enumerate(step2.get("clinvar") or []):
        if cv.get("status") == "not_found":
            _fact(led, case_id, 2, text2, t2, f"clinvar[{i}].status", cv["status"],
                  f"No ClinVar record matches {cv['query']} exactly.", all_b, cv.get("search_url"))
        for rec in cv.get("records") or []:
            _fact(led, case_id, 2, text2, t2, f"clinvar[{i}].{rec['vcv']}.clinical_significance",
                  rec["clinical_significance"],
                  f"ClinVar {rec['vcv']} ({rec['title']}): {rec['clinical_significance']}, review status "
                  f"'{rec['review_status']}' ({rec['stars']} stars).", all_b, rec.get("url"),
                  {"type": "clinvar_vcv", "id": rec["vcv"]})
    # GeneReviews chapters for the gene(s)
    for gene, chapters in (step2.get("genereviews") or {}).items():
        for ch in chapters:
            _fact(led, case_id, 2, text2, t2, f"genereviews.{gene}.{ch['nbk']}.title", ch["title"],
                  f"GeneReviews chapter for {gene}: {ch['title']} ({ch['nbk']}).", all_b, ch.get("url"),
                  {"type": "nbk", "id": ch["nbk"]})
    # variant facts from step 1
    for i, v in enumerate(step1["variants"]):
        tag = f"{v['gene']} {v['variant_cdna']}"
        ref = (v.get("evidence") or [{}])[0].get("source")
        up = {"type": "refseq", "id": v["transcript"]}
        p = f"variants[{i}]"
        _fact(led, case_id, 1, text1, t1, f"{p}.variant_class", v["variant_class"],
              f"{tag} ({v['variant_protein']}) is a {v['variant_class'].replace('_', ' ')} variant, {v['zygosity']}.",
              all_b, ref, up)
        nmd = v.get("nmd") or {}
        _fact(led, case_id, 1, text1, t1, f"{p}.nmd.prediction", nmd.get("prediction"),
              f"NMD prediction for {tag}: {nmd.get('prediction')} ({'; '.join(nmd.get('reasons') or [])}).", all_b, ref, up)
        ex = v.get("exon") or {}
        if ex.get("number"):
            _fact(led, case_id, 1, text1, t1, f"{p}.exon.number", ex["number"],
                  f"{tag} lies in exon {ex['number']} of {ex.get('total')}.", all_b, ref, up)
        cmp_ = (v.get("retranslation") or {}).get("comparison") or {}
        if cmp_.get("agree") is not None:
            _fact(led, case_id, 1, text1, t1, f"{p}.retranslation.comparison.agree", cmp_["agree"],
                  f"Independent re-translation of {tag} {'agrees' if cmp_['agree'] else 'DISAGREES'} with "
                  f"{v['variant_protein']} ({cmp_.get('what')}: computed {cmp_.get('computed')}).", all_b, ref, up)
        st = v.get("structure") or {}
        if st.get("rsa"):
            af = st["source"]
            _fact(led, case_id, 1, text1, t1, f"{p}.structure.rsa.class", st["rsa"]["class"],
                  f"In the AlphaFold model {af['alphafold_entry']} (v{af['model_version']}), the variant residue is "
                  f"{st['rsa']['class']} (RSA {st['rsa']['value']}) with pLDDT {st['plddt']['value']}"
                  f"{' (unreliable region)' if not st['plddt']['reliable'] else ''}.", all_b, af["pdb_url"],
                  {"type": "alphafold", "id": af["alphafold_entry"]})


def run_case(case: dict, step1: dict, step2: dict) -> dict:
    cid = case["id"]
    branches, dropped = build_branches(step2)
    led = LG.Ledger(cid, branches)
    led.patient_context, led.missing_information = patient_context(step1, step2)
    text1 = runmeta.path(1, cid).read_text() if runmeta.path(1, cid).exists() else json.dumps(step1, indent=2, ensure_ascii=False)
    text2 = runmeta.path(2, cid).read_text() if runmeta.path(2, cid).exists() else json.dumps(step2, indent=2, ensure_ascii=False)
    apply_rules(led, load_rules(), step1, step2)       # may promote a step 2 candidate to a branch
    background(led, cid, step1, step2, text1, text2)
    record_sex_inference(led, cid, step1, text1)
    add_established(led, step1, step2)                 # 3a: Tier 1 sections
    add_trials(led, case, step1, step2)                # 3b: Clinical Trial Eligibility
    add_offlabel(led, case, step1, step2)              # 3c: Off-label / Expanded Access
    led.possible_duplicates += LG.possible_duplicates(led.actions, led.evidence)    # N3: flagged, never deleted
    add_bespoke(led, case, step1, step2)               # 3d: Bespoke Therapies
    add_repurposing(led, case, step1, step2)           # 3e: Drug Repurposing
    out = led.to_dict()
    out["branches_dropped"] = dropped
    out["ok"] = all(c["status"] != "fail" for c in out["checks"])
    return out

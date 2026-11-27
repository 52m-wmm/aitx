"""Lossless L1-L4 presentation of existing Step 2 evidence; no new adjudication.

References are JSON pointers rooted at this `layers` object, not a new ledger.
The original Step 2 fields remain available to existing downstream readers.
"""
from __future__ import annotations

from copy import deepcopy


def _reference(kind: str, path: str, evidence_kind: str) -> dict:
    return {"kind": kind, "evidence_kind": evidence_kind, "ref": path}


def _candidate(c: dict, root: str, primary: dict) -> dict:
    """Index existing evidence by direction without changing its strength or status."""
    support, oppose, pending = [], [], []
    ref = root + "/record"
    if c["validity"]["has_ranked_evidence"]:
        support.append(_reference("gene_disease_association", ref + "/validity", "database_assertion"))
    if c["validity"]["only_disputed_or_refuted"]:
        oppose.append(_reference("disputed_gene_disease_association", ref + "/validity", "database_assertion"))
    for i, m in enumerate(c["inheritance"]["per_moi"]):
        target = support if m["result"] == "consistent" else oppose if m["result"] == "inconsistent" else pending
        target.append(_reference("inheritance_fit", f"{ref}/inheritance/per_moi/{i}", "derived_compatibility"))
    if c["inheritance"]["result"] == "unknown":
        pending.append(_reference("inheritance_unknown", ref + "/inheritance", "unknown"))
    for i, match in enumerate(c["phenotype"]["matches"]):
        if match["ic"] > 0:
            support.append(_reference("phenotype_similarity", f"{ref}/phenotype/matches/{i}", "auxiliary_computation"))
    for i, penalty in enumerate(c["phenotype"]["penalties"]):
        if penalty["penalty"] <= 0:
            continue
        oppose.append(_reference("phenotype_penalty", f"{ref}/phenotype/penalties/{i}", "auxiliary_computation"))
    onset = c["phenotype"]["onset"]
    if onset["adjustment"]:
        (support if onset["adjustment"] > 0 else oppose).append(
            _reference("onset_fit", ref + "/phenotype/onset", "auxiliary_computation"))
    if c["phenotype"]["score"] is None:
        pending.append(_reference("phenotype_annotations_unavailable", ref + "/phenotype", "unknown"))
    for i, _ in enumerate(c["clinvar"]):
        support.append(_reference("variant_disease_assertion", f"{ref}/clinvar/{i}", "database_assertion"))
    for i, _ in enumerate(c["clinvar_info"]):
        pending.append(_reference("clinvar_not_used_for_ranking", f"{ref}/clinvar_info/{i}", "database_assertion"))
    for i, _ in enumerate(c["g2p_evidence"]):
        support.append(_reference("g2p_gene_disease_association", f"{ref}/g2p_evidence/{i}", "disease_level_evidence"))
    mol = c["molecular_assessment"]
    pending.append(_reference("variant_mechanism_requires_confirmation", ref + "/molecular_assessment", mol["status"]))
    if mol["status"] == "conflicting":
        oppose.append(_reference("molecular_input_conflict", ref + "/molecular_assessment", "conflicting"))
    for i, route in enumerate(mol["paths"]):
        for j, v in enumerate(route["variant_assessments"]):
            if v["status"] == "prediction_tension":
                oppose.append(_reference("predicted_mechanism_tension",
                    f"{ref}/molecular_assessment/paths/{i}/variant_assessments/{j}", "prediction"))
    if c["excluded"]:
        oppose.append(_reference("existing_exclusion", ref + "/exclusion_reasons", "existing_decision"))
    alternatives = {a["id"] for a in primary["alternatives"]}
    role = "primary" if c["key"] == primary["id"] else "alternative" if c["key"] in alternatives else "retained"
    return {"id": c["key"], "name": c["label"], "gene": c["gene"],
            "selection_role": "not_supported" if c["excluded"] else role,
            "supporting_evidence": support, "opposing_evidence": oppose,
            "pending_information": pending, "record": deepcopy(c)}


def build_layers(case: dict, step1: dict | None, out: dict) -> dict:
    """Assemble only supplied facts/results, preserving unknowns and all candidates."""
    facts = out["patient_facts"]
    native = "clinical" in facts
    clinical = deepcopy(facts["clinical"]) if native else None
    reported = [deepcopy(item) for item in clinical["items"]
                if item["kind"] == "diagnosis" and item["scope"] == "patient"] if native else []
    candidates = [_candidate(c, f"#/L3/candidates/{i}", out["primary"])
                  for i, c in enumerate(out["candidates"])]
    excluded = [_candidate(c, f"#/L3/not_supported/{i}", out["primary"])
                for i, c in enumerate(out["not_supported"])]
    # Existing broad/group terms only. Do not invent a category from a gene,
    # label substring or primary ranking; no ontology fetch or new inference.
    groups = [{"id": c["key"], "name": c["label"], "status": "candidate", "ref": f"#/L3/candidates/{i}/record"}
              for i, c in enumerate(out["candidates"])
              if c["grouping"] or c["merge"].get("narrower_competing")]
    return {
        "schema_version": "step2-l1-l4-v1",
        "case_id": case["id"],
        "reference_root": "this layers object; external Step 1 pointers identify their source case",
        "L1": {
            "source_text": case["patient"]["clinical_context"],
            "clinical": clinical,
            "clinical_coverage": "native_four_state" if native else "legacy_scope_and_four_state_not_available",
            "saved_patient_facts": deepcopy(facts),
            "saved_phenotypes": deepcopy(out["phenotypes"]),
            "extraction_provenance": deepcopy(out["phenotype_extraction"]),
            "reported_genotype": deepcopy(case["patient"]["genotype"]),
            "step1_result": deepcopy(step1),
            "molecular_evidence": deepcopy(out["molecular_evidence"]),
            "evidence_boundary": "clinical facts are reported with their original status/scope; sequence checks are not proof of pathogenicity; legacy scope remains unknown",
        },
        "L2": {
            "disease_category": {"status": "unknown", "established": None,
                                 "recorded_group_candidates": groups,
                                 "reason": "no independently established broad disease category in the existing output; group candidates are not confirmed patient diagnoses"},
            "reported_diagnoses": reported,
            "reported_diagnosis_status": "documented" if any(d["status"] == "present" for d in reported) else "unknown",
            "source_diagnosis_mentions": deepcopy(out["explicit_diagnosis"]),
            "diagnostic_resolution": deepcopy(out["primary"]),
            "resolution_kind": "existing_step2_decision_not_new_clinical_confirmation",
        },
        "L3": {
            "candidates": candidates,
            "not_supported": excluded,
            "interpretation": "all eligible candidates are retained, including those outside primary.alternatives; negative evidence is not automatic exclusion; missing evidence is unknown, not negative",
        },
        "L4": {
            "patient_mechanism": {"status": "unknown", "reason": "existing Step 1 supplies hypotheses, not patient functional confirmation"},
            "variant_predictions": [{"variant": {k: v[k] for k in ("gene", "transcript", "variant_cdna")},
                                     "evidence_kind": "prediction", "ref": f"#/L1/molecular_evidence/{i}",
                                     "step1_status": v["status"],
                                     "nmd": deepcopy(v["nmd"]) if v["from_step1"] else None,
                                     "mechanism_hypothesis": deepcopy(v["mechanism_hypothesis"]) if v["from_step1"] else None,
                                     "pathogenicity_prediction": deepcopy(v["pathogenicity_prediction"]) if v["from_step1"] else None}
                                    for i, v in enumerate(out["molecular_evidence"])],
            "g2p_records": deepcopy(out["g2p_records"]),
            "candidate_mechanisms": [{"id": c["id"], "name": c["name"], "selection_role": c["selection_role"],
                                      "assessment": deepcopy(c["record"]["molecular_assessment"]),
                                      "orphanet_hints": deepcopy(c["record"]["orphanet_mechanism_hint"]),
                                      "ref": f"#/L3/{name}/{i}/record"}
                                     for name, group in (("candidates", candidates), ("not_supported", excluded))
                                     for i, c in enumerate(group)],
            "evidence_boundary": "G2P and Orphanet describe disease-level mechanisms; inferred and predicted evidence is not confirmation of this patient's variant mechanism",
        },
        "sources_manifest": deepcopy(out["sources_manifest"]),
        "evidence": deepcopy(out["evidence"]),
    }

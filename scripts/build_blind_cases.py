"""Turn out/blind/<batch>/sample.json into a case file the pipeline can run. Deterministic, no LLM.

Usage: python scripts/build_blind_cases.py --batch 20261108

Group A keeps the Phase 1 Validator cases as they are (their own clinical context and their own question).
Group B1 takes its clinical description verbatim from the GeneReviews chapter's Clinical Characteristics; group
B2's description is built from the HPO phenotypes the draw chose and is marked synthetic. Every caveat the
review asked for travels with the case, so it reaches the judging table (2026-11-09).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VALIDATION = ROOT / "data" / "cases" / "validation" / "phase1_hf_unseen_genes.json"

CAVEATS = {
    "THRA": "HPO carries no frequency annotation for this disease, so the description fell back to HPO id order: "
            "low confidence. Also check whether step 2 calls this ambiguous or low-confidence rather than "
            "picking one disease outright (review request 2026-11-09).",
    "PSMD12": "every chosen phenotype is Very frequent but counted in very few patients (1/1, 5/5, 7/7): the "
              "frequency band rests on small denominators (review note 2026-11-09).",
}


def chapter_phenotypes(nbk: str) -> tuple[str, str]:
    """(verbatim sentence(s), section) from the chapter's Clinical Characteristics, or ("", reason).

    A gene-family Overview chapter titles the section "Clinical Characteristics of <disease>", not plain
    "Clinical Characteristics", so the match is by prefix (2026-11-09: four of the five B1 genes turned out to
    be covered by an Overview chapter).
    """
    from aitx.evidence import genereviews as GR
    titles = [t for t in GR.sections(nbk) if t.startswith("Clinical Characteristics")]
    # the deepest-named section first would be a sub-section; take the top-level one, then its first sub-section
    titles.sort(key=lambda t: (t.count("/"), len(t)))
    for title in titles:
        text = GR.section_text(nbk, title)
        if not text:
            continue
        body = re.sub(r"\s+", " ", text).strip()
        sentences = re.split(r"(?<=[.!?])\s+", body)
        keep = [s for s in sentences if len(s) > 40][:3]
        if keep:
            return " ".join(keep)[:900], title
    return "", f"no Clinical Characteristics text in the local archive for {nbk}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="20261108")
    args = ap.parse_args()
    d = ROOT / "out" / "blind" / args.batch
    sample = json.loads((d / "sample.json").read_text())
    cases, notes = [], []

    for c in json.loads(VALIDATION.read_text()):
        cases.append({**c, "blind": {"group": "A", "source": "Phase 1 Validator case, used as given",
                                     "description_source": "official"}})

    for case in sample["cases"]:
        g, v = case["gene"], case["variant"]
        cid = f"BLIND-{g}"
        patient = {"genotype": [{"gene": g, "transcript": v["transcript"], "variant_cdna": v["variant_cdna"],
                                 "variant_protein": v["variant_protein"], "zygosity": case["zygosity"]}]}
        blind = {"group": case["group"], "gencc": case["gencc"], "clinvar": v["accession"],
                 "zygosity_rule": "from the GenCC mode of inheritance"}
        if case["group"] == "B1":
            text, where = chapter_phenotypes(case["chapters"][0])
            patient["clinical_description"] = text
            blind.update(description_source="genereviews_verbatim", description_from=where,
                         chapters=case["chapters"])
            if not text:
                notes.append(f"{cid}: no chapter text found ({where}); the case has no clinical description")
        else:
            ph = case["phenotypes"]
            patient["clinical_description"] = ph["description"]
            blind.update(description_source="synthetic_from_hpo", description_rule=ph["rule"],
                         phenotypes=[{k: p.get(k) for k in ("hpo_id", "label", "frequency_raw", "frequency_band",
                                                            "why", "counted_in")} for p in ph["chosen"]])
        if g in CAVEATS:
            blind["caveat"] = CAVEATS[g]
            notes.append(f"{cid}: {CAVEATS[g]}")
        cases.append({"id": cid, "patient": patient, "blind": blind})

    out = ROOT / "data" / "cases" / "blind" / f"{args.batch}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cases, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(cases)} cases -> {out.relative_to(ROOT)}")
    for c in cases:
        b = c["blind"]
        desc = (c["patient"].get("clinical_description") or c["patient"].get("clinical_context") or "")
        print(f"  {b['group']} {c['id']:<16} {b['description_source']:<24} {desc[:84]}")
    if notes:
        print("\nnotes carried into the judging table:")
        for n in notes:
            print(f"  - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

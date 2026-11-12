"""Draw and build the retest cases (fix-phase retest, user decision 2026-11-12). Deterministic, no LLM.

Usage:
    python3 scripts/sample_retest_cases.py --dry      # show the draw, write nothing
    python3 scripts/sample_retest_cases.py            # write out/blind/<batch>/sample.json and data/cases/blind/<batch>.json

Rules (fixed here, reproducible from this file plus the dated dataset snapshots in .cache/datasets):
  - seed RETEST_SEED (new; the blind batch 20261108 used "blind-2026-11-08");
  - four cases: one gene with its own single-gene GeneReviews chapter (L1), one gene covered only by a multi-gene
    overview (L2), two genes with no GeneReviews chapter (B2); pools and the L1 / L2 label as in
    scripts/sample_blind_cases.py (GenCC Definitive with an OMIM disease; chapter title rule of the pipeline);
  - excluded: the evaluation genes, the practice genes, the validator genes and every gene of an earlier blind batch;
  - variant and zygosity as in the blind batch (lowest-VCV Pathogenic coding variant; zygosity from GenCC MOI);
  - description: L1 verbatim from its own chapter's "Suggestive Findings" (the chapter's specific manifestations,
    so step 2 has phenotypes to read - the blind batch's B1 cases took the first sentences of Clinical
    Characteristics, which for an overview names only the disease group); L2 and B2 synthesized from the disease's
    HPO annotations (same rule as blind B2) and marked synthetic, because an overview has no gene-specific text.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import sample_blind_cases as S  # noqa: E402
from aitx import runmeta  # noqa: E402

RETEST_SEED = "retest-2026-11-12"
WANT = {"B1-L1": 1, "B1-L2": 1, "B2": 2}
# adjustments before any run (user, 2026-11-12; not tuning - nothing had been run):
#  - the L1 description keeps only the later-onset (classic childhood) form when the findings are listed per form;
#  - the L2 overview must not be one an earlier blind case used (MERTK's NBK1417 was SNRNP200's);
#  - at least two of the four are autosomal dominant heterozygous, as three of the four evaluation cases are:
#    the L2 case must be AD, and of the two B2 cases one is the first gene in seeded order (any inheritance) and
#    the other the first AD gene in seeded order.
AD = "Autosomal dominant"
LATE_FORM = re.compile(r"(Later-onset|Late-onset|Classic[a-z ]*|Childhood[a-z -]*) form:", re.I)
FORM_END = re.compile(r"\b(Laboratory findings|MRI findings|Imaging findings|Neuroimaging|[A-Z][a-z/ -]{2,30} form:)")
DESCRIPTION_FIELD = "clinical_context"


def earlier_blind_genes() -> dict[str, str]:
    out = {}
    for f in sorted((ROOT / "data" / "cases" / "blind").glob("*.json")):
        if f.stem.startswith("retest-"):
            continue
        for c in json.loads(f.read_text()):
            for v in c["patient"]["genotype"]:
                out[v["gene"]] = f"used in blind batch {f.stem}"
    return out


def suggestive_findings(nbk: str) -> tuple[str, str]:
    """(verbatim text, section) of the chapter's Suggestive Findings, the specific manifestations it lists."""
    from aitx.evidence import genereviews as GR
    titles = sorted((t for t in GR.sections(nbk) if "Suggestive Findings" in t), key=lambda t: (t.count("/"), len(t)))
    for t in titles:
        text = re.sub(r"\s+", " ", GR.section_text(nbk, t) or "").strip()
        m = LATE_FORM.search(text)
        if m:                                        # findings listed per form: the later-onset form only
            rest = text[m.start():]
            end = FORM_END.search(rest, len(m.group(0)))
            text = rest[:end.start()].strip() if end else rest
        if len(text) > 60:
            if len(text) > 900:                      # cut at the last sentence end, never mid-word
                cut = max(text.rfind(". ", 0, 900), text.rfind(" ", 0, 900))
                text = text[:cut + 1].strip()
            return text, t
    return "", f"no Suggestive Findings text for {nbk}"


def earlier_chapters() -> set[str]:
    out = set()
    for f in sorted((ROOT / "data" / "cases" / "blind").glob("*.json")):
        if not f.stem.startswith("retest-"):
            out |= {n for c in json.loads(f.read_text()) for n in (c.get("blind") or {}).get("chapters") or []}
    return out


def draw() -> list[dict]:
    p = S.pools()
    excluded = {**S.EXCLUDED, **earlier_blind_genes()}
    counts = S.index_gene_counts()
    names = S.hpo_names()
    taken = {k: 0 for k in WANT}
    used_chapters = earlier_chapters()
    b2_ad = False
    cases, skipped = [], []
    for group, pool in (("B1", p["b1"]), ("B2", p["b2"])):
        order = random.Random(RETEST_SEED).sample(pool, len(pool))
        for g in order:
            if g in excluded:
                continue
            chapters = p["chapters"].get(g, [])
            kinds = [S.chapter_kind(n, counts.get(n, 0)) for n in chapters]
            sub = S.subgroup_of(kinds) if group == "B1" else "B2"
            if taken[sub] >= WANT[sub]:
                continue
            rec = next(r for r in p["definitive"][g] if r.get("omim"))
            if sub == "B1-L2" and (rec["moi"] != AD or set(chapters) & used_chapters):
                continue
            if sub == "B2" and taken["B2"] == 1 and not b2_ad and rec["moi"] != AD:
                continue                              # the second B2 case must be AD unless the first already is
            v = S.clinvar_variant(g)
            if v is None:
                skipped.append({"gene": g, "subgroup": sub, "why": "no Pathogenic coding variant with transcript and c."})
                continue
            case = {"subgroup": sub, "gene": g, "gencc": rec, "chapters": chapters, "chapter_kinds": kinds,
                    "variant": v, "zygosity": S.zygosity_for(rec["moi"])}
            if sub == "B1-L1":
                own = next(k["nbk"] for k in kinds if k["kind"] == "chapter")
                text, where = suggestive_findings(own)
                case.update(description=text, description_source="genereviews_verbatim", description_from=where)
            else:
                ph = S.phenotypes_for(rec["omim"], names)
                case.update(description=ph["description"], description_source="synthetic_from_hpo",
                            description_rule=ph["rule"], phenotypes=ph["chosen"])
            if not case["description"]:
                skipped.append({"gene": g, "subgroup": sub, "why": "no description could be built"})
                continue
            taken[sub] += 1
            b2_ad |= sub == "B2" and rec["moi"] == AD
            cases.append(case)
            if all(taken[k] >= WANT[k] for k in WANT if k.startswith(group)):
                break
    return cases, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--batch", default="retest-20261112")
    args = ap.parse_args()
    cases, skipped = draw()
    for c in cases:
        v = c["variant"]
        print(f"\n{c['subgroup']:<6} {c['gene']:<10} {c['gencc']['omim']} {c['gencc']['disease_title']}  ({c['gencc']['moi']})")
        print(f"       chapters: {[(k['nbk'], k['kind'], k['title']) for k in c['chapter_kinds']] or '-'}")
        print(f"       variant: {v['transcript']} {v['variant_cdna']} {v['variant_protein']} [{v['accession']}] "
              f"{c['zygosity']}")
        print(f"       description ({c['description_source']}): {c['description']}")
    for s in skipped:
        print(f"skipped {s}")
    if args.dry:
        return 0
    d = ROOT / "out" / "blind" / args.batch
    d.mkdir(parents=True, exist_ok=True)
    (d / "sample.json").write_text(json.dumps({"schema": "retest-sample-v1", "batch": args.batch, "seed": RETEST_SEED,
                                               "drawn_at": int(time.time()), "code_commit": runmeta.code_commit(),
                                               "want": WANT, "rules": {
        "seed": RETEST_SEED, "L1": "first gene in seeded order with its own single-gene chapter; description verbatim "
        "from that chapter's Suggestive Findings, later-onset (classic childhood) form only when listed per form",
        "L2": "first autosomal dominant gene in seeded order covered only by an overview not used by an earlier blind "
        "case; description synthesized from HPO", "B2": "the first gene in seeded order and the first autosomal dominant "
        "gene in seeded order (one gene if the first is AD, then the next); descriptions synthesized from HPO",
        "excluded": "evaluation, practice and validator genes, and every gene of an earlier blind batch",
        "adjusted": "2026-11-12, before any run, by the user: EIF2B1 later-onset form only; MERTK replaced (overview "
        "NBK1417 used by SNRNP200); at least two AD heterozygous cases (three of the four evaluation cases are)"},
        "cases": cases, "skipped": skipped}, indent=1,
                                              ensure_ascii=False))
    out = []
    for c in cases:
        v = c["variant"]
        out.append({"id": f"RETEST-{c['gene']}", "patient": {
            "genotype": [{"gene": c["gene"], "transcript": v["transcript"], "variant_cdna": v["variant_cdna"],
                          "variant_protein": v["variant_protein"], "zygosity": c["zygosity"]}],
            DESCRIPTION_FIELD: c["description"]},
            "blind": {"group": c["subgroup"], "gencc": c["gencc"], "clinvar": v["accession"],
                      "description_source": c["description_source"],
                      **({"description_from": c["description_from"]} if "description_from" in c else
                         {"description_rule": c["description_rule"]}),
                      "chapters": c["chapters"]}})
    f = ROOT / "data" / "cases" / "blind" / f"{args.batch}.json"
    f.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"\n{len(out)} cases -> {f.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

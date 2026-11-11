"""Draw the blind-test cases (docs/blind_test_plan.md). Deterministic, no LLM.

Usage:
    python scripts/sample_blind_cases.py --pools-only      # show the candidate pools and the drawn genes
    python scripts/sample_blind_cases.py                   # also look up a variant and build the cases

Everything that decides the draw is fixed in this file: the seed, the exclusion list, the pool rules, the
variant rule and the description rule. The draw is reproducible from this script plus the dated dataset
snapshots in .cache/datasets, and the result is written to out/blind/<batch>/sample.json together with the
code fingerprint and git commit at the time, so the freeze can be checked afterwards.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx import http, runmeta  # noqa: E402

SEED = "blind-2026-11-08"
N_PER_SUBGROUP = 5
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Genes that may never appear in a blind-test or tuning case.
EVAL_GENES = ["ACTL6B", "ITPR1", "SPTLC1", "SYT1"]          # the four evaluation cases' genes (permanent)
PRACTICE_GENES = ["AGXT", "ANO10", "CFTR", "COL1A1", "DMD", "GRIN2B", "KMT2B", "NF1", "OTC", "SLC35A2"]
VALIDATOR_GENES = ["DDC", "KCNT1"]                           # group A, used on their own terms
EXCLUDED = {
    **{g: "evaluation case gene: permanently excluded from every blind-test and tuning case set" for g in EVAL_GENES},
    **{g: "practice case gene: the pipeline was tuned on it" for g in PRACTICE_GENES},
    **{g: "Phase 1 Validator gene: used as group A" for g in VALIDATOR_GENES},
}

# HPO frequency terms, most frequent first. Group B2 takes Very frequent and Frequent only, and goes further
# down this list only to reach two phenotypes (decision 2026-11-08).
# The hpoa frequency column carries either one of these terms or a ratio ("26/27") or a percentage ("50%"),
# so both encodings are read and put on the same scale. The percentages are HPO's own band definitions.
FREQ_TERMS = {"HP:0040280": ("Obligate", 1.00), "HP:0040281": ("Very frequent", 0.895),
              "HP:0040282": ("Frequent", 0.545), "HP:0040283": ("Occasional", 0.17),
              "HP:0040284": ("Very rare", 0.025), "HP:0040285": ("Excluded", 0.0)}
BANDS = [(0.80, "Very frequent"), (0.30, "Frequent"), (0.05, "Occasional"), (0.0, "Very rare")]
PREFERRED_BANDS = {"Obligate", "Very frequent", "Frequent"}
MIN_PHENOTYPES, MAX_PHENOTYPES = 2, 4


def frequency(raw: str) -> tuple[float | None, str]:
    """(value in 0..1, band name) for one frequency cell, or (None, "not stated")."""
    raw = (raw or "").strip()
    if raw in FREQ_TERMS:
        label, value = FREQ_TERMS[raw]
        return value, label
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", raw)
    if m and int(m.group(2)):
        value = int(m.group(1)) / int(m.group(2))
    elif re.fullmatch(r"\d+(\.\d+)?\s*%", raw):
        value = float(raw.rstrip("% ")) / 100
    else:
        return None, "not stated"
    return value, next(name for cut, name in BANDS if value >= cut)


def newest(dataset: str) -> Path:
    d = ROOT / ".cache" / "datasets" / dataset
    return sorted(d.iterdir())[-1]


def genereviews_genes() -> dict[str, list[str]]:
    """gene symbol -> NBK ids of its chapters (local archive)."""
    out: dict[str, list[str]] = defaultdict(list)
    for line in (newest("genereviews") / "genereviews.txt").read_text().splitlines():
        parts = line.split("|")
        if len(parts) >= 3 and parts[2]:
            out[parts[2].strip()].append(parts[1].strip())
    return out


def index_gene_counts() -> dict[str, int]:
    """NBK id -> how many genes the archive index lists for it."""
    out: dict[str, int] = defaultdict(int)
    for line in (newest("genereviews") / "genereviews.txt").read_text().splitlines():
        parts = line.split("|")
        if len(parts) >= 3 and parts[2]:
            out[parts[1].strip()] += 1
    return out


def chapter_kind(nbk: str, n_genes: int, title_of=None) -> dict:
    """Single-gene chapter (L1) or multi-gene overview (L2), by the pipeline's own rule (decision 2026-11-11).

    The pipeline (`fallback.is_overview`) calls a chapter an overview when its title says "Overview"; the archive
    index drops that word from the titles, so the title is read from the local chapter. Only when the chapter is not
    available locally does the index's gene count decide (more than one gene -> overview), and the record says so.
    """
    if title_of is None:
        from aitx.evidence import fallback as F
        title_of = F.GR_title
    title = title_of(nbk)
    if title:
        return {"nbk": nbk, "kind": "overview" if "overview" in title.lower() else "chapter", "title": title,
                "n_genes": n_genes, "rule": "chapter title (pipeline rule)"}
    return {"nbk": nbk, "kind": "overview" if n_genes > 1 else "chapter", "title": None, "n_genes": n_genes,
            "rule": "archive index gene count (chapter not available locally)"}


def subgroup_of(kinds: list[dict]) -> str:
    """B1-L1 when the gene has at least one single-gene chapter (the pipeline uses it and ignores overviews);
    B1-L2 when it is listed only in overviews (the pipeline falls back to disease-group advice)."""
    return "B1-L1" if any(k["kind"] == "chapter" for k in kinds) else "B1-L2"


SUBGROUP_LABEL = {"B1-L1": "有专章 L1", "B1-L2": "只有总论 L2", "B2": "无章节", "A": "Validator"}


def regroup(batch: str, title_of=None) -> dict:
    """Label an existing draw's B1 cases L1 / L2 without redrawing (decision 2026-11-11). The genes, variants and
    descriptions are untouched; the labels and the reason are added to sample.json and the change is logged."""
    p = ROOT / "out" / "blind" / batch / "sample.json"
    sample = json.loads(p.read_text())
    counts = index_gene_counts()
    for c in sample.get("cases") or []:
        if c["group"] == "B1":
            c["chapter_kinds"] = [chapter_kind(n, counts.get(n, 0), title_of) for n in c["chapters"]]
            c["subgroup"] = subgroup_of(c["chapter_kinds"])
        else:
            c["subgroup"] = c["group"]
    sample.setdefault("regrouped", []).append({
        "at": int(time.time()),
        "why": "B1 was drawn as 'listed in any GeneReviews chapter', which counts multi-gene overviews; the plan meant "
               "a chapter on the disease. Not redrawn: B1 is split into L1 (single-gene chapter) and L2 (overview "
               "only) and reported in separate columns next to B2 (decision 2026-11-11)",
        "subgroups": {c["gene"]: c["subgroup"] for c in sample.get("cases") or []}})
    p.write_text(json.dumps(sample, indent=1, ensure_ascii=False))
    return sample


def gencc_definitive() -> dict[str, list[dict]]:
    """gene symbol -> its Definitive GenCC records (disease curie, title, mode of inheritance)."""
    out: dict[str, list[dict]] = defaultdict(list)
    with (newest("gencc") / "gencc-submissions.tsv").open() as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if (row.get("classification_title") or "").strip() != "Definitive":
                continue
            g = (row.get("gene_symbol") or "").strip()
            if not g:
                continue
            out[g].append({"disease": (row.get("disease_curie") or "").strip(),
                           "disease_title": (row.get("disease_title") or "").strip(),
                           "moi": (row.get("moi_title") or "").strip(),
                           "submitter": (row.get("submitter_title") or "").strip()})
    return out


def mondo_to_omim() -> dict[str, str]:
    """MONDO id -> OMIM id from the pinned SSSOM snapshot (GenCC records diseases as MONDO while the HPO
    annotations are keyed by OMIM, so the two have to be joined).

    Read straight from the snapshot on disk, with the same rule the pipeline's loader uses (exact matches
    only). The pipeline's `ensure_all()` may re-download a dataset, and a dataset that changes mid-draw changes
    the draw: between two runs on 2026-11-08 the B2 pool went from 1020 to 1021 genes and two of the five drawn
    genes changed. A blind-test draw has to be reproducible, so nothing is downloaded here.
    """
    out: dict[str, str] = {}
    with (newest("mondo_sssom") / "mondo.sssom.tsv").open() as f:
        header = None
        for row in csv.reader(f, delimiter="\t"):
            if not row or row[0].startswith("#"):
                continue
            if header is None:
                header = {k: i for i, k in enumerate(row)}
                continue
            if len(row) <= header["object_id"] or row[header["predicate_id"]] != "skos:exactMatch":
                continue
            subject, obj = row[header["subject_id"]], row[header["object_id"]]
            if obj.startswith("OMIM:"):
                out.setdefault(subject, obj)
    return out


def pools() -> dict:
    """The two candidate pools, each sorted by gene symbol so the source order cannot affect the draw.

    A gene qualifies only when its Definitive GenCC disease maps to an OMIM id: group B2's description is built
    from the HPO annotations, which are keyed by OMIM, so without that mapping there is nothing to build from.
    """
    chapters, definitive = genereviews_genes(), gencc_definitive()
    to_omim = mondo_to_omim()
    for recs in definitive.values():
        for r in recs:
            r["omim"] = to_omim.get(r["disease"], "")
    with_omim = {g for g, recs in definitive.items() if any(r["omim"] for r in recs)}
    b1 = sorted(g for g in definitive if g in chapters and g in with_omim and g not in EXCLUDED)
    b2 = sorted(g for g in definitive if g not in chapters and g in with_omim and g not in EXCLUDED)
    return {"b1": b1, "b2": b2, "chapters": chapters, "definitive": definitive}


def order_of(pool: list[str]) -> list[str]:
    """The whole pool in one seeded order. Genes are taken from the front; one that yields no eligible variant
    is skipped and the next is taken (plan rule 4), which keeps the draw reproducible either way."""
    return random.Random(SEED).sample(pool, len(pool))


def draw(pool: list[str], n: int = N_PER_SUBGROUP) -> list[str]:
    return sorted(order_of(pool)[:n])


# ------------------------------------------------------------------ variant (ClinVar, rule fixed)

_TITLE = re.compile(r"^(?P<tx>N[MR]_\d+\.\d+)\((?P<gene>[^)]+)\):(?P<c>c\.[^ ]+)(?:\s+\((?P<p>p\.[^)]+)\))?")


def clinvar_variant(gene: str, use_cache: bool = True) -> dict | None:
    """The gene's Pathogenic coding variant with the lowest ClinVar accession number.

    "Earliest submitted" is operationalised as the lowest VCV accession: ClinVar hands those out in order, and
    it is a value anyone can re-read from the record, unlike a submission date that varies by submitter.
    """
    # any Pathogenic variant whose title gives a transcript and a c. change: restricting this to missense left
    # PSMD12 with no variant at all (2026-11-08), and the step 1 profile handles every class we may get back
    q = f"{gene}[gene] AND \"clinsig pathogenic\"[Properties]"
    import urllib.parse
    url = f"{EUTILS}/esearch.fcgi?db=clinvar&retmode=json&retmax=200&term={urllib.parse.quote(q)}"
    ids = json.loads(http.get(url, use_cache=use_cache, timeout=60).text)["esearchresult"].get("idlist") or []
    if not ids:
        return None
    s = json.loads(http.get(f"{EUTILS}/esummary.fcgi?db=clinvar&retmode=json&id={','.join(ids[:200])}",
                            use_cache=use_cache, timeout=60).text)["result"]
    best = None
    for uid in s.get("uids", []):
        rec = s[uid]
        acc = rec.get("accession", "")
        m = _TITLE.match(rec.get("title", ""))
        if not m or not acc.startswith("VCV"):
            continue
        # coding region only (the plan says so, and step 1 reads a protein consequence): a c. position carrying
        # an intron offset is skipped, e.g. CTDP1 c.863+389C>T, which was the lowest accession for that gene
        if re.search(r"c\.[-*]?\d+[+-]\d+", m.group("c")):
            continue
        num = int(re.sub(r"\D", "", acc) or 0)
        if best is None or num < best["accession_number"]:
            best = {"accession": acc, "accession_number": num, "title": rec.get("title"),
                    "transcript": m.group("tx"), "variant_cdna": m.group("c"),
                    "variant_protein": m.group("p") or "", "gene": m.group("gene"),
                    "germline_classification": (rec.get("germline_classification") or {}).get("description")}
    return best


def zygosity_for(moi: str) -> str:
    """Fixed rule: the mode of inheritance GenCC records decides it, so no judgement is involved."""
    m = (moi or "").lower()
    if "x-linked" in m:
        return "hemizygous"
    if "autosomal recessive" in m:
        return "homozygous"
    return "heterozygous"


# ------------------------------------------------------------------ description (group B2 only)

def hpo_names() -> dict[str, str]:
    """HPO id -> name, from the local ontology snapshot."""
    import gzip
    d = newest("hpo_ontology")
    f = next((p for p in d.iterdir() if p.suffix in (".json", ".gz") or p.name.endswith(".obo")), None)
    if f is None:
        return {}
    text = gzip.open(f, "rt").read() if f.suffix == ".gz" else f.read_text()
    if f.suffix == ".json" or text.lstrip().startswith("{"):
        data = json.loads(text)
        nodes = data.get("graphs", [{}])[0].get("nodes", []) if "graphs" in data else data.get("nodes", [])
        return {n["id"].split("/")[-1].replace("_", ":"): n.get("lbl") or n.get("label", "")
                for n in nodes if n.get("id")}
    out = {}
    tid = None
    for line in text.splitlines():
        if line.startswith("id: HP:"):
            tid = line[4:].strip()
        elif line.startswith("name:") and tid:
            out[tid] = line[5:].strip()
            tid = None
    return out


def phenotypes_for(disease: str, names: dict[str, str]) -> dict:
    """The phenotypes a synthetic description may use, and why each was taken (decision 2026-11-08):
    Very frequent / Frequent (and Obligate) only, most frequent first; go further down only to reach two;
    at most four. Ratios and percentages are converted, so a disease annotated "26/27" is not treated as
    having no frequency at all."""
    rows = []
    with (newest("hpo_annotations") / "phenotype.hpoa").open() as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) < 11 or p[0] != disease or p[10] != "P" or p[2] == "NOT":
                continue
            value, band = frequency(p[7])
            rows.append({"hpo_id": p[3], "frequency_raw": p[7], "frequency_value": value,
                         "frequency_band": band, "reference": p[4]})
    # most frequent first; among equal frequencies the one counted in more patients first ("44/51" before
    # "1/1", which the data also calls Very frequent); an unstated frequency sorts last; the HPO id only breaks
    # remaining ties, so the order is fixed
    def denominator(r):
        m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", (r["frequency_raw"] or "").strip())
        return int(m.group(2)) if m else 0

    rows.sort(key=lambda r: (-(r["frequency_value"] if r["frequency_value"] is not None else -1),
                             -denominator(r), r["hpo_id"]))
    preferred = [r for r in rows if r["frequency_band"] in PREFERRED_BANDS]
    chosen = [{**r, "why": f"{r['frequency_band']} ({r['frequency_raw'] or 'term'})"}
              for r in preferred[:MAX_PHENOTYPES]]
    if len(chosen) < MIN_PHENOTYPES:
        for r in [x for x in rows if x not in preferred][:MIN_PHENOTYPES - len(chosen)]:
            chosen.append({**r, "why": f"taken to reach the minimum of {MIN_PHENOTYPES}; "
                                       f"{r['frequency_band']} ({r['frequency_raw'] or 'none stated'})"})
    for c in chosen:
        c["label"] = names.get(c["hpo_id"], c["hpo_id"])
        c["counted_in"] = denominator(c) or None
    return {"chosen": chosen, "n_annotations": len(rows), "n_preferred": len(preferred),
            "description": "; ".join(c["label"] for c in chosen if c.get("label")),
            "rule": f"Obligate / Very frequent / Frequent only (terms, ratios and percentages on one scale), "
                    f"most frequent first, down the list only to reach {MIN_PHENOTYPES}, at most "
                    f"{MAX_PHENOTYPES}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools-only", action="store_true", help="show the pools and the drawn genes, fetch nothing")
    ap.add_argument("--batch", default=time.strftime("%Y%m%d"))
    ap.add_argument("--regroup", action="store_true",
                    help="label an existing batch's B1 cases L1 / L2 in its sample.json; draws nothing")
    args = ap.parse_args()
    if args.regroup:
        s = regroup(args.batch)
        for c in s.get("cases") or []:
            kinds = ", ".join(f"{k['nbk']} {k['kind']} ({k['n_genes']} genes)" for k in c.get("chapter_kinds", []))
            print(f"{c['subgroup']:<6} {c['gene']:<10} {kinds}")
        return 0
    p = pools()
    b1, b2 = draw(p["b1"]), draw(p["b2"])
    print(f"seed {SEED!r}; excluded {len(EXCLUDED)} genes "
          f"({len(EVAL_GENES)} evaluation, {len(PRACTICE_GENES)} practice, {len(VALIDATOR_GENES)} validator)")
    print(f"B1 pool (GenCC Definitive with an OMIM disease AND listed in a GeneReviews chapter or overview; "
          f"drawn cases are labelled L1 single-gene chapter / L2 overview only): {len(p['b1'])} genes")
    print(f"   drawn: {b1}")
    print(f"B2 pool (GenCC Definitive with an OMIM disease, no GeneReviews chapter): {len(p['b2'])} genes")
    print(f"   drawn: {b2}")
    out = {"schema": "blind-sample-v1", "batch": args.batch, "seed": SEED, "drawn_at": int(time.time()),
           "code_fingerprint": runmeta.code_fingerprint(), "code_commit": runmeta.code_commit(),
           "excluded_genes": EXCLUDED, "pool_sizes": {"b1": len(p["b1"]), "b2": len(p["b2"])},
           "dataset_snapshots": {d: newest(d).name for d in ("genereviews", "gencc", "mondo_sssom",
                                                             "hpo_annotations", "hpo_ontology")},
           "drawn_first_five": {"b1": b1, "b2": b2}, "group_a": VALIDATOR_GENES,
           "rules": {"seed": SEED, "variant": "the Pathogenic ClinVar variant with the lowest VCV accession "
                                              "whose title gives a transcript and a coding c. change",
                     "zygosity": "from the GenCC mode of inheritance",
                     "skip": "a gene with no eligible variant is skipped and the next gene in the seeded order "
                             "is taken; every skip is recorded"}}
    if not args.pools_only:
        names, counts = hpo_names(), index_gene_counts()
        out["cases"], out["skipped"] = [], []
        for group, pool in (("B1", p["b1"]), ("B2", p["b2"])):
            taken = 0
            for g in order_of(pool):
                if taken >= N_PER_SUBGROUP:
                    break
                rec = next(r for r in p["definitive"][g] if r.get("omim"))
                v = clinvar_variant(g)
                if v is None:
                    why = "no Pathogenic coding variant in ClinVar whose title gives a transcript and c. change"
                    out["skipped"].append({"group": group, "gene": g, "why": why})
                    print(f"{group} {g:<10} SKIPPED: {why}")
                    continue
                taken += 1
                case = {"group": group, "gene": g, "gencc": rec, "chapters": p["chapters"].get(g, []),
                        "variant": v, "zygosity": zygosity_for(rec["moi"])}
                if group == "B1":            # the draw itself is unchanged; L1 / L2 is reported (2026-11-11)
                    case["chapter_kinds"] = [chapter_kind(n, counts.get(n, 0)) for n in case["chapters"]]
                    case["subgroup"] = subgroup_of(case["chapter_kinds"])
                else:
                    case["subgroup"] = group
                if group == "B2":
                    case["phenotypes"] = phenotypes_for(rec["omim"], names)
                out["cases"].append(case)
                vt = f"{v['transcript']} {v['variant_cdna']} {v['variant_protein']}"
                print(f"\n{group} {g:<10} {rec['omim']} / {rec['disease']} {rec['disease_title'][:40]}")
                print(f"     moi {rec['moi']} -> {case['zygosity']}; chapters {case['chapters'] or '-'}")
                print(f"     variant {vt} [{v['accession']}]")
                if group == "B2":
                    ph = case["phenotypes"]
                    print(f"     description ({ph['n_preferred']} preferred of {ph['n_annotations']} annotations): "
                          f"{ph['description'] or '(none)'}")
                    for c in ph["chosen"]:
                        thin = "  <- counted in fewer than 3 patients" if (c.get("counted_in") or 9) < 3 else ""
                        print(f"       - {c['label']} ({c['hpo_id']}): {c['why']}{thin}")
    d = ROOT / "out" / "blind" / args.batch
    d.mkdir(parents=True, exist_ok=True)
    (d / "sample.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"\nwritten {(d / 'sample.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

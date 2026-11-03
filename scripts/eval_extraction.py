"""Symptom extraction test set: precision / recall of step-2 phenotype extraction.

Gold: data/eval/hpo_extraction_gold.json (practice + Phase 1 validator contexts only;
no evaluation case, no clean validation case). Every gold HPO id is first checked
against hp.json (exists, current, under Phenotypic abnormality); a bad id stops the run.

  precision = extracted terms matching a gold span / all extracted terms
  recall    = gold spans matched by an extracted term / all gold spans
A match needs the same status and an id in the span's "acceptable" list (strict).
Terms that hit a gold id's ancestor or descendant are listed as near misses.

Two sets: the basic set (hpo_extraction_gold.json) and the hard set (hpo_extraction_hard.json:
negation, colloquial phrasing, abbreviations, multi-sentence narratives; recall is also
reported per 'kind'). Each set is evaluated and reported on its own.

Usage:  python scripts/eval_extraction.py [--set basic|hard|all] [--fresh-llm]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx.disease import datasets as D  # noqa: E402
from aitx.disease import extract  # noqa: E402
from aitx.disease.hpo import Ontology  # noqa: E402

GOLD = ROOT / "data" / "eval" / "hpo_extraction_gold.json"
GOLD_HARD = ROOT / "data" / "eval" / "hpo_extraction_hard.json"
SETS = {"basic": GOLD, "hard": GOLD_HARD}


def load_ontology() -> Ontology:
    ont = Ontology(D.ensure("hpo_ontology"))
    for legacy in ("hpo_ontology_2022", "hpo_ontology_2024"):
        ont.add_former_names(D.ensure(legacy))
    return ont


def check_gold(gold: dict, ont: Ontology) -> list[str]:
    bad = []
    for c in gold["contexts"]:
        for a in c["annotations"]:
            if a["quote"] not in c["context"]:
                bad.append(f"{c['id']}: quote {a['quote']!r} not in context")
            for t in a["acceptable"]:
                cur, note = ont.resolve(t)
                if cur != t or not ont.is_phenotype(t):
                    bad.append(f"{c['id']}: {t} invalid ({note or 'not a phenotype term'})")
        for n in c["negatives"]:
            if n["quote"] not in c["context"]:
                bad.append(f"{c['id']}: negative {n['quote']!r} not in context")
    return bad


def evaluate(gold: dict, ont: Ontology, use_cache: bool = True) -> dict:
    tp_ext = n_ext = matched = n_gold = 0
    false_pos, misses, near = [], [], []
    for c in gold["contexts"]:
        ext = extract.extract(c["context"], ont, use_cache=use_cache)["phenotypes"]
        n_ext += len(ext)
        n_gold += len(c["annotations"])
        hit_gold = set()
        for e in ext:
            g = [i for i, a in enumerate(c["annotations"]) if a["status"] == e["status"] and e["hpo_id"] in a["acceptable"]]
            if g:
                tp_ext += 1
                hit_gold.update(g)
                continue
            rel = [a for a in c["annotations"] if a["status"] == e["status"] and any(
                e["hpo_id"] in ont.ancestors(t) or t in ont.ancestors(e["hpo_id"]) for t in a["acceptable"])]
            neg = [n["quote"] for n in c["negatives"] if n["quote"] in e["quote"] or e["quote"] in n["quote"]]
            entry = {"context": c["id"], "quote": e["quote"], "hpo_id": e["hpo_id"], "label": e["label"],
                     "status": e["status"], "from_negative_span": neg[0] if neg else None,
                     "near_miss_of": [a["quote"] for a in rel]}
            false_pos.append(entry)
            if rel:
                near.append(entry)
        matched += len(hit_gold)
        for i, a in enumerate(c["annotations"]):
            if i not in hit_gold:
                got = [f"{e['hpo_id']} {e['label']} ({e['quote']!r})" for e in ext]
                misses.append({"context": c["id"], "quote": a["quote"], "acceptable": a["acceptable"], "extracted": got})
    by_kind: dict[str, list[int]] = {}
    for c in gold["contexts"]:
        for i, a in enumerate(c["annotations"]):
            k = a.get("kind")
            if k:
                hit = not any(m["context"] == c["id"] and m["quote"] == a["quote"] for m in misses)
                by_kind.setdefault(k, [0, 0])
                by_kind[k][0] += hit
                by_kind[k][1] += 1
    return {"precision": round(tp_ext / n_ext, 3) if n_ext else None, "recall": round(matched / n_gold, 3),
            "recall_by_kind": {k: f"{h}/{n}" for k, (h, n) in sorted(by_kind.items())},
            "extracted": n_ext, "true_positive_terms": tp_ext, "gold_spans": n_gold, "gold_matched": matched,
            "negative_spans": sum(len(c["negatives"]) for c in gold["contexts"]),
            "false_positives": false_pos, "near_misses": near, "missed": misses}


def report(r: dict) -> None:
    print(f"precision {r['precision']}  ({r['true_positive_terms']}/{r['extracted']} extracted terms correct)")
    print(f"recall    {r['recall']}  ({r['gold_matched']}/{r['gold_spans']} gold spans found)")
    if r.get("recall_by_kind"):
        print("recall by kind: " + ", ".join(f"{k} {v}" for k, v in r["recall_by_kind"].items()))
    print(f"false positives: {len(r['false_positives'])} (of which near misses on the hierarchy: {len(r['near_misses'])})")
    for f in r["false_positives"]:
        why = (f"from negative span {f['from_negative_span']!r}" if f["from_negative_span"]
               else f"near miss of {f['near_miss_of']}" if f["near_miss_of"] else "no gold span")
        print(f"  FP {f['context']}: {f['quote']!r} -> {f['hpo_id']} {f['label']} [{f['status']}]  ({why})")
    for m in r["missed"]:
        print(f"  MISS {m['context']}: {m['quote']!r} want {m['acceptable']}; got {m['extracted']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["basic", "hard", "all"], default="all")
    ap.add_argument("--fresh-llm", action="store_true")
    args = ap.parse_args()
    if args.fresh_llm:
        extract.CACHE_DIR = Path(tempfile.mkdtemp(prefix="aitx-llm-"))
    ont = load_ontology()
    out = {}
    for name in (["basic", "hard"] if args.set == "all" else [args.set]):
        gold = json.loads(SETS[name].read_text())
        bad = check_gold(gold, ont)
        if bad:
            print(f"{name} set has invalid entries:\n  " + "\n  ".join(bad))
            return 2
        print(f"== {name} set ({SETS[name].name}) ==")
        out[name] = evaluate(gold, ont)
        report(out[name])
    dest = ROOT / "out" / "eval_extraction.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

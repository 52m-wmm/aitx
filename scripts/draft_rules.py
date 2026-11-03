"""Draft gene-specific rules for every gene in the step 2 results (step 3.0 contract, section 4).

Usage:
    python3 scripts/draft_rules.py                 # all genes found in out/step2/
    python3 scripts/draft_rules.py --gene DMD      # one gene

Writes data/rules/<GENE>.json (see aitx/evidence/drafting.py). A reviewer may only veto a rule:
set "review": {"decision": "vetoed", "by": ..., "at": ..., "reason": ...} in the file. Redrafting keeps the
review of any rule whose content is unchanged (same content_sha256), so a veto survives reruns.
Needs AITX_LLM_API_KEY unless the LLM answers are cached.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx.evidence import drafting  # noqa: E402
from aitx.evidence.rules import RULES_DIR  # noqa: E402


def genes_from_step2() -> dict[str, dict]:
    """gene -> {candidates (not excluded, with OMIM; union over cases), nbks}"""
    out: dict[str, dict] = {}
    for f in sorted((ROOT / "out" / "step2").glob("*.json")):
        r = json.loads(f.read_text())
        if not isinstance(r, dict) or "candidates" not in r:
            continue
        for gene in sorted({v["gene"] for v in r["inheritance_evidence"]["variants"]}):
            g = out.setdefault(gene, {"candidates": {}, "nbks": []})
            for c in r["candidates"]:
                if c["gene"] == gene and not c.get("excluded") and c["omim"]:
                    g["candidates"].setdefault(c["key"], c)
            for ch in (r.get("genereviews") or {}).get(gene, []):
                if ch["nbk"] not in g["nbks"]:
                    g["nbks"].append(ch["nbk"])
    return out


def keep_reviews(new: dict, path: Path) -> None:
    if not path.exists():
        return
    old = {r["content_sha256"]: r.get("review") for r in json.loads(path.read_text()).get("rules", [])}
    for r in new["rules"]:
        if r["content_sha256"] in old and old[r["content_sha256"]]:
            r["review"] = old[r["content_sha256"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gene", action="append")
    args = ap.parse_args()
    genes = genes_from_step2()
    RULES_DIR.mkdir(parents=True, exist_ok=True)
    for gene in sorted(args.gene or genes):
        g = genes[gene]
        cands = sorted(g["candidates"].values(), key=lambda c: c["key"])
        doc = drafting.draft_gene(gene, cands, g["nbks"])
        path = RULES_DIR / f"{gene}.json"
        keep_reviews(doc, path)
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
        print(f"{gene:<8} sources {len(doc['sources']):>2}  rules {len(doc['rules'])}  rejected drafts "
              f"{len(doc['rejected_drafts'])}  " + (f"no rule: {doc.get('no_rule_reason', '')[:90]}" if not doc["rules"] else
                                                   "; ".join(r["statement"][:90] for r in doc["rules"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

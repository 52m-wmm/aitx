"""Online acceptance test for step 1 (run where NCBI is reachable).

Runs the four challenge cases and the official Phase 0 example variants
against the real RefSeq records and checks:
  HARD  every variant passes all consistency checks (reference base,
        reference amino acid, codon math, transcript version)
  HARD  self-check 6: the protein re-translated from the c. change agrees with
        the stated p. notation (pass, not just "not fail"), for every variant
  HARD  reverse validation: a deliberately wrong p. notation per variant must fail
  HARD  results that the official examples or UniProt state explicitly
  SOFT  values printed for a human to eyeball (no single right answer here)

Usage:  python scripts/acceptance_step1.py
Exit code 0 only if every HARD expectation passes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx.variant.hgvs import AA1_TO_3, parse_protein  # noqa: E402
from aitx.variant.profile import build_profile  # noqa: E402
from aitx.variant.transcript import fetch_transcript  # noqa: E402

# (case id, field path, expected value, where the expectation comes from)
HARD = [
    ("PRAC-AGXT-c33dup", "protein_length", 392, "UniProt P21549: 392 aa"),
    ("PRAC-AGXT-c33dup", "variant_class", "frameshift", "notation"),
    ("PRAC-AGXT-c33dup", "ptc_aa_position", 167, "Lys12 + Ter156 - 1"),
    ("PRAC-AGXT-c33dup", "nmd.prediction", "likely_triggers", "early PTC, not in last exon"),
    ("PRAC-CFTR-F508del", "protein_length", 1480, "UniProt P13569: 1480 aa"),
    ("PRAC-CFTR-F508del", "variant_class", "inframe_deletion", "notation"),
    ("PRAC-CFTR-F508del", "nmd.prediction", "not_applicable", "no premature stop"),
    ("PRAC-KMT2B", "nmd.prediction", "likely_escapes", "official example answer: NMD = No"),
    ("PRAC-SLC35A2", "variant_class", "start_lost", "p.Met1Ile"),
    ("PRAC-GRIN2B", "variant_class", "nonsense", "p.Gln919Ter"),
    ("AITX-40001", "ptc_aa_position", 414, "Gln367 + Ter48 - 1"),
]
SOFT = [
    ("PRAC-ANO10", "exon.coding_fraction_of_cds", "official example answer: 0.1 (to nearest tenth)"),
    ("PRAC-DMD-del", "exon", "official explanation mentions exons 52-63"),
    ("PRAC-KMT2B", "nmd", "reasons"),
    ("AITX-40001", "nmd", "ACTL6B frameshift: NMD?"),
    ("AITX-40001", "exon", "ACTL6B exon"),
]


def get(d: dict, path: str):
    for k in path.split("."):
        d = d.get(k) if isinstance(d, dict) else None
    return d


def wrong_notation(p_raw: str, protein: str) -> str:
    """A deliberately wrong version of a correct p. notation (for reverse validation)."""
    pv = parse_protein(p_raw)
    if pv.kind == "frameshift":
        return f"p.({pv.ref_aa}{pv.pos}{pv.alt_aa}fsTer{(pv.fs_ter or 0) + 1})"
    if pv.kind == "nonsense":
        return f"p.{AA1_TO_3[protein[pv.pos]]}{pv.pos + 1}Ter"
    if pv.kind == "missense":
        return f"p.{pv.ref_aa}{pv.pos}{'Gly' if pv.alt_aa != 'Gly' else 'Ala'}"
    if pv.kind == "inframe_deletion":
        a, b = pv.pos + 1, pv.end_pos + 1
        return f"p.{AA1_TO_3[protein[a - 1]]}{a}" + (f"_{AA1_TO_3[protein[b - 1]]}{b}" if b != a else "") + "del"
    if pv.kind == "start_lost":
        return f"p.{AA1_TO_3[protein[1]]}2Val"
    raise ValueError(f"no wrong-notation rule for {pv.kind}")


def load_cases() -> list[dict]:
    cases = json.loads((ROOT / "data/cases/aitx_final_patients.json").read_text())
    cases += json.loads((ROOT / "data/cases/practice/official_examples.json").read_text())
    return cases


def main() -> int:
    results: dict[str, dict] = {}
    variants: dict[str, tuple[dict, object]] = {}
    hard_fail = 0
    print("== consistency checks (HARD) ==")
    for case in load_cases():
        v = case["patient"]["genotype"][0]
        try:
            t = fetch_transcript(v["transcript"])
            variants[case["id"]] = (v, t)
            p = build_profile(v, t).to_dict()
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {case['id']:<20} could not build profile: {e}")
            hard_fail += 1
            continue
        results[case["id"]] = p
        bad = [c for c in p["checks"] if c["status"] != "pass"]
        mark = "PASS" if not any(c["status"] == "fail" for c in bad) else "FAIL"
        hard_fail += mark == "FAIL"
        print(f"{mark} {case['id']:<20} {v['gene']:<8} {v['variant_cdna']:<16} "
              f"{p['variant_class']:<17} exon {p['exon'].get('number')}/{p['exon'].get('total')}  "
              f"NMD {p['nmd']['prediction']}")
        for c in bad:
            print(f"       {c['status'].upper()} {c['name']}: {c['detail']}")

    print("\n== self-check 6: independent re-translation (HARD) ==")
    for cid, p in results.items():
        c = next(c for c in p["checks"] if c["name"] == "independent_translation")
        ok = c["status"] == "pass"
        hard_fail += not ok
        print(f"{'PASS' if ok else 'FAIL'} {cid:<20} {c['detail']}")

    print("\n== reverse validation: wrong p. notation must fail (HARD) ==")
    for cid, (v, t) in variants.items():
        bad = dict(v, variant_protein=wrong_notation(v["variant_protein"], t.protein))
        c = next(c for c in build_profile(bad, t).checks if c.name == "independent_translation")
        ok = c.status == "fail"
        hard_fail += not ok
        print(f"{'PASS' if ok else 'FAIL'} {cid:<20} {bad['variant_protein']:<28} -> {c.status}: {c.detail}")

    print("\n== stated expectations (HARD) ==")
    for cid, path, want, why in HARD:
        got = get(results.get(cid, {}), path)
        ok = got == want
        hard_fail += not ok
        print(f"{'PASS' if ok else 'FAIL'} {cid:<20} {path:<28} want {want!r:<20} got {got!r}   [{why}]")

    print("\n== values to eyeball (SOFT) ==")
    for cid, path, why in SOFT:
        print(f"     {cid:<20} {path:<28} = {json.dumps(get(results.get(cid, {}), path), ensure_ascii=False)}"
              f"   [{why}]")

    out = ROOT / "out" / "acceptance_step1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n{'ALL HARD CHECKS PASSED' if not hard_fail else f'{hard_fail} HARD CHECK(S) FAILED'}"
          f" — full profiles in {out}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

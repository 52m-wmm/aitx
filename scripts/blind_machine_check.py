"""Machine judging for a blind-test batch (docs/blind_test_plan.md section 3). Deterministic, no LLM.

Six checks that need no medical judgement. Anything that fails one of them is a "wrong" entry with the rule it
broke; everything else is listed for the reviewer to judge.

  1 quote-verbatim      every quoted requirement / use quote appears verbatim in the source text the ledger kept
  2 record-resolvable   every cited record id looks like a resolvable id of its kind, and --online checks it
  3 section-rules       no action in two sections; no human precedent left in 3e; no bespoke modality in 3e
  4 direction           3e candidates act in the direction the branch's mechanism calls for
  5 wording             no conclusion claims efficacy, and no 3d/3e conclusion carries a dose
  6 patient-facts       a requirement said to be met has a quoted patient fact; an unknown one is in missing_information

Usage: python scripts/blind_machine_check.py --batch 20261108 [--online]
Writes out/blind/<batch>/machine.json and prints a summary plus the reviewer's list.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx import runmeta  # noqa: E402
from aitx.evidence import ledger as LG  # noqa: E402
from aitx.evidence import repurposing as RP  # noqa: E402

SECTIONS = ("existing_targeted_therapies", "supportive_management", "contraindications_precautions",
            "clinical_trial_eligibility", "off_label_expanded_access", "bespoke_therapies", "drug_repurposing")
STRONG = re.compile(r"\b(recommended|effective|efficacious|proven|cures?|will work|should be (?:given|tried))\b", re.I)
DOSE = re.compile(r"\b\d+\s*(?:mg|mcg|µg|g|ml|mg/kg|units?)\b", re.I)
ID_SHAPES = {"pmid": r"^\d{6,9}$", "nct": r"^NCT\d{8}$", "setid": r"^[0-9a-f-]{36}$", "nbk": r"^NBK\d+$",
             "chembl": r"^CHEMBL\d+$", "reactome": r"^R-HSA-\d+$", "ensembl": r"^ENSG\d{11}$",
             "vcv": r"^VCV\d+$", "omim": r"^OMIM:\d{6}$"}


def id_kind(value: str) -> str | None:
    for kind, shape in ID_SHAPES.items():
        if re.match(shape, str(value or "")):
            return kind
    return None


def check_quotes(led: dict) -> list[dict]:
    """Check 1: the ledger records, per evidence item, whether its quote was found verbatim."""
    out = []
    for e in led.get("evidence", []):
        if e.get("kind") != "sourced" or not e.get("quote"):
            continue
        if e.get("quote_verified") is False:
            out.append({"check": "quote-verbatim", "evidence": e["id"], "section": e.get("section"),
                        "detail": f"quote not verbatim in the source: {e['quote'][:120]!r}"})
    return out


def check_records(led: dict, online: bool) -> list[dict]:
    """Check 2: every cited id has the shape of a resolvable id; with --online, a sample is fetched."""
    out, seen = [], set()
    for e in led.get("evidence", []):
        src = e.get("source") or {}
        if not src:
            continue
        value = src.get("id") or ""
        kind = id_kind(value)
        if value and kind is None:
            out.append({"check": "record-resolvable", "evidence": e["id"], "section": e.get("section"),
                        "detail": f"cited id {value!r} ({src.get('type')}) is not a recognisable record id"})
        elif kind:
            seen.add((kind, value))
    if online:
        from aitx import http
        for kind, value in sorted(seen):
            if kind != "pmid":
                continue
            url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id=" + value)
            try:
                got = json.loads(http.get(url, timeout=60).text)["result"].get(value) or {}
            except Exception as e:  # noqa: BLE001
                out.append({"check": "record-resolvable", "detail": f"PMID {value}: fetch failed ({e})"})
                continue
            if not got.get("title"):
                out.append({"check": "record-resolvable", "detail": f"PMID {value} does not resolve to a record"})
    return out


def check_sections(led: dict) -> list[dict]:
    out, by_key = [], {}
    for a in led.get("actions", []):
        key = a.get("action_key")
        if not key:
            continue
        by_key.setdefault(key, set()).add(a["section"])
    for key, sections in by_key.items():
        if len(sections) > 1:
            out.append({"check": "section-rules", "action": key,
                        "detail": f"the same action appears in {sorted(sections)}"})
    for a in led.get("actions", []):
        if a["section"] != "drug_repurposing":
            continue
        if a.get("human_precedent"):
            out.append({"check": "section-rules", "action": a.get("label"),
                        "detail": "3e candidate has a human precedent, which belongs in 3c"})
        if RP.is_bespoke_type((a.get("facts") or {}).get("drug_type") or a.get("drug_type")):
            out.append({"check": "section-rules", "action": a.get("label"),
                        "detail": "3e candidate is a bespoke modality, which belongs in 3d"})
    return out


def check_direction(led: dict) -> list[dict]:
    out = []
    mech = {b: (r or {}).get("mechanism") for b, r in (led.get("bespoke_mechanism") or {}).items()}
    for a in led.get("actions", []):
        if a["section"] != "drug_repurposing":
            continue
        for b in a.get("applies_to", []):
            if not RP.direction_ok(mech.get(b), a.get("direction")):
                out.append({"check": "direction", "action": a.get("label"), "branch": b,
                            "detail": f"direction {a.get('direction')} does not address mechanism {mech.get(b)}"})
    return out


def check_wording(led: dict) -> list[dict]:
    out = []
    for a in led.get("actions", []):
        text = a.get("conclusion") or ""
        if STRONG.search(text):
            out.append({"check": "wording", "action": a.get("label"), "section": a["section"],
                        "detail": f"conclusion claims efficacy: {text[:140]!r}"})
        if a["section"] in ("bespoke_therapies", "drug_repurposing") and DOSE.search(text):
            out.append({"check": "wording", "action": a.get("label"), "section": a["section"],
                        "detail": f"hypothetical-layer conclusion carries a dose: {text[:140]!r}"})
    return out


def check_patient_facts(led: dict) -> list[dict]:
    out, missing = [], {m["variable"] for m in led.get("missing_information", [])}
    for a in led.get("actions", []):
        for r in a.get("requirements", []):
            fact = r.get("patient_fact") or {}
            if r.get("patient_status") in ("satisfies", "does_not_satisfy") and not fact.get("quote"):
                out.append({"check": "patient-facts", "action": a.get("label"), "requirement": r.get("id"),
                            "detail": f"{r.get('patient_status')} without a quoted patient fact"})
            if r.get("result") == "unknown" and fact.get("field") and fact["field"] not in missing:
                out.append({"check": "patient-facts", "action": a.get("label"), "requirement": r.get("id"),
                            "detail": f"unknown {fact['field']!r} is not in missing_information"})
    return out


def entries(led: dict, case: str) -> list[dict]:
    """Every written entry the reviewer may have to judge, with what it rests on."""
    out = []
    for a in led.get("actions", []):
        if a["section"] not in SECTIONS:
            continue
        quotes = [e for e in led.get("evidence", []) if e["id"] in (a.get("evidence_ids") or [])]
        out.append({"case": case, "section": a["section"], "label": a.get("label") or a.get("modality"),
                    "conclusion": a.get("conclusion") or "",
                    "status": {b: v.get("status") for b, v in (a.get("status_by_branch") or {}).items()}
                    or a.get("classification"),
                    "cites": [{"type": (e.get("source") or {}).get("type"), "id": (e.get("source") or {}).get("id"),
                               "url": (e.get("source") or {}).get("url"), "quote": (e.get("quote") or "")[:300]}
                              for e in quotes],
                    "needs_review": ["semantics: does the conclusion match the quote",
                                     "applicability: does it apply to this patient"]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="20261108")
    ap.add_argument("--online", action="store_true", help="also fetch the cited PubMed records")
    args = ap.parse_args()
    d = ROOT / "out" / "blind" / args.batch
    sample = json.loads((d / "sample.json").read_text())
    cases = [c["id"] for c in json.loads((ROOT / "data" / "cases" / "blind" / f"{args.batch}.json").read_text())]
    wrong, listed, per_case = [], [], {}
    for cid in cases:
        p = runmeta.path(3, cid)
        if not p.exists():
            per_case[cid] = {"ran": False}
            continue
        led = json.loads(p.read_text())
        found = (check_quotes(led) + check_records(led, args.online) + check_sections(led)
                 + check_direction(led) + check_wording(led) + check_patient_facts(led))
        for f in found:
            f["case"] = cid
        wrong += found
        ent = entries(led, cid)
        listed += ent
        per_case[cid] = {"ran": True, "entries": len(ent), "machine_wrong": len(found),
                         "ledger_ok": led.get("ok"),
                         "failed_checks": [c["name"] for c in led.get("checks", []) if c["status"] == "fail"],
                         "sections": {s: sum(1 for a in led.get("actions", []) if a["section"] == s)
                                      for s in SECTIONS}}
    out = {"schema": "blind-machine-v1", "batch": args.batch, "checked_at": int(time.time()),
           "code_fingerprint": runmeta.code_fingerprint(),
           "frozen_as_drawn": runmeta.code_fingerprint() == sample["code_fingerprint"],
           "cases": per_case, "machine_wrong": wrong, "for_review": listed}
    (d / "machine.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"frozen as drawn: {out['frozen_as_drawn']}")
    ran = [c for c, m in per_case.items() if m.get("ran")]
    print(f"{len(ran)}/{len(cases)} cases have a step 3 ledger; "
          f"{sum(m.get('entries', 0) for m in per_case.values())} written entries in total")
    for cid, m in per_case.items():
        if not m.get("ran"):
            print(f"  {cid:<16} NOT RUN")
            continue
        print(f"  {cid:<16} entries {m['entries']:<4} machine-wrong {m['machine_wrong']:<3} "
              f"ledger {'ok' if m['ledger_ok'] else 'FAILED ' + str(m['failed_checks'])}")
    if wrong:
        print(f"\n{len(wrong)} machine-judged WRONG entries:")
        for w in wrong:
            print(f"  [{w['check']}] {w['case']} {w.get('action') or w.get('evidence') or ''}: {w['detail'][:150]}")
    else:
        print("\nno entry failed a machine check")
    print(f"\n{len(listed)} entries need a human judgement -> {(d / 'machine.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

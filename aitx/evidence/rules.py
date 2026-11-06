"""Gene-specific rule layer (step 3.0 contract, section 4).

Rules are data in data/rules/<GENE>.json, drafted by the system (scripts/draft_rules.py) and never
edited by hand: a reviewer may only veto a rule, or accept a rule left pending by the support check,
always with a reason. A rule is loaded only if
  - status is "verified" (support check passed) or "pending_review" accepted by a reviewer, and it was not vetoed,
  - its content hash still matches what the drafting pipeline wrote (no hand edits),
  - every source quote is found verbatim in the source text fetched again now (aitx.http, cached),
  - its conditions use step 1 fields only.
A loaded rule that matches a variant adds background evidence (the rule's literature) and a
branch assessment; rules never delete branches, they only reorder them (branch_order). A rule may
promote a step 2 candidate it supports to a branch while there are fewer than MAX_BRANCHES branches
(contract section 2, "rule promotion"); otherwise the promotion is recorded as blocked.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from aitx import http
from aitx.evidence import ledger as LG
from aitx.evidence.branches import MAX_BRANCHES, make_branch, set_roles

ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = ROOT / "data" / "rules"
CONDITION_FIELDS = {"variant_class", "nmd_prediction", "zygosity", "exon", "protein_position",
                    "aa_substitution", "exon_loss"}      # narrowing fields added 2026-11-05 (review)


def identity(rule: dict) -> str:
    """What a reviewer decided about: statement, conditions, effect and quotes (not status or checks)."""
    body = {k: rule.get(k) for k in ("gene", "statement", "applies_when", "effect")}
    body["quotes"] = sorted(s.get("quote", "") for s in rule.get("sources") or [])
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def content_hash(rule: dict) -> str:
    body = {k: v for k, v in rule.items() if k not in ("review", "content_sha256")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _source_text(src: dict) -> str | None:
    """The source text a quote is checked against: GeneReviews sections from the local archive, others via HTTP."""
    if src.get("type") == "nbk":
        from aitx.evidence import genereviews
        return genereviews.section_text(src["id"], src.get("section", ""))
    try:
        return http.get(src["text_url"]).text
    except (KeyError, RuntimeError):
        return None


def validate(rule: dict) -> list[str]:
    """Reasons a rule may not be loaded ([] = loadable)."""
    bad = []
    review = rule.get("review") or {}
    if review.get("decision") == "vetoed":
        bad.append("vetoed: " + (review.get("reason") or "NO REASON GIVEN"))
    accepted = review.get("decision") == "accepted" and review.get("reason")
    if rule.get("status") == "pending_review" and not accepted:
        bad.append("pending review: the support check found the quotes do not fully support it ("
                   + (rule.get("support_check") or {}).get("overall", "?") + ")")
    elif rule.get("status") not in ("verified", "pending_review"):
        bad.append(f"status {rule.get('status')!r}, not verified")
    if rule.get("status") == "verified" and (rule.get("support_check") or {}).get("overall", "supported") != "supported":
        bad.append("marked verified but the support check did not find it supported")
    if rule.get("content_sha256") != content_hash(rule):
        bad.append("content differs from the drafted version (hand edit)")
    unknown = set(rule.get("applies_when") or {}) - CONDITION_FIELDS
    if unknown:
        bad.append(f"conditions use non-step-1 fields {sorted(unknown)}")
    if not rule.get("sources"):
        bad.append("no source")
    for s in rule.get("sources") or []:
        text = _source_text(s)
        if text is None or not LG.quote_in(s.get("quote", ""), text):
            bad.append(f"quote not verified in {s.get('type')} {s.get('id')}")
    return bad


def load_rules(rules_dir: Path = RULES_DIR) -> dict:
    loaded, skipped = [], []
    for f in sorted(rules_dir.glob("*.json")) if rules_dir.exists() else []:
        doc = json.loads(f.read_text())
        for r in doc.get("rules", []):
            reasons = validate(r)
            if reasons:
                skipped.append({"rule_id": r.get("id"), "file": f.name, "reasons": reasons})
            else:
                loaded.append(r)
    return {"loaded": loaded, "skipped": skipped}


_AA3 = {"Ala", "Arg", "Asn", "Asp", "Cys", "Gln", "Glu", "Gly", "His", "Ile", "Leu", "Lys", "Met", "Phe", "Pro",
        "Ser", "Thr", "Trp", "Tyr", "Val", "Ter", "Sec"}
# the whole protein change must be this one substitution: "p.(Ile2694SerfsTer44)" is a frameshift, not Ile->Ser
_SUB = re.compile(r"^p\.\(?([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})\)?$")


def substitution(v: dict) -> dict | None:
    """{position, from, to} of a single amino-acid substitution, from the step 1 re-translation (preferred, since
    it is computed from the sequence) or from the stated protein change. None when the variant is not one."""
    fc = ((v.get("retranslation") or {}).get("first_changed_aa") or {})
    if fc.get("position") and fc.get("reference") in _AA3 and fc.get("variant") in _AA3:
        return {"position": int(fc["position"]), "from": fc["reference"], "to": fc["variant"]}
    m = _SUB.match(str(v.get("variant_protein") or "").strip())
    if m and m.group(1) in _AA3 and m.group(3) in _AA3:
        return {"position": int(m.group(2)), "from": m.group(1), "to": m.group(3)}
    return None


def loses_exon(v: dict, lo: int, hi: int) -> bool:
    """Does this variant remove (or plausibly skip) a whole exon in [lo, hi]?

    Only two deterministic cases (2026-11-05 review): a deletion whose span covers such an exon, and a splice
    variant at such an exon's own boundary (the usual way an exon is skipped; we do not predict splicing, so
    this is as far as step 1 facts reach). A coding change inside the exon is NOT exon loss.
    """
    ex = v.get("exon") or {}
    n, spanned = ex.get("number"), ex.get("exons_spanned") or ([ex["number"]] if ex.get("number") else [])
    cls = v.get("variant_class")
    if cls in ("deletion", "inframe_deletion", "cnv_deletion", "whole_exon_deletion"):
        return any(lo <= e <= hi for e in spanned)
    if cls == "splice":
        return n is not None and lo <= n <= hi
    return False


def matches(cond: dict, v: dict) -> bool:
    """Conditions on one step 1 variant; every listed condition must hold."""
    pos = v.get("first_affected_aa")

    def is_sub(want: dict) -> bool:
        got = substitution(v)
        return bool(got) and all(got.get(k) == want[k] for k in ("position", "from", "to") if k in want)

    checks = {
        "variant_class": lambda want: v.get("variant_class") in want,
        "nmd_prediction": lambda want: (v.get("nmd") or {}).get("prediction") in want,
        "zygosity": lambda want: v.get("zygosity") in want,
        "exon": lambda r: (v.get("exon") or {}).get("number") is not None and r[0] <= v["exon"]["number"] <= r[1],
        "protein_position": lambda r: pos is not None and r[0] <= pos <= r[1],
        "aa_substitution": is_sub,
        "exon_loss": lambda r: loses_exon(v, r[0], r[1]),
    }
    return all(checks[k](want) for k, want in cond.items())


def promote(led: LG.Ledger, rule: dict, step2: dict | None) -> list[dict]:
    """Make step 2 candidates the rule supports into branches (contract section 2). Returns records."""
    out = []
    present = {o for b in led.branches if b["diagnosis"] for o in b["diagnosis"]["omim"]}
    cands = [c for c in (step2 or {}).get("candidates", []) if not c.get("excluded")]
    for omim in (rule.get("effect") or {}).get("supports", []):
        if omim in present:
            continue
        c = next((c for c in cands if omim in [o["id"] for o in c["omim"]]), None)
        if c is None:
            out.append({"omim": omim, "promoted": False, "reason": "not a step 2 candidate"})
        elif len(led.branches) >= MAX_BRANCHES:
            out.append({"omim": omim, "candidate": c["key"], "promoted": False,
                        "reason": f"branch limit ({MAX_BRANCHES}) reached; no branch is removed"})
        else:
            b = make_branch(c, led.branches[0]["gene"] if led.branches else rule["gene"],
                            [f"promoted by rule {rule['id']}: {rule['statement']}"])
            b["promoted_by"] = rule["id"]
            led.branches.append(b)
            present.update(b["diagnosis"]["omim"])
            out.append({"omim": omim, "candidate": c["key"], "promoted": True})
    if any(x["promoted"] for x in out):
        set_roles(led.branches, resolved=False)          # more than one diagnosis now: all are 'ambiguous_N'
    return out


def apply_rules(led: LG.Ledger, rules: dict, step1: dict, step2: dict | None = None) -> None:
    led.rules_applied = []
    led.rules_skipped = rules.get("skipped", [])
    for v in step1["variants"]:
        for r in rules.get("loaded", []):
            if r["gene"] != v["gene"] or not matches(r.get("applies_when") or {}, v):
                continue
            weak = r.get("strength") == "weak"           # weak rules are background only (decision 2026-11-03)
            promotions = [] if weak else promote(led, r, step2)
            by_omim = {o: b["id"] for b in led.branches if b["diagnosis"] for o in b["diagnosis"]["omim"]}
            eff = r.get("effect") or {}
            sup = [by_omim[o] for o in eff.get("supports", []) if o in by_omim]
            ag = [by_omim[o] for o in eff.get("argues_against", []) if o in by_omim]
            applies = sorted(set(sup + ag)) or [b["id"] for b in led.branches]
            ev_ids = []
            for s in r["sources"]:
                e = led.add(LG.sourced(r["statement"], "background", applies,
                                       {"type": s["type"], "id": s["id"], "url": s.get("url")}, s["quote"],
                                       _source_text(s) or "", s.get("accessed_at") or 0,
                                       produced_by=r.get("drafted", {}).get("llm") or "code",
                                       retrieved_by=f"rule {r['id']}"))
                ev_ids.append(e["id"])
            led.rules_applied.append({"rule_id": r["id"], "variant": f"{v['gene']} {v['variant_cdna']}",
                                      "statement": r["statement"], "strength": r.get("strength"),
                                      "supports": sup, "argues_against": ag, "evidence_ids": ev_ids,
                                      "promotions": promotions,
                                      "affects_branches": not weak,
                                      "branches_not_present": [o for o in eff.get("supports", []) + eff.get("argues_against", [])
                                                               if o not in by_omim]})
            if not weak:
                led.branch_assessment += [{"branch": b, "rule_id": r["id"], "effect": "supports", "evidence_ids": ev_ids}
                                          for b in sup]
                led.branch_assessment += [{"branch": b, "rule_id": r["id"], "effect": "argues_against",
                                           "evidence_ids": ev_ids} for b in ag]
    led.branch_order = branch_order(led.branches, led.branch_assessment)


def branch_order(branches: list[dict], assessment: list[dict]) -> list[str]:
    """Rule-supported branches first, argued-against last, otherwise step 2 order. Nothing is removed."""
    def weight(b):
        effs = [a["effect"] for a in assessment if a["branch"] == b["id"]]
        return -effs.count("supports") + effs.count("argues_against")
    return [b["id"] for _, b in sorted(enumerate(branches), key=lambda ib: (weight(ib[1]), ib[0]))]

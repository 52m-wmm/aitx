"""Gene-specific rule layer (step 3.0 contract, section 4).

Rules are data in data/rules/<GENE>.json, drafted by the system (scripts/draft_rules.py) and never
edited by hand: a reviewer may only veto a rule, with a reason. A rule is loaded only if
  - status is "verified" and it was not vetoed,
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
from pathlib import Path

from aitx import http
from aitx.evidence import ledger as LG
from aitx.evidence.branches import MAX_BRANCHES, make_branch, set_roles

ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = ROOT / "data" / "rules"
CONDITION_FIELDS = {"variant_class", "nmd_prediction", "zygosity", "exon", "protein_position"}


def content_hash(rule: dict) -> str:
    body = {k: v for k, v in rule.items() if k not in ("review", "content_sha256")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _source_text(src: dict) -> str | None:
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
    if rule.get("status") != "verified":
        bad.append(f"status {rule.get('status')!r}, not verified")
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


def matches(cond: dict, v: dict) -> bool:
    """Conditions on one step 1 variant; every listed condition must hold."""
    pos = v.get("first_affected_aa")
    checks = {
        "variant_class": lambda want: v.get("variant_class") in want,
        "nmd_prediction": lambda want: (v.get("nmd") or {}).get("prediction") in want,
        "zygosity": lambda want: v.get("zygosity") in want,
        "exon": lambda r: (v.get("exon") or {}).get("number") is not None and r[0] <= v["exon"]["number"] <= r[1],
        "protein_position": lambda r: pos is not None and r[0] <= pos <= r[1],
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
            promotions = promote(led, r, step2)
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
                                      "branches_not_present": [o for o in eff.get("supports", []) + eff.get("argues_against", [])
                                                               if o not in by_omim]})
            led.branch_assessment += [{"branch": b, "rule_id": r["id"], "effect": "supports", "evidence_ids": ev_ids} for b in sup]
            led.branch_assessment += [{"branch": b, "rule_id": r["id"], "effect": "argues_against", "evidence_ids": ev_ids} for b in ag]
    led.branch_order = branch_order(led.branches, led.branch_assessment)


def branch_order(branches: list[dict], assessment: list[dict]) -> list[str]:
    """Rule-supported branches first, argued-against last, otherwise step 2 order. Nothing is removed."""
    def weight(b):
        effs = [a["effect"] for a in assessment if a["branch"] == b["id"]]
        return -effs.count("supports") + effs.count("argues_against")
    return [b["id"] for _, b in sorted(enumerate(branches), key=lambda ib: (weight(ib[1]), ib[0]))]

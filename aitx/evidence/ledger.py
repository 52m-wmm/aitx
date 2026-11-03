"""Evidence ledger (step 3.0 contract, section 1): one record per claim, plus the checks.

Three kinds of evidence:
  sourced    a claim backed by a verbatim quote from a record the code fetched (URL, PMID, NCT, ...)
  reasoning  a claim derived from other verified evidence in the same ledger (premises)
  negative   "searched, found nothing": database, exact query, time, number of results (code only)

Only `verified` evidence may sit in a report section. The ledger never trusts the LLM for sources,
quotes, result counts or identifiers: those come from code (same principle as step 2).
"""
from __future__ import annotations

import hashlib
import json
import re

from aitx.evidence.actions import same_action

SCHEMA_VERSION = "evidence-ledger-v1"

SECTIONS = {   # report sections (template order, Summary excluded) -> evidence tier
    "existing_targeted_therapies": "established",
    "supportive_management": "established",
    "contraindications_precautions": "established",
    "clinical_trial_eligibility": "emerging",
    "off_label_expanded_access": "emerging",
    "bespoke_therapies": "hypothesized",
    "drug_repurposing": "hypothesized",
    "outcome_measures_ranking": "hypothesized",
}
TIERS = {**SECTIONS, "background": "background"}
KINDS = ("sourced", "reasoning", "negative")
STATUSES = ("candidate", "verified", "rejected")

SOURCE_ID = {   # source type -> id format
    "url": r"https?://\S+",
    "pmid": r"\d{1,9}",
    "nct": r"NCT\d{8}",
    "nbk": r"NBK\d+",
    "spl_setid": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "clinvar_vcv": r"VCV\d{9}(\.\d+)?",
    "omim": r"OMIM:\d{6}",
    "mondo": r"MONDO:\d{7}",
    "orphanet": r"ORPHA:\d+",
    "hpo": r"HP:\d{7}",
    "refseq": r"N[MPRC]_\d+\.\d+",
    "alphafold": r"AF-[A-Z0-9-]+-F\d+",
    "clingen": r"CGGV:\S+",
    "pipeline_fact": r"step[0-9](\.[0-9])?:[A-Za-z0-9-]+:\S+",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_in(quote: str, source_text: str) -> bool:
    """Verbatim check, insensitive to case and whitespace only."""
    return bool(quote) and _norm(quote) in _norm(source_text)


def evidence_id(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def source_ok(src: dict) -> bool:
    rx = SOURCE_ID.get((src or {}).get("type"))
    return bool(rx and re.fullmatch(rx, str(src.get("id") or "")))


# ------------------------------------------------------------ constructors

def _base(kind: str, claim: str, section: str, applies_to: list[str], produced_by, retrieved_by: str,
          action: dict | None, conditions: list[dict] | None) -> dict:
    if section not in TIERS:
        raise ValueError(f"unknown section {section!r}")
    return {"kind": kind, "claim": claim, "section": section, "tier": TIERS[section], "action": action,
            "applies_to": sorted(applies_to), "conditions": conditions or [], "produced_by": produced_by,
            "retrieved_by": retrieved_by, "status": "candidate", "reasons": []}


def sourced(claim: str, section: str, applies_to: list[str], source: dict, quote: str, source_text: str,
            accessed_at: int, *, produced_by="code", retrieved_by: str = "", action: dict | None = None,
            conditions: list[dict] | None = None) -> dict:
    """Evidence from a fetched record. `source_text` is the fetched text the quote must appear in."""
    e = _base("sourced", claim, section, applies_to, produced_by, retrieved_by, action, conditions)
    e.update(source=source, quote=quote, accessed_at=accessed_at, quote_verified=quote_in(quote, source_text))
    e["id"] = evidence_id(source.get("type"), source.get("id"), claim, section, (action or {}).get("key"), e["applies_to"])
    if not source_ok(source):
        e["reasons"].append(f"source id {source.get('id')!r} is not a valid {source.get('type')!r} id")
    if not e["quote_verified"]:
        e["reasons"].append("quote not found verbatim in the fetched source")
    if not accessed_at:
        e["reasons"].append("no access time")
    e["status"] = "verified" if not e["reasons"] else "rejected"
    return e


def reasoning(claim: str, section: str, applies_to: list[str], premises: list[str], *, produced_by="code",
              retrieved_by: str = "", action: dict | None = None, conditions: list[dict] | None = None) -> dict:
    """Derived claim; becomes verified in Ledger.add once every premise is verified evidence."""
    e = _base("reasoning", claim, section, applies_to, produced_by, retrieved_by, action, conditions)
    e.update(premises=list(premises))
    e["id"] = evidence_id("reasoning", sorted(premises), claim, section, (action or {}).get("key"), e["applies_to"])
    return e


def negative(section: str, applies_to: list[str], *, database: str, endpoint: str, query: str, queried_at: int,
             n_results: int, response_count: int, filters: dict | None = None, excluded: list[dict] | None = None,
             claim: str = "") -> dict:
    """'Searched, found nothing (applicable)'. n_results must equal the count read from the response."""
    excluded = excluded or []
    claim = claim or (f"No applicable records were found in {database} for {query!r} "
                      f"({n_results} returned, {len(excluded)} excluded).")
    e = _base("negative", claim, section, applies_to, "code", f"{database} {query}", None, None)
    e["search"] = {"database": database, "endpoint": endpoint, "query": query, "filters": filters or {},
                   "queried_at": queried_at, "n_results": n_results, "n_excluded": len(excluded), "excluded": excluded}
    e["id"] = evidence_id("negative", database, query, section, e["applies_to"])
    if n_results != response_count:
        e["reasons"].append(f"n_results {n_results} != {response_count} records in the response")
    if not queried_at:
        e["reasons"].append("no query time")
    if n_results != len(excluded):
        e["reasons"].append("records were returned but not all are listed as excluded with a reason")
    e["status"] = "verified" if not e["reasons"] else "rejected"
    return e


# ------------------------------------------------------------------ ledger

class Ledger:
    def __init__(self, patient_id: str, branches: list[dict]):
        self.patient_id = patient_id
        self.branches = branches
        self.evidence: dict[str, dict] = {}
        self.sections_status = {s: "not_searched" for s in SECTIONS}
        self.patient_context: dict = {}
        self.missing_information: list[dict] = []
        self.rules_applied: list[dict] = []
        self.branch_assessment: list[dict] = []

    def add(self, e: dict) -> dict:
        if e["kind"] == "reasoning" and e["status"] == "candidate":
            bad = [p for p in e["premises"] if self.evidence.get(p, {}).get("status") != "verified"]
            e["reasons"] += [f"premise {p} missing or not verified" for p in bad]
            e["status"] = "verified" if not bad and e["premises"] else "rejected"
            if not e["premises"]:
                e["reasons"].append("reasoning without premises")
        self.evidence[e["id"]] = e
        return e

    def mark_searched(self, section: str) -> None:
        self.sections_status[section] = "searched"

    def in_section(self, section: str) -> list[dict]:
        return [e for e in self.evidence.values() if e["section"] == section and e["status"] == "verified"
                and e["kind"] != "negative" and e.get("action")]

    # ---- checks (contract section 8)
    def checks(self) -> list[dict]:
        out = []

        def chk(name, bad, detail_ok, level="fail"):
            out.append({"name": name, "status": level if bad else "pass",
                        "detail": "; ".join(map(str, bad[:8])) + (" …" if len(bad) > 8 else "") if bad else detail_ok})

        ev = list(self.evidence.values())
        branch_ids = {b["id"] for b in self.branches}
        chk("schema", [e["id"] for e in ev if e["kind"] not in KINDS or e["section"] not in TIERS
                       or e["tier"] != TIERS[e["section"]] or e["status"] not in STATUSES or not e["claim"]],
            f"{len(ev)} items well-formed")
        chk("applies_to_subset_of_branches", [e["id"] for e in ev if not set(e["applies_to"]) <= branch_ids
                                             or not e["applies_to"]], "all items name existing branches")
        chk("verified_sourced_have_quote_and_source",
            [e["id"] for e in ev if e["kind"] == "sourced" and e["status"] == "verified"
             and not (e["quote_verified"] and source_ok(e["source"]) and e["accessed_at"])],
            "every verified sourced item has a valid source id, a verbatim quote and an access time")
        chk("reasoning_premises_verified",
            [e["id"] for e in ev if e["kind"] == "reasoning" and e["status"] == "verified"
             and any(self.evidence.get(p, {}).get("status") != "verified" for p in e["premises"])],
            "every verified reasoning item rests on verified evidence")
        chk("llm_output_records_model",
            [e["id"] for e in ev if isinstance(e["produced_by"], dict)
             and not (e["produced_by"].get("served_model") and e["produced_by"].get("prompt_version"))],
            "LLM-produced items record the served model and prompt version")
        # one action, one section (key or 'implements')
        placed = [e for s in SECTIONS for e in self.in_section(s)]
        clash = sorted({f"{a['action']['key']} in {a['section']} and {b['section']}"
                        for i, a in enumerate(placed) for b in placed[i + 1:]
                        if a["section"] != b["section"] and same_action(a["action"], b["action"])})
        chk("one_action_one_section", clash, "no action appears in two sections")
        # empty searched section -> a verified negative for each branch
        gaps = []
        for s, st in self.sections_status.items():
            if st != "searched":
                continue
            for b in branch_ids:
                has_action = any(b in e["applies_to"] for e in self.in_section(s))
                has_neg = any(e["kind"] == "negative" and e["status"] == "verified" and e["section"] == s
                              and b in e["applies_to"] for e in ev)
                if not has_action and not has_neg:
                    gaps.append(f"{s} / {b}")
        chk("empty_section_has_negative_evidence", gaps,
            "every searched section has an action or a verified negative search for each branch")
        unknown = {c["variable"] for e in ev for c in e["conditions"] if not c.get("known")}
        listed = {m["variable"] for m in self.missing_information}
        chk("unknown_conditions_listed_as_missing", sorted(unknown - listed),
            "every unknown patient variable used in a condition is in missing_information")
        chk("umbrella_branches_expanded",
            [b["id"] for b in self.branches if b.get("umbrella") and not (b.get("expanded_from") or b.get("not_expandable"))],
            "no unexpanded umbrella branch")
        chk("drug_keys_normalized",
            [f"{e['action']['key']} ({e['section']})" for s in SECTIONS for e in self.in_section(s)
             if e["action"].get("normalized") is False], "all drugs normalized to RxNorm / ChEMBL", level="warn")
        return out

    def to_dict(self) -> dict:
        ev = sorted(self.evidence.values(), key=lambda e: (list(TIERS).index(e["section"]), e["id"]))
        return {"schema_version": SCHEMA_VERSION, "patient_id": self.patient_id, "branches": self.branches,
                "branch_assessment": self.branch_assessment, "patient_context": self.patient_context,
                "missing_information": self.missing_information, "rules_applied": self.rules_applied,
                "sections_status": self.sections_status,
                "sections": {s: [e["id"] for e in self.in_section(s)] for s in SECTIONS},
                "evidence": ev, "checks": self.checks()}

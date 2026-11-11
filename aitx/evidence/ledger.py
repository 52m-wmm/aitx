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

SCHEMA_VERSION = "evidence-ledger-v3"   # v2: requirement result not_assessed (3b contract); v3: requirement alternatives (rows)

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
ACTION_STATUSES = ("applicable", "not_applicable", "conditional", "searched_none")
REQ_KINDS = ("inclusion", "exclusion", "label_condition", "other")
# lines the context check adds or changes: scope / limit of the source (not patient variables), an exemption from an
# avoidance (decides nothing), a degree the patient's finding was not shown to reach (an ordinary unknown)
CONTEXT_LINE_KINDS = ("scope", "limit", "exemption", "degree")
PATIENT_STATUSES = ("satisfies", "does_not_satisfy", "unknown", "not_assessed")
ALTERNATIVE_GENE_NOTE = ("another gene, listed beside a criterion that names the patient's gene: read as alternatives, "
                         "not compared")
NOT_ASSESSED_NOTE = "screening assessment"   # administrative criteria (consent, adherence, visits): left to trial screening
AGE_BY_REGISTRY_NOTE = "age: decided by the registry age fields"   # 3b: text age clauses, shown, not compared
UNMAPPED_NOTE = "not mapped; shown verbatim"  # a criterion the mapping could not turn into a checked comparison (3b)

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
    # the quote is part of the identity: two passages behind the same claim are two items (2026-11-04: without it,
    # a later item with the same claim silently replaced an earlier one and a requirement pointed at the wrong quote)
    e["id"] = evidence_id(source.get("type"), source.get("id"), claim, section, (action or {}).get("key"), e["applies_to"],
                          _norm(quote))
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


# ------------------------------------------------------------ action records (contract 1.4)

def requirement_result(kind: str, patient_status: str) -> str:
    """pass / fail / unknown / not_assessed for one requirement line; exclusion criteria are inverted.
    not_assessed: an administrative criterion assessed at trial screening, never from the case."""
    if patient_status in ("unknown", "not_assessed"):
        return patient_status
    meets = patient_status == "satisfies"
    return ("fail" if meets else "pass") if kind == "exclusion" else ("pass" if meets else "fail")


def status_from(results: list[str]) -> str:
    """Branch status from its requirement results: any fail -> not applicable; else any unknown -> conditional.
    not_assessed results are ignored."""
    if "fail" in results:
        return "not_applicable"
    if "unknown" in results:
        return "conditional"
    return "applicable"


_RANK = {"applicable": 2, "conditional": 1, "not_applicable": 0}


def status_of(lines: list[dict], branch: str) -> tuple[str, str | None]:
    """(status, deciding alternative) for one branch. Lines without an `alternative` apply in every case; lines that
    share an `alternative` id are one alternative (e.g. one GeneReviews table row: "F508del homozygous"; another row:
    "F508del heterozygous + minimal function variant"). Any alternative met -> applicable; the best alternative decides.
    Without alternatives this is status_from() over all lines."""
    mine = [l for l in lines if branch in l["applies_to"]]
    common = [l["result"] for l in mine if not l.get("alternative")]
    alts: dict[str, list[str]] = {}
    for l in mine:
        if l.get("alternative"):
            alts.setdefault(l["alternative"], []).append(l["result"])
    if not alts:
        return status_from(common), None
    best = max(alts, key=lambda a: _RANK[status_from(common + alts[a])])
    return status_from(common + alts[best]), best


def requirement(rid: str, kind: str, text: str, evidence_id: str, patient_fact: dict | None, patient_status: str,
                applies_to: list[str], note: str = "", alternative: str | None = None) -> dict:
    if kind not in REQ_KINDS or patient_status not in PATIENT_STATUSES:
        raise ValueError(f"bad requirement kind/status {kind!r}/{patient_status!r}")
    out = {"id": rid, "kind": kind, "requirement": text, "requirement_evidence": evidence_id,
           "applies_to": sorted(applies_to), "patient_fact": patient_fact, "patient_status": patient_status,
           "result": requirement_result(kind, patient_status), "note": note}
    if alternative:
        out["alternative"] = alternative
    return out


def action_record(action_key: str | None, section: str, label: str, applies_to: list[str],
                  requirements: list[dict], evidence_ids: list[str], reasons: dict[str, str],
                  searched_none: bool = False) -> dict:
    """Status per branch is derived from the requirement lines (or searched_none); reasons: branch -> short text."""
    by_branch = {}
    for b in sorted(applies_to):
        st = "searched_none" if searched_none else status_of(requirements, b)[0]
        by_branch[b] = {"status": st, "reason": reasons.get(b, "")}
    return {"action_key": action_key, "section": section, "label": label, "applies_to": sorted(applies_to),
            "status_by_branch": by_branch, "requirements": requirements, "evidence_ids": evidence_ids}


# ------------------------------------------------------------------ ledger

class Ledger:
    def __init__(self, patient_id: str, branches: list[dict]):
        self.patient_id = patient_id
        self.branches = branches
        self.evidence: dict[str, dict] = {}
        self.sections_status = {s: "not_searched" for s in SECTIONS}
        self.bespoke_mechanism: dict[str, dict] = {}        # 3d: the mechanism each branch's judgements rest on
        self.bespoke_unassessable: list[dict] = []          # 3d: every "unable to assess" with its missing input
        self.repurposing_searches: dict[str, dict] = {}     # 3e: per branch, what was queried and what was excluded
        self.patient_context: dict = {}
        self.missing_information: list[dict] = []
        self.rules_applied: list[dict] = []
        self.rules_skipped: list[dict] = []
        self.branch_assessment: list[dict] = []
        self.branch_order: list[str] = [b["id"] for b in branches]
        self.actions: list[dict] = []
        self.dropped_conditions: list[dict] = []
        self.reextracted_rows: list[dict] = []
        self.supportive_tiers: dict = {}
        self.offlabel_searches: dict = {}            # 3c: per branch, PubMed search, papers and why each was not used             # fallback chain: tier, chapters, literature, symptoms, per branch     # 3a: table rows no extracted action covered, extracted again   # 3a: requirements refused by a code rule (text, rule, source)
        self.trial_searches: dict = {}         # 3b: per branch, every search, filtered study (with reason) and over-cap study

    def add(self, e: dict) -> dict:
        if e["kind"] == "reasoning" and e["status"] == "candidate":
            bad = [p for p in e["premises"] if self.evidence.get(p, {}).get("status") != "verified"]
            e["reasons"] += [f"premise {p} missing or not verified" for p in bad]
            e["status"] = "verified" if not bad and e["premises"] else "rejected"
            if not e["premises"]:
                e["reasons"].append("reasoning without premises")
        old = self.evidence.get(e["id"])
        if old is not None:
            if old.get("quote") != e.get("quote") or old.get("claim") != e.get("claim"):
                raise ValueError(f"evidence id {e['id']} already holds different content")
            return old
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
                # an action row for this branch also fills the section: 3d judgements rest on step 1 facts and
                # need no fetched evidence of their own (2026-11-06)
                has_action = any(b in e["applies_to"] for e in self.in_section(s)) or \
                    any(a["section"] == s and b in a.get("applies_to", []) for a in self.actions)
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
        chk("action_records_consistent", self._action_problems(), "every action record is traceable and consistent")
        if any(a["section"] == "off_label_expanded_access" for a in self.actions):
            from aitx.evidence import offlabel as O             # local import: offlabel imports this module
            chk("offlabel_consistent", O.problems(self.actions), "3c actions: valid precedents, efficacy summary, US status")
        if any(a["section"] == "bespoke_therapies" for a in self.actions):
            from aitx.evidence import bespoke as BS             # local import: bespoke imports this module
            chk("bespoke_consistent", BS.problems(self.actions, [b["id"] for b in self.branches if b.get("diagnosis")]),
                "3d: every branch has all six modality judgements, each with its reason")
        if any(a["section"] == "drug_repurposing" for a in self.actions) or self.repurposing_searches:
            from aitx.evidence import repurposing as RP      # local import: repurposing imports this module
            chk("repurposing_consistent",
                RP.problems(self.actions, [b["id"] for b in self.branches if b.get("diagnosis")],
                            {a.get("action_key"): a for a in self.actions if a.get("action_key")
                             and a["section"] != "drug_repurposing"}, self.repurposing_searches),
                "3e: every candidate's hops resolve, the direction addresses the mechanism, nothing is repeated")
        if self.supportive_tiers:
            from aitx.evidence import fallback as F            # local import: fallback imports this module
            present = {i for r in self.supportive_tiers.values() for i in r.get("present_ids") or []}
            chk("supportive_tiers_consistent", F.tier_problems(self.supportive_tiers, self.actions, present),
                "supportive actions carry their tier; tiers follow the fallback chain")
        chk("drug_keys_normalized",
            [f"{e['action']['key']} ({e['section']})" for s in SECTIONS for e in self.in_section(s)
             if e["action"].get("normalized") is False], "all drugs normalized to RxNorm / ChEMBL", level="warn")
        return out

    def _action_problems(self) -> list[str]:
        bad, branch_ids = [], {b["id"] for b in self.branches}
        missing = {m["variable"] for m in self.missing_information}
        for a in self.actions:
            tag = a.get("action_key") or f"{a['section']} (searched_none)"
            if a.get("modality") or a.get("hypothesis"):
                # 3d judges a therapeutic modality and 3e proposes a hypothesis about a drug; neither says whether
                # something fits this patient, so neither carries requirement lines or a per-branch status. Their
                # own checks (bespoke_consistent, repurposing_consistent) cover them. A 3d row has no action key;
                # a 3e row must have one, since it is a drug and has to be deduped against the other sections
                # (2026-11-06: the shared rule had refused every 3e row).
                what = a.get("modality") or a.get("label") or "hypothesis"
                if a.get("requirements") or not set(a["applies_to"]) <= branch_ids:
                    bad.append(f"{a['section']} {what}: must name existing branches and carry no requirement lines")
                if a.get("modality") and a.get("action_key"):
                    bad.append(f"{a['section']} {what}: a modality judgement carries no action key")
                if a.get("hypothesis") and not a.get("action_key"):
                    bad.append(f"{a['section']} {what}: a drug hypothesis needs an action key for deduplication")
                continue
            if not set(a["applies_to"]) <= branch_ids or set(a["status_by_branch"]) != set(a["applies_to"]):
                bad.append(f"{tag}: branches")
            for r in a["requirements"]:
                ev = self.evidence.get(r["requirement_evidence"]) or {}
                cc = r.get("context_check")         # lines the context check added or changed (2026-11-11)
                if cc and cc not in CONTEXT_LINE_KINDS:
                    bad.append(f"{tag}: requirement {r['id']} unknown context-check kind {cc!r}")
                if cc and not str(r.get("note") or "").count("context check:"):
                    bad.append(f"{tag}: requirement {r['id']} context-check line without its reason")
                verbatim = quote_in(r["requirement"], str(ev.get("quote", ""))) or (
                    cc == "limit" and quote_in(r["requirement"], str((a.get("context_check") or {}).get("passage", ""))))
                if ev.get("status") != "verified" or not (verbatim or cc == "scope"):
                    bad.append(f"{tag}: requirement {r['id']} not verbatim in verified evidence {r['requirement_evidence']}")
                if r["result"] != requirement_result(r["kind"], r["patient_status"]):
                    bad.append(f"{tag}: requirement {r['id']} result inconsistent")
                if cc == "exemption":
                    if r["result"] != "not_assessed":
                        bad.append(f"{tag}: requirement {r['id']} an exemption decides nothing (not_assessed)")
                    continue
                if cc in ("scope", "limit"):         # a limit of the source, not a missing patient variable
                    continue
                if r["result"] == "not_assessed":
                    if r["kind"] not in ("inclusion", "exclusion") or r.get("note") not in (NOT_ASSESSED_NOTE, UNMAPPED_NOTE, AGE_BY_REGISTRY_NOTE, ALTERNATIVE_GENE_NOTE) or r.get("patient_fact"):
                        bad.append(f"{tag}: requirement {r['id']} not_assessed must be a trial criterion noted "
                                   f"'{NOT_ASSESSED_NOTE}' with no patient fact")
                    continue
                if r["patient_status"] != "unknown" and not (r.get("patient_fact") or {}).get("quote"):
                    bad.append(f"{tag}: requirement {r['id']} has no quoted patient fact")
                if r["result"] == "unknown" and (r.get("patient_fact") or {}).get("field", r["id"]) not in missing:
                    bad.append(f"{tag}: unknown {(r.get('patient_fact') or {}).get('field', r['id'])} not in missing_information")
            for b, st in a["status_by_branch"].items():
                if st["status"] == "searched_none":
                    neg = [e for e in a["evidence_ids"] if self.evidence.get(e, {}).get("kind") == "negative"
                           and self.evidence[e]["status"] == "verified"]
                    if a.get("action_key") or not neg:
                        bad.append(f"{tag}: searched_none needs no action key and a verified negative search")
                elif st["status"] != status_of(a["requirements"], b)[0]:
                    bad.append(f"{tag}: status for {b} does not follow its requirements")
                if not st.get("reason"):
                    bad.append(f"{tag}: no reason for {b}")
        return bad

    def note_missing(self, variable: str, action: str, detail: str, asked_by: str) -> str:
        """One missing-information row per variable type (2026-11-04), listing every action that depends on it.
        Returns the variable name to put in the requirement line's patient_fact."""
        row = next((m for m in self.missing_information if m["variable"] == variable), None)
        if row is None:
            row = {"variable": variable, "why_it_matters": "", "affects": [], "details": [], "asked_by": asked_by}
            self.missing_information.append(row)
        row.setdefault("details", [])
        if action not in row["affects"]:
            row["affects"].append(action)
        if detail and detail not in row["details"]:
            row["details"].append(detail)
        if asked_by not in row["asked_by"].split(", "):
            row["asked_by"] += f", {asked_by}"
        n = len(row["affects"])
        row["why_it_matters"] = (f"{n} action{'s' if n > 1 else ''} depend{'' if n > 1 else 's'} on it: "
                                 + "; ".join(row["affects"][:12]) + (" …" if n > 12 else ""))
        return variable

    def to_dict(self) -> dict:
        ev = sorted(self.evidence.values(), key=lambda e: (list(TIERS).index(e["section"]), e["id"]))
        return {"schema_version": SCHEMA_VERSION, "patient_id": self.patient_id, "branches": self.branches,
                "branch_assessment": self.branch_assessment, "branch_order": self.branch_order,
                "patient_context": self.patient_context, "missing_information": self.missing_information,
                "rules_applied": self.rules_applied, "rules_skipped": self.rules_skipped,
                "sections_status": self.sections_status, "actions": self.actions, "trial_searches": self.trial_searches,
                "dropped_conditions": self.dropped_conditions, "reextracted_rows": self.reextracted_rows,
                "supportive_tiers": self.supportive_tiers, "offlabel_searches": self.offlabel_searches,
                "bespoke_mechanism": self.bespoke_mechanism, "bespoke_unassessable": self.bespoke_unassessable,
                "repurposing_searches": self.repurposing_searches,
                "sections": {s: [e["id"] for e in self.in_section(s)] for s in SECTIONS},
                "evidence": ev, "checks": self.checks()}

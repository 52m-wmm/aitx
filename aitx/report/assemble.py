"""Step 4: one case's report in markdown, from its ledger only (contract docs/step4_contract.md v1.0).

Step 4 presents and never judges: no status is changed, no entry is added, no source is re-read. Every fact (drug,
status, condition, number, quote) is filled by code from the ledger with fixed templates; the first version uses no
LLM (contract Q1). `assemble()` returns the markdown and a trace (which ledger record each line came from).
"""
from __future__ import annotations

import datetime as dt
import re
import textwrap
from collections import OrderedDict

from aitx.evidence import ledger as LG
from aitx.report.validate import HEADINGS, TITLE

CAPS = {"off_label_expanded_access": 5, "drug_repurposing": 3}
STALE_YEARS, STALE_YEARS_PRODUCT = 5, 3                    # contract Q7
PRODUCT = re.compile(r"\b(device|prosthes\w*|implant\w*|system|stimulator|pump)\b", re.I)
DIRECTION_RANK = {"reported_improvement": 0, "partial_improvement": 1, "inconsistent": 2, "insufficient": 3,
                  "combined_unattributable": 4, "not_reported": 5, "reported_ineffective": 9}
FURTHER = "{n} further {what} {verb} recorded in the evidence ledger and not listed here."
SUMMARY_VARIABLES = {"age", "sex", "kidney function", "liver function", "eGFR", "creatinine", "bilirubin",
                     "height", "weight", "gestational age", "current medication", "prior therapy",
                     "participation in other trials", "pregnancy status", "family history"}


# ------------------------------------------------------------------ small helpers

def status_of(a: dict) -> str:
    if "status_by_branch" in a and a["status_by_branch"]:
        sts = {v["status"] for v in a["status_by_branch"].values()}
        for s in ("applicable", "conditional", "searched_none", "not_applicable"):
            if s in sts:
                return s
    return a.get("classification") or ""


def written(a: dict) -> bool:
    """Entries the report writes (contract section 3): not not-applicable, not flagged report=false, not a
    non-recommendation, not an age band ruled out."""
    if a.get("report") is False:
        return False
    if any(r.get("context_check") == "recommendation" for r in a.get("requirements") or []):
        return False
    return status_of(a) in ("applicable", "conditional")


def unknown_lines(a: dict, branch: str | None = None) -> list[dict]:
    lines = a.get("requirements") or []
    resolved = set()
    for b in ([branch] if branch is not None else a["applies_to"]):
        options = {}
        for r in lines:
            if b in r["applies_to"] and r.get("alternative"):
                options.setdefault(r["alternative"], []).append(r["result"])
        if any(LG.status_from(results) == "applicable" for results in options.values()):
            resolved.add(b)
    return [r for r in lines if r["result"] == "unknown" and any(
        (branch is None or b == branch) and (not r.get("alternative") or b not in resolved)
        for b in r["applies_to"])]


def trial_rank(a: dict) -> tuple:
    lines = trial_lines(a)
    key_met = {r.get("fact") or (r.get("patient_fact") or {}).get("field") for r in lines if r["result"] == "pass"}
    return ({"RECRUITING": 0, "ENROLLING_BY_INVITATION": 1, "NOT_YET_RECRUITING": 2,
             "ACTIVE_NOT_RECRUITING": 3}.get(a.get("overall_status"), 4),
            any(r["result"] == "fail" for r in lines), -len(key_met & {"diagnosis", "age"}),
            sum(r["result"] in ("unknown", "not_assessed") for r in lines), a["label"])


def trial_lines(a: dict) -> list[dict]:
    """A satisfied any-of option removes competing options; shared requirements still apply."""
    lines = a["requirements"]
    chosen = {b: LG.status_of(lines, b) for b in a["applies_to"]}
    return [r for r in lines if any(not r.get("alternative") or st != "applicable" or r["alternative"] == alt
                                    for b, (st, alt) in chosen.items() if b in r["applies_to"])]


def variable_of(r: dict) -> str:
    f = (r.get("patient_fact") or {}).get("field") or "other"
    return {"source scope": "the source's scope", "usage situation": "the situation of use",
            "other": "other trial criteria",
            "manifestations not reported": "whether the patient has the manifestation it treats"}.get(f, f)


def clean(text: str, n: int | None = 240) -> str:
    import html
    text = re.sub(r"\s+", " ", html.unescape(str(text or ""))).strip()
    return text if n is None else textwrap.shorten(text, width=n, placeholder=" …", break_long_words=False, break_on_hyphens=False)


UNREPORTED = ("manifestations not reported", "whether the patient has the manifestation it treats", "manifestation")


def depends_on_unreported(a: dict) -> bool:
    """The entry waits on a complication or manifestation the case does not report (user decision 2026-11-15: such
    entries rank after every other entry)."""
    return any(r.get("target_symptom") or (r.get("patient_fact") or {}).get("field") in UNREPORTED
               for r in unknown_lines(a))


class Report:
    def __init__(self, led: dict, case: dict, date_of, safety: dict | None = None, today: dt.date | None = None):
        self.led, self.case, self.date_of, self.safety = led, case, date_of, safety or {}
        self.today = today or dt.date.today()
        self.ev = {e["id"]: e for e in led.get("evidence") or []}
        self.branches = {b["id"]: b for b in led.get("branches") or [] if b.get("diagnosis")}
        self.trace: list[dict] = []
        self.out: list[str] = []
        self.used_evidence: set[str] = set()

    def refs(self, ids) -> str:
        ids = list(dict.fromkeys(ids))
        for eid in ids:
            if self.ev[eid]["status"] != "verified":
                raise ValueError(f"report evidence {eid} is not verified")
        self.used_evidence.update(ids)
        return " ".join(f"[E:{eid}](#evidence-{eid})" for eid in ids)

    def action_ids(self, a: dict) -> list[str]:
        return [eid for eid in a.get("evidence_ids", []) if self.ev[eid]["status"] == "verified"]

    def variant_ids(self) -> list[str]:
        return [i for i, e in self.ev.items() if e.get("section") == "background"
                and (e.get("source", {}).get("upstream") or {}).get("type") == "refseq"]

    def count(self, items: list) -> list[str]:
        return [f"Listed actions: **{len(items)}**."]

    # -------------------------------------------------------------- citations
    def cite(self, e: dict, product: bool = False) -> str:
        src = e.get("source") or {}
        if src.get("type") == "pipeline_fact" and src.get("upstream"):
            src = dict(src["upstream"], url=src["url"])
        t, sid = src.get("type"), src.get("id")
        date = self.date_of(src, e)
        when = f"; updated {date}" if date else "; update date not recorded"
        stale = ""
        if date:
            try:
                y = int(str(date)[:4])
                limit = STALE_YEARS_PRODUCT if product else STALE_YEARS
                if self.today.year - y > limit:
                    stale = f" (source more than {limit} years old: may be out of date" + \
                            ("; check that the product is still available)" if product else ")")
            except ValueError:
                pass
        name = {"nbk": f"GeneReviews {sid}" + (f", {src.get('section')}" if src.get("section") else ""),
                "pmid": f"PMID {sid}", "nct": f"{sid}", "spl_setid": f"FDA label {sid}" +
                (f" ({src.get('brand')})" if src.get("brand") else ""),
                "url": f"Guideline {src.get('guideline') or sid}", "refseq": f"RefSeq {sid}",
                "clinvar_vcv": f"ClinVar {sid}"}.get(t, f"{t} {sid}")
        url = src.get("url")
        return f"[{name}{when}]" + (f"({url})" if url else "") + stale

    def sources(self, a: dict, k: int = 2) -> list[str]:
        product = bool(PRODUCT.search(a.get("label") or ""))
        if a["section"] == "clinical_trial_eligibility":     # the criteria are quoted in the entry; cite the record
            e = next((self.ev[i] for i in a.get("evidence_ids") or [] if i in self.ev), None)
            return [f"  - {self.cite(e)} {self.refs([e['id']])}"] if e else []
        lines = []
        shown = 0
        ids = list(dict.fromkeys(a.get("presentation_evidence_ids", []) + self.action_ids(a)))
        outcomes = {p["outcome_quote"] for p in a.get("precedents") or []
                    if p.get("direction") == "negative" and p.get("outcome_quote")}
        if a["section"] == "existing_targeted_therapies":
            ids = sorted(ids, key=lambda i: (self.ev[i].get("source") or {}).get("type") != "spl_setid")
        elif a.get("efficacy_direction") == "reported_ineffective":
            ids = sorted(ids, key=lambda i: self.ev[i]["quote"] not in outcomes)
        for i in ids:
            e = self.ev.get(i)
            if not e or e.get("kind") != "sourced" or e.get("quote") in (a.get("cautions") or []):
                continue                                   # a caution sentence is shown as a caution, not as support
            if shown >= k:
                break
            shown += 1
            lines.append(f"  - \"{clean(e['quote'], None)}\" {self.cite(e, product)} {self.refs([i])}")
        return lines

    def applies(self, a: dict) -> str:
        if len(self.branches) < 2:
            return ""
        labs = [self.branches[b]["diagnosis"]["label"] for b in a.get("applies_to") or [] if b in self.branches]
        return f" Applies to: {', '.join(labs)}." if labs else ""

    def entry(self, a: dict, section: str) -> list[str]:
        st = status_of(a)
        head = f"- **{a['label']}** — {st}."
        unk = unknown_lines(a)
        if st == "conditional" and unk:
            by = OrderedDict()
            for r in unk:
                by.setdefault(variable_of(r), []).append(clean(r["requirement"], 120))
            head += " Depends on " + "; ".join(f"{v} ({' / '.join(dict.fromkeys(t))})" for v, t in by.items()) + "."
        if a.get("access_route_label") and section == "off_label_expanded_access":
            head += f" Access: {a['access_route_label']}."
        head += self.applies(a) + " " + self.refs(self.action_ids(a))
        if a.get("conclusion") and section in ("off_label_expanded_access", "bespoke_therapies", "drug_repurposing"):
            head += f" {clean(a['conclusion'], 300)}"
        self.trace.append({"section": section, "label": a["label"], "action_key": a.get("action_key"),
                           "evidence_ids": a.get("evidence_ids") or []})
        lines = [head] + self.sources(a)
        if section == "off_label_expanded_access":
            for p in a.get("precedents") or []:
                for d in p.get("patient_description") or []:
                    ids = [i for i in self.action_ids(a) if LG.quote_in(d["quote"], self.ev[i].get("quote", ""))]
                    if ids:
                        lines.append(f"  - Precedent patient description (PMID {p['pmid']}): \"{clean(d['quote'], None)}\" {self.refs(ids)}")
        for c in a.get("cautions") or []:
            ids = [i for i in self.action_ids(a) if LG.quote_in(c, self.ev[i].get("quote", ""))]
            if ids:
                lines.append(f"  - Caution (same source): \"{clean(c, None)}\" {self.refs(ids)}")
        return lines

    def negative(self, section: str) -> list[str]:
        """Searched and found nothing (contract section 10): database, query, date, counts."""
        out = []
        acts = [a for a in self.led["actions"] if a["section"] == section and status_of(a) == "searched_none"]
        ids = list(dict.fromkeys(i for a in acts for i in a["evidence_ids"]))
        ids += [i for i, e in self.ev.items() if i not in ids and e.get("section") == section
                and e["kind"] == "negative" and e["status"] == "verified"]
        for i in ids:
            e = self.ev[i]
            s = e.get("search") or {}
            if s:
                day = dt.datetime.utcfromtimestamp(s["queried_at"]).date().isoformat()
                out.append(f"- Searched {s['database']} (query: {clean(s['query'], 160)}; {day}; "
                           f"{s['n_results']} results, {s['n_excluded']} excluded with reasons): "
                           f"nothing qualified. {clean(e['claim'], 300)} {self.refs([i])}")
            elif e.get("claim"):
                out.append(f"- {clean(e['claim'], 300)} {self.refs([i])}")
        for a in acts:
            self.trace.append({"section": section, "label": "searched_none", "action_key": None,
                               "evidence_ids": a.get("evidence_ids") or []})
        if ids:
            self.trace.append({"section": section, "label": "negative searches", "action_key": None, "evidence_ids": ids})
        return list(dict.fromkeys(out)) or (["- Search result not recorded; unable to assess."] if section == "drug_repurposing"
                                            else ["- No entry for this section in the evidence ledger."])

    # -------------------------------------------------------------- sections
    def actions(self, section: str) -> list[dict]:
        return [a for a in self.led["actions"] if a["section"] == section]

    def section(self, section: str, items: list[dict], cap: int | None, what: str) -> list[str]:
        items = [a for a in items if self.action_ids(a)]
        if not items:
            return self.count([]) + self.negative(section)
        shown = items[:cap] if cap else items
        out = self.count(shown)
        for a in shown:
            out += self.entry(a, section)
        if cap and len(items) > cap:
            out.append(FURTHER.format(n=len(items) - cap, what=what, verb="are") + " " +
                       self.refs([i for a in items[cap:] for i in self.action_ids(a)]))
        return out

    def targeted(self) -> list[str]:
        items = sorted([a for a in self.actions("existing_targeted_therapies") if written(a)],
                       key=lambda a: (status_of(a) != "applicable", len(unknown_lines(a))))
        out = self.section("existing_targeted_therapies", items, None, "entries")
        if not items:      # cross-reference (contract 6.1): disease-modifying drugs written under Supportive Management
            drugs = [a["label"] for a in self.actions("supportive_management") if written(a)
                     and str(a.get("action_key") or "").startswith("drug:")
                     and any("without Targeted Therapies" in v.get("reason", "") for v in a["status_by_branch"].values())]
            if drugs:
                out.append(f"- See Supportive Management for {', '.join(drugs)} (listed there by the source chapter, "
                           f"which has no Targeted Therapies section).")
        return out

    def supportive(self) -> list[str]:
        items = [a for a in self.actions("supportive_management") if written(a)]
        items.sort(key=lambda a: (status_of(a) != "applicable", len(unknown_lines(a))))
        return self.section("supportive_management", items, None, "supportive measures")

    def contraindications(self) -> list[str]:
        acts = self.actions("contraindications_precautions")
        items = [a for a in acts if written(a)]
        out = self.section("contraindications_precautions", items, None, "entries")
        # reported worsening or adverse effect (contract Q4) - from the 3c precaution candidates
        for bid, s in (self.led.get("offlabel_searches") or {}).items():
            for p in s.get("precaution_candidates") or []:
                ids = [i for i, e in self.ev.items() if e["status"] == "verified" and
                       e.get("source", {}).get("id") == p["pmid"] and LG.quote_in(p["quote"], e.get("quote", ""))]
                if ids:
                    out.append(f"- Caution for {p['drug']}: \"{clean(p['quote'], None)}\" {self.refs(ids)}")
        n_na = sum(1 for a in acts if a.get("action_key") and status_of(a) == "not_applicable")
        if n_na:
            out.append(FURTHER.format(n=n_na, what="entries", verb="do not apply to this patient and are") + " " +
                       self.refs([i for a in acts if status_of(a) == "not_applicable" for i in self.action_ids(a)]))
        return out or self.negative("contraindications_precautions")

    def trials(self) -> list[str]:
        items = [a for a in self.actions("clinical_trial_eligibility") if a.get("action_key") and
                 a.get("report") is not False and self.action_ids(a)]
        trials = sorted([a for a in items if a.get("study_type") == "interventional"], key=trial_rank)
        out = self.count(trials)
        if trials:
            out += ["| Trial | Already met | Unable to assess | Known exclusions | Recruitment status / verified |",
                    "| --- | --- | --- | --- | --- |"]
        def cell(text):
            return clean(text, None).replace("|", "\\|")
        def verified(a):
            times = [self.ev[i]["accessed_at"] for i in self.action_ids(a) if self.ev[i].get("accessed_at")]
            return dt.datetime.utcfromtimestamp(max(times)).date().isoformat() if times else "unknown"
        for a in trials:
            rs = trial_lines(a)
            groups = []
            for results in (("pass",), ("unknown", "not_assessed"), ("fail",)):
                group = [r for r in rs if r["result"] in results]
                groups.append("<br>".join(f"{cell(r.get('kind', 'condition'))}: &quot;{cell(r['requirement'])}&quot;"
                                          for r in group) or "None established from the recorded criteria")
            out.append(f"| **{cell(a['label'])}** {self.refs(self.action_ids(a))} | " + " | ".join(groups) +
                       f" | {a.get('overall_status') or 'unknown'}; verified {verified(a)} |")
            self.trace.append({"section": "clinical_trial_eligibility", "label": a["label"], "action_key": a["action_key"],
                               "evidence_ids": self.action_ids(a)})
        obs = sorted([a for a in items if a.get("study_type") == "observational"], key=trial_rank)
        if obs:
            out.append(f"- **Observational studies ({len(obs)})**: " + "; ".join(
                f"{a['label']} ({a.get('overall_status') or 'unknown'}; verified {verified(a)}) {self.refs(self.action_ids(a))}"
                for a in obs) + ".")
        return out if items else out + self.negative("clinical_trial_eligibility")

    def offlabel(self) -> list[str]:
        acts = [a for a in self.actions("off_label_expanded_access") if a.get("action_key")]
        neg = [a for a in acts if a.get("efficacy_direction") == "reported_ineffective"]
        items = [a for a in acts if written(a) and a not in neg]
        items.sort(key=lambda a: (DIRECTION_RANK.get(a.get("efficacy_direction"), 6), len(unknown_lines(a))))
        out = self.section("off_label_expanded_access", items, CAPS["off_label_expanded_access"], "drugs") \
            if items else []
        for a in neg:                                       # contract Q4
            if not self.action_ids(a):
                continue
            out.append(f"- **{a['label']}** — reported ineffective; not recommended. {self.refs(self.action_ids(a))}")
            out += self.sources(a, 1)
        if neg:
            shown = [a for a in items[:CAPS["off_label_expanded_access"]] if self.action_ids(a)] + neg
            out = [l for l in out if not l.startswith("Listed actions:")]
            out = self.count(shown) + out
        return out or self.negative("off_label_expanded_access")

    def bespoke(self) -> list[str]:
        acts = self.actions("bespoke_therapies")
        if not acts:
            return self.negative("bespoke_therapies")
        good = [a for a in acts if a.get("classification") in ("theoretically_possible", "eligible", "likely_eligible",
                                                                 "possibly_eligible")]
        bases = self.variant_ids()
        acts = [a for a in acts if self.action_ids(a) or bases]
        out = self.count(acts)
        for a in good + [a for a in acts if a not in good]:
            if a not in acts:
                continue
            ids = list(dict.fromkeys(self.action_ids(a) + bases))
            out.append(f"- **{a['label']}** — technical feasibility: unconfirmed." + self.applies(a) + " " + self.refs(ids))
            out.append("  - Patient variant and calculations: see the source-labelled facts in Summary.")
            # Only a premise with its own verified source may be stated as a fact. Code-only modality grades,
            # capacity thresholds and editing arguments do not supply a published technical source.
            for field, name in (("target_tissue", "Target tissue"), ("delivery", "Delivery method"),
                                ("human_precedent", "Human precedent"), ("technical_feasibility", "Technical feasibility")):
                supported = [self.ev[i] for i in self.action_ids(a) if self.ev[i].get("premise") == field]
                if supported:
                    out += [f"  - {name}: \"{clean(e['quote'], None)}\" {self.refs([e['id']])}" for e in supported]
                else:
                    out.append(f"  - {name}: unconfirmed (未确认; no supporting evidence ID recorded).")
            self.trace.append({"section": "bespoke_therapies", "label": a["label"], "action_key": None,
                               "evidence_ids": ids})
        return out

    def repurposing(self) -> list[str]:
        items = [a for a in self.actions("drug_repurposing") if a.get("hypothesis")]
        return self.section("drug_repurposing", items, CAPS["drug_repurposing"], "candidates") if items \
            else self.negative("drug_repurposing")

    def ranking(self) -> list[str]:
        out = ["**Outcome measures**:", "", "**Preclinical validation**:"]
        bases = self.variant_ids()
        for a in self.actions("bespoke_therapies"):
            ids = self.action_ids(a) + bases
            if not ids:
                continue
            out.append(f"- {a['label']}: verify the source-labelled patient facts in Summary before further assessment. "
                       f"Target tissue, delivery, technical validation and modality-specific outcome measures: "
                       f"unconfirmed (未确认). {self.refs(ids)}")
            for i in self.action_ids(a):
                if self.ev[i].get("premise") == "preclinical_validation":
                    out.append(f"  - \"{clean(self.ev[i]['quote'], None)}\" {self.refs([i])}")
            for i in bases:
                if self.ev[i]["source"]["id"].endswith(".transcript_layout.cds"):
                    out.append(f"  - Recorded calculation to verify: {self.ev[i]['claim']} {self.refs([i])}")
        if not bases:
            out.append("- Source-backed preclinical prerequisites are not recorded; unconfirmed (未确认).")
        out += ["", "**Safety**:"] + self.safety_measures()
        out += ["", "**Efficacy measures**:"] + self.outcome_measures("efficacy")
        out += ["", "**Ranking**:"]
        # Cross-references only: a modality without sourced technical premises cannot be promoted into a treatment.
        trials = sorted([a for a in self.actions("clinical_trial_eligibility") if written(a)
                         and a.get("study_type") == "interventional" and self.action_ids(a)], key=trial_rank)
        cands = [(depends_on_unreported(a), 0, len(unknown_lines(a)), a,
                  "human precedent with reported improvement; see Off-label or Expanded-Access Therapies")
                 for a in self.actions("off_label_expanded_access") if written(a) and self.action_ids(a)
                 and a.get("efficacy_direction") in ("reported_improvement", "partial_improvement")]
        cands += [(False, 1, i, a, "screening review; see Clinical Trial Eligibility for recruitment status, "
                   "known exclusions, met diagnosis/age criteria and unknown criteria") for i, a in enumerate(trials)]
        for n, (later, _, _, a, why) in enumerate(sorted(cands, key=lambda c: c[:3]), 1):
            out.append(f"{n}. **{a['label']}** — {why}" +
                       (" (depends on a manifestation the case does not report, so ranked after the others)" if later else "") +
                       f". {self.refs(self.action_ids(a))}")
        if not cands:
            out.append("- No source-backed trial ranking is recorded; unable to assess.")
        return out

    def safety_measures(self) -> list[str]:
        out = []
        for kind in ("warnings", "interactions", "contraindications"):
            for row in self.safety.get(kind, []):
                ids = row.get("evidence_ids", [])
                if ids:
                    out.append(f"- {row['drug']} ({kind}): \"{clean(row['quote'], None)}\" {self.refs(ids)}")
        for search in self.led.get("offlabel_searches", {}).values():
            for p in search.get("precaution_candidates", []):
                ids = [i for i, e in self.ev.items() if e["status"] == "verified" and
                       e.get("source", {}).get("id") == p["pmid"] and LG.quote_in(p["quote"], e.get("quote", ""))]
                if ids:
                    out.append(f"- Reported adverse event ({p['drug']}): \"{clean(p['quote'], None)}\" {self.refs(ids)}")
        out += self.outcome_measures("safety", empty=False)
        return out or ["- Source-backed safety measures are not recorded; unconfirmed (未确认)."]

    def outcome_measures(self, kind: str = "efficacy", empty: bool = True) -> list[str]:
        out = []
        for row in self.led.get("report_context", {}).get("outcomes", []):
            if row["kind"] != kind:
                continue
            e = self.ev[row["evidence_id"]]
            out.append(f"- {row['label']}: \"{clean(e['quote'], None)}\" {self.cite(e)} {self.refs([e['id']])}")
        return out or (["- Source-backed measures are not recorded; unconfirmed (未确认)."] if empty else [])

    def summary_action(self, a: dict) -> str:
        unk = unknown_lines(a)
        if a["section"] == "clinical_trial_eligibility":
            text = f"{a['label']} ({status_of(a)}; registry {a.get('overall_status') or 'unknown'}; "
            text += "screening conditions in Clinical Trial Eligibility)"
        elif status_of(a) == "conditional" and unk:
            text = f"If {clean(unk[0]['requirement'], None)}: {a['label']}"
            if len(unk) > 1:
                text += "; remaining conditions: " + "; ".join(clean(r["requirement"], None) for r in unk[1:])
        else:
            text = a["label"] + f" ({status_of(a)})"
        return text + ". " + self.refs(self.action_ids(a))

    def priority(self) -> list[str]:
        out = ["- **Priority actions**:", "- **Tier 1:**"]
        tt = [a for a in self.actions("existing_targeted_therapies") if written(a) and self.action_ids(a)]
        sup = [a for a in self.actions("supportive_management") if written(a) and status_of(a) == "applicable" and self.action_ids(a)]
        first = [a for a in tt if status_of(a) == "applicable"][:2] + sup[:1]
        first += [a for a in tt if a not in first]
        out += ["  - " + self.summary_action(a) for a in first[:3]] or ["  - Source-backed priority action not recorded; unable to assess."]
        out += ["- **Tier 2:**"]
        trials = sorted([a for a in self.actions("clinical_trial_eligibility") if written(a)
                         and a.get("study_type") == "interventional" and self.action_ids(a)], key=trial_rank)
        out += ["  - Screening review: " + self.summary_action(a) for a in trials[:3]] or ["  - Source-backed priority action not recorded; unable to assess."]
        out += ["- **Tier 3:**"]
        bases = self.variant_ids()
        research = [a for a in self.actions("bespoke_therapies") if a.get("classification") == "theoretically_possible"]
        for a in research[:3]:
            ids = self.action_ids(a) + bases
            if ids:
                out.append(f"  - Review source-backed premises for {a['label']}; technical feasibility, target tissue, "
                           f"delivery and human precedent unconfirmed (未确认); see Bespoke Therapies. {self.refs(ids)}")
        if not any(l.startswith("  - Review") for l in out):
            out.append("  - Source-backed technical premises not recorded; unconfirmed (未确认).")
        return out

    def variant_provenance(self) -> list[str]:
        out = []
        for i, e in self.ev.items():
            src = e.get("source", {})
            if src.get("type") != "pipeline_fact" or e["status"] != "verified":
                continue
            up = src.get("upstream", {})
            if up.get("type") == "clinvar_vcv" or (up.get("type") == "refseq" and
                    src["id"].endswith((".variant_class", ".nmd.prediction", ".transcript_layout.cds"))):
                out.append(f"- {clean(e['claim'], None)} {self.cite(e)} {self.refs([i])}")
        return out

    def summary(self) -> list[str]:
        out = self.priority()
        diagnoses = [e for e in self.ev.values() if e.get("section") == "background" and
                     e.get("source", {}).get("id", "").endswith("].label") and e["status"] == "verified"]
        if diagnoses:
            out.append("- **Diagnosis**: " + "; ".join(f"{e['claim']} {self.refs([e['id']])}" for e in diagnoses))
        out += self.variant_provenance()
        variables = OrderedDict()
        for m in self.led.get("missing_information") or []:
            var = "kidney function" if m["variable"] == "eGFR" else m["variable"]
            if var in SUMMARY_VARIABLES:
                variables.setdefault(var, []).extend(m["affects"])
        miss = [{"variable": v, "affects": list(dict.fromkeys(affects))} for v, affects in variables.items() if affects]
        miss = sorted(miss, key=lambda m: -len(m["affects"]))[:3]
        if miss:
            out.append("- **Most important missing information**:")
            for m in miss:
                n = len(m["affects"])
                var = variable_of({"patient_fact": {"field": m["variable"]}})
                ids = [i for a in self.led["actions"] if a["label"] in m["affects"] for i in self.action_ids(a)]
                out.append(f"  - {var}: {n} entr{'y' if n == 1 else 'ies'} depend on it "
                           f"({'<br>'.join(m['affects'])}). {self.refs(ids)}")
        s = self.safety
        if s.get("coverage"):
            out.append("- **Check before use** (coverage of FDA label text, not a comprehensive interaction database):")
            for row in s["coverage"]:
                if not row.get("evidence_ids"):
                    continue
                out.append(f"  - {row['drug']}: interactions — " +
                           ("label text checked against the named drugs" if row["interactions_checked"] else "未检查 (not checked)") +
                           "; contraindications — " + ("label text checked" if row["contraindications_checked"] else "未检查 (not checked)") +
                           ". Empty findings do not establish absence of risk. " + self.refs(row["evidence_ids"]))
        for row in s.get("contraindications", []):
            if row.get("none") and row.get("evidence_ids"):
                e = self.ev[row["evidence_ids"][0]]
                out.append(f"  - {row['drug']}: the label lists no contraindications {self.cite(e)} {self.refs(row['evidence_ids'])}")
        return out

    def build(self) -> str:
        body = {"## Summary": self.summary, "### Existing Targeted Therapies": self.targeted,
                "### Supportive Management": self.supportive,
                "### Contraindications & Precautions": self.contraindications,
                "### Clinical Trial Eligibility": self.trials,
                "### Off-label or Expanded-Access Therapies": self.offlabel,
                "### Bespoke Therapies": self.bespoke, "### Drug Repurposing": self.repurposing,
                "### Outcome Measures & Ranking": self.ranking}
        out = [TITLE.replace("AITX-XXXXX", self.case['id']), "",
               "Generated by code from the evidence ledger; every entry cites its source and the source's update date.",
               ""]
        for h in HEADINGS:
            out.append(h)
            if h in body:
                out += [""] + body[h]()
            out.append("")
        # References can be reused; each evidence ID is defined once in the evidence table.
        pending = list(self.used_evidence)
        while pending:
            for eid in self.ev[pending.pop()].get("premises", []):
                if eid not in self.used_evidence:
                    self.refs([eid])
                    pending.append(eid)
        out += ["#### Evidence table", ""]
        for eid in sorted(self.used_evidence):
            e = self.ev[eid]
            out += [f'<a id="evidence-{eid}"></a>',
                    f"- **Evidence ID: `{eid}`** — " + (self.cite(e) if e["kind"] == "sourced" else e["claim"])]
        return "\n".join(out).rstrip() + "\n"


def assemble(led: dict, case: dict, date_of, safety: dict | None = None, today: dt.date | None = None) -> tuple[str, list[dict]]:
    r = Report(led, case, date_of, safety, today)
    md = r.build()
    return md, r.trace


def drugs_for_safety(led: dict) -> list[dict]:
    """Every drug the report writes, with its FDA label set ids from the ledger (contract section 9)."""
    ev = {e["id"]: e for e in led.get("evidence") or []}
    out = []
    for a in led["actions"]:
        if a["section"] not in ("existing_targeted_therapies", "supportive_management", "off_label_expanded_access") \
                or not str(a.get("action_key") or "").startswith("drug:") or not written(a) \
                or a.get("efficacy_direction") == "reported_ineffective":       # written as "not recommended"
            continue
        ings = [i.get("name") for e in (ev.get(i) for i in a.get("evidence_ids") or []) if e
                for i in ((e.get("action") or {}).get("ingredients") or []) if i.get("name")]
        sids = {(ev[i].get("source") or {}).get("id") for i in a.get("evidence_ids") or []
                if i in ev and (ev[i].get("source") or {}).get("type") == "spl_setid"}
        fda = ((a.get("regulatory") or {}).get("fda") or {})          # 3c drugs carry their label set id
        if fda.get("approved") and fda.get("set_id"):
            sids.add(fda["set_id"])
        sids = sorted(sids)
        out.append({"label": a["label"], "names": sorted(set([a["label"]] + ings)), "set_ids": sids})
    return out

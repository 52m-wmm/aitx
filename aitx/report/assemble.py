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
from aitx.report.validate import HEADINGS

CAPS = {"clinical_trial_eligibility": 5, "off_label_expanded_access": 5, "drug_repurposing": 3,
        "supportive_management": 10}                      # contract Q6; targeted and contraindications uncapped
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
    return ({"interventional": 0, "observational": 1}.get(a.get("study_type"), 2), len(unknown_lines(a)),
            -max([int(re.sub(r"\D", "", p) or 0) for p in a.get("phases") or []] or [0]))


def variable_of(r: dict) -> str:
    f = (r.get("patient_fact") or {}).get("field") or "other"
    return {"source scope": "the source's scope", "usage situation": "the situation of use",
            "other": "other trial criteria",
            "manifestations not reported": "whether the patient has the manifestation it treats"}.get(f, f)


def clean(text: str, n: int | None = 240) -> str:
    import html
    text = re.sub(r"\s+", " ", html.unescape(str(text or ""))).strip()
    return text if n is None else textwrap.shorten(text, width=n, placeholder=" …", break_long_words=False, break_on_hyphens=False)


# outcome measures (user decision 2026-11-15): efficacy measures only - a disease marker or function, not safety counts,
# samples or registries (code filter on the registered wording)
EFFICACY = re.compile(r"\b(oxal\w*|glycol\w*|eGFR|GFR|creatinine|cystatin|urin\w*|plasma|serum|blood|level|levels|"
                      r"concentration|excretion|function|score|scale|progression|frequency|survival|change)\b", re.I)
NOT_EFFICACY = re.compile(r"\b(adverse events?|TEAEs?|safety|tolerability|samples?|registr\w*|biobank|enrol\w*|"
                          r"recruit\w*|pharmacokinetic\w*)\b", re.I)


UNREPORTED = ("manifestations not reported", "whether the patient has the manifestation it treats", "manifestation")


def depends_on_unreported(a: dict) -> bool:
    """The entry waits on a complication or manifestation the case does not report (user decision 2026-11-15: such
    entries rank after every other entry)."""
    return any(r.get("target_symptom") or (r.get("patient_fact") or {}).get("field") in UNREPORTED
               for r in unknown_lines(a))


class Report:
    def __init__(self, led: dict, case: dict, date_of, safety: dict | None = None, today: dt.date | None = None,
                 outcomes_of=None, surveillance_of=None):
        self.led, self.case, self.date_of, self.safety = led, case, date_of, safety or {}
        self.outcomes_of = outcomes_of or (lambda nct: [])
        self.surveillance_of = surveillance_of or (lambda nbk: [])
        self.today = today or dt.date.today()
        self.ev = {e["id"]: e for e in led.get("evidence") or []}
        self.branches = {b["id"]: b for b in led.get("branches") or [] if b.get("diagnosis")}
        self.trace: list[dict] = []
        self.out: list[str] = []

    # -------------------------------------------------------------- citations
    def cite(self, e: dict, product: bool = False) -> str:
        src = e.get("source") or {}
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
                "url": f"Guideline {src.get('guideline') or sid}"}.get(t, f"{t} {sid}")
        url = src.get("url")
        return f"[{name}{when}]" + (f"({url})" if url else "") + stale

    def sources(self, a: dict, k: int = 2) -> list[str]:
        product = bool(PRODUCT.search(a.get("label") or ""))
        if a["section"] == "clinical_trial_eligibility":     # the criteria are quoted in the entry; cite the record
            e = next((self.ev[i] for i in a.get("evidence_ids") or [] if i in self.ev), None)
            return [f"  - {self.cite(e)}"] if e else []
        lines = []
        shown = 0
        ids = a.get("evidence_ids") or []
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
            full = (a["section"] == "existing_targeted_therapies" and e["source"]["type"] == "spl_setid") \
                or (a.get("efficacy_direction") == "reported_ineffective" and e["quote"] in outcomes)
            lines.append(f"  - \"{clean(e.get('quote'), None if full else 240)}\" {self.cite(e, product)}")
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
        head += self.applies(a)
        if a.get("conclusion") and section in ("off_label_expanded_access", "bespoke_therapies", "drug_repurposing"):
            head += f" {clean(a['conclusion'], 300)}"
        self.trace.append({"section": section, "label": a["label"], "action_key": a.get("action_key"),
                           "evidence_ids": a.get("evidence_ids") or []})
        lines = [head] + self.sources(a)
        if section == "off_label_expanded_access":
            for p in a.get("precedents") or []:
                for d in p.get("patient_description") or []:
                    lines.append(f"  - Precedent patient description (PMID {p['pmid']}): {clean(d['quote'])}.")
        for c in a.get("cautions") or []:
            lines.append(f"  - Caution (same source): \"{clean(c)}\"")
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
                           f"nothing qualified. {clean(e['claim'], 300)}")
            elif e.get("claim"):
                out.append(f"- {clean(e['claim'], 300)}")
        for a in acts:
            if not a.get("evidence_ids"):
                reason = next(iter(a["status_by_branch"].values())).get("reason", "")
                out.append(f"- Searched; nothing found ({clean(reason, 200)}).")
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
        if not items:
            return self.negative(section)
        out, shown = [], items[:cap] if cap else items
        for a in shown:
            out += self.entry(a, section)
        if cap and len(items) > cap:
            out.append(FURTHER.format(n=len(items) - cap, what=what, verb="are"))
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
        return self.section("supportive_management", items, CAPS["supportive_management"], "supportive measures")

    def contraindications(self) -> list[str]:
        acts = self.actions("contraindications_precautions")
        items = [a for a in acts if written(a)]
        out = self.section("contraindications_precautions", items, None, "entries") if items else []
        # reported worsening or adverse effect (contract Q4) - from the 3c precaution candidates
        for bid, s in (self.led.get("offlabel_searches") or {}).items():
            for p in s.get("precaution_candidates") or []:
                out.append(f"- **{p.get('drug')}** — caution: {p.get('note')}.")
                out.append(f"  - \"{clean(p.get('quote'))}\" [PMID {p.get('pmid')}]({p.get('url')})")
        n_na = sum(1 for a in acts if a.get("action_key") and status_of(a) == "not_applicable")
        if n_na:
            out.append(FURTHER.format(n=n_na, what="entries", verb="do not apply to this patient and are") )
        return out or self.negative("contraindications_precautions")

    def trials(self) -> list[str]:
        items = [a for a in self.actions("clinical_trial_eligibility") if written(a)]
        items.sort(key=trial_rank)
        return self.section("clinical_trial_eligibility", items, CAPS["clinical_trial_eligibility"], "trials")

    def offlabel(self) -> list[str]:
        acts = [a for a in self.actions("off_label_expanded_access") if a.get("action_key")]
        neg = [a for a in acts if a.get("efficacy_direction") == "reported_ineffective"]
        items = [a for a in acts if written(a) and a not in neg]
        items.sort(key=lambda a: (DIRECTION_RANK.get(a.get("efficacy_direction"), 6), len(unknown_lines(a))))
        out = self.section("off_label_expanded_access", items, CAPS["off_label_expanded_access"], "drugs") \
            if items else []
        for a in items[:CAPS["off_label_expanded_access"]]:
            if (a.get("regulatory") or {}).get("supplement"):
                out.append(f"  - {a['label']}: not an FDA-approved drug; product quality and dose are not regulated.")
        for a in neg:                                       # contract Q4
            out.append(f"- **{a['label']}** — reported ineffective; not recommended.")
            out += self.sources(a, 1)
        return out or self.negative("off_label_expanded_access")

    def bespoke(self) -> list[str]:
        acts = self.actions("bespoke_therapies")
        if not acts:
            return self.negative("bespoke_therapies")
        good = [a for a in acts if a.get("classification") in ("theoretically_possible", "eligible", "likely_eligible",
                                                                 "possibly_eligible")]
        out = []
        variants = (self.led.get("patient_context") or {}).get("variants") or []
        for v in variants:
            out.append(f"- Variant facts: {v['gene']} {v['variant_cdna']} ({v['variant_class']}, {v['zygosity']}); "
                       f"NMD prediction: {v['nmd']}.")
        for a in good + [a for a in acts if a not in good]:
            conclusion = a["conclusion"]
            out.append(f"- **{a['label']}** — {clean(conclusion, None)}" + self.applies(a))
            facts = a.get("facts") or {}
            reasons = list(a.get("criteria_met") or [])
            reasons += [r for r in (a.get("failed_criterion"), facts.get("reason"), a.get("note")) if r]
            reasons += a.get("unassessable_reason") or []
            for reason in dict.fromkeys(reasons):
                if reason not in conclusion:
                    out.append(f"  - {clean(reason, None)}.")
            if a.get("modality") == "gene_replacement":
                out.append(f"  - Target organ: {facts.get('target_organ') or 'not recorded'}.")
            out += self.sources(a)
            self.trace.append({"section": "bespoke_therapies", "label": a["label"], "action_key": None,
                               "evidence_ids": a.get("evidence_ids") or []})
        return out

    def repurposing(self) -> list[str]:
        items = [a for a in self.actions("drug_repurposing") if a.get("hypothesis")]
        return self.section("drug_repurposing", items, CAPS["drug_repurposing"], "candidates") if items \
            else self.negative("drug_repurposing")

    def ranking(self) -> list[str]:
        """Fixed order, no weights (contract Q5): human precedent with improvement > enrollable trial > molecular
        feasibility > mechanism only; then fewer unknowns; then access route. One reason sentence each."""
        cands = []
        later = " (depends on a manifestation the case does not report, so ranked after the others)"
        for a in self.actions("off_label_expanded_access"):
            if written(a) and a.get("efficacy_direction") in ("reported_improvement", "partial_improvement"):
                u = depends_on_unreported(a)
                cands.append((u, 0, len(unknown_lines(a)), a["label"],
                              "human precedent with reported improvement (off-label)" + (later if u else "")))
        for a in self.actions("clinical_trial_eligibility"):
            if written(a) and a.get("study_type") == "interventional":
                u = depends_on_unreported(a)
                cands.append((u, 1, len(unknown_lines(a)), a["label"],
                              "open interventional trial the patient may enter" + (later if u else "")))
        for a in self.actions("bespoke_therapies"):
            if a.get("classification") in ("theoretically_possible", "eligible", "likely_eligible", "possibly_eligible"):
                cands.append((False, 2, 0 if a.get("premises_complete") else 1, a["label"],
                              "molecularly feasible for this variant; no product for it"
                              + ("" if a.get("premises_complete") else " (some premises could not be checked)")))
        for a in self.actions("drug_repurposing"):
            if a.get("hypothesis"):
                cands.append((False, 3, 0, a["label"], "mechanism-based hypothesis only"))
        out = ["**Outcome measures** (verbatim from the trials' registered primary outcomes and the GeneReviews "
               "surveillance section):"] + self.outcome_measures() + ["", "**Ranking**:"]
        if not cands:
            return out + ["- No Tier 2 or Tier 3 option qualified for ranking; see the sections above."]
        cands.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
        return out + [f"{i}. **{lab}** — {why}" + (f"; {n} unknown condition(s)" if n and tier < 2 else "") + "."
                      for i, (_, tier, n, lab, why) in enumerate(cands[:10], 1)]

    def outcome_measures(self) -> list[str]:
        """Code extraction, no LLM (user decision 2026-11-15): primary outcome measures of the trials the report lists,
        and the measured items in the GeneReviews Surveillance section of the chapters it cites."""
        out = []
        trials = [a for a in self.actions("clinical_trial_eligibility") if written(a)]
        trials.sort(key=trial_rank)
        for a in [a for a in trials[:CAPS["clinical_trial_eligibility"]] if a.get("study_type") == "interventional"]:
            for m in [m for m in self.outcomes_of(a.get("nct") or "") if EFFICACY.search(m) and not NOT_EFFICACY.search(m)][:2]:
                out.append(f"- {clean(m, 200)} [{a.get('nct')} primary outcome]({a.get('url') or ''})")
        nbks = []
        for a in self.led["actions"]:
            if a["section"] in ("existing_targeted_therapies", "supportive_management") and written(a):
                for i in a.get("evidence_ids") or []:
                    src = (self.ev.get(i) or {}).get("source") or {}
                    if src.get("type") == "nbk" and src.get("id") not in nbks:
                        nbks.append(src["id"])
        for nbk in nbks:
            date = self.date_of({"type": "nbk", "id": nbk}, None)
            for s in self.surveillance_of(nbk)[:8]:
                out.append(f"- \"{clean(s, 220)}\" [GeneReviews {nbk}, Management / Surveillance"
                           f"{'; updated ' + date if date else ''}](https://www.ncbi.nlm.nih.gov/books/{nbk}/)")
        self.trace.append({"section": "outcome_measures", "label": "outcome measures", "action_key": None,
                           "evidence_ids": []})
        return out or ["- No outcome measure is recorded for the entries above."]

    def priority(self) -> list[str]:
        """Highest-value actions first (user decision 2026-11-15): applicable Tier 1 targeted therapies, then the
        targeted therapies that hinge on one condition ("If <condition>: <drug>"), then applicable supportive measures
        that depend on nothing unreported."""
        out = []
        tt = [a for a in self.actions("existing_targeted_therapies") if written(a)]
        for a in [a for a in tt if status_of(a) == "applicable"]:
            out.append(f"  - {a['label']} (existing targeted therapy; applicable).")
        for a in [a for a in tt if status_of(a) == "conditional"]:
            unk = unknown_lines(a)
            if unk:
                out.append(f"  - If {clean(unk[0]['requirement'], 120)}: {a['label']} (existing targeted therapy)"
                           + (f"; also depends on {len(unk) - 1} more condition(s)" if len(unk) > 1 else "") + ".")
        sup = [a for a in self.actions("supportive_management") if written(a) and status_of(a) == "applicable"]
        for a in sup[:3]:
            out.append(f"  - {a['label']} (supportive management; applicable).")
        return ["- **Priority actions**:"] + out if out else []

    def summary(self) -> list[str]:
        out = self.priority()
        dx = [b["diagnosis"]["label"] for b in self.branches.values()]
        out.append(f"- **Diagnosis**: {'; '.join(dx) if dx else 'not established'}"
                   + (f" ({len(dx)} possible diagnoses; entries say which they apply to)" if len(dx) > 1 else "") + ".")
        g = self.case["patient"]["genotype"]
        out.append("- **Variant**: " + "; ".join(f"{v['gene']} {v['variant_cdna']} {v.get('variant_protein', '')} "
                                                 f"({v.get('zygosity')})" for v in g) + ".")
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
                out.append(f"  - {var}: {n} entr{'y' if n == 1 else 'ies'} depend on it "
                           f"({', '.join(m['affects'][:5])}{' …' if n > 5 else ''}).")
        s = self.safety
        if s.get("interactions") or s.get("contraindications") or s.get("not_checked"):
            out.append("- **Check before use** (FDA label text, verbatim):")
            for f in s.get("interactions") or []:
                out.append(f"  - {f['drug']} with {f['other']}: \"{clean(f['quote'])}\" "
                           f"[FDA label {f['set_id']}; effective {f.get('effective_date')}]({f['url']})")
            for f in s.get("contraindications") or []:
                if f.get("none"):                       # one conclusion, no fragment text (user decision 2026-11-15)
                    out.append(f"  - {f['drug']}: the label lists no contraindications "
                               f"[FDA label {f['set_id']}; effective {f.get('effective_date')}]({f['url']}).")
                else:
                    out.append(f"  - {f['drug']}: label contraindication: \"{clean(f['quote'])}\" "
                               f"[FDA label {f['set_id']}; effective {f.get('effective_date')}]({f['url']})")
            if s.get("not_checked"):
                out.append(f"  - No FDA label in the evidence ledger for {', '.join(s['not_checked'])}: "
                           f"interactions not checked.")
        counts = {sec: sum(1 for a in self.actions(sec) if written(a)) for sec in
                  ("existing_targeted_therapies", "supportive_management", "contraindications_precautions",
                   "clinical_trial_eligibility", "off_label_expanded_access")}
        out.append(f"- **Entries**: {counts['existing_targeted_therapies']} targeted, {counts['supportive_management']} "
                   f"supportive, {counts['contraindications_precautions']} contraindications / precautions, "
                   f"{counts['clinical_trial_eligibility']} trials, {counts['off_label_expanded_access']} off-label "
                   f"(applicable or conditional; caps per section apply below).")
        return out

    def build(self) -> str:
        body = {"## Summary": self.summary, "### Existing Targeted Therapies": self.targeted,
                "### Supportive Management": self.supportive,
                "### Contraindications & Precautions": self.contraindications,
                "### Clinical Trial Eligibility": self.trials,
                "### Off-label or Expanded-Access Therapies": self.offlabel,
                "### Bespoke Therapies": self.bespoke, "### Drug Repurposing": self.repurposing,
                "### Outcome Measures & Ranking": self.ranking}
        tier_note = {"## Tier 1: Established": "Evidence level: established (GeneReviews, FDA labels, guidelines).",
                     "## Tier 2: Emerging": "Evidence level: emerging (open trials, published off-label use).",
                     "## Tier 3: Hypothetical": "Evidence level: hypothetical (molecular and mechanistic reasoning)."}
        out = [f"# Actionability report: {self.case['id']}", "",
               "Generated by code from the evidence ledger; every entry cites its source and the source's update date.",
               ""]
        for h in HEADINGS:
            out.append(h)
            if h in tier_note:
                out += ["", tier_note[h]]
            if h in body:
                out += [""] + body[h]()
            out.append("")
        return "\n".join(out).rstrip() + "\n"


def assemble(led: dict, case: dict, date_of, safety: dict | None = None, today: dt.date | None = None,
             outcomes_of=None, surveillance_of=None) -> tuple[str, list[dict]]:
    r = Report(led, case, date_of, safety, today, outcomes_of, surveillance_of)
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

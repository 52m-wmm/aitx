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
from aitx.report.validate import HEADINGS, TITLE, sentences, source_identity

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
    """Present applicable/conditional entries unless an existing broader entry represents them."""
    if a.get("report") is False:
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
    key_met = {r.get("fact") or (r.get("patient_fact") or {}).get("field") for r in lines
               if r["result"] == "pass" and r["kind"] == "inclusion"}
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


def readable(text: str) -> str:
    return re.sub(r'\b(?:theoretically_possible|not_applicable|not_eligible|not_graded|unable_to_assess|likely_eligible|possibly_eligible|unlikely_eligible|likely_triggers|likely_escapes|loss_of_function|gain_of_function|dominant_negative|NOT_YET_RECRUITING|ENROLLING_BY_INVITATION|ACTIVE_NOT_RECRUITING)\b',
                  lambda m:m[0].replace('_',' '),text)


def display_label(text: str) -> str:
    return re.sub(r'\b(NCT\d{8})\s+\(\1\)',r'\1',text)


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
        self.ref_groups = OrderedDict()
        self.heading = "Summary"
        self.seen_quotes = {}

    def refs(self, ids, label: str | None = None, inline: bool = True) -> str:
        ids = list(dict.fromkeys(ids))
        for eid in ids:
            if self.ev[eid]["status"] != "verified":
                raise ValueError(f"report evidence {eid} is not verified")
        self.used_evidence.update(ids)
        mapping = ""
        if len(ids) > 3 or not inline:
            key = tuple(ids)
            if key not in self.ref_groups:
                name = display_label(label or self.heading)
                nct = re.search(r'\((NCT\d{8})\)$',name)
                self.ref_groups[key] = (f"G{len(self.ref_groups)+1}", nct[1] if nct else name)
            gid, _ = self.ref_groups[key]
            mapping = f" [full mapping {gid}](#mapping-{gid})"
        return (" ".join(f"[E:{eid}]" for eid in ids[:3]) + mapping) if inline else ""

    def quote_lines(self, text: str, ids: list[str], prefix: str = "  - ", citation: str = "") -> list[str]:
        """Keep the first full passage. If it overlaps an earlier quote, emit only new verbatim sentences."""
        text = clean(text, None)
        e = next(self.ev[i] for i in ids if LG.quote_in(text,clean(self.ev[i].get('quote',''),None)) or
                 LG.quote_in(text,clean(self.ev[i].get('display_quote',''),None)))
        if text==clean(e.get('quote',''),None) and 'display_quote' in e:text=e['display_quote']
        source = source_identity(e)
        seen = self.seen_quotes.setdefault(self.heading, set())
        parts, new = sentences(text), []
        for part in parts:
            key = (source, part)
            if key not in seen:
                seen.add(key)
                new.append(part)
        passages = [text] if len(new) == len(parts) else new
        return [f'{prefix}"{p}" {citation} {self.refs(ids, prefix)}'.rstrip() for p in passages]

    def action_ids(self, a: dict) -> list[str]:
        ids = a.get("evidence_ids", []) + [r["requirement_evidence"] for r in a.get("requirements", [])
                                          if "requirement_evidence" in r]
        return [eid for eid in dict.fromkeys(ids) if self.ev[eid]["status"] == "verified"]

    def variant_ids(self) -> list[str]:
        return [i for i, e in self.ev.items() if e.get("section") == "background"
                and e["status"] == "verified"
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

    def short_cite(self, e: dict) -> str:
        src=e['source']
        if src.get('type')=='pipeline_fact' and src.get('upstream'):src=src['upstream']
        return {'nbk':'GeneReviews '+src['id'],'spl_setid':'FDA label '+(src.get('brand') or src['id']),
                'pmid':'PMID '+src['id'],'nct':src['id'],'refseq':'RefSeq '+src['id'],
                'clinvar_vcv':'ClinVar '+src['id']}.get(src['type'],src['id'])

    def sources(self, a: dict, k: int = 2) -> list[str]:
        product = bool(PRODUCT.search(a.get("label") or ""))
        if a["section"] == "clinical_trial_eligibility":     # the criteria are quoted in the entry; cite the record
            e = next((self.ev[i] for i in a.get("evidence_ids") or [] if i in self.ev), None)
            return [f"  - {self.cite(e)} {self.refs([e['id']])}"] if e else []
        lines = []
        shown = 0
        ids = list(dict.fromkeys(a.get("presentation_evidence_ids", []) + a.get("evidence_ids", [])))
        outcomes = {p["outcome_quote"] for p in a.get("precedents") or []
                    if p.get("direction") == "negative" and p.get("outcome_quote")}
        if a["section"] == "existing_targeted_therapies":
            ids = sorted(ids, key=lambda i: (self.ev[i].get("source") or {}).get("type") != "spl_setid")
        elif a.get("efficacy_direction") == "reported_ineffective":
            ids = sorted(ids, key=lambda i: self.ev[i]["quote"] not in outcomes)
        for i in ids:
            e = self.ev.get(i)
            if not e or e.get("kind") != "sourced" or e.get("quote") in (a.get("cautions") or []) or i in a.get("pregnancy_note_evidence_ids",[]):
                continue                                   # a caution sentence is shown as a caution, not as support
            if shown >= k:
                break
            shown += 1
            lines += self.quote_lines(e['quote'], [i], citation=self.short_cite(e))
        return lines

    def applies(self, a: dict) -> str:
        if len(self.branches) < 2:
            return ""
        labs = [self.branches[b]["diagnosis"]["label"] for b in a.get("applies_to") or [] if b in self.branches]
        return f" Applies to: {', '.join(labs)}." if labs else ""

    def entry(self, a: dict, section: str) -> list[str]:
        st = status_of(a)
        head = f"- **{display_label(a['label'])}** — {st}."
        unk = unknown_lines(a)
        if st == "conditional" and unk:
            by = OrderedDict()
            for r in unk:
                by.setdefault(variable_of(r), []).append(clean(r["requirement"], 120))
            head += " Depends on " + "; ".join(f"{v} ({' / '.join(dict.fromkeys(t))})" for v, t in by.items()) + "."
            if any(r.get("check_votes_disagreed") for r in unk):
                head += " check votes disagreed; unknown."
        if a.get("access_route_label") and section == "off_label_expanded_access":
            head += f" Access: {a['access_route_label']}."
        head += self.applies(a) + " " + self.refs(self.action_ids(a), a['label'])
        if a.get("conclusion") and section in ("off_label_expanded_access", "bespoke_therapies", "drug_repurposing"):
            head += f" {clean(a['conclusion'], 300)}"
        self.trace.append({"section": section, "label": a["label"], "action_key": a.get("action_key"),
                           "evidence_ids": a.get("evidence_ids") or []})
        lines = [head] + self.sources(a)
        for eid in a.get("pregnancy_note_evidence_ids",[]):
            lines += self.quote_lines(self.ev[eid]['quote'],[eid],"  - Pregnancy management note: ")
        if section == "off_label_expanded_access":
            for p in a.get("precedents") or []:
                for d in p.get("patient_description") or []:
                    ids = [i for i in self.action_ids(a) if LG.quote_in(d["quote"], self.ev[i].get("quote", ""))]
                    if ids:
                        lines += self.quote_lines(d['quote'], ids, f"  - Precedent patient description (PMID {p['pmid']}): ")
        for c in a.get("cautions") or []:
            ids = [i for i in self.action_ids(a) if LG.quote_in(c, self.ev[i].get("quote", ""))]
            if ids:
                lines += self.quote_lines(c, ids, "  - Caution (same source): ")
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
        items=[a for a in self.led['actions'] if a['section']==section]
        if section=='clinical_trial_eligibility':
            return sorted(items,key=lambda a:({"interventional":0,"observational":1}.get(a.get('study_type'),2),trial_rank(a)))
        if section=='off_label_expanded_access':
            return sorted(items,key=lambda a:({"reported_improvement":0,"insufficient":1}.get(a.get('efficacy_direction'),2),-self.precedent_count(a)))
        return [a for _,a in sorted(enumerate(items),key=lambda pair:pair[1].get('source_order',[1000000,pair[0],0]))]

    def precedent_count(self, a: dict) -> int:
        return len({self.ev[i]['source']['id'] for i in self.action_ids(a)
                    if self.ev[i]['kind']=='sourced' and self.ev[i]['source']['type']=='pmid'})

    def shown(self, section: str) -> list[dict]:
        items=[a for a in self.actions(section) if a.get('report') is not False]
        if section=='bespoke_therapies':return items
        items=[a for a in items if self.action_ids(a)]
        if section=='clinical_trial_eligibility':return [a for a in items if a.get('action_key')]
        if section=='drug_repurposing':return [a for a in items if a.get('hypothesis')][:CAPS[section]]
        positive=[a for a in items if written(a) and a.get('efficacy_direction')!='reported_ineffective']
        if section=='off_label_expanded_access':
            return positive[:CAPS[section]]+[a for a in items if a.get('efficacy_direction')=='reported_ineffective']
        return positive

    def preventative(self, a: dict) -> bool:
        if a['section']=='contraindications_precautions':return True
        paths=[self.ev[i]['source'].get('section','') for i in self.action_ids(a)
               if self.ev[i]['kind']=='sourced' and self.ev[i]['source']['type']=='nbk' and i not in a.get('pregnancy_note_evidence_ids',[])]
        return a['section']=='supportive_management' and bool(paths) and all('prevention' in p.lower() for p in paths)

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
        items = self.shown('existing_targeted_therapies')
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
        items = self.shown('supportive_management')
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
            out += ["| Trial | Inclusion met | Exclusion ruled out | Unable to assess | Known exclusions | Status & verified date |",
                    "| --- | --- | --- | --- | --- | --- |"]
        def cell(text):
            return clean(text, None).replace("|", "\\|")
        def verified(a):
            times = [self.ev[i]["accessed_at"] for i in self.action_ids(a) if self.ev[i].get("accessed_at")]
            return dt.datetime.utcfromtimestamp(max(times)).date().isoformat() if times else "unknown"
        for a in trials:
            grouped = OrderedDict()
            for r in trial_lines(a):
                text = r['requirement']
                if r.get('fact') == 'age' and r['result'] == 'pass' and r.get('any_of'):
                    text = next(o['requirement'] for o in r['any_of'] if o['patient_status'] == 'satisfies')
                grouped.setdefault((r['kind'], text), []).append(r)
            cells = [[], [], [], []]
            passages = []
            for (kind, text), rows in grouped.items():
                results = [r['result'] for r in rows]
                result = next((v for v in ('fail','unknown','not_assessed','pass') if v in results))
                dest = 3 if result == 'fail' else 2 if result in ('unknown','not_assessed') else 1 if kind == 'exclusion' else 0
                passages.append((kind,text,dest))
            for kind,text,dest in passages:
                if any(k==kind and d==dest and text!=t and text in t for k,t,d in passages):
                    continue  # the complete original clause already contains this same-result fragment
                cells[dest].append('"'+cell(text)+'"')
            values = ['<br>'.join(g) or 'None established' for g in cells]
            link = f" [registry]({a['url']})" if a.get('url') else ''
            out.append(f"| **{cell(display_label(a['label']))}**{link} | " + ' | '.join(values) +
                       f" | {a.get('overall_status') or 'unknown'}; verified {verified(a)} {self.refs(self.action_ids(a),a['label'])} |")
            self.trace.append({'section':'clinical_trial_eligibility','label':a['label'],'action_key':a['action_key'],
                               'evidence_ids':self.action_ids(a)})
        obs = sorted([a for a in items if a.get('study_type') == 'observational'], key=trial_rank)
        if obs:
            out.append(f"- **Observational studies ({len(obs)})**: " + '; '.join(
                f"{a['label']}" + (f" [registry]({a['url']})" if a.get('url') else '') +
                f" ({a.get('overall_status') or 'unknown'}; verified {verified(a)})" for a in obs) + '. ' +
                self.refs([i for a in obs for i in self.action_ids(a)],'Observational studies'))
        return out if items else out + self.negative('clinical_trial_eligibility')

    def offlabel(self) -> list[str]:
        acts = [a for a in self.actions("off_label_expanded_access") if a.get("action_key")]
        neg = [a for a in acts if a.get("efficacy_direction") == "reported_ineffective"]
        items = [a for a in acts if written(a) and a not in neg]
        out = self.section("off_label_expanded_access", items, CAPS["off_label_expanded_access"], "drugs") \
            if items else []
        for a in neg:                                       # contract Q4
            if not self.action_ids(a):
                continue
            out.append(f"- **{a['label']}** — reported outcome. {self.refs(self.action_ids(a),a['label'])}")
            out += self.sources(a, 1)
        if neg:
            shown = [a for a in items[:CAPS["off_label_expanded_access"]] if self.action_ids(a)] + neg
            out = [l for l in out if not l.startswith("Listed actions:")]
            out = self.count(shown) + out
        return out or self.negative("off_label_expanded_access")


    def bespoke(self) -> list[str]:
        acts = self.actions('bespoke_therapies')
        if not acts:
            return self.negative('bespoke_therapies')
        bases = self.variant_ids()
        order = {'theoretically_possible':0,'eligible':1,'likely_eligible':2,'possibly_eligible':3,
                 'unlikely_eligible':4,'unable_to_assess':5,'not_eligible':6,'not_applicable':7,'not_graded':8}
        acts = sorted(acts,key=lambda a:order[a['classification']])
        out = self.count(acts)
        group = None
        for a in acts:
            if a['classification'] != group:
                group = a['classification']
                out.append(f"**{readable(group)}**")
            ids = self.action_ids(a) + bases
            head = f"- **{display_label(a['label'])}** — {readable(a['classification'])} (Step 3d code rule)."
            if a.get('failed_criterion'):
                head += ' Reason: '+a['failed_criterion']+'.'
            if a['classification'] != 'theoretically_possible':
                for field,name in (('exceptions','Exceptions'),('unassessable_reason','Unassessed')):
                    if a.get(field):head += ' '+name+': '+'; '.join(a[field])+'.'
                if a.get('note') and a['note'] not in a.get('unassessable_reason',[]):head += ' Note: '+readable(a['note'])
                out.append(head+' '+self.refs(ids,a['label']))
            else:
                out.append(head+' '+self.refs(ids,a['label']))
                out.append('  - '+a['conclusion'])
                for field,name in (('criteria_met','Criteria met'),('exceptions','Exceptions'),('unassessable_reason','Unassessed')):
                    for value in a.get(field,[]):out.append(f'  - {name}: {value}')
                if (a.get('provenance') or {}).get('code_only') is True and (a.get('facts') or {}).get('reason'):
                    out.append('  - Rule rationale: '+a['facts']['reason'])
                if a.get('note') and a['note'] not in a.get('unassessable_reason',[]):out.append('  - Note: '+readable(a['note']))
            self.trace.append({'section':'bespoke_therapies','label':a['label'],'action_key':None,'evidence_ids':ids})
        return out

    def repurposing(self) -> list[str]:
        items = [a for a in self.actions("drug_repurposing") if a.get("hypothesis")]
        return self.section("drug_repurposing", items, CAPS["drug_repurposing"], "candidates") if items \
            else self.negative("drug_repurposing")


    def ranking(self) -> list[str]:
        out = ['**Outcome measures**:', '', '**Preclinical validation**:']
        bases = self.variant_ids()
        methods = [a for a in self.actions('bespoke_therapies') if a['classification']=='theoretically_possible']
        for a in methods:
            out.append(f"- {a['label']} — {readable(a['classification'])}; verify its recorded Step 3d prerequisites. " +
                       self.refs(self.action_ids(a)+bases,a['label']))
            for reason in a.get('unassessable_reason',[]):out.append('  - Unassessed: '+reason)
            if a.get('note') and a['note'] not in a.get('unassessable_reason',[]):out.append('  - '+readable(a['note']))
            for eid in self.action_ids(a):
                if self.ev[eid].get('premise')=='preclinical_validation':
                    out += self.quote_lines(self.ev[eid]['quote'],[eid])
        if not methods:out.append('- No theoretically possible method is recorded in Step 3d.')
        out += ['', '**Safety**:'] + self.safety_measures()
        out += ['', '**Efficacy measures**:'] + self.outcome_measures('efficacy')
        out += ['', '**Ranking**:']
        candidates = []
        sections = ('existing_targeted_therapies','supportive_management','clinical_trial_eligibility',
                    'off_label_expanded_access','bespoke_therapies')
        for section in sections:
            for a in self.shown(section):
                if self.preventative(a) or a.get('efficacy_direction')=='reported_ineffective':continue
                if section=='bespoke_therapies' and a['classification']!='theoretically_possible':continue
                if section!='bespoke_therapies' and not written(a):continue
                why = section.replace('_',' ')+'; '+readable(status_of(a))
                if section=='off_label_expanded_access' and a.get('efficacy_direction'):
                    why += '; '+a['efficacy_direction'].replace('_',' ')
                if section=='clinical_trial_eligibility':
                    rank=trial_rank(a)
                    why += (f"; {readable(a.get('study_type') or 'unknown')}; {a.get('overall_status') or 'unknown'}; "
                            f"{'known exclusions present' if rank[1] else 'no known exclusions'}; "
                            f"{-rank[2]} key inclusion fields met; {rank[3]} unknown criteria")
                elif section=='off_label_expanded_access':
                    why += f'; independent precedent reports: {self.precedent_count(a)}'
                else:
                    why += '; '+('source position not recorded; ledger/collection order' if a.get('source_order_note') or 'source_order' not in a else 'source order')
                candidates.append((a,why))
        for n,(a,why) in enumerate(candidates,1):
            ids = self.action_ids(a) or bases
            self.refs(ids,a['label'],inline=False)
            label=display_label(a.get('nct') or a['label'])
            out.append(f"{n}. **{label}** — {why}. {self.refs(ids[:1])}")
        if not candidates:out.append('- Action ranking cannot be assessed from the recorded entries.')
        return out


    def safety_measures(self) -> list[str]:
        out = []
        for kind in ('warnings','interactions','contraindications'):
            for row in self.safety.get(kind,[]):
                ids = row.get('evidence_ids',[])
                if not ids:continue
                if kind=='contraindications' and row.get('none'):
                    out.append(f"- {row['drug']}: the label lists no contraindications. {self.refs(ids)}")
                    continue
                text = clean(row['quote'],None)
                # Selected complete sentences keep label warnings readable; the evidence table points to the full label.
                passages = sentences(text)[:3] if kind=='warnings' else [text]
                for passage in passages:
                    out += self.quote_lines(passage,ids,f"- {row['drug']} ({kind}; label passage): ")
        for search in self.led.get('offlabel_searches',{}).values():
            for p in search.get('precaution_candidates',[]):
                ids = [i for i,e in self.ev.items() if e['status']=='verified' and e.get('source',{}).get('id')==p['pmid']
                       and LG.quote_in(p['quote'],e.get('quote',''))]
                if ids:out += self.quote_lines(p['quote'],ids,f"- Reported adverse event ({p['drug']}): ")
        out += self.outcome_measures('safety',empty=False)
        return out or ['- Source-backed safety measures are not recorded; unconfirmed.']


    def outcome_measures(self, kind: str = 'efficacy', empty: bool = True) -> list[str]:
        out = []
        for row in self.led.get('report_context',{}).get('outcomes',[]):
            if row['kind']==kind:
                e = self.ev[row['evidence_id']]
                out += self.quote_lines(e['quote'],[e['id']],f"- {row['label']}: ",self.short_cite(e))
        return out or (['- Source-backed measures are not recorded; unconfirmed.'] if empty else [])

    def summary_action(self, a: dict) -> str:
        unk = unknown_lines(a)
        sources = a["evidence_ids"]
        labels = [i for i in sources if self.ev[i].get("source", {}).get("type") == "spl_setid"]
        ids = (labels or sources)[:1]
        if a["section"] == "clinical_trial_eligibility":
            text = f"{a.get('nct') or a['label']} ({status_of(a)}; {a.get('overall_status') or 'unknown'}; see trial criteria)"
        elif status_of(a) == "conditional" and unk:
            ids += [r["requirement_evidence"] for r in unk if "requirement_evidence" in r]
            text = f"If {clean(unk[0]['requirement'], None)}: {a['label']}"
            if len(unk) > 1:
                text += "; remaining conditions: " + "; ".join(clean(r["requirement"], None) for r in unk[1:])
        else:
            text = display_label(a['label']) + f" ({readable(status_of(a))})"
        return text + ". " + self.refs(ids)

    def priority(self) -> list[str]:
        out = ["- **Priority actions**:", "- **Tier 1:**"]
        first = [a for section in ('existing_targeted_therapies','supportive_management')
                 for a in self.shown(section) if not self.preventative(a)]
        if not first:first=self.shown('contraindications_precautions')
        first=sorted(first,key=lambda a:status_of(a)!='applicable')  # retain ranking order within each status
        out += ["  - "+self.summary_action(a) for a in first[:3]] or ["  - No priority treatment found in the recorded searches."]
        out += ["- **Tier 2:**"]
        second=[a for a in self.shown('clinical_trial_eligibility') if a.get('study_type')=='interventional']+self.shown('off_label_expanded_access')
        out += ["  - "+self.summary_action(a) for a in second[:3]] or ["  - No interventional trial or off-label entry found in the recorded searches."]
        out += ["- **Tier 3:**"]
        research=[a for a in self.shown('bespoke_therapies') if a['classification']=='theoretically_possible']
        if research:
            for a in research[:3]:
                ids=self.action_ids(a)+self.variant_ids()
                limitations=a.get('unassessable_reason',[]) or ([a['note']] if a.get('note') else [])
                out.append(f"  - {a['label']}: theoretically possible (Step 3d code rule); unassessed items: " +
                           ('; '.join(limitations) or 'not recorded; see Bespoke Therapies')+'. '+self.refs(ids,a['label']))
        else:
            assessed=self.shown('bespoke_therapies')+self.shown('drug_repurposing')
            out += ["  - Recorded assessment: "+a['label']+' — '+readable(status_of(a) or 'ungraded hypothesis')+'. '+
                    self.refs(self.action_ids(a)+self.variant_ids(),a['label']) for a in assessed[:3]] or ["  - No bespoke assessment or repurposing candidate found in the recorded searches."]
        return out

    def variant_provenance(self) -> list[str]:
        out = []
        for i, e in self.ev.items():
            src = e.get("source", {})
            if src.get("type") != "pipeline_fact" or e["status"] != "verified":
                continue
            up = src.get("upstream", {})
            if up.get("type") == "clinvar_vcv" or (up.get("type") == "refseq" and
                    src["id"].endswith((".variant_class", ".nmd.prediction", ".protein_length"))):
                out.append(f"- {readable(clean(e['claim'], None))} {self.short_cite(e)} {self.refs([i])}")
        return out

    def summary(self) -> list[str]:
        out = self.priority()
        diagnoses = [e for e in self.ev.values() if e.get("section") == "background" and
                     e.get("source", {}).get("id", "").endswith("].label") and e["status"] == "verified"]
        if diagnoses:
            out.append("- **Diagnosis**: " + "; ".join(f"{e['claim']} {self.refs([e['id']])}" for e in diagnoses))
        out += self.variant_provenance()
        shown_names={a['label'] for section in ('existing_targeted_therapies','supportive_management','contraindications_precautions','clinical_trial_eligibility','off_label_expanded_access','bespoke_therapies','drug_repurposing') for a in self.shown(section) if a.get('study_type')!='observational'}
        variables = OrderedDict()
        for m in self.led.get("missing_information") or []:
            var = "kidney function" if m["variable"] == "eGFR" else m["variable"]
            if var in SUMMARY_VARIABLES:
                variables.setdefault(var, []).extend(name for name in m["affects"] if name in shown_names)
        miss = [{"variable": v, "affects": list(dict.fromkeys(affects))} for v, affects in variables.items() if affects]
        miss = sorted(miss, key=lambda m: -len(m["affects"]))[:3]
        if miss:
            out.append("- **Most important missing information**:")
            for m in miss:
                n = len(m["affects"])
                var = variable_of({"patient_fact": {"field": m["variable"]}})
                ids = [r['requirement_evidence'] for a in self.led['actions'] if a['label'] in m['affects']
                       for r in unknown_lines(a) if 'requirement_evidence' in r and
                       ('kidney function' if (r.get('patient_fact') or {}).get('field')=='eGFR'
                        else (r.get('patient_fact') or {}).get('field')) == m['variable']]
                out.append(f"  - {var}: {n} entr{'y' if n == 1 else 'ies'} depend on it "
                           f"({'<br>'.join(display_label(name) for name in m['affects'])})."
                           + self.refs(ids, 'Missing information: '+var, inline=False))
        s = self.safety
        if s.get("coverage"):
            out.append("- **Check before use**: FDA interaction text was checked against the named drugs where recorded; "
                       "empty findings do not establish absence of risk. Coverage:")
            for row in s["coverage"]:
                if not row.get("evidence_ids") or row["drug"] not in shown_names:
                    continue
                out.append(f"  - {row['drug']}: interactions — " +
                           ("checked" if row["interactions_checked"] else "not checked") +
                           "; contraindications — " + ("checked" if row["contraindications_checked"] else "not checked") +
                           ". " + self.refs(row["evidence_ids"]))
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
            self.heading = h
            out.append(h)
            if h in body:
                out += [""] + body[h]()
            out.append("")
        # Full relationships live here; the body exposes at most three IDs per line.
        pending = list(self.used_evidence)
        while pending:
            eid = pending.pop()
            parents = self.ev[eid].get('premises',[])
            new = [p for p in parents if p not in self.used_evidence]
            if parents:self.refs(parents,'Premises of E:'+eid,inline=False)
            pending.extend(new)
        out += ['**Evidence table**','']
        for ids,(gid,label) in self.ref_groups.items():
            out.append(f'- <a id="mapping-{gid}"></a>**{gid}**: {clean(label,None)}')
            for start in range(0,len(ids),3):
                out.append('  - '+' '.join(f'`E:{i}`' for i in ids[start:start+3]))
        by_source = OrderedDict()
        for eid in sorted(self.used_evidence):
            e = self.ev[eid]
            key = source_identity(e) if e['kind']=='sourced' else (e['kind'],e['search']['database'],e['search']['endpoint']) if e['kind']=='negative' else (e['kind'],)
            by_source.setdefault(key,[]).append(eid)
        for key,ids in by_source.items():
            e = self.ev[ids[0]]
            if e['kind']=='sourced':label=self.cite(e)
            elif e['kind']=='negative':label='Search record: '+e['search']['database']
            else:label='Ledger reasoning; premise mappings are listed above.'
            out.append('- '+label)
            for start in range(0,len(ids),3):
                out.append('  - '+'; '.join(f'**E:{i}**' for i in ids[start:start+3]))
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

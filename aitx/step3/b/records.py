"""Step 3b production entry: full-context Conflict-Only screening and Python-owned verdicts.

The per-record assembler remains for saved-result replay and criterion regression tests.
"""
from __future__ import annotations

import re
import copy
import json

from aitx import caseinput
from aitx.evidence import actions as A
from aitx.step3.b import criteria as C
from aitx.evidence import patient_matching as E
from aitx.evidence import ledger as LG
from aitx.evidence import trials as T

SECTION = "clinical_trial_eligibility"


def refresh_trials(previous: dict, case: dict, step1: dict, step2: dict) -> dict:
    """Refresh only 3b, explicitly preserving the accepted outputs of other sections."""
    if previous['schema_version'] != LG.SCHEMA_VERSION or previous['patient_id'] != case['id']:
        raise ValueError('Expected the same case and current Ledger schema')
    led = LG.Ledger(case['id'], previous['branches'])
    for name in vars(led):
        if name == 'evidence':
            led.evidence = {e['id']: copy.deepcopy(e) for e in previous['evidence']}
        else:
            setattr(led, name, copy.deepcopy(previous[name]))
    frozen_actions = [a for a in led.actions if a['section'] != SECTION]
    retained_context = json.dumps(frozen_actions + [e for e in previous['evidence'] if e['section'] != SECTION], ensure_ascii=False)
    led.evidence = {eid: e for eid, e in led.evidence.items() if e['section'] != SECTION or eid in retained_context}
    led.actions = list(frozen_actions)
    led.missing_information = [m for m in led.missing_information if m['asked_by'] != '3b']
    add_trials(led, case, step1, step2)
    result = led.to_dict()
    if [a for a in result['actions'] if a['section'] != SECTION] != frozen_actions:
        raise ValueError('A frozen non-3b action changed')
    result['report_context'] = copy.deepcopy(previous['report_context'])
    result['branches_dropped'] = copy.deepcopy(previous['branches_dropped'])
    result['refresh_scope'] = {'updated': ['3b'], 'reused': ['step1', 'step2', '3a', '3c', '3d', '3e', 'report_context']}
    result['ok'] = all(c['status'] != 'fail' for c in result['checks'])
    return result


def confirmed(branch: dict, step1: dict, step2: dict) -> bool:
    """Step 2 resolved this branch as the diagnosis, the branch gene carries the patient's variant, and a ClinVar
    record of exactly that variant used for ranking is pathogenic or likely pathogenic (user decision 2026-11-15)."""
    p = step2.get("primary") or {}
    genes = {v.get("gene") for v in (step1 or {}).get("variants") or []}
    path = any(rec.get("used_for_ranking") and "athogenic" in str(rec.get("clinical_significance") or "")
               and "onflicting" not in str(rec.get("clinical_significance") or "")
               for cv in step2.get("clinvar") or [] for rec in cv.get("records") or [])
    return p.get("status") == "resolved" and p.get("id") == branch.get("id") and branch.get("gene") in genes and path


def confirmed_target_gene(branch: dict, case: dict, step1: dict, step2: dict) -> bool:
    """For target matching, an explicit named genetic diagnosis is also known evidence."""
    if confirmed(branch, step1, step2):
        return True
    primary = step2['primary']
    gene = branch['gene']
    return (primary['status'] == 'resolved' and primary['id'] == branch['id']
            and gene in {v['gene'] for v in step1['variants']}
            and re.search(rf'\b(?:diagnosed with|diagnosis of)\s+{re.escape(gene)}\s+deficiency\b',
                          caseinput.clinical_context(case), re.I) is not None)


def add_trials(led: LG.Ledger, case: dict, step1: dict, step2: dict, *, use_cache: bool = True) -> None:
    """Production default: full-context Conflict-Only screening, Python-owned verdicts."""
    from aitx.step3.b.screening import add_trials as screen
    screen(led, case, step1, step2, use_cache=use_cache)


def _record(led, study, bs: dict, mapped: dict | None, pf, extra, by_id, step2) -> None:
    nct, branches = study["nct"], sorted(bs)
    src = {"type": "nct", "id": nct, "url": T.study_url(nct)}
    crit_text = T.unescape(study.get("criteria") or "")
    reg_text = C.registry_source(study)
    produced = (mapped or {}).get("produced_by") or "code"
    lines, reasons, details = [], {}, {}
    population_evidence = set()

    def ev_for(text: str, kind: str, registry: bool, code_only: bool = False, source_text: str | None = None):
        source_text = source_text if source_text is not None else reg_text if registry else crit_text
        claim = f"{nct} {'registry field' if registry else kind + ' criterion'}: {text[:120]}"
        return led.add(LG.sourced(claim, SECTION, branches, src, text, source_text, study.get("_accessed_at") or 1,
                                  produced_by="code" if registry or code_only else produced, retrieved_by="3b clinicaltrials.gov",
                                  action={"key": A.trial_key(nct)}))

    for b in branches:
        bl = C.registry_lines(study, pf)
        if bs[b] == "analysed" and mapped:
            bl += C.lines_for(study, mapped, pf, extra, by_id[b], E.disease_names(by_id[b], step2))
        else:
            bl += C.enrollment_note_lines(study, pf)
        if ('confirmed' in by_id[b] and by_id[b]['confirmed']) or ('target_gene_confirmed' in by_id[b] and by_id[b]['target_gene_confirmed']):
            genes = list(dict.fromkeys(x['gene'] for x in by_id.values()
                                      if ('confirmed' in x and x['confirmed']) or ('target_gene_confirmed' in x and x['target_gene_confirmed'])))
            conflict = C.single_target_conflict(study, genes)
            if conflict is not None:
                variant = next(v for v in pf['variants'] if v['gene'] == by_id[b]['gene'])
                bl.append({'kind': 'inclusion', 'text': conflict['trial_rule_quote'],
                           'patient_status': 'does_not_satisfy',
                           'patient_fact': {'field': 'molecular target', 'value': variant['gene'],
                                            'quote': variant['quote'], 'step': 1},
                           'note': conflict['reason'], 'details': {'molecular_target_conflict': conflict},
                           'item': 'code:molecular-target', 'fact': 'genetic_confirmation'})
        for x in bl:
            ev = ev_for(x["text"], x["kind"], x["item"].startswith("registry:"),
                        bool(x.get("details", {}).get("enrollment_note") or x.get("details", {}).get("reviewed_rejections")
                             or x.get('details', {}).get('molecular_target_conflict')),
                        study['title'] if x.get('details', {}).get('molecular_target_conflict', {}).get('quote_source') == 'title' else None)
            line = LG.requirement(f"r{len(lines) + 1}", x["kind"], x["text"], ev["id"], x["patient_fact"],
                                  x["patient_status"], [b], x["note"], alternative=x.get('alternative'))
            for k in ("any_of", "fact", "item"):
                if x.get(k):
                    line[k] = x[k]
            if x.get("details"):
                line["details"] = dict(x["details"])
            if 'population_relation' in x.get('details', {}):
                sources = []
                for proof in x['details']['population_relation']['sources']:
                    context = '\n'.join(g['description'] for g in study['population_groups'] if 'description' in g)
                    evidence = ev_for(proof['quote'], 'population relation', False, True, context)
                    population_evidence.add(evidence['id'])
                    sources.append(dict(proof, evidence_id=evidence['id']))
                line['details']['population_relation'] = dict(x['details']['population_relation'], sources=sources)
            if line["result"] == "unknown":
                field = (x["patient_fact"] or {}).get("field") or "other"
                var = E.variable_type(field)                  # one row per variable type, listing the trials
                line["patient_fact"] = dict(x["patient_fact"] or {"value": None, "quote": None, "step": None},
                                            field=var, detail=field)
                led.note_missing(var, f"{study.get('acronym') or nct} ({nct})", x["text"][:120], "3b")
            lines.append(line)
        mine = [l for l in lines if b in l["applies_to"]]
        _, chosen = LG.status_of(mine, b)
        if chosen and LG.status_from([l['result'] for l in mine if l.get('alternative')==chosen]) == 'applicable':
            mine = [l for l in mine if not l.get('alternative') or l['alternative']==chosen]
        fail = [l for l in mine if l["result"] == "fail"]
        unk = [l for l in mine if l["result"] == "unknown"]
        reasons[b] = (("excluded: " if fail[0]["kind"] == "exclusion" else "not met: ")
                      + (fail[0]["requirement"] if fail[0].get("details", {}).get("enrollment_note") else fail[0]["requirement"][:80]) if fail
                      else "depends on: " + "; ".join(sorted({(l.get("patient_fact") or {}).get("field") or l["requirement"][:30]
                                                             for l in unk}))[:110] if unk
                      else "registry and assessed criteria met" + (" (registry only; not analysed)" if bs[b] != "analysed" else ""))
        target_failure = next((l for l in fail if l.get('details', {}).get('molecular_target_conflict')), None)
        if target_failure is not None:
            reasons[b] = target_failure['note']
    evs = sorted({l["requirement_evidence"] for l in lines} | population_evidence)
    if not evs:                                   # a study without lines still needs its registry evidence
        evs = [ev_for(C.registry_text(study, "age"), "inclusion", True)["id"]]
    label = f"{study.get('acronym') or study.get('title') or nct} ({nct})"
    rec = LG.action_record(A.trial_key(nct), SECTION, label, branches, lines, evs, reasons)
    rec.update(nct=nct, url=T.study_url(nct), title=study.get("title"), study_type=study.get("study_type"),
               interventions=study.get("interventions") or [],
               overall_status=study.get("status"), phases=study.get("phases"), relevance=study.get("relevance"),
               specific=study.get("specific"), analysed_in=[b for b in branches if bs[b] == "analysed"])
    if 'protocolSection' in study:
        rec['protocolSection'] = study['protocolSection']
        classification = T.classify_pathway(study['protocolSection'])
        rec['pathway'] = {**classification,
                          'known_conditions': list(dict.fromkeys(l['requirement'] for l in lines if l['result'] == 'pass')),
                          'pending_prerequisites': list(dict.fromkeys(l['requirement'] for l in lines if l['result'] == 'unknown')),
                          'status': ('治疗性干预研究；需核实开放队列及完整资格' if classification['therapeutic'] else
                                     '诊断性测定/生物标志物研究' if classification['category_rank'] == 2 else
                                     '观察性/自然史研究' if classification['category_rank'] == 3 else '研究性质待核实'),
                          'target_path_supported': False,
                          'cohort_note': '具体队列及剩余资格须由研究团队核实'}
    if mapped:
        rec["mapping_rejected"] = [{"id": m.get("id"), "quote": m.get("quote"), "why": m["rejected"]} for m in mapped["rejected"]]
    led.actions.append(rec)

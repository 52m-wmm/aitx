"""Step 3b: Clinical Trial Eligibility in the ledger (contract docs/step3b_contract.md, steps 1-8).

Per branch: trials.plan_branch (retrieval, status groups, relevance, prefilter, ranking, cap K) -> for the analysed
studies criteria.map_study (one LLM call per study) and code comparison -> one action record per trial
(`trial:NCT...`) with every criterion line, its verbatim evidence and the result. Studies the registry age / sex
rules out are recorded as not applicable without an LLM call. Every search, every filtered study (with the reason)
and every study over the cap are kept in the ledger's trial_searches; a branch with no trial gets searched_none and
negative evidence.
"""
from __future__ import annotations

from aitx.evidence import actions as A
from aitx.evidence import criteria as C
from aitx.evidence import established as E
from aitx.evidence import ledger as LG
from aitx.evidence import patient_facts as PFX
from aitx.evidence import trials as T

SECTION = "clinical_trial_eligibility"


def add_trials(led: LG.Ledger, case: dict, step1: dict, step2: dict, *, use_cache: bool = True) -> None:
    pf = E.facts(step1, step2)
    extra = led.patient_context.get("extra_facts") or PFX.extract(case, use_cache=use_cache)
    led.patient_context["extra_facts"] = extra
    plans, studies, in_branch = {}, {}, {}
    for b in [b for b in led.branches if b.get("diagnosis")]:
        names = E.disease_names(b, step2)
        plans[b["id"]] = p = T.plan_branch(names, b.get("gene"), pf["age_months"], pf["sex"], use_cache=use_cache)
        when = min([s["queried_at"] for s in p["searches"]] or [0])
        for st, how in [(s, "analysed") for s in p["analysed"]] + [(s, "ineligible") for s in p["ineligible"]]:
            studies.setdefault(st["nct"], {**st, "_accessed_at": when})
            in_branch.setdefault(st["nct"], {})[b["id"]] = how
    mapped = {nct: C.map_study(studies[nct], use_cache=use_cache) for nct, bs in in_branch.items()
              if "analysed" in bs.values()}
    by_id = {b["id"]: b for b in led.branches}
    for nct, bs in sorted(in_branch.items()):
        _record(led, studies[nct], bs, mapped.get(nct), pf, extra, by_id, step2)
    led.mark_searched(SECTION)
    trial_branches = {b for bs in in_branch.values() for b in bs}
    led.trial_searches = {bid: {k: v for k, v in p.items() if k not in ("analysed", "ineligible")}
                          | {"analysed": [s["nct"] for s in p["analysed"]], "ineligible": [s["nct"] for s in p["ineligible"]]}
                          for bid, p in plans.items()}
    for bid, p in plans.items():
        if bid in trial_branches:
            continue
        s0 = p["searches"][0] if p["searches"] else {}
        neg = led.add(LG.negative(SECTION, [bid], database="clinicaltrials.gov", endpoint=T.API,
                                  query="; ".join(str(s["query"]) for s in p["searches"]),
                                  queried_at=min([s["queried_at"] for s in p["searches"]] or [0]) or 1,
                                  n_results=p["n_unique"], response_count=p["n_unique"],
                                  excluded=[{"id": e["nct"], "reason": f"{e['reason']}: {e['detail']}"} for e in p["excluded"]],
                                  claim=f"No open trial naming {by_id[bid]['diagnosis']['label']} or {p['gene']} passed the "
                                        f"filters ({p['n_unique']} studies returned; {len(p['excluded'])} excluded with reasons).",
                                  filters={"status": list(T.OPEN), "url": s0.get("url")}))
        led.actions.append(LG.action_record(None, SECTION, "None found", [bid], [], [neg["id"]],
                                            {bid: "searched ClinicalTrials.gov; no open relevant trial"}, searched_none=True))


def _record(led, study, bs: dict, mapped: dict | None, pf, extra, by_id, step2) -> None:
    nct, branches = study["nct"], sorted(bs)
    src = {"type": "nct", "id": nct, "url": T.study_url(nct)}
    crit_text = T.unescape(study.get("criteria") or "")
    reg_text = C.registry_source(study)
    produced = (mapped or {}).get("produced_by") or "code"
    lines, reasons, details = [], {}, {}

    def ev_for(text: str, kind: str, registry: bool):
        source_text = reg_text if registry else crit_text
        claim = f"{nct} {'registry field' if registry else kind + ' criterion'}: {text[:120]}"
        return led.add(LG.sourced(claim, SECTION, branches, src, text, source_text, study.get("_accessed_at") or 1,
                                  produced_by="code" if registry else produced, retrieved_by="3b clinicaltrials.gov",
                                  action={"key": A.trial_key(nct)}))

    for b in branches:
        bl = C.registry_lines(study, pf)
        if bs[b] == "analysed" and mapped:
            bl += C.lines_for(study, mapped, pf, extra, by_id[b], E.disease_names(by_id[b], step2))
        for x in bl:
            ev = ev_for(x["text"], x["kind"], x["item"].startswith("registry:"))
            line = LG.requirement(f"r{len(lines) + 1}", x["kind"], x["text"], ev["id"], x["patient_fact"],
                                  x["patient_status"], [b], x["note"])
            for k in ("any_of", "fact", "item"):
                if x.get(k):
                    line[k] = x[k]
            if x.get("details"):
                line["details"] = x["details"]
            if line["result"] == "unknown":
                var = (x["patient_fact"] or {}).get("field") or x["text"][:60]
                if var not in {m["variable"] for m in led.missing_information}:
                    led.missing_information.append({"variable": var, "why_it_matters": f"{nct}: {x['text'][:120]}",
                                                    "affects": [], "asked_by": "3b"})
            lines.append(line)
        mine = [l for l in lines if b in l["applies_to"]]
        fail = [l for l in mine if l["result"] == "fail"]
        unk = [l for l in mine if l["result"] == "unknown"]
        reasons[b] = (("excluded: " if fail[0]["kind"] == "exclusion" else "not met: ") + fail[0]["requirement"][:80] if fail
                      else "depends on: " + "; ".join(sorted({(l.get("patient_fact") or {}).get("field") or l["requirement"][:30]
                                                             for l in unk}))[:110] if unk
                      else "registry and assessed criteria met" + (" (registry only; not analysed)" if bs[b] != "analysed" else ""))
    evs = sorted({l["requirement_evidence"] for l in lines})
    if not evs:                                   # a study without lines still needs its registry evidence
        evs = [ev_for(C.registry_text(study, "age"), "inclusion", True)["id"]]
    label = f"{study.get('acronym') or study.get('title') or nct} ({nct})"
    rec = LG.action_record(A.trial_key(nct), SECTION, label, branches, lines, evs, reasons)
    rec.update(nct=nct, url=T.study_url(nct), title=study.get("title"), study_type=study.get("study_type"),
               overall_status=study.get("status"), phases=study.get("phases"), relevance=study.get("relevance"),
               specific=study.get("specific"), analysed_in=[b for b in branches if bs[b] == "analysed"])
    if mapped:
        rec["mapping_rejected"] = [{"id": m.get("id"), "quote": m.get("quote"), "why": m["rejected"]} for m in mapped["rejected"]]
    led.actions.append(rec)

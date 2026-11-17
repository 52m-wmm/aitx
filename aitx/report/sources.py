"""Source update dates for Step 4 citations (contract section 8, Q7). Cached lookups; None when unknown."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET


def genereviews_updated(nbk: str) -> str | None:
    """The chapter's "updated" date (GeneReviews' Last Update) from the local book archive."""
    from aitx.evidence import genereviews as GR
    try:
        path = GR.extract_chapters([nbk]).get(nbk)
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError, KeyError, TypeError, RuntimeError):
        return None
    for d in root.iter("date"):
        if d.get("date-type") == "updated":
            parts = {c.tag: c.text for c in d}
            if parts.get("year"):
                return f"{parts['year']}-{int(parts.get('month') or 1):02d}-{int(parts.get('day') or 1):02d}"
    return None


def trial_updated(nct: str) -> str | None:
    from aitx import http
    try:
        d = json.loads(http.get(f"https://clinicaltrials.gov/api/v2/studies/{nct}?fields=LastUpdatePostDate").text)
    except (RuntimeError, ValueError):
        return None
    return ((d.get("protocolSection") or {}).get("statusModule") or {}).get("lastUpdatePostDateStruct", {}).get("date")


def pubmed_year(pmid: str) -> str | None:
    from aitx.evidence import offlabel as O
    try:
        return (O._fetch_records([pmid]).get(pmid) or {}).get("year")
    except Exception:            # noqa: BLE001 - a missing date is reported as such, never guessed
        return None


def date_of(src: dict, evidence: dict | None = None) -> str | None:
    t, sid = src.get("type"), src.get("id")
    if t == "nbk":
        return genereviews_updated(sid)
    if t == "spl_setid":
        return src.get("effective_date")
    if t == "nct":
        return trial_updated(sid)
    if t == "pmid":
        return pubmed_year(sid)
    if t == "url":
        return src.get("version")
    return None


MEASURE = None


def trial_primary_outcomes(nct: str) -> list[str]:
    """The trial's registered primary outcome measures, verbatim (with their time frame)."""
    from aitx import http
    try:
        d = json.loads(http.get(f"https://clinicaltrials.gov/api/v2/studies/{nct}?fields=OutcomesModule").text)
    except (RuntimeError, ValueError):
        return []
    po = ((d.get("protocolSection") or {}).get("outcomesModule") or {}).get("primaryOutcomes") or []
    return [p["measure"] + (f" ({p['timeFrame']})" if p.get("timeFrame") else "") for p in po if p.get("measure")]


def genereviews_surveillance(nbk: str) -> list[str]:
    """Sentences of the chapter's Surveillance section that name something measured (code filter, verbatim)."""
    import re
    from aitx.evidence import genereviews as GR
    global MEASURE
    MEASURE = MEASURE or re.compile(r"\b(serum|plasma|urine|urinary|blood|monitor\w*|ultrasound|imaging|MRI|eGFR|GFR|"
                                    r"creatinine|cystatin|level|levels|concentration|examination|assessment|evaluation|"
                                    r"test|testing|measure\w*)\b", re.I)
    try:
        sec = next((v for k, v in GR.sections_for_llm(nbk).items() if k.endswith("Surveillance")), "")
    except (OSError, KeyError, ValueError, RuntimeError):
        return []
    out = []
    for line in sec.splitlines():
        body = line.split("]: ", 1)[-1] if "]: " in line else line.split(": ", 1)[-1]
        for s in re.split(r"(?<=[.!?])\s+", body):
            heading = s.rstrip().endswith(":") or re.match(r"^\W*(CKD\s+)?stages?\b", s, re.I)
            if MEASURE.search(s) and len(s) > 15 and not heading and s not in out:
                out.append(s.strip())
    return out


def record_context(led) -> dict:
    """Enter presentation sources into Step 3 using only source IDs already present in the ledger.

    No LLM, new search or patient judgement: exact label sections, primary outcomes and surveillance.
    Step 4 then consumes these evidence IDs rather than fetching clinical content itself.
    """
    from aitx import http
    from aitx.evidence import genereviews as GR, ledger as LG
    from aitx.report import assemble as A, safety as S

    drugs = A.drugs_for_safety({"actions": led.actions, "evidence": list(led.evidence.values())})
    safety = S.check(drugs)
    section_ids = {}
    for row in safety.pop("sections"):
        source = {"type": "spl_setid", "id": row["set_id"], "url": row["url"], "section": row["field"],
                  "effective_date": row["effective_date"]}
        e = led.add(LG.sourced(f"{row['drug']}: label {row['field']}", "outcome_measures_ranking",
                              [b["id"] for b in led.branches], source, row["quote"], row["quote"], row["accessed_at"],
                              retrieved_by="existing FDA label record, verbatim section"))
        section_ids[(row["drug"], row["field"], row["quote"])] = e["id"]
    for kind in ("interactions", "contraindications", "warnings"):
        for row in safety[kind]:
            row["evidence_ids"] = [eid for (drug, _, quote), eid in section_ids.items()
                                   if drug == row["drug"] and LG.quote_in(row["quote"], quote)]
    for row in safety["coverage"]:
        acts = [a for a in led.actions if a["label"] == row["drug"]]
        premises = list(dict.fromkeys(i for a in acts for i in a["evidence_ids"]))
        premises += [eid for (drug, _, _), eid in section_ids.items() if drug == row["drug"]]
        claim = (f"{row['drug']}: interaction text {'checked against the report drug names' if row['interactions_checked'] else '未检查 (not checked)'}; "
                 f"contraindication text {'checked' if row['contraindications_checked'] else '未检查 (not checked)'}. "
                 "This records source coverage, not absence of interactions or contraindications.")
        e = led.add(LG.reasoning(claim, "outcome_measures_ranking", [b["id"] for b in led.branches], premises,
                                retrieved_by="deterministic FDA section availability and name matching"))
        row["evidence_ids"] = [e["id"]]

    outcomes = []
    for a in led.actions:
        if a["section"] != "clinical_trial_eligibility" or a.get("study_type") != "interventional":
            continue
        nct = a["nct"]
        fetched = http.get(f"https://clinicaltrials.gov/api/v2/studies/{nct}?fields=OutcomesModule")
        data = json.loads(fetched.text)
        primary = data["protocolSection"].get("outcomesModule", {}).get("primaryOutcomes", [])
        for row in primary:
            quote = row["measure"]
            kind = "safety" if re.search(r"\b(safety|adverse events?|TEAEs?|tolerability)\b", quote, re.I) else "efficacy"
            source = {"type": "nct", "id": nct, "url": a["url"], "section": "Primary outcomes"}
            e = led.add(LG.sourced(f"{nct}: registered primary {kind} outcome", "outcome_measures_ranking", a["applies_to"],
                                  source, quote, quote, fetched.accessed_at, retrieved_by="registered primary outcome field"))
            outcomes.append({"kind": kind, "label": nct, "evidence_id": e["id"]})
    nbks = {}
    for a in led.actions:
        if a["section"] in ("existing_targeted_therapies", "supportive_management") and A.written(a):
            for eid in a["evidence_ids"]:
                e = led.evidence[eid]
                if e["kind"] == "sourced" and e["source"]["type"] == "nbk":
                    nbks[e["source"]["id"]] = e
    for nbk, original in nbks.items():
        sec = next((v for k, v in GR.sections_for_llm(nbk).items() if k.endswith("Surveillance")), "")
        for quote in genereviews_surveillance(nbk):
            source = {"type": "nbk", "id": nbk, "url": original["source"]["url"], "section": "Management / Surveillance"}
            e = led.add(LG.sourced(f"{nbk}: recorded surveillance measure", "outcome_measures_ranking", original["applies_to"],
                                  source, quote, sec, original["accessed_at"], retrieved_by="existing GeneReviews surveillance section"))
            outcomes.append({"kind": "efficacy", "label": f"GeneReviews {nbk} surveillance", "evidence_id": e["id"]})
    for e in led.evidence.values():
        if e['kind']=='sourced' and e['source']['type']=='nbk':
            rendered=GR.display_quote(e['source']['id'],e['quote'])
            if rendered!=re.sub(r'\s+',' ',e['quote']).strip():e['display_quote']=rendered
    return {"safety": safety, "outcomes": outcomes}

"""Source update dates for Step 4 citations (contract section 8, Q7). Cached lookups; None when unknown."""
from __future__ import annotations

import json
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

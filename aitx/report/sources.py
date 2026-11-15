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

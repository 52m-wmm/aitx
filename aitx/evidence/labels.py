"""FDA drug labels via openFDA (step 3a): search, sections, SPL set id, version and effective date.

Every label used as evidence records its SPL set id, version and effective date; reports cite the
label version date. Links point to DailyMed. All requests go through aitx.http (cached, access time).
"""
from __future__ import annotations

import json
import re
import urllib.parse

from aitx import http

API = "https://api.fda.gov/drug/label.json"
DAILYMED = "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={set_id}"
SECTIONS = ("indications_and_usage", "dosage_and_administration", "contraindications", "warnings_and_cautions",
            "warnings", "boxed_warning", "pediatric_use", "use_in_specific_populations", "clinical_pharmacology")


def _strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def parse(r: dict, accessed_at: int) -> dict:
    o = r.get("openfda") or {}
    sections = {k: " ".join(r[k]) for k in SECTIONS if r.get(k)}
    tables = " ".join(_strip(t) for k, v in r.items() if k.endswith("_table") for t in v)
    eff = str(r.get("effective_time") or "")
    return {"set_id": r.get("set_id"), "version": r.get("version"),
            "effective_date": f"{eff[:4]}-{eff[4:6]}-{eff[6:8]}" if len(eff) >= 8 else eff,
            "brand": (o.get("brand_name") or [""])[0], "generic": (o.get("generic_name") or [""])[0],
            "url": DAILYMED.format(set_id=r.get("set_id")), "sections": sections,
            "full_text": " ".join(sections.values()) + " " + tables, "accessed_at": accessed_at}


def search(field: str, phrase: str, limit: int = 10) -> tuple[list[dict], dict]:
    """(labels, search record) for labels whose `field` contains the phrase."""
    q = urllib.parse.urlencode({"search": f'{field}:"{phrase}"', "limit": limit})
    url = f"{API}?{q}"
    try:
        f = http.get(url)
        d = json.loads(f.text)
        total, acc = d.get("meta", {}).get("results", {}).get("total", 0), f.accessed_at
        labels = [parse(r, acc) for r in d.get("results", [])]
    except RuntimeError as e:                      # openFDA answers "no match" with HTTP 404
        if "404" not in str(e):
            raise
        total, labels, acc = 0, [], 0
    return labels, {"database": "openfda drug label", "endpoint": url, "query": f'{field}:"{phrase}"',
                    "queried_at": acc, "n_results": total, "returned": len(labels)}


def latest(labels: list[dict]) -> list[dict]:
    """One label per generic name: the most recent effective date (many generics share one drug)."""
    best: dict[str, dict] = {}
    for lb in labels:
        k = (lb["generic"] or lb["brand"]).lower()
        if k and (k not in best or lb["effective_date"] > best[k]["effective_date"]):
            best[k] = lb
    return list(best.values())

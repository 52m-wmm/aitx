"""Medication safety check for Step 4 (contract section 9; data source decided 2026-11-15, Q8): the FDA label's
Drug Interactions, Contraindications and Warnings sections from openFDA, quoted verbatim. Presents what the labels say; never
judges, doses or chooses between drugs."""
from __future__ import annotations

import json
import re
import urllib.parse

OPENFDA = "https://api.fda.gov/drug/label.json?search="


def fetch_label(set_id: str) -> dict | None:
    """openFDA label record for one SPL set id (cached HTTP), or None."""
    from aitx import http
    url = OPENFDA + urllib.parse.quote(f'set_id:"{set_id}"')
    try:
        fetched = http.get(url)
        res = json.loads(fetched.text).get("results") or []
    except (RuntimeError, ValueError):
        return None
    return dict(res[0], _url=url, _accessed_at=fetched.accessed_at) if res else None


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;])\s+", re.sub(r"\s+", " ", text or "")) if s.strip()]


def check(drugs: list[dict], fetch=fetch_label) -> dict:
    """drugs: [{label, names: [...], set_ids: [...]}] for every drug the report writes. Returns
    {interactions: [...], contraindications: [...], not_checked: [labels without an FDA label]}; every finding
    carries the verbatim sentence, the set id, the label URL and its effective date."""
    out = {"interactions": [], "contraindications": [], "warnings": [], "not_checked": [], "coverage": [], "sections": []}
    labels = {}
    for d in drugs:
        recs = [r for r in (fetch(s) for s in d.get("set_ids") or []) if r]
        out["coverage"].append({"drug": d["label"], "set_ids": [r["set_id"] for r in recs],
                                "interactions_checked": any(r.get("drug_interactions") for r in recs),
                                "contraindications_checked": any(r.get("contraindications") for r in recs)})
        if not recs:
            out["not_checked"].append(d["label"])
            continue
        labels[d["label"]] = recs
    for d, recs in [(d, labels[d["label"]]) for d in drugs if d["label"] in labels]:
        for r in recs:
            meta = {"drug": d["label"], "set_id": r.get("set_id"), "effective_date": r.get("effective_time"),
                    "url": f"https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={r.get('set_id')}",
                    "accessed_at": r.get("_accessed_at")}
            for field in ("drug_interactions", "contraindications", "boxed_warning", "warnings_and_cautions", "warnings"):
                for text in r.get(field, []):
                    if text.strip():
                        out["sections"].append({**meta, "field": field, "quote": text})
            for text in dict.fromkeys(r.get("boxed_warning", []) + r.get("warnings_and_cautions", r.get("warnings", []))):
                if text.strip():
                    out["warnings"].append({**meta, "quote": text})
            for other in drugs:
                if other is d:
                    continue
                pats = [re.compile(rf"\b{re.escape(n)}\b", re.I) for n in other.get("names") or [other["label"]] if n]
                for s in _sentences(" ".join(r.get("drug_interactions") or [])):
                    if any(p.search(s) for p in pats):
                        out["interactions"].append({**meta, "other": other["label"], "quote": s})
            # the section as one verbatim passage, without its heading number fragments ("( 4 )")
            text = re.sub(r"\s+", " ", " ".join(r.get("contraindications") or [])).strip()
            if text:
                none = re.fullmatch(r"(?:\d+\s+)?CONTRAINDICATIONS\s+None\.?(?:\s*\(\s*\d+\s*\))?(?:\s*None\.?)?(?:\s*\(\s*\d+\s*\))?",
                                    text, re.I) is not None
                quote = next((s for s in _sentences(text) if len(s) > 12), text)
                out["contraindications"].append({**meta, "quote": quote if not none else text, "none": none})
    return out

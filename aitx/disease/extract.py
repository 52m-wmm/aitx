"""Contract 4a + 7: LLM extracts phenotypes (HPO) and patient facts; code verifies.

The LLM only proposes. Every item is checked deterministically and dropped
(with the reason recorded) if it fails:
  - the quote must occur verbatim in clinical_context
  - the HPO id must exist, be current (alt ids / replaced terms are followed)
    and sit under Phenotypic abnormality (HP:0000118)
  - the quote and the term's label/synonyms must share a content word
  - "excluded" needs a negation cue in or just before the quote

Each case is sampled N_SAMPLES times (temperature 0, separate cache entries).
A term is kept if it appears with the same status in a majority of samples;
facts likewise. Disagreements are reported for prompt tuning.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
from collections import Counter
from pathlib import Path

from aitx import llm
from aitx.disease.hpo import Ontology, lexical_overlap

N_SAMPLES = 3
CACHE_DIR = Path(os.environ.get("AITX_LLM_CACHE_DIR", Path.cwd() / ".cache" / "llm"))
PROMPT_VERSION = "step2-extract-v2"

SYSTEM = """You extract structured facts from a short clinical description of a patient with a rare genetic disease.
Return only a JSON object with this shape:
{
  "phenotypes": [
    {"quote": "<shortest exact span from the text naming one clinical feature>",
     "hpo_id": "HP:nnnnnnn", "hpo_label": "<exact HPO term label>",
     "status": "present" | "excluded",
     "onset": null | {"min": <number or null>, "max": <number or null>, "unit": "day"|"week"|"month"|"year"|null,
                      "approximate": <true|false>, "quote": <exact span>}}
  ],
  "facts": {
    "age": {"value": <number or null>, "unit": "day"|"week"|"month"|"year"|null, "quote": <exact span or null>},
    "onset": {"min": <number or null>, "max": <number or null>, "unit": "day"|"week"|"month"|"year"|null,
              "approximate": <true|false>, "quote": <exact span or null>},
    "sex": {"value": "male"|"female"|"unknown", "quote": <exact span or null>},
    "variant_origin": {"value": "de_novo"|"inherited"|"unknown", "quote": <exact span or null>},
    "family_history": {"statement": <short paraphrase or null>, "quote": <exact span or null>}
  }
}
Rules:
- phenotypes: every sign, symptom, clinical finding or tumour mentioned (one entry per feature). Do not list
  disease or syndrome names, genes, variants, test methods, ages or sex. Choose the most specific HPO
  Phenotypic abnormality term the text supports; do not add features that are not stated.
- "excluded" only when the text explicitly says the feature is absent (e.g. "without seizures").
- Every quote must be copied character-for-character from the text.
- facts.onset: age at onset of the DISEASE as a whole, filled ONLY when the text explicitly dates the disease
  or its main presentation (e.g. "presented at 8 months of age", "symptoms since birth", or the onset of the
  feature the description is centred on). "first months of life" -> min 0, max 6, unit month, approximate true.
  A single age -> min = max.
- If the text dates only one particular symptom (e.g. "around 10 years of age began losing weight"), put that
  timing in the "onset" of that phenotype entry and leave facts.onset null. Otherwise a phenotype's onset is null.
- Anything the text does not state is null / "unknown". Never guess."""


# ------------------------------------------------------------------ LLM call

def _cached_chat(messages: list[dict], k: int, use_cache: bool) -> dict:
    cfg = llm.config()
    key = hashlib.sha256(json.dumps([cfg["model"], cfg["base_url"], PROMPT_VERSION, messages, k],
                                    sort_keys=True).encode()).hexdigest()
    path = CACHE_DIR / f"{key}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text())
    for attempt in range(3):
        try:
            resp = llm.chat(messages, temperature=0, max_tokens=16384, response_format={"type": "json_object"})
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500 and e.code != 429:
                raise RuntimeError(f"LLM API refused the request: HTTP {e.code} {e.reason}") from e
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
            print(f"[llm] transient error, retrying: {e}", flush=True)
            continue
        choice = resp["choices"][0]
        content = choice["message"].get("content") or ""
        if content.strip() and choice.get("finish_reason") != "length":
            break
    else:  # never cache a truncated or empty answer
        raise RuntimeError(f"LLM returned no usable content (finish_reason={choice.get('finish_reason')})")
    out = {"requested_model": cfg["model"], "served_model": resp.get("model", ""),
           "content": content, "sample": k}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def llm_samples(context: str, *, use_cache: bool = True, n: int = N_SAMPLES) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Clinical description:\n{context}"}]
    out = []
    for k in range(n):
        r = _cached_chat(messages, k, use_cache)
        try:
            r["parsed"] = json.loads(r["content"])
        except json.JSONDecodeError as e:
            r["parsed"], r["error"] = {}, f"invalid JSON: {e}"
        out.append(r)
    return out


# ------------------------------------------------------------- verification

_NEG = re.compile(r"\b(without|no|not|absence of|absent|denies|negative for|free of)\b", re.I)


def verify_phenotype(item: dict, context: str, ont: Ontology) -> dict:
    quote = str(item.get("quote") or "")
    status = item.get("status")
    raw_id = str(item.get("hpo_id") or "")
    out = {"quote": quote, "status": status, "proposed_id": raw_id, "proposed_label": item.get("hpo_label"),
           "hpo_id": None, "label": None, "valid": False, "reasons": []}
    if not quote or quote not in context:
        out["reasons"].append("quote not found verbatim in clinical_context")
        return out
    if status not in ("present", "excluded"):
        out["reasons"].append(f"bad status {status!r}")
        return out
    cur, note = ont.resolve(raw_id)
    if note:
        out["reasons"].append(note)
    if cur and not ont.is_phenotype(cur):
        out["reasons"].append(f"{cur} is not under Phenotypic abnormality")
        cur = None
    if cur and not lexical_overlap(quote, ont.names(cur)):
        out["reasons"].append(f"no word overlap between quote and {cur} '{ont.terms[cur].label}'")
        cur = None
    if cur is None:
        # Proposed ids are often wrong while the label is right: fall back to an
        # exact HPO name match of the proposed label, then of the quote itself,
        # still requiring word overlap with the quote.
        for name, what in ((str(item.get("hpo_label") or ""), "proposed label"), (quote, "quote")):
            exact = sorted({t for t in ont.exact_lookup(name) if lexical_overlap(quote, ont.names(t))}) if name else []
            if len(exact) == 1:
                cur = exact[0]
                out["reasons"].append(f"used exact HPO name match of the {what}: {cur}")
                break
        else:
            return out
    start = context.find(quote)
    window = context[max(0, start - 30):start] + quote
    negated = bool(_NEG.search(window))
    if status == "excluded" and not negated:
        out["reasons"].append("marked excluded but no negation cue in text")
        return out
    if status == "present" and _NEG.search(quote):
        out["reasons"].append("marked present but the quote itself is negated")
        return out
    out.update(hpo_id=cur, label=ont.terms[cur].label, valid=True,
               lexical_overlap=lexical_overlap(quote, ont.names(cur)))
    if item.get("onset"):
        out["onset"] = verify_onset(item["onset"], context)   # symptom-specific timing, not the overall onset
    return out


_UNIT_MONTHS = {"day": 1 / 30.4375, "week": 7 / 30.4375, "month": 1.0, "year": 12.0}


def to_months(value, unit) -> float | None:
    """Age conversion is done here, never by the LLM. 3 year -> 36, 18 month -> 18, 2 week -> 0.5."""
    if value is None or unit is None:
        return None
    u = str(unit).lower().rstrip("s")
    if u not in _UNIT_MONTHS:
        return None
    m = float(value) * _UNIT_MONTHS[u]
    return int(m) if m == int(m) else round(m, 1)


_SEX = {"male": re.compile(r"\b(male|boy|man|he|his|him)\b", re.I),
        "female": re.compile(r"\b(female|girl|woman|she|her)\b", re.I)}


def _number_cue(v) -> re.Pattern:
    """The number as written in text: 3.0 -> '3', 1.5 -> '1.5'; also matches spelled-out 1-12."""
    words = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]
    f = float(v)
    num = str(int(f)) if f == int(f) else str(f)
    alts = [re.escape(num)] + ([words[int(f) - 1]] if f == int(f) and 1 <= f <= 12 else [])
    return re.compile(r"(?<![\d.])(" + "|".join(alts) + r")(?![\d.])", re.I)


def _fact(value, quote, context, reasons: list[str], cue: re.Pattern | None = None) -> dict:
    if value in (None, "unknown"):
        return {"value": "unknown", "quote": None, "verified": True}
    if not quote or quote not in context:
        reasons.append("quote not found verbatim")
        return {"value": "unknown", "quote": quote, "verified": False, "reasons": reasons}
    if cue is not None and not cue.search(quote):
        reasons.append("quote does not support the value")
        return {"value": "unknown", "quote": quote, "verified": False, "reasons": reasons}
    return {"value": value, "quote": quote, "verified": True, **({"reasons": reasons} if reasons else {})}


def verify_onset(o: dict, context: str) -> dict:
    """{min, max, unit, approximate, quote} from the LLM -> months, with a verbatim quote check."""
    lo, hi = to_months(o.get("min"), o.get("unit")), to_months(o.get("max"), o.get("unit"))
    onset = _fact((lo, hi) if lo is not None or hi is not None else None, o.get("quote"), context, [])
    if onset["value"] != "unknown":
        onset["months_min"], onset["months_max"] = onset.pop("value")
        onset["approximate"] = bool(o.get("approximate")) or lo != hi
    else:
        onset.pop("value")
        onset["months_min"] = onset["months_max"] = None
    return onset


def verify_facts(f: dict, context: str) -> dict:
    f = f or {}
    out = {}
    a = f.get("age") or {}
    months = to_months(a.get("value"), a.get("unit"))
    age = _fact(months, a.get("quote"), context, [], _number_cue(a.get("value")) if months is not None else None)
    age["months"] = age.pop("value") if age["value"] != "unknown" else None
    out["age"] = {**age, "source_value": a.get("value"), "source_unit": a.get("unit")}

    out["onset"] = verify_onset(f.get("onset") or {}, context)

    s = f.get("sex") or {}
    sv = s.get("value") if s.get("value") in ("male", "female") else None
    sex = _fact(sv, s.get("quote"), context, [], _SEX.get(sv) if sv else None)
    if sex["value"] in _SEX:  # whole-text cross-check: no cue for the other sex
        other = "female" if sex["value"] == "male" else "male"
        if _SEX[other].search(context):
            sex = {"value": "unknown", "quote": sex["quote"], "verified": False,
                   "reasons": [f"text also contains cues for {other}"]}
    out["sex"] = sex

    v = f.get("variant_origin") or {}
    vv = v.get("value") if v.get("value") in ("de_novo", "inherited") else None
    cue = re.compile(r"de novo", re.I) if vv == "de_novo" else re.compile(r"inherit|maternal|paternal|from (his|her|the) (mother|father)", re.I)
    out["variant_origin"] = _fact(vv, v.get("quote"), context, [], cue if vv else None)

    h = f.get("family_history") or {}
    fh = _fact(h.get("statement"), h.get("quote"), context, [])
    out["family_history"] = {"statement": fh.pop("value"), **fh}
    return out


# --------------------------------------------------------------- aggregation

def _fact_key(name: str, f: dict):
    if name == "age":
        return f.get("months")
    if name == "onset":
        return (f.get("months_min"), f.get("months_max"))
    if name == "family_history":
        return f.get("statement") if f.get("statement") != "unknown" else "unknown"
    return f.get("value")


def extract(context: str, ont: Ontology, *, use_cache: bool = True, n: int = N_SAMPLES) -> dict:
    samples = llm_samples(context, use_cache=use_cache, n=n)
    per_sample = []
    for s in samples:
        items = [verify_phenotype(p, context, ont) for p in (s["parsed"].get("phenotypes") or [])]
        per_sample.append({"phenotypes": items, "facts": verify_facts(s["parsed"].get("facts") or {}, context),
                           "served_model": s["served_model"], "error": s.get("error")})

    votes: Counter = Counter()
    first: dict = {}
    for ps in per_sample:
        seen = set()
        for p in ps["phenotypes"]:
            if p["valid"] and (p["hpo_id"], p["status"]) not in seen:
                seen.add((p["hpo_id"], p["status"]))
                votes[(p["hpo_id"], p["status"])] += 1
                first.setdefault((p["hpo_id"], p["status"]), p)
    need = n // 2 + 1
    kept = [dict(first[k], votes=c) for k, c in sorted(votes.items()) if c >= need]
    ids_present = {p["hpo_id"] for p in kept if p["status"] == "present"}
    conflicts = [p for p in kept if p["status"] == "excluded" and p["hpo_id"] in ids_present]
    if conflicts:
        bad = {p["hpo_id"] for p in conflicts}
        kept = [p for p in kept if p["hpo_id"] not in bad]
    unstable = [dict(first[k], votes=c) for k, c in sorted(votes.items()) if c < need]
    rejected = [p for ps in per_sample for p in ps["phenotypes"] if not p["valid"]]

    facts, fact_notes = {}, []
    for name in ("age", "onset", "sex", "variant_origin", "family_history"):
        keys = Counter(repr(_fact_key(name, ps["facts"][name])) for ps in per_sample)
        top, c = keys.most_common(1)[0]
        if c >= need:
            facts[name] = next(ps["facts"][name] for ps in per_sample if repr(_fact_key(name, ps["facts"][name])) == top)
        else:
            facts[name] = {"value": "unknown", "verified": True, "reasons": ["samples disagree"]}
            fact_notes.append(f"{name}: samples disagree {dict(keys)}")
    return {
        "phenotypes": kept,
        "phenotype_conflicts": conflicts,
        "unstable_phenotypes": unstable,
        "rejected_phenotypes": rejected,
        "patient_facts": facts,
        "fact_notes": fact_notes,
        "samples": [{"served_model": ps["served_model"], "error": ps["error"],
                     "terms": sorted({(p["hpo_id"], p["status"]) for p in ps["phenotypes"] if p["valid"]})}
                    for ps in per_sample],
        "prompt_version": PROMPT_VERSION,
    }

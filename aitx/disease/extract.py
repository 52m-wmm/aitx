"""Contract 4a + 7: LLM extracts phenotypes and patient facts; code assigns HPO ids.

Same principle as disease selection: the LLM never writes an identifier.
  Stage 1  LLM returns each clinical feature as (verbatim quote, short medical
           description, present/excluded, optional onset), plus patient facts.
  Mapping  code matches the description, then the quote, against HPO labels,
           synonyms and former names (older releases); a unique exact match is used.
  Stage 2  otherwise code retrieves the closest candidate terms (up to 10) and the
           LLM picks one of them by number, or none. Only code-listed ids can be chosen.
Deterministic checks: quote verbatim in clinical_context; "excluded" needs a
negation cue in or just before the quote.

Each case is sampled N_SAMPLES times. Votes are merged along the HPO hierarchy:
a term is kept when it or a more specific term below it appears in a majority
of samples, at the most specific level the majority supports.
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
from aitx.disease.hpo import Ontology

N_SAMPLES = 3
CACHE_DIR = Path(os.environ.get("AITX_LLM_CACHE_DIR", Path.cwd() / ".cache" / "llm"))
PROMPT_VERSION = "step2-extract-v4"
N_CANDIDATES = 10

SYSTEM = """You extract structured facts from a short clinical description of a patient with a rare genetic disease.
Return only a JSON object with this shape:
{
  "phenotypes": [
    {"quote": "<shortest exact span from the text naming one clinical feature>",
     "description": "<the feature as a standard English clinical term, e.g. 'Hypotonia', 'Weight loss',
                     'Distal sensory impairment'; no onset, age or frequency words>",
     "alternatives": ["<up to 3 other standard clinical names for the same feature, e.g. a broader or
                      lay-to-medical rewording>"],
     "status": "present" | "excluded",
     "presenting": <true if the text describes this as the presenting / first symptom, e.g. "presented with">,
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
- phenotypes: every sign, symptom, clinical finding, abnormal laboratory value or tumour mentioned, one entry per
  feature. Do not list disease or syndrome names, genes, variants, test methods, normal findings, ages or sex.
  Do not add features that are not stated. Do not give any ontology identifiers.
- "excluded" only when the text explicitly says the feature is absent (e.g. "without seizures").
- Every quote must be copied character-for-character from the text.
- facts.onset: age at onset of the DISEASE as a whole, filled ONLY when the text explicitly dates the disease
  or its main presentation (e.g. "presented at 8 months of age", "symptoms since birth").
  "first months of life" -> min 0, max 6, unit month, approximate true. A single age -> min = max.
- If the text dates one particular symptom (e.g. "around 10 years of age began losing weight"), put that timing in
  the "onset" of that phenotype entry; put it in facts.onset only if that symptom is the presenting one.
- Anything the text does not state is null / "unknown". Never guess."""

PICK_SYSTEM = """You map clinical features of a patient to Human Phenotype Ontology terms.
For each numbered feature you get the exact text and a numbered list of candidate terms.
Pick the candidate that names the feature the text describes, at the most specific level the text supports
(do not pick a narrower term than the text states). A feature the text states as absent (e.g. "without seizures")
is still mapped to the feature itself. If no candidate fits, answer null.
Return only JSON: {"choices": [{"feature": <feature number>, "candidate": <candidate number or null>}]}"""


# ------------------------------------------------------------------ LLM call

CALL_PARAMS = {"temperature": 0, "max_tokens": 16384, "response_format": {"type": "json_object"}}


def cache_key(messages: list[dict], k: int, cfg: dict | None = None) -> str:
    """Cache key: requested model, endpoint, prompt version, full prompt text, sample index.

    Changing the prompt (even without bumping PROMPT_VERSION), the model or the endpoint
    gives a new key, so stale answers are never reused. Call parameters are stored in the
    entry and checked on every hit (see _cache_usable).
    """
    cfg = cfg or llm.config()
    return hashlib.sha256(json.dumps([cfg["model"], cfg["base_url"], PROMPT_VERSION, messages, k],
                                     sort_keys=True).encode()).hexdigest()


def _cache_usable(entry: dict, cfg: dict) -> bool:
    """Reuse only answers made with the current call parameters and, if an expected model
    prefix is set, served by that model (guards against a silent alias switch)."""
    if entry.get("call_params") != CALL_PARAMS:
        return False
    prefix = cfg.get("expect_model_prefix")
    return not prefix or str(entry.get("served_model", "")).startswith(prefix)


def _cached_chat(messages: list[dict], k: int, use_cache: bool) -> dict:
    """One chat completion, cached under cache_key()."""
    cfg = llm.config()
    path = CACHE_DIR / f"{cache_key(messages, k, cfg)}.json"
    if use_cache and path.exists():
        entry = json.loads(path.read_text())
        if _cache_usable(entry, cfg):
            return entry
    for attempt in range(3):
        try:
            resp = llm.chat(messages, **CALL_PARAMS)
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
           "content": content, "sample": k, "call_params": CALL_PARAMS, "call_params_source": "recorded",
           "prompt_version": PROMPT_VERSION}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def _parse(r: dict) -> dict:
    try:
        r["parsed"] = json.loads(r["content"])
    except json.JSONDecodeError as e:
        r["parsed"], r["error"] = {}, f"invalid JSON: {e}"
    return r


def llm_samples(context: str, *, use_cache: bool = True, n: int = N_SAMPLES) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Clinical description:\n{context}"}]
    return [_parse(_cached_chat(messages, k, use_cache)) for k in range(n)]


# ------------------------------------------------------------- verification

_NEG = re.compile(r"\b(without|no|not|absence of|absent|denies|negative for|free of)\b", re.I)
_PRESENTING = re.compile(r"\b(present(ed|s|ing)|first (sign|symptom|noticed)s?|initial(ly)? (sign|symptom|present)\w*)\b", re.I)


def check_item(item: dict, context: str) -> dict:
    """Deterministic checks on a stage-1 item (no ids involved)."""
    quote = str(item.get("quote") or "")
    status = item.get("status")
    alts = item.get("alternatives") if isinstance(item.get("alternatives"), list) else []
    out = {"quote": quote, "description": str(item.get("description") or ""),
           "alternatives": [str(a) for a in alts if a][:3], "status": status,
           "presenting": bool(item.get("presenting")), "hpo_id": None, "label": None, "valid": False, "reasons": []}
    if not quote or quote not in context:
        out["reasons"].append("quote not found verbatim in clinical_context")
        return out
    if status not in ("present", "excluded"):
        out["reasons"].append(f"bad status {status!r}")
        return out
    start = context.find(quote)
    negated = bool(_NEG.search(context[max(0, start - 30):start] + quote))
    if status == "excluded" and not negated:
        out["reasons"].append("marked excluded but no negation cue in text")
        return out
    if status == "present" and _NEG.search(quote):
        out["reasons"].append("marked present but the quote itself is negated")
        return out
    if out["presenting"]:
        sentence = context[context.rfind(".", 0, start) + 1:start + len(quote)]
        if not _PRESENTING.search(sentence):
            out["presenting"] = False
            out["reasons"].append("marked presenting but no 'presented with'-type cue in the sentence")
    if item.get("onset"):
        out["onset"] = verify_onset(item["onset"], context)
    out["checked"] = True
    return out


def candidates_for(item: dict, ont: Ontology) -> tuple[str | None, list[dict], str]:
    """(exact id or None, retrieval candidates, how).

    Exact = unique HPO name match of the verbatim quote, then the description, then each alternative name.
    Otherwise retrieval over the description, alternatives and quote (query expansion), up to N_CANDIDATES.
    """
    texts = [(item["quote"], "quote"), (item["description"], "description")] + [
        (a, "alternative name") for a in item.get("alternatives", [])]
    for text, what in texts:
        hits = ont.exact_lookup(text) if text else []
        if len(hits) == 1:
            return hits[0], [], f"exact HPO name match of the {what}"
        if len(hits) > 1:
            return None, [{"hpo_id": h, "label": ont.terms[h].label} for h in hits], f"several terms share the name '{text}'"
    seen, cands = set(), []
    queries = [(item["description"], 5)] + [(a, 3) for a in item.get("alternatives", [])] + [(item["quote"], 3)]
    for text, k in queries:
        for c in ont.search(text, k) if text else []:
            if c["hpo_id"] not in seen and len(cands) < N_CANDIDATES:
                seen.add(c["hpo_id"])
                cands.append(c)
    return None, cands, "retrieved candidates"


def map_items(items: list[dict], context: str, ont: Ontology, k: int, use_cache: bool) -> list[dict]:
    """Assign HPO ids to checked items: exact match in code, else LLM picks from code-listed candidates."""
    pending = []
    for it in items:
        if not it.get("checked"):
            continue
        tid, cands, how = candidates_for(it, ont)
        if tid:
            it.update(hpo_id=tid, label=ont.terms[tid].label, valid=True, mapping=how)
        elif cands:
            it["candidates"] = cands
            pending.append(it)
        else:
            it["reasons"].append("no candidate HPO term found")
    if not pending:
        return items
    lines = [f"Clinical description: {context}", ""]
    for i, it in enumerate(pending, 1):
        lines.append(f"Feature {i}: text \"{it['quote']}\" (described as: {it['description']})")
        for j, c in enumerate(it["candidates"], 1):
            syn = [n for n in ont.names(c["hpo_id"])[1:4]]
            lines.append(f"  {j}. {c['label']}" + (f" (also: {'; '.join(syn)})" if syn else ""))
    r = _parse(_cached_chat([{"role": "system", "content": PICK_SYSTEM},
                             {"role": "user", "content": "\n".join(lines)}], k, use_cache))
    picks = {}
    for ch in (r["parsed"].get("choices") or []):
        try:
            picks[int(ch.get("feature"))] = ch.get("candidate")
        except (TypeError, ValueError):
            continue
    for i, it in enumerate(pending, 1):
        j = picks.get(i)
        if isinstance(j, int) and 1 <= j <= len(it["candidates"]):
            tid = it["candidates"][j - 1]["hpo_id"]
            it.update(hpo_id=tid, label=ont.terms[tid].label, valid=True, mapping="LLM pick from retrieved candidates")
        else:
            it["reasons"].append("LLM picked none of the candidates" if i in picks else "no pick returned")
    return items


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


def vote_terms(per_sample: list[list[dict]], ont: Ontology, n: int) -> tuple[list[dict], list[dict]]:
    """Majority vote merged along the HPO hierarchy.

    support(t) = number of samples with t itself or a more specific term below t (same status).
    Terms with support >= majority are kept, except those that have a more specific kept term
    below them, so the result is the most specific level a majority of samples agrees on.
    Returns (kept, unstable).
    """
    need = n // 2 + 1
    kept, unstable = [], []
    for status in ("present", "excluded"):
        by_sample = [{it["hpo_id"]: it for it in items if it["valid"] and it["status"] == status} for items in per_sample]
        terms = sorted({t for smp in by_sample for t in smp})
        support = {t: sum(any(u == t or t in ont.ancestors(u) for u in smp) for smp in by_sample) for t in terms}
        ok = [t for t in terms if support[t] >= need]
        top = [t for t in ok if not any(u != t and t in ont.ancestors(u) for u in ok)]
        for t in top:
            src = next((smp[t] for smp in by_sample if t in smp), None)
            kept.append(dict(src, votes=support[t],
                             merged_from=sorted({u for smp in by_sample for u in smp if u != t and t in ont.ancestors(u)})))
        covered = {u for t in top for u in terms if u == t or t in ont.ancestors(u) or u in ont.ancestors(t)}
        for t in terms:
            if t not in covered:
                unstable.append(dict(next(smp[t] for smp in by_sample if t in smp), votes=support[t]))
    return kept, unstable


def presenting_onset(items: list[dict]) -> dict | None:
    """Rule v2.4: the onset of a verified presenting symptom counts as the overall onset."""
    ons = [it["onset"] for it in items if it.get("valid") and it.get("presenting")
           and it.get("onset", {}).get("months_min") is not None]
    if not ons:
        return None
    lo = min(o["months_min"] for o in ons)
    hi = max(o["months_max"] for o in ons)
    return {"months_min": lo, "months_max": hi, "approximate": any(o.get("approximate") for o in ons) or lo != hi,
            "quote": ons[0]["quote"], "verified": True, "source": "presenting symptom"}


def extract(context: str, ont: Ontology, *, use_cache: bool = True, n: int = N_SAMPLES) -> dict:
    samples = llm_samples(context, use_cache=use_cache, n=n)
    per_sample = []
    for k, s in enumerate(samples):
        items = [check_item(p, context) for p in (s["parsed"].get("phenotypes") or [])]
        items = map_items(items, context, ont, k, use_cache)
        facts = verify_facts(s["parsed"].get("facts") or {}, context)
        if facts["onset"].get("months_min") is None:
            po = presenting_onset(items)
            if po:
                facts["onset"] = po
        per_sample.append({"phenotypes": items, "facts": facts,
                           "served_model": s["served_model"], "error": s.get("error")})

    kept, unstable = vote_terms([ps["phenotypes"] for ps in per_sample], ont, n)
    need = n // 2 + 1
    ids_present = {p["hpo_id"] for p in kept if p["status"] == "present"}
    conflicts = [p for p in kept if p["status"] == "excluded" and p["hpo_id"] in ids_present]
    if conflicts:
        bad = {p["hpo_id"] for p in conflicts}
        kept = [p for p in kept if p["hpo_id"] not in bad]
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
        "phenotypes": sorted(kept, key=lambda p: (p["status"], p["hpo_id"])),
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

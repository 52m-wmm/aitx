"""Single structured clinical extraction, with deterministic evidence and HPO mapping.

Native four-state records retain patient/general/unknown attribution and source quotes.
Only definite patient phenotypes are projected to the legacy scoring interface.
The shared LLM transport remains available to other steps with their own prompts.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import threading
import socket
import time
import urllib.error
from pathlib import Path

from aitx import budget, llm, peak, session
from aitx.disease.hpo import Ontology

N_SAMPLES = 1
# LLM requests in flight at once across all threads (cache hits are not limited). Results do not depend on it:
# cache keys and sample numbers are the same as in a serial run.
CONCURRENCY = max(1, int(os.environ.get("AITX_LLM_CONCURRENCY", "16")))   # provider limit is 2500
_SLOTS = threading.BoundedSemaphore(CONCURRENCY)
CACHE_DIR = Path(os.environ.get("AITX_LLM_CACHE_DIR", Path.cwd() / ".cache" / "llm"))
PROMPT_VERSION = "step2-clinical-v6"
N_CANDIDATES = 10

SYSTEM = """Extract the clinical facts actually stated in the supplied text, once, as JSON.
Do not infer missing facts, diagnoses, sex from genes, lab units, or trial eligibility.
Distinguish an individual patient's observations from general disease descriptions, possibilities,
recommendations and literature summaries. A disease overview is NOT a patient's history, even when
supplied as a clinical description. In mixed text classify each item separately; uncertain attribution
is scope unknown. Retain general statements as background, not patient findings.
Return this complete shape (all keys required, empty lists/null mean unreported, never absent):
{
 "phenotypes": [{
   "quote": "exact span naming the feature with its assertion/uncertainty context",
   "description": "standard English clinical feature, no ontology identifiers",
   "alternatives": ["up to 3 equivalent clinical names"],
   "scope": "patient|general|unknown",
   "status": "present|absent|possible|unknown",
   "presenting": false,
   "onset": null,
   "severity": null,
   "course": null
 }],
 "facts": {
   "age": {"value": null, "unit": null, "quote": null, "scope": "unknown", "status": "unknown"},
   "onset": {"quote": null, "scope": "unknown", "status": "unknown"},
   "sex": {"value": "unknown", "quote": null, "scope": "unknown", "status": "unknown"},
   "variant_origin": {"value": "unknown", "quote": null, "scope": "unknown", "status": "unknown"},
   "family_history": {"statement": null, "quote": null, "scope": "unknown", "status": "unknown"}
 },
 "clinical_facts": [{
   "kind": "diagnosis|demographic|history|treatment|lab|trial_status",
   "name": "exact name from quote",
   "quote": "exact statement with patient attribution and uncertainty/negation",
   "scope": "patient|general|unknown",
   "status": "present|absent|possible|unknown",
   "value": null,
   "unit": null,
   "timing": null
 }],
 "background": [{"quote": "exact general disease description", "reason": "why this is not a patient observation"}]
}
Rules:
- Do not give any ontology identifiers.
- Every quote is a contiguous character-for-character copy. Never fabricate or complete an unfinished sentence.
- Extract all stated patient diagnoses separately from signs/symptoms. Include demographics, gestational age,
  hospitalization, medical/family history, current and past treatments (including diet and supplements),
  numeric lab results with original units, and actual clinical trial participation/status.
- Keep history, severity, progression and symptom onset. onset/severity/course are null or {"quote": "exact span"}.
  Current age is numeric with unit day/week/month/year; do not confuse it with gestational age or symptom onset.
  facts.onset is filled ONLY when the text explicitly dates disease onset or main presentation;
  do not extrapolate from another symptom. Give the quote only; do not convert it to numbers.
  clinical_facts.timing is null or an exact span describing when the fact occurred.
- present = explicitly observed/reported; absent = explicitly denied or specific function/test explicitly normal;
  possible = suspected, uncertain, may occur, alternatives such as normal OR delayed;
  unknown = explicitly undetermined/not assessed. Unmentioned fields are unknown, not absent.
- A feature itself defined by absence (e.g. absent speech) can be present. Do not negate it twice.
- Do not turn normal growth in the past into absence of current weight loss. Do not infer a lab value from a
  symptom name. No conversion or unit completion. No clinical trial mention means no trial_status items.
- Descriptions of what patients generally develop, sex-specific disease manifestations, and literature citations
  belong in background. If listing their features, use scope general and the wording's actual assertion status.
- Facts about a relative are history, not the patient's own phenotypes or demographics.
- For missing age use value/unit/quote null; missing sex/origin use value unknown; missing history statement null.
Return JSON only."""

PICK_SYSTEM = """You map clinical features of a patient to Human Phenotype Ontology terms.
For each numbered feature you get the exact text and a numbered list of candidate terms.
Pick the candidate that names the feature the text describes, at the most specific level the text supports
(do not pick a narrower term than the text states). A feature the text states as absent (e.g. "without seizures")
is still mapped to the feature itself. If no candidate fits, answer null.
Return only JSON: {"choices": [{"feature": <feature number>, "candidate": <candidate number or null>}]}"""


# ------------------------------------------------------------------ LLM call

CALL_PARAMS = {"temperature": 0, "max_tokens": 16384, "response_format": {"type": "json_object"}}
# a truncated answer (finish_reason=length) is retried once with a larger budget, then fails: at temperature 0
# the identical request runs away the same way again (2026-11-04: five identical retries, 16384 tokens each)
LENGTH_RETRY_PARAMS = {**CALL_PARAMS, "max_tokens": 32768}


def check_claim_key_messages(messages, prompt_version):
    """Normalize only quoted action claims in checker questions; keep real prompts intact."""
    if prompt_version != 'context-check-v3':return messages
    pattern = re.compile(r"((?:advice about |recommend or advise |advises avoiding |advice about |advice concerning )')([^']*)(')")
    result=[]
    for m in messages:
        content=m['content']
        if m['role']=='user' and '\n\nQuestions:\n' in content:
            prefix,questions=content.split('\n\nQuestions:\n',1)
            questions=pattern.sub(lambda x:x[1]+' '.join(x[2].lower().split())+x[3],questions)
            content=prefix+'\n\nQuestions:\n'+questions
        result.append(dict(m,content=content))
    return result


def cache_key(messages: list[dict], k: int, cfg: dict | None = None, prompt_version: str | None = None) -> str:
    """Cache key: requested model, endpoint, prompt version, full prompt text, sample index.

    Changing the prompt (even without bumping PROMPT_VERSION), the model or the endpoint
    gives a new key, so stale answers are never reused. Call parameters are stored in the
    entry and checked on every hit (see _cache_usable).
    """
    cfg = cfg or llm.config()
    return hashlib.sha256(json.dumps([cfg["model"], cfg["base_url"], prompt_version or PROMPT_VERSION, check_claim_key_messages(messages, prompt_version), k],
                                     sort_keys=True).encode()).hexdigest()


def retry_params(params: dict) -> dict:
    """The one retry after a truncated answer: the same parameters with a larger output budget."""
    return {**params, "max_tokens": 32768}


def _cache_usable(entry: dict, cfg: dict, params: dict | None = None) -> bool:
    """Reuse only answers made with the requested call parameters (default CALL_PARAMS) and, if an expected model
    prefix is set, served by that model (guards against a silent alias switch)."""
    params = params or CALL_PARAMS
    if entry.get("call_params") not in (params, retry_params(params)):
        return False
    prefix = cfg.get("expect_model_prefix")
    return not prefix or str(entry.get("served_model", "")).startswith(prefix)


# Other endpoints whose cached answers may be reused (2026-11-05 decision): "base_url|requested model", comma separated.
DEFAULT_CACHE_FROM = "https://api.deepseek.com|deepseek-flash"
REUSE_LOG = "cache_reuse.jsonl"


def cache_sources(cfg: dict) -> list[dict]:
    raw = os.environ.get("AITX_LLM_CACHE_FROM", DEFAULT_CACHE_FROM)
    out = []
    for part in [x.strip() for x in raw.split(",") if x.strip()]:
        url, _, model = part.partition("|")
        src = dict(cfg, base_url=url.strip().rstrip("/"), model=(model.strip() or cfg["model"]))
        if (src["base_url"], src["model"]) != (cfg["base_url"], cfg["model"]):
            out.append(src)
    return out


def cross_provider_ok(entry: dict, cfg: dict) -> bool:
    """An answer cached from another endpoint is reused only when the model name its server returned is exactly the
    expected one (AITX_EXPECT_MODEL_PREFIX set to the full served name): same weights, not just the same alias.
    Without an expected name nothing is reused across endpoints."""
    want = cfg.get("expect_model_prefix") or ""
    return bool(want) and str(entry.get("served_model") or "") == want


def cache_lookup(messages: list[dict], k: int, cfg: dict, prompt_version: str | None = None,
                 params: dict | None = None) -> dict | None:
    """This endpoint's cached answer, else one from a listed other endpoint under cross_provider_ok. The provider
    that produced the answer is recorded on the entry (`provider`) and every cross-endpoint reuse is logged."""
    path = CACHE_DIR / f"{cache_key(messages, k, cfg, prompt_version)}.json"
    if path.exists():
        entry = json.loads(path.read_text())
        if _cache_usable(entry, cfg, params):
            entry.setdefault("provider", cfg["base_url"])
            return entry
    for src in cache_sources(cfg):
        other = CACHE_DIR / f"{cache_key(messages, k, src, prompt_version)}.json"
        if not other.exists():
            continue
        entry = json.loads(other.read_text())
        if _cache_usable(entry, cfg, params) and cross_provider_ok(entry, cfg):
            entry.setdefault("provider", src["base_url"])
            entry["reused_on"] = cfg["base_url"]
            log = llm.LOG.parent / REUSE_LOG
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a") as f:
                f.write(json.dumps({"ts": int(time.time()), "key": other.stem, "provider": entry["provider"],
                                    "reused_on": cfg["base_url"], "served_model": entry.get("served_model")}) + "\n")
            return entry
    return None


def _cached_chat(messages: list[dict], k: int, use_cache: bool, prompt_version: str | None = None,
                 call_params: dict | None = None) -> dict:
    """One chat completion, cached under cache_key(). Other modules pass their own prompt_version and, if they need
    other settings (2026-11-11: the context check runs with reasoning_effort "low"), their own call parameters."""
    cfg = llm.config()
    base = call_params or CALL_PARAMS
    retry = retry_params(base)
    path = CACHE_DIR / f"{cache_key(messages, k, cfg, prompt_version)}.json"
    call_id = path.stem                        # session log and ledger attribution (1a / 1b, 2026-11-12)
    if use_cache:
        entry = cache_lookup(messages, k, cfg, prompt_version, base)
        if entry is not None:
            session.log_call(call_id=call_id, messages=messages, entry=entry, cache_hit=True, k=k,
                             params=entry.get("call_params") or base)
            return dict(entry, call_id=call_id)
    attempts, params = 5, base
    t0 = time.time()
    for attempt in range(attempts):
        peak.check_before_call()               # --offpeak-only: never start a call inside a peak window
        budget.check_before_call()             # daily spend cap (2026-11-05): stop instead of overspending
        try:
            with _SLOTS:
                resp = llm.chat(messages, **params)
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, http.client.HTTPException,
                llm.NoServedModel) as e:
            # NoServedModel: a stream that carried no model name - retried, never accepted silently (2026-11-06)
            # socket.timeout is not a TimeoutError before Python 3.10 (2026-11-04: a read timeout ended COL1A1 unretried)
            if isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500 and e.code != 429:
                raise RuntimeError(f"LLM API refused the request: HTTP {e.code} {e.reason}") from e
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))
            print(f"[llm] transient error, retrying: {e}", flush=True)
            continue
        choice = resp["choices"][0]
        content = choice["message"].get("content") or ""
        if choice.get("finish_reason") == "length":
            if params is retry:                        # never cache a truncated answer; never retry it again
                raise RuntimeError(f"LLM output truncated twice (max_tokens {base['max_tokens']}, "
                                   f"then {retry['max_tokens']})")
            params = retry
            print(f"[llm] output truncated at {base['max_tokens']} tokens; one retry with "
                  f"{retry['max_tokens']}", flush=True)
            continue
        if content.strip():
            break
    else:  # never cache an empty answer
        raise RuntimeError(f"LLM returned no usable content (finish_reason={choice.get('finish_reason')})")
    out = {"requested_model": cfg["model"], "served_model": resp.get("model", ""),
           "content": content, "sample": k, "call_params": params, "call_params_source": "recorded",
           "prompt_version": prompt_version or PROMPT_VERSION, "provider": cfg["base_url"]}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    session.log_call(call_id=call_id, messages=messages, entry=out, cache_hit=False, k=k, params=params,
                     usage=resp.get("usage"), seconds=time.time() - t0,
                     reserved_usd=resp.get("reserved_usd"),
                     reasoning=choice["message"].get("reasoning_content"))
    return dict(out, call_id=call_id)


def _parse(r: dict) -> dict:
    try:
        r["parsed"] = json.loads(r["content"])
    except json.JSONDecodeError as e:
        r["parsed"], r["error"] = {}, f"invalid JSON: {e}"
    return r


def _messages(context: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Clinical description:\n{context}"}]


# ------------------------------------------------------------- verification

# "normal" negates only when something is said to BE normal; comparisons ("further than normal",
# "below normal") describe an abnormality and are not negations
_NEG = re.compile(r"\b(without|no|not|never|(?<!than )(?<!above )(?<!below )(?<!beyond )normal|unremarkable|ruled out|"
                  r"absence of|absent|denies|negative for|free of)\b", re.I)
# HPO term names that themselves denote an absence (Absent vas deferens, Azoospermia = "Absent sperm in semen",
# Absent speech = "No speech development"): a negation word in the quote can then be part of the feature
_ABSENCE_TERM = re.compile(r"\b(absent|absence|aplasia|agenesis|lack|lacking|missing|no|without|none)\b", re.I)
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
    if status not in ("present", "absent", "possible", "unknown", "excluded"):
        out["reasons"].append(f"bad status {status!r}")
        return out
    start = context.find(quote)
    negated = bool(_NEG.search(context[max(0, start - 30):start] + quote))
    if status in ("absent", "excluded") and not negated:
        out["reasons"].append("marked excluded but no negation cue in text")
        return out
    if status == "present" and _NEG.search(quote):
        # decided after mapping (negation_check): kept only if the mapped term itself denotes an absence
        out["negated_quote"] = _NEG.search(quote).group(0).lower()
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


# "development is normal or mildly delayed": the feature is one of two possibilities, not a stated finding
# (user decision 2026-11-12, RETEST-EIF2B1); deterministic, on the text around the verified quote
_OR_BEFORE = re.compile(r"\b(normal|unaffected|typical|absent|none|no)\s+or\s+(?:\w+\s+){0,2}$", re.I)
_OR_AFTER = re.compile(r"^(?:\s+\w+){0,2}\s+or\s+(normal|unaffected|typical|absent|none)\b", re.I)
_OR_INSIDE = re.compile(r"\b(normal|unaffected|typical)\s+or\b|\bor\s+(normal|unaffected|typical)\b", re.I)


def possible_phrase(context: str, quote: str) -> str | None:
    """The words that make a quoted feature only one possibility ("normal or mildly delayed"), or None."""
    i = (context or "").find(quote or "")
    if not quote or i < 0:
        return None
    before, after = context[max(0, i - 40):i], context[i + len(quote):i + len(quote) + 40]
    m = _OR_BEFORE.search(before) or _OR_INSIDE.search(quote)
    if m:
        return (before[m.start():] if m.re is _OR_BEFORE else "") + quote
    m = _OR_AFTER.search(after)
    return quote + after[:m.end()] if m else None


def negation_check(it: dict, ont: Ontology) -> None:
    """A 'present' item whose quote contains a negation word is kept only when the mapped HPO term itself
    denotes an absence (its name or a synonym), or the same word is part of the term's name
    ("born without the vas deferens" -> Absent vas deferens). Otherwise the LLM marked a negated
    feature as present ("no seizures" -> Seizure) and the item is rejected."""
    word = it.get("negated_quote")
    if not word or not it.get("valid"):
        return
    names = ont.names(it["hpo_id"])
    if any(_ABSENCE_TERM.search(n) or re.search(rf"\b{re.escape(word)}\b", n, re.I) for n in names):
        it["negation_note"] = f"'{word}' in the quote is part of the feature: the term denotes an absence"
        return
    it.update(valid=False, hpo_id=None, label=None)
    it["reasons"].append("marked present but the quote itself is negated, and the mapped term is not an absence")


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
        for it in items:
            negation_check(it, ont)
        return items
    lines = [f"Clinical description: {context}", ""]
    for i, it in enumerate(pending, 1):
        lines.append(f"Feature {i}: text \"{it['quote']}\" (described as: {it['description']})")
        for j, c in enumerate(it["candidates"], 1):
            syn = [n for n in ont.names(c["hpo_id"])[1:4]]
            lines.append(f"  {j}. {c['label']}" + (f" (also: {'; '.join(syn)})" if syn else ""))
    r = _parse(_cached_chat([{"role": "system", "content": PICK_SYSTEM},
                             {"role": "user", "content": "\n".join(lines)}], k, use_cache))
    if r.get("error"):
        raise ValueError(r["error"])
    picks = {}
    choices = r["parsed"]["choices"]
    if not isinstance(choices, list):
        raise ValueError("HPO choices must be a list")
    for ch in choices:
        feature, candidate = ch["feature"], ch["candidate"]
        if type(feature) is not int or not 1 <= feature <= len(pending) or feature in picks:
            raise ValueError("invalid/duplicate HPO feature number")
        if candidate is not None and (type(candidate) is not int or
                                     not 1 <= candidate <= len(pending[feature - 1]["candidates"])):
            raise ValueError("invalid HPO candidate number")
        picks[feature] = candidate
    if len(picks) != len(pending):
        raise ValueError("missing HPO selection answer")
    for i, it in enumerate(pending, 1):
        j = picks.get(i)
        if isinstance(j, int) and 1 <= j <= len(it["candidates"]):
            tid = it["candidates"][j - 1]["hpo_id"]
            it.update(hpo_id=tid, label=ont.terms[tid].label, valid=True, mapping="LLM pick from retrieved candidates")
        else:
            it["reasons"].append("LLM picked none of the candidates" if i in picks else "no pick returned")
    for it in items:
        negation_check(it, ont)
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


_NUM_WORDS = {w: i for i, w in enumerate(["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
                                           "ten", "eleven", "twelve"])}
_N = r"(\d+(?:\.\d+)?|" + "|".join(_NUM_WORDS) + r")"
_U = r"(day|week|month|year)s?"
_RANGE = re.compile(_N + r"\s*(?:-|–|to|and)\s*" + _N + r"[\s-]*" + _U, re.I)
_FIRST = re.compile(r"first\s+" + _N + r"\s+" + _U + r"(?:\s+of\s+life)?", re.I)
_AGE = re.compile(_N + r"[\s-]*" + _U, re.I)
_DAY_OF_LIFE = re.compile(r"\bday\s+(\d+)(?:\s+of\s+life)?\b", re.I)          # "day 3 (of life)": age in days
_AGE_YEARS = re.compile(r"\bage(?:d)?\s+(?:of\s+)?" + _N + r"\b(?![\s-]*(?:day|week|month|year))", re.I)   # "age 6"
_APPROX = re.compile(r"\b(around|about|approximately|roughly|~|circa)\b", re.I)


def _num(x: str) -> float:
    return float(_NUM_WORDS[x.lower()]) if x.lower() in _NUM_WORDS else float(x)


def stated_months(quote: str) -> tuple[float, float] | None:
    """Age range stated in an onset description, in months (code, never the LLM)."""
    m = _DAY_OF_LIFE.search(quote)
    if m:
        v = to_months(int(m.group(1)), "day")
        return v, v
    m = _RANGE.search(quote)
    if m:
        return to_months(_num(m.group(1)), m.group(3)), to_months(_num(m.group(2)), m.group(3))
    m = _FIRST.search(quote)
    if m:
        return 0, to_months(_num(m.group(1)), m.group(2))
    m = _AGE.search(quote)
    if m:
        v = to_months(_num(m.group(1)), m.group(2))
        return v, v
    m = _AGE_YEARS.search(quote)
    if m:
        v = to_months(_num(m.group(1)), "year")
        return v, v
    return None


def map_onset(quote: str | None) -> dict:
    """Onset description -> HPO onset term(s) and the HPO-defined month interval used for scoring.

    A stated age is placed in the onset term(s) whose HPO interval contains it (a range takes every term it
    touches); otherwise a named period ("since birth", "in infancy", "childhood") picks its term.
    The interval compared with diseases is the HPO one, not the stated number."""
    out = {"hpo_onset": [], "months_min": None, "months_max": None, "stated_months": None,
           "approximate": bool(quote and _APPROX.search(quote))}
    if not quote:
        return out
    from aitx.disease.hpo import INF, ONSET_MONTHS, ONSET_WORDS, onset_terms_for_months
    st = stated_months(quote)
    if st and None not in st:
        terms = onset_terms_for_months(*st)
        out.update(stated_months=list(st), method="age stated in the text, placed in the HPO onset interval")
    else:
        terms = [(t, lbl) for rx, t, lbl in ONSET_WORDS if re.search(rx, quote, re.I)][:1]
        out["method"] = "onset period named in the text"
    if not terms:
        out["reasons"] = ["onset description could not be mapped to an HPO onset term"]
        return out
    lo = min(ONSET_MONTHS[t][0] for t, _ in terms)
    hi = max(ONSET_MONTHS[t][1] for t, _ in terms)
    out.update(hpo_onset=[{"id": t, "label": lbl} for t, lbl in terms], months_min=lo,
               months_max=None if hi == INF else hi)
    return out


def verify_onset(o: dict, context: str) -> dict:
    """{quote} from the LLM -> verbatim check -> HPO onset term and interval (map_onset)."""
    q = (o or {}).get("quote")
    if not q:
        return {"quote": None, "verified": True, **map_onset(None)}
    if q not in context:
        return {"quote": q, "verified": False, "reasons": ["quote not found verbatim"], **map_onset(None)}
    return {"quote": q, "verified": True, **map_onset(q)}


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


STATES = ("present", "absent", "possible", "unknown")
SCOPES = ("patient", "general", "unknown")
CLINICAL_KINDS = ("diagnosis", "demographic", "history", "treatment", "lab", "trial_status")


def _source_item(item: dict, context: str, *, nullable: bool = False) -> None:
    """Required extraction fields and verbatim evidence; malformed answers stop."""
    if item["status"] not in STATES or item["scope"] not in SCOPES:
        raise ValueError("invalid clinical status or scope")
    quote = item["quote"]
    if quote is None and nullable and item["status"] == "unknown":
        return
    if not isinstance(quote, str) or not quote or quote not in context:
        raise ValueError("clinical quote not found verbatim")


def structure_clinical(parsed: dict, context: str) -> tuple[list, dict, dict]:
    """Check source evidence, retain native records, and project legacy scalar facts.

    Attribution is the one semantic extraction decision. Code never promotes general or
    uncertain observations to definite patient facts. No lab interpretation or unit inference.
    """
    from aitx.evidence.patient_facts import _number_in
    phenotypes, scalars, extras, background = (parsed[k] for k in
        ("phenotypes", "facts", "clinical_facts", "background"))
    if not all(isinstance(v, list) for v in (phenotypes, extras, background)) or not isinstance(scalars, dict):
        raise ValueError("invalid clinical extraction shape")
    for p in phenotypes:
        _source_item(p, context)
        if not isinstance(p["description"], str) or not p["description"].strip():
            raise ValueError("missing clinical feature description")
        if not isinstance(p["alternatives"], list) or not isinstance(p["presenting"], bool):
            raise ValueError("invalid feature alternatives/presenting")
        for key in ("onset", "severity", "course"):
            detail = p[key]
            if detail is not None and (not detail["quote"] or detail["quote"] not in context):
                raise ValueError(f"{key} quote not found verbatim")
    for f in extras:
        _source_item(f, context)
        if f["kind"] not in CLINICAL_KINDS:
            raise ValueError("unknown clinical fact kind")
        if not f["name"] or f["name"] not in f["quote"]:
            raise ValueError("clinical fact name not in quote")
        value = f["value"]
        if isinstance(value, str):
            if not value or value not in f["quote"]:
                raise ValueError("clinical fact text value not in quote")
        elif not _number_in(value, f["quote"]):
            raise ValueError("clinical fact number not in quote")
        if f["unit"] is not None and (not f["unit"] or f["unit"] not in f["quote"]):
            raise ValueError("clinical fact unit not in quote")
        if f["timing"] is not None and (not f["timing"] or f["timing"] not in context):
            raise ValueError("clinical fact timing not in source")
    for b in background:
        if not b["quote"] or b["quote"] not in context or not b["reason"]:
            raise ValueError("background missing verbatim source/reason")
    # Do not let a symptom-level date echoed into facts.onset become disease onset.
    scalars = {name: dict(value) for name, value in scalars.items()}
    onset = scalars["onset"]
    symptom_dates = [p for p in phenotypes if p["onset"] is not None
                     and p["onset"]["quote"] == onset["quote"]]
    if symptom_dates and not any(p["scope"] == "patient" and p["status"] == "present"
                                 and check_item(p, context)["presenting"] for p in symptom_dates):
        onset.update(source_status=onset["status"], status="unknown",
                     reason="date belongs to a symptom, not an explicit disease presentation")
    origin = scalars["variant_origin"]
    if origin["value"] == "de novo":
        origin.update(source_value=origin["value"], value="de_novo")
    if origin["value"] not in ("de_novo", "inherited", "unknown"):
        raise ValueError("invalid variant origin")
    if scalars["sex"]["value"] not in ("male", "female", "unknown"):
        raise ValueError("invalid sex value")
    projected = {}
    for name in ("age", "onset", "sex", "variant_origin", "family_history"):
        f = scalars[name]
        _source_item(f, context, nullable=True)
        required = {"age": ("value", "unit"), "sex": ("value",),
                    "variant_origin": ("value",), "family_history": ("statement",), "onset": ()}[name]
        for key in required:
            if key not in f:
                raise KeyError(f"facts.{name}.{key}")
        projected[name] = f if f["scope"] == "patient" and f["status"] == "present" else {}
    facts = verify_facts(projected, context)
    clinical = {"phenotypes": phenotypes, "facts": scalars, "items": extras,
                "background": background, "source_text": context}
    return phenotypes, facts, clinical


def extract(context: str, ont: Ontology, *, use_cache: bool = True, n: int = N_SAMPLES) -> dict:
    if not isinstance(context, str) or not context.strip():
        raise ValueError("clinical_context must be nonempty")
    if n != 1:
        raise ValueError("clinical extraction requires one sample")
    response = _parse(_cached_chat(_messages(context), 0, use_cache))
    if response.get("error"):
        raise ValueError(response["error"])
    raw, facts, clinical = structure_clinical(response["parsed"], context)
    items = []
    for p in raw:
        item = check_item(p, context)
        item.update(scope=p["scope"], source_status=p["status"], severity=p["severity"], course=p["course"])
        why = possible_phrase(context, p["quote"])
        if why and item["status"] == "present":
            item.update(status="possible", possible_because=why)
            item.pop("negated_quote", None)
        # Mapping a general/unknown-subject finding provides no patient evidence.
        if p["scope"] != "patient":
            item.update(checked=False)
            item["reasons"].append("not an attributed patient observation")
        items.append(item)
    items = map_items(items, context, ont, 0, use_cache)
    conflicts = []
    by_id = {}
    for p in items:
        if p["valid"]:
            by_id.setdefault(p["hpo_id"], []).append(p)
    for group in by_id.values():
        if {p["status"] for p in group} >= {"present", "absent"}:
            conflicts.extend(dict(p) for p in group)
            for p in group:
                p.update(status="unknown", conflict=True)
    # This adapter keeps scoring, disease recall, adjudication and Step 3 unchanged.
    # The canonical records below retain absent/possible/unknown, unmapped findings,
    # repetitions and all original quotes; no vote or hierarchy aggregation discards them.
    kept = [dict(p, status="excluded" if p["status"] == "absent" else "present",
                 votes=1, merged_from=[]) for p in items
            if p["valid"] and p["scope"] == "patient" and p["status"] in ("present", "absent")]
    clinical["phenotypes"] = items
    clinical["produced_by"] = {"prompt_version": PROMPT_VERSION,
                               "served_model": response["served_model"], "call_id": response.get("call_id")}
    facts["clinical"] = clinical
    return {"phenotypes": kept, "phenotype_conflicts": conflicts, "unstable_phenotypes": [],
            "rejected_phenotypes": [p for p in items if not p["valid"]],
            "patient_facts": facts, "fact_notes": [],
            "samples": [{"served_model": response["served_model"], "error": None,
                         "terms": sorted({(p["hpo_id"], p["status"]) for p in kept})}],
            "prompt_version": PROMPT_VERSION}

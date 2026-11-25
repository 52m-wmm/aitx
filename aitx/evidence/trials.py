"""ClinicalTrials.gov transport, source parsing and shared matching/ranking helpers.

The only production search plan lives in aitx.step3.b.screening.
"""
from __future__ import annotations

import json
import re

from aitx.evidence import genecontext as GC
import urllib.parse

from aitx import http

API = "https://clinicaltrials.gov/api/v2/studies"
PAGE_SIZE = 100


def study_url(nct: str) -> str:
    return f"https://clinicaltrials.gov/study/{nct}"


# ------------------------------------------------------------------ retrieval

def search(params: dict, *, use_cache: bool = True) -> dict:
    """All pages of one query, no status filter. Returns the search record and the flattened studies."""
    base = {**params, "pageSize": str(PAGE_SIZE), "countTotal": "true", "format": "json"}
    urls, studies, total, accessed, token = [], [], None, [], None
    while True:
        q = {**base, **({"pageToken": token} if token else {})}
        url = API + "?" + urllib.parse.urlencode(q)
        f = http.get(url, use_cache=use_cache, timeout=60)
        d = json.loads(f.text)
        urls.append(url)
        accessed.append(f.accessed_at)
        if total is None:
            total = d.get("totalCount")
        studies += [flat(s) for s in d.get("studies", [])]
        token = d.get("nextPageToken")
        if not token:
            break
    return {"database": "clinicaltrials.gov", "endpoint": API, "query": params, "url": urls[0], "page_urls": urls,
            "queried_at": min(accessed), "total_count": total, "n_retrieved": len(studies), "studies": studies,
            "complete": total == len(studies)}


def flat(study: dict) -> dict:
    p = study.get("protocolSection", {})
    idm, st, de = p.get("identificationModule", {}), p.get("statusModule", {}), p.get("designModule", {})
    cm, el = p.get("conditionsModule", {}), p.get("eligibilityModule", {})
    return {"protocolSection": p, "nct": idm.get("nctId"), "title": idm.get("briefTitle"), "acronym": idm.get("acronym"),
            "status": st.get("overallStatus"), "last_update": (st.get("lastUpdatePostDateStruct") or {}).get("date"),
            "study_type": (de.get("studyType") or "").lower() or None, "phases": de.get("phases") or [],
            "conditions": cm.get("conditions") or [], "keywords": cm.get("keywords") or [],
            "interventions": [i.get("name") for i in (p.get("armsInterventionsModule", {}).get("interventions") or [])],
            "min_age": el.get("minimumAge"), "max_age": el.get("maximumAge"), "sex": el.get("sex"),
            "healthy_volunteers": el.get("healthyVolunteers"), "criteria": el.get("eligibilityCriteria") or "",
            "population_groups": (p.get("armsInterventionsModule") or {}).get("armGroups") or []}


# ------------------------------------------------------------------ relevance (contract step 2)

_ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5"}
_STOP = {"of", "the", "and", "type", "with", "due", "to", "a", "an", "in", "or"}


def _tokens(s: str) -> list[str]:
    return [_ROMAN.get(t, t) for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in _STOP]


def name_matches(name: str, text: str) -> bool:
    """Does `text` (one Condition or Keyword entry) name the disease? Word order free ("Type 1 Primary
    Hyperoxaluria" = "primary hyperoxaluria type 1"); a one-word name (an abbreviation such as PH1)
    must appear as a whole word with the same letter case."""
    want = _tokens(name)
    if not want:
        return False
    if len(want) == 1:
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(name.strip())}(?![A-Za-z0-9])", text) is not None
    have = set(_tokens(text))
    return all(t in have for t in want)


# words that make a gene symbol in a Condition / Keyword entry mean the gene (short symbols such as OTC
# are also ordinary abbreviations: "over-the-counter", "Outside the Cage (OTC)")
_GENE_CONTEXT = r"(?:gene|genes|mutation|mutations|variant|variants|deficiency|deficient|related|associated|pathogenic|disorder|disease|syndrome|cdg|carrier|carriers)"


def gene_matches(gene: str, text: str) -> bool:
    """Gene symbol as a whole word in the same case, next to a gene word in any case ("SLC35A2-CDG",
    "OTC deficiency", "CFTR mutation", "Mutation in CFTR", "GRIN2B-related"). A bare symbol does not count
    ("OTC", "Hearing Aid OTC", "OTC-Pre Pub") unless the symbol cannot be an ordinary abbreviation: it
    contains a digit or has 5+ characters (SLC35A2, GRIN2B, as in a keyword list of gene symbols)."""
    g = rf"(?<![A-Za-z0-9]){re.escape(gene)}(?![A-Za-z0-9])"
    if (re.search(r"\d", gene) or len(gene) >= 5) and re.search(g, text):
        return True
    ctx = rf"(?i:{_GENE_CONTEXT})"
    return re.search(rf"{g}\W{{1,3}}{ctx}\b|(?<![A-Za-z]){ctx}\W{{1,3}}(?:(?i:in|of)\W+)?{g}", text) is not None


def gene_names_condition(gene: str, entry: str, study: dict) -> bool:
    """A gene match counts only as the patient's genetic condition (decision 2026-11-10, blind test): never in a
    cancer study, and never as a marker ("LRPPRC Positive" colorectal cancer). The same rule 3c has used for
    precedents since 2026-11-05 (genecontext)."""
    if not gene_matches(gene, entry):
        return False
    whole = " ".join([study.get("title") or ""] + list(study.get("conditions") or []) + list(study.get("keywords") or []))
    return not GC.cancer_context(whole) and not GC.biomarker_use(gene, entry)


def is_abbrev(name: str) -> bool:
    """A short upper-case abbreviation: one token, no lower-case letter, at most 5 letters (digits and hyphens
    allowed): LS, LSS, CMT, PH1, CHNG6, STISS. Such a name never counts on its own (fix plan N1, 2026-11-11):
    "LS" also stands for limited-stage lung cancer, an HIV antibody suffix, lumbar stenosis..."""
    n = (name or "").strip()
    return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9\-]*", n)) and 1 <= sum(ch.isalpha() for ch in n) <= 5


def corroboration(study: dict, names: list[str], gene: str) -> str | None:
    """What else in the same record names this patient's disease: a full name (not an abbreviation) in the title,
    a Condition or a Keyword, or the gene as the patient's condition. None when nothing does."""
    full = [n for n in names if n and not is_abbrev(n)]
    for text in [study.get("title") or ""] + list(study.get("conditions") or []) + list(study.get("keywords") or []):
        for n in full:
            if name_matches(n, text):
                return n
        if gene and gene_names_condition(gene, text, study):
            return gene
    return None


def _names_entry(n: str, entry: str, study: dict, names: list[str], gene: str) -> tuple[bool, str | None]:
    """(match, corroborated by) for one name and one entry; an abbreviation needs corroboration."""
    if not name_matches(n, entry):
        return False, None
    if not is_abbrev(n):
        return True, None
    by = corroboration(study, names, gene)
    return by is not None, by


def relevance(study: dict, names: list[str], gene: str) -> dict | None:
    """Which registry field names the branch disease or gene; None = not relevant (filtered). A short abbreviation
    alone never makes a study relevant: the same record must also carry a full name or the gene (fix plan N1)."""
    for field in ("conditions", "keywords"):
        for entry in study[field]:
            for n in names:
                ok, by = _names_entry(n, entry, study, names, gene)
                if ok:
                    rel = {"by": "disease", "field": field, "entry": entry, "name": n}
                    return {**rel, "corroborated_by": by} if by else rel
            if gene and gene_names_condition(gene, entry, study):
                return {"by": "gene", "field": field, "entry": entry, "name": gene}
    return None


def abbrev_only(study: dict, names: list[str]) -> str | None:
    """The abbreviation a not-relevant study matched on its own, if any (for the exclusion reason)."""
    for field in ("conditions", "keywords"):
        for entry in study[field]:
            for n in names:
                if is_abbrev(n) and name_matches(n, entry):
                    return n
    return None


def exclusion_reason(study: dict, names: list[str], gene: str) -> str:
    """Why a study is not relevant, in the words of the rule that excluded it (fix plan O3, 2026-11-11: cancer studies
    excluded by the gene-as-condition rule still said "no entry names the gene", though their entries did)."""
    ab = abbrev_only(study, names)
    if ab:
        return (f"only the short abbreviation '{ab}' matched, and nothing else in the record names the disease or "
                f"gene")
    if gene and any(gene_matches(gene, e) for e in list(study.get("conditions") or []) + list(study.get("keywords") or [])):
        return ("the gene is named only in a cancer study or as a marker (tumour status, expression), not as the "
                "patient's condition")
    return "no Condition or Keyword entry names the disease or gene"


def specific(study: dict, names: list[str], gene: str) -> bool:
    """Every listed condition names the branch disease or gene (not a many-disease study)."""
    conds = study["conditions"]
    return bool(conds) and all(any(_names_entry(n, c, study, names, gene)[0] for n in names)
                               or (gene and gene_names_condition(gene, c, study)) for c in conds)


# ------------------------------------------------------------------ structured prefilter (contract step 3)

_AGE_UNITS = {"year": 12.0, "month": 1.0, "week": 12 / 52.1775, "day": 12 / 365.25, "hour": 12 / 8766, "minute": 12 / 525960}


def age_months(s: str | None) -> float | None:
    """Registry age ('18 Years', '1 Month', '6 Weeks') in months; None if absent or unreadable."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(year|month|week|day|hour|minute)s?\s*", (s or "").lower())
    return float(m.group(1)) * _AGE_UNITS[m.group(2)] if m else None


def prefilter(study: dict, patient_age_months: float | None, patient_sex: str | None) -> dict:
    """Registry age / sex limits and healthy-volunteer-only studies against the patient. Unknown patient
    facts keep the study (result unknown -> at most conditional)."""
    checks = []
    lo, hi = age_months(study["min_age"]), age_months(study["max_age"])
    if lo is not None or hi is not None:
        limit = f"{study['min_age'] or 'no minimum'} to {study['max_age'] or 'no maximum'}"
        if patient_age_months is None:
            checks.append({"field": "age", "registry": limit, "result": "unknown"})
        else:
            ok = (lo is None or patient_age_months >= lo) and (hi is None or patient_age_months <= hi)
            checks.append({"field": "age", "registry": limit, "result": "pass" if ok else "fail"})
    sex = (study["sex"] or "ALL").upper()
    if sex in ("MALE", "FEMALE"):
        if patient_sex not in ("male", "female"):
            checks.append({"field": "sex", "registry": sex, "result": "unknown"})
        else:
            checks.append({"field": "sex", "registry": sex, "result": "pass" if patient_sex.upper() == sex else "fail"})
    # healthyVolunteers=true only says healthy people are accepted; the study is healthy-only when every
    # listed condition is a "healthy" entry
    if study["healthy_volunteers"] and study["conditions"] and all(re.search(r"\bhealthy\b", c, re.I) for c in study["conditions"]):
        checks.append({"field": "healthy_volunteers", "registry": "healthy volunteers only", "result": "fail"})
    res = [c["result"] for c in checks]
    return {"checks": checks, "result": "fail" if "fail" in res else "unknown" if "unknown" in res else "pass"}


# ------------------------------------------------------------------ ranking (contract step 4)

_PHASE = {"PHASE4": 4, "PHASE3": 3, "PHASE2": 2, "PHASE1": 1, "EARLY_PHASE1": 0.5}


CATEGORIES = ['基因/靶向治疗干预', '药物/对症治疗干预', '诊断性测定/生物标志物评估', '观察性/自然史登记', '研究性质待核实']


def classify_pathway(protocol: dict) -> dict:
    design = protocol['designModule']
    arms = protocol['armsInterventionsModule'] if 'armsInterventionsModule' in protocol else {}
    interventions = arms['interventions'] if 'interventions' in arms else []
    info = design['designInfo']
    purpose = info['primaryPurpose'] if 'primaryPurpose' in info else None
    text = json.dumps(interventions, ensure_ascii=False) + ' ' + protocol['identificationModule']['briefTitle']
    diagnostic = purpose == 'DIAGNOSTIC' or any(i['type'] == 'DIAGNOSTIC_TEST' for i in interventions)
    measurement = bool(re.search(r'test system|biomarker|histopathology|measurement|validation|genetic testing', text, re.I))
    therapeutic = design['studyType'] == 'INTERVENTIONAL' and purpose == 'TREATMENT'
    targeted = any(i['type'] == 'GENETIC' for i in interventions) or bool(re.search(
        r'gene[ -](?:therapy|editing)|base edit|\bsiRNA\b|\bRNAi\b|targeted therapy', text, re.I))
    if therapeutic:
        rank = 0 if targeted else 1
    elif diagnostic or measurement:
        rank = 2
    elif design['studyType'] == 'OBSERVATIONAL':
        rank = 3
    else:
        rank = 4
    return {'category_rank': rank, 'category': CATEGORIES[rank], 'therapeutic': therapeutic,
            'evidence': {'design': design, 'interventions': interventions, 'arm_groups': arms}}


def clinical_priority_key(candidate):
    p = candidate['pathway']
    known, pending = p['known_conditions'], p['pending_prerequisites']
    return (p['category_rank'], known is None, -len(known) if known is not None else 0,
            pending is None, len(pending) if pending is not None else 0, candidate['nct_id'])


def rank_key(study: dict, names: list[str], gene: str) -> tuple:
    """Registry-derived pathway class, known checks, pending checks, then stable registry ties."""
    category = classify_pathway(study["protocolSection"])["category_rank"] if "protocolSection" in study else (0 if study["study_type"] == "interventional" else 3)
    checks = study["prefilter"]["checks"] if "prefilter" in study else []
    return (category, -sum(c["result"] == "pass" for c in checks), sum(c["result"] == "unknown" for c in checks), not specific(study, names, gene),
            -max([_PHASE.get(p, 0) for p in study["phases"]] or [0]), _neg_date(study["last_update"]))


def _neg_date(d: str | None) -> tuple:
    parts = [int(x) for x in (d or "0").split("-") if x.isdigit()]
    return tuple(-x for x in parts + [0] * (3 - len(parts)))


# ------------------------------------------------------------------ criterion splitting (contract step 5)

_HEADER = re.compile(r"^\W*(?:key\s+|main\s+|general\s+)?(inclusion|exclusion)\s+criteri\w*\b[^:\n]{0,80}:?\s*(.*)$", re.I)
_BULLET = re.compile(r"^(\s*)(?:[*\-•·]|\d{1,3}[.)]|[a-zA-Z][.)]|\(\w{1,3}\))\s+(.*\S)\s*$")


def split_criteria(text: str) -> list[dict]:
    """EligibilityCriteria -> one item per criterion, verbatim (registry markdown escapes kept so every
    item is a substring of the record). kind: inclusion / exclusion; lines before the first heading are
    kind 'enrollment_note' with preamble=True. Nested bullets keep a `parent` id and their indent level."""
    items, kind, n, stack = [], None, {"inclusion": 0, "exclusion": 0, "other": 0}, []

    def add(k: str, body: str, level: int) -> None:
        body = body.strip()
        if not body:
            return
        n[k] += 1
        prefix = {"inclusion": "inc", "exclusion": "exc", "other": "pre"}[k]
        while stack and stack[-1][0] >= level:
            stack.pop()
        item = {"id": f"{prefix}{n[k]}", "kind": "enrollment_note" if k == "other" else k, "text": body, "level": level,
                "parent": stack[-1][1] if stack else None}
        if k == "other":
            item["preamble"] = True
        items.append(item)
        stack.append((level, item["id"]))

    for line in text.splitlines():
        if not line.strip():
            continue
        h = _HEADER.match(line)
        if h and len(line.strip()) <= 120 + len(h.group(2)):
            kind = h.group(1).lower()
            stack.clear()
            add(kind, h.group(2), 0)
            continue
        b = _BULLET.match(line)
        if b:
            add(kind or "other", b.group(2), 1 + len(b.group(1).expandtabs(4)) // 2)
        else:
            add(kind or "other", line, 0)
    return items


def unescape(s: str) -> str:
    """Registry markdown escapes for display (\\< -> <); the stored requirement stays verbatim."""
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!<>|~])", r"\1", s)


# ------------------------------------------------------------------ one branch (contract steps 1-4)

def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())










def _ex(st: dict, reason: str, detail: str) -> dict:
    return {"nct": st["nct"], "title": st["title"], "status": st["status"], "reason": reason, "detail": detail,
            "last_update": st["last_update"], "url": study_url(st["nct"])}

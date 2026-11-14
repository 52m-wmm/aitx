"""Step 3b, code-only parts: ClinicalTrials.gov retrieval, status grouping, relevance filter,
structured prefilter, ranking with a cap, and criterion splitting (contract docs/step3b_contract.md, steps 1-5).

No LLM here. The per-criterion mapping to structured fields (LLM) and the ledger entries are added
on top of `plan_branch`, whose result says, for one diagnosis branch, which studies are analysed and
why every other returned study is not.
"""
from __future__ import annotations

import json
import re

from aitx.evidence import genecontext as GC
import urllib.parse

from aitx import http

API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ("NCTId,BriefTitle,Acronym,OverallStatus,Phase,StudyType,Condition,Keyword,InterventionName,"
          "MinimumAge,MaximumAge,Sex,HealthyVolunteers,EligibilityCriteria,LastUpdatePostDate")
OPEN = ("RECRUITING", "NOT_YET_RECRUITING")
K = 10                       # studies analysed criterion by criterion per branch (contract decision 4)
MAX_LISTED_CLOSED = 50       # relevant studies with other statuses listed by name (most recently updated)
MAX_NAMES = 3                # disease names searched per branch
PAGE_SIZE = 100


def study_url(nct: str) -> str:
    return f"https://clinicaltrials.gov/study/{nct}"


# ------------------------------------------------------------------ retrieval

def search(params: dict, *, use_cache: bool = True) -> dict:
    """All pages of one query, no status filter. Returns the search record and the flattened studies."""
    base = {**params, "pageSize": str(PAGE_SIZE), "countTotal": "true", "format": "json", "fields": FIELDS}
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
    return {"nct": idm.get("nctId"), "title": idm.get("briefTitle"), "acronym": idm.get("acronym"),
            "status": st.get("overallStatus"), "last_update": (st.get("lastUpdatePostDateStruct") or {}).get("date"),
            "study_type": (de.get("studyType") or "").lower() or None, "phases": de.get("phases") or [],
            "conditions": cm.get("conditions") or [], "keywords": cm.get("keywords") or [],
            "interventions": [i.get("name") for i in (p.get("armsInterventionsModule", {}).get("interventions") or [])],
            "min_age": el.get("minimumAge"), "max_age": el.get("maximumAge"), "sex": el.get("sex"),
            "healthy_volunteers": el.get("healthyVolunteers"), "criteria": el.get("eligibilityCriteria") or ""}


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


def rank_key(study: dict, names: list[str], gene: str) -> tuple:
    """Interventional first -> single-disease studies first -> higher phase -> more recently updated."""
    return (study["study_type"] != "interventional", not specific(study, names, gene),
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
    kind 'other' with preamble=True. Nested bullets keep a `parent` id and their indent level."""
    items, kind, n, stack = [], None, {"inclusion": 0, "exclusion": 0, "other": 0}, []

    def add(k: str, body: str, level: int) -> None:
        body = body.strip()
        if not body:
            return
        n[k] += 1
        prefix = {"inclusion": "inc", "exclusion": "exc", "other": "pre"}[k]
        while stack and stack[-1][0] >= level:
            stack.pop()
        item = {"id": f"{prefix}{n[k]}", "kind": k, "text": body, "level": level,
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


def parent_names(label: str, parents: list[tuple[str, str]]) -> list[str]:
    """Names of the disease one level up, used as extra search names when the diagnosis is a numbered or named subtype
    of it (user decision 2026-11-12: ALS18 -> amyotrophic lateral sclerosis; the subtype name alone missed every
    general ALS trial). Only a parent whose name is the start of the subtype's name counts ("amyotrophic lateral
    sclerosis" for "amyotrophic lateral sclerosis type 18"), so a broad grouping ("motor neuron disease") never does.
    Trials limited to other genes are then ruled out by the genotype rule (criteria.other_gene_required)."""
    child = _words(label)
    out = []
    for _, plabel in parents:
        pw = [w for w in _words(plabel) if w not in INHERITANCE_WORDS]
        if pw and len(pw) < len(child) and child[:len(pw)] == pw and plabel not in out:
            out.append(plabel)
    return out


# words that say how a disease is inherited, not which disease it is: MONDO puts "familial amyotrophic lateral
# sclerosis" between ALS18 and ALS (2026-11-13), so they are ignored when matching a parent's name
INHERITANCE_WORDS = {"familial", "hereditary", "inherited", "autosomal", "dominant", "recessive", "x", "linked"}
ANCESTOR_LEVELS = 3


def ancestors_up(mondo_id: str, parents_of, levels: int = ANCESTOR_LEVELS) -> list[tuple[str, str]]:
    """MONDO ancestors (id, label), nearest first, up to `levels` steps: parents_of(id) -> [(id, label)]."""
    out, frontier, seen = [], [mondo_id], {mondo_id}
    for _ in range(levels):
        nxt = []
        for mid in frontier:
            for pid, plabel in parents_of(mid):
                if pid not in seen:
                    seen.add(pid)
                    out.append((pid, plabel))
                    nxt.append(pid)
        frontier = nxt
    return out


def plan_branch(names: list[str], gene: str | None, patient_age_months: float | None, patient_sex: str | None,
                *, use_cache: bool = True) -> dict:
    """Search by disease names (at most 3) and by gene, then sort every returned study into exactly one of:
    analysed (open, relevant, prefilter pass or unknown, within top K), over_cap (same, beyond K),
    ineligible (open, relevant, registry age / sex / healthy-only rules the patient out -> not_applicable
    action with the registry field as the requirement; no LLM needed), excluded (not relevant, or
    another status; with the reason)."""
    names = [n for n in dict.fromkeys(names) if n]
    # an abbreviation is never a search term on its own (fix plan N1): search with the first full names, match with
    # those plus the abbreviations, which count only when the same record also carries a full name or the gene
    search_names = [n for n in names if not is_abbrev(n)][:MAX_NAMES]
    names = search_names + [n for n in names if is_abbrev(n)]
    searches = [search({"query.cond": n}, use_cache=use_cache) for n in search_names]
    if gene:
        searches.append(search({"query.term": gene}, use_cache=use_cache))
    seen: dict[str, dict] = {}
    for s in searches:
        for st in s["studies"]:
            seen.setdefault(st["nct"], st)
    open_rel, closed_rel, excluded, ineligible = [], [], [], []
    for st in seen.values():
        rel = relevance(st, names, gene or "")
        if not rel:
            excluded.append(_ex(st, "relevance", exclusion_reason(st, names, gene or "")))
        elif st["status"] not in OPEN:
            closed_rel.append(st)
        else:
            pre = prefilter(st, patient_age_months, patient_sex)
            st = {**st, "relevance": rel, "prefilter": pre, "specific": specific(st, names, gene or "")}
            if pre["result"] == "fail":
                ineligible.append(st)        # open and relevant, but the registry limits rule the patient out
            else:
                open_rel.append(st)
    closed_rel.sort(key=lambda s: _neg_date(s["last_update"]))
    for st in closed_rel:
        excluded.append(_ex(st, "status", f"overall status {st['status']}"))
    open_rel.sort(key=lambda s: rank_key(s, names, gene or ""))
    analysed, over_cap = open_rel[:K], open_rel[K:]
    return {"names": names, "gene": gene, "searches": [{k: v for k, v in s.items() if k != "studies"} for s in searches],
            "n_unique": len(seen), "analysed": analysed,
            "over_cap": [{"nct": s["nct"], "title": s["title"], "study_type": s["study_type"],
                          "prefilter": s["prefilter"]["result"], "url": study_url(s["nct"])} for s in over_cap],
            "ineligible": sorted(ineligible, key=lambda s: rank_key(s, names, gene or "")),
            "excluded": excluded, "n_closed_relevant": len(closed_rel),
            "closed_listed": [e["nct"] for e in excluded if e["reason"] == "status"][:MAX_LISTED_CLOSED]}


def _ex(st: dict, reason: str, detail: str) -> dict:
    return {"nct": st["nct"], "title": st["title"], "status": st["status"], "reason": reason, "detail": detail,
            "last_update": st["last_update"], "url": study_url(st["nct"])}

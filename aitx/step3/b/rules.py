"""Deterministic rules used by conflict screening; no model calls or Ledger writes.

Unknown scope and missing patient facts remain unknown. Disease-gene mismatch
is independent of intervention type; this module does not infer full eligibility.
"""
from __future__ import annotations
import re
import json
from aitx import caseinput
from aitx.evidence import genecontext as GC, ledger as LG, patient_matching as E, trials as T


FACTS = ("age", "sex", "diagnosis", "genetic_confirmation", "variant", "variant_class", "zygosity", "lab", "egfr",
         "organ_function", "weight", "gestational_age", "current_medication", "prior_therapy", "other_trial",
         "pregnancy", "administrative", "header", "other")



OPS = (">=", ">", "<=", "<", "==", "")



_RANGE = re.compile(r"\d\s*(?:-|–|—|to|through)\s*\d", re.I)       # "10 to 17", "0-90": inclusive on both ends



_GE = re.compile(r"≥|>=|\bat least\b|\b(?:or|and)\s+(?:older|above|over)\b|\bor more\b|\bor greater\b|\bminimum\b|\binclusive\b", re.I)



_LE = re.compile(r"≤|<=|\bat most\b|\b(?:or|and)\s+(?:younger|under|below)\b|\bor less\b|\bup to\b|\bmaximum\b|\bno more than\b|\bnot exceeding\b|\binclusive\b", re.I)



_GT = re.compile(r"(?<![<≤])>(?!=)|\bgreater than\b|\bmore than\b|\bover\b|\babove\b|\bolder than\b|\bexceed", re.I)



_LT = re.compile(r"(?<![>≥])<(?!=)|\bless than\b|\bunder\b|\bbelow\b|\byounger than\b|\blower than\b", re.I)



def sign_ok(op: str, quote: str) -> bool:
    """The comparison sign must be the one written (>= vs >): a sign is accepted when the quote has its cue and
    no cue of a different strictness in the same direction."""
    if op in ("", "=="):
        return True
    rng = bool(_RANGE.search(quote))
    ge, le = bool(_GE.search(quote)) or rng, bool(_LE.search(quote)) or rng
    gt = bool(_GT.search(_GE.sub(" ", quote)))
    lt = bool(_LT.search(_LE.sub(" ", quote)))
    return {">=": ge, ">": gt and not ge, "<=": le, "<": lt and not le}[op]



def _numbers(value) -> list[float]:
    vals = value if isinstance(value, list) else [value]
    out = []
    for v in vals:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(float(v))
        elif isinstance(v, str) and re.fullmatch(r"\s*-?\d+(?:\.\d+)?\s*", v):
            out.append(float(v))
    return out



def check_mapping(m: dict, items: dict[str, dict]) -> str | None:
    """Why a mapping is rejected, or None. Code only."""
    it = items.get(str(m.get("id")))
    if not it:
        return "unknown criterion id"
    fact, quote = m.get("fact"), str(m.get("quote") or "")
    if fact not in FACTS:
        return f"unknown fact type {fact!r}"
    if m.get("op", "") not in OPS:
        return f"unknown comparison {m.get('op')!r}"
    if not LG.quote_in(quote, T.unescape(it["text"])):
        return "quote not verbatim in the criterion"
    in_quote = [float(n.replace(",", "")) for n in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", quote)]   # "100,000"
    for n in _numbers(m.get("value")):
        if not any(abs(n - q) < 1e-9 for q in in_quote):
            return f"threshold {n:g} not in the quote"
    if m.get("op") in ("<", "<=", ">", ">=") and not _numbers(m.get("value")) and fact not in ("variant", "variant_class", "zygosity"):
        return "comparison without a threshold"
    if not sign_ok(m.get("op", ""), quote):
        return f"comparison {m.get('op')!r} not as written"
    if m.get("unit") and not re.search(rf"(?<![A-Za-zµμ]){re.escape(str(m['unit']).strip())}(?![A-Za-z])", quote):
        return "unit not in the quote"              # whole unit: "g/dL" is not in "mg/dL"
    return None



_GENE_WORDS = re.compile(r"\b(?:genes?|variants?|mutations?|mutated|duplications?|deletions?|pathogenic|alleles?|"
                         r"genetic(?:ally)?|genotyp\w*|carriers?)\b", re.I)



_NOT_REQUIRED = re.compile(r"\b(?:not|no|without|regardless|irrespective|need\s+not)\b", re.I)



_SOMATIC = re.compile(r"\b(?:tumou?rs?|somatic|cancer|carcinoma|neoplas\w*|malignan\w*)\b", re.I)



def other_gene_required(quote: str, branch: dict, pf: dict) -> list[str]:
    """Genes a genotype criterion requires that are not the patient's (fix plan D2, decision 2026-11-11): the
    patient's reported genotype is a known fact, so "genetic testing showing duplication of the PMP22 gene" is not met
    by an MPZ patient. Only when the criterion speaks of genes and names known gene symbols, none of them the
    patient's; a criterion that names no gene ("genetic confirmation of CMT") is left to the other rules."""
    if not _GENE_WORDS.search(quote or "") or _NOT_REQUIRED.search(quote) or _SOMATIC.search(quote):
        return []
    named = GC.genes_named(quote)
    mine = {branch.get("gene")} | {v["gene"] for v in pf.get("variants") or []}
    if not named or any(g in mine for g in named):
        return []
    # "a confirmed diagnosis of CDG or NGLY1 deficiency": an alternative that names no gene (a disease group that may
    # include the patient's) keeps the rule out; it decides only when every alternative names a gene
    # A variant-classification standard is not an alternative disease/cohort.
    alternatives = re.sub(r'\bACMG\s*/\s*AMP\b', 'classification standard', quote, flags=re.I)
    parts = [x for x in re.split(r"\bor\b|/|;", alternatives) if x.strip()]
    if len(parts) > 1 and any(not GC.genes_named(x) and _names_disease(x) for x in parts):
        return []
    return named



_DISEASE_WORD = re.compile(r"\b(?:deficiency|disease|disorders?|syndrome|dystroph\w*|neuropath\w*|"
                           r"encephalopath\w*|ataxia|CDG)\b", re.I)



def _names_disease(part: str) -> bool:
    """An alternative that names a disease: a disease word, or an upper-case acronym that is not a gene symbol ("coding
    or non-coding mutation" has neither - it is one condition, not two)."""
    if _DISEASE_WORD.search(part):
        return True
    acr = re.findall(r"(?<![A-Za-z0-9])[A-Z]{2,6}(?![A-Za-z0-9])", part)
    return any(a not in GC.known_genes() for a in acr)



def single_target_conflict(study: dict, patient_genes: list[str]) -> dict | None:
    """A mandatory disease gene differs from all reported patient genes.

    This compares disease/therapy targets, not an unreported gene's test result.
    Local cohort requirements, alternative gene paths and unclear scope cannot exclude.
    """
    if not patient_genes:
        return None
    raw = study['criteria']
    if 'population_groups' not in study:
        return None  # The caller has not supplied alternative-cohort context.
    inclusion = [x for x in T.split_criteria(raw) if x['kind'] == 'inclusion']
    text = '\n'.join(x['text'] for x in inclusion)
    # A heading can restrict the following requirement to a local path. Do not flatten it to AND.
    if re.search(r'\bcohort\b|\b(?:part|group)\s*[A-Z0-9]\b|\b(?:any|all|other)\s+(?:UCD|urea cycle disorders?)\b', text, re.I):
        return None
    pf = {'variants': [{'gene': gene} for gene in patient_genes]}
    required = [(x, other_gene_required(x['text'], {'gene': patient_genes[0]}, pf))
                for x in inclusion if not x['parent']
                and re.search(r'\b(?:mutations?|variants?|duplications?|deletions?|alleles?|carriers?|genotyp\w*|genetically confirmed)\b', x['text'], re.I)
                and not re.search(r'\b(?:optional|testing for|samples? for|analysis of|measurement of)\b', x['text'], re.I)]
    targets = set(g for x in inclusion if _GENE_WORDS.search(x['text'])
                  and not _NOT_REQUIRED.search(x['text']) for g in GC.genes_named(x['text']))
    title_genes = GC.genes_named(study['title'])
    if not targets and len(title_genes) == 1:
        gene = title_genes[0]
        if re.search(rf'\b{re.escape(gene)}(?:[- ]related)?[- ](?:deficiency|disease)\b', study['title'], re.I):
            targets = {gene}
            required.append(({'text': study['title'], 'source': 'title'}, [gene]))
    if set(title_genes) - targets:
        return None
    if len(targets) != 1 or targets.intersection(patient_genes):
        return None
    target = next(iter(targets))
    groups = study['population_groups']
    for group in groups:
        context = group['label'] + '\n' + (group['description'] if 'description' in group else '')
        named = set(GC.genes_named(context))
        if named - {target} or re.search(r'\b(?:any|all|other)\s+(?:UCD|urea cycle disorders?)\b|regardless of genotype', context, re.I):
            return None
        # Treatment/control arms share global inclusion criteria. A population
        # alternative (including healthy controls) must not be flattened away.
        if re.search(r'\bhealthy|\bunaffected|\bcaregivers?|\brelatives?|\bfamily members?|\bcohorts?\b', context, re.I):
            return None
        if (re.search(r'\bcontrols?\b', group['label'], re.I)
                and group.get('type') not in ('PLACEBO_COMPARATOR', 'ACTIVE_COMPARATOR', 'SHAM_COMPARATOR')
                and not re.search(r'\bplacebo|\bsham\b', context, re.I)):
            return None  # Unspecified controls may have different genetic eligibility.
    for item, genes in required:
        if genes == [target] and not relative_subject(item['text']) and not re.search(r'\b(?:if|unless|for participants|for patients)\b', item['text'], re.I):
            return {'axis': 'molecular', 'target_gene': target, 'patient_genes': patient_genes,
                    'trial_rule_quote': item['text'], 'other_cohort_applicable': False,
                    'quote_source': item['source'] if 'source' in item else 'criteria',
                    'reason': f"疾病基因不匹配：试验明确要求 {target}，病例已报告变异基因为 {'、'.join(patient_genes)}；无其他适用基因队列，不推断未报告基因检测阴性。"}
    return None



_RELATIVE_SUBJECT = re.compile(
    r'^\s*(?:(?:a|an|the|biological|first.degree|second.degree)\s+)*'
    r'(?:relatives?|family members?|siblings?|parents?|children|offspring)\s+of\b|'
    r'^\s*(?:(?:individuals|participants|patients|subjects)\s+(?:have|has|with)\s+)?(?:a\s+)?family history\b', re.I)



def relative_subject(text: str) -> bool:
    return bool(_RELATIVE_SUBJECT.search(text))



_ENROLLMENT = re.compile(
    r"(?:note:\s*)?(?:currently[, :]+)?"
    r"(?:(?:(?:the|this)\s+)?(?:[\w-]+\s+)?(?:study|trial)\s+is\s+)?(?:currently\s+)?"
    r"(?P<mode>only\s+(?:enrolling|recruiting|accepting)|(?:enrolling|recruiting|accepting)\s+only|open\s+only\s+to|closed\s+to)"
    r"\s+(?P<population>.+?)\.?", re.I)



_NOTE_AGE = re.compile(
    r"(?:(?:aged?|ages)\s+)?(?:(?P<cue><=|>=|≤|≥|<|>|under|below|younger than|less than|"
    r"over|above|older than|greater than|at least|at most|up to)\s*)?"
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>years?|months?)"
    r"(?P<tail>\s+or\s+(?:older|younger))?(?:\s+(?:of age|old))?", re.I)



_NOTE_RANGE = re.compile(r"(?:aged?\s+)?(?P<lo>\d+(?:\.\d+)?)\s*(?:to|[-–])\s*"
                         r"(?P<hi>\d+(?:\.\d+)?)\s*(?P<unit>years?|months?)(?:\s+(?:of age|old))?", re.I)



def enrollment_note_lines(study: dict, pf: dict) -> list[dict]:
    """Keep every preamble; decide only whole, explicit current population restrictions.

    Unrecognised cohort labels, historical/conditional notes and compound alternatives remain unknown.
    No LLM or prompt change: existing body mappings can be replayed without losing the notes.
    """
    out = []
    scoped_context = False
    for item in T.split_criteria(study['criteria']):
        if not item.get('preamble'):
            continue
        text = T.unescape(item['text'])
        kind, status, fact = 'inclusion', 'unknown', {'field': 'other', 'value': None, 'quote': None, 'step': None}
        why, mappings = 'enrollment note: population restriction or scope not resolved', []
        match = _ENROLLMENT.fullmatch(text.strip()) if not scoped_context and not item['parent'] else None
        if match:
            kind = 'exclusion' if re.sub(r'\s+', ' ', match['mode'].lower()) == 'closed to' else 'inclusion'
            population = re.sub(r'^(?:(?:potential|new|eligible)\s+)?(?:participants?|patients?|subjects?|volunteers?)\s+(?:who are\s+)?',
                                '', match['population'], flags=re.I)
            age, span = _NOTE_AGE.fullmatch(population), _NOTE_RANGE.fullmatch(population)
            if age:
                cue, tail = (age['cue'] or '').lower(), (age['tail'] or '').lower().strip()
                op = ('>=' if tail == 'or older' else '<=' if tail == 'or younger' else
                      '<=' if cue in ('<=', '≤', 'at most', 'up to') else
                      '>=' if cue in ('>=', '≥', 'at least') else
                      '<' if cue in ('<', 'under', 'below', 'younger than', 'less than') else
                      '>' if cue in ('>', 'over', 'above', 'older than', 'greater than') else '')
                if op and not (cue and tail):
                    mappings = [{'id': item['id'], 'fact': 'age', 'quote': population, 'op': op,
                                 'value': float(age['value']), 'unit': age['unit']}]
            elif span and float(span['lo']) <= float(span['hi']):
                mappings = [{'id': item['id'], 'fact': 'age', 'quote': population, 'op': op,
                             'value': float(span[key]), 'unit': span['unit']} for key, op in [('lo', '>='), ('hi', '<=')]]
            if mappings:
                errors = [check_mapping(m, {item['id']: item}) for m in mappings]
                if any(errors):
                    raise ValueError(f'invalid enrollment-note extraction: {errors}')
                months = pf['age_months']
                if months is not None:
                    comparisons = []
                    for m in mappings:
                        threshold = T.age_months(f"{m['value']} {m['unit']}")
                        comparisons.append({'<': months < threshold, '<=': months <= threshold,
                                            '>': months > threshold, '>=': months >= threshold}[m['op']])
                    status = 'satisfies' if all(comparisons) else 'does_not_satisfy'
                    fact = {'field': 'age', 'value': f'{months / 12:g} years', 'quote': pf['age_quote'], 'step': 2}
                    why = 'enrollment note: verified current age restriction'
                else:
                    fact = {'field': 'age', 'value': None, 'quote': None, 'step': None}
                    why = 'enrollment note: patient age not stated'
            elif population.lower() in ('male', 'males', 'female', 'females'):
                wanted = population.lower().rstrip('s')
                fact = {'field': 'sex', 'value': None, 'quote': None, 'step': None}
                why = 'enrollment note: patient sex not stated'
                if pf['sex'] in ('male', 'female'):
                    status = 'satisfies' if pf['sex'] == wanted else 'does_not_satisfy'
                    fact = E.sex_evidence(pf)
                    why = 'enrollment note: verified current sex restriction'
        # A following line cannot silently lose a cohort, arm, historical or conditional scope.
        scoped_context = scoped_context or bool(re.search(r'\b(?:cohorts?|arms?|groups?|previously|historically|if|when)\b', text, re.I))
        out.append({'kind': kind, 'text': text, 'patient_status': status, 'patient_fact': fact,
                    'note': why, 'details': {'enrollment_note': True, 'mappings': mappings},
                    'item': f"enrollment-note:{item['id']}"})
    return out



def registry_lines(study: dict, pf: dict) -> list[dict]:
    """Registry age / sex / healthy-volunteer fields (structured) as inclusion lines."""
    pre = study.get("prefilter") or T.prefilter(study, pf["age_months"], pf["sex"])
    out = []
    for c in pre["checks"]:
        st = {"pass": "satisfies", "fail": "does_not_satisfy", "unknown": "unknown"}[c["result"]]
        text = registry_text(study, c["field"])
        fact = ({"field": "age", "value": f"{pf['age_months'] / 12:g} years", "quote": pf["age_quote"], "step": 2}
                if c["field"] == "age" and pf["age_months"] is not None else
                E.sex_evidence(pf)
                if c["field"] == "sex" and pf["sex"] else
                # a healthy-volunteers-only study: the patient is not a healthy volunteer - the reported variant says so
                # (2026-11-13: the line had no quoted patient fact, which the ledger check rejects)
                {"field": "healthy_volunteers", "value": "patient with a reported disease-causing variant",
                 "quote": pf["variants"][0]["quote"], "step": 1}
                if c["field"] == "healthy_volunteers" and pf.get("variants") else
                {"field": c["field"], "value": None, "quote": None, "step": None})
        out.append({"kind": "inclusion", "text": text, "patient_status": st, "patient_fact": fact,
                    "note": "registry field", "details": {}, "item": f"registry:{c['field']}"})
    return out



def registry_source(study: dict) -> str:
    return (f"minimumAge: {study.get('min_age') or 'none'}; maximumAge: {study.get('max_age') or 'none'}; "
            f"sex: {study.get('sex') or 'ALL'}; healthyVolunteers: {json.dumps(study.get('healthy_volunteers'))}; "
            f"conditions: {'; '.join(study.get('conditions') or [])}")



def registry_text(study: dict, field: str) -> str:
    return {"age": f"minimumAge: {study.get('min_age') or 'none'}; maximumAge: {study.get('max_age') or 'none'}",
            "sex": f"sex: {study.get('sex') or 'ALL'}",
            "healthy_volunteers": f"conditions: {'; '.join(study.get('conditions') or [])}"}[field]



def confirmed(branch: dict, step1: dict, step2: dict) -> bool:
    """Step 2 resolved this branch as the diagnosis, the branch gene carries the patient's variant, and a ClinVar
    record of exactly that variant used for ranking is pathogenic or likely pathogenic (user decision 2026-11-15)."""
    p = step2.get("primary") or {}
    genes = {v.get("gene") for v in (step1 or {}).get("variants") or []}
    path = any(rec.get("used_for_ranking") and "athogenic" in str(rec.get("clinical_significance") or "")
               and "onflicting" not in str(rec.get("clinical_significance") or "")
               for cv in step2.get("clinvar") or [] for rec in cv.get("records") or [])
    return p.get("status") == "resolved" and p.get("id") == branch.get("id") and branch.get("gene") in genes and path



def confirmed_target_gene(branch: dict, case: dict, step1: dict, step2: dict) -> bool:
    """For target matching, an explicit named genetic diagnosis is also known evidence."""
    if confirmed(branch, step1, step2):
        return True
    primary = step2['primary']
    gene = branch['gene']
    return (primary['status'] == 'resolved' and primary['id'] == branch['id']
            and gene in {v['gene'] for v in step1['variants']}
            and re.search(rf'\b(?:diagnosed with|diagnosis of)\s+{re.escape(gene)}\s+deficiency\b',
                          caseinput.clinical_context(case), re.I) is not None)

"""Scoped conflict acceptance and retrieval relevance; never infer absent diagnoses.

These guards use saved patient facts and complete criterion items, not the model's
reason as evidence. Unresolved qualifiers and alternative populations stay unknown.
"""
from __future__ import annotations

import re

from aitx.evidence import genecontext as GC, trials as T


_ALTERNATIVE = re.compile(r'\bhealthy|\bunaffected|\bcontrols?\b|\brelatives?|\bcaregivers?|\bfamily members?', re.I)
_SCOPED = re.compile(r'\bcohort\b|\b(?:part|group)\s+[A-Z0-9]\b', re.I)
_QUALIFIED = re.compile(
    r'\b(?:if|unless|except|within|prior|previous|history|treated|treatment|requiring|requires|'
    r'received|receiving|resolved|cured|suspected|possible|without|negative|no|not)\b|\d', re.I)
_CANCER = re.compile(r'\b(?:cancers?|carcinoma|tumou?rs?|malignan\w*|lymphoma|leukemia|leukaemia|myeloma|sarcoma)\b', re.I)
_LOW_PLATELETS = re.compile(r'\bthrombocytopen\w*|\bITP\b', re.I)
_HIGH_PLATELETS = re.compile(r'\bthrombocytosis\b|\bthrombocythemia\b', re.I)
_NF2 = re.compile(r'\bNF2(?:[- ](?:SWN|related))?\b|\bneurofibromatosis\s+(?:type\s+)?(?:2|II)\b', re.I)
_NF1 = re.compile(r'\bNF1\b|\bneurofibromatosis\s+(?:type\s+)?(?:1|I)\b', re.I)
_DPPM = re.compile(r'\bDPPMs?\b|\bpurine[s]?\s*(?:and|&|[-/])\s*pyrimidine[s]?\b', re.I)


def disease_scope(study, patient, facts, names):
    """Reject an unrelated *patient-disease* route, not all human participation.

Independent relative/control routes are recorded, never asserted ineligible.
This runs before the older conservative whole-study alternative guard.
"""
    genes = {v['gene'] for v in facts['variants']}
    if not genes:
        return None
    items = [i for i in T.split_criteria(study['criteria']) if i['kind'] == 'inclusion']
    inclusion = '\n'.join(i['text'] for i in items)
    context = patient['clinical_context'] + '\n' + '\n'.join(names)
    declared = study['title'] + '\n' + '\n'.join(study['conditions'])
    groups = study['population_groups']
    group_text = '\n'.join(g['label'] + '\n' + (g['description'] if 'description' in g else '') for g in groups)
    # A matching reported gene anywhere in a possible patient path is reason
    # to retain it. Only exclusion text is deliberately outside this check.
    if any(_contains(inclusion + '\n' + group_text, gene) for gene in genes):
        return None
    if 'NF1' in genes and _NF1.search(inclusion + '\n' + group_text):
        return None
    if re.search(r'\b(?:other patient|any diagnosis|regardless of diagnosis|unselected patient)', group_text, re.I):
        return None
    category = None
    anchors = []
    targets = []
    if _NF2.search(declared) and 'NF2' not in genes and not _NF2.search(context):
        anchors = [i['text'] for i in items if _NF2.search(i['text']) and
                   re.search(r'\bdiagnos\w*\b|\bmust meet\b|\bmeet the.*criteria', i['text'], re.I) and
                   not re.search(r'\b(?:without|optional|unless|if|family history|first.degree relative)\b', i['text'], re.I)]
        if anchors:
            category, targets = 'different_disease_gene', ['NF2']
    elif _DPPM.search(declared) and not _DPPM.search(context):
        # The source declares its disease genes; no invented metabolic gene list.
        targets = sorted({m[1] for c in study['conditions']
                          if (m := re.match(r'^([A-Z][A-Z0-9]+)\b', c)) and m[1] in GC.known_genes()})
        anchors = [i['text'] for i in items if _DPPM.search(i['text']) and
                   re.search(r'(?:medical history.*consistent with|as a subject with a known)', i['text'], re.I)]
        if (targets and not genes.intersection(targets) and anchors
                and not re.search(r'\burate\b|\buric acid\b|\bpurine\w*\b|\bpyrimidine\w*\b', context, re.I)):
            category = 'different_disease_scope'
    if category is None:
        return None
    # Do not mistake a separate, unexplained patient cohort for an auxiliary
    # family/control route. Drug/dose arms may share the mandatory diagnosis.
    auxiliary = []
    for g in groups:
        if _ALTERNATIVE.search(g['label']):
            auxiliary.append({'label': g['label'], 'eligibility': 'unknown',
                              'description': g['description'] if 'description' in g else None})
        elif category == 'different_disease_scope' and not _DPPM.search(g['label'] + ' ' + (g['description'] if 'description' in g else '')):
            return None
    return {'id': study['nct'], 'nct': study['nct'], 'reason': 'relevance',
            'category': category, 'scope': 'patient_disease_candidates',
            'detail': '患者疾病候选范围不符：患者报告 ' + '、'.join(sorted(genes)) +
                      ('，试验患者路径明确要求NF2诊断。' if category == 'different_disease_gene' else
                       '，试验患者路径要求已知或疑似嘌呤/嘧啶代谢障碍（DPPM）。') +
                      '不推断另一疾病或基因检测阴性；亲属/对照路径如存在，资格仍未知。',
            'patient_context': patient['clinical_context'], 'patient_genes': sorted(genes),
            'conditions': study['conditions'], 'inclusion': inclusion, 'disease_scope_anchors': anchors,
            'declared_disease_genes': targets, 'auxiliary_populations': auxiliary,
            'url': T.study_url(study['nct'])}


def alternatives(study):
    """A treatment placebo is not a separate healthy/relative population."""
    for group in study['population_groups']:
        context = group['label'] + '\n' + (group['description'] if 'description' in group else '')
        if _ALTERNATIVE.search(context):
            if ('type' not in group or group['type'] not in
                    ('PLACEBO_COMPARATOR', 'ACTIVE_COMPARATOR', 'SHAM_COMPARATOR')):
                return True
    return bool(_ALTERNATIVE.search(study['criteria']) and
                re.search(r'\b(?:control group|healthy volunteers|unaffected relatives|caregiver cohort)\b',
                          study['criteria'], re.I))


def _items(study, kind):
    items = T.split_criteria(study['criteria'])
    by_id = {item['id']: item for item in items}
    return [item for item in items if item['kind'] == kind and
            (item['parent'] is None or re.fullmatch(
                r'We will exclude subjects with any of the following:',
                by_id[item['parent']]['text'], re.I))]


def _contains(text, term):
    return re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text, re.I) is not None


def core_conflict(study, facts, patient, conflict):
    """Return the supported conflict class; quotes/scope flags are checked by caller."""
    if alternatives(study) or _SCOPED.search(study['criteria']):
        return None
    quote = conflict['trial_rule_quote']
    patient_quote = conflict['patient_fact_quote']
    if conflict['axis'] == 'clinical_history':
        terms = [(p['quote'], [p['label']]) for p in facts['present']]
        # Registry spelling/acronym aliases for the explicitly supported diagnoses.
        terms = [(q, names + (['MPNST', 'malignant peripheral schwannoma']
                  if 'malignant peripheral nerve sheath tumor' in names[0].lower() else []))
                 for q, names in terms]
        cf = re.search(r'\bcystic fibrosis\b', patient['clinical_context'], re.I)
        if cf:
            context = patient['clinical_context']
            sentence = re.split(r'[.;\n]', context[:cf.start()])[-1] + cf.group()
            if not re.search(r'\bno|\bnot|\bwithout|\bsuspected|\bpossible|\bfamily history', sentence, re.I):
                terms.append((cf.group(), ['cystic fibrosis']))
        for item in _items(study, 'exclusion'):
            if quote not in item['text']:
                continue
            # "or with ..." explicitly starts another subject, unlike a bare OR
            # list whose trailing treatment/time qualifier can govern the whole list.
            clauses = re.split(r',?\s+or (?:with|has|is accompanied by)\s+', item['text'], flags=re.I)
            for fact_quote, names in terms:
                if not _contains(patient_quote, fact_quote):
                    continue
                for clause in clauses:
                    normalized = re.sub(r'confirmed or suspected', 'confirmed', clause, flags=re.I)
                    # Separate diagnostic confirmation instructions from the
                    # exclusion itself, not treatment/time restrictions.
                    normalized = re.split(r';\s*(?:CT scan|histological confirmation)\b', normalized, flags=re.I)[0]
                    if any(name in ('MPNST', 'malignant peripheral schwannoma') for name in names):
                        normalized = re.sub(r'\(excluding low-grade glioma[^)]*\)', '', normalized, flags=re.I)
                    if any(_contains(normalized, name) for name in names) and not _QUALIFIED.search(normalized):
                        return 'explicit_excluded_condition'
    if conflict['axis'] != 'molecular':
        return None
    for item in _items(study, 'inclusion'):
        if quote not in item['text'] or re.search(r'\bor\b|\bif\b|\bunless\b|\bnot\b', item['text'], re.I):
            continue
        required = re.findall(r'\b(?:homozygous|heterozygous|hemizygous)\b', item['text'], re.I)
        genes = GC.genes_named(item['text'])
        variants = [v for v in facts['variants'] if v['gene'] in genes]
        if (len(set(genes)) == 1 and len(set(w.lower() for w in required)) == 1 and variants
                and all(v['zygosity'] in ('homozygous', 'heterozygous', 'hemizygous')
                        and v['zygosity'] != required[0].lower() for v in variants)
                and any(_contains(patient_quote, v['zygosity']) for v in variants)):
            return 'zygosity_mismatch'
    for item in _items(study, 'exclusion'):
        if quote not in item['text']:
            continue
        text = item['text']
        # Same gene, explicit non-nonsense exclusion: do not confuse a single
        # non-nonsense allele with a requirement that also permits another allele.
        genes = GC.genes_named(text)
        variants = [v for v in facts['variants'] if v['gene'] in genes]
        if (re.search(r'mutation other than nonsense', text, re.I) and variants
                and all(v['zygosity'] in ('homozygous', 'hemizygous') and
                        v['class'] in ('missense', 'inframe_deletion', 'inframe_insertion') for v in variants)
                and not re.search(r'\bif|\bunless|\bexcept', text, re.I)):
            return 'variant_class_mismatch'
        genetic = re.search(r'genetic forms of (.+?),.*?except for (.+?) gene variants', text, re.I)
        if genetic:
            exemptions = set(GC.genes_named(genetic[2]))
            if (exemptions and not exemptions.intersection(v['gene'] for v in facts['variants'])
                    and any(_contains(patient_quote, v['gene']) for v in facts['variants'])):
                # The study condition supplies disease context; the model supplies
                # the explicit genetic-form conflict. No negative gene test inferred.
                return 'genetic_exclusion_outside_exemptions'
    return None


def relevance(study, patient, facts, names):
    """A retrieval rejection is not a clinical assertion of an absent comorbidity."""
    scope = disease_scope(study, patient, facts, names)
    if scope is not None:
        return scope
    if alternatives(study) or _SCOPED.search(study['criteria']):
        return None
    conditions = study['conditions']
    if not conditions:
        return None
    inclusion = '\n'.join(x['text'] for x in _items(study, 'inclusion'))
    declared = '\n'.join(conditions)
    context = patient['clinical_context']
    genes = {v['gene'] for v in facts['variants']}
    result = None
    high = [p for p in facts['present'] if _HIGH_PLATELETS.fullmatch(p['label'])]
    low = [p for p in facts['present'] if _LOW_PLATELETS.fullmatch(p['label'])]
    low_count = re.compile(r'\b(?:platelet counts?|platelets|PLT)\s*(?:is\s*|of\s*)?[\\ ]*(?:<|≤|less than|below)', re.I)
    mandatory_low = any(
        (_LOW_PLATELETS.search(item['text']) or low_count.search(item['text']))
        and not re.search(r'\b(?:or|if|prior|previous|history|after|hemolytic|neutropenia)\b', item['text'], re.I)
        and not re.search(r'[A-Z]{2,}/', item['text'])
        for item in _items(study, 'inclusion'))
    only_low_disease = all(_LOW_PLATELETS.search(c) for c in conditions)
    if (high and not low and _LOW_PLATELETS.search(declared)
            and not _HIGH_PLATELETS.search(declared)
            and (mandatory_low or (only_low_disease and
                 (_LOW_PLATELETS.search(inclusion) or low_count.search(inclusion))))):
        result = ('opposite_phenotype', '初筛方向不符：患者已报告血小板增多，登记疾病及患者入组要求为血小板减少；不推断当前化验数值。')
    targets = set()
    for condition in conditions:
        match = re.fullmatch(r'([A-Z][A-Z0-9]+)(?:[- ]related)?[- ](?:deficiency|disease|D)', condition, re.I)
        if match and match[1].upper() in GC.known_genes():
            targets.add(match[1].upper())
        else:
            break
    else:
        if (genes and targets and not targets.intersection(genes)
                and any(re.search(r'\b' + re.escape(g) + r'[- ](?:D\b|deficiency\b|disease\b)', inclusion, re.I)
                        for g in targets)):
            result = ('different_disease_gene', '初筛疾病不符：登记疾病及入组明确限定 ' + '、'.join(sorted(targets))
                      + '，病例报告 ' + '、'.join(sorted(genes)) + '；不是未报告基因的阴性检测结论。')
    if (all(_CANCER.search(c) for c in conditions)
            and not _CANCER.search(context + '\n' + '\n'.join(names))
            and not any(_contains(declared, g) for g in genes)
            and not any(_contains(declared, n) for n in names)
            and (_CANCER.search(inclusion) or re.search(r'\bbiops\w*', inclusion, re.I))):
        result = ('unrelated_oncology', '初筛相关性未建立：登记患者队列为肿瘤/肿瘤活检，已记录疾病背景未建立该研究路径；不推断患者无肿瘤。')
    if result is None:
        return None
    return {'id': study['nct'], 'nct': study['nct'], 'reason': 'relevance',
            'detail': result[1], 'category': result[0],
            'patient_context': context, 'patient_genes': sorted(genes),
            'conditions': conditions, 'inclusion': inclusion,
            'url': T.study_url(study['nct'])}

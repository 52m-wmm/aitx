"""Explicit retrieval terms; a search hit is not evidence of patient eligibility.

Family terms are selected disease relationships, not the first ontology parent.
The mapping and its MONDO sources are documented in docs/step3b_contract.md.
Unlisted diseases receive no automatic family expansion.
"""
from __future__ import annotations

import json
import re

from aitx.evidence import patient_matching as E

OPEN_STATUSES = 'RECRUITING,NOT_YET_RECRUITING,ENROLLING_BY_INVITATION'
# Explicitly authorized family aliases; other short codes remain excluded.
FAMILY_ABBREVIATIONS = {'ALS', 'DEE'}
FAMILIES = {
    'MONDO:0009823': ('primary hyperoxaluria',),
    'MONDO:0013392': ('autosomal recessive cerebellar ataxia',),
    'MONDO:0007522': ('Ehlers-Danlos syndrome',),
    'MONDO:0020521': ('Ehlers-Danlos syndrome, arthrochalasia type',
                     'COL1A1-related Ehlers-Danlos syndrome'),
    'MONDO:0030854': ('Ehlers-Danlos/osteogenesis imperfecta syndrome',
                     'COL1A1-related Ehlers-Danlos syndrome'),
    'MONDO:0010679': ('DMD-related muscular dystrophy',),
    'MONDO:0010311': ('DMD-related muscular dystrophy',),
    'MONDO:0013509': ('GRIN2B-related complex neurodevelopmental disorder',
                     'developmental and epileptic encephalopathy', 'DEE'),
    'MONDO:0014505': ('GRIN2B-related complex neurodevelopmental disorder',
                     'developmental and epileptic encephalopathy', 'DEE'),
    'MONDO:0015004': ('inherited dystonia',),
    'MONDO:0018975': ('neurofibromatosis',),
    'MONDO:0010703': ('urea cycle disorder', 'inherited hyperammonemia'),
    'MONDO:0010478': ('congenital disorder of glycosylation type II',
                     'disorder of multiple glycosylation'),
    'MONDO:0020507': ('leukoencephalopathy with vanishing white matter',),
    'MONDO:0015519': ('leukoencephalopathy with vanishing white matter',),
    'MONDO:0015520': ('leukoencephalopathy with vanishing white matter',),
    'MONDO:0013891': ('familial amyotrophic lateral sclerosis',
                     'amyotrophic lateral sclerosis', 'ALS'),
    'MONDO:0008554': ('familial thrombocytosis',),
}


def condition_names(names, *, abbreviations=()):
    """All full names, case/whitespace deduplicated; no standalone short codes."""
    unique = {}
    for name in names:
        name = ' '.join(name.split())
        # PH1, CF, EDS VIIA and cEDS are ambiguous retrieval terms. Gene
        # symbols have their own query, so need not masquerade as disease names.
        if re.search(r'[a-z]{3}', name) or name in abbreviations:
            unique.setdefault(name.casefold(), name)
    return list(unique.values())


def branch_terms(branch, step1, step2):
    names = E.disease_names(branch, step2)
    family = list(FAMILIES.get(branch['id'], ()))
    # Reported variants can seed retrieval even when causality is unconfirmed.
    # Retrieval and target comparison do not establish causality or negative tests.
    genes = [branch['gene']] if any(v['gene'] == branch['gene'] for v in step1['variants']) else []
    return names, family, genes


def gene_query(gene):
    """Use the existing gene-token distinction for ambiguous short symbols."""
    if re.search(r'\d', gene) or len(gene) >= 5:
        return json.dumps(gene, ensure_ascii=False)
    # Matches the context requirement in trials.gene_matches. Co-occurrence
    # anywhere in a record is insufficient (e.g. OTC medicines + another gene).
    phrases = [f'{gene} {word}' for word in ('gene', 'mutation', 'variant', 'deficiency')]
    phrases += [f'{word} {gene}' for word in ('gene', 'mutation in', 'mutations in',
                                             'variant in', 'variants in')]
    return ' OR '.join(json.dumps(p, ensure_ascii=False) for p in phrases)


def queries(names, family, genes):
    disease_names = condition_names(names)
    if not disease_names:
        raise ValueError('Step 3b needs a full disease name; abbreviations alone are insufficient')
    requests = [{'query.cond': json.dumps(name, ensure_ascii=False),
                 'filter.overallStatus': OPEN_STATUSES}
                for name in condition_names(disease_names + family,
                    abbreviations=FAMILY_ABBREVIATIONS.intersection(family))]
    requests.extend({'query.term': gene_query(gene),
                     'filter.overallStatus': OPEN_STATUSES}
                    for gene in dict.fromkeys(genes))
    return requests

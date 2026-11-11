"""When a gene symbol in a text names the patient's genetic condition, and when it does not.

Shared by 3b (clinical trials) and 3c (off-label precedents). A gene symbol on its own is not evidence that a
text is about this patient's disease: many genes are also tumour biomarkers, and 3c (2026-11-05) and then 3b
(2026-11-10, blind test) both admitted cancer material on a bare symbol - colorectal-cancer papers on "AGXT
expression", and colorectal-cancer trials for "LRPPRC Positive" tumours offered to a Leigh-syndrome patient.
"""
from __future__ import annotations

import re

CANCER = re.compile(r"\b(?:cancers?|carcinomas?|tumou?rs?|neoplas\w*|malignan\w*|leuka?emi\w*|lymphomas?|"
                    r"metasta\w*|chemotherapy|oncolog\w*|sarcomas?|gliomas?|glioblastomas?|melanomas?|"
                    r"myelomas?|adenocarcinomas?|mcrc|nsclc|crc)\b", re.I)

# words right after a gene symbol that make it a tumour or assay marker rather than the patient's disease
BIOMARKER = re.compile(r"\b(?:positive|negative|expression|expressing|over-?express\w*|amplif\w*|high|low|"
                       r"status|levels?|fusions?|rearrange\w*|mutant|mutated|wild-?type|inhibitors?)\b", re.I)


def cancer_context(*texts: str) -> bool:
    return any(CANCER.search(t or "") for t in texts)


def biomarker_use(gene: str, text: str) -> bool:
    """The symbol is used as a marker ("LRPPRC Positive", "KRAS-mutant", "EGFR expression")."""
    g = rf"(?<![A-Za-z0-9]){re.escape(gene)}(?![A-Za-z0-9])"
    return re.search(rf"{g}[\s-]{{1,3}}{BIOMARKER.pattern}", text or "", re.I) is not None

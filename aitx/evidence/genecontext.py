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


# ------------------------------------------------------------------ known gene symbols (fix plan D2, 2026-11-11)

_KNOWN: set[str] | None = None


def known_genes() -> set[str]:
    """HGNC symbols that GenCC curates (the step 2 dataset already on disk), so that a criterion naming a gene can be
    compared with the patient's reported gene by code. Empty if the dataset is unavailable (then nothing is decided)."""
    global _KNOWN
    if _KNOWN is None:
        import csv
        from aitx.disease import datasets as D
        try:
            f = D.ensure("gencc")
            with open(f.path, newline="") as fh:
                _KNOWN = {(r.get("gene_symbol") or "").strip() for r in csv.DictReader(fh, delimiter="\t")} - {""}
        except (OSError, RuntimeError, KeyError, ValueError):
            _KNOWN = set()
    return _KNOWN


def genes_named(text: str, known: set[str] | None = None) -> list[str]:
    """Gene symbols written in `text` as whole words, same letter case, that are known HGNC symbols."""
    known = known_genes() if known is None else known
    toks = re.findall(r"(?<![A-Za-z0-9-])[A-Z][A-Z0-9]{1,9}(?:-[A-Z0-9]+)?(?![A-Za-z0-9])", text or "")
    return list(dict.fromkeys(t for t in toks if t in known))

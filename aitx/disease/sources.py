"""Parsers for the step-2 bulk files. Every record keeps (dataset, line) so a
claim can be traced to the exact row of the snapshot it came from.

Identifier conventions used throughout step 2:
  MONDO:0015004   OMIM:617284   Orphanet:363654 (HPO writes ORPHA:, MONDO writes Orphanet:)
"""
from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field

from aitx.disease.datasets import DATASETS, LocalFile, tsv_rows


def norm_id(curie: str) -> str:
    curie = curie.strip()
    if curie.startswith("ORPHA:"):
        return "Orphanet:" + curie[6:]
    if curie.startswith("MIM:"):
        return "OMIM:" + curie[4:]
    return curie


@dataclass(frozen=True)
class Cite:
    dataset: str
    snapshot: str
    line: int

    def to_dict(self) -> dict:
        return {"dataset": self.dataset, "url": DATASETS[self.dataset].url,
                "snapshot": self.snapshot, "line": self.line}


# ------------------------------------------------------------- gene-disease

@dataclass
class Assoc:
    """One gene-disease assertion from one source / submitter."""
    gene: str
    disease_id: str         # as submitted, normalised (MONDO:/OMIM:/Orphanet:)
    disease_label: str
    source: str             # gencc | clingen | hpo | orphanet
    submitter: str          # e.g. "Ambry Genetics", "ClinGen", "HPO", "Orphanet"
    classification: str     # Definitive ... Refuted | Supportive | unrated
    moi: str                # AD | AR | XL | XLR | XLD | SD | MT | unknown
    cite: Cite
    original_id: str = ""   # GenCC disease_original_curie (often OMIM:)
    mechanism: str = ""     # Orphanet association type, e.g. "(loss of function)"
    report_url: str = ""


_MOI = {
    "autosomal dominant": "AD", "autosomal recessive": "AR", "x-linked": "XL",
    "x-linked recessive": "XLR", "x-linked dominant": "XLD", "semidominant": "SD",
    "mitochondrial": "MT", "ad": "AD", "ar": "AR", "xl": "XL", "xlr": "XLR", "xld": "XLD",
    "sd": "SD", "mt": "MT",
}
HPO_MOI = {"HP:0000006": "AD", "HP:0000007": "AR", "HP:0001417": "XL", "HP:0001419": "XLR",
           "HP:0001423": "XLD", "HP:0032113": "SD", "HP:0001427": "MT"}


def moi_code(text: str) -> str:
    t = text.strip().lower().replace(" inheritance", "")
    return _MOI.get(t, "unknown")


def _gencc_class(title: str) -> str:
    t = title.strip()
    return {"Disputed Evidence": "Disputed", "Refuted Evidence": "Refuted",
            "No Known Disease Relationship": "Refuted"}.get(t, t)


def load_gencc(lf: LocalFile, genes: set[str]) -> list[Assoc]:
    out, header = [], None
    for line, row in tsv_rows(lf.path, "", quoted=True):
        if header is None:
            header = {k: i for i, k in enumerate(row)}
            continue
        g = row[header["gene_symbol"]]
        if g not in genes:
            continue
        sub = row[header["submitter_title"]]
        out.append(Assoc(
            g, norm_id(row[header["disease_curie"]]), row[header["disease_title"]], "gencc", sub,
            _gencc_class(row[header["classification_title"]]), moi_code(row[header["moi_title"]]),
            Cite("gencc", lf.snapshot, line), original_id=norm_id(row[header["disease_original_curie"]]),
            report_url=row[header["submitted_as_public_report_url"]]))
    return out


def load_clingen(lf: LocalFile, genes: set[str]) -> list[Assoc]:
    out, header = [], None
    with lf.path.open(newline="", encoding="utf-8") as f:
        for line, row in enumerate(csv.reader(f), start=1):
            if not row or row[0].startswith("+"):
                continue
            if row[0] == "GENE SYMBOL":
                header = {k: i for i, k in enumerate(row)}
                continue
            if header is None or row[0] not in genes:
                continue
            out.append(Assoc(
                row[0], row[header["DISEASE ID (MONDO)"]], row[header["DISEASE LABEL"]], "clingen", "ClinGen",
                row[header["CLASSIFICATION"]].replace("No Known Disease Relationship", "Refuted"),
                moi_code(row[header["MOI"]]), Cite("clingen", lf.snapshot, line),
                report_url=row[header["ONLINE REPORT"]]))
    return out


def load_hpo_genes(lf: LocalFile, genes: set[str]) -> list[Assoc]:
    out, header = [], None
    for line, row in tsv_rows(lf.path):
        if header is None:
            header = {k: i for i, k in enumerate(row)}
            continue
        if row[header["gene_symbol"]] in genes and row[header["association_type"]] == "MENDELIAN":
            out.append(Assoc(row[header["gene_symbol"]], norm_id(row[header["disease_id"]]), "", "hpo", "HPO",
                             "unrated", "unknown", Cite("hpo_genes_to_disease", lf.snapshot, line)))
    return out


_ORPHA_CAUSAL = re.compile(r"^Disease-causing germline mutation\(s\)( \((loss|gain) of function\))? in$")


def load_orphanet(lf: LocalFile, genes: set[str]) -> list[Assoc]:
    """Only 'Disease-causing germline mutation(s) [...] in' with status Assessed.

    The XML has no line numbers after parsing, so the cite line is the
    Disorder's OrphaCode (recorded in `line` as a record number).
    """
    out = []
    for dis in ET.parse(lf.path).getroot().iter("Disorder"):
        code = dis.findtext("OrphaCode")
        name = dis.findtext("Name") or ""
        for a in dis.iter("DisorderGeneAssociation"):
            sym = a.findtext("Gene/Symbol")
            kind = a.findtext("DisorderGeneAssociationType/Name") or ""
            status = a.findtext("DisorderGeneAssociationStatus/Name") or ""
            if sym not in genes or status != "Assessed":
                continue
            m = _ORPHA_CAUSAL.match(kind)
            if not m:
                continue
            out.append(Assoc(sym, f"Orphanet:{code}", name, "orphanet", "Orphanet", "Supportive", "unknown",
                             Cite("orphanet_genes", lf.snapshot, int(code)),
                             mechanism=f"{m.group(2)} of function" if m.group(2) else ""))
    return out


# --------------------------------------------------------------- ID mapping

@dataclass
class Mondo:
    to_mondo: dict[str, str] = field(default_factory=dict)          # OMIM:/Orphanet: -> MONDO
    xrefs: dict[str, dict[str, list[str]]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(list)))
    label: dict[str, str] = field(default_factory=dict)
    line: dict[str, int] = field(default_factory=dict)
    snapshot: str = ""

    def xref(self, mondo: str, prefix: str) -> list[str]:
        return list(self.xrefs.get(mondo, {}).get(prefix, []))


def load_mondo(lf: LocalFile) -> Mondo:
    m, header = Mondo(snapshot=lf.snapshot), None
    for line, row in tsv_rows(lf.path):
        if header is None:
            header = {k: i for i, k in enumerate(row)}
            continue
        if len(row) < 4 or row[header["predicate_id"]] != "skos:exactMatch":
            continue
        s, o = row[header["subject_id"]], norm_id(row[header["object_id"]])
        prefix = o.split(":")[0]
        if prefix not in ("OMIM", "Orphanet", "MEDGEN", "UMLS"):
            continue
        m.label.setdefault(s, row[header["subject_label"]])
        m.line.setdefault(s, line)
        m.xrefs[s][prefix].append(o)
        if prefix in ("OMIM", "Orphanet", "UMLS"):
            m.to_mondo.setdefault(o, s)
    return m


def load_mim2gene(lf: LocalFile) -> dict[str, tuple[str, int]]:
    """MIM number -> (entry type, line). Types: gene, phenotype, predominantly phenotypes, gene/phenotype, moved/removed."""
    out = {}
    for line, row in tsv_rows(lf.path):
        if len(row) >= 2 and row[0].isdigit():
            out[row[0]] = (row[1], line)
    return out


OMIM_PHENOTYPE_TYPES = {"phenotype", "predominantly phenotypes", "gene/phenotype"}


@dataclass
class GeneReview:
    nbk: str
    shortname: str
    title: str
    genes: list[str]
    line: int

    @property
    def url(self) -> str:
        return f"https://www.ncbi.nlm.nih.gov/books/{self.nbk}/"

    def to_dict(self, snapshot: str) -> dict:
        return {"nbk": self.nbk, "title": self.title, "url": self.url,
                "scope": "single_gene" if len(self.genes) == 1 else "multi_gene",
                "genes_in_chapter": len(self.genes),
                "cite": Cite("genereviews", snapshot, self.line).to_dict()}


def load_genereviews(lf: LocalFile) -> dict[str, list[GeneReview]]:
    chapters: dict[str, GeneReview] = {}
    for line, raw in enumerate(lf.path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = raw.split("|")
        if len(parts) != 4 or not parts[1].startswith("NBK"):
            continue
        short, nbk, gene, title = parts
        ch = chapters.setdefault(nbk, GeneReview(nbk, short, title, [], line))
        if gene and gene not in ch.genes:
            ch.genes.append(gene)
    by_gene: dict[str, list[GeneReview]] = defaultdict(list)
    for ch in chapters.values():
        for g in ch.genes:
            by_gene[g].append(ch)
    return by_gene


# ---------------------------------------------------------------- HPO annotations

@dataclass
class Annotation:
    hpo_id: str
    frequency: float | None   # 0..1, None if not given
    negated: bool
    line: int


_FREQ_TERMS = {"HP:0040280": 1.0, "HP:0040281": 0.9, "HP:0040282": 0.55, "HP:0040283": 0.17,
               "HP:0040284": 0.025, "HP:0040285": 0.0}


def parse_frequency(f: str) -> float | None:
    f = f.strip()
    if not f:
        return None
    if f in _FREQ_TERMS:
        return _FREQ_TERMS[f]
    m = re.fullmatch(r"(\d+)/(\d+)", f)
    if m and int(m.group(2)):
        return int(m.group(1)) / int(m.group(2))
    m = re.fullmatch(r"([\d.]+)%", f)
    return float(m.group(1)) / 100 if m else None


@dataclass
class HpoAnnotations:
    phenotypes: dict[str, list[Annotation]]   # disease id -> P-aspect annotations
    inheritance: dict[str, list[tuple[str, int]]]  # disease id -> [(MOI code, line)]
    names: dict[str, str]
    snapshot: str
    clinical: dict[str, list[tuple[str, int]]] = field(default_factory=dict)  # aspect C (onset, course): [(hpo id, line)]


def load_hpoa(lf: LocalFile) -> HpoAnnotations:
    ph: dict[str, list[Annotation]] = defaultdict(list)
    inh: dict[str, list[tuple[str, int]]] = defaultdict(list)
    clin: dict[str, list[tuple[str, int]]] = defaultdict(list)
    names: dict[str, str] = {}
    header = None
    for line, row in tsv_rows(lf.path):
        if header is None:
            header = {k: i for i, k in enumerate(row)}
            continue
        d = norm_id(row[header["database_id"]])
        names.setdefault(d, row[header["disease_name"]])
        aspect, hp = row[header["aspect"]], row[header["hpo_id"]]
        if aspect == "P":
            ph[d].append(Annotation(hp, parse_frequency(row[header["frequency"]]),
                                    row[header["qualifier"]] == "NOT", line))
        elif aspect == "I" and hp in HPO_MOI:
            inh[d].append((HPO_MOI[hp], line))
        elif aspect == "C" and row[header["qualifier"]] != "NOT":
            clin[d].append((hp, line))
    return HpoAnnotations(dict(ph), dict(inh), names, lf.snapshot, dict(clin))


def manifest(files: dict[str, LocalFile]) -> list[dict]:
    return [files[k].manifest_entry() for k in sorted(files)]


def dump(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)

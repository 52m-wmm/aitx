"""Fetch and parse a RefSeq transcript record (NCBI GenBank flat file).

One record gives everything step 1 needs: exon boundaries, CDS location,
the mRNA sequence and the protein translation, all for the exact transcript
version named in the challenge input.
"""
from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass, field

from aitx import http

EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


@dataclass
class Transcript:
    accession: str                     # e.g. NM_000030.3
    gene: str
    seq: str                           # mRNA sequence, uppercase, 1-based positions map to seq[i-1]
    cds_start: int                     # mRNA position of the A of ATG (1-based)
    cds_end: int                       # mRNA position of the last base of the stop codon
    exons: list[tuple[int, int]]       # mRNA coordinates, 1-based inclusive, in order
    protein: str                       # translation without the stop "*"
    protein_id: str = ""
    source_url: str = ""
    accessed_at: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def protein_length(self) -> int:
        return len(self.protein)

    @property
    def coding_length(self) -> int:
        """Coding nucleotides excluding the stop codon."""
        return 3 * self.protein_length

    def c_to_mrna(self, c: int, utr3: bool = False) -> int:
        """Map an exonic c. position to an mRNA position."""
        if utr3:
            return self.cds_end + c
        if c >= 1:
            return self.cds_start + c - 1
        if c < 0:
            return self.cds_start + c          # c.-1 is the base just before the ATG
        raise ValueError("c.0 does not exist")

    def exon_index(self, mrna_pos: int) -> int | None:
        """1-based exon number containing an mRNA position."""
        for i, (s, e) in enumerate(self.exons, start=1):
            if s <= mrna_pos <= e:
                return i
        return None

    def codon(self, aa_pos: int) -> str:
        p = self.c_to_mrna(3 * (aa_pos - 1) + 1)
        return self.seq[p - 1:p + 2]


def efetch_url(accession: str) -> str:
    params = {"db": "nuccore", "id": accession, "rettype": "gb", "retmode": "text", "tool": "aitx"}
    key = os.environ.get("NCBI_API_KEY")
    if key:
        params["api_key"] = key
    return EFETCH + "?" + urllib.parse.urlencode(params)


def public_url(accession: str) -> str:
    """Human-openable citation URL for the record."""
    return f"https://www.ncbi.nlm.nih.gov/nuccore/{accession}"


def fetch_transcript(accession: str) -> Transcript:
    f = http.get(efetch_url(accession))
    t = parse_genbank(f.text)
    if t.accession != accession:
        raise ValueError(f"requested {accession} but NCBI returned {t.accession}")
    t.source_url = public_url(accession)
    t.accessed_at = f.accessed_at
    return t


# ------------------------------------------------------------------ parsing

_RANGE = re.compile(r"^<?(\d+)\.\.>?(\d+)$")


def _parse_range(loc: str) -> tuple[int, int]:
    m = _RANGE.match(loc.strip())
    if not m:
        raise ValueError(f"unsupported feature location: {loc!r}")
    return int(m.group(1)), int(m.group(2))


def _features(lines: list[str]) -> list[dict]:
    """Return [{'key':..., 'location':..., 'quals': {name: value}}] from FEATURES lines."""
    feats: list[dict] = []
    cur: dict | None = None
    qual_name: str | None = None
    for line in lines:
        if len(line) > 5 and line[5] != " " and line[:5] == "     ":
            key, _, loc = line[5:].partition(" ")
            cur = {"key": key.strip(), "location": loc.strip(), "quals": {}}
            feats.append(cur)
            qual_name = None
        elif cur is not None and line.startswith(" " * 21):
            body = line[21:].rstrip()
            if body.startswith("/"):
                name, eq, value = body[1:].partition("=")
                qual_name = name
                cur["quals"][name] = value if eq else True
            elif qual_name is None:
                cur["location"] += body.strip()          # wrapped location
            else:
                prev = cur["quals"][qual_name]
                cur["quals"][qual_name] = (prev if isinstance(prev, str) else "") + body
    for f in feats:
        for k, v in list(f["quals"].items()):
            if isinstance(v, str) and v.startswith('"') and v.endswith('"'):
                f["quals"][k] = v[1:-1]
    return feats


def parse_genbank(text: str) -> Transcript:
    lines = text.splitlines()
    version = ""
    feat_lines: list[str] = []
    seq_parts: list[str] = []
    section = None
    for line in lines:
        if line.startswith("VERSION"):
            version = line.split()[1]
        if line.startswith("FEATURES"):
            section = "features"
            continue
        if line.startswith("ORIGIN"):
            section = "origin"
            continue
        if line.startswith("//"):
            break
        if section == "features":
            if line and not line.startswith(" "):
                section = None
                continue
            feat_lines.append(line)
        elif section == "origin":
            seq_parts.append("".join(ch for ch in line if ch.isalpha()))
    if not version:
        raise ValueError("GenBank record has no VERSION line")
    seq = "".join(seq_parts).upper()

    feats = _features(feat_lines)
    exons = sorted(_parse_range(f["location"]) for f in feats if f["key"] == "exon")
    cds = [f for f in feats if f["key"] == "CDS"]
    if not cds:
        raise ValueError(f"{version}: no CDS feature (not a protein-coding transcript?)")
    if len(cds) > 1:
        raise ValueError(f"{version}: more than one CDS feature")
    cds_start, cds_end = _parse_range(cds[0]["location"])
    quals = cds[0]["quals"]
    protein = str(quals.get("translation", "")).replace(" ", "")
    gene = str(quals.get("gene") or next((f["quals"].get("gene") for f in feats if f["key"] == "gene"), ""))

    notes = []
    if not exons:
        exons = [(1, len(seq))]
        notes.append("record has no exon features; treated as a single exon")
    if not protein:
        raise ValueError(f"{version}: CDS has no /translation")
    if (cds_end - cds_start + 1) != 3 * (len(protein) + 1):
        notes.append("CDS length does not equal 3 x (protein length + stop); check record")

    return Transcript(
        accession=version, gene=gene, seq=seq, cds_start=cds_start, cds_end=cds_end,
        exons=exons, protein=protein, protein_id=str(quals.get("protein_id", "")), notes=notes,
    )

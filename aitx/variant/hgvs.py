"""Minimal HGVS parsing for simple coding variants (SNVs and small indels).

Covers what the challenge allows: single-nucleotide and insertion/deletion
variants written in HGVS cDNA (c.) and protein (p.) notation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

AA3_TO_1 = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Gln": "Q",
    "Glu": "E", "Gly": "G", "His": "H", "Ile": "I", "Leu": "L", "Lys": "K",
    "Met": "M", "Phe": "F", "Pro": "P", "Ser": "S", "Thr": "T", "Trp": "W",
    "Tyr": "Y", "Val": "V", "Sec": "U", "Pyl": "O", "Ter": "*", "Xaa": "X",
}
AA1_TO_3 = {v: k for k, v in AA3_TO_1.items()}


class HgvsError(ValueError):
    pass


# ---------------------------------------------------------------- cDNA (c.)

@dataclass
class CPos:
    """A position in c. coordinates.

    base: the number before any intronic offset (negative = 5'UTR).
    utr3: True for c.*N positions (3'UTR, base counts from the stop codon).
    offset: intronic offset (c.123+1 -> offset +1); 0 for exonic positions.
    """
    base: int
    utr3: bool = False
    offset: int = 0

    @property
    def intronic(self) -> bool:
        return self.offset != 0


@dataclass
class CVariant:
    raw: str
    start: CPos
    end: CPos
    kind: str            # sub | del | dup | ins | delins
    ref: str = ""        # reference bases, when stated
    alt: str = ""        # alternate / inserted bases, when stated

    @property
    def length(self) -> int | None:
        """Length of the affected reference span (exonic positions only)."""
        if self.start.intronic or self.end.intronic or self.start.utr3 != self.end.utr3:
            return None
        return self.end.base - self.start.base + 1

    @property
    def net_change(self) -> int | None:
        """Net change in sequence length (+1 for a 1-nt dup, -3 for a 3-nt del)."""
        n = self.length
        if self.kind == "sub":
            return 0
        if self.kind == "dup":
            return n
        if self.kind == "del":
            return None if n is None else -n
        if self.kind == "ins":
            return len(self.alt) if self.alt else None
        if self.kind == "delins":
            return None if n is None or not self.alt else len(self.alt) - n
        return None


_POS = r"(\*?-?\d+(?:[+-]\d+)?)"
_C_RE = re.compile(
    rf"^c\.{_POS}(?:_{_POS})?"
    r"(?:(?P<sub>[ACGT])>(?P<subalt>[ACGT])"
    r"|delins(?P<delinsalt>[ACGT]+)"
    r"|del(?P<delref>[ACGT]*)"
    r"|dup(?P<dupref>[ACGT]*)"
    r"|ins(?P<insalt>[ACGT]+))$"
)


def _parse_cpos(s: str) -> CPos:
    utr3 = s.startswith("*")
    if utr3:
        s = s[1:]
    m = re.match(r"^(-?\d+)([+-]\d+)?$", s)
    if not m:
        raise HgvsError(f"bad c. position: {s!r}")
    return CPos(base=int(m.group(1)), utr3=utr3, offset=int(m.group(2) or 0))


def parse_cdna(raw: str) -> CVariant:
    s = raw.strip().replace(" ", "")
    m = _C_RE.match(s)
    if not m:
        raise HgvsError(f"unsupported c. notation: {raw!r}")
    start = _parse_cpos(m.group(1))
    end = _parse_cpos(m.group(2)) if m.group(2) else start
    if m.group("sub"):
        return CVariant(raw, start, end, "sub", ref=m.group("sub"), alt=m.group("subalt"))
    if m.group("delinsalt"):
        return CVariant(raw, start, end, "delins", alt=m.group("delinsalt"))
    if m.group("delref") is not None and "del" in s and "delins" not in s:
        return CVariant(raw, start, end, "del", ref=m.group("delref") or "")
    if m.group("dupref") is not None and "dup" in s:
        return CVariant(raw, start, end, "dup", ref=m.group("dupref") or "")
    if m.group("insalt"):
        return CVariant(raw, start, end, "ins", alt=m.group("insalt"))
    raise HgvsError(f"unsupported c. notation: {raw!r}")


# ------------------------------------------------------------- protein (p.)

@dataclass
class PVariant:
    raw: str
    predicted: bool                 # written in parentheses -> predicted
    kind: str                       # missense | nonsense | frameshift | start_lost | stop_lost |
                                    # synonymous | inframe_deletion | inframe_insertion |
                                    # inframe_duplication | inframe_delins | unknown | no_protein
    ref_aa: str = ""                # 3-letter code of the first affected residue
    pos: int | None = None          # first affected residue
    end_ref_aa: str = ""
    end_pos: int | None = None
    alt_aa: str = ""                # 3-letter code (missense/nonsense/frameshift first new residue)
    fs_ter: int | None = None       # frameshift: Ter position counted from pos (pos itself = 1)
    extra: dict = field(default_factory=dict)


_AA = r"(?:[A-Z][a-z]{2})"
_P_PATTERNS = [
    ("frameshift", re.compile(rf"^(?P<ref>{_AA})(?P<pos>\d+)(?P<alt>{_AA})?fs(?:Ter|\*)(?P<ter>\d+|\?)?$")),
    ("range_del", re.compile(rf"^(?P<ref>{_AA})(?P<pos>\d+)_(?P<eref>{_AA})(?P<epos>\d+)del$")),
    ("range_dup", re.compile(rf"^(?P<ref>{_AA})(?P<pos>\d+)_(?P<eref>{_AA})(?P<epos>\d+)dup$")),
    ("range_ins", re.compile(rf"^(?P<ref>{_AA})(?P<pos>\d+)_(?P<eref>{_AA})(?P<epos>\d+)ins(?P<ins>(?:{_AA})+)$")),
    ("delins", re.compile(rf"^(?P<ref>{_AA})(?P<pos>\d+)(?:_(?P<eref>{_AA})(?P<epos>\d+))?delins(?P<ins>(?:{_AA})+)$")),
    ("single_del", re.compile(rf"^(?P<ref>{_AA})(?P<pos>\d+)del$")),
    ("single_dup", re.compile(rf"^(?P<ref>{_AA})(?P<pos>\d+)dup$")),
    ("sub", re.compile(rf"^(?P<ref>{_AA})(?P<pos>\d+)(?P<alt>{_AA}|\*|=)$")),
]


def parse_protein(raw: str) -> PVariant:
    s = raw.strip().replace(" ", "")
    if not s.startswith("p."):
        raise HgvsError(f"protein notation must start with 'p.': {raw!r}")
    body = s[2:]
    predicted = body.startswith("(") and body.endswith(")")
    if predicted:
        body = body[1:-1]
    if body in ("?", ""):
        return PVariant(raw, predicted, "unknown")
    if body == "0":
        return PVariant(raw, predicted, "no_protein")

    for name, rx in _P_PATTERNS:
        m = rx.match(body)
        if not m:
            continue
        g = m.groupdict()
        ref, pos = g["ref"], int(g["pos"])
        for aa in [ref, g.get("eref"), g.get("alt")]:
            if aa and aa not in ("*", "=") and aa not in AA3_TO_1:
                raise HgvsError(f"unknown amino acid {aa!r} in {raw!r}")
        epos = int(g["epos"]) if g.get("epos") else None
        if name == "frameshift":
            ter = g.get("ter")
            return PVariant(raw, predicted, "frameshift", ref, pos, alt_aa=g.get("alt") or "",
                            fs_ter=int(ter) if ter and ter != "?" else None)
        if name in ("range_del", "single_del"):
            return PVariant(raw, predicted, "inframe_deletion", ref, pos,
                            g.get("eref") or ref, epos or pos)
        if name in ("range_dup", "single_dup"):
            return PVariant(raw, predicted, "inframe_duplication", ref, pos,
                            g.get("eref") or ref, epos or pos)
        if name == "range_ins":
            return PVariant(raw, predicted, "inframe_insertion", ref, pos, g["eref"], epos,
                            extra={"inserted": g["ins"]})
        if name == "delins":
            return PVariant(raw, predicted, "inframe_delins", ref, pos,
                            g.get("eref") or ref, epos or pos, extra={"inserted": g["ins"]})
        # substitution
        alt = g["alt"]
        if alt == "=":
            kind = "synonymous"
        elif alt in ("Ter", "*"):
            kind = "nonsense"
            alt = "Ter"
        elif pos == 1 and ref == "Met":
            kind = "start_lost"
        elif ref == "Ter":
            kind = "stop_lost"
        else:
            kind = "missense"
        return PVariant(raw, predicted, kind, ref, pos, alt_aa=alt)

    raise HgvsError(f"unsupported p. notation: {raw!r}")

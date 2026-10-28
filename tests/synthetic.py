"""A small synthetic transcript written in NCBI GenBank layout, for offline tests.

Layout (mRNA coordinates, 1-based):
    5'UTR 1..10 | CDS 11..613 (200 aa + stop TAA) | 3'UTR 614..663
    exon1 1..100, exon2 101..300, exon3 301..450, exon4 451..663 (last)
"""
from aitx.variant.hgvs import AA1_TO_3

CODONS = [("GCT", "A"), ("CGT", "R"), ("AAT", "N"), ("GAT", "D"), ("CAG", "Q"),
          ("GGC", "G"), ("CTG", "L"), ("AAA", "K"), ("TTC", "F"), ("ATT", "I")]
UTR5 = "GCCGCCACCA"
UTR3 = "AC" * 25
EXONS = [(1, 100), (101, 300), (301, 450), (451, 663)]
PROTEIN_LEN = 200


def build():
    cds, prot = ["ATG"], ["M"]
    for i in range(1, PROTEIN_LEN):
        c, a = CODONS[i % len(CODONS)]
        cds.append(c)
        prot.append(a)
    cds.append("TAA")
    seq = UTR5 + "".join(cds) + UTR3
    return seq, "".join(prot)


SEQ, PROTEIN = build()
CDS_START, CDS_END = 11, 10 + 3 * (PROTEIN_LEN + 1)


def aa3(pos: int) -> str:
    return AA1_TO_3[PROTEIN[pos - 1]]


def cbase(c: int) -> str:
    return SEQ[CDS_START + c - 2]


def genbank_text() -> str:
    n = len(SEQ)
    lines = [
        f"LOCUS       NM_TEST01                {n} bp    mRNA    linear   PRI 01-JAN-2026",
        "DEFINITION  Synthetic test transcript.",
        "ACCESSION   NM_TEST01",
        "VERSION     NM_TEST01.1",
        "FEATURES             Location/Qualifiers",
        f"     source          1..{n}",
        '                     /organism="Homo sapiens"',
        f"     gene            1..{n}",
        '                     /gene="TEST1"',
    ]
    for s, e in EXONS:
        lines += [f"     exon            {s}..{e}", '                     /gene="TEST1"']
    lines += [f"     CDS             {CDS_START}..{CDS_END}", '                     /gene="TEST1"',
              '                     /protein_id="NP_TEST01.1"']
    tr = '/translation="' + PROTEIN + '"'
    first = True
    while tr:
        lines.append(" " * 21 + tr[:58])
        tr = tr[58:]
        first = False
    lines.append("ORIGIN      ")
    low = SEQ.lower()
    for i in range(0, n, 60):
        chunk = low[i:i + 60]
        groups = " ".join(chunk[j:j + 10] for j in range(0, len(chunk), 10))
        lines.append(f"{i + 1:>9} {groups}")
    lines.append("//")
    return "\n".join(lines) + "\n"

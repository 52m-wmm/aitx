import pytest

from aitx.variant.hgvs import HgvsError, parse_cdna, parse_protein

# Every variant string used in the official examples and the four challenge cases.
PROTEIN_CASES = [
    ("p.(Gln367ProfsTer48)", "frameshift", "Gln", 367, 48),
    ("p.(Lys12GlnfsTer156)", "frameshift", "Lys", 12, 156),
    ("p.(Ile2694SerfsTer44)", "frameshift", "Ile", 2694, 44),
    ("p.Asp34Asn", "missense", "Asp", 34, None),
    ("p.Leu39His", "missense", "Leu", 39, None),
    ("p.Ile368Thr", "missense", "Ile", 368, None),
    ("p.(Gly170Arg)", "missense", "Gly", 170, None),
    ("p.Phe508del", "inframe_deletion", "Phe", 508, None),
    ("p.(Thr2516_Ala3096del)", "inframe_deletion", "Thr", 2516, None),
    ("p.(Met97Ter)", "nonsense", "Met", 97, None),
    ("p.Gln919Ter", "nonsense", "Gln", 919, None),
    ("p.Met1Ile", "start_lost", "Met", 1, None),
    ("p.Arg129His", "missense", "Arg", 129, None),
]


@pytest.mark.parametrize("raw,kind,ref,pos,ter", PROTEIN_CASES)
def test_protein(raw, kind, ref, pos, ter):
    p = parse_protein(raw)
    assert (p.kind, p.ref_aa, p.pos, p.fs_ter) == (kind, ref, pos, ter)
    assert p.predicted == raw.startswith("p.(")


def test_protein_range_end():
    p = parse_protein("p.(Thr2516_Ala3096del)")
    assert (p.end_ref_aa, p.end_pos) == ("Ala", 3096)


CDNA_CASES = [
    ("c.1099dup", "dup", 1099, 1099, +1),
    ("c.33dup", "dup", 33, 33, +1),
    ("c.100G>A", "sub", 100, 100, 0),
    ("c.1521_1523del", "del", 1521, 1523, -3),
    ("c.7544_9286del", "del", 7544, 9286, -1743),
    ("c.289del", "del", 289, 289, -1),
    ("c.8079delC", "del", 8079, 8079, -1),
    ("c.3G>A", "sub", 3, 3, 0),
]


@pytest.mark.parametrize("raw,kind,s,e,net", CDNA_CASES)
def test_cdna(raw, kind, s, e, net):
    c = parse_cdna(raw)
    assert (c.kind, c.start.base, c.end.base, c.net_change) == (kind, s, e, net)


def test_cdna_stated_ref():
    assert parse_cdna("c.8079delC").ref == "C"
    assert parse_cdna("c.100G>A").alt == "A"


def test_cdna_intronic_and_utr():
    c = parse_cdna("c.123+1G>A")
    assert c.start.intronic and c.start.offset == 1
    assert parse_cdna("c.-5C>T").start.base == -5
    assert parse_cdna("c.*10del").start.utr3


@pytest.mark.parametrize("bad", ["c.12G", "g.12G>A", "c.12_G>A", "c.1delinsZ"])
def test_cdna_rejects(bad):
    with pytest.raises(HgvsError):
        parse_cdna(bad)


@pytest.mark.parametrize("bad", ["Gln367Pro", "p.Xyz12Ala", "p.(Gln367Pro"])
def test_protein_rejects(bad):
    with pytest.raises(HgvsError):
        parse_protein(bad)

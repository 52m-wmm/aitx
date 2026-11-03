"""Self-check 6: independent re-translation of the c. change vs the stated p. notation.

Each kind is tested forward (correct notation -> pass) and in reverse (a deliberately
wrong notation -> fail), so the check is shown to catch errors, not just to agree.
"""
import pytest

from aitx.variant.hgvs import parse_cdna
from aitx.variant.profile import build_profile
from aitx.variant.transcript import parse_genbank
from aitx.variant.translate import CODON_TABLE, WINDOW_CODONS, retranslate, translate
from tests import synthetic as S


@pytest.fixture(scope="module")
def tx():
    return parse_genbank(S.genbank_text())


def check(tx, cdna, prot):
    p = build_profile({"gene": "TEST1", "transcript": "NM_TEST01.1", "variant_cdna": cdna,
                       "variant_protein": prot, "zygosity": "heterozygous"}, tx)
    c = next(c for c in p.checks if c.name == "independent_translation")
    return c.status, p.retranslation


def test_codon_table_and_reference_translation(tx):
    assert len(CODON_TABLE) == 64 and CODON_TABLE["ATG"] == "M" and CODON_TABLE["TGA"] == "*"
    prot, stop = translate(tx.seq, tx.cds_start)
    assert prot == S.PROTEIN and stop == S.CDS_END - 2
    assert retranslate(tx, parse_cdna("c.33T>C"))["reference_translation_matches_record"]


@pytest.mark.parametrize("cdna,good,bad", [
    # frameshift: c.300dup -> Ala101Cys, stop 3 residues later (residue 103)
    ("c.300dup", "p.(Ala101CysfsTer3)", "p.(Ala101CysfsTer4)"),
    # nonsense: codon 18 AAA (Lys) -> TAA
    ("c.52A>T", "p.Lys18Ter", "p.Lys19Ter"),
    # missense: codon 50 ATT (Ile) -> AGT (Ser)
    ("c.149T>G", "p.Ile50Ser", "p.Ile50Pro"),
    # in-frame deletion of codon 11 (Ala)
    ("c.31_33del", "p.Ala11del", "p.Arg12del"),
    # in-frame duplication of codon 11
    ("c.31_33dup", "p.Ala11dup", "p.Arg12dup"),
    # insertion of GGG (Gly) between codons 11 and 12
    ("c.33_34insGGG", "p.Ala11_Arg12insGly", "p.Ala11_Arg12insAla"),
    # synonymous: GCT -> GCC
    ("c.33T>C", "p.Ala11=", "p.Ala11Gly"),
])
def test_forward_and_reverse(tx, cdna, good, bad):
    status, rt = check(tx, cdna, good)
    assert status == "pass", rt.get("comparison")
    assert rt["comparison"]["agree"] is True
    status, rt = check(tx, cdna, bad)
    assert status == "fail", rt.get("comparison")


def test_frameshift_records_both_positions(tx):
    _, rt = check(tx, "c.300dup", "p.(Ala101CysfsTer3)")
    assert rt["stop_position"] == 103 and rt["variant_protein_length"] == 102
    assert rt["first_changed_aa"] == {"position": 101, "reference": "Ala", "variant": "Cys"}
    assert rt["comparison"]["stated"].startswith("Ter3") and rt["comparison"]["computed"].startswith("Ter3")
    assert not rt["same_frame_after_change"]
    assert rt["variant_protein"] == S.PROTEIN[:100] + "CS"


def test_frameshift_wrong_first_residue_is_warn(tx):
    status, _ = check(tx, "c.300dup", "p.(Ala101GlyfsTer3)")      # stop right, new residue wrong
    assert status == "warn"


def test_frameshift_without_stop(tx):
    # deleting a base of the stop codon's neighbour reads into the 3'UTR (ACAC...) with no stop
    status, rt = check(tx, "c.595del", "p.(Ile199SerfsTer?)")
    assert rt["stop_found"] is False and rt["stop_position"] is None
    assert status in ("pass", "warn")
    status, _ = check(tx, "c.595del", "p.(Ile199SerfsTer10)")
    assert status == "fail"


def test_start_lost(tx):
    status, rt = check(tx, "c.3G>A", "p.Met1Ile")
    assert status == "pass"
    assert rt["start_codon"] == {"reference": "ATG", "variant": "ATA"}
    assert rt["first_changed_aa"]["variant"] == "Ile"
    status, _ = check(tx, "c.3G>A", "p.Met1Val")
    assert status == "warn"
    status, _ = check(tx, "c.3G>A", "p.Ala2Val")                  # notation is not start-lost at all
    assert status == "fail"


def test_codon_window(tx):
    rt = retranslate(tx, parse_cdna("c.149T>G"))
    w = rt["codon_window"]
    assert len(w["reference"]) == len(w["variant"]) == WINDOW_CODONS
    assert w["changed_codon"] == 50
    ref = {c["n"]: c for c in w["reference"]}
    var = {c["n"]: c for c in w["variant"]}
    assert ref[50]["codon"] == "ATT" and var[50]["codon"] == "AGT" and var[50]["aa"] == "Ser"
    assert all(ref[k]["codon"] == var[k]["codon"] and not var[k]["changed"] for k in ref if k != 50)
    assert var[50]["changed"]


def test_intronic_not_computable(tx):
    status, rt = check(tx, "c.90+1G>A", "p.?")
    assert status == "warn" and rt["status"] == "not_computable"


def test_codon_window_marks_changed_codons(tx):
    w = retranslate(tx, parse_cdna("c.300dup"))["codon_window"]     # frameshift at codon 101
    changed = [c["n"] for c in w["variant"] if c["changed"]]
    assert changed and changed[0] == 101 and all(not c["changed"] for c in w["variant"] if c["n"] < 101)

import pytest

from aitx.variant.profile import build_profile, patient_summary
from aitx.variant.transcript import parse_genbank
from tests import synthetic as S


@pytest.fixture(scope="module")
def tx():
    t = parse_genbank(S.genbank_text())
    t.source_url = "https://www.ncbi.nlm.nih.gov/nuccore/NM_TEST01.1"
    return t


def v(cdna, prot, zyg="heterozygous"):
    return {"gene": "TEST1", "transcript": "NM_TEST01.1", "variant_cdna": cdna,
            "variant_protein": prot, "zygosity": zyg}


def statuses(p):
    return {c.name: c.status for c in p.checks}


# ------------------------------------------------------------ parsing

def test_genbank_parse(tx):
    assert tx.accession == "NM_TEST01.1"
    assert tx.gene == "TEST1"
    assert (tx.cds_start, tx.cds_end) == (S.CDS_START, S.CDS_END)
    assert tx.exons == S.EXONS
    assert tx.protein == S.PROTEIN and tx.protein_length == 200
    assert tx.seq == S.SEQ
    assert tx.notes == []


def test_c_to_mrna(tx):
    assert tx.c_to_mrna(1) == 11            # A of ATG
    assert tx.c_to_mrna(-1) == 10           # last 5'UTR base
    assert tx.c_to_mrna(1, utr3=True) == S.CDS_END + 1
    assert tx.codon(1) == "ATG"


# ------------------------------------------------------- NMD / classes

def test_frameshift_mid_transcript_triggers_nmd(tx):
    # dup at c.300 (codon 100); first changed residue 101 (Ala -> Cys); Ter3 -> PTC at 103
    p = build_profile(v("c.300dup", f"p.({S.aa3(101)}101CysfsTer3)", "homozygous"), tx)
    assert p.ok, p.checks
    assert p.variant_class == "frameshift"
    assert p.ptc_aa_position == 103 and p.truncated_protein_length == 102
    assert p.fraction_of_protein_retained == 0.5          # 100 normal residues of 200
    assert p.nmd["prediction"] == "likely_triggers"
    assert p.nmd["ptc_exon"] == 3
    assert p.mechanism_hypothesis["hypothesis"] == "loss_of_function"
    assert p.allelic_state["copies_affected"] == 2


def test_nonsense_in_last_exon_escapes(tx):
    p = build_profile(v(f"c.478{S.cbase(478)}>T", f"p.{S.aa3(160)}160Ter"), tx)
    assert p.nmd["prediction"] == "likely_escapes"
    assert "last exon" in p.nmd["reasons"][0]
    assert p.mechanism_hypothesis["hypothesis"] == "loss_of_function_or_altered_function"


def test_nonsense_near_last_junction_escapes(tx):
    # codon 143 -> c.427 -> mRNA 437; last exon starts at 451 -> 14 nt upstream
    p = build_profile(v(f"c.427{S.cbase(427)}>T", f"p.{S.aa3(143)}143Ter"), tx)
    assert p.nmd["nt_upstream_of_last_junction"] == 14
    assert p.nmd["prediction"] == "likely_escapes"


def test_frameshift_reading_past_normal_stop_escapes(tx):
    # like KMT2B c.8079delC p.(Ile2694SerfsTer44): the new stop lies past the normal one
    # Ter10 from 199 -> stop codon 208 -> c.623 (after the -1 shift) -> mRNA 633, last exon
    p = build_profile(v("c.595del", f"p.({S.aa3(199)}199SerfsTer10)"), tx)
    assert p.variant_class == "frameshift"
    assert p.ptc_aa_position == 208
    assert p.truncated_protein_length is None
    assert p.nmd["prediction"] == "likely_escapes"
    assert p.nmd["protein_extended_by_aa"] == 7
    assert "last exon" in p.nmd["reasons"][0] and "past the normal stop" in p.nmd["reasons"][0]
    assert "longer than normal" in p.mechanism_hypothesis["basis"]
    assert "shortened" not in p.mechanism_hypothesis["basis"]


def test_frameshift_stop_beyond_record_uncertain(tx):
    # Ter50 from 199 -> stop codon 248 -> mRNA ~753, past the 663-nt record
    p = build_profile(v("c.595del", f"p.({S.aa3(199)}199SerfsTer50)"), tx)
    assert p.nmd["prediction"] == "uncertain"
    assert p.nmd["ptc_exon"] is None


def test_start_proximal_ptc_uncertain(tx):
    p = build_profile(v(f"c.31{S.cbase(31)}>T", f"p.{S.aa3(11)}11Ter"), tx)
    assert p.nmd["prediction"] == "uncertain"


def test_missense(tx):
    alt = "G" if S.cbase(149) != "G" else "C"
    p = build_profile(v(f"c.149{S.cbase(149)}>{alt}", f"p.{S.aa3(50)}50Ser"), tx)     # ATT -> AGT
    assert p.ok, p.checks
    assert p.variant_class == "missense"
    assert p.nmd["prediction"] == "not_applicable"
    assert p.mechanism_hypothesis["hypothesis"] == "unknown"
    assert p.exon["number"] == 2          # c.149 -> mRNA 159, exon 2 (101..300)


def test_inframe_deletion(tx):
    p = build_profile(v("c.31_33del", f"p.{S.aa3(11)}11del", "homozygous"), tx)
    assert p.ok
    assert p.variant_class == "inframe_deletion"
    assert statuses(p)["cdna_protein_consistency"] == "pass"


def test_exon_coding_fraction(tx):
    alt = "G" if S.cbase(200) != "G" else "C"
    p = build_profile(v(f"c.200{S.cbase(200)}>{alt}", f"p.{S.aa3(67)}67Pro"), tx)
    assert p.exon["number"] == 2
    assert p.exon["coding_nt"] == 200
    assert p.exon["coding_fraction_of_cds"] == round(200 / 600, 4)
    assert p.exon["c_range"] == [91, 290]


# ---------------------------------------------------- checks that must fail

def test_wrong_reference_base_fails(tx):
    wrong = "A" if S.cbase(149) != "A" else "C"
    p = build_profile(v(f"c.149{wrong}>T", f"p.{S.aa3(50)}50Pro"), tx)
    assert statuses(p)["cdna_reference"] == "fail"
    assert not p.ok


def test_wrong_protein_reference_fails(tx):
    wrong = "Trp"                      # synthetic protein contains no Trp
    alt = "G" if S.cbase(149) != "G" else "C"
    p = build_profile(v(f"c.149{S.cbase(149)}>{alt}", f"p.{wrong}50Pro"), tx)
    assert statuses(p)["protein_reference_start"] == "fail"


def test_codon_mismatch_fails(tx):
    alt = "G" if S.cbase(149) != "G" else "C"
    p = build_profile(v(f"c.149{S.cbase(149)}>{alt}", f"p.{S.aa3(60)}60Pro"), tx)
    assert statuses(p)["codon_math"] == "fail"


def test_frameshift_claim_with_inframe_cdna_fails(tx):
    p = build_profile(v("c.31_33del", f"p.({S.aa3(11)}11AlafsTer5)"), tx)
    assert statuses(p)["cdna_protein_consistency"] == "fail"


def test_transcript_version_mismatch_fails(tx):
    var = v("c.31_33del", f"p.{S.aa3(11)}11del")
    var["transcript"] = "NM_TEST01.2"
    assert statuses(build_profile(var, tx))["transcript_version"] == "fail"


def test_patient_summary_biallelic(tx):
    a = build_profile(v("c.300dup", f"p.({S.aa3(101)}101CysfsTer3)"), tx)
    b = build_profile(v("c.31_33del", f"p.{S.aa3(11)}11del"), tx)
    s = patient_summary([a, b])
    assert s["genes"]["TEST1"]["allelic_model"].startswith("biallelic")
    assert s["all_checks_pass"]

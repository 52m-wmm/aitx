"""Step 3d bespoke therapies (docs/step3d_contract.md): deterministic judgements, offline.

Written before the module (2026-11-05 instruction). Every expectation here is a rule from the contract, which
quotes the N1C VARIANT guidelines (PMID 40139194) and its Data S1.
"""
import pytest

from aitx.evidence import bespoke as BS

# --- a small made-up transcript: 4 exons, CDS from the middle of exon 1 to the middle of exon 4.
# exon coding lengths: e1 30, e2 60, e3 61, e4 30 -> e2 in frame (phase 0-0), e3 out of frame.
SEQ = "".join(["T" * 10,                      # 5' UTR
               "ATG" + "GCT" * 9,             # exon 1 coding: 30 nt
               "GCT" * 20,                    # exon 2: 60 nt
               "GCT" * 20 + "A",              # exon 3: 61 nt
               "GC" + "GCT" * 8 + "TAA",      # exon 4: 29 nt + stop
               "T" * 10])                     # 3' UTR
EXONS = [(1, 40), (41, 100), (101, 161), (162, 193), (194, 203)]


class Tr:
    """Only what the judgements use (same attribute names as aitx.variant.transcript.Transcript)."""
    def __init__(self, seq=SEQ, exons=None, cds=(11, 190), protein_len=60):
        self.seq, self.exons = seq, exons if exons is not None else EXONS
        self.cds_start, self.cds_end = cds
        self.protein = "M" * protein_len

    @property
    def protein_length(self):
        return len(self.protein)


def test_coding_exons_ignore_utr_only_exons():
    """N1C: the first and last exons of a transcript are not necessarily the first and last CODING exons."""
    got = BS.coding_exons(Tr())
    assert [e["number"] for e in got] == [1, 2, 3, 4]        # exon 5 is 3' UTR only
    assert [e["coding_nt"] for e in got] == [30, 60, 61, 29]   # exon 4 is cut short by the stop codon
    assert [e["in_frame"] for e in got] == [True, True, False, False]
    assert [e["phase_in"] for e in got] == [0, 0, 0, 1]      # exon 4 starts mid-codon


def test_single_coding_exon_gene_is_not_eligible():
    tr = Tr(exons=[(1, 203)], cds=(11, 190))
    r = BS.exon_skipping(tr, 1, mechanism="loss_of_function")
    assert r["classification"] == "not_eligible" and "one coding exon" in r["failed_criterion"]


@pytest.mark.parametrize("n", [1, 4])
def test_first_and_last_coding_exon_are_not_eligible(n):
    r = BS.exon_skipping(Tr(), n, mechanism="loss_of_function")
    assert r["classification"] == "not_eligible"
    assert "first" in r["failed_criterion"] or "last" in r["failed_criterion"]


def test_out_of_frame_exon_is_not_eligible_but_names_the_exception():
    r = BS.exon_skipping(Tr(), 3, mechanism="loss_of_function")
    assert r["classification"] == "not_eligible" and "not a multiple of 3" in r["failed_criterion"]
    assert "consecutive" in " ".join(r["exceptions"])        # N1C: adjacent out-of-frame exons may be skipped together


def test_in_frame_exon_passes_the_computable_criteria_but_stays_unassessable():
    """Frame and position are computable; functional domains and natural-skipping evidence are not connected
    (decision 2026-11-05), so the verdict is 'unable to assess' with both reasons named."""
    r = BS.exon_skipping(Tr(protein_len=300), 2, mechanism="loss_of_function")   # exon 2 is 6.7% of the protein
    assert r["classification"] == "unable_to_assess"
    assert any("domain" in x for x in r["unassessable_reason"])
    assert any("natural" in x or "skipping has been observed" in x for x in r["unassessable_reason"])
    assert "in frame (60 nt, a multiple of 3)" in " ".join(r["criteria_met"])
    assert r["exon_share_percent"] == pytest.approx(6.7, abs=0.1)
    assert r["classification_ceiling"] == "likely_eligible"  # never 'eligible' without functional evidence


def test_exon_over_ten_percent_of_the_protein_is_unlikely_eligible():
    tr = Tr(protein_len=600)                                 # exon 2 is now 3.3% of the protein
    assert BS.exon_skipping(tr, 2, "loss_of_function")["exon_share_percent"] < 10
    r = BS.exon_skipping(Tr(protein_len=90), 2, "loss_of_function")   # 20/90 = 22%
    assert r["classification"] == "unlikely_eligible" and "more than 10%" in r["failed_criterion"]


def test_junction_stop_codon_makes_it_not_eligible():
    """An in-frame exon with a non-zero phase forms a new codon when its neighbours are joined; if that codon is
    a stop (TAA/TAG/TGA), N1C classifies the exon as not eligible."""
    # exon 1 carries 31 coding nt, so exon 2 starts at phase 1: skipping exon 2 joins exon 1's last nucleotide
    # ("T") with exon 3's first two ("AA") -> TAA, a stop codon.
    seq = "".join(["T" * 10,                      # 5' UTR, 10 nt
                   "ATG" + "GCT" * 9 + "T",       # exon 1 coding: 31 nt, ends in T
                   "GCT" * 20,                    # exon 2: 60 nt, in frame, phase 1 in
                   "AAG" + "GCT" * 9,             # exon 3: 30 nt, starts with AA
                   "GC" + "GCT" * 8 + "TAA",      # exon 4
                   "T" * 10])
    e1 = (1, 41)                                  # 10 UTR + 31 coding
    tr = Tr(seq=seq, exons=[e1, (42, 101), (102, 131), (132, 160), (161, 170)], cds=(11, 158), protein_len=49)
    assert [e["phase_in"] for e in BS.coding_exons(tr)] == [0, 1, 1, 1]
    r = BS.exon_skipping(tr, 2, "loss_of_function")
    assert r["junction_codon"] == "TAA"
    assert r["classification"] == "not_eligible" and "stop codon TAA" in r["failed_criterion"]
    assert any("penultimate" in x for x in r["exceptions"])


def test_gain_of_function_mechanism_is_not_the_frame_restoring_case():
    """N1C: restoring the reading frame is the aim for LoF variants; for GoF/DN, skipping is a knockdown idea."""
    r = BS.exon_skipping(Tr(), 3, mechanism="gain_of_function")
    assert r["classification"] != "not_eligible" or "multiple of 3" not in (r.get("failed_criterion") or "")
    assert any("knockdown" in x for x in r["exceptions"])


# --- gene replacement (AAV): capacity is deterministic, mechanism is not

@pytest.mark.parametrize("cds_nt,fits", [(4700, True), (4701, False), (1179, True), (11058, False)])
def test_aav_capacity_threshold(cds_nt, fits):
    r = BS.gene_replacement(cds_nt, mechanism="loss_of_function")
    assert (r["cds_fits_aav"] is True) is fits
    if not fits:
        assert r["classification"] == "not_applicable" and "4.7 kb" in r["failed_criterion"]
    else:
        assert r["classification"] == "theoretically_possible"
        assert "promoter" in r["note"]                       # the other elements are not sized here


@pytest.mark.parametrize("mech", ["gain_of_function", "dominant_negative"])
def test_gene_replacement_not_for_gain_of_function(mech):
    r = BS.gene_replacement(1179, mechanism=mech)
    assert r["classification"] == "not_applicable" and "abnormal protein" in r["failed_criterion"]


def test_gene_replacement_without_a_mechanism_source():
    r = BS.gene_replacement(1179, mechanism=None)
    assert r["classification"] == "unable_to_assess"
    assert any("mechanism" in x for x in r["unassessable_reason"])


# --- RNA knockdown

def test_total_knockdown_needs_dosage_data_that_is_not_connected():
    r = BS.knockdown(mechanism="gain_of_function", copies_affected=1, zygosity="heterozygous", allele_specific=False)
    assert r["classification"] == "unable_to_assess"
    assert any("dosage" in x for x in r["unassessable_reason"])


def test_total_knockdown_not_for_loss_of_function():
    r = BS.knockdown(mechanism="loss_of_function", copies_affected=1, zygosity="heterozygous", allele_specific=False)
    assert r["classification"] == "not_applicable" and "reduce" in r["failed_criterion"]


def test_allele_specific_knockdown_needs_a_normal_allele():
    het = BS.knockdown(mechanism="dominant_negative", copies_affected=1, zygosity="heterozygous", allele_specific=True)
    assert het["classification"] == "theoretically_possible" and het["target"] == "the variant itself"
    for zyg, copies in (("homozygous", 2), ("hemizygous", 1)):
        r = BS.knockdown(mechanism="dominant_negative", copies_affected=copies, zygosity=zyg, allele_specific=True)
        assert r["classification"] == "not_applicable" and "no normal allele" in r["failed_criterion"]


# --- upregulation from the wild-type allele: never graded (N1C)

def test_upregulation_is_described_not_graded():
    r = BS.upregulation(mechanism="haploinsufficiency", copies_affected=1, zygosity="heterozygous")
    assert r["classification"] == "not_graded" and r["premises_met"] is True
    assert "N1C" in r["note"]
    r2 = BS.upregulation(mechanism="haploinsufficiency", copies_affected=1, zygosity="hemizygous")
    assert r2["premises_met"] is False and "no normal copy" in r2["failed_criterion"]
    r3 = BS.upregulation(mechanism=None, copies_affected=1, zygosity="heterozygous")
    assert r3["classification"] == "unable_to_assess"


# --- base and prime editing: from the HGVS alone

@pytest.mark.parametrize("cdna,editor,why", [
    ("c.1678G>A", "base_editing", "transition"),             # G>A: reverted by an adenine base editor
    ("c.386G>A", "base_editing", "transition"),
    ("c.2755C>T", "base_editing", "transition"),
    ("c.1521_1523del", "prime_editing", "deletion"),
    ("c.33dup", "prime_editing", "insertion"),
    ("c.289del", "prime_editing", "deletion"),
    ("c.1678G>C", "prime_editing", "transversion"),
    ("c.7544_9286del", None, "large"),
])
def test_editor_from_the_variant(cdna, editor, why):
    r = BS.editing(cdna)
    assert r["editor"] == editor, (cdna, r)
    assert why in r["reason"]
    if editor is None:
        assert r["classification"] == "not_applicable"
    else:
        assert r["classification"] == "theoretically_possible"
        assert "PAM" in r["note"]                            # not assessed (decision 2026-11-05)


# --- X inactivation / mosaicism

def test_x_linked_female_heterozygote_is_unassessable_for_the_wt_dependent_modalities():
    out = BS.x_inactivation_caveat(chromosome="X", sex="female", zygosity="heterozygous", stated_skew=None)
    assert out and "X inactivation" in out
    assert BS.x_inactivation_caveat("X", "male", "hemizygous", None) is None
    assert BS.x_inactivation_caveat("X", "female", "heterozygous", "80:20 skewed") is None
    assert BS.x_inactivation_caveat("17", "female", "heterozygous", None) is None


# --- the record the ledger keeps, and what step 4 ranks on

def test_every_modality_is_recorded_once_per_branch():
    assert len(BS.MODALITIES) == 6
    rec = BS.record("gene_replacement", {"classification": "not_applicable", "failed_criterion": "x"}, branch="B")
    assert rec["modality"] == "gene_replacement" and rec["section"] == BS.SECTION
    assert rec["premises_complete"] is True and rec["human_precedent"] is None
    un = BS.record("rna_knockdown", {"classification": "unable_to_assess", "unassessable_reason": ["dosage"]}, branch="B")
    assert un["premises_complete"] is False


def test_conclusion_words_never_claim_efficacy():
    for m in BS.MODALITIES:
        for c in ("not_eligible", "unlikely_eligible", "likely_eligible", "unable_to_assess", "not_applicable",
                  "theoretically_possible", "not_graded"):
            text = BS.sentence(m, {"classification": c})
            assert not any(w in text.lower() for w in ("recommended", "effective", "proven", "will work", "cure"))


# --- ledger checks

def _rows(**over):
    base = {"section": BS.SECTION, "applies_to": ["B"], "classification": "not_applicable",
            "failed_criterion": "x", "conclusion": "fine", "unassessable_reason": [], "evidence_ids": ["e1"]}
    return [{**base, "modality": m, **over.get(m, {})} for m in BS.MODALITIES]


def test_check_passes_on_a_complete_set():
    assert BS.problems(_rows(), ["B"]) == []


def test_check_catches_what_the_contract_forbids():
    assert "no judgement for" in " ".join(BS.problems(_rows()[:3], ["B"]))
    doubled = _rows() + _rows()[:1]
    assert "judged more than once" in " ".join(BS.problems(doubled, ["B"]))
    graded = BS.problems(_rows(gene_replacement={"classification": "likely_eligible"}), ["B"])
    assert "N1C eligibility grade" in " ".join(graded)
    silent = BS.problems(_rows(rna_knockdown={"classification": "unable_to_assess", "unassessable_reason": []}), ["B"])
    assert "without saying what is missing" in " ".join(silent)
    nores = BS.problems(_rows(gene_replacement={"classification": "not_applicable", "failed_criterion": None}), ["B"])
    assert "without the criterion it failed" in " ".join(nores)
    strong = BS.problems(_rows(gene_replacement={"conclusion": "this is effective"}), ["B"])
    assert "claims efficacy" in " ".join(strong)
    nomech = BS.problems(_rows(wt_upregulation={"classification": "not_graded", "evidence_ids": [],
                                                "facts": {"used_mechanism": True}}), ["B"])
    assert "cites no evidence" in " ".join(nomech)
    # a verdict that did not use the mechanism (AAV capacity) needs no mechanism evidence
    size = BS.problems(_rows(gene_replacement={"evidence_ids": [], "facts": {"used_mechanism": False}}), ["B"])
    assert "cites no evidence" not in " ".join(size)

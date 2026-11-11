"""Fix plan D2 (decision 2026-11-11): a genotype criterion that names another gene is not met by the patient's
reported genotype. Blind test: an MPZ patient was "conditional" for a trial requiring PMP22 duplication (CMT1A)."""
import pytest

from aitx.evidence import criteria as C
from aitx.evidence import genecontext as GC

KNOWN = {"PMP22", "MPZ", "GJB1", "CFTR", "DMD", "AR"}
PF = {"variants": [{"gene": "MPZ", "protein": "p.Lys96Glu", "quote": "MPZ c.286A>G p.Lys96Glu (heterozygous)",
                    "class": "missense", "zygosity": "heterozygous"}], "sex": None, "age_months": None}
BRANCH = {"gene": "MPZ", "diagnosis": {"label": "CMT1B"}}


@pytest.fixture(autouse=True)
def _known(monkeypatch):
    monkeypatch.setattr(GC, "known_genes", lambda: KNOWN)


def ev(quote, fact="genetic_confirmation", kind="inclusion"):
    return C.evaluate({"fact": fact, "op": "", "value": "", "quote": quote}, PF, {}, BRANCH, ["CMT1B"], kind)


@pytest.mark.parametrize("quote,fact", [
    ("verified documentation of genetic testing showing duplication of the PMP22 gene by an accredited lab",
     "genetic_confirmation"),
    ("duplication of the PMP22 gene", "variant"),
])
def test_a_criterion_requiring_another_gene_is_not_met(quote, fact):
    st, f, note, _ = ev(quote, fact)
    assert st == "does_not_satisfy" and "PMP22" in note and f["value"] == "p.Lys96Glu"


def test_an_exclusion_naming_another_gene_passes():
    st, _, _, _ = ev("known pathogenic variant in GJB1", "variant", "exclusion")
    assert st == "does_not_satisfy"            # the patient does not have it: the exclusion does not exclude


@pytest.mark.parametrize("quote,fact", [
    ("genetic confirmation of CMT", "genetic_confirmation"),             # names no gene: other rules decide
    ("pathogenic variant in MPZ or PMP22", "genetic_confirmation"),       # the patient's gene is among them
    ("AR", "variant"),                                                    # no gene words around a gene-like token
])
def test_reverse_cases_are_not_decided_by_this_rule(quote, fact):
    st, _, note, _ = ev(quote, fact)
    assert not (st == "does_not_satisfy" and "requires" in note)


def test_genes_named_needs_known_symbols_and_same_case():
    assert GC.genes_named("duplication of the PMP22 gene", KNOWN) == ["PMP22"]
    assert GC.genes_named("pmp22 duplication; CMTNSv2R score", KNOWN) == []


# --- guards found by the offline scan of the existing ledgers (2026-11-11)

@pytest.mark.parametrize("quote", [
    "there will not be a requirement for confirmed CDKN2A deletion for study eligibility",    # nothing is required
    "Tumor positive for a pathogenic BRAF alteration",                                        # somatic, not germline
])
def test_negated_or_somatic_gene_criteria_are_not_decided(quote, monkeypatch):
    monkeypatch.setattr(GC, "known_genes", lambda: KNOWN | {"CDKN2A", "BRAF"})
    st, _, note, _ = ev(quote, "variant")
    assert not (st == "does_not_satisfy" and "requires" in note)


def test_genes_listed_one_per_line_beside_the_patients_gene_are_alternatives(monkeypatch):
    """DEEPTYPE (NCT06566066): 'mutation in SLC16A2' / 'mutation in THRA' / 'abnormal fT3/fT4 ratio' - a THRA patient."""
    monkeypatch.setattr(GC, "known_genes", lambda: {"SLC16A2", "THRA"})
    pf = {"variants": [{"gene": "THRA", "protein": "p.Ser45Ile", "quote": "THRA c.134G>T p.Ser45Ile (heterozygous)",
                        "class": "missense", "zygosity": "heterozygous"}], "sex": None, "age_months": None}
    items = [{"id": "inc1", "kind": "inclusion", "text": "Presence of a coding or non-coding mutation in SLC16A2"},
             {"id": "inc2", "kind": "inclusion", "text": "Presence of a coding or non-coding mutation in THRA"}]
    mapped = {"items": items, "mappings": [
        {"id": "inc1", "fact": "genetic_confirmation", "quote": items[0]["text"], "op": "", "value": ""},
        {"id": "inc2", "fact": "genetic_confirmation", "quote": items[1]["text"], "op": "", "value": ""}]}
    lines = C.lines_for({}, mapped, pf, {}, {"gene": "THRA"}, ["congenital hypothyroidism"])
    by = {l["item"]: l for l in lines}
    assert by["inc1"]["patient_status"] == "not_assessed" and by["inc1"]["note"] == C.ALTERNATIVE_GENE_NOTE
    assert by["inc2"]["patient_status"] == "satisfies"


def test_reverse_another_gene_alone_still_fails(monkeypatch):
    items = [{"id": "inc1", "kind": "inclusion", "text": "duplication of the PMP22 gene"}]
    mapped = {"items": items, "mappings": [{"id": "inc1", "fact": "variant", "quote": items[0]["text"], "op": "", "value": ""}]}
    lines = C.lines_for({}, mapped, PF, {}, BRANCH, ["CMT1B"])
    assert lines[0]["patient_status"] == "does_not_satisfy"


def test_an_alternative_naming_a_disease_group_keeps_the_rule_out(monkeypatch):
    """PRAC-SLC35A2 (NCT04199000): 'confirmed diagnosis of CDG or NGLY1 deficiency' - CDG includes SLC35A2-CDG."""
    monkeypatch.setattr(GC, "known_genes", lambda: KNOWN | {"NGLY1"})
    st, _, note, _ = ev("genetically confirmed diagnosis of CDG or NGLY1 deficiency")
    assert not (st == "does_not_satisfy" and "requires" in note)


def test_reverse_alternatives_that_all_name_other_genes_still_fail(monkeypatch):
    monkeypatch.setattr(GC, "known_genes", lambda: KNOWN | {"GDAP1"})
    st, _, note, _ = ev("pathogenic variant in PMP22 or GDAP1")
    assert st == "does_not_satisfy"

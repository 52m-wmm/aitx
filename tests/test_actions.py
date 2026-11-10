"""'Same action' keys (step 3.0 contract 1.3). RxNav / openFDA / ChEMBL responses are recorded
(tests/fixtures/actions_http.json, captured 2026-11-03 from the live APIs); no network here."""
import json
from pathlib import Path

import pytest

from aitx import http
from aitx.evidence import actions as A

FIX = json.loads((Path(__file__).parent / "fixtures" / "actions_http.json").read_text())


@pytest.fixture(autouse=True)
def recorded(monkeypatch):
    def fake_get(url, **kw):
        if url not in FIX:
            pytest.fail(f"unrecorded request {url}")
        text = FIX[url]
        if text.startswith("__HTTP_ERROR__"):                   # recorded failure, e.g. openFDA 'no matches' = 404
            raise RuntimeError(text.split(" ", 1)[1])
        return http.Fetched(url, text, 1793700000, True)
    monkeypatch.setattr(http, "get", fake_get)


def key(name):
    return A.drug_key(name)["key"]


@pytest.mark.parametrize("case,a,b,same", [
    ("1 brand vs generic combo", "Trikafta", "elexacaftor / tezacaftor / ivacaftor", True),
    ("2 order and case", "Trikafta", "ELEXACAFTOR/IVACAFTOR/TEZACAFTOR", True),
    ("3 combo vs single", "Trikafta", "ivacaftor", False),
    ("3 single brand vs generic", "Kalydeco", "ivacaftor", True),
    ("4 brand vs generic", "Oxlumo", "lumasiran", True),
    ("5 different drugs", "lumasiran", "nedosiran", False),
    ("6 salt vs ingredient", "pyridoxine hydrochloride", "pyridoxine", True),
    ("13 fallback, salt removed", "ABC-123 hydrochloride", "abc-123", True),
    ("13b fallback, combo sorted", "Foo sodium / Bar", "bar + foo", True),
])
def test_drug_identity(case, a, b, same):
    assert (key(a) == key(b)) is same, (case, key(a), key(b))


def test_rxcui_values_match_live_check():
    assert key("Trikafta") == "drug:rxcui:1243041+1999382+2256951"   # MIN 2257010 -> 3 ingredients
    assert key("Oxlumo") == "drug:rxcui:2467140"
    assert key("pyridoxine hydrochloride") == "drug:rxcui:684879"
    assert "openfda" in A.drug_key("Trikafta")["method"]               # not an RxNorm name; via the FDA label


def test_unresolvable_brand_gets_fallback_key():
    r = A.drug_key("Kaftrio")                                          # 2b: EU brand, in none of the sources
    assert r == {"input": "Kaftrio", "key": "drug:name:kaftrio", "normalized": False, "ingredients": [],
                 "method": "fallback: normalized name (no RxNorm, openFDA or ChEMBL match)"}


def test_dose_wording_does_not_change_the_action():
    # 7: dose, route and schedule live in the claim, not in the key
    assert A.strip_dose("lumasiran 3 mg/kg monthly") == "lumasiran"
    assert key("lumasiran 3 mg/kg monthly") == key("lumasiran quarterly") == key("lumasiran") == "drug:rxcui:2467140"
    assert A.fallback_key("XYZ-9 sodium 25 mg tablets twice daily") == A.fallback_key("xyz-9") == "drug:name:xyz-9"


def test_trial_keys():
    assert A.trial_key("nct01234567") == "trial:NCT01234567"
    with pytest.raises(ValueError):
        A.trial_key("NCT123")


@pytest.mark.parametrize("a,b,same", [
    (("aso_exon_skipping", "DMD", "exon51"), ("aso_exon_skipping", "dmd", "Exon51"), True),
    (("aso_exon_skipping", "DMD", "exon51"), ("aso_exon_skipping", "DMD", "exon53"), False),            # 10
    (("aso_knockdown_allele_specific", "SPTLC1", None), ("aso_knockdown_total", "SPTLC1", None), False),  # 11
    (("organ_transplant", "liver", None), ("organ_transplant", ["kidney", "liver"], None), False),        # 12
    (("organ_transplant", ["liver", "kidney"], None), ("organ_transplant", ["kidney", "liver"], None), True),
    (("diet", "Protein restriction", None), ("diet", "protein-restriction", None), True),
])
def test_strategy_identity(a, b, same):
    assert (A.strategy_key(*a) == A.strategy_key(*b)) is same


def test_strategy_vocabulary_is_closed():
    with pytest.raises(ValueError):
        A.strategy_key("magic_cure", "DMD")
    with pytest.raises(ValueError):
        A.strategy_key("organ_transplant", "spleen")


def test_drug_implementing_a_strategy_is_the_same_action():
    # 9: approved exon-51 ASO (Existing Targeted) vs a bespoke exon-51 ASO (Bespoke)
    ete = {"key": key("eteplirsen"), "implements": A.strategy_key("aso_exon_skipping", "DMD", "exon51")}
    bespoke = {"key": A.strategy_key("aso_exon_skipping", "DMD", "exon51")}
    assert A.same_action(ete, bespoke)
    assert not A.same_action(ete, {"key": A.strategy_key("aso_exon_skipping", "DMD", "exon53")})


# --- parenthesised abbreviations (2026-11-09, found in the blind test)

@pytest.mark.parametrize("name,want", [
    ("potassium bromide (KBr)", "potassium bromide"),
    ("sodium thiosulfate (STS)", "sodium thiosulfate"),
    ("anti-seizure medication (ASM)", "anti-seizure medication"),
    ("coenzyme Q10 (CoQ10)", "coenzyme Q10"),
    # kept: a spelled-out synonym or qualifier is not an abbreviation, and dropping it could lose the drug
    ("vitamin B6 (pyridoxine)", "vitamin B6 (pyridoxine)"),
    ("insulin (human)", "insulin (human)"),
    ("NMDA antagonist (memantine)", "NMDA antagonist (memantine)"),
    ("quinidine", "quinidine"),
    ("", ""),
])
def test_strip_abbrev(name, want):
    assert A.strip_abbrev(name) == want


@pytest.mark.parametrize("pair", [
    ("potassium bromide", "potassium bromide (KBr)"),
    ("sodium thiosulfate", "sodium thiosulfate (STS)"),
    ("anti-seizure medication", "anti-seizure medication (ASM)"),
])
def test_the_two_spellings_share_one_key(pair):
    """The bug: 'potassium bromide' got drug:rxcui:34299 and 'potassium bromide (KBr)' got drug:name:kbr, so
    the same drug was written twice in one section with conflicting conclusions."""
    plain, abbrev = pair
    assert A.components(plain) == A.components(abbrev)
    assert A.fallback_key(plain) == A.fallback_key(abbrev)
    assert "kbr" not in A.fallback_key(abbrev) and "asm" not in A.fallback_key(abbrev)


def test_drug_key_uses_the_stripped_name(monkeypatch):
    seen = []

    def rxnorm(name):
        seen.append(name)
        return [{"rxcui": "34299", "name": "potassium bromide"}] if name == "potassium bromide" else []

    monkeypatch.setattr(A, "rxnorm_ingredients", rxnorm)
    got = A.drug_key("potassium bromide (KBr)")
    assert got["key"] == "drug:rxcui:34299" and got["normalized"] is True
    assert seen[0] == "potassium bromide"              # the abbreviation never reached RxNorm
    # reverse: a spelled-out parenthetical is still passed through unchanged
    seen.clear()
    monkeypatch.setattr(A, "openfda_generic", lambda n: None)
    monkeypatch.setattr(A, "chembl_parent", lambda n: None)
    A.drug_key("insulin (human)")
    assert seen[0] == "insulin (human)"


@pytest.mark.parametrize("a,b", [
    ("potassium bromide", "potassium chloride"),
    ("sodium thiosulfate", "sodium nitroprusside"),
    ("anti-seizure medication", "anti-reflux medication"),
    ("potassium bromide (KBr)", "potassium chloride (KCl)"),
    ("coenzyme Q10 (CoQ10)", "coenzyme A"),
    ("vitamin B6 (pyridoxine)", "vitamin B12 (cobalamin)"),
])
def test_different_drugs_are_never_merged(a, b):
    """Reverse check for the abbreviation fix: stripping "(KBr)" must not pull unrelated drugs together."""
    assert A.components(a) != A.components(b)
    assert A.fallback_key(a) != A.fallback_key(b)


def test_a_name_made_only_of_salt_words_keeps_them():
    """Both words of "potassium bromide" are salt-form words, so stripping them left nothing and the fallback
    key was the empty "drug:name:" - which every such drug would share (2026-11-09)."""
    assert A.components("potassium bromide") == ["potassium bromide"]
    assert A.fallback_key("potassium bromide") == "drug:name:potassium bromide"
    assert A.fallback_key("potassium chloride") != A.fallback_key("potassium bromide")
    # the salt-stripping itself still works where a real ingredient name remains
    assert A.components("metoprolol succinate") == ["metoprolol"]
    assert A.components("sodium thiosulfate") == ["thiosulfate"]

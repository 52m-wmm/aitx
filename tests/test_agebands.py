"""Age-band limits decided by code (user decision 2026-11-12; ICH E11 section 2.5, disputed zones unknown)."""
import pytest

from aitx.evidence import agebands as AB


def pf(months, quote="x-year-old"):
    return {"age_months": months, "age_quote": quote if months is not None else None}


@pytest.mark.parametrize("text,months,want", [
    ("Newborns", 15 * 12, "does_not_satisfy"),                 # CFTR: 15-year-old, newborn row
    ("Newborn with Cystic Fibrosis", 15 * 12, "does_not_satisfy"),
    ("Newborns – management", 0.3, "satisfies"),
    ("Newborns", None, "unknown"),                              # age not stated
    ("Infants", 6, "satisfies"),
    ("Infants", 18, "unknown"),                                 # 12-23 months: ICH vs common use differ
    ("Infants", 7 * 12, "does_not_satisfy"),
    ("Children", 7 * 12, "satisfies"),
    ("Children", 15 * 12, "unknown"),                           # "children" is often used for all minors
    ("Children", 30 * 12, "does_not_satisfy"),
    ("Adolescents", 14 * 12, "satisfies"),
    ("Adolescents", 17 * 12, "unknown"),                        # 16-18 by region (ICH), 10-19 (WHO)
    ("Adults", 40 * 12, "satisfies"),
    ("Adults", 7 * 12, "does_not_satisfy"),
    ("Adults", 17 * 12, "unknown"),
    ("Pediatric patients", 7 * 12, "satisfies"),
    ("Pediatric patients", 19 * 12, "unknown"),
])
def test_band_against_stated_age(text, months, want):
    st, fact, note = AB.limit_status(text, pf(months), "cystic fibrosis")
    assert st == want and "ICH E11" in note
    assert (fact["quote"] is None) == (months is None)


@pytest.mark.parametrize("text", ["After the newborn period", "older than infants", "only for select persons",
                                  "children younger than 2 years", "severe disease"])
def test_reverse_not_a_plain_band_is_left_to_the_context_check(text):
    assert AB.limit_status(text, pf(15 * 12), "cystic fibrosis") is None


def test_reverse_a_band_with_more_conditions_is_not_settled_by_age_alone():
    st, _, _ = AB.limit_status("Children with severe lung disease", pf(7 * 12), "cystic fibrosis")
    assert st == "unknown"                                        # inside the band, but "severe lung disease" remains
    st, _, _ = AB.limit_status("Children with severe lung disease", pf(30 * 12), "cystic fibrosis")
    assert st == "does_not_satisfy"                               # outside the band: the other words cannot rescue it


def test_reverse_alternatives_are_never_ruled_out():
    st, _, _ = AB.limit_status("Newborns or persons with meconium ileus", pf(15 * 12), "cystic fibrosis")
    assert st == "unknown"

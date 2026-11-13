"""Step 2: a feature stated as one of two possibilities ("normal or mildly delayed") is possible, not present
(user decision 2026-11-12, RETEST-EIF2B1)."""
import pytest

from aitx.disease import extract as X

TEXT = "Initial motor and intellectual development is normal or mildly delayed. Truncal and appendicular ataxia."


@pytest.mark.parametrize("quote,want", [
    ("mildly delayed", "normal or mildly delayed"),
    ("normal or mildly delayed", "normal or mildly delayed"),
])
def test_or_with_a_normal_alternative_is_possible(quote, want):
    assert X.possible_phrase(TEXT, quote) == want


def test_the_alternative_after_the_quote_counts_too():
    assert X.possible_phrase("Hearing is mildly reduced or normal.", "mildly reduced") == "mildly reduced or normal"


@pytest.mark.parametrize("text,quote", [
    (TEXT, "Truncal and appendicular ataxia"),                  # stated plainly
    ("Seizures or episodes of lethargy occur.", "Seizures"),   # two findings, neither negated
    ("Intellectual disability, mild or moderate.", "Intellectual disability"),
])
def test_reverse_a_plain_or_two_abnormal_alternatives_stay_present(text, quote):
    assert X.possible_phrase(text, quote) is None

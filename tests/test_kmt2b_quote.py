import pytest
from scripts.quote_kmt2b_two_votes import offpeak_cost


def test_same_input_quote_uses_both_input_categories_and_output():
    value={'prompt_cache_hit_tokens':1000,'prompt_cache_miss_tokens':2000,'completion_tokens':3000}
    assert offpeak_cost(value)==pytest.approx(.002103)
    with pytest.raises(KeyError):offpeak_cost({})

"""Independent support check (generic; used by rule drafting now and by step 5 later). Offline: fake LLM."""
import json

import pytest

from aitx.evidence import support_check as SC


def fake(monkeypatch, answer):
    seen = {}

    def chat(messages, k, use_cache, prompt_version=None):
        seen["prompt"] = messages[1]["content"]
        seen["version"] = prompt_version
        return {"content": json.dumps(answer), "served_model": "fake-model"}
    monkeypatch.setattr(SC.X, "_cached_chat", chat)
    monkeypatch.setattr(SC.X.llm, "config", lambda: {"model": "m", "base_url": "u", "api_key": "", "expect_model_prefix": ""})
    return seen


@pytest.mark.parametrize("verdicts,want", [
    (["supported", "supported"], "supported"),
    (["supported", "partially_supported"], "partially_supported"),
    (["partially_supported", "not_supported"], "not_supported"),
    ([], "not_supported"),
])
def test_overall_is_computed_by_code(verdicts, want):
    assert SC.overall(verdicts) == want


def test_items_judged_separately_and_missing_answers_count_as_not_supported(monkeypatch):
    seen = fake(monkeypatch, {"items": [{"item": 1, "verdict": "supported", "reason": "stated"}],
                              "overall": "supported"})             # the LLM's own overall is ignored
    r = SC.check_support("claim", ["cond", "concl"], ["quote one"])
    assert [i["verdict"] for i in r["items"]] == ["supported", "not_supported"]
    assert r["overall"] == "not_supported" and r["llm"]["served_model"] == "fake-model"
    assert seen["version"] == SC.PROMPT_VERSION and "quote one" in seen["prompt"]


def test_bad_verdicts_and_item_numbers_ignored(monkeypatch):
    fake(monkeypatch, {"items": [{"item": 1, "verdict": "probably"}, {"item": 7, "verdict": "supported"}]})
    r = SC.check_support("claim", ["only item"], ["q"])
    assert r["items"][0]["verdict"] == "not_supported"


def test_rule_items_spell_out_conditions_conclusion_scope():
    rule = {"gene": "CFTR", "statement": "s", "applies_when": {"zygosity": ["heterozygous"], "variant_class": ["missense"]},
            "effect": {"supports": ["OMIM:277180"], "argues_against": ["OMIM:219700"]}, "sources": []}
    items = SC.rule_items(rule, {"OMIM:277180": "CBAVD", "OMIM:219700": "cystic fibrosis"})
    assert any("a single heterozygous variant (one variant, on one allele)" in i for i in items)
    assert any(i.startswith("Conclusion: such variants point to CBAVD rather than cystic fibrosis") for i in items)
    assert items[-1].startswith("Scope:") and "difference in frequency" in items[-1]

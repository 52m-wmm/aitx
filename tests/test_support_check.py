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
    r = SC.check_support("claim", ["cond", "concl"], ["quote one"], n_checks=1)
    assert [i["verdict"] for i in r["items"]] == ["supported", "not_supported"]
    assert r["overall"] == "not_supported" and r["llm"]["served_model"] == "fake-model"
    assert seen["version"] == SC.PROMPT_VERSION and "quote one" in seen["prompt"]


def test_bad_verdicts_and_item_numbers_ignored(monkeypatch):
    fake(monkeypatch, {"items": [{"item": 1, "verdict": "probably"}, {"item": 7, "verdict": "supported"}]})
    r = SC.check_support("claim", ["only item"], ["q"], n_checks=1)
    assert r["items"][0]["verdict"] == "not_supported"


def test_rule_items_spell_out_conditions_conclusion_scope():
    rule = {"gene": "CFTR", "statement": "s", "applies_when": {"zygosity": ["heterozygous"], "variant_class": ["missense"]},
            "effect": {"supports": ["OMIM:277180"], "argues_against": ["OMIM:219700"]}, "sources": []}
    items = SC.rule_items(rule, {"OMIM:277180": {"label": "CBAVD", "synonyms": ["congenital bilateral aplasia of vas deferens"]},
                                 "OMIM:219700": {"label": "cystic fibrosis", "synonyms": []}})
    assert items[0] == ("Condition: the rule is about CFTR variants that are missense variants and that are present as "
                        "a single heterozygous variant (one variant, on one allele).")      # conditions judged together
    assert any(i.startswith("Conclusion: such variants point to CBAVD (also called: congenital bilateral aplasia "
                            "of vas deferens) rather than cystic fibrosis") for i in items)


def test_conclusion_uses_code_supplied_names_not_rule_wording():
    rule = {"gene": "COL1A1", "statement": "Loss of exon 6 results in arthrochalasia EDS.", "applies_when": {"exon": [6, 6]},
            "effect": {"supports": ["OMIM:130060"], "argues_against": []}, "sources": []}
    items = SC.rule_items(rule, {"OMIM:130060": {"label": "Ehlers-Danlos syndrome arthrochalasia type 1",
                                                 "synonyms": ["EDS VIIA", "arthrochalasia EDS type 1"]}})
    concl = next(i for i in items if i.startswith("Conclusion"))
    assert "Ehlers-Danlos syndrome arthrochalasia type 1 (also called: EDS VIIA; arthrochalasia EDS type 1)" in concl
    assert items[-1].startswith("Scope:") and "difference in frequency" in items[-1]


@pytest.mark.parametrize("js,want", [
    (["supported"] * 3, "supported"),
    (["supported", "supported", "partially_supported"], "partially_supported"),   # not unanimous
    (["supported", "not_supported", "partially_supported"], "not_supported"),
])
def test_three_independent_checks_must_agree(js, want):
    assert SC.combine(js) == want


def test_independent_samples_are_combined(monkeypatch):
    answers = {0: "supported", 1: "supported", 2: "partially_supported"}

    def chat(messages, k, use_cache, prompt_version=None):
        return {"content": json.dumps({"items": [{"item": 1, "verdict": answers[k], "reason": f"r{k}"}]}), "served_model": "m"}
    monkeypatch.setattr(SC.X, "_cached_chat", chat)
    monkeypatch.setattr(SC.X.llm, "config", lambda: {"model": "m", "base_url": "u", "api_key": "", "expect_model_prefix": ""})
    r = SC.check_support("claim", ["item"], ["q"])
    assert r["items"][0]["judgements"] == ["supported", "supported", "partially_supported"]
    assert r["items"][0]["verdict"] == "partially_supported" and r["overall"] == "partially_supported"


def test_prompt_states_conclusion_strength_limits():
    assert "does not support" in SC.SYSTEM and "single case" in SC.SYSTEM and "does not support causation" in SC.SYSTEM


def test_rule_items_say_the_narrowing_conditions(monkeypatch):
    """A narrowed rule must be judged on its narrow condition, not as if it had none (2026-11-05)."""
    names = {"OMIM:619115": {"label": "EDS/OI overlap"}}
    sub = {"gene": "COL1A1", "applies_when": {"variant_class": ["missense"],
           "aa_substitution": {"position": 134, "from": "Arg", "to": "Cys"}},
           "effect": {"supports": ["OMIM:619115"]}}
    cond = SC.rule_items(sub, names)[0]
    assert "replace Arg at protein residue 134 with Cys" in cond and "missense" in cond
    loss = {"gene": "COL1A1", "applies_when": {"exon_loss": [6, 6]}, "effect": {"supports": ["OMIM:130060"]}}
    cond = SC.rule_items(loss, {})[0]
    assert "remove the whole of exon 6" in cond and "splice variant at its boundary" in cond
    assert "lie in exon 6" not in cond                      # not the old, wider wording


# --- report-claim cases in the regression set (2026-11-11, blind batch 2: GEMIN5 CoQ10)

def _eval_module():
    import importlib.util
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "scripts" / "eval_support_check.py"
    spec = importlib.util.spec_from_file_location("eval_support_check", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _claim_case():
    E = _eval_module()
    cases = json.loads(E.SET.read_text())["cases"]
    return E, next(c for c in cases if c.get("kind") == "claim" and c["rule_id"] == "CLAIM-GEMIN5-COQ10")


def test_the_gemin5_claim_case_records_why_it_needs_context():
    _, c = _claim_case()
    assert c["expected"] == "supported" and "完整上下文" in c["note"]
    assert c["as_run"]["overall"] == "partially_supported"
    ctx = " ".join(c["claim"]["context_quotes"])
    assert "GEMIN5" in ctx and not any("GEMIN5" in q for q in c["claim"]["quotes"])   # identity only in context


def test_a_claim_case_is_judged_with_its_context_quotes(monkeypatch):
    E, c = _claim_case()
    seen = fake(monkeypatch, {"items": [{"item": 1, "verdict": "supported", "reason": "stated"}]})
    r = E.check_case(c, use_cache=True)
    assert r["overall"] == "supported"
    for q in c["claim"]["quotes"] + c["claim"]["context_quotes"]:
        assert q in seen["prompt"]


def test_claim_cases_survive_collection_and_leak_check(tmp_path):
    E, c = _claim_case()
    path = tmp_path / "set.json"
    path.write_text(json.dumps({"description": "d", "cases": [c]}))
    E.collect(rules_dir=tmp_path / "no_rules", path=path)
    assert [x["rule_id"] for x in json.loads(path.read_text())["cases"]] == ["CLAIM-GEMIN5-COQ10"]
    assert E.leaks([c]) == []


def test_batch3_cases_are_in_the_set():
    E = _eval_module()
    cases = {c["rule_id"]: c for c in json.loads(E.SET.read_text())["cases"]}
    light = cases["CLAIM-SNRNP200-BRIGHT-LIGHT"]
    assert light["expected"] == "blocked" and "animal models" in light["claim"]["quotes"][0]
    same = cases["SAME-SNRNP200-UV-SUNGLASSES"]
    assert same["expected"] == "same" and {x["section"] for x in same["entries"]} == {
        "contraindications_precautions", "supportive_management"}


def test_same_action_cases_are_listed_not_scored(monkeypatch):
    E = _eval_module()
    cases = json.loads(E.SET.read_text())["cases"]
    same = [c for c in cases if c.get("kind") == "same_action"]
    claim = [c for c in cases if c["rule_id"] == "CLAIM-SNRNP200-BRIGHT-LIGHT"]
    fake(monkeypatch, {"items": [{"item": 1, "verdict": "partially_supported", "reason": "animal models"}]})
    r = E.evaluate(same + claim)
    assert r["n"] == 1 and r["unscored"] == [c["rule_id"] for c in same]
    assert r["false_pass"] == [] and r["accuracy"] == 1.0     # blocked as expected
    assert E.leaks(same) == []

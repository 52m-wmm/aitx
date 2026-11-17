"""acceptance_step3a.compare: actions not written to the report do not decide an expectation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import acceptance_step3a as A  # noqa: E402


def _act(label, status, report=True, reqs=()):
    a = {"label": label, "action_key": f"procedure:{label}", "section": "supportive_management", "applies_to": ["b1"],
         "status_by_branch": {"b1": {"status": status, "reason": ""}},
         "requirements": [{"requirement": r, "result": "unknown", "applies_to": ["b1"]} for r in reqs]}
    if report is False:
        a["report"] = False
    return a


LED = {"branches": [{"id": "b1", "diagnosis": {"label": "primary hyperoxaluria type 1"}}],
       "actions": [_act("intravenous fluid administration", "not_applicable", report=False),
                   _act("IV fluid", "conditional", reqs=["if needed"])]}
ITEM = {"section": "supportive_management", "match": "IV fluid|intravenous fluid",
        "expect": {"status": "conditional", "unknown": ["if needed"]}}


def test_hidden_action_does_not_decide_when_a_reported_one_matches():
    r = A.compare(ITEM, LED)
    assert r["ok"] and [a["label"] for a in r["actual"]] == ["IV fluid"]


def test_hidden_action_still_counts_when_it_is_the_only_match():
    led = dict(LED, actions=[LED["actions"][0]])
    r = A.compare(ITEM, led)                      # reverse check: nothing reported matches -> the hidden one fails it
    assert not r["ok"] and "not_applicable" in r["problem"]


def test_reported_expectation_rejects_a_hidden_conditional_action():
    item = dict(ITEM, expect={"status": "conditional", "reported": True})
    a = _act("IV fluid", "conditional", report=False)
    assert "hidden from the report" in A.compare(item, dict(LED, actions=[a]))["problem"]
    a.pop("report")
    assert A.compare(item, dict(LED, actions=[a]))["ok"]


# --- supportive fallback-chain expectations (2026-11-05)

def _led_tier(tier="symptomatic", lit=None, actions=(), disabled=("developmental_delay_intellectual_disability",)):
    return {"branches": [{"id": "b1", "diagnosis": {"label": "SLC35A2-congenital disorder of glycosylation"}}],
            "supportive_tiers": {"b1": {"tier": tier, "literature": lit if lit is not None else {"count": 4, "query": "q"},
                                        "symptomatic": {"disabled": list(disabled)}}},
            "actions": list(actions)}


TIER_ITEM = {"expect": {"tier": {"tier": "symptomatic", "literature_searched": True, "no_literature_actions": True}}}
DIS_ITEM = {"expect": {"tier": {"disabled_category": "developmental_delay_intellectual_disability", "disabled_hpo": ["HP:0001263"]}}}


def test_tier_expectation_holds_and_its_reverse_cases_fail():
    assert A.compare(TIER_ITEM, _led_tier())["ok"]
    assert not A.compare(TIER_ITEM, _led_tier(tier="literature"))["ok"]
    assert not A.compare(TIER_ITEM, _led_tier(lit={"error": "HTTP 500"}))["ok"]                 # not searched
    lit_act = {"label": "D-galactose", "tier_source": "literature", "applies_to": ["b1"], "section": "supportive_management"}
    assert not A.compare(TIER_ITEM, _led_tier(actions=[lit_act]))["ok"]


def test_disabled_category_expectation():
    assert A.compare(DIS_ITEM, _led_tier())["ok"]
    assert not A.compare(DIS_ITEM, _led_tier(disabled=()))["ok"]
    made = {"label": "early intervention", "tier_source": "symptomatic", "applies_to": ["b1"], "section": "supportive_management",
            "for_symptom": {"hpo_id": "HP:0001263", "label": "Global developmental delay"}}
    assert not A.compare(DIS_ITEM, _led_tier(actions=[made]))["ok"]                             # an action anyway: fails


def test_absent_and_tier_source_expectations():
    gal = {"label": "D-galactose supplementation", "action_key": "drug:galactose", "section": "supportive_management",
           "applies_to": ["b1"], "status_by_branch": {"b1": {"status": "conditional", "reason": ""}}, "requirements": []}
    item = {"section": "supportive_management", "match": "galactose", "expect": {"status": "absent"}}
    assert A.compare(item, _led_tier())["ok"]
    assert not A.compare(item, _led_tier(actions=[gal]))["ok"]
    l4 = {**gal, "label": "individualised antiseizure medication treatment strategy", "tier_source": "symptomatic",
          "for_symptom": {"label": "Seizure"}, "status_by_branch": {"b1": {"status": "applicable", "reason": ""}}}
    want = {"section": "supportive_management", "match": "individualised antiseizure",
            "expect": {"status": "applicable", "tier_source": "symptomatic", "for_symptom": "seizure"}}
    assert A.compare(want, _led_tier(actions=[l4]))["ok"]
    assert not A.compare(want, _led_tier(actions=[{**l4, "tier_source": "literature"}]))["ok"]

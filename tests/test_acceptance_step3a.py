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

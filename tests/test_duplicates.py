"""Fix plan N3 + N4 (2026-11-11): one action written twice - across sections (flagged) or across diagnosis branches
(merged when the precedents agree)."""
from aitx.evidence import ledger as LG
from aitx.evidence import offlabel as O


def _ev(eid, src):
    return {eid: {"id": eid, "source": {"type": "nbk", "id": src}}}


def _act(section, label, key, evs):
    return {"section": section, "label": label, "action_key": key, "evidence_ids": evs}


def test_reworded_action_in_two_sections_from_one_source_is_flagged():         # SNRNP200 sunglasses
    ev = {**_ev("e1", "NBK1417"), **_ev("e2", "NBK1417")}
    acts = [_act("contraindications_precautions", "UV-blocking sunglasses", "k1", ["e1"]),
            _act("supportive_management", "UV-A and UV-B blocking sunglasses", "k2", ["e2"])]
    got = LG.possible_duplicates(acts, ev)
    assert len(got) == 1 and "one label within the other" in got[0]["why"]


def test_same_action_key_in_two_sections_is_flagged():
    acts = [_act("supportive_management", "valproate", "drug:rxcui:11118", []),
            _act("contraindications_precautions", "valproic acid", "drug:rxcui:11118", [])]
    assert LG.possible_duplicates(acts, {})[0]["why"] == "same action key"


def test_reverse_different_actions_or_sources_are_not_flagged():
    ev = {**_ev("e1", "NBK1417"), **_ev("e2", "NBK9999"), **_ev("e3", "NBK1417")}
    acts = [_act("contraindications_precautions", "UV-blocking sunglasses", "k1", ["e1"]),
            _act("supportive_management", "UV-A and UV-B blocking sunglasses", "k2", ["e2"]),   # other source
            _act("supportive_management", "hearing aids", "k3", ["e3"])]                       # other action
    assert LG.possible_duplicates(acts, ev) == []
    same_section = [_act("supportive_management", "hearing aids", "k1", ["e1"]),
                    _act("supportive_management", "cochlear implants", "k1", ["e3"])]
    assert LG.possible_duplicates(same_section, ev) == []          # within a section: the merge step's job


class _Led:
    def __init__(self, actions):
        self.actions, self.possible_duplicates = actions, []


def _offlabel(label, branch, prec):
    line = LG.requirement("r1", "other", "x", "e1", {"field": "f", "value": None, "quote": None, "step": None},
                          "unknown", [branch])
    return {"section": O.SECTION, "label": label, "action_key": "drug:rxcui:6902", "applies_to": [branch],
            "status_by_branch": {branch: {"status": "conditional", "reason": "r"}}, "requirements": [line],
            "evidence_ids": [f"e-{branch}"], "precedents": prec}


def test_one_drug_on_two_branches_with_the_same_precedent_is_merged():          # SFTPC methylprednisolone
    p = [{"pmid": "33179299", "direction": "positive", "subject": "same"}]
    led = _Led([_offlabel("Methylprednisolone", "B1", p), _offlabel("methylprednisolone", "B2", p)])
    O.merge_branches(led)
    assert len(led.actions) == 1
    a = led.actions[0]
    assert a["applies_to"] == ["B1", "B2"] and set(a["status_by_branch"]) == {"B1", "B2"}
    assert [r["id"] for r in a["requirements"]] == ["r1", "r2"] and led.possible_duplicates == []


def test_reverse_branches_that_read_the_precedent_differently_stay_apart_and_are_flagged():   # GRIN2B memantine
    led = _Led([_offlabel("memantine", "B1", [{"pmid": "41489401", "direction": "not_reported", "subject": "same"}]),
                _offlabel("memantine", "B2", [{"pmid": "41489401", "direction": "mixed", "subject": "same"}])])
    O.merge_branches(led)
    assert len(led.actions) == 2 and led.actions[0]["same_action_other_branches"] == ["B2"]
    assert led.possible_duplicates[0]["kind"] == "cross_branch"

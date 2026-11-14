"""3b: a subtype is also searched by its parent disease's name (user decision 2026-11-12, RETEST-PFN1 ALS18)."""
from aitx.evidence import trials as T


def test_a_numbered_subtype_adds_its_parent():
    assert T.parent_names("amyotrophic lateral sclerosis type 18",
                          [("MONDO:0004976", "amyotrophic lateral sclerosis")]) == ["amyotrophic lateral sclerosis"]
    assert T.parent_names("retinitis pigmentosa 33", [("MONDO:0019200", "retinitis pigmentosa")]) == ["retinitis pigmentosa"]


def test_reverse_a_broad_grouping_or_the_same_name_is_not_added():
    assert T.parent_names("amyotrophic lateral sclerosis type 18",
                          [("MONDO:1", "motor neuron disease"), ("MONDO:2", "amyotrophic lateral sclerosis type 18")]) == []
    assert T.parent_names("Jalili syndrome", [("MONDO:3", "cone-rod dystrophy")]) == []


def test_the_parent_name_is_searched_and_recorded(monkeypatch):
    from aitx.evidence import trial_records as TR
    seen = {}

    def plan(names, gene, age, sex, use_cache=True):
        seen["names"] = names
        return {"names": names, "gene": gene, "searches": [], "n_unique": 0, "analysed": [], "over_cap": [],
                "ineligible": [], "excluded": [], "n_closed_relevant": 0, "closed_listed": []}
    monkeypatch.setattr(TR.T, "plan_branch", plan)
    monkeypatch.setattr(TR.L, "mondo_parents", lambda mid, use_cache=True:
                        [("MONDO:0004976", "amyotrophic lateral sclerosis")] if mid == "MONDO:0013891" else [])
    monkeypatch.setattr(TR.E, "facts", lambda s1, s2: {"age_months": None, "sex": None})
    monkeypatch.setattr(TR.E, "disease_names", lambda b, s2: ["amyotrophic lateral sclerosis type 18", "ALS18"])
    from aitx.evidence import ledger as LG
    led = LG.Ledger("P", [{"id": "MONDO:0013891", "gene": "PFN1",
                           "diagnosis": {"label": "amyotrophic lateral sclerosis type 18"}}])
    led.patient_context["extra_facts"] = {"facts": []}
    TR.add_trials(led, {"id": "P"}, {}, {})
    assert seen["names"][:2] == ["amyotrophic lateral sclerosis type 18", "amyotrophic lateral sclerosis"]
    assert led.trial_searches["MONDO:0013891"]["parent_names"] == ["amyotrophic lateral sclerosis"]


def test_an_inheritance_word_in_between_is_ignored_and_ancestors_are_walked():
    # MONDO: ALS18 -> familial amyotrophic lateral sclerosis -> amyotrophic lateral sclerosis (2026-11-13)
    tree = {"MONDO:0013891": [("MONDO:0005144", "familial amyotrophic lateral sclerosis")],
            "MONDO:0005144": [("MONDO:0004976", "amyotrophic lateral sclerosis")],
            "MONDO:0004976": [("MONDO:0020128", "motor neuron disease")]}
    up = T.ancestors_up("MONDO:0013891", lambda m: tree.get(m, []))
    assert [i for i, _ in up] == ["MONDO:0005144", "MONDO:0004976", "MONDO:0020128"]
    assert T.parent_names("amyotrophic lateral sclerosis type 18", up) == [
        "familial amyotrophic lateral sclerosis", "amyotrophic lateral sclerosis"]


def test_reverse_the_walk_stops_after_three_levels():
    chain = {f"M{i}": [(f"M{i + 1}", f"x{i + 1}")] for i in range(10)}
    assert len(T.ancestors_up("M0", lambda m: chain.get(m, []))) == 3

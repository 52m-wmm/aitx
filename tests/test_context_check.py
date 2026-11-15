"""Context check (fix plan, 2026-11-11): answers in, requirement lines / precedent fields out. Offline: fake LLM.

Cases are the blind-test mistakes (docs/clinical_reading_rules.md), each with a reverse case that must not change.
"""
import json

import pytest

from aitx.evidence import context_check as CC
from aitx.evidence import ledger as LG


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setattr(CC, "ENABLED", True)


def fake_llm(monkeypatch, *answer_sets):
    """answer_sets[k] is what judgement k returns; one set is repeated for every judgement."""
    seen = []

    def chat(messages, k, use_cache, prompt_version=None, call_params=None):
        seen.append({"messages": messages, "version": prompt_version, "params": call_params})
        a = answer_sets[k if len(answer_sets) > 1 else 0]
        return {"content": json.dumps({"answers": a}), "served_model": "fake"}
    monkeypatch.setattr(CC.X, "_cached_chat", chat)
    return seen


def answers(**by_q):
    return [{"q": q, "answer": a, "quote": quote, "reason": "r"} for q, (a, quote) in by_q.items()]


def line(rid, text, result, step=None, field="other"):
    status = {"pass": "satisfies", "unknown": "unknown", "fail": "does_not_satisfy"}[result]
    fact = {"field": field, "value": "x" if step else None, "quote": "x" if step else None, "step": step}
    return LG.requirement(rid, "other", text, "ev1", fact, status, ["B"])


# --- combining judgements

@pytest.mark.parametrize("given,want", [
    (["yes", "yes", "yes"], "yes"), (["yes", "no", "yes"], "split"), (["yes", None, "yes"], "split"), ([], "split")])
def test_only_unanimous_answers_count(given, want):
    assert CC.combine(given) == want


def test_ask_keeps_only_verbatim_quotes_and_sends_the_whole_passage(monkeypatch):
    seen = fake_llm(monkeypatch, answers(**{"1": ("yes", "in animal models"), "2": ("no", "not in the passage")}))
    qs = [{"id": "a", "text": "A?", "allowed": CC.YES_NO}, {"id": "b", "text": "B?", "allowed": CC.YES_NO}]
    res = CC.ask("GeneReviews NBK1", "Light harms retinas in animal models of RP.", "Diagnosis: RP", qs)
    assert [q["final"] for q in res["questions"]] == ["yes", "no"]
    assert res["questions"][0]["quotes"] == ["in animal models"] and res["questions"][1]["quotes"] == []
    user = seen[0]["messages"][1]["content"]
    assert "Light harms retinas" in user and "Diagnosis: RP" in user and seen[0]["version"] == CC.PROMPT_VERSION
    assert len(seen) == CC.N_CHECKS


def test_an_answer_outside_the_allowed_list_counts_as_missing(monkeypatch):
    fake_llm(monkeypatch, answers(**{"1": ("maybe", "")}))
    res = CC.ask("h", "p", "pt", [{"id": "a", "text": "A?", "allowed": CC.YES_NO}])
    assert res["questions"][0]["final"] == "split"


# --- 3a decisions

def _res(**finals):
    return {"questions": [{"id": k, "final": v[0] if isinstance(v, tuple) else v,
                           "answers": [v[0] if isinstance(v, tuple) else v] * 3,
                           "quotes": [v[1]] if isinstance(v, tuple) else [], **({"line": k.split(":")[1]} if ":" in k else {})}
                          for k, v in finals.items()], "n_checks": 3}


def test_reverse_nothing_changes_when_every_answer_confirms():
    lines = [line("r1", "seizures", "pass", step=2)]
    out, notes = CC.decide_3a(_res(subject="yes", limit="no", **{"meets:r1": "yes"}), lines, "ev1", "p", ["B"])
    assert out == lines and notes == [] and LG.status_of(out, "B")[0] == "applicable"


def test_animal_model_evidence_makes_the_entry_conditional():          # R3 / S5: avoid bright light
    for ev in ("animals_or_cells", "other_gene_or_subtype_patients"):
        out, notes = CC.decide_3a(_res(subject="yes", evidence=ev, limit="no"), [], "ev1", "p", ["B"])
        assert LG.status_of(out, "B")[0] == "conditional" and out[0]["context_check"] == "scope"


def test_reverse_evidence_from_this_disease_or_not_stated_changes_nothing():
    for ev in ("this_disease_patients", "not_stated"):
        out, _ = CC.decide_3a(_res(subject="yes", evidence=ev, limit="no"), [], "ev1", "p", ["B"])
        assert out == []


def test_the_limit_question_is_about_the_entrys_own_words():
    qs = CC.questions_3a("supportive_management", "surgery", "CMT", [], "Surgery is sometimes required for hip dysplasia")
    lim = next(q for q in qs if q["id"] == "limit")
    assert "Surgery is sometimes required for hip dysplasia" in lim["text"]


def test_reverse_clinical_advice_not_said_to_be_animal_only_is_unchanged():
    """Trial run 2026-11-11: "rests on human findings?" got "not stated" for GeneReviews therapy referrals."""
    res = _res(subject="yes", limit="no")
    res["questions"].append({"id": "evidence", "final": "split",
                             "answers": ["this_disease_patients", "not_stated", "animals_or_cells"], "quotes": []})
    out, _ = CC.decide_3a(res, [], "ev1", "p", ["B"])
    assert out == []


def test_reverse_a_split_limit_is_not_added():
    """Trial run 2026-11-11: a 2-of-3 split had made "In the US" a patient limit."""
    passage = "In the US, developmental preschool through the local public school district is recommended."
    res = _res(subject="yes")
    res["questions"].append({"id": "limit", "final": "split", "answers": ["yes", "no", "yes"], "quotes": ["In the US"]})
    out, _ = CC.decide_3a(res, [], "ev1", passage, ["B"])
    assert out == []


def test_another_disease_or_not_stated_makes_the_entry_conditional():
    for subj in ("no", "not_stated", "split"):
        out, _ = CC.decide_3a(_res(subject=subj, limit="no"), [], "ev1", "p", ["B"])
        assert LG.status_of(out, "B")[0] == "conditional"


def test_an_exemption_no_longer_decides_the_avoidance():               # R5 / S3: valproic acid
    lines = [line("r1", "exceptional circumstances", "unknown")]
    assert LG.status_of(lines, "B")[0] == "conditional"
    out, _ = CC.decide_3a(_res(subject="yes", limit="no", **{"exemption:r1": "yes"}), lines, "ev1", "p", ["B"])
    assert out[0]["context_check"] == "exemption" and out[0]["result"] == "not_assessed"
    assert LG.status_of(out, "B")[0] == "applicable"


def test_reverse_a_split_exemption_keeps_the_condition():
    lines = [line("r1", "exceptional circumstances", "unknown")]
    out, _ = CC.decide_3a(_res(subject="yes", limit="no", **{"exemption:r1": "split"}), lines, "ev1", "p", ["B"])
    assert out == lines


def test_a_degree_the_patient_was_not_shown_to_reach_becomes_unknown():  # R6 / S7: sodium bicarbonate
    lines = [line("r1", "significant acidosis", "pass", step=2)]
    out, _ = CC.decide_3a(_res(subject="yes", limit="no", **{"meets:r1": "no"}), lines, "ev1", "p", ["B"])
    assert out[0]["result"] == "unknown" and out[0]["context_check"] == "degree"
    assert LG.status_of(out, "B")[0] == "conditional"


def test_a_limit_is_kept_only_when_quoted_from_the_passage():          # R9 / S6: milder form
    passage = "Some patients with a milder form of ACDMPV may be candidates for lung transplantation."
    out, _ = CC.decide_3a(_res(subject="yes", limit=("yes", "a milder form of ACDMPV")), [], "ev1", passage, ["B"])
    assert out[0]["requirement"] == "a milder form of ACDMPV" and out[0]["context_check"] == "limit"
    out, _ = CC.decide_3a(_res(subject="yes", limit=("yes", "severe disease")), [], "ev1", passage, ["B"])
    assert out == []


def test_questions_ask_polarity_only_for_avoidances_and_degree_only_for_patient_matches():
    lines = [line("r1", "exceptional circumstances", "unknown"), line("r2", "seizures", "pass", step=2)]
    ids = [q["id"] for q in CC.questions_3a("contraindications_precautions", "valproic acid", "MDDS", lines)]
    assert "exemption:r1" in ids and "meets:r2" in ids and "exemption:r2" not in ids
    ids = [q["id"] for q in CC.questions_3a("supportive_management", "laxatives", "MDDS", lines)]
    assert not any(i.startswith("exemption:") for i in ids)


# --- 3c decisions

def _res3c(disease, purpose, harm, direction, gene="yes"):
    q = lambda i, v, quote=None: {"id": i, "final": v, "answers": [v] * 3, "quotes": [quote] if quote else []}
    return {"questions": [q("disease", disease, "two of these patients"), q("gene", gene, "GEMIN5"),
                          q("purpose", purpose), q("harm", harm), q("direction", direction, "improved")]}


def test_an_adverse_report_is_not_a_treatment_precedent():              # R4 / S4: voriconazole
    d = CC.decide_3c(_res3c("yes", "no", "yes", "worsened"))
    assert d["treatment"] is False and d["adverse"] is True


def test_reverse_side_effects_during_treatment_keep_the_precedent():
    """Trial run 2026-11-11: L-serine and memantine were dropped for "irritability", "rare adverse events (3/15)"."""
    d = CC.decide_3c(_res3c("yes", "yes", "yes", "improved"))
    assert d["treatment"] is True and d["adverse"] is False and d["side_effects"] is True


def test_a_reported_improvement_with_the_patients_identified_is_positive():  # R7 / S1: GEMIN5 coenzyme Q10
    d = CC.decide_3c(_res3c("yes", "yes", "no", "improved"))
    assert d["treatment"] and d["subject"] == "same" and d["direction"] == "positive"


def test_a_precedent_whose_patients_gene_is_not_stated_is_marked():    # R3: idebenone
    """Validation 2026-11-11: "a patient with Leigh syndrome" matches the disease; the gene question is separate."""
    assert CC.decide_3c(_res3c("yes", "yes", "no", "improved", gene="not_stated"))["subject"] == "not_stated"
    assert CC.decide_3c(_res3c("yes", "yes", "no", "improved", gene="other_gene"))["subject"] == "other"   # sildenafil
    assert CC.decide_3c(_res3c("no", "yes", "no", "improved"))["subject"] == "other"
    assert CC.decide_3c(_res3c("not_stated", "yes", "no", "improved"))["subject"] == "not_stated"


def test_disease_and_gene_are_asked_apart():
    ids = [q["id"] for q in CC.questions_3c("idebenone", "Leigh syndrome", "LRPPRC")]
    assert ids[:2] == ["disease", "gene"]
    assert "gene" not in [q["id"] for q in CC.questions_3c("x", "D", None)]


def test_a_single_mixed_report_is_a_partial_improvement_not_a_conflict():
    """Validation 2026-11-11: GEMIN5 coenzyme Q10 "neurological improvements, although MRI abnormalities remained"."""
    from aitx.evidence import offlabel as O
    d = CC.decide_3c(_res3c("yes", "yes", "no", "mixed"))
    assert d["direction"] == "mixed" and O.aggregate([d["direction"]]) == "partial_improvement"
    c = O.conclusion("partial_improvement", ["mixed"], ["neurological improvements"])
    assert "Improvement has been reported in neurological improvements" in c and "conflict" not in c


def test_a_split_direction_is_not_reported():
    assert CC.decide_3c(_res3c("yes", "yes", "no", "split"))["direction"] == "not_reported"


def test_reverse_a_split_purpose_is_not_a_treatment_precedent():
    assert CC.decide_3c(_res3c("yes", "split", "no", "improved"))["treatment"] is False


# --- the ledger accepts context-check lines and only them

def _ledger_with(req, passage="Some patients with a milder form may be candidates."):
    led = LG.Ledger("T", [{"id": "B", "gene": "G", "diagnosis": {"label": "D"}}])
    ev = led.add(LG.sourced("claim", "supportive_management", ["B"], {"type": "pmid", "id": "123", "url": "u"},
                            "may be candidates", passage, 1))
    req = dict(req, requirement_evidence=ev["id"])
    rec = LG.action_record("k", "supportive_management", "x", ["B"], [req], [ev["id"]], {"B": "r"})
    rec["context_check"] = {"passage": passage}
    led.actions.append(rec)
    return led


def _cc_line(kind, text, status="unknown"):
    l = LG.requirement("r1", "other", text, "e", {"field": "source scope", "value": None, "quote": None, "step": None},
                       status, ["B"], "context check: why")
    l["context_check"] = kind
    return l


@pytest.mark.parametrize("kind,text,ok", [
    ("scope", "the source passage concerns this patient's disease", True),
    ("limit", "a milder form", True),
    ("limit", "a severe form", False),                 # not in the passage
    ("bogus", "x", False),
])
def test_ledger_rules_for_context_check_lines(kind, text, ok):
    probs = _ledger_with(_cc_line(kind, text))._action_problems()
    assert (probs == []) is ok, probs


def test_reverse_an_ordinary_line_still_needs_a_verbatim_quote():
    l = LG.requirement("r1", "other", "a milder form", "e", {"field": "x", "value": None, "quote": None, "step": None},
                       "unknown", ["B"], "")
    assert any("not verbatim" in p for p in _ledger_with(l)._action_problems())


# --- the prompt carries principles, never the regression set's examples

def test_no_test_case_material_in_the_prompt():
    from pathlib import Path
    cases = json.loads((Path(__file__).resolve().parents[1] / "data/eval/support_check_regression.json").read_text())["cases"]
    for c in cases:
        assert c["gene"] not in CC.SYSTEM
        for q in (c.get("claim") or {}).get("quotes", []) + [s["quote"] for s in (c.get("rule") or {}).get("sources", [])]:
            assert q[:40] not in CC.SYSTEM
    for word in ("valpro", "voriconazole", "coenzyme", "bright light", "acidosis", "GEMIN5", "rhodopsin"):
        assert word.lower() not in CC.SYSTEM.lower()



def test_the_check_runs_with_low_reasoning_effort(monkeypatch):
    seen = fake_llm(monkeypatch, answers(**{"1": ("yes", "")}))
    CC.ask("h", "p", "pt", [{"id": "a", "text": "A?", "allowed": CC.YES_NO}])
    assert seen[0]["params"]["reasoning_effort"] == "low" and seen[0]["params"]["response_format"]["type"] == "json_object"


def test_cache_entries_with_other_parameters_are_not_reused():
    from aitx.disease import extract as X
    low = CC.CALL_PARAMS
    assert X._cache_usable({"call_params": low, "served_model": "m"}, {"expect_model_prefix": ""}, low)
    assert not X._cache_usable({"call_params": X.CALL_PARAMS, "served_model": "m"}, {"expect_model_prefix": ""}, low)
    assert not X._cache_usable({"call_params": low, "served_model": "m"}, {"expect_model_prefix": ""})   # default callers
    assert X._cache_usable({"call_params": X.retry_params(low), "served_model": "m"}, {"expect_model_prefix": ""}, low)


# --- limit follow-up (fix 2026-11-12): is the limit the patient's own row or genotype?

def test_limit_followup_yes_keeps_the_limit_as_a_note():
    passage = "Approved for persons heterozygous for variant A & a minimal function variant."
    asked = []
    out, notes = CC.decide_3a(_res(subject="yes", limit=("yes", "heterozygous for variant A")), [], "ev1", passage,
                              ["B"], limit_followup=lambda q: asked.append(q) or "yes")
    assert out == [] and asked == ["heterozygous for variant A"] and "own row" in notes[-1]


@pytest.mark.parametrize("answer", ["no", "not_stated", "split"])
def test_reverse_limit_followup_otherwise_adds_the_limit(answer):
    passage = "Approved for persons heterozygous for variant A & a minimal function variant."
    out, _ = CC.decide_3a(_res(subject="yes", limit=("yes", "heterozygous for variant A")), [], "ev1", passage, ["B"],
                          limit_followup=lambda q: answer)
    assert [l["context_check"] for l in out] == ["limit"]


def test_limit_followup_is_not_asked_without_a_limit():
    asked = []
    CC.decide_3a(_res(subject="yes", limit=("no", "")), [], "ev1", "Some passage.", ["B"],
                 limit_followup=lambda q: asked.append(q) or "yes")
    assert asked == []


def test_limit_followup_question_names_no_test_material():
    text = CC.questions_limit("drug X", "limit words")[0]["text"].lower()
    for word in ("phe508del", "cftr", "elexacaftor", "minimal function"):
        assert word not in text


# --- recommendation question (user decision 2026-11-12, reading rule R15)

def _rec(*answers):
    return {"questions": [{"id": "recommendation", "answers": list(answers), "final": CC.combine(list(answers))}]}


def test_describing_use_or_reporting_no_benefit_is_not_a_recommendation():
    assert CC.not_recommended(_rec("describes_use", "describes_use", "describes_use"))
    assert CC.not_recommended(_rec("reports_ineffective", "describes_use", "reports_ineffective"))


@pytest.mark.parametrize("answers", [("recommends",) * 3, ("describes_use", "recommends", "describes_use"),
                                     ("describes_use", None, "describes_use"), ("not_stated",) * 3, ()])
def test_reverse_anything_short_of_unanimous_non_recommendation_keeps_the_entry(answers):
    assert not CC.not_recommended(_rec(*answers))


def test_the_recommendation_question_names_no_test_material():
    text = CC.questions_recommendation("drug X", "disease Y")[0]["text"].lower()
    for word in ("als", "amyotrophic", "supplement", "vitamin", "cochrane", "antioxidant"):
        assert word not in text.split() and word not in text


# --- three-tier reason (user decision 2026-11-15: EIF2B1 corticosteroids "used with inconsistent results")

def test_unanimous_no_benefit_without_inconsistency_wording_is_reports_ineffective():
    r = _rec("reports_ineffective", "reports_ineffective", "reports_ineffective")
    assert CC.not_recommended_reason(r, "Antioxidants showed no significant differences.") == "reports_ineffective"


@pytest.mark.parametrize("answers,passage", [
    (("reports_ineffective",) * 3, "Corticosteroids have been used with inconsistent results in acute situations."),
    (("describes_use", "reports_ineffective", "reports_ineffective"), "People commonly take X."),
    (("describes_use",) * 3, "People commonly take X."),
])
def test_otherwise_the_reason_is_described_use(answers, passage):
    assert CC.not_recommended_reason(_rec(*answers), passage) == "describes_use"

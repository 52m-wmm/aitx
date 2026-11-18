"""Step 3a: code-side comparisons (contract docs/step3a_contract.md). Offline."""
import pytest

from aitx.evidence import actions as A
from aitx.evidence import established as E
from aitx.evidence import variants as V

PF = {"age_months": 84, "age_quote": "7-year-old", "sex": "male", "sex_quote": "boy",
      "variants": [{"gene": "AGXT", "protein": "p.(Lys12GlnfsTer156)", "class": "frameshift", "zygosity": "homozygous",
                    "quote": "AGXT c.33dup"}], "present": [], "excluded": []}
BR = {"id": "M:PH1", "gene": "AGXT", "diagnosis": {"label": "primary hyperoxaluria type 1"}, "synonyms": ["PH1"]}


@pytest.mark.parametrize("op,value,unit,want", [
    (">=", 2, "year", "satisfies"),          # Rivfloza: "children 2 years of age and older"
    (">=", 9, "year", "does_not_satisfy"),
    ("<", 18, "year", "satisfies"),
    (">=", 6, "month", "satisfies"),
])
def test_age_requirements(op, value, unit, want):
    st, fact, _ = E.evaluate({"field": "age", "op": op, "value": value, "unit": unit, "text": "x"}, PF, BR)
    assert st == want and fact["quote"] == "7-year-old"


def test_unknown_age_and_lab_values_are_unknown():
    pf = dict(PF, age_months=None)
    assert E.evaluate({"field": "age", "op": ">=", "value": 2, "unit": "year", "text": "x"}, pf, BR)[0] == "unknown"
    assert E.evaluate({"field": "kidney_function", "op": ">=", "value": 30, "text": "eGFR ≥30"}, PF, BR)[0] == "unknown"


def test_variant_class_requirement_frameshift_is_not_missense():
    # GeneReviews PH1 table 7: pyridoxine for "Persons w/missense AGXT variants"
    st, _, _ = E.evaluate({"field": "variant_class", "op": "in", "value": ["missense"], "text": "missense AGXT variants"}, PF, BR)
    assert st == "does_not_satisfy"
    pf = dict(PF, variants=[dict(PF["variants"][0], protein="p.(Gly170Arg)", **{"class": "missense"})])
    assert E.evaluate({"field": "variant_class", "op": "in", "value": ["missense"], "text": "missense"}, pf, BR)[0] == "satisfies"


def test_variant_looked_up_only_in_the_requirement_and_the_tables_it_cites():
    pf = dict(PF, variants=[{"gene": "CFTR", "protein": "p.Phe508del", "class": "inframe_deletion",
                             "zygosity": "homozygous", "quote": "CFTR c.1521_1523del"}])
    br = dict(BR, gene="CFTR")
    full = ("1 INDICATIONS ... at least one variant that is responsive (see Table 6). 14 CLINICAL STUDIES Trial 1 enrolled "
            "patients homozygous for F508del. Table 6: List of CFTR Gene Variants Responsive to TRIKAFTA F508del G551D "
            "R117H Table 7: Adverse reactions")
    text = "at least one variant that is responsive (see Table 6)"
    req = {"field": "variant", "text": text, "_label_tables": E.label_tables(full, text)}
    st, _, note = E.evaluate(req, pf, br)
    assert st == "satisfies" and "Table 6" in note
    # 2026-11-04 regression: Kalydeco names F508del only in its trial descriptions; the whole label is never searched
    full2 = "Trial 3 enrolled patients homozygous for F508del. Table 6: G551D R117H Table 7: other F508del"
    req = {"field": "variant", "text": text, "_label_tables": E.label_tables(full2, text)}
    assert E.evaluate(req, pf, br)[0] == "unknown"
    req = {"field": "variant", "text": "responsive to ivacaftor based on clinical data [see Clinical Pharmacology]"}
    assert E.evaluate(req, pf, br)[0] == "unknown"


@pytest.mark.parametrize("text,zyg,want", [
    # GeneReviews ETI row: the homozygous patient may qualify by the second alternative -> unknown, not unmet
    ("heterozygous for p.Phe508del & a minimal function variant or other known responsive PV", "homozygous", "unknown"),
    ("homozygous for p.Phe508del or heterozygous for p.Phe508del & a residual function variant", "homozygous", "satisfies"),
    ("homozygous for p.Phe508del or hemizygous for p.Phe508del", "heterozygous", "does_not_satisfy"),
    # a part naming another variant cannot be judged from the case -> unknown, never unmet
    ("homozygous for p.Phe508del or homozygous for p.Gly551Asp", "heterozygous", "unknown"),
])
def test_or_in_a_requirement_is_alternatives(text, zyg, want):
    st, _, note = E.evaluate({"field": "variant", "text": text}, cf_pf(zyg), CF_BR)
    assert st == want and "alternatives" in note


def test_or_older_is_not_split():
    assert E.or_parts("children 2 years of age or older") == ["children 2 years of age or older"]


def test_diagnosis_requirement_by_name_or_synonym():
    assert E.evaluate({"field": "diagnosis", "text": "patients with PH1 and preserved kidney function"}, PF, BR)[0] == "satisfies"


@pytest.mark.parametrize("protein,text,hit", [
    ("p.Phe508del", "homozygous for the F508del mutation", "F508del"),
    ("p.(Gly170Arg)", "esp homozygotes for p.Phe152Ile, p.Gly170Arg, & p.Ile244Thr", "p.Gly170Arg"),
    ("p.Gly170Arg", "G170R carriers", "G170R"),
    ("p.Gly170Arg", "G170RX", None),
])
def test_variant_aliases(protein, text, hit):
    assert V.mentioned(protein, text) == hit


@pytest.mark.parametrize("sex,age_months,want", [
    ("male", 300, "does_not_satisfy"),          # male -> not applicable
    ("female", 84, "does_not_satisfy"),         # under 12 -> not applicable
    ("unknown", 84, "does_not_satisfy"),
    ("female", 180, "unknown"),                 # female 12 or older -> conditional (pregnancy status unknown)
    ("unknown", 200, "unknown"),                # sex unknown and older than 12 -> conditional
    ("unknown", None, "unknown"),
])
def test_pregnancy_items(sex, age_months, want):
    st, fact = E.pregnancy_status(dict(PF, sex=sex, age_months=age_months))
    assert st == want and (fact["field"] == "pregnancy status") == (want == "unknown")


def test_requirements_keep_only_patient_fields():
    raw = [{"text": "children 2 years of age and older", "field": "age", "op": ">=", "value": 2, "unit": "year"},
           {"text": "throughout pregnancy", "field": "other"},
           {"text": "not in the quote", "field": "age", "op": ">=", "value": 2}]
    got = E._reqs(raw, None, "indicated in children 2 years of age and older and adults")
    assert [r["text"] for r in got] == ["children 2 years of age and older"]


# ------------------------------------------------ label matching, one section per action, dedupe, merged lines

from aitx.evidence import ledger as LG  # noqa: E402


def label(generic, indication):
    return {"generic": generic, "sections": {"indications_and_usage": indication}}


# --- label indication sentences (decision 2026-11-04)

CF = ["cystic fibrosis", "CF"]
OTC = ["ornithine carbamoyltransferase deficiency", "OTC deficiency", "ornithine transcarbamylase deficiency", "OTCD"]


@pytest.mark.parametrize("ind,names,want", [
    ("TRIKAFTA is indicated for the treatment of cystic fibrosis (CF) in patients aged 2 years and older.", CF, "targeted"),
    ("Lumasiran is indicated for the treatment of primary hyperoxaluria type 1 (PH1).", ["primary hyperoxaluria type 1"], "targeted"),
    # the diagnosis written as "deficiencies of ... <enzyme>" in the treated condition
    ("Sodium Phenylbutyrate Tablets is indicated as adjunctive therapy in the chronic management of patients with urea "
     "cycle disorders involving deficiencies of carbamylphosphate synthetase (CPS), ornithine transcarbamylase (OTC), "
     "or argininosuccinic acid synthetase (AS).", OTC, "targeted"),
    # read as supportive by the sentence rule; GeneReviews keeps nedosiran in Targeted with its own conditions
    ("RIVFLOZA is indicated to lower urinary oxalate levels in children 2 years of age and older and adults with primary "
     "hyperoxaluria type 1 (PH1) and relatively preserved kidney function.", ["primary hyperoxaluria type 1"], "supportive"),
    # a symptom or complication in patients with the diagnosis
    ("AZLI is indicated for the treatment of lung infections in patients with cystic fibrosis.", CF, "supportive"),
    ("CAYSTON is indicated to improve respiratory symptoms in cystic fibrosis (CF) patients with Pseudomonas aeruginosa.", CF, "supportive"),
    ("Phytonadione is indicated in: • hemorrhagic disease of the newborn; • hypoprothrombinemia secondary to factors "
     "limiting absorption of vitamin K, e.g., obstructive jaundice, cystic fibrosis of the pancreas.", CF, "supportive"),
    ("PULMOZYME is indicated, in conjunction with standard therapies, for the management of pediatric and adult patients "
     "with cystic fibrosis to improve pulmonary function.", CF, "supportive"),
    # not an "indicated" sentence, or negated
    ("Azithromycin is indicated for mild infections. Azithromycin is not recommended in patients with pneumonia who have "
     "risk factors such as cystic fibrosis.", CF, None),
    ("X is not indicated for the treatment of cystic fibrosis.", CF, None),
    # a short abbreviation alone is never used; the name must be whole words
    ("Y is indicated for the treatment of CF.", CF, None),
    ("Z is indicated for the treatment of cystic fibrosis-like syndromes.", ["cystic fibrosis"], "targeted"),
    ("W is indicated for the treatment of chronic hypoxanthine excess.", ["hypoxanthine excess"], "targeted"),
    ("V is indicated for vitamin B6 deficiency.", ["primary hyperoxaluria type 1", "PH1"], None),
])
def test_indication_role(ind, names, want):
    got = E.indication_role(ind, names)
    assert (got[0] if got else None) == want


def test_searchable_names_skip_short_abbreviations():
    assert [n for n in CF + OTC if E.searchable_name(n)] == ["cystic fibrosis", "ornithine carbamoyltransferase deficiency",
                                                           "OTC deficiency", "ornithine transcarbamylase deficiency"]


# --- quote repair (decision 2026-11-04)

ROW = ("Elexacaftor/tezacaftor/ivacaftor: approved for persons age ≥2 years who are heterozygous for p.Phe508del & a "
       "minimal function variant. Ivacaftor is indicated for persons with gating variants.")
ETI = "Elexacaftor/tezacaftor/ivacaftor"


def test_quote_with_a_letter_typo_is_repaired_to_the_source_span():
    q = ("Elexacaftor/tezacaftor/ivacaftor: approved for persons age ≥2 years who are heterozygous for p.Phe508el & a "
         "minimal function variant.")
    span, why = E.repair_quote(q, ROW, ETI)
    assert span is not None and "p.Phe508del" in span and LG.quote_in(span, ROW) and span.startswith(ETI)


@pytest.mark.parametrize("q", [
    # a different number: never repaired
    "Elexacaftor/tezacaftor/ivacaftor: approved for persons age ≥12 years who are heterozygous for p.Phe508del & a minimal function variant.",
    # a different comparison sign
    "Elexacaftor/tezacaftor/ivacaftor: approved for persons age ≤2 years who are heterozygous for p.Phe508del & a minimal function variant.",
])
def test_quote_with_a_different_number_or_sign_is_not_repaired(q):
    span, why = E.repair_quote(q, ROW, ETI)
    assert span is None and "differ" in why


def test_quote_that_adds_or_drops_a_negation_is_not_repaired():
    src = ("Drug X is not indicated for persons with a creatinine clearance below thirty milliliters per minute "
           "according to the label of the drug")
    q = ("Drug X is indicated for persons with a creatinine clearance below thirty milliliters per minute "
         "according to the label of the drug")
    span, why = E.repair_quote(q, src, "Drug X")
    assert span is None
    span, why = E.repair_quote(src.replace("label", "lable"), q, "Drug X")
    assert span is None


def test_quote_repair_needs_the_name_verbatim_and_high_similarity():
    assert E.repair_quote("Ivacaftor is indicated for persons with gating variants.", ROW, "lumacaftor")[0] is None
    assert E.repair_quote("Something entirely different from the row text here.", ROW, ETI)[0] is None


def test_repaired_item_extracts_conditions_again_from_the_span(monkeypatch):
    seen = {}

    def fake_llm(system, user, use_cache, what=""):
        seen["user"] = user
        return {"items": [{"name": "elexacaftor/tezacaftor/ivacaftor", "kind": "drug", "quote": "x",
                           "requirements": [{"text": "age ≥2 years", "field": "age", "op": ">=", "value": 2, "unit": "year"}]}]}, {"m": 1}
    monkeypatch.setattr(E, "_llm", fake_llm)
    it = {"name": ETI, "kind": "drug", "requirements": [{"text": "age ≥2 yeras", "field": "age"}],
          "quote": "Elexacaftor/tezacaftor/ivacaftor: approved for persons age ≥2 years who are heterozygous for p.Phe508el & a minimal function variant."}
    got = E._repaired_item(it, ETI, "Management / Targeted Therapies", ROW, True, "NBK1250")
    assert got and LG.quote_in(got["quote"], ROW) and "p.Phe508del" in seen["user"]
    assert [r["text"] for r in got["requirements"]] == ["age ≥2 years"]        # from the second extraction
    assert got["quote_repaired"]["llm_quote"] == it["quote"]


def test_repaired_item_dropped_when_requirement_words_are_not_in_the_span(monkeypatch):
    monkeypatch.setattr(E, "_llm", lambda *a, **k: ({"items": [{"name": ETI, "kind": "drug", "requirements": [
        {"text": "age ≥2 yeras", "field": "age", "op": ">=", "value": 2}]}]}, {}))
    it = {"name": ETI, "kind": "drug",
          "quote": "Elexacaftor/tezacaftor/ivacaftor: approved for persons age ≥2 years who are heterozygous for p.Phe508el & a minimal function variant."}
    assert E._repaired_item(it, ETI, "s", ROW, True, "NBK1250") is None


def _found(section, *, reqs=(), specs=None, pregnancy=False, label="pyridoxine", key="drug:rxcui:684879"):
    text = "Pyridoxine (vitamin B6) for persons w/missense AGXT variants. Also given throughout pregnancy."
    src = {"type": "nbk", "id": "NBK1283", "url": "u", "section": "Management / x", "credit": "c"}
    spec = E._spec("GeneReviews lists pyridoxine", src, "Pyridoxine (vitamin B6) for persons w/missense AGXT variants.",
                   text, 1)
    return {key: {"key": {"key": key, "normalized": True}, "section": section, "label": label, "branches": {"b1"},
                  "specs": specs or [spec], "reqs": [dict(r, spec=spec) for r in reqs], "why": "Management / x",
                  "pregnancy_only": pregnancy}}


PF_FS = dict(PF)


def test_evidence_created_in_the_actions_final_section():
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("existing_targeted_therapies"), PF_FS, [])
    ev = [e for e in led.evidence.values() if (e.get("action") or {}).get("key") == "drug:rxcui:684879"]
    assert ev and all(e["section"] == "existing_targeted_therapies" for e in ev)
    assert next(c for c in led.checks() if c["name"] == "one_action_one_section")["status"] == "pass"


def test_duplicate_requirements_kept_once_and_frameshift_fails_missense():
    r = {"kind": "label_condition", "text": "missense AGXT variants", "field": "variant_class", "op": "in", "value": ["missense"]}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("existing_targeted_therapies", reqs=[r, dict(r)]), PF_FS, [])
    a = next(a for a in led.actions if a["action_key"] == "drug:rxcui:684879")
    assert len(a["requirements"]) == 1 and a["status_by_branch"]["b1"]["status"] == "not_applicable"


def test_unreported_manifestations_merged_into_one_missing_line(monkeypatch):
    monkeypatch.setattr(E, "manifestation_status", lambda text, pf: ("unknown", None))
    reqs = [{"kind": "other", "text": "stones", "field": "manifestation"},
            {"kind": "other", "text": "oxalosis", "field": "manifestation"}]
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("supportive_management", reqs=reqs, key="procedure:ureteroscopy", label="ureteroscopy")
    found["procedure:ureteroscopy"]["specs"][0]["quote"] = "Pyridoxine (vitamin B6)"
    E._records(led, found, PF_FS, [])
    rows = [m for m in led.missing_information if m["variable"] == E.MISSING_MANIFESTATIONS]
    assert len(rows) == 1 and rows[0]["details"] == ["stones", "oxalosis"] and rows[0]["affects"] == ["ureteroscopy"]
    a = next(a for a in led.actions if a["action_key"] == "procedure:ureteroscopy")
    assert a["status_by_branch"]["b1"]["status"] == "conditional"


def test_pregnancy_item_does_not_create_an_action_or_missing_information():
    req = {"kind": "other", "text": "Pregnancy Management", "field": "pregnancy"}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("supportive_management", pregnancy=True, key="procedure:iv_fluids", label="IV fluids")
    src = found["procedure:iv_fluids"]["specs"][0]["src"]
    found["procedure:iv_fluids"]["reqs"] = [dict(req, spec=E._spec("section", src, "Pregnancy Management",
                                                                  "Management / Pregnancy Management", 1))]
    E._records(led, found, PF_FS, [])                       # PF: 7-year-old boy
    assert not [a for a in led.actions if a["action_key"] == "procedure:iv_fluids"]
    assert not led.missing_information


def test_pregnancy_passage_conditions_are_notes_for_a_drug_with_a_general_recommendation():
    # 2026-11-04 regression: "known to be pyridoxine responsive" (Pregnancy Management) made pyridoxine not
    # applicable for a homozygous p.Gly170Arg patient
    pf = dict(PF, variants=[dict(PF["variants"][0], protein="p.(Gly170Arg)", **{"class": "missense"})])
    general = {"kind": "label_condition", "text": "missense AGXT variants", "field": "variant_class", "op": "in", "value": ["missense"]}
    preg = {"kind": "label_condition", "text": "given throughout pregnancy", "field": "variant_class", "op": "in",
            "value": ["pyridoxine responsive"], "pregnancy_passage": True}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("existing_targeted_therapies", reqs=[general])
    src = found["drug:rxcui:684879"]["specs"][0]["src"]
    text = "Pyridoxine (vitamin B6) for persons w/missense AGXT variants. Also given throughout pregnancy."
    found["drug:rxcui:684879"]["reqs"].append(dict(preg, spec=E._spec("GeneReviews lists pyridoxine (pregnancy)", src,
                                                                     "Also given throughout pregnancy.", text, 1)))
    found["drug:rxcui:684879"]["specs"].append(E._spec("Pregnancy note",dict(src,section="Management / Pregnancy Management"),
                                                         "Also given throughout pregnancy.",text,1))
    E._records(led, found, pf, [])
    a = next(a for a in led.actions if a["action_key"] == "drug:rxcui:684879")
    assert a["status_by_branch"]["b1"]["status"] == "applicable"
    assert [r["requirement"] for r in a["requirements"]] == ["missense AGXT variants"]
    assert a["pregnancy_notes"] == ["Also given throughout pregnancy."]
    assert a['pregnancy_note_evidence_ids']


@pytest.mark.parametrize("subject,want", [("no", "conditional"), ("yes", "applicable")])
def test_mixed_pregnancy_source_reason_identifies_the_ordinary_scope_uncertainty(monkeypatch, subject, want):
    from aitx.evidence import context_check as CC
    monkeypatch.setattr(CC, "ENABLED", True)
    ordinary = "Physical and occupational therapy should be initiated."
    pregnancy = "Physiotherapist referral should be made to address pelvic instability and pain."
    src = {"type": "nbk", "id": "NBK1295", "url": "u", "section": "Management / Treatment of Manifestations"}
    specs = [E._spec("Ordinary physical therapy", src, ordinary, ordinary, 1),
             E._spec("Pregnancy note", dict(src, section="Management / Pregnancy Management"), pregnancy, pregnancy, 1)]
    _patch_passage(monkeypatch, lambda spec: ("Ordinary source", ordinary))

    def chat(messages, k, use_cache, **kwargs):
        rec = "Does the passage recommend or advise" in messages[-1]["content"]
        answers = [{"q": 1, "answer": "recommends", "quote": ""}] if rec else [
            {"q": 1, "answer": subject, "quote": ""},
            {"q": 2, "answer": "not_stated", "quote": ""}, {"q": 3, "answer": "no", "quote": ""}]
        return {"content": json.dumps({"answers": answers}), "served_model": "fake", "call_id": f"c{k}"}

    monkeypatch.setattr(CC.X, "_cached_chat", chat)
    found = _found("supportive_management", specs=specs, label="physiotherapist", key="therapy:physical_therapy")
    found["therapy:physical_therapy"]["branches"] = {"b1", "b2"}
    branches = [dict(BR, id=bid, diagnosis={"label": label}) for bid, label in [("b1", "diagnosis A"), ("b2", "diagnosis B")]]
    led = LG.Ledger("P", branches)
    E._records(led, found, PF_FS, [])
    a = next(a for a in led.actions if a["action_key"] == "therapy:physical_therapy")
    for branch in branches:
        state = a["status_by_branch"][branch["id"]]
        assert state["status"] == want
        if subject == "no":
            assert "GeneReviews NBK1295 (Management / Treatment of Manifestations)" in state["reason"]
            assert branch["diagnosis"]["label"] in state["reason"] and "source-scope check unknown" in state["reason"]
            assert all(r["patient_fact"]["field"] == "source scope" for r in a["requirements"])
        assert "Pregnancy Management" not in state["reason"]


def test_unrecognized_variant_class_value_is_unknown_not_unmet():
    st, _, note = E.evaluate({"field": "variant_class", "op": "in", "value": ["pyridoxine responsive"],
                              "text": "known to be pyridoxine responsive"}, PF, BR)
    assert st == "unknown" and note == "requirement not comparable"


def test_requirement_points_to_its_own_quote_when_claims_coincide():
    # 2026-11-04 regression: a manifestation item with the same claim replaced the item's evidence
    led = LG.Ledger("P", [dict(BR, id="b1")])
    src = {"type": "nbk", "id": "NBK1283", "url": "u", "section": "s", "credit": "c"}
    text = "Potassium citrate if the GFR is preserved, to reduce calcium oxalate crystallization."
    a = led.add(LG.sourced("GeneReviews lists potassium citrate", "supportive_management", ["b1"], src,
                           "Potassium citrate if the GFR is preserved", text, 1, action={"key": "k"}))
    b = led.add(LG.sourced("GeneReviews lists potassium citrate", "supportive_management", ["b1"], src,
                           "calcium oxalate crystallization", text, 1, action={"key": "k"}))
    assert a["id"] != b["id"] and led.evidence[a["id"]]["quote"] == "Potassium citrate if the GFR is preserved"
    assert led.add(dict(a))["id"] == a["id"]                 # identical content: same item
    bad = dict(a, claim="something else")
    with pytest.raises(ValueError):
        led.add(bad)


def test_label_conditions_decide_and_genereviews_conditions_become_notes():
    # 2026-11-04: GeneReviews "heterozygous for p.Phe508del & a minimal function variant" would have overruled the
    # label's "at least one F508del" for a homozygous patient
    gr = {"kind": "label_condition", "text": "missense AGXT variants", "field": "variant_class", "op": "in", "value": ["nonsense"]}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("existing_targeted_therapies", reqs=[gr])
    a = found["drug:rxcui:684879"]
    lsrc = {"type": "spl_setid", "id": "0b0e8c5a-1111-2222-3333-444455556666", "url": "u", "version": "3",
            "effective_date": "20250101", "brand": "B"}
    ltext = "B is indicated for the treatment of primary hyperoxaluria type 1 in patients 2 years and older."
    a["specs"].append(dict(E._spec("B label indicated", lsrc, ltext, ltext, 1), label_section="existing_targeted_therapies"))
    a["reqs"].append({"kind": "label_condition", "text": "2 years and older", "field": "age", "op": ">=", "value": 2,
                      "unit": "year", "spec": E._spec("B label requirement", lsrc, "2 years and older", ltext, 1)})
    E._records(led, found, PF_FS, [])                        # PF: 7-year-old
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert [r["requirement"] for r in rec["requirements"]] == ["2 years and older"]
    assert rec["status_by_branch"]["b1"]["status"] == "applicable"
    assert rec["genereviews_notes"] == ["missense AGXT variants"]


def test_without_a_label_genereviews_conditions_still_decide():
    gr = {"kind": "label_condition", "text": "missense AGXT variants", "field": "variant_class", "op": "in", "value": ["missense"]}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("existing_targeted_therapies", reqs=[gr]), PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["requirements"] and "genereviews_notes" not in rec


def test_repaired_quote_marked_on_the_evidence():
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("existing_targeted_therapies")
    found["drug:rxcui:684879"]["specs"][0]["quote_repaired"] = {"llm_quote": "Pyridoxine (vitamin B6) for persons w/misense", "check": "similarity 0.99"}
    E._records(led, found, PF_FS, [])
    ev = [x for x in led.evidence.values() if x.get("quote_repaired")]
    assert ev and ev[0]["status"] == "verified"


def test_any_label_naming_the_disease_decides_conditions_whatever_its_wording():
    # decision 2026-11-04: Rivfloza "indicated to lower urinary oxalate levels in children 2 years ... with PH1 and
    # relatively preserved kidney function" gives nedosiran's conditions; nedosiran stays Targeted (GeneReviews)
    gr = {"kind": "label_condition", "text": "missense AGXT variants", "field": "variant_class", "op": "in", "value": ["nonsense"]}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("existing_targeted_therapies", reqs=[gr])
    lsrc = {"type": "spl_setid", "id": "0b0e8c5a-1111-2222-3333-444455556666", "url": "u", "version": "3",
            "effective_date": "20250101", "brand": "RIVFLOZA"}
    ltext = ("RIVFLOZA is indicated to lower urinary oxalate levels in children 2 years of age and older and adults with "
             "primary hyperoxaluria type 1 (PH1) and relatively preserved kidney function.")
    found["drug:rxcui:684879"]["specs"].append(dict(E._spec("label", lsrc, ltext, ltext, 1), label_section="supportive_management"))
    found["drug:rxcui:684879"]["reqs"] += [
        {"kind": "label_condition", "text": "2 years of age and older", "field": "age", "op": ">=", "value": 2, "unit": "year",
         "spec": E._spec("req", lsrc, "2 years of age and older", ltext, 1)},
        {"kind": "label_condition", "text": "relatively preserved kidney function", "field": "kidney_function", "op": "", "value": "",
         "spec": E._spec("req", lsrc, "relatively preserved kidney function", ltext, 1)}]
    E._records(led, found, PF_FS, [])                        # 7-year-old, eGFR not given
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["section"] == "existing_targeted_therapies"
    assert [r["requirement"] for r in rec["requirements"]] == ["2 years of age and older", "relatively preserved kidney function"]
    assert rec["status_by_branch"]["b1"]["status"] == "conditional"
    assert rec["genereviews_notes"] == ["missense AGXT variants"]


def test_contraindication_label_supplies_no_conditions():
    gr = {"kind": "label_condition", "text": "missense AGXT variants", "field": "variant_class", "op": "in", "value": ["missense"]}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("existing_targeted_therapies", reqs=[gr])
    lsrc = {"type": "spl_setid", "id": "0b0e8c5a-1111-2222-3333-444455556666", "url": "u", "version": "3",
            "effective_date": "20250101", "brand": "B"}
    found["drug:rxcui:684879"]["specs"].append(dict(E._spec("c", lsrc, "Contraindicated in PH1.", "Contraindicated in PH1.", 1),
                                                    label_section="contraindications_precautions"))
    E._records(led, found, PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["requirements"] and "genereviews_notes" not in rec


SPEC = {"src": {"type": "nbk"}}
KEY = {"key": "drug:x", "normalized": True}


def test_new_version_chapter_decides_the_section_over_a_label():
    found = {}
    E.place(found, KEY, "supportive_management", "dornase alfa", ["b1"], SPEC, [], "Management / Treatment of Manifestations")
    E.place(found, KEY, "existing_targeted_therapies", "PULMOZYME", ["b1"], SPEC, [], "label", source="label")
    assert found["drug:x"]["section"] == "supportive_management" and len(found["drug:x"]["specs"]) == 2
    found = {}                                              # same when the label comes first
    E.place(found, KEY, "existing_targeted_therapies", "PULMOZYME", ["b1"], SPEC, [], "label", source="label")
    E.place(found, KEY, "supportive_management", "dornase alfa", ["b1"], SPEC, [], "Management / Treatment of Manifestations")
    assert found["drug:x"]["section"] == "supportive_management"


def test_old_version_chapter_label_naming_the_disease_promotes_to_targeted():
    # correction 2026-11-04: OTC chapter has no Targeted Therapies section; the sodium phenylbutyrate label treats
    # urea cycle disorders involving OTC deficiency -> targeted (old rule i)
    found = {}
    E.place(found, KEY, "supportive_management", "sodium phenylbutyrate", ["b1"], SPEC, [], "Treatment of Manifestations",
            source="gr_old")
    E.place(found, KEY, "existing_targeted_therapies", "BUPHENYL", ["b1"], SPEC, [], "label", source="label")
    assert found["drug:x"]["section"] == "existing_targeted_therapies"


def test_label_decides_the_section_only_for_an_action_genereviews_does_not_list():
    found = {}
    E.place(found, KEY, "supportive_management", "CAYSTON", ["b1"], SPEC, [], "label", source="label")
    E.place(found, KEY, "existing_targeted_therapies", "X", ["b1"], SPEC, [], "label", source="label")
    assert found["drug:x"]["section"] == "existing_targeted_therapies"
    found = {}
    E.place(found, KEY, "existing_targeted_therapies", "y", ["b1"], SPEC, [], "Targeted Therapies")
    E.place(found, KEY, "supportive_management", "y", ["b1"], SPEC, [], "Treatment of Manifestations")
    assert found["drug:x"]["section"] == "existing_targeted_therapies"     # within GeneReviews: targeted first


# --- zygosity and alternatives (decision 2026-11-04)

CF_BR = {"id": "b1", "gene": "CFTR", "diagnosis": {"label": "cystic fibrosis"}, "synonyms": []}


def cf_pf(zyg):
    return dict(PF, age_months=180, variants=[{"gene": "CFTR", "protein": "p.Phe508del", "class": "inframe_deletion",
                                                "zygosity": zyg, "quote": f"CFTR p.Phe508del ({zyg})"}])


@pytest.mark.parametrize("text,field,zyg,want", [
    ("heterozygous for p.Phe508del & a minimal function variant", "variant", "homozygous", "does_not_satisfy"),
    ("heterozygous for p.Phe508del & a minimal function variant", "variant", "heterozygous", "unknown"),
    ("homozygous for p.Phe508del", "variant", "homozygous", "satisfies"),
    ("homozygous for p.Phe508del", "zygosity", "homozygous", "satisfies"),     # value held the variant name
    ("homozygous for p.Phe508del", "zygosity", "heterozygous", "does_not_satisfy"),
    ("at least one F508del", "variant", "homozygous", "satisfies"),
    ("at least one F508del", "variant", "heterozygous", "satisfies"),
])
def test_variant_requirement_respects_zygosity(text, field, zyg, want):
    st, _, _ = E.evaluate({"field": field, "op": "in", "value": ["p.Phe508del"], "text": text}, cf_pf(zyg), CF_BR)
    assert st == want


def _rows(*rows):
    """One action with several GeneReviews rows, each its own alternative."""
    src = {"type": "nbk", "id": "NBK1250", "url": "u", "section": "Management / Targeted Therapies", "credit": "c"}
    text = " ".join(q for q, _ in rows)
    specs, reqs = [], []
    for q, rr in rows:
        sp = E._spec(f"GeneReviews lists ETI: {q[:20]}", src, q, text, 1)
        specs.append(sp)
        reqs += [dict(r, spec=E._spec("req", src, r["text"], text, 1), alternative=q) for r in rr]
    return {"drug:eti": {"key": {"key": "drug:eti", "normalized": True}, "section": "existing_targeted_therapies",
                         "label": "ETI", "branches": {"b1"}, "specs": specs, "reqs": reqs, "why": "Targeted", "pregnancy_only": False}}


HOM_ROW = ("ETI: age ≥2 yrs & homozygous for p.Phe508del",
           [{"kind": "label_condition", "text": "age ≥2 yrs", "field": "age", "op": ">=", "value": 2, "unit": "year"},
            {"kind": "label_condition", "text": "homozygous for p.Phe508del", "field": "zygosity", "op": "in", "value": ["p.Phe508del"]}])
HET_ROW = ("ETI: age ≥2 yrs & heterozygous for p.Phe508del & a minimal function variant",
           [{"kind": "label_condition", "text": "age ≥2 yrs", "field": "age", "op": ">=", "value": 2, "unit": "year"},
            {"kind": "label_condition", "text": "heterozygous for p.Phe508del & a minimal function variant", "field": "variant",
             "op": "in", "value": ["p.Phe508del"]}])


def test_any_row_met_makes_the_action_applicable_and_names_that_row():
    led = LG.Ledger("P", [CF_BR])
    E._records(led, _rows(HET_ROW, HOM_ROW), cf_pf("homozygous"), [])
    rec = next(a for a in led.actions if a["action_key"] == "drug:eti")
    assert rec["status_by_branch"]["b1"]["status"] == "applicable"
    assert "homozygous for p.Phe508del" in rec["status_by_branch"]["b1"]["reason"]
    assert {r["alternative"] for r in rec["requirements"]} == {HOM_ROW[0], HET_ROW[0]}
    assert all(c["status"] == "pass" for c in led.checks() if "action" in c["name"]), led.checks()


def test_no_row_met_is_not_applicable():
    led = LG.Ledger("P", [CF_BR])
    E._records(led, _rows(HET_ROW), cf_pf("homozygous"), [])
    rec = next(a for a in led.actions if a["action_key"] == "drug:eti")
    assert rec["status_by_branch"]["b1"]["status"] == "not_applicable"


def test_status_of_alternatives():
    line = lambda res, alt=None: {"applies_to": ["b"], "result": res, **({"alternative": alt} if alt else {})}
    assert LG.status_of([line("fail", "a"), line("pass", "b")], "b") == ("applicable", "b")
    assert LG.status_of([line("fail", "a"), line("unknown", "b")], "b") == ("conditional", "b")
    assert LG.status_of([line("fail"), line("pass", "b")], "b")[0] == "not_applicable"    # common lines apply to all
    assert LG.status_of([line("pass"), line("unknown")], "b") == ("conditional", None)


def test_label_only_supportive_action_needs_the_complication():
    led = LG.Ledger("P", [dict(BR, id="b1")])
    lsrc = {"type": "spl_setid", "id": "0b0e8c5a-1111-2222-3333-444455556666", "url": "u", "version": "3",
            "effective_date": "20250101", "brand": "Phytonadione"}
    ltext = "Phytonadione is indicated in: • hypoprothrombinemia secondary to factors limiting absorption, e.g., cystic fibrosis of the pancreas."
    sp = dict(E._spec("label", lsrc, ltext, ltext, 1), label_section="supportive_management")
    found = {"drug:k": {"key": {"key": "drug:k", "normalized": True}, "section": "supportive_management", "label": "Phytonadione",
                        "branches": {"b1"}, "specs": [sp], "reqs": [], "why": "label", "pregnancy_only": False}}
    E._records(led, found, PF_FS, [])
    rec = next(a for a in led.actions if a["action_key"] == "drug:k")
    assert rec["status_by_branch"]["b1"]["status"] == "conditional"
    assert [m["variable"] for m in led.missing_information].count(E.MISSING_MANIFESTATIONS) == 1


def _label_found(reqs, pf_section="existing_targeted_therapies"):
    found = _found(pf_section)
    a = found["drug:rxcui:684879"]
    lsrc = {"type": "spl_setid", "id": "0b0e8c5a-1111-2222-3333-444455556666", "url": "u", "version": "3",
            "effective_date": "20250101", "brand": "B"}
    ltext = " ".join(r["text"] for r in reqs)
    a["specs"].append(dict(E._spec("label", lsrc, ltext, ltext, 1), label_section="existing_targeted_therapies"))
    a["reqs"] += [dict(r, spec=E._spec("req", lsrc, r["text"], ltext, 1), alternative="B label") for r in reqs]
    return found


def test_label_conditions_outside_indications_are_precautions():
    # decision 2026-11-04: Trikafta "Should not be used in patients with severe hepatic impairment" (Dosage and
    # Administration) is a precaution: ETI stays applicable, nothing is added to the missing information
    reqs = [{"kind": "label_condition", "text": "aged 2 years and older", "field": "age", "op": ">=", "value": 2, "unit": "year",
             "label_part": "indications_and_usage"},
            {"kind": "label_condition", "text": "Should not be used in patients with severe hepatic impairment.",
             "field": "liver_function", "op": "", "value": "", "label_part": "dosage_and_administration"}]
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _label_found(reqs), PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["status_by_branch"]["b1"]["status"] == "applicable"
    assert rec["precautions"] == ["Should not be used in patients with severe hepatic impairment."]
    assert not any("liver" in m["variable"] for m in led.missing_information)


def test_precaution_the_patient_is_known_to_have_makes_it_not_applicable():
    reqs = [{"kind": "label_condition", "text": "not recommended in patients less than 10 years of age", "field": "age",
             "op": "<", "value": 10, "unit": "year", "label_part": "dosage_and_administration"}]
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _label_found(reqs), PF_FS, [])                 # PF: 7 years old
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["status_by_branch"]["b1"]["status"] == "not_applicable"
    assert all(c["status"] == "pass" for c in led.checks() if "action" in c["name"])


def test_eligibility_in_indications_still_decides():
    reqs = [{"kind": "label_condition", "text": "relatively preserved kidney function, e.g., eGFR ≥30 mL/min/1.73 m 2",
             "field": "kidney_function", "op": ">=", "value": 30, "label_part": "indications_and_usage"}]
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _label_found(reqs), PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["status_by_branch"]["b1"]["status"] == "conditional" and "precautions" not in rec


def test_omim_alias_lists_split_for_label_search():
    # 2026-11-04: openFDA answers HTTP 400 to a ";" in the phrase
    assert E.label_names(["epileptic encephalopathy, early infantile, 22; EIEE22", 'x "quoted" name', "CF"]) == \
        ["epileptic encephalopathy, early infantile, 22", "x quoted name"]


def test_single_chapter_is_still_matched_to_the_diagnoses(monkeypatch):
    # one gene, two different diseases, one GeneReviews chapter: only the covered branch gets it
    branches = [{"id": "b1", "gene": "COL1A1", "diagnosis": {"label": "osteogenesis imperfecta type 1"}},
                {"id": "b2", "gene": "COL1A1", "diagnosis": {"label": "Ehlers-Danlos syndrome, classic type"}}]
    led = LG.Ledger("P", branches)
    step2 = {"genereviews": {"COL1A1": [{"nbk": "NBK1295", "title": "COL1A1/2 Osteogenesis Imperfecta"}]}}
    seen = []

    def fake(system, user, use_cache, what=""):
        seen.append(user)
        return {"links": [{"diagnosis": 1, "chapters": [1]}, {"diagnosis": 2, "chapters": []}]}, {}
    monkeypatch.setattr(E, "_llm", fake)
    assert E.chapters_for(led, step2, True) == {"b1": ["NBK1295"], "b2": []}
    assert seen and "Ehlers-Danlos" in seen[0]                        # the LLM was asked, not skipped
    # reverse: an answer that names no chapter for either diagnosis leaves both empty
    monkeypatch.setattr(E, "_llm", lambda *a, **k: ({"links": []}, {}))
    assert E.chapters_for(led, step2, True) == {"b1": [], "b2": []}


# --- 2026-11-04 review: conditions lost, purpose clauses, usage situations, missing information by type

def test_row_cells_give_the_items_row_and_only_that_row():
    shown = ("Table 9. Treatment of Manifestations\n"
             "Row 1: [Manifestation/Concern: Kidney stones] [Treatment: Ureteroscopy] [Considerations/Other: In kidney failure]\n"
             "Row 2: [Manifestation/Concern: Oxalosis] [Treatment: Dialysis] [Considerations/Other: if needed]")
    assert E.row_cells(shown, "Ureteroscopy") == ["Kidney stones", "Ureteroscopy", "In kidney failure"]
    assert E.row_cells(shown, "Dialysis") == ["Oxalosis", "Dialysis", "if needed"]
    assert E.row_cells(shown, "Pyridoxine is given to all persons.") is None


def test_purpose_or_mechanism_clauses_are_not_requirements():
    raw = [{"text": "to reduce hepatic oxalate production", "field": "situation"},
           {"text": "which lowers urinary oxalate", "field": "situation"},
           {"text": "in kidney failure", "field": "situation"},
           {"text": "as needed", "field": "situation"}]
    where = "Dialysis in kidney failure as needed, to reduce hepatic oxalate production, which lowers urinary oxalate"
    assert [r["text"] for r in E._reqs(raw, None, where)] == ["in kidney failure", "as needed"]


def test_usage_situation_makes_it_conditional_without_comparing():
    led = LG.Ledger("P", [dict(BR, id="b1")])
    reqs = [{"kind": "other", "text": "missense AGXT variants", "field": "situation"}]
    E._records(led, _found("supportive_management", reqs=reqs), PF_FS, [])
    a = next(a for a in led.actions if a["action_key"] == "drug:rxcui:684879")
    assert a["status_by_branch"]["b1"]["status"] == "conditional"
    assert a["requirements"][0]["note"] == E.SITUATION_NOTE
    row = next(m for m in led.missing_information if m["variable"] == "usage situation")
    assert row["affects"] == ["pyridoxine"]


def test_missing_information_merged_by_variable_type():
    led = LG.Ledger("P", [dict(BR, id="b1")])
    for label in ("nedosiran", "lumasiran", "nedosiran"):
        led.note_missing("kidney function", label, f"{label}: eGFR >= 30", "3a")
    led.note_missing("kidney function", "DCR-PHXC (NCT04580420)", "eGFR < 30", "3b")
    rows = [m for m in led.missing_information if m["variable"] == "kidney function"]
    assert len(rows) == 1 and rows[0]["affects"] == ["nedosiran", "lumasiran", "DCR-PHXC (NCT04580420)"]
    assert rows[0]["asked_by"] == "3a, 3b" and rows[0]["why_it_matters"].startswith("3 actions depend on it")
    assert E.variable_type("current medication: valproate") == "current medication"
    assert E.variable_type("kidney_function") == "kidney function"


def _np(key, label, section="Management / Treatment of Manifestations", quote=None):
    src = {"type": "nbk", "id": "NBK1283", "url": "u", "section": section, "credit": "c"}
    q = quote or f"{label} is recommended."
    return {key: {"key": {"key": key, "normalized": True}, "section": "supportive_management", "label": label,
                  "branches": {"b1"}, "specs": [E._spec(f"GeneReviews lists {label}", src, q, q, 1)], "reqs": [],
                  "why": section, "pregnancy_only": False}}


def test_synonyms_merged_only_within_one_chapter_section(monkeypatch):
    found = {**_np("procedure:a", "high fluid intake"), **_np("procedure:b", "hyperhydration"),
             **_np("procedure:c", "fluid intake", section="Management / Prevention of Secondary Complications")}
    monkeypatch.setattr(E, "_llm", lambda *a, **k: ({"same": [[2, 3], [1, 2]], "broader": []}, {"m": 1}))
    log = E.merge_synonyms(found, True)
    assert set(found) == {"procedure:a", "procedure:c"}                       # a + b merged; b + c refused
    assert found["procedure:a"]["merged_from"] == [{"key": "procedure:b", "label": "hyperhydration"}]
    assert any(x.get("refused") and x["why"] == "not from the same chapter section" for x in log)


def test_broader_and_narrower_are_related_not_merged(monkeypatch):
    found = {**_np("procedure:dialysis", "dialysis"), **_np("procedure:hd", "hemodialysis")}
    monkeypatch.setattr(E, "_llm", lambda *a, **k: ({"same": [], "broader": [[1, 2]]}, {}))
    E.merge_synonyms(found, True)
    assert set(found) == {"procedure:dialysis", "procedure:hd"}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, found, PF_FS, [])
    hd = next(a for a in led.actions if a["action_key"] == "procedure:hd")
    dia = next(a for a in led.actions if a["action_key"] == "procedure:dialysis")
    assert hd["report"] is False and "dialysis" in hd["report_note"] and dia["includes"][0]["label"] == "hemodialysis"


def test_removed_pregnancy_only_parent_does_not_hide_a_clinical_action():
    found = {**_np("procedure:dbs", "DBS", section="Management / Pregnancy Management"),
             **_np("procedure:gpi", "GPi-DBS")}
    found["procedure:dbs"]["pregnancy_only"] = True
    found["procedure:gpi"]["narrower_than"] = {"key": "procedure:dbs", "label": "DBS"}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, found, PF_FS, [])
    rec = next(a for a in led.actions if a["action_key"] == "procedure:gpi")
    assert rec.get("report", True) is True and "narrower_than" not in rec
    assert not any(a["action_key"] == "procedure:dbs" for a in led.actions)


def test_condition_from_another_row_is_not_attached():
    row1 = ["Kidney stones", "Ureteroscopy", "In kidney failure"]
    assert E._reqs([{"text": "if needed", "field": "situation"}], None, " | ".join(row1)) == []


def test_dropped_purpose_clauses_are_logged_with_the_rule():
    log = []
    raw = [{"text": "to reduce hepatic oxalate production", "field": "situation"}, {"text": "as needed", "field": "situation"}]
    kept = E._reqs(raw, None, "as needed to reduce hepatic oxalate production", log, {"source": "NBK1283 s", "action": "x"})
    assert [r["text"] for r in kept] == ["as needed"]
    assert log == [{"text": "to reduce hepatic oxalate production", "field": "situation", "rule": E.PURPOSE_RULE,
                    "pattern": E.PURPOSE_CLAUSE.pattern, "source": "NBK1283 s", "action": "x"}]
    assert "dropped_conditions" in LG.Ledger("P", [dict(BR, id="b1")]).to_dict()


# --- therapy programs (decision 2026-11-04): code vocabulary decides, the LLM gives the name only

@pytest.mark.parametrize("name,want", [
    ("early intervention program", "early_intervention"),
    ("Referral to an early intervention program", "early_intervention"),
    ("physical therapy", "physical_therapy"), ("physiotherapy", "physical_therapy"), ("PT", "physical_therapy"),
    ("occupational therapy", "occupational_therapy"), ("speech-language therapy", "speech_language_therapy"),
    ("speech therapy", "speech_language_therapy"), ("feeding therapy", "feeding_therapy"),
    ("developmental preschool", "other_rehabilitation"),
    # reverse checks: evaluation / counselling referrals, airway clearance, unknown programs, lower-case abbreviations
    ("referral to a developmental pediatrician for evaluation", None), ("genetic counseling", None),
    ("speech and language assessment", None), ("chest physical therapy", None), ("music class", None), ("pt", None),
])
def test_therapy_vocabulary(name, want):
    assert A.therapy_type(name) == want


def _gr_item(monkeypatch, items, *, path="Management / Treatment of Manifestations", text=None, shown=None, pf=None):
    """Run the GeneReviews part of add_established on one fake section with the given LLM items."""
    text = text if text is not None else ("Ages 0-3 years. Referral to an early intervention program is recommended. "
            "Referral to a developmental pediatrician for evaluation is recommended. Chest physical therapy daily.")
    monkeypatch.setattr(E, "chapters_for", lambda led, s2, uc: {"b1": ["NBK1"]})
    monkeypatch.setattr(E, "mgmt_sections", lambda nbk: [(path, text)])
    monkeypatch.setattr(E.GR, "sections_for_llm", lambda nbk: {path: text if shown is None else shown})
    monkeypatch.setitem(E._SHOWN, "NBK1", {path: text if shown is None else shown})
    monkeypatch.setattr(E.D, "ensure", lambda name: type("S", (), {"downloaded_at": 1})())
    monkeypatch.setattr(E, "_llm", lambda system, user, uc, what="": ({"items": items}, {"served_model": "fake", "prompt_version": "fake"}) if "management actions" in system
                        else ({"same": [], "broader": []}, {}))
    monkeypatch.setattr(E.LB, "search", lambda *a, **k: ([], {"database": "openfda", "endpoint": "e", "query": "q",
                                                              "queried_at": 1, "n_results": 0, "returned": 0}))
    monkeypatch.setattr(E, "disease_names", lambda b, s2: ["dystonia 28"])
    monkeypatch.setattr(E, "facts", lambda s1, s2: pf if pf is not None else dict(PF, age_months=None, age_quote=None))
    monkeypatch.setattr(E, "ontology", lambda: type("O", (), {"exact_lookup": lambda self, t: [], "search": lambda self, t, k: [],
                                                         "ancestors": lambda self, h: []})())
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E.add_established(led, {}, {}, use_cache=True)
    return led


@pytest.mark.parametrize("heading,sex,months,want", [
    ("Affected Males", "male", 84, "applicable"),
    ("Affected Males", "female", 84, "not_applicable"),
    ("Affected Males", "unknown", 84, "conditional"),
    ("Adults", "male", 30 * 12, "applicable"),
    ("Adults", "male", 7 * 12, "not_applicable"),
    ("Adults", "male", None, "conditional"),
    ("Children", "male", 7 * 12, "applicable"),
    ("Children", "male", 30 * 12, "not_applicable"),
    ("Children", "male", 15 * 12, "conditional"),  # existing disputed age-band boundary stays unknown
    ("Infants", "male", 6, "applicable"),
    ("Infants", "male", 84, "not_applicable"),
    ("Infants", "male", None, "conditional"),
    ("Female carriers", "male", 84, "not_applicable"),
    ("Female carriers", "female", 84, "conditional"),  # sex alone does not establish carrier status
    ("Heterozygous Females", "female", 84, "not_applicable"),  # PF is explicitly homozygous
])
def test_population_section_heading_conditions_every_item_even_when_llm_omits_it(monkeypatch, heading, sex, months, want):
    monkeypatch.setattr(E.CC, "ENABLED", False)
    text = "Chest physical therapy daily. Stretching daily."
    items = [{"name": name, "kind": "procedure", "quote": quote} for name, quote in
             [("Chest physical therapy", "Chest physical therapy daily."), ("stretching", "Stretching daily.")]]
    pf = dict(PF, sex=sex, sex_quote=None if sex == "unknown" else sex,
              age_months=months, age_quote=None if months is None else "stated age")
    led = _gr_item(monkeypatch, items, path=f"Management / Treatment of Manifestations / {heading}", text=text, pf=pf)
    actions = [a for a in led.actions if a["action_key"]]
    assert len(actions) == 2
    for a in actions:
        assert a["status_by_branch"]["b1"]["status"] == want
        assert heading in [r["requirement"] for r in a["requirements"]]
    assert not [c for c in led.checks() if c["status"] == "fail"]
    if sex == "unknown" or months is None:
        assert {m["variable"] for m in led.missing_information} & {"sex", "age"}


def test_dmd_bisphosphonates_keep_affected_males_and_bone_health_after_removing_purpose(monkeypatch):
    monkeypatch.setattr(E.CC, "ENABLED", False)
    text = "Bone health Bisphosphonates to prevent fractures"
    item = {"name": "Bisphosphonates", "kind": "procedure", "quote": "Bisphosphonates to prevent fractures",
            "manifestation": "fractures"}
    led = _gr_item(monkeypatch, [item], path="Management / Supportive Care / Affected Males", text=text,
                   shown=BONE_ROW, pf=dict(PF, sex="unknown", sex_quote=None))
    a = next(a for a in led.actions if a["action_key"])
    assert {r["requirement"] for r in a["requirements"]} == {"Affected Males", "Bone health"}
    assert a["purposes"] == ["fractures"] and a["status_by_branch"]["b1"]["status"] == "conditional"


def test_population_subheading_applies_to_list_and_table_but_not_next_heading(monkeypatch):
    from aitx.evidence import genereviews as GR
    shown = ("Subheading: Infants\nParagraph 1 [context: Infants]: Stretching daily.\n"
             "Table 1. Care\nRow 1: [Treatment: Chest physical therapy daily.]\n"
             "Subheading: General care\nParagraph 2 [context: General care]: Regular exercise.")
    path = "Management / Supportive Care"
    for quote in ["Stretching daily.", "Chest physical therapy daily."]:
        assert "Infants" in GR.heading_context(path, shown, quote)
    assert "Infants" not in GR.heading_context(path, shown, "Regular exercise.")
    assert "Infants" not in GR.heading_context(path + " / Adults", "Paragraph 1: Regular exercise.", "Regular exercise.")
    monkeypatch.setattr(E.CC, "ENABLED", False)
    items = [{"name": "stretching", "kind": "procedure", "quote": "Stretching daily."},
             {"name": "exercise", "kind": "procedure", "quote": "Regular exercise."}]
    led = _gr_item(monkeypatch, items, path=path, text="Infants Stretching daily. General care Regular exercise.",
                   shown=shown.replace("Table 1. Care\nRow 1: [Treatment: Chest physical therapy daily.]\n", ""), pf=PF)
    states = {a["label"]: a["status_by_branch"]["b1"]["status"] for a in led.actions if a["action_key"]}
    assert states == {"stretching": "not_applicable", "exercise": "applicable"}


def test_unknown_zygosity_in_population_heading_does_not_satisfy():
    req = {"field": "zygosity", "text": "Heterozygous Females", "value": ["heterozygous"]}
    for zyg in (None, "", "unknown"):
        pf = dict(PF, variants=[dict(PF["variants"][0], zygosity=zyg)])
        assert E.evaluate(req, pf, BR)[0] == "unknown"


def test_therapy_referral_kept_evaluation_referral_dropped(monkeypatch):
    led = _gr_item(monkeypatch, [
        {"name": "early intervention program", "kind": "therapy", "quote": "Referral to an early intervention program is recommended.",
         "requirements": [{"text": "Ages 0-3 years", "field": "age", "op": "<=", "value": 3, "unit": "year"}]},
        {"name": "developmental pediatrician evaluation", "kind": "therapy",
         "quote": "Referral to a developmental pediatrician for evaluation is recommended."},
        {"name": "chest physical therapy", "kind": "therapy", "quote": "Chest physical therapy daily."}])
    keys = {a["action_key"]: a for a in led.actions if a.get("action_key")}
    assert "therapy:early_intervention" in keys                         # treatment referral kept, keyed by the vocabulary
    assert not any("pediatrician" in a["label"] for a in led.actions)  # evaluation referral excluded
    assert "procedure:chest_physical_therapy" in keys                   # airway clearance stays a procedure


# --- paragraph lead-ins and row coverage (decision 2026-11-04)

SHOWN_P = ("Paragraph 1: The following information represents typical recommendations.\n"
           "Paragraph 2 [context: Ages 0-3 years.]: Ages 0-3 years. Referral to an early intervention program is recommended.\n"
           "Paragraph 3 [context: Ages 3-5 years.]: Ages 3-5 years. In the US, developmental preschool is recommended.")


def test_paragraph_scope_is_the_items_paragraph_only():
    from aitx.evidence import genereviews as GR
    sc = GR.paragraph_scope(SHOWN_P, "Referral to an early intervention program is recommended.")
    assert sc.startswith("Paragraph 2") and "Ages 0-3 years" in sc
    assert E._reqs([{"text": "Ages 0-3 years", "field": "age"}], None, sc)               # lead-in of its own paragraph
    assert not E._reqs([{"text": "Ages 3-5 years", "field": "age"}], None, sc)           # reverse: another paragraph's


def test_lead_in_and_subheading_rendered_as_paragraph_context(tmp_path, monkeypatch):
    from aitx.evidence import genereviews as GR
    xml = ("<book-part><body><sec><title>Management</title><sec><title>Treatment of Manifestations</title>"
           "<p><bold>Pharmacologic treatment of dystonia</bold></p>"
           "<p><bold>Ages 0-3 years.</bold> Referral to an early intervention program is recommended.</p>"
           "<p>All ages. Physical therapy.</p>"
           "<list><list-item><p>Feeding therapy if needed.</p></list-item></list></sec></sec></body></book-part>")
    f = tmp_path / "x.nxml"
    f.write_text(xml)
    monkeypatch.setattr(GR, "extract_chapters", lambda nbks: {nbks[0]: f})
    shown = GR.sections_for_llm("NBK9")["Management / Treatment of Manifestations"].splitlines()
    assert shown[0] == "Subheading: Pharmacologic treatment of dystonia"
    assert shown[1].startswith("Paragraph 1 [context: Pharmacologic treatment of dystonia; Ages 0-3 years.]: Ages 0-3 years.")
    assert shown[2].startswith("Paragraph 2 [context: Pharmacologic treatment of dystonia]: All ages.")   # no bold: no lead-in
    assert shown[3].startswith("Paragraph 3 [context: Pharmacologic treatment of dystonia]: Feeding therapy")  # list after it
    assert GR.sections("NBK9")["Management / Treatment of Manifestations"].count("Ages 0-3 years.") == 1    # plain text unchanged


SHOWN_T = ("Table 10. Supportive Care\n"
           "Row 1: [Objective: Reduce stones] [Treatment: Maintain high oral fluid intake.] [Consideration/Other: Gastrostomy tube.]\n"
           "Row 2: [Objective: Preserve kidney function] [Treatment: Avoid dehydration.] [Consideration/Other: Use IV fluid if needed.]\n"
           "Row 3: [Objective: Follow-up] [Treatment: Renal ultrasound yearly.] [Consideration/Other: ]")
TEXT_T = ("Table 10. Supportive Care Objective Treatment Consideration/Other Reduce stones Maintain high oral fluid intake. "
          "Gastrostomy tube. Preserve kidney function Avoid dehydration. Use IV fluid if needed. Follow-up Renal ultrasound yearly.")


def test_uncovered_rows_found_and_quotes_must_be_verbatim():
    items = [{"name": "fluids", "quote": "Maintain high oral fluid intake."},
             {"name": "iv", "quote": "Use IV fluids when required."}]                  # not verbatim: does not cover row 2
    rows = E.uncovered_rows(SHOWN_T, TEXT_T, items)
    assert [r["row"] for r in rows] == ["Row 2", "Row 3"] and rows[0]["caption"] == "Table 10. Supportive Care"
    assert E.uncovered_rows(SHOWN_T, TEXT_T, items + [{"quote": "Use IV fluid if needed."},
                                                      {"quote": "Renal ultrasound yearly."}]) == []


def test_uncovered_row_extracted_again_and_logged(monkeypatch):
    calls = []

    def fake(system, user, uc, what=""):
        calls.append(what)
        if system == E.ROW_SYSTEM and "Row 2" in user:
            return {"items": [{"name": "IV fluid", "kind": "procedure", "quote": "Use IV fluid if needed.",
                               "requirements": [{"text": "if needed", "field": "situation"}]}]}, {"m": "row"}
        if system == E.ROW_SYSTEM:
            return {"items": [], "no_treatment": True, "reason": "surveillance"}, {"m": "row"}
        if "management actions" in system:
            return {"items": [{"name": "high oral fluid intake", "kind": "diet", "quote": "Maintain high oral fluid intake."}]}, {"m": 1}
        return {"same": [], "broader": []}, {}
    monkeypatch.setattr(E, "chapters_for", lambda led, s2, uc: {"b1": ["NBK1"]})
    monkeypatch.setattr(E, "mgmt_sections", lambda nbk: [("Management / Treatment of Manifestations / Supportive Care", TEXT_T)])
    monkeypatch.setattr(E.GR, "sections_for_llm", lambda nbk: {"Management / Treatment of Manifestations / Supportive Care": SHOWN_T})
    monkeypatch.setattr(E.D, "ensure", lambda name: type("S", (), {"downloaded_at": 1})())
    monkeypatch.setattr(E, "_llm", fake)
    monkeypatch.setattr(E.LB, "search", lambda *a, **k: ([], {"database": "openfda", "endpoint": "e", "query": "q",
                                                              "queried_at": 1, "n_results": 0, "returned": 0}))
    monkeypatch.setattr(E, "disease_names", lambda b, s2: ["primary hyperoxaluria type 1"])
    monkeypatch.setattr(E, "facts", lambda s1, s2: PF)
    monkeypatch.setattr(E, "ontology", lambda: type("O", (), {"exact_lookup": lambda self, t: [], "search": lambda self, t, k: [],
                                                         "ancestors": lambda self, h: []})())
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E.add_established(led, {}, {}, use_cache=True)
    labels = {a["label"] for a in led.actions}
    assert "IV fluid" in labels and "high oral fluid intake" in labels
    log = {r["row"]: r for r in led.reextracted_rows}
    assert set(log) == {"Row 2", "Row 3"} and log["Row 2"]["n_items"] == 1 and log["Row 3"]["no_treatment"]
    iv = next(a for a in led.actions if a["label"] == "IV fluid")
    assert iv["status_by_branch"]["b1"]["status"] == "conditional"


def test_or_between_counts_is_not_split():
    # 2026-11-05 run: "1 or 2 missense AGXT pathogenic variants" was split into "1" and "2 missense ..." -> unknown
    assert E.or_parts("persons w/1 or 2 missense AGXT pathogenic variants") == ["persons w/1 or 2 missense AGXT pathogenic variants"]
    assert E.or_parts("one or two missense AGXT variants") == ["one or two missense AGXT variants"]
    assert len(E.or_parts("heterozygous for p.Phe508del & a minimal function variant or other known responsive PV")) == 2


def test_count_alternatives_compare_on_the_variant_class():
    req = {"field": "variant_class", "op": "in", "value": ["missense"], "text": "1 or 2 missense AGXT pathogenic variants"}
    assert E.evaluate(req, PF, BR)[0] == "does_not_satisfy"                      # frameshift patient
    pf = dict(PF, variants=[dict(PF["variants"][0], protein="p.(Gly170Arg)", **{"class": "missense"})])
    assert E.evaluate(req, pf, BR)[0] == "satisfies"


# --- broadening clauses (decision 2026-11-05)

ROW_PYR = ("a trial of pyridoxine should be considered in all persons w/1 or 2 missense AGXT pathogenic variants, "
           "incl those w/advanced CKD or kidney failure.")


def test_broadening_clause_dropped_when_a_main_condition_remains():
    raw = [{"text": "1 or 2 missense AGXT pathogenic variants", "field": "variant_class", "op": "in", "value": ["missense"]},
           {"text": "advanced CKD or kidney failure", "field": "kidney_function"}]
    reqs = E._reqs(raw, None, ROW_PYR)
    assert reqs[1]["_broadening"] == "incl those w/" and "_broadening" not in reqs[0]
    log = []
    kept = E.drop_broadening(reqs, log, {"source": "NBK1283 x", "action": "pyridoxine"})
    assert [r["text"] for r in kept] == ["1 or 2 missense AGXT pathogenic variants"]
    assert log[0]["text"] == "advanced CKD or kidney failure" and log[0]["rule"] == E.BROADENING_RULE and not log[0]["kept"]


def test_broadening_clause_alone_is_kept_with_an_alarm():
    reqs = E._reqs([{"text": "advanced CKD or kidney failure", "field": "kidney_function"}], None, ROW_PYR)
    log = []
    kept = E.drop_broadening(reqs, log, {"source": "s", "action": "a"})
    assert [r["text"] for r in kept] == ["advanced CKD or kidney failure"] and "_broadening" not in kept[0]
    assert log[0]["warning"] and log[0]["kept"] and log[0]["rule"] == E.BROADENING_ALARM


@pytest.mark.parametrize("where", [
    "considered in all persons w/1 or 2 missense AGXT pathogenic variants, except those w/advanced CKD or kidney failure.",
    "considered in all persons w/1 or 2 missense AGXT pathogenic variants, excluding those w/advanced CKD or kidney failure.",
    "considered in persons w/missense variants other than those w/advanced CKD or kidney failure.",
    "considered in persons w/missense variants unless advanced CKD or kidney failure is present.",
])
def test_narrowing_words_keep_the_condition(where):
    # reverse check: the same sentence with a narrowing word is a real condition
    raw = [{"text": "missense", "field": "variant_class", "op": "in", "value": ["missense"]},
           {"text": "advanced CKD or kidney failure", "field": "kidney_function"}]
    reqs = E._reqs(raw, None, where)
    assert not any(r.get("_broadening") for r in reqs)
    assert len(E.drop_broadening(reqs, [], {})) == 2


def test_plain_situation_without_broadening_word_stays():
    reqs = E._reqs([{"text": "in kidney failure", "field": "situation"}], None, "Dialysis in kidney failure.")
    assert reqs and not reqs[0].get("_broadening")


def test_variant_class_with_empty_value_uses_the_requirement_words():
    # 2026-11-05: {"field": "variant_class", "op": "", "value": ""} for "1 or 2 missense AGXT pathogenic variants"
    req = {"field": "variant_class", "op": "", "value": "", "text": "1 or 2 missense AGXT pathogenic variants"}
    assert E.evaluate(req, PF, BR)[0] == "does_not_satisfy"                     # frameshift patient
    pf = dict(PF, variants=[dict(PF["variants"][0], protein="p.(Gly170Arg)", **{"class": "missense"})])
    assert E.evaluate(req, pf, BR)[0] == "satisfies"
    # reverse: no class word in the text and no usable value -> still not comparable (unknown, never "not met")
    assert E.evaluate({"field": "variant_class", "op": "", "value": "", "text": "known to be pyridoxine responsive"},
                      PF, BR)[0] == "unknown"


@pytest.mark.parametrize("text", ["persons without missense AGXT variants", "missense or nonsense AGXT variants",
                                  "non-missense AGXT variants", "AGXT variants other than missense",
                                  "any AGXT variant except missense", "not missense"])
def test_variant_class_fallback_refuses_negated_or_several_class_words(text):
    # reverse checks (2026-11-05): the text's class word is used only when it is the only one and is not negated
    req = {"field": "variant_class", "op": "", "value": "", "text": text}
    for cls in ("frameshift", "missense"):
        pf = dict(PF, variants=[dict(PF["variants"][0], **{"class": cls})])
        assert E.evaluate(req, pf, BR)[0] == "unknown"


# --- context check and the label rule (fix 2026-11-12: CFTR ETI made conditional by another genotype's table row)

import json  # noqa: E402


def _patch_passage(monkeypatch, fn):
    """The passage(s) the context check reads: one per spec, given by fn."""
    monkeypatch.setattr(E, "context_passage", fn)
    monkeypatch.setattr(E, "context_passages", lambda spec: [fn(spec)])

PASSAGE = "Pyridoxine (vitamin B6) for persons w/missense AGXT variants. Also given throughout pregnancy."


def _cc(monkeypatch, limit_patient=None):
    """Context check on, passage fixed; the main check finds the limit 'missense AGXT variants'; the follow-up
    (asked only when given) answers limit_patient. Returns the list of follow-ups asked."""
    from aitx.evidence import context_check as CC
    monkeypatch.setattr(CC, "ENABLED", True)
    _patch_passage(monkeypatch, lambda spec: ("GeneReviews NBK1283", PASSAGE))
    asked = []

    def chat(messages, k, use_cache, prompt_version=None, call_params=None):
        user = messages[-1]["content"]
        if "Is that the group, table row or genotype" in user:
            asked.append(user)
            ans = [{"q": 1, "answer": limit_patient, "quote": ""}]
        else:
            n = user.count(" Answers: ")
            ans = [{"q": 1, "answer": "yes", "quote": ""}, {"q": 2, "answer": "this_disease_patients", "quote": ""},
                   {"q": 3, "answer": "yes", "quote": "missense AGXT variants"}] + \
                  [{"q": i, "answer": "yes", "quote": ""} for i in range(4, n + 1)]
        return {"content": json.dumps({"answers": ans}), "served_model": "fake"}
    monkeypatch.setattr(CC.X, "_cached_chat", chat)
    return asked


def _with_label(found):
    a = found["drug:rxcui:684879"]
    lsrc = {"type": "spl_setid", "id": "0b0e8c5a-1111-2222-3333-444455556666", "url": "u", "version": "3",
            "effective_date": "20250101", "brand": "B"}
    ltext = "B is indicated for the treatment of primary hyperoxaluria type 1 in patients 2 years and older."
    a["specs"].append(dict(E._spec("B label indicated", lsrc, ltext, ltext, 1), label_section="existing_targeted_therapies"))
    a["reqs"].append({"kind": "label_condition", "text": "2 years and older", "field": "age", "op": ">=", "value": 2,
                      "unit": "year", "spec": E._spec("B label requirement", lsrc, "2 years and older", ltext, 1)})
    return found


def test_when_the_label_decides_a_limit_from_genereviews_is_a_note_only(monkeypatch):
    asked = _cc(monkeypatch, limit_patient="no")
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _with_label(_found("existing_targeted_therapies")), PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["status_by_branch"]["b1"]["status"] == "applicable"
    assert [r["requirement"] for r in rec["requirements"]] == ["2 years and older"]
    assert rec["context_check"]["label_decides"] and rec["context_check"]["not_applied"] == ["missense AGXT variants"]
    assert asked == []                                      # no follow-up needed: nothing would be applied


def test_reverse_without_a_label_the_limit_still_makes_the_entry_conditional(monkeypatch):
    asked = _cc(monkeypatch, limit_patient="no")
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("existing_targeted_therapies"), PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["status_by_branch"]["b1"]["status"] == "conditional"
    assert [r.get("context_check") for r in rec["requirements"]] == ["limit"]
    assert len(asked) == 3 and "label_decides" not in rec["context_check"]


def test_a_limit_that_is_the_patients_own_row_is_kept_as_a_note(monkeypatch):
    _cc(monkeypatch, limit_patient="yes")
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("existing_targeted_therapies"), PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["status_by_branch"]["b1"]["status"] == "applicable" and rec["requirements"] == []
    assert any("patient's own row" in n for n in rec["context_check"]["notes"])
    assert "missense AGXT variants" in rec["context_check"]["limit_followup"]


@pytest.mark.parametrize("answer", ["not_stated", "no"])
def test_reverse_an_unconfirmed_own_row_keeps_the_limit(monkeypatch, answer):
    _cc(monkeypatch, limit_patient=answer)
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("existing_targeted_therapies"), PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["status_by_branch"]["b1"]["status"] == "conditional"


# --- age-band limits (user decision 2026-11-12): unknown age -> conditional, inside -> applicable, outside -> not applicable

def _cc_limit(monkeypatch, limit, passage):
    from aitx.evidence import context_check as CC
    monkeypatch.setattr(CC, "ENABLED", True)
    _patch_passage(monkeypatch, lambda spec: ("GeneReviews NBK1283", passage))

    def chat(messages, k, use_cache, prompt_version=None, call_params=None):
        user = messages[-1]["content"]
        if "Is that the group, table row or genotype" in user:
            ans = [{"q": 1, "answer": "not_stated", "quote": ""}]
        else:
            n = user.count(" Answers: ")
            ans = [{"q": 1, "answer": "yes", "quote": ""}, {"q": 2, "answer": "this_disease_patients", "quote": ""},
                   {"q": 3, "answer": "yes", "quote": limit}] + [{"q": i, "answer": "yes", "quote": ""} for i in range(4, n + 1)]
        return {"content": json.dumps({"answers": ans}), "served_model": "fake"}
    monkeypatch.setattr(CC.X, "_cached_chat", chat)


@pytest.mark.parametrize("months,quote,want", [(None, None, "conditional"), (0.3, "a 9-day-old", "applicable"),
                                               (84, "7-year-old", "not_applicable")])
def test_an_age_band_limit_is_decided_against_the_stated_age(monkeypatch, months, quote, want):
    _cc_limit(monkeypatch, "Newborns", "Newborns: pyridoxine (vitamin B6) for persons w/missense AGXT variants.")
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("existing_targeted_therapies"), dict(PF, age_months=months, age_quote=quote), [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert rec["status_by_branch"]["b1"]["status"] == want
    (l,) = [r for r in rec["requirements"] if r.get("context_check") == "limit"]
    assert "ICH E11" in l["note"] and "context check:" in l["note"]
    assert [p["name"] for p in led.checks() if p["status"] == "fail"] == []
    if months is None:
        assert any(m["variable"] == "age" for m in led.missing_information)


# --- merged actions are checked passage by passage (user decision 2026-11-12: CFTR airway clearance, laxatives, salt)

NEWBORN = "Newborns: teach airway clearance to aid in mucus clearance."
ALL = "Individuals with the disease: airway clearance to aid in mucus clearance."
ADULT = "Adults: airway clearance to aid in mucus clearance."


def _two_passages(monkeypatch, passages):
    """One merged action whose specs come from the given passages; the check finds the age word that opens each
    passage as its limit ('Individuals' passages have no limit)."""
    from aitx.evidence import context_check as CC
    monkeypatch.setattr(CC, "ENABLED", True)
    by_quote = {}
    specs = []
    for n, psg in enumerate(passages):
        src = {"type": "nbk", "id": "NBK1283", "url": "u", "section": f"Management / part {n}", "credit": "c"}
        q = "airway clearance to aid in mucus clearance"
        sp = E._spec(f"GeneReviews lists airway clearance ({n})", src, q, psg, 1)
        sp["src"] = dict(src)
        specs.append(sp)
        by_quote[src["section"]] = psg
    _patch_passage(monkeypatch, lambda spec: (f"GeneReviews {spec['src']['section']}",
                                                            by_quote[spec["src"]["section"]]))
    asked = []

    def chat(messages, k, use_cache, prompt_version=None, call_params=None):
        user = messages[-1]["content"]
        psg = next(p for p in passages if p in user)
        if "Is that the group, table row or genotype" in user:
            return {"content": json.dumps({"answers": [{"q": 1, "answer": "not_stated", "quote": ""}]}), "served_model": "f"}
        asked.append(psg)
        word = psg.split(":")[0]
        limit = ("no", "") if word.startswith("Individuals") else ("yes", word)
        n = user.count(" Answers: ")
        ans = [{"q": 1, "answer": "yes", "quote": ""}, {"q": 2, "answer": "this_disease_patients", "quote": ""},
               {"q": 3, "answer": limit[0], "quote": limit[1]}] + [{"q": i, "answer": "yes", "quote": ""} for i in range(4, n + 1)]
        return {"content": json.dumps({"answers": ans}), "served_model": "f"}
    monkeypatch.setattr(CC.X, "_cached_chat", chat)
    return specs, asked


def _status(monkeypatch, passages, months):
    specs, asked = _two_passages(monkeypatch, passages)
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("supportive_management", specs=specs, label="airway clearance",
                           key="procedure:airway_clearance"),
               dict(PF, age_months=months, age_quote="stated age"), [])
    rec = next(x for x in led.actions if x["action_key"] == "procedure:airway_clearance")
    assert [p["name"] for p in led.checks() if p["status"] == "fail"] == []
    return rec, asked


def test_a_general_passage_restores_the_action_a_newborn_passage_limited(monkeypatch):
    rec, asked = _status(monkeypatch, [NEWBORN, ALL], 15 * 12)
    assert set(asked) == {NEWBORN, ALL}                       # each passage checked
    assert rec["status_by_branch"]["b1"]["status"] == "applicable"
    assert not [r for r in rec["requirements"] if r.get("context_check") == "limit"]
    cc = rec["context_check"]
    assert cc["passage_decision"].startswith("a passage with no limit") and cc["not_applied"] == ["Newborns"]
    assert len(cc["other_passages"]) == 1 and cc["other_passages"][0]["call_ids"] is not None


def test_reverse_a_newborn_only_action_stays_not_applicable(monkeypatch):
    rec, asked = _status(monkeypatch, [NEWBORN], 15 * 12)
    assert set(asked) == {NEWBORN} and rec["status_by_branch"]["b1"]["status"] == "not_applicable"
    assert "other_passages" not in rec["context_check"]


def test_when_every_passage_is_limited_any_one_met_decides(monkeypatch):
    rec, _ = _status(monkeypatch, [NEWBORN, ADULT], 40 * 12)
    assert rec["status_by_branch"]["b1"]["status"] == "applicable"
    assert {r.get("alternative") for r in rec["requirements"] if r.get("context_check") == "limit"} == {"passage 1", "passage 2"}
    rec, _ = _status(monkeypatch, [NEWBORN, ADULT], 7 * 12)
    assert rec["status_by_branch"]["b1"]["status"] == "not_applicable"
    rec, _ = _status(monkeypatch, [NEWBORN, ADULT], None)
    assert rec["status_by_branch"]["b1"]["status"] == "conditional"


def test_a_label_decided_action_checks_only_its_first_passage(monkeypatch):
    # 2026-11-12: checking the label passage as well gave a split subject answer and made lumasiran conditional
    from aitx.evidence import context_check as CC
    _cc(monkeypatch, limit_patient="no")
    label_text = "B is indicated for the treatment of primary hyperoxaluria type 1 in patients 2 years and older."
    _patch_passage(monkeypatch, lambda spec: ("h", PASSAGE) if spec["src"]["type"] == "nbk"
                        else ("label", label_text))
    inner, seen = CC.X._cached_chat, []

    def spy(messages, k, use_cache, prompt_version=None, call_params=None):
        seen.append("label" if label_text in messages[-1]["content"] else "genereviews")
        return inner(messages, k, use_cache, prompt_version, call_params)
    monkeypatch.setattr(CC.X, "_cached_chat", spy)
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _with_label(_found("existing_targeted_therapies")), PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert set(seen) == {"genereviews"} and "other_passages" not in rec["context_check"]
    assert rec["status_by_branch"]["b1"]["status"] == "applicable"



# --- the same quote in several places is several passages (user decision 2026-11-12: CFTR salt supplementation)

def test_every_place_a_row_text_occurs_is_a_passage(monkeypatch):
    shown = ("Table 6a. Newborn with the disease: Treatment\n"
             "Row 8: [Concern: Salt loss] [Treatment: Salt supplementation for salt loss]\n"
             "Table 6b. Individuals with the disease: Treatment\n"
             "Row 12: [Concern: Salt loss] [Treatment: Salt supplementation for salt loss]")
    monkeypatch.setitem(E._SHOWN, "NBK9", {"Management / Supportive Care": shown})
    monkeypatch.setattr(E.F, "GR_title", lambda nbk: "T")
    spec = {"src": {"type": "nbk", "id": "NBK9", "section": "Management / Supportive Care"},
            "quote": "Salt supplementation for salt loss"}
    got = E.context_passages(spec)
    assert [p.splitlines()[0] for _, p in got] == ["Table 6a. Newborn with the disease: Treatment",
                                                  "Table 6b. Individuals with the disease: Treatment"]
    assert E.context_passage(spec) == got[0]


def test_reverse_a_quote_in_one_place_is_one_passage(monkeypatch):
    shown = "Table 6a. Newborn: Treatment\nRow 2: [Treatment: Teach airway clearance]\nRow 3: [Treatment: Vaccinations]"
    monkeypatch.setitem(E._SHOWN, "NBK9", {"Management / Supportive Care": shown})
    monkeypatch.setattr(E.F, "GR_title", lambda nbk: "T")
    spec = {"src": {"type": "nbk", "id": "NBK9", "section": "Management / Supportive Care"}, "quote": "Teach airway clearance"}
    assert len(E.context_passages(spec)) == 1


def test_one_quote_found_in_a_newborn_and_a_general_table_follows_the_general_one(monkeypatch):
    specs, asked = _two_passages(monkeypatch, [NEWBORN, ALL])
    monkeypatch.setattr(E, "context_passages", lambda spec: [("h6a", NEWBORN), ("h6b", ALL)])
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("supportive_management", specs=specs[:1], label="airway clearance",
                           key="procedure:airway_clearance"), dict(PF, age_months=180, age_quote="15 y"), [])
    rec = next(x for x in led.actions if x["action_key"] == "procedure:airway_clearance")
    assert set(asked) == {NEWBORN, ALL} and rec["status_by_branch"]["b1"]["status"] == "applicable"


def test_reverse_one_quote_only_in_a_newborn_table_stays_not_applicable(monkeypatch):
    specs, asked = _two_passages(monkeypatch, [NEWBORN])
    monkeypatch.setattr(E, "context_passages", lambda spec: [("h6a", NEWBORN)])
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("supportive_management", specs=specs, label="airway clearance",
                           key="procedure:airway_clearance"), dict(PF, age_months=180, age_quote="15 y"), [])
    rec = next(x for x in led.actions if x["action_key"] == "procedure:airway_clearance")
    assert rec["status_by_branch"]["b1"]["status"] == "not_applicable"


# --- not a recommendation (user decision 2026-11-12, R15: RETEST-PFN1 "commonly supplement their diets with ...")

def _cc_rec(monkeypatch, rec_answer, passage=PASSAGE):
    from aitx.evidence import context_check as CC
    monkeypatch.setattr(CC, "ENABLED", True)
    _patch_passage(monkeypatch, lambda spec: ("GeneReviews NBK1283", passage))
    asked = []

    def chat(messages, k, use_cache, prompt_version=None, call_params=None):
        user = messages[-1]["content"]
        if "Does the passage recommend or advise" in user:
            asked.append(k)
            ans = [{"q": 1, "answer": rec_answer, "quote": ""}]
        else:
            n = user.count(" Answers: ")
            ans = [{"q": 1, "answer": "yes", "quote": ""}, {"q": 2, "answer": "this_disease_patients", "quote": ""},
                   {"q": 3, "answer": "no", "quote": ""}] + [{"q": i, "answer": "yes", "quote": ""} for i in range(4, n + 1)]
        return {"content": json.dumps({"answers": ans}), "served_model": "fake", "call_id": f"c{k}"}
    monkeypatch.setattr(CC.X, "_cached_chat", chat)
    return asked


def test_an_entry_the_source_only_describes_is_conditional_and_kept(monkeypatch):
    asked = _cc_rec(monkeypatch, "describes_use")
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("supportive_management"), PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert len(asked) == 3 and rec["status_by_branch"]["b1"]["status"] == "conditional"
    (l,) = [r for r in rec["requirements"] if r.get("context_check") == "recommendation"]
    assert l["result"] == "unknown" and l['requirement']=="source describes use; no explicit recommendation"
    assert l["recommendation_reason"] == "describes_use" and "describes use" in l["note"]
    assert [p["name"] for p in led.checks() if p["status"] == "fail"] == []
    assert len(rec["context_check"]["recommendation"]["call_ids"]) == 3


def test_source_wording_does_not_override_a_real_patient_mismatch(monkeypatch):
    _cc_rec(monkeypatch,'describes_use')
    req={'kind':'label_condition','field':'sex','op':'in','value':['female'],'text':'female patients'}
    led=LG.Ledger('P',[dict(BR,id='b1')])
    E._records(led,_found('supportive_management',reqs=[req]),dict(PF_FS,sex='male',sex_quote='boy'),[])
    rec=next(a for a in led.actions if a['action_key']=='drug:rxcui:684879')
    assert rec['status_by_branch']['b1']['status']=='not_applicable'
    assert all(r['context_check']!='recommendation' for r in rec['requirements'] if r['result']=='fail' and 'context_check' in r)


def test_negative_source_result_is_not_a_patient_exclusion(monkeypatch):
    _cc_rec(monkeypatch,'reports_ineffective')
    led=LG.Ledger('P',[dict(BR,id='b1')]);E._records(led,_found('supportive_management'),PF_FS,[])
    rec=next(a for a in led.actions if a['action_key']=='drug:rxcui:684879')
    assert rec['status_by_branch']['b1']['status']=='conditional'
    assert not [r for r in rec['requirements'] if r['result']=='fail']


@pytest.mark.parametrize("answer", ["recommends", "not_stated"])
def test_reverse_a_recommended_entry_is_unchanged(monkeypatch, answer):
    _cc_rec(monkeypatch, answer)
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("supportive_management"), PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert not [r for r in rec["requirements"] if r.get("context_check") == "recommendation"]


def test_reverse_contraindications_and_label_decided_drugs_are_not_asked(monkeypatch):
    asked = _cc_rec(monkeypatch, "describes_use")
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, _found("contraindications_precautions"), PF_FS, [])
    E._records(LG.Ledger("P", [dict(BR, id="b1")]), _with_label(_found("existing_targeted_therapies")), PF_FS, [])
    assert asked == []


def test_a_finding_stated_only_as_possible_makes_its_entry_conditional(monkeypatch):
    # "development is normal or mildly delayed": the supportive measure for it depends on that finding
    from aitx.evidence import context_check as CC
    monkeypatch.setattr(CC, "ENABLED", False)
    monkeypatch.setattr(E, "ontology", lambda: type("O", (), {"exact_lookup": lambda s, t: ["HP:1"],
                                                               "search": lambda s, t, k: [], "ancestors": lambda s, i: []})())
    x = {"hpo_id": "HP:1", "label": "Global developmental delay", "quote": "mildly delayed",
         "possible_because": "normal or mildly delayed", "status": "possible"}
    st, fact = E.manifestation_status("developmental delay", dict(PF, present=[], possible=[x]))
    assert st == "unknown" and fact["quote"] == "normal or mildly delayed"
    st, _ = E.manifestation_status("developmental delay", dict(PF, present=[dict(x, status="present")], possible=[]))
    assert st == "satisfies"


def test_a_possible_finding_counts_for_the_supportive_tier_record():
    # 2026-11-13: EIF2B1's early-intervention entries for a finding stated as possible failed supportive_tiers_consistent
    import inspect
    assert 'pf["present"] + (pf.get("possible") or [])' in inspect.getsource(E)


# --- the recommending sentence is cited, a limitation sentence becomes a caution (user decision 2026-11-15, SWL)

SWL = ("Paragraph 3 [context: Lithotripsy.]: Lithotripsy. Although a reasonable option, lithotripsy has a lower "
       "success rate. Hard stones are resistant to lithotripsy.")


def _swl(monkeypatch, entry_quote, rec_quote):
    from aitx.evidence import context_check as CC
    monkeypatch.setattr(CC, "ENABLED", True)
    _patch_passage(monkeypatch, lambda spec: ("GeneReviews NBK1283", SWL))

    def chat(messages, k, use_cache, prompt_version=None, call_params=None):
        user = messages[-1]["content"]
        if "Does the passage recommend or advise" in user:
            ans = [{"q": 1, "answer": "recommends", "quote": rec_quote}]
        else:
            n = user.count(" Answers: ")
            ans = [{"q": 1, "answer": "yes", "quote": ""}, {"q": 2, "answer": "this_disease_patients", "quote": ""},
                   {"q": 3, "answer": "no", "quote": ""}] + [{"q": i, "answer": "yes", "quote": ""} for i in range(4, n + 1)]
        return {"content": json.dumps({"answers": ans}), "served_model": "fake", "call_id": f"c{k}"}
    monkeypatch.setattr(CC.X, "_cached_chat", chat)
    text = SWL.split("]: ", 1)[1]
    src = {"type": "nbk", "id": "NBK1283", "url": "u", "section": "Management / Supportive Care", "credit": "c"}
    spec = E._spec("GeneReviews lists lithotripsy", src, entry_quote, text, 1)
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("supportive_management", specs=[spec], label="lithotripsy", key="procedure:lithotripsy")
    if "Hard stones" in entry_quote:      # the condition the extraction read from the limitation sentence
        own = E._spec("GeneReviews: lithotripsy for Hard stones", src, "Hard stones", text, 1)   # its own item
        found["procedure:lithotripsy"]["reqs"] = [{"kind": "other", "text": "Hard stones", "field": "manifestation",
                                                   "spec": own}]
    E._records(led, found, PF_FS, [])
    return led, next(x for x in led.actions if x["action_key"] == "procedure:lithotripsy")


def test_a_limitation_quote_gives_way_to_the_recommending_sentence(monkeypatch):
    led, rec = _swl(monkeypatch, "Hard stones are resistant to lithotripsy.", "Although a reasonable option")
    first = next(e for e in led.evidence.values() if e["id"] == rec["evidence_ids"][0])
    assert first["quote"].startswith("Although a reasonable option") and first["status"] == "verified"
    assert rec["cautions"] == ["Hard stones are resistant to lithotripsy."]
    (l,) = [r for r in rec["requirements"] if r.get("patient_fact", {}).get("field") == "manifestations not reported"]
    assert l["requirement"] == "Hard stones"   # replacing the supporting quote must not replace the manifestation
    assert led.evidence[l["requirement_evidence"]]["quote"] == "Hard stones"
    assert [p["name"] for p in led.checks() if p["status"] == "fail"] == []


def test_reverse_an_entry_quoting_the_recommending_sentence_is_unchanged(monkeypatch):
    led, rec = _swl(monkeypatch, "Although a reasonable option, lithotripsy has a lower success rate.",
                    "Although a reasonable option")
    assert "cautions" not in rec


# --- manifestation conditions (user decision 2026-11-15, PRAC-AGXT-c33dup)

@pytest.mark.parametrize("text,passage", [
    ("crystal injury to kidneys", "Row 1: [Objective: Prevent crystal injury to kidneys by ↓ crystal formation] [Treatment: x]"),
    ("calcium oxalate crystallization in the urine",
     "Paragraph 6 [context: Reduce calcium oxalate crystallization in the urine.]: Inhibition of crystallization."),
    ("Prevent fractures", "anything"),
])
def test_what_a_measure_prevents_is_its_purpose(text, passage):
    assert E.is_purpose(text, passage)


@pytest.mark.parametrize("text,passage", [
    ("seizures", "Paragraph 2: Treat seizures with standard anti-seizure medication."),
    ("seizures", "Row 3: [Manifestation/Concern: Seizures] [Treatment: Standard ASM]"),
    ("spasticity", "Paragraph 1: Manage spasticity with baclofen; control pain."),
    ("systemic oxalosis", "Row 2: [Manifestation/Concern: Systemic oxalosis] [Treatment: Initiate dialysis]"),
])
def test_reverse_a_treated_manifestation_stays_a_condition(text, passage):
    assert not E.is_purpose(text, passage)


class _Ont:
    terms = {"HP:1": "Kidney stone", "HP:2": "Acute kidney injury", "HP:3": "Nephrolithiasis (child of stone)"}

    def exact_lookup(self, t):
        return ["HP:1"] if t.lower() == "kidney stone" else []

    def search(self, t, k):
        return [{"hpo_id": "HP:2"}, {"hpo_id": "HP:1"}]

    def names(self, i):
        return {"HP:1": ["Kidney stone", "Kidney stones", "Renal stone"], "HP:2": ["Acute kidney injury"]}.get(i, [])

    def ancestors(self, i):
        return {"HP:3": ["HP:1"]}.get(i, [])


def test_strict_mapping_needs_every_word_and_records_the_basis(monkeypatch):
    monkeypatch.setattr(E, "ontology", lambda: _Ont())
    ids, basis = E.hpo_targets("kidney stone")
    assert ids == {"HP:1"} and basis == "exact HPO name or synonym"
    ids, basis = E.hpo_targets("renal stones")
    assert ids == {"HP:1"} and "every word" in basis
    ids, basis = E.hpo_targets("crystal injury to kidneys")             # the old top hit was acute kidney injury
    assert ids == set() and basis.startswith("no HPO term")
    pf = {"present": [{"hpo_id": "HP:3", "label": "Nephrolithiasis", "quote": "stones"}], "excluded": []}
    st, fact, _ = E.manifestation_match("kidney stone", pf)
    assert st == "satisfies" and fact["match"]["relation"] == "more specific than HP:1"
    assert E.manifestation_match("crystal injury to kidneys", pf)[0] == "unknown"   # reverse: unmapped stays unknown


def test_a_preventive_word_right_before_the_condition_counts_wherever_it_occurs():
    p = ("Paragraph 1: Early diagnosis of PH1 with initiation of supportive care aims to prevent crystal injury to "
         "kidneys, reduce stones.")
    assert E.is_purpose("crystal injury to kidneys", [p])
    assert not E.is_purpose("crystal injury to kidneys",
                            [p, "Row 4: [Manifestation/Concern: crystal injury to kidneys] [Treatment: x]"])   # reverse


# --- removing a purpose removes only the purpose (user decision 2026-11-15: dialysis, bisphosphonates)

DIALYSIS_ROW = ("Table 10. Supportive Care\nRow 5: [Objective: Prevent systemic oxalosis] [Treatment: Monitor plasma "
                "oxalate concentration during transient or permanent periods of low GFR.Initiate dialysis promptly to "
                "lower oxalate concentration.] [Consideration/Other: x]")
BONE_ROW = ("Table 7. Supportive Care\nRow 14: [Manifestation/Concern: Bone health] [Treatment: Bisphosphonates to "
            "prevent fractures] [Considerations/Other: High risk of fractures]")


def test_review_situation_stays_in_its_treatment_row_not_a_name_reference(monkeypatch):
    row = "Row 4: [Treatment: Liver transplant] [Therapy Candidates: GFR below 30]"
    other = ("Paragraph 12: Continue pyridoxine until liver transplant "
             "when the patient has recurrent vomiting.")
    monkeypatch.setattr(E, "context_passages", lambda s: [("h", row), ("h", other)])
    assert E.situational_phrases({"quote": "Liver transplant"}, "Liver transplant") == []


@pytest.mark.parametrize("phrase,want", [
    ("when a normal organ replaces a deficient organ", []),
    ("when kidney replacement therapy is needed", ["when kidney replacement therapy is needed"]),
    ("during vomiting", ["during vomiting"]),
])
def test_review_situation_is_a_patient_state_or_time_not_a_mechanism(monkeypatch, phrase, want):
    text = f"Paragraph 1: Give treatment X {phrase}."
    monkeypatch.setattr(E, "context_passages", lambda s: [("h", text)])
    assert E.situational_phrases({"quote": "Give treatment X"}, "treatment X") == want


def test_review_situation_does_not_cut_a_long_phrase_mid_word(monkeypatch):
    phrase = "during " + "prolonged " * 10 + "vomiting"
    monkeypatch.setattr(E, "context_passages", lambda s: [("h", f"Paragraph 1: Give treatment X {phrase}.")])
    assert E.situational_phrases({"quote": "Give treatment X"}, "treatment X") == [phrase]


def _row_entry(monkeypatch, row, quote, cond, label):
    from aitx.evidence import context_check as CC
    monkeypatch.setattr(CC, "ENABLED", False)
    source_text = row.replace("[", " ").replace("]", " ")
    _patch_passage(monkeypatch, lambda spec: ("GeneReviews NBK1", row))
    src = {"type": "nbk", "id": "NBK1", "url": "u", "section": "Management / Supportive Care", "credit": "c"}
    spec = E._spec(f"GeneReviews lists {label}", src, quote, source_text, 1)
    own = E._spec(f"{label} for {cond}", src, cond, source_text, 1)
    found = _found("supportive_management", specs=[spec], label=label, key=f"procedure:{label}")
    found[f"procedure:{label}"]["reqs"] = [{"kind": "other", "text": cond, "field": "manifestation", "spec": own}]
    led = LG.Ledger("P", [dict(BR, id="b1")])
    E._records(led, found, PF_FS, [])
    return led, next(x for x in led.actions if x["action_key"] == f"procedure:{label}")


def test_a_situational_qualifier_in_the_treatment_cell_is_a_condition(monkeypatch):
    led, rec = _row_entry(monkeypatch, DIALYSIS_ROW, "Initiate dialysis promptly to lower oxalate concentration.",
                          "systemic oxalosis", "dialysis")
    reqs = [r["requirement"] for r in rec["requirements"]]
    assert "during transient or permanent periods of low GFR" in reqs and "systemic oxalosis" not in reqs
    assert rec["purposes"] == ["systemic oxalosis"] and rec["status_by_branch"]["b1"]["status"] == "conditional"
    assert [p["name"] for p in led.checks() if p["status"] == "fail"] == []


def test_the_row_concern_column_stays_when_the_purpose_goes(monkeypatch):
    led, rec = _row_entry(monkeypatch, BONE_ROW, "Bisphosphonates to prevent fractures", "fractures", "bisphosphonates")
    reqs = [r["requirement"] for r in rec["requirements"]]
    assert "Bone health" in reqs and "fractures" not in reqs
    assert rec["status_by_branch"]["b1"]["status"] == "conditional"


def test_reverse_a_qualifier_in_another_sentence_of_a_paragraph_is_not_taken():
    spec = {"src": {"type": "nbk", "id": "NBK1"}, "quote": "Give drug X daily."}
    p = "Paragraph 1: Monitor levels during illness. Give drug X daily."
    import aitx.evidence.established as EE
    orig = EE.context_passages
    try:
        EE.context_passages = lambda s: [("h", p)]
        assert E.situational_phrases(spec) == []
        spec2 = {"src": {"type": "nbk", "id": "NBK1"}, "quote": "Give drug X daily"}
        EE.context_passages = lambda s: [("h", "Paragraph 1: Give drug X daily during illness. Rest when tired.")]
        assert E.situational_phrases(spec2) == ["during illness"]     # the quote's own sentence only
    finally:
        EE.context_passages = orig


def test_reverse_a_qualifier_of_another_list_item_or_a_hedge_is_not_taken():
    import aitx.evidence.established as EE
    orig = EE.context_passages
    try:
        EE.context_passages = lambda s: [("h", "Paragraph 2: After infancy - pancreatic enzyme replacement; vitamins; "
                                               "liver transplant when indicated; salt supplementation.")]
        assert E.situational_phrases({"src": {"type": "nbk"}, "quote": "pancreatic enzyme replacement"}) == []
        assert E.situational_phrases({"src": {"type": "nbk"}, "quote": "liver transplant"}) == ["when indicated"]
        EE.context_passages = lambda s: [("h", "Paragraph 1: Prevent fever when possible through vaccinations.")]
        assert E.situational_phrases({"src": {"type": "nbk"}, "quote": "vaccinations"}) == []
    finally:
        EE.context_passages = orig


def test_reverse_a_comma_list_neighbours_qualifier_is_not_taken():
    import aitx.evidence.established as EE
    orig = EE.context_passages
    try:
        EE.context_passages = lambda s: [("h", "Paragraph 2: Prevention of fever through the use of vaccinations, "
                                               "maintenance antibiotics during winter, and antipyretics.")]
        assert E.situational_phrases({"src": {"type": "nbk"}, "quote": "the use of vaccinations"}) == []
        assert E.situational_phrases({"src": {"type": "nbk"}, "quote": "maintenance antibiotics"}) == ["during winter"]
    finally:
        EE.context_passages = orig


def test_reverse_a_long_list_quote_takes_only_the_entrys_own_item():
    import aitx.evidence.established as EE
    orig = EE.context_passages
    q = "prevent fever (e.g., through vaccinations); maintenance antibiotics during winter, antipyretics for fever"
    try:
        EE.context_passages = lambda s: [("h", f"Paragraph 1: It is important to {q}.")]
        assert E.situational_phrases({"src": {"type": "nbk"}, "quote": q}, "vaccinations") == []
        assert E.situational_phrases({"src": {"type": "nbk"}, "quote": q}, "maintenance antibiotics") == ["during winter"]
    finally:
        EE.context_passages = orig

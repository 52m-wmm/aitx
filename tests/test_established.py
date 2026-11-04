"""Step 3a: code-side comparisons (contract docs/step3a_contract.md). Offline."""
import pytest

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


def test_variant_named_in_label_text():
    pf = dict(PF, variants=[{"gene": "CFTR", "protein": "p.Phe508del", "class": "inframe_deletion",
                             "zygosity": "homozygous", "quote": "CFTR c.1521_1523del"}])
    br = dict(BR, gene="CFTR")
    req = {"field": "variant", "text": "at least one variant ... responsive (see Table 6)",
           "_label_text": "Table 6: CFTR Gene Mutations Responsive: ... F508del ... G551D"}
    st, _, note = E.evaluate(req, pf, br)
    assert st == "satisfies" and "F508del" in note
    req["_label_text"] = "Table 6: G551D R117H"
    assert E.evaluate(req, pf, br)[0] == "unknown"           # not listed -> unknown, never a guess


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
    assert len(rows) == 1 and "stones; oxalosis" in rows[0]["why_it_matters"]
    a = next(a for a in led.actions if a["action_key"] == "procedure:ureteroscopy")
    assert a["status_by_branch"]["b1"]["status"] == "conditional"


def test_pregnancy_item_for_a_boy_kept_but_not_reported():
    req = {"kind": "other", "text": "Pregnancy Management", "field": "pregnancy"}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("supportive_management", pregnancy=True, key="procedure:iv_fluids", label="IV fluids")
    src = found["procedure:iv_fluids"]["specs"][0]["src"]
    found["procedure:iv_fluids"]["reqs"] = [dict(req, spec=E._spec("section", src, "Pregnancy Management",
                                                                  "Management / Pregnancy Management", 1))]
    E._records(led, found, PF_FS, [])                       # PF: 7-year-old boy
    a = next(a for a in led.actions if a["action_key"] == "procedure:iv_fluids")
    assert a["status_by_branch"]["b1"]["status"] == "not_applicable" and a["report"] is False


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
    E._records(led, found, pf, [])
    a = next(a for a in led.actions if a["action_key"] == "drug:rxcui:684879")
    assert a["status_by_branch"]["b1"]["status"] == "applicable"
    assert [r["requirement"] for r in a["requirements"]] == ["missense AGXT variants"]
    assert a["pregnancy_notes"] == ["given throughout pregnancy"]


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


def test_a_supportive_role_label_does_not_override_genereviews_conditions():
    # 2026-11-04 regression: Rivfloza "indicated to lower urinary oxalate levels in ... PH1" (read as supportive, no
    # conditions extracted) turned the GeneReviews eGFR and age conditions into notes -> nedosiran "applicable"
    gr = {"kind": "label_condition", "text": "missense AGXT variants", "field": "variant_class", "op": "in", "value": ["missense"]}
    led = LG.Ledger("P", [dict(BR, id="b1")])
    found = _found("existing_targeted_therapies", reqs=[gr])
    lsrc = {"type": "spl_setid", "id": "0b0e8c5a-1111-2222-3333-444455556666", "url": "u", "version": "3",
            "effective_date": "20250101", "brand": "B"}
    ltext = "B is indicated to lower urinary oxalate levels in patients with primary hyperoxaluria type 1."
    found["drug:rxcui:684879"]["specs"].append(dict(E._spec("B label", lsrc, ltext, ltext, 1), label_section="supportive_management"))
    E._records(led, found, PF_FS, [])
    rec = next(x for x in led.actions if x["action_key"] == "drug:rxcui:684879")
    assert [r["requirement"] for r in rec["requirements"]] == ["missense AGXT variants"] and "genereviews_notes" not in rec

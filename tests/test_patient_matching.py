import pytest

from aitx.evidence import actions as A

from aitx.evidence import patient_matching as E

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

from aitx.evidence import ledger as LG  # noqa: E402

def label(generic, indication):
    return {"generic": generic, "sections": {"indications_and_usage": indication}}

CF = ["cystic fibrosis", "CF"]

OTC = ["ornithine carbamoyltransferase deficiency", "OTC deficiency", "ornithine transcarbamylase deficiency", "OTCD"]

def test_searchable_names_skip_short_abbreviations():
    assert [n for n in CF + OTC if E.searchable_name(n)] == ["cystic fibrosis", "ornithine carbamoyltransferase deficiency",
                                                           "OTC deficiency", "ornithine transcarbamylase deficiency"]

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

def test_status_of_alternatives():
    line = lambda res, alt=None: {"applies_to": ["b"], "result": res, **({"alternative": alt} if alt else {})}
    assert LG.status_of([line("fail", "a"), line("pass", "b")], "b") == ("applicable", "b")
    assert LG.status_of([line("fail", "a"), line("unknown", "b")], "b") == ("conditional", "b")
    assert LG.status_of([line("fail"), line("pass", "b")], "b")[0] == "not_applicable"    # common lines apply to all
    assert LG.status_of([line("pass"), line("unknown")], "b") == ("conditional", None)

def test_omim_alias_lists_split_for_label_search():
    # 2026-11-04: openFDA answers HTTP 400 to a ";" in the phrase
    assert E.label_names(["epileptic encephalopathy, early infantile, 22; EIEE22", 'x "quoted" name', "CF"]) == \
        ["epileptic encephalopathy, early infantile, 22", "x quoted name"]

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

def test_unknown_zygosity_in_population_heading_does_not_satisfy():
    req = {"field": "zygosity", "text": "Heterozygous Females", "value": ["heterozygous"]}
    for zyg in (None, "", "unknown"):
        pf = dict(PF, variants=[dict(PF["variants"][0], zygosity=zyg)])
        assert E.evaluate(req, pf, BR)[0] == "unknown"

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

import json  # noqa: E402

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

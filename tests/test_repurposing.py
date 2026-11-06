"""Step 3e drug repurposing (docs/step3e_contract.md): deterministic judgements, offline.

Written before the module (development rule, 2026-11-06). Every expectation here is a contract rule.
"""
import pytest

from aitx.evidence import repurposing as RP

# --- direction vocabulary: the whole point of 3e's safety (a GRIN2B loss-of-function patient must never be
# offered an NMDA antagonist, and Open Targets lists 31 candidates for GRIN2B, most of them antagonists)


@pytest.mark.parametrize("mechanism,want", [
    ("loss_of_function", "up"), ("haploinsufficiency", "up"),
    ("gain_of_function", "down"), ("dominant_negative", None), (None, None),
])
def test_needed_direction_follows_the_mechanism(mechanism, want):
    assert RP.needed_direction(mechanism) == want


@pytest.mark.parametrize("action,text,want", [
    ("ANTAGONIST", "", "down"),
    ("INHIBITOR", "", "down"),
    ("BLOCKER", "", "down"),
    ("NEGATIVE ALLOSTERIC MODULATOR", "", "down"),
    ("INVERSE AGONIST", "", "down"),
    ("AGONIST", "", "up"),
    ("POSITIVE ALLOSTERIC MODULATOR", "", "up"),
    ("ACTIVATOR", "", "up"),
    ("PARTIAL AGONIST", "", "partial_up"),
    ("MODULATOR", "", None),                                        # not up or down: never written
    ("", "Glutamate [NMDA] receptor positive allosteric modulator", "up"),      # read from the mechanism text
    ("", "Glutamate [NMDA] receptor negative allosteric modulator", "down"),
    ("", "Glutamate [NMDA] receptor antagonist", "down"),
    ("", "Glutamate [NMDA] receptor modulator", None),
    ("", "", None),
])
def test_direction_from_the_record(action, text, want):
    assert RP.direction_of(action, text) == want


def test_negative_modulator_is_not_read_as_a_modulator():
    """Substring order matters: 'negative allosteric modulator' must not fall through to the bare 'modulator'."""
    assert RP.direction_of("", "a negative allosteric modulator of the receptor") == "down"
    assert RP.direction_of("", "a positive allosteric modulator of the receptor") == "up"


@pytest.mark.parametrize("mechanism,direction,ok", [
    ("loss_of_function", "up", True),
    ("loss_of_function", "partial_up", True),                      # allowed, but must be labelled
    ("loss_of_function", "down", False),                           # the antagonist case
    ("gain_of_function", "down", True),
    ("gain_of_function", "up", False),
    ("gain_of_function", "partial_up", False),                      # a partial agonist is still the wrong way
    ("loss_of_function", None, False),                              # direction unknown
    ("dominant_negative", "down", False),                           # 3e does not write for dominant negative
])
def test_direction_match(mechanism, direction, ok):
    assert RP.direction_ok(mechanism, direction) is ok


# --- ChEMBL target levels

@pytest.mark.parametrize("target_type,level", [
    ("SINGLE PROTEIN", "subunit"),
    ("PROTEIN COMPLEX", "complex"),
    ("PROTEIN COMPLEX GROUP", "family_group"),
    ("PROTEIN FAMILY", "family_group"),
    ("CELL-LINE", None),
])
def test_target_level(target_type, level):
    assert RP.target_level(target_type) == level


def test_family_level_candidates_carry_the_selectivity_caveat():
    sub = RP.sentence(_cand(level="subunit"))
    fam = RP.sentence(_cand(level="family_group"))
    assert "selectivity" not in sub
    assert "selectivity for this gene's subunit is unknown" in fam
    for s in (sub, fam):
        assert s.startswith("A hypothesis only:")
        assert "No human has been treated" in s or "no human precedent" in s
        assert not any(w in s.lower() for w in ("recommended", "effective", "proven", "could be tried", "cure"))


def _cand(**over):
    c = {"drug": "compound X", "chembl_id": "CHEMBL1", "target": "GRIN2B", "target_level": "subunit",
         "mechanism": "loss_of_function",
         "direction": "up", "action_type": "POSITIVE ALLOSTERIC MODULATOR", "route": "same_target",
         "pathway": None, "member_target": None, "evidence_level": "in_vitro",
         "evidence_quote": "the compound restored current amplitude in cells expressing the variant",
         "pmids": ["12345678"], "max_clinical_stage": "PHASE_2", "disease": "GRIN2B-related disorder"}
    if "level" in over:
        c["target_level"] = over.pop("level")
    c.update(over)
    return c


def test_sentence_says_what_the_evidence_is():
    assert "in cells" in RP.sentence(_cand(evidence_level="in_vitro")).lower() or \
        "in vitro" in RP.sentence(_cand(evidence_level="in_vitro")).lower()
    only = RP.sentence(_cand(evidence_level="target_rationale_only", evidence_quote=None, pmids=[]))
    assert "no experimental evidence" in only.lower() and "no human precedent" in only.lower()
    partial = RP.sentence(_cand(direction="partial_up", action_type="PARTIAL AGONIST"))
    assert "partial agonist" in partial.lower()
    assert "mg" not in RP.sentence(_cand()) and "dose" not in RP.sentence(_cand()).lower()


# --- ranking and caps

def test_ranking_prefers_a_complete_evidence_chain():
    """The policy (2026-11-06): having experimental evidence at all outranks having none; within one evidence
    tier a direct subunit mechanism outranks a complex or family-level one; the species (cells or animal) is
    only a tiebreak, since neither is a human."""
    rows = [
        _cand(drug="family only", level="family_group", evidence_level="target_rationale_only"),
        _cand(drug="subunit in vitro", level="subunit", evidence_level="in_vitro"),
        _cand(drug="subunit animal", level="subunit", evidence_level="animal_model"),
        _cand(drug="complex in vitro", level="complex", evidence_level="in_vitro"),
        _cand(drug="subunit rationale", level="subunit", evidence_level="target_rationale_only"),
    ]
    order = [c["drug"] for c in sorted(rows, key=RP.rank_key)]
    assert order[:2] == ["subunit animal", "subunit in vitro"]          # same tier, subunit first, animal tiebreak
    assert order.index("complex in vitro") < order.index("subunit rationale")   # evidence outranks target level
    assert order[-1] == "family only"                                   # weakest chain last
    assert order.index("subunit rationale") < order.index("family only")


def test_caps(monkeypatch):
    many = [_cand(drug=f"d{i}", evidence_level="in_vitro") for i in range(14)]
    kept, dropped = RP.pick(many)
    assert len(kept) == RP.N_CANDIDATES == 10 and len(dropped) == 4
    rationale = [_cand(drug=f"r{i}", evidence_level="target_rationale_only") for i in range(6)]
    kept, dropped = RP.pick(rationale)
    assert len(kept) == RP.N_RATIONALE_ONLY == 3               # at most three with no experimental evidence
    assert all(d["why"] == "over the cap for candidates with no experimental evidence" for d in dropped)
    mixed = [_cand(drug=f"v{i}", evidence_level="in_vitro") for i in range(9)] + \
            [_cand(drug=f"r{i}", evidence_level="target_rationale_only") for i in range(5)]
    kept, _ = RP.pick(mixed)
    assert len(kept) == 10 and sum(1 for c in kept if c["evidence_level"] == "target_rationale_only") == 1


# --- boundaries with the other sections

def test_a_drug_already_in_another_section_is_not_repeated():
    earlier = {"drug:chembl:CHEMBL1": {"section": "off_label_expanded_access", "label": "L-serine"}}
    assert RP.elsewhere(_cand(chembl_id="CHEMBL1"), earlier, [])["section"] == "off_label_expanded_access"
    assert RP.elsewhere(_cand(chembl_id="CHEMBL9"), earlier, []) is None
    # by name as well, since the same drug reaches the sections under different ids
    by_name = {"drug:rxcui:123": {"section": "existing_targeted_therapies", "label": "Compound X"}}
    assert RP.elsewhere(_cand(drug="compound x"), by_name, [])["section"] == "existing_targeted_therapies"


def test_a_human_precedent_belongs_to_3c_not_3e():
    c = _cand(human_precedent={"pmid": "999", "quote": "the patient received compound X"})
    assert RP.belongs_to_3c(c) is True
    assert RP.belongs_to_3c(_cand()) is False


# --- records and checks

def test_record_carries_what_step_4_ranks_on():
    rec = RP.record(_cand(), branch="B")
    assert rec["section"] == RP.SECTION and rec["applies_to"] == ["B"] and rec["action_key"] == "drug:chembl:CHEMBL1"
    for k in ("evidence_level", "direction_match", "approved_elsewhere", "premises_complete", "target_level"):
        assert k in rec
    assert rec["direction_match"] is True and rec["premises_complete"] is True
    assert rec["requirements"] == [] and rec["status_by_branch"] == {}       # a hypothesis, not a patient judgement


def _rows(**over):
    return [RP.record(_cand(**over), branch="B")]


def test_checks_catch_the_contract_breaches():
    assert RP.problems(_rows(), ["B"], {}) == []
    wrong = _rows(direction="down")                                 # mismatch must never reach the actions
    assert "direction" in " ".join(RP.problems(wrong, ["B"], {}))
    no_dir = _rows(direction=None)
    assert "direction" in " ".join(RP.problems(no_dir, ["B"], {}))
    noref = _rows(chembl_id="")
    assert "record id" in " ".join(RP.problems(noref, ["B"], {}))
    dup = RP.problems(_rows(), ["B"], {"drug:chembl:CHEMBL1": {"section": "clinical_trial_eligibility"}})
    assert "already in" in " ".join(dup)
    prec = _rows(human_precedent={"pmid": "1", "quote": "q"})
    assert "human precedent" in " ".join(RP.problems(prec, ["B"], {}))
    strong = [dict(RP.record(_cand(), branch="B"), conclusion="Compound X is effective in this disease.")]
    assert "claims efficacy" in " ".join(RP.problems(strong, ["B"], {}))
    dose = [dict(RP.record(_cand(), branch="B"), conclusion="A hypothesis only: give 50 mg daily.")]
    assert "dose" in " ".join(RP.problems(dose, ["B"], {}))


def test_a_branch_needs_candidates_or_a_recorded_empty_search():
    assert "no candidate and no recorded search" in " ".join(RP.problems([], ["B"], {}))
    assert RP.problems([], ["B"], {}, searched={"B": {"count": 0, "query": "x"}}) == []


# --- the mechanism gate

def test_without_a_mechanism_nothing_is_produced():
    out = RP.gate(mechanism=None)
    assert out["produce"] is False and "mechanism" in out["reason"]
    assert RP.gate(mechanism="dominant_negative")["produce"] is False
    assert RP.gate(mechanism="loss_of_function") == {"produce": True, "reason": None, "needed": "up"}


# --- a mechanism row must be about this gene's target (2026-11-06, found in the live Open Targets data)

NMDA = ["GRIN1", "GRIN2A", "GRIN2B"]
GABA = ["GABRA1", "GABRB2"]


def test_rows_about_another_target_are_dropped():
    rows = [{"drug": "ACAMPROSATE", "action_type": "ANTAGONIST", "mechanism_targets": NMDA},
            {"drug": "ACAMPROSATE", "action_type": "POSITIVE MODULATOR", "mechanism_targets": GABA}]
    kept = RP.rows_for_target(rows, "GRIN2B")
    assert len(kept) == 1 and kept[0]["action_type"] == "ANTAGONIST"
    assert RP.rows_for_target(rows, "GABRA1")[0]["action_type"] == "POSITIVE MODULATOR"
    assert RP.rows_for_target(rows, "SCN1A") == []


def test_direction_over_a_drugs_rows():
    assert RP.one_direction([{"action_type": "ANTAGONIST"}]) == ("down", None)
    assert RP.one_direction([{"action_type": "POSITIVE ALLOSTERIC MODULATOR"}]) == ("up", None)
    assert RP.one_direction([{"action_type": "AGONIST"}, {"action_type": "PARTIAL AGONIST"}]) == ("partial_up", None)
    d, why = RP.one_direction([{"action_type": "AGONIST"}, {"action_type": "ANTAGONIST"}])
    assert d is None and "both ways" in why
    d, why = RP.one_direction([{"action_type": "MODULATOR"}])
    assert d is None and "do not say which way" in why
    d, why = RP.one_direction([])
    assert d is None and why


def test_the_acamprosate_case_end_to_end():
    """A GRIN2B loss-of-function patient must not be offered acamprosate on the strength of its GABA-A row."""
    rows = [{"drug": "ACAMPROSATE", "action_type": "ANTAGONIST", "mechanism_targets": NMDA},
            {"drug": "ACAMPROSATE", "action_type": "POSITIVE MODULATOR", "mechanism_targets": GABA}]
    direction, _ = RP.one_direction(RP.rows_for_target(rows, "GRIN2B"))
    assert direction == "down"
    assert RP.direction_ok("loss_of_function", direction) is False


def test_level_is_read_off_the_mechanism_not_off_the_gene():
    """All three GRIN2B candidates name seven GRIN targets, so their claims are family level even though the gene
    has a SINGLE PROTEIN record in ChEMBL (2026-11-06)."""
    family = [{"chembl_id": "CHEMBL1", "mechanism_targets": ["GRIN1", "GRIN2A", "GRIN2B"]}]
    assert RP.level_from_rows(family, "GRIN2B") == "family_group"
    only = [{"chembl_id": "CHEMBL1", "mechanism_targets": ["GRIN2B"]}]
    assert RP.level_from_rows(only, "GRIN2B") == "subunit"
    # a mechanism recorded on the subunit's own ChEMBL target upgrades it
    assert RP.level_from_rows(family, "GRIN2B", {"CHEMBL1"}) == "subunit"
    assert RP.level_from_rows(family, "GRIN2B", {"CHEMBL9"}) == "family_group"
    assert RP.level_from_rows([], "GRIN2B") == "family_group"


def test_the_ledger_accepts_a_hypothesis_row_with_a_drug_key():
    """2026-11-06: the shared rule for rows without a per-branch status forbade an action key, which 3d rows do
    not have but 3e rows must (they are drugs and have to be deduped against the other sections)."""
    from aitx.evidence import ledger as LG
    led = LG.Ledger("P", [{"id": "B", "gene": "GRIN2B", "diagnosis": {"label": "d", "omim": ["OMIM:1"]},
                           "synonyms": []}])
    led.patient_context, led.missing_information = {}, []
    led.actions.append(RP.record(_cand(), branch="B"))
    led.repurposing_searches["B"] = {"candidates": 1, "kept": 1, "excluded": []}
    problems = led._action_problems()
    assert problems == [], problems
    # a 3e row without a key is still refused, and a 3d row with one too
    led.actions.append({**RP.record(_cand(chembl_id="", drug=""), branch="B"), "action_key": None})
    assert any("needs an action key" in x for x in led._action_problems())
    led.actions = [{"section": "bespoke_therapies", "modality": "gene_replacement", "applies_to": ["B"],
                    "requirements": [], "status_by_branch": {}, "action_key": "drug:x", "label": "x"}]
    assert any("carries no action key" in x for x in led._action_problems())


def test_every_returned_drug_is_listed_as_excluded(monkeypatch):
    """The ledger rejects a 'found nothing' record that does not account for every returned record. A drug has
    several mechanism rows, so the counts must be in drugs, not rows (2026-11-06: COL1A1 returned 4 rows for 2
    drugs, the record said 4 vs 2 excluded, and the ledger rejected it)."""
    from aitx.evidence import ledger as LG
    rows = [{"chembl_id": "C1", "drug": "d1", "action_type": "AGONIST", "mechanism_targets": ["COL1A1"],
             "mechanism_text": "", "max_clinical_stage": "PHASE_1"},
            {"chembl_id": "C1", "drug": "d1", "action_type": "AGONIST", "mechanism_targets": ["OTHER"],
             "mechanism_text": "", "max_clinical_stage": "PHASE_1"},
            {"chembl_id": "C2", "drug": "d2", "action_type": "ANTAGONIST", "mechanism_targets": ["OTHER"],
             "mechanism_text": "", "max_clinical_stage": "PHASE_1"}]
    monkeypatch.setattr(RP, "target_facts", lambda gene, use_cache=True: {
        "ensembl_id": "ENSG1", "symbol": "COL1A1", "uniprot": "P1", "pathways": [], "candidates": rows,
        "accessed_at": 1})
    monkeypatch.setattr(RP, "chembl_targets", lambda uni, use_cache=True: [])
    led = LG.Ledger("P", [{"id": "B", "gene": "COL1A1", "diagnosis": {"label": "d", "omim": ["OMIM:1"]},
                           "synonyms": []}])
    led.patient_context, led.missing_information = {}, []
    led.bespoke_mechanism["B"] = {"mechanism": "gain_of_function"}     # needs "down"; d1 is an agonist
    RP.add_repurposing(led, {"id": "P"}, {"variants": []}, {"candidates": []}, use_cache=True)
    rec = led.repurposing_searches["B"]
    assert rec["drugs_returned"] == 2 and rec["kept"] == 0
    assert len(rec["excluded"]) == 2                                   # both drugs accounted for
    neg = [e for e in led.evidence.values() if e["section"] == RP.SECTION and e["kind"] == "negative"]
    assert len(neg) == 1 and neg[0]["status"] == "verified", neg[0].get("reasons")


# --- bespoke modalities belong to 3d, not here (2026-11-06, found in the live DMD data)

@pytest.mark.parametrize("drug_type,kind", [
    ("Oligonucleotide", "oligonucleotide"), ("oligonucleotide", "oligonucleotide"),
    ("Gene therapy", "gene therapy"), ("Cell therapy", "cell therapy"),
    ("Small molecule", None), ("Protein", None), ("Antibody", None), (None, None), ("", None),
])
def test_bespoke_drug_types_are_recognised(drug_type, kind):
    assert RP.is_bespoke_type(drug_type) == kind


def test_an_exon_skipping_aso_is_not_a_repurposing_candidate(monkeypatch):
    """DMD's Open Targets candidates include drisapersen and suvodirsen, exon-skipping ASOs. 3e must hand them
    to 3d: which exon they skip is a per-variant judgement, and this patient's deletion may not match."""
    from aitx.evidence import ledger as LG
    rows = [{"chembl_id": "C1", "drug": "DRISAPERSEN", "drug_type": "Oligonucleotide",
             "action_type": "POSITIVE MODULATOR", "mechanism_targets": ["DMD"], "mechanism_text": "",
             "max_clinical_stage": "PHASE_3"}]
    monkeypatch.setattr(RP, "target_facts", lambda gene, use_cache=True: {
        "ensembl_id": "ENSG1", "symbol": "DMD", "uniprot": "P1", "pathways": [], "candidates": rows,
        "accessed_at": 1})
    monkeypatch.setattr(RP, "chembl_targets", lambda uni, use_cache=True: [])
    led = LG.Ledger("P", [{"id": "B", "gene": "DMD", "diagnosis": {"label": "d", "omim": ["OMIM:1"]},
                           "synonyms": []}])
    led.patient_context, led.missing_information = {}, []
    led.bespoke_mechanism["B"] = {"mechanism": "loss_of_function"}
    RP.add_repurposing(led, {"id": "P"}, {"variants": []}, {"candidates": []}, use_cache=True)
    rec = led.repurposing_searches["B"]
    assert rec["kept"] == 0 and [a for a in led.actions if a["section"] == RP.SECTION] == []
    assert "oligonucleotide" in rec["excluded"][0]["why"] and "3d" in rec["excluded"][0]["why"]
    assert rec["excluded"][0]["see_also"]["section"] == "bespoke_therapies"

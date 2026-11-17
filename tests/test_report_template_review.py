"""User's template/content review: deterministic sources and presentation, never an LLM call."""
import json
from pathlib import Path
import re

import pytest

from aitx.evidence import genereviews as GR, ledger as LG, pipeline as P
from aitx.evidence import established as E
from aitx.report import assemble as A, safety as S, sources as SRC, validate as V
from tests.test_report import CASE, act, build, ev, ledger, unk, variant_evidence, safety_evidence


def trial(name, status="RECRUITING", rs=(), **kw):
    return act("trial:" + name, "clinical_trial_eligibility", name, "conditional", rs,
               study_type="interventional", overall_status=status, **kw)


def test_headers_and_patient_title_come_from_the_saved_official_template():
    template = (Path(__file__).resolve().parents[1] / "data/aitxchallenge_report_template.md").read_text()
    wanted = re.findall(r"^#{1,3} .+$", template, re.M)
    md, _ = build(ledger([]))
    assert re.findall(r"^#{1,3} .+$", md, re.M) == [h.replace("AITX-XXXXX", "P") for h in wanted]
    assert not V.check_markdown(md)
    for correct in ("Established Actions", "Emerging Actions", "Hypothesized Actions"):
        assert V.check_markdown(md.replace(correct, correct.split()[0]))
    assert V.check_markdown(md.replace("### Supportive Management", "## Supportive Management"))
    assert V.check_submission(json.dumps([{"id": "different", "report_markdown": md}]))


def test_summary_covers_all_three_tiers_and_limits_each_to_three_actions():
    acts = [act("drug:L", "existing_targeted_therapies", "drug L", "applicable"),
            act("drug:N", "existing_targeted_therapies", "drug N", "conditional", [unk("eGFR >= 30")]),
            act("diet:H", "supportive_management", "hydration", "applicable"),
            *[trial(f"Trial {i}", rs=[unk("screening")]) for i in range(5)],
            {"section": "bespoke_therapies", "label": "prime editing", "classification": "theoretically_possible",
             "conclusion": "Theoretical only.", "unassessable_reason": ["PAM not assessed"], "applies_to": ["B"]}]
    led = ledger(acts); led['evidence'].append(variant_evidence())
    md, _ = build(led); summary = md.split("## Tier 1")[0]
    for tier in (1, 2, 3):
        part = summary.split(f"- **Tier {tier}:**")[1].split("\n- **")[0]
        assert 1 <= part.count("  - ") <= 3
    assert "If eGFR >= 30: drug N" in summary
    assert "prime editing" in summary and "PAM not assessed" in summary


def test_supportive_cap_does_not_hide_core_management_or_conditional_surgery():
    acts = [act(f"diet:{i}", "supportive_management", f"core measure {i}", "applicable") for i in range(11)]
    acts += [act("procedure:U", "supportive_management", "ureteroscopy", "conditional", [unk("symptomatic stones")])]
    md, _ = build(ledger(acts)); part = md.split("### Supportive Management")[1].split("### Contraindications")[0]
    assert all(f"core measure {i}" in part for i in range(11))
    assert "ureteroscopy" in part and "symptomatic stones" in part and "further supportive" not in part


def test_management_quotes_include_the_exact_quantitative_paragraph_and_own_transplant_comment(monkeypatch):
    fluid = "High oral fluid intake. Drinking large volumes of fluid (2-3 L/m2/24 hours) at regular intervals minimizes crystals."
    choice = "When kidney replacement therapy is needed, choose kidney transplant alone or liver & kidney transplant simultaneously."
    path = "Management / Treatment"
    sec = f"Row 1: [Treatment: Maintain high oral fluid intake.]\nParagraph 1: {fluid}\nRow 2: [Treatment: Liver transplant] [Comment: {choice}]"
    monkeypatch.setattr(GR, "sections_for_llm", lambda nbk: {path: sec, "Pregnancy": "Paragraph 1: High oral fluid intake (9 L/day)."})
    src = {"type": "nbk", "id": "NBK1", "section": path}
    assert fluid in E.management_quotes(sec, "high oral fluid intake", "Maintain high oral fluid intake.")
    assert choice in E.management_quotes(sec, "liver transplant", "Liver transplant")
    assert not any("9 L/day" in q for q in E.management_quotes(sec, "high oral fluid intake", "Maintain high oral fluid intake."))
    assert E.management_quotes(sec, "unrelated treatment", "unrelated") == []


def test_doses_and_targets_are_full_verbatim_quotes_not_shortened_or_rephrased():
    quote = "High oral fluid intake. " + " ".join(f"Source context {i}." for i in range(20)) + " " + "Drinking fluid (2-3 L/m2/24 hours) throughout day/night."
    md, _ = build(ledger([act("diet:H", "supportive_management", "hydration", "applicable")], missing=[])
                  | {"evidence": [ev("e1", quote)]})
    assert f'"{quote}"' in md and "2–3 L/m²" not in md


def test_all_interventional_trials_and_one_observational_summary_are_shown():
    acts = [trial(f"Intervention {i}", rs=[unk("q")] * i) for i in range(7)]
    acts += [act(f"trial:O{i}", "clinical_trial_eligibility", f"Registry {i}", "conditional", study_type="observational") for i in range(3)]
    md, _ = build(ledger(acts)); part = md.split("### Clinical Trial Eligibility")[1].split("### Off-label")[0]
    assert all(f"**Intervention {i}**" in part for i in range(7))
    rows = [line for line in part.splitlines() if "Registry" in line]
    assert len(rows) == 1 and all(f"Registry {i}" in rows[0] for i in range(3))
    assert "further trials" not in part


def test_trial_columns_separate_met_unknown_disqualifying_and_status_date():
    met = dict(unk("diagnosis D", "diagnosis"), result="pass", fact="diagnosis", kind="inclusion")
    fail = dict(unk("disallowed medicine", "current medication"), result="fail", kind="exclusion")
    a = trial("T", rs=[met, unk("eGFR threshold"), fail]); a["status_by_branch"]["B"]["status"] = "not_applicable"
    led = ledger([a]); led["evidence"][0]["accessed_at"] = 1794824083
    md, _ = build(led); part = md.split("### Clinical Trial Eligibility")[1].split("### Off-label")[0]
    for field in ("Inclusion met", "Exclusion ruled out", "Unable to assess", "Known exclusions", "Status & verified date"):
        assert field in part
    assert "diagnosis D" in part and "eGFR threshold" in part and "disallowed medicine" in part
    assert "RECRUITING" in part and "2026-11-16" in part


@pytest.mark.parametrize("first,second", [
    (trial("recruiting", rs=[unk("q")] * 6), trial("later", "NOT_YET_RECRUITING")),
    (trial("no known exclusion", rs=[unk("q")] * 6), trial("excluded", rs=[dict(unk("q"), result="fail")])),
    (trial("key facts", rs=[dict(unk("D", "diagnosis"), result="pass", fact="diagnosis"), dict(unk("age", "age"), result="pass", fact="age")] + [unk("q")] * 6), trial("no key facts")),
    (trial("one unknown", rs=[unk("q")]), trial("two unknowns", rs=[unk("q")] * 2)),
])
def test_trial_rank_uses_recruitment_exclusions_key_facts_then_unknowns(first, second):
    assert A.trial_rank(first) < A.trial_rank(second)


def test_three_outcome_blocks_use_only_recorded_premises_warnings_precedents_and_metrics():
    a = {"section": "bespoke_therapies", "modality": "gene_replacement", "label": "AAV",
         "classification": "theoretically_possible", "conclusion": "Theoretical.", "applies_to": ["B"],
         "note": "promoter and polyA not sized", "unassessable_reason": ["PAM not assessed"], "evidence_ids": ["e1"]}
    led = ledger([a, trial("T", nct="NCT1", url="u")], offlabel={"B": {"precaution_candidates": [
        {"drug": "drug W", "pmid": "1", "url": "u", "quote": "Adverse event after W.", "note": "adverse event"}]}})
    safety = {"warnings": [{"drug": "drug L", "quote": "Monitor for hypersensitivity.", "set_id": "s1", "url": "u", "effective_date": "2025"}]}
    led['evidence'][0].update(quote='Check the promoter and polyA design.',premise='preclinical_validation')
    led['evidence'] += [ev('harm','Adverse event after W.',{'type':'pmid','id':'1','url':'u'}),ev('out','Change in urinary oxalate')]
    led['report_context']={'outcomes':[{'kind':'efficacy','label':'T','evidence_id':'out'}]}
    led=safety_evidence(led,safety)
    md, _ = A.assemble(led, CASE, lambda *a: None, safety)
    part = md.split("### Outcome Measures & Ranking")[1].split("**Ranking**")[0]
    assert part.index("**Preclinical validation**") < part.index("**Safety**") < part.index("**Efficacy measures**")
    for text in ("Check the promoter and polyA design.", "PAM not assessed", "Monitor for hypersensitivity.", "Adverse event after W.", "Change in urinary oxalate"):
        assert text in part
    assert "animal model" not in part


def test_label_warnings_are_verbatim_and_missing_warnings_remain_unknown():
    labels = {"s1": {"set_id": "s1", "warnings_and_cautions": ["Watch for adverse reaction. Monitor liver enzymes."]}, "s2": {"set_id": "s2"}}
    out = S.check([{"label": "L", "set_ids": ["s1"]}, {"label": "N", "set_ids": ["s2"]}], fetch=labels.get)
    assert [w["quote"] for w in out["warnings"]] == [labels["s1"]["warnings_and_cautions"][0]]
    assert not any(w["drug"] == "N" for w in out["warnings"])


@pytest.mark.parametrize('indent',[None,2])
def test_background_sources_name_transcript_clinvar_and_computation_basis(indent):
    from tests.test_step3 import cand
    v = {"gene": "AGXT", "transcript": "NM_000030.3", "variant_cdna": "c.33dup", "variant_protein": "p.Lys12fs",
         "variant_class": "frameshift", "zygosity": "homozygous", "protein_length": 392,
         "evidence": [{"source": "https://www.ncbi.nlm.nih.gov/nuccore/NM_000030.3"}],
         "transcript_layout": {"cds": [43, 1221]},
         "nmd": {"prediction": "likely_triggers", "rules": "nmd-v1", "reasons": ["574 nt upstream of the last exon junction"]}}
    s1 = {"_meta": {"created_at": 1}, "variants": [v]}
    s2 = {"_meta": {"created_at": 1}, "candidates": [cand("B", "D")], "primary": {"confidence": "high"},
          "clinvar": [{"records": [{"vcv": "VCV000140583", "title": "c.33dup", "clinical_significance": "Pathogenic",
            "review_status": "reviewed", "stars": 2, "url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/140583/"}]}]}
    led = LG.Ledger("P", [{"id": "B", "gene": "AGXT", "diagnosis": {"label": "D", "omim": []}}])
    P.background(led, "P", s1, s2, json.dumps(s1,indent=indent), json.dumps(s2,indent=indent))
    data = ledger([]) | {"evidence": list(led.evidence.values()), "patient_context": {"variants": [v | {"nmd": "likely_triggers"}]}}
    md, _ = build(data)
    for text in ("RefSeq NM_000030.3", "VCV000140583", "nmd-v1", "574 nt", "1176", "43", "1221"):
        assert text in md
    assert all(e["status"] == "verified" for e in led.evidence.values())


def test_report_evidence_references_exist_and_each_definition_is_unique():
    led = ledger([act("drug:L", "existing_targeted_therapies", "drug L", "applicable")])
    md, _ = build(led)
    assert "[E:e1]" in md
    assert not V.check_report(md, led, "P")
    assert V.check_report(md.replace("[E:e1]", "[E:missing]"), led, "P")
    assert V.check_report(md + '\n<a id="evidence-e1"></a>\n', led, "P")
    assert V.check_report(md, led | {"evidence": led["evidence"] * 2}, "P")


def test_report_validator_rejects_changed_counts_or_unquoted_doses():
    quote = "Drink fluid (2-3 L/m2/24 hours) throughout day/night."
    led = ledger([act("diet:H", "supportive_management", "hydration", "applicable")])
    led["evidence"] = [ev("e1", quote)]
    md, _ = build(led)
    assert not V.check_report(md, led, "P")
    assert V.check_report(md.replace("Listed actions: **1**", "Listed actions: **9**"), led, "P")
    assert V.check_report(md.replace("2-3 L/m2/24 hours", "7-9 L/m2/24 hours"), led, "P")


def test_a_modalitys_unsourced_technical_argument_is_removed_and_premises_are_unconfirmed():
    a = {"section": "bespoke_therapies", "modality": "base_or_prime_editing", "label": "prime editing",
         "classification": "theoretically_possible", "conclusion": "Prime editing is theoretically possible.",
         "facts": {"reason": "A fictional vector guarantees correction."}, "evidence_ids": [], "applies_to": ["B"]}
    led = ledger([a]); led["evidence"] = [ev("v1", '"frameshift"',
        {"type": "pipeline_fact", "id": "step1:P:variants[0].variant_class", "upstream": {"type": "refseq", "id": "NM_000030.3"},
         "url": "https://www.ncbi.nlm.nih.gov/nuccore/NM_000030.3"})]
    led['evidence'][0]['section']='background'
    led["patient_context"] = {"variants": [{"gene": "AGXT", "variant_cdna": "c.33dup", "transcript": "NM_000030.3",
        "variant_class": "frameshift", "zygosity": "homozygous", "nmd": "likely_triggers"}]}
    md, _ = build(led); part = md.split("### Bespoke Therapies")[1].split("### Drug Repurposing")[0]
    assert "fictional vector" not in md and "Prime editing is theoretically possible" in part
    assert "theoretically possible" in part and "[E:v1]" in part


def test_safety_coverage_records_missing_sections_without_claiming_no_interactions():
    labels = {"s1": {"set_id": "s1", "drug_interactions": [], "contraindications": []}}
    out = S.check([{"label": "L", "set_ids": ["s1"]}, {"label": "N", "set_ids": []}], fetch=labels.get)
    assert len(out["coverage"]) == 2
    assert all(not r["interactions_checked"] and not r["contraindications_checked"] for r in out["coverage"])
    assert "no interactions" not in json.dumps(out).lower()


def test_report_lists_unchecked_ledger_drugs_even_when_not_current_candidates(monkeypatch):
    from scripts.build_report import report_safety
    from aitx import http
    monkeypatch.setattr(http,'get',lambda *a,**k:pytest.fail('presentation must not add a source lookup'))
    a=act('drug:P','existing_targeted_therapies','pyridoxine','not_applicable')
    n=act('drug:S','off_label_expanded_access','Stiripentol','conditional',efficacy_direction='reported_ineffective')
    led=ledger([a,n]);led['report_context']={'safety':{'coverage':[]}}
    safety=report_safety(led)
    assert {r['drug'] for r in safety['coverage']}=={'pyridoxine','Stiripentol'}
    assert all(not r['interactions_checked'] and not r['contraindications_checked'] for r in safety['coverage'])
    assert led['report_context']['safety']['coverage']==[]  # report presentation does not rewrite ledger checks
    md,_=build(led,safety=safety)
    summary=md.split('## Tier 1')[0]
    assert 'pyridoxine: interactions — not checked' not in summary and 'Stiripentol: interactions — not checked' in summary


@pytest.mark.parametrize('quantity', ['200 mg', '0.5 mL', '30%', '20-30 mg/kg/day', '2-3 L/m2/24 hours'])
def test_validator_checks_standalone_doses_and_compound_targets(quantity):
    led=ledger([act('drug:L','existing_targeted_therapies','drug L','applicable')])
    md,_=build(led)
    assert V.check_report(md.replace('drug L** — applicable.',f'drug L** — applicable. Dose {quantity}.'),led,'P')


def test_a_condition_references_its_own_evidence_in_addition_to_the_action_quote():
    r=unk('GFR <25-30 mL/min/1.73 m2');r['requirement_evidence']='cond'
    led=ledger([act('procedure:T','existing_targeted_therapies','transplant','conditional',[r])])
    led['evidence'] += [ev('cond','Persons with GFR <25-30 mL/min/1.73 m2')]
    md,_=build(led)
    assert not V.check_report(md,led,'P')
    line=next(l for l in md.splitlines() if l.startswith('- **transplant**'))
    assert '[E:cond]' in line


def test_dose_units_must_keep_the_sources_case():
    led=ledger([act('drug:L','existing_targeted_therapies','drug L','applicable')])
    led['evidence'][0]['quote']='The administered volume was 0.5 mL.'
    md,_=build(led)
    assert not V.check_report(md,led,'P')
    assert V.check_report(md.replace('0.5 mL','0.5 ML'),led,'P')


def test_a_measure_without_its_evidence_reference_is_rejected():
    led=ledger([]);led['report_context']={'outcomes':[{'kind':'efficacy','label':'Trial T','evidence_id':'e1'}]}
    md,_=build(led)
    assert not V.check_report(md,led,'P')
    line=next(l for l in md.splitlines() if l.startswith('- Trial T:'))
    assert V.check_report(md.replace(line,REF_WITHOUT_ID(line)),led,'P')


def REF_WITHOUT_ID(line):
    return re.sub(r'\[E:[^\]]+\](?:\([^)]*\))?', '',line)


def test_omitted_counts_match_the_ledger_and_evidence_definitions_are_not_duplicated():
    acts=[act(f'drug:{i}','off_label_expanded_access',f'drug {i}','conditional') for i in range(8)]
    led=ledger(acts);md,_=build(led)
    assert '3 further drugs' in md and not V.check_report(md,led,'P')
    assert V.check_report(md.replace('3 further drugs','4 further drugs'),led,'P')
    assert md.count('**E:e1**')==1 and md.count('[E:e1]')>1


def test_report_generation_automatically_fails_step5_for_an_unquoted_dose(tmp_path,monkeypatch):
    from scripts import build_report as B, validate_report as R
    import sys
    led=ledger([act('drug:L','existing_targeted_therapies','drug L','applicable')])
    led['report_context']={'safety':{'coverage':[]}}
    (tmp_path/'out/step3').mkdir(parents=True)
    (tmp_path/'out/step3/P.json').write_text(json.dumps(led))
    monkeypatch.setattr(B,'ROOT',tmp_path);monkeypatch.setattr(R,'ROOT',tmp_path)
    monkeypatch.setattr(B.runmeta,'find_case',lambda cid:CASE)
    monkeypatch.setattr(B.SRC,'date_of',lambda *a:None)
    monkeypatch.setattr(sys,'argv',['build_report.py','--case','P'])
    assert B.main()==0
    actual=B.A.assemble
    def bad(*args,**kw):
        md,trace=actual(*args,**kw)
        return md.replace('drug L** — applicable.','drug L** — applicable. Dose 999 mg.'),trace
    monkeypatch.setattr(B.A,'assemble',bad)
    assert B.main()==1


def test_presentation_source_collection_only_uses_existing_ledger_source_ids(monkeypatch):
    from aitx import http
    led=LG.Ledger('P',[{'id':'B'}]);led.add(ev('e1'))
    led.actions=[trial('T',nct='NCT00000001',url='https://clinicaltrials.gov/study/NCT00000001'),
                 act('trial:O','clinical_trial_eligibility','Registry','conditional',study_type='observational')]
    urls=[]
    def get(url):
        urls.append(url)
        return http.Fetched(url,json.dumps({'protocolSection':{'outcomesModule':{'primaryOutcomes':[{'measure':'Change in urinary oxalate'}]}}}),1,True)
    monkeypatch.setattr(http,'get',get)
    data=SRC.record_context(led)
    assert urls==['https://clinicaltrials.gov/api/v2/studies/NCT00000001?fields=OutcomesModule']
    assert all(led.evidence[r['evidence_id']]['status']=='verified' for r in data['outcomes'])
    assert led.evidence[data['outcomes'][0]['evidence_id']]['quote']=='Change in urinary oxalate'

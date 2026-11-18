from aitx.report import validate as V
from tests.test_report import act, build, ev, ledger, unk


def test_trials_rank_by_type_status_exclusions_key_inclusions_and_unknowns():
    def trial(name, status="RECRUITING", reqs=(), grade="conditional", kind="interventional"):
        return act("trial:"+name, "clinical_trial_eligibility", name, grade, reqs,
                   study_type=kind, overall_status=status)

    diagnosis = dict(unk("diagnosis confirmed", "diagnosis"), result="pass")
    age = dict(unk("age in range", "age"), result="pass")
    ruled_out = dict(age, kind="exclusion")
    acts = [trial("Registry", kind="observational", grade="applicable"),
            trial("Not recruiting", status="ACTIVE_NOT_RECRUITING"),
            trial("Known exclusion", reqs=[dict(unk("excluded condition"), result="fail")], grade="not_applicable"),
            trial("A ruled-out age", reqs=[ruled_out, unk("scope", "other")]),
            trial("Z diagnosis", reqs=[diagnosis, unk("age", "age")]),
            trial("Both with unknown", reqs=[diagnosis, age, unk("kidney function")]),
            trial("Both met", reqs=[diagnosis, age], grade="applicable")]
    md, _ = build(ledger(acts))
    table = md.split("### Clinical Trial Eligibility", 1)[1].split("### Off-label", 1)[0]
    order = ["Both met", "Both with unknown", "Z diagnosis", "A ruled-out age",
             "Known exclusion", "Not recruiting", "Registry"]
    positions = [table.index(name if name=="Registry" else "**"+name+"**") for name in order]
    assert positions == sorted(positions)
    ranking = md.split("**Ranking**:", 1)[1].split("**Evidence table**", 1)[0]
    order.remove("Known exclusion")
    assert [ranking.index(name) for name in order] == sorted(ranking.index(name) for name in order)
    summary = md.split("## Summary", 1)[1].split("## Tier 1:", 1)[0]
    assert "Registry" not in summary


def test_offlabel_ranking_counts_independent_reports_and_sorts_direction_first():
    specs = [("Few positive", "reported_improvement", [101, 101, 101]),
             ("Many positive", "reported_improvement", [102, 103]),
             ("Insufficient", "insufficient", [201, 202, 203]),
             ("Other", "partial_improvement", [301, 302, 303, 304])]
    actions, evidence = [], []
    for name, direction, pmids in specs:
        ids = []
        for n, pmid in enumerate(pmids):
            eid = f"p{pmid}_{n}"; ids.append(eid)
            evidence.append(ev(eid, f"Report {n} for {name}.",
                               {"type": "pmid", "id": str(pmid), "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"}))
        actions.append(act("drug:"+name, "off_label_expanded_access", name, "applicable",
                           evs=ids, efficacy_direction=direction))
    led = ledger(actions); led["evidence"] = evidence
    md, _ = build(led)
    body = md.split("### Off-label or Expanded-Access Therapies", 1)[1].split("## Tier 3:", 1)[0]
    ranking = md.split("**Ranking**:", 1)[1].split("**Evidence table**", 1)[0]
    order = ["Many positive", "Few positive", "Insufficient", "Other"]
    for text in [body, ranking]:
        assert [text.index("**"+name+"**") for name in order] == sorted(text.index("**"+name+"**") for name in order)
    assert "independent precedent reports: 2" in ranking and "independent precedent reports: 1" in ranking


def test_observational_only_summary_is_empty_of_studies_and_validator_rejects_insertion():
    obs = act("trial:registry", "clinical_trial_eligibility", "Registry", "applicable",
              study_type="observational", nct="NCT00000001")
    led = ledger([obs], missing=[{"variable": "age", "affects": ["Registry"]}])
    md, _ = build(led)
    summary = md.split("## Summary", 1)[1].split("## Tier 1:", 1)[0]
    assert "Registry" not in summary and "NCT00000001" not in summary and "age:" not in summary
    assert not V.check_report(md, led, "P")
    bad = md.replace("- **Tier 2:**", "- **Tier 2:**\n  - NCT00000001 (applicable). [E:e1]", 1)
    assert any("observational study in Summary Tier 2" in e for e in V.check_report(bad, led, "P"))

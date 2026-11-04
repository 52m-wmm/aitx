"""Action board, acceptance comparison and acceptance page (no LLM, no network)."""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import acceptance_step3a as A  # noqa: E402
import build_viewer as B  # noqa: E402

B1 = {"id": "MONDO:1", "role": "ambiguous_1", "gene": "G", "diagnosis": {"label": "classic type"}}
B2 = {"id": "MONDO:2", "role": "ambiguous_2", "gene": "G", "diagnosis": {"label": "other type"}}
EV = {"id": "ev1", "kind": "sourced", "claim": "Label X lists drug A.", "section": "existing_targeted_therapies",
      "status": "verified", "reasons": [], "accessed_at": 1793700000, "quote": "indicated for children 2 years of age and older",
      "source": {"type": "spl_setid", "id": "s", "url": "https://dailymed.example/x", "version": "4", "effective_date": "2025-03-03"}}


def req(rid, result, status, text="2 years of age and older", kind="label_condition", applies=("MONDO:1", "MONDO:2"), note=""):
    return {"id": rid, "kind": kind, "requirement": text, "requirement_evidence": "ev1", "applies_to": list(applies),
            "patient_fact": None, "patient_status": status, "result": result, "note": note}


def act(label, section, sbb, reqs=(), report=None, key=None):
    a = {"action_key": key or f"drug:name:{label.lower()}", "section": section, "label": label, "applies_to": sorted(sbb),
         "status_by_branch": {b: {"status": s, "reason": f"why {s}"} for b, s in sbb.items()}, "requirements": list(reqs),
         "evidence_ids": ["ev1"]}
    if report is False:
        a["report"], a["report_note"] = False, "pregnancy-specific management; patient is male or under 12"
    return a


def ledger():
    return {"branches": [B1, B2], "branch_order": ["MONDO:1", "MONDO:2"], "evidence": [EV],
            "missing_information": [{"variable": "eGFR", "why_it_matters": "Drug A: eGFR ≥30"}],
            "sections_status": {"existing_targeted_therapies": "searched", "supportive_management": "searched",
                                "contraindications_precautions": "searched"},
            "actions": [act("Drug A", "existing_targeted_therapies", {"MONDO:1": "conditional", "MONDO:2": "conditional"},
                            [req("r1", "unknown", "unknown", "eGFR ≥30"),
                             req("r2", "not_assessed", "not_assessed", "Signed informed consent", "inclusion", note="screening assessment")]),
                        act("Drug B", "existing_targeted_therapies", {"MONDO:2": "not_applicable"}),
                        act("Folic acid", "supportive_management", {"MONDO:1": "not_applicable", "MONDO:2": "not_applicable"}, report=False)]}


def test_board_counts_columns_and_folded_items():
    B.LANG = "zh"
    h = B.v_board(ledger())
    assert "有条件</span> <b>2</b>" in h and "不适用</span> <b>1</b>" in h          # Folic acid (not reported) not counted
    assert "不写入报告 1" in h and "不写入报告的条目 1 个" in h
    assert "grid-column:1 / 3" in h and "grid-column:2 / 3" in h                      # shared spans both, Drug B only column 2
    assert "筛选时评估" in h and "eGFR ≥30" in h and "缺失信息 1 项" in h
    assert "说明书版本 4" in h and "生效 2025-03-03" in h
    assert "尚未检索的章节" in h and "Clinical Trial Eligibility" in h


def test_board_without_ledger():
    B.LANG = "en"
    assert "has not run" in B.v_board(None)


def item(**kw):
    base = {"id": "x", "case": "C", "section": "existing_targeted_therapies", "match": "drug a", "expect": {"status": "conditional"},
            "what": {"zh": "", "en": ""}, "source": {"doc": "d", "quote": "q"}}
    return {**base, **kw}


def test_compare_status_unknown_and_branch_filter():
    led = ledger()
    assert A.compare(item(expect={"status": "conditional", "unknown": ["eGFR"]}), led)["ok"]
    r = A.compare(item(expect={"status": "conditional", "unknown": ["age"]}), led)
    assert not r["ok"] and "/age/" in r["problem"]
    assert not A.compare(item(expect={"status": "applicable"}), led)["ok"]
    assert A.compare(item(match="drug b", expect={"status": "not_applicable"}, branch="other"), led)["ok"]
    assert "no branch" in A.compare(item(branch="nope"), led)["problem"]
    r = A.compare(item(match="folic", expect={"status": "present"}), led)
    assert not r["ok"] and "supportive_management" in r["problem"]                    # found, but in another section
    assert A.compare(item(), None)["problem"] == "no step 3 ledger for this case"


def test_compare_prefers_label_over_combination_key():
    led = ledger()
    led["actions"].append(act("PNV-DHA", "existing_targeted_therapies", {"MONDO:1": "conditional"}, key="drug:name:folic acid+pyridoxine"))
    led["actions"].append(act("pyridoxine", "existing_targeted_therapies", {"MONDO:1": "not_applicable"}))
    r = A.compare(item(match="pyridoxine", expect={"status": "not_applicable"}), led)
    assert r["ok"] and [a["label"] for a in r["actual"]] == ["pyridoxine"]


def test_acceptance_page_shows_result_as_is():
    B.LANG = "zh"
    assert "还没有验收结果" in B.acceptance_page(None)
    row = {**item(), "branch": None, "ok": False, "problem": "lumasiran: conditional", "actual": [
        {"action_key": "k", "label": "Drug A", "report": True, "status_by_branch": {"MONDO:1": {"status": "conditional", "reason": "r"}},
         "unknown_requirements": ["eGFR ≥30"]}]}
    res = {"created_at": 1793700000, "code_commit": "abc", "expectations_verified_on": "2026-11-03", "n": 1, "n_ok": 0, "ok": False,
           "cases": {"C": {"created_at": None, "code_commit": None, "prompt_versions": [], "schema_version": None,
                           "ledger_ok": None, "failed_checks": [], "branches": {}}}, "rows": [copy.deepcopy(row)]}
    h = B.acceptance_page(res)
    assert "FAIL" in h and "badrow" in h and "lumasiran: conditional" in h and "eGFR ≥30" in h

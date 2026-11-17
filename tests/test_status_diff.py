"""Status snapshots and approval-gated promotion are offline and never change clinical verdicts."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import status_diff as S
import promote_baseline as P


def action(status="applicable", reason="patient finding matches", evidence="e1"):
    return {"section":"supportive_management","action_key":"procedure:dbs","label":"DBS","applies_to":["B"],
            "status_by_branch":{"B":{"status":status,"reason":reason}},"evidence_ids":[evidence],"requirements":[]}


def ledger(tmp_path, cid="P", actions=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    p=tmp_path/f"{cid}.json"
    p.write_text(json.dumps({"_meta":{"code_commit":"abc","input_fingerprint":"patient1"},
                             "actions":[action()] if actions is None else actions}))
    return p


def test_status_reason_and_evidence_changes_are_all_reported(tmp_path):
    ledger(tmp_path)
    before=S.build_snapshot(tmp_path,["P"],"old")
    ledger(tmp_path,actions=[action("not_applicable","not met: the source recommends this measure","e2")])
    after=S.build_snapshot(tmp_path,["P"],"new")
    row,=S.compare(before,after)["changes"]
    assert (row["case_id"],row["action"],row["branch"],row["old_status"],row["new_status"])==("P","DBS","B","applicable","not_applicable")
    assert row["old_evidence_ids"]==["e1"] and row["new_evidence_ids"]==["e2"]
    assert "the source recommends this measure" in row["change_reason"]
    assert row["review"]=="needs_review"  # a recorded reason is not an approved explanation
    assert "status" in row["changed_fields"]


def test_reason_only_and_evidence_only_changes_are_not_hidden(tmp_path):
    ledger(tmp_path); before=S.build_snapshot(tmp_path,["P"],"old")
    for a,field in [(action(reason="a different rationale"),"reason"),(action(evidence="e2"),"evidence_ids")]:
        ledger(tmp_path,actions=[a]);after=S.build_snapshot(tmp_path,["P"],"new")
        row,=S.compare(before,after)["changes"]
        assert row["kind"]=="details_changed" and row["changed_fields"]==[field]


def test_missing_historical_case_is_explicit_but_missing_current_input_raises(tmp_path):
    ledger(tmp_path,"P");ledger(tmp_path,"RETEST")
    before=S.build_snapshot(tmp_path,["P","RETEST"],"historical",missing=("RETEST",))
    after=S.build_snapshot(tmp_path,["P","RETEST"],"current")
    result=S.compare(before,after);row,=result["changes"]
    assert result["baseline_missing_cases"]==["RETEST"]
    assert row["old_status"] is None and row["kind"]=="baseline_missing"
    assert row["review"]=="not_comparable"
    with pytest.raises(FileNotFoundError):S.build_snapshot(tmp_path,["MISSING"],"current")


def test_missing_branch_status_fails_instead_of_filling_a_default(tmp_path):
    a=action();a["applies_to"].append("C");ledger(tmp_path,actions=[a])
    with pytest.raises(KeyError):S.build_snapshot(tmp_path,["P"],"current")


@pytest.mark.parametrize('field',['applies_to','evidence_ids'])
def test_malformed_id_lists_fail_instead_of_being_read_as_characters(tmp_path,field):
    a=action();a[field]='B' if field=='applies_to' else 'e1';ledger(tmp_path,actions=[a])
    with pytest.raises(ValueError,match='list of nonempty IDs'):S.build_snapshot(tmp_path,['P'],'current')


def test_duplicate_records_preserve_every_grade_and_evidence_id(tmp_path):
    ledger(tmp_path,actions=[action(),action("conditional","unconfirmed scope","e2")])
    row,=S.build_snapshot(tmp_path,["P"],"current")["rows"]
    assert row["status"]=="applicable; conditional"
    assert row["records"]==2 and row["evidence_ids"]==["e1","e2"]


def test_historical_search_none_records_without_newer_flag_remain_distinct(tmp_path):
    a=action("searched_none","searched, none found");a.update(action_key=None,label="None found")
    b=copy.deepcopy(a);b["section"]="existing_targeted_therapies"
    ledger(tmp_path,actions=[a,b])
    rows=S.build_snapshot(tmp_path,["P"],"history")["rows"]
    assert len(rows)==2 and all(r["status"]=="searched_none" for r in rows)
    assert len({r["action_id"] for r in rows})==2


def setup_promotion(tmp_path):
    ledger(tmp_path/"ledgers");before=S.build_snapshot(tmp_path/"ledgers",["P"],"history")
    root=tmp_path/"baselines"
    for name in ("current","historical/step3a.2-accepted"):
        p=root/name/"snapshot.json";p.parent.mkdir(parents=True);p.write_text(json.dumps(before))
    (root/"approvals.md").write_text("# Approved changes\n")
    ledger(tmp_path/"ledgers",actions=[action("conditional","no explicit recommendation","e2")])
    after=S.build_snapshot(tmp_path/"ledgers",["P"],"candidate")
    candidate=tmp_path/"candidate.json";candidate.write_text(json.dumps(after))
    changes=S.compare(before,after)["changes"]
    approval={"date":"2026-11-17","commit":"abc","approver":"test fixture approver","reason":"test fixture approval",
              "baseline_sha256":S.digest((root/"current/snapshot.json").read_bytes()),"candidate_sha256":S.digest(candidate.read_bytes()),
              "approved_changes":[{"change_id":r["change_id"],"approved":True,"reason":"explicit fixture approval"} for r in changes]}
    return root,candidate,approval


@pytest.mark.parametrize("bad",["missing_change","unapproved","wrong_candidate","wrong_baseline","wrong_commit","missing_reason"])
def test_promotion_rejects_unapproved_or_stale_changes_without_writing(tmp_path,bad):
    root,candidate,approval=setup_promotion(tmp_path)
    before=(root/"current/snapshot.json").read_bytes();log=(root/"approvals.md").read_bytes()
    if bad=="missing_change":approval["approved_changes"]=[]
    elif bad=="unapproved":approval["approved_changes"][0]["approved"]=False
    elif bad=="wrong_candidate":approval["candidate_sha256"]="wrong"
    elif bad=="wrong_baseline":approval["baseline_sha256"]="wrong"
    elif bad=="wrong_commit":approval["commit"]="another commit"
    else:approval["approved_changes"][0]["reason"]=""
    with pytest.raises(ValueError):P.promote(candidate,approval,"abc",root)
    assert (root/"current/snapshot.json").read_bytes()==before
    assert (root/"approvals.md").read_bytes()==log


def test_explicit_promotion_appends_audit_and_never_writes_history(tmp_path):
    root,candidate,approval=setup_promotion(tmp_path)
    history=root/"historical/step3a.2-accepted/snapshot.json";original=history.read_bytes()
    P.promote(candidate,approval,"abc",root)
    assert (root/"current/snapshot.json").read_bytes()==candidate.read_bytes()
    assert history.read_bytes()==original
    log=(root/"approvals.md").read_text()
    assert log.startswith("# Approved changes\n")
    for text in ("2026-11-17","abc","test fixture approver","explicit fixture approval","DBS","applicable","conditional"):
        assert text in log


def test_promotion_rejects_a_candidate_that_silently_drops_a_case(tmp_path):
    root,candidate,approval=setup_promotion(tmp_path)
    data=json.loads(candidate.read_text());data['cases']={};candidate.write_text(json.dumps(data))
    approval['candidate_sha256']=S.digest(candidate.read_bytes())
    old=(root/'current/snapshot.json').read_bytes()
    with pytest.raises(ValueError,match='complete baseline case set'):P.promote(candidate,approval,'abc',root)
    assert (root/'current/snapshot.json').read_bytes()==old


def test_additions_and_removals_are_reported(tmp_path):
    ledger(tmp_path);old=S.build_snapshot(tmp_path,["P"],"old")
    changed=action();changed["action_key"]="procedure:other";changed["label"]="Other action"
    ledger(tmp_path,actions=[changed]);new=S.build_snapshot(tmp_path,["P"],"new")
    assert S.compare(old,new)["counts"]=={"action_removed":1,"action_added":1}

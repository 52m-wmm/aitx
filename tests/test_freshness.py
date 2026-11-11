"""Acceptance freshness (2026-11-05): outputs from other code or older upstream files are not scored."""
import hashlib
import json

from aitx import runmeta as R

CASE = {"id": "PRAC-X", "patient": {"a": 1}}


def _write(tmp_path, step, obj):
    p = R.path(step, "PRAC-X", tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj)
    p.write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "case_versions", lambda cid: [CASE])
    h1 = _write(tmp_path, 1, {"s": 1})
    meta = {"input_fingerprint": R.fingerprint(CASE), "upstream": {"1": h1}, "code_fingerprint": "C", "code_commit": "abc"}
    _write(tmp_path, 3, {"_meta": meta})
    return meta


def test_fresh(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert R.freshness(3, "PRAC-X", tmp_path, code="C") == {"fresh": True, "reasons": []}


def test_other_code_is_stale(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    f = R.freshness(3, "PRAC-X", tmp_path, code="D")
    assert not f["fresh"] and "other code" in f["reasons"][0]


def test_missing_fingerprint_is_stale(monkeypatch, tmp_path):
    meta = _setup(monkeypatch, tmp_path)
    _write(tmp_path, 3, {"_meta": {k: v for k, v in meta.items() if k != "code_fingerprint"}})
    assert "no code fingerprint" in R.freshness(3, "PRAC-X", tmp_path, code="C")["reasons"][0]


def test_changed_upstream_is_stale(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _write(tmp_path, 1, {"s": 2})
    assert R.freshness(3, "PRAC-X", tmp_path, code="C")["reasons"] == ["step 1 output changed since"]


def test_other_input_is_stale(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(R, "case_versions", lambda cid: [{"id": "PRAC-X", "patient": {"a": 2}}])
    assert R.freshness(3, "PRAC-X", tmp_path, code="C")["reasons"] == ["made from another case input"]


def test_stale_rows_are_not_scored():
    rows = [{"case": "A", "ok": True, "problem": None}, {"case": "B", "ok": True, "problem": None}]
    R.apply_freshness(rows, {"A": {"fresh": True, "reasons": []}, "B": {"fresh": False, "reasons": ["made by other code"]}})
    assert rows[0]["ok"] and not rows[0]["stale"]
    assert not rows[1]["ok"] and rows[1]["stale"] and rows[1]["problem"].startswith("STALE")


def test_code_fingerprint_changes_with_content(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "aitx").mkdir()
    (tmp_path / "aitx" / "m.py").write_text("x = 1\n")
    a = R.code_fingerprint(tmp_path)
    (tmp_path / "aitx" / "m.py").write_text("x = 2\n")
    assert a != R.code_fingerprint(tmp_path) and a != "unknown"


def test_an_output_from_either_version_of_a_case_is_fresh(monkeypatch, tmp_path):
    """O3 (2026-11-11): a group-A blind case exists in the validation file and, with a `blind` block, in its batch."""
    plain = {"id": "PRAC-X", "patient": {"a": 1}}
    batch = {**plain, "blind": {"group": "A"}}
    monkeypatch.setattr(R, "case_versions", lambda cid: [plain, batch])
    h1 = _write(tmp_path, 1, {"s": 1})
    for version in (plain, batch):
        _write(tmp_path, 3, {"_meta": {"input_fingerprint": R.fingerprint(version), "upstream": {"1": h1},
                                       "code_fingerprint": "C", "code_commit": "abc"}})
        assert R.freshness(3, "PRAC-X", tmp_path, code="C")["fresh"] is True


def test_blind_batches_are_part_of_the_case_lookup():
    assert R.BLIND_CASE_DIR.name == "blind"
    ids = {c["id"] for f in R.BLIND_CASE_DIR.glob("*.json") for c in __import__("json").loads(f.read_text())}
    if ids:
        some = sorted(ids)[0]
        assert R.case_versions(some)

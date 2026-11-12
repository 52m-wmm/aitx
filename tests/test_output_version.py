"""runmeta.version_of_output: score an output against the case version it was run from (fix 2026-11-12)."""
import json

from aitx import runmeta


def _write(tmp_path, case):
    p = runmeta.path(1, case["id"], tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"_meta": {"input_fingerprint": runmeta.fingerprint(case)}}))


def test_picks_the_version_the_output_came_from(tmp_path, monkeypatch):
    a = {"id": "X-1", "patient": {"clinical_context": "from the validation file"}}
    b = {"id": "X-1", "patient": {"clinical_context": "from the blind batch"}, "blind": {"batch": "t"}}
    _write(tmp_path, b)
    monkeypatch.setattr(runmeta, "case_versions", lambda cid, files=None: [a, b])
    got = runmeta.version_of_output(1, a, tmp_path)
    assert got is b
    runmeta.load_output(1, got, tmp_path)          # no StaleOutput


def test_reverse_no_version_matches_stays_stale(tmp_path, monkeypatch):
    a = {"id": "X-1", "patient": {"clinical_context": "v1"}}
    other = {"id": "X-1", "patient": {"clinical_context": "edited after the run"}}
    _write(tmp_path, {"id": "X-1", "patient": {"clinical_context": "something else"}})
    monkeypatch.setattr(runmeta, "case_versions", lambda cid, files=None: [a, other])
    got = runmeta.version_of_output(1, a, tmp_path)
    assert got is a
    try:
        runmeta.load_output(1, got, tmp_path)
        raise AssertionError("expected StaleOutput")
    except runmeta.StaleOutput:
        pass

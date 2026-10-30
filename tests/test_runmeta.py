"""Pipeline restart: step outputs carry provenance; stale or missing outputs are refused."""
import json

import pytest

from aitx import runmeta as M

CASE = {"id": "T-1", "patient": {"genotype": [{"gene": "G", "variant_cdna": "c.1A>G"}], "clinical_context": "x"}}


def test_roundtrip_and_fingerprint(tmp_path):
    h1 = M.write_output(1, CASE, {"variants": []}, out=tmp_path)
    got, h = M.load_output(1, CASE, out=tmp_path)
    assert h == h1 and got["_meta"]["input_fingerprint"] == M.fingerprint(CASE)
    assert got["_meta"]["step"] == 1 and got["_meta"]["code_commit"]


def test_missing_output_is_stale(tmp_path):
    with pytest.raises(M.StaleOutput, match="run from step 1"):
        M.load_output(1, CASE, out=tmp_path)


def test_output_from_other_input_is_stale(tmp_path):
    M.write_output(1, CASE, {"variants": []}, out=tmp_path)
    changed = json.loads(json.dumps(CASE))
    changed["patient"]["clinical_context"] = "y"
    with pytest.raises(M.StaleOutput, match="different case input"):
        M.load_output(1, changed, out=tmp_path)


def test_output_without_provenance_is_stale(tmp_path):
    p = M.path(1, CASE["id"], tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"variants": []}))          # written by an older script, no _meta
    with pytest.raises(M.StaleOutput):
        M.load_output(1, CASE, out=tmp_path)


def test_downstream_built_on_older_upstream_is_stale(tmp_path):
    h1 = M.write_output(1, CASE, {"v": 1}, out=tmp_path)
    M.write_output(2, CASE, {"r": 1}, upstream={1: h1}, out=tmp_path)
    h1b = M.write_output(1, CASE, {"v": 2}, out=tmp_path)            # step 1 rerun, step 2 not
    s2, _ = M.load_output(2, CASE, out=tmp_path)
    with pytest.raises(M.StaleOutput, match="older step 1 output"):
        M.check_upstream(s2, 2, {1: h1b})
    M.check_upstream(s2, 2, {1: h1})                                  # consistent chain passes

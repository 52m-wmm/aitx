"""Accepted-version archives (scripts/tag_accepted.py)."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import tag_accepted as TA  # noqa: E402


def test_archive_copies_results_with_manifest(tmp_path):
    out = tmp_path / "out"
    for rel, text in {"step1/P-1.json": "{\"a\": 1}", "step2/P-1.json": "{}", "step2/sources_manifest.json": "[]",
                      "acceptance_step2.json": "{}", "review/x/index.html": "skip", "viewer_runs/h.jsonl": "skip"}.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    dest = TA.archive("stepX-accepted", "abc1234", "note", out=out, dest_root=tmp_path / "snap")
    m = json.loads((dest / "manifest.json").read_text())
    assert m["tag"] == "stepX-accepted" and m["code_commit"] == "abc1234" and m["note"] == "note"
    assert sorted(m["files"]) == ["acceptance_step2.json", "step1/P-1.json", "step2/P-1.json", "step2/sources_manifest.json"]
    assert m["cases"] == {"P-1": {"step1": hashlib.sha256(b'{"a": 1}').hexdigest(), "step2": hashlib.sha256(b"{}").hexdigest()}}
    assert (dest / "out" / "step1" / "P-1.json").read_text() == '{"a": 1}'
    assert not (dest / "out" / "review").exists() and not (dest / "out" / "viewer_runs").exists()

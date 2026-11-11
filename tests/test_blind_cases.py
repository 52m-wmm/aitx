"""Blind case files carry the description in the field the pipeline reads (2026-11-11: group B was written under
`clinical_description`, which the pipeline never reads, and ran with an empty description)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_blind_cases", ROOT / "scripts" / "build_blind_cases.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)


def test_the_builder_writes_the_field_the_pipeline_reads():
    from aitx import caseinput
    assert B.DESCRIPTION_FIELD == caseinput.FIELD == "clinical_context"
    for f in ("aitx/disease/pipeline.py", "aitx/evidence/patient_facts.py"):
        text = (ROOT / f).read_text()
        assert "caseinput.clinical_context(case)" in text and 'get("clinical_context"' not in text, f


def test_every_blind_case_has_a_nonempty_description_in_that_field():
    for f in sorted((ROOT / "data" / "cases" / "blind").glob("*.json")):
        for c in json.loads(f.read_text()):
            p = c["patient"]
            assert "clinical_description" not in p, (f.name, c["id"])
            assert str(p.get("clinical_context") or "").strip(), (f.name, c["id"])

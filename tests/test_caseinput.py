"""Fix plan O1 (2026-11-11): a missing or empty clinical description stops the run instead of reading as ""."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from aitx import caseinput as CI
from aitx.evidence import patient_facts as PF

ROOT = Path(__file__).resolve().parents[1]


def case(**patient):
    return {"id": "T-1", "patient": {"genotype": [], **patient}}


def test_a_description_is_returned_as_is():
    assert CI.clinical_context(case(clinical_context="Global developmental delay")) == "Global developmental delay"


@pytest.mark.parametrize("patient,why", [
    ({}, "missing"),
    ({"clinical_description": "Global developmental delay"}, "clinical_description"),   # the blind-test mistake
    ({"clinical_context": ""}, "empty"),
    ({"clinical_context": "   \n "}, "empty"),
    ({"clinical_context": None}, "empty"),
])
def test_missing_or_empty_is_an_input_error(patient, why):
    with pytest.raises(CI.MissingDescription) as e:
        CI.clinical_context(case(**patient))
    assert why in str(e.value) and "T-1" in str(e.value)


def test_problems_lists_only_the_bad_cases():
    good, bad = case(clinical_context="x"), {"id": "T-2", "patient": {"genotype": []}}
    assert CI.problems([good]) == [] and len(CI.problems([good, bad])) == 1


def test_patient_facts_refuses_an_empty_description():
    with pytest.raises(CI.MissingDescription):
        PF.extract(case(clinical_context=""), use_cache=True)


def test_run_pipeline_stops_before_any_step(tmp_path):
    f = tmp_path / "cases.json"
    f.write_text(json.dumps([{"id": "T-9", "patient": {"genotype": [{"gene": "X"}], "clinical_description": "y"}}]))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_pipeline.py"), str(f), "--to-step", "1"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == CI.EXIT_CODE
    assert "[INPUT] T-9: patient.clinical_context is missing" in r.stdout and "[OK" not in r.stdout


def test_every_case_file_the_pipeline_runs_is_readable():
    files = list((ROOT / "data" / "cases").rglob("*.json"))
    assert files
    for f in files:
        data = json.loads(f.read_text())
        for c in data if isinstance(data, list) else [data]:
            if "patient" in c:
                assert CI.problems([c]) == [], (f.name, c.get("id"))

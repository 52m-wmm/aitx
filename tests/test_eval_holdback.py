"""The four evaluation cases are held back (decision 2026-11-08).

A run without --case had regenerated three of them. Running them is not itself the harm; looking at what they
produce and tuning to it is, so reaching them has to be deliberate.
"""
import importlib.util
import json
import pathlib

import pytest

from aitx import runmeta

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location("runpipe", ROOT / "scripts" / "run_pipeline.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_eval_ids_come_from_the_file_not_a_name_pattern():
    ids = runmeta.eval_ids()
    assert ids == {c["id"] for c in json.loads((ROOT / "data/cases/aitx_final_patients.json").read_text())}
    assert len(ids) == 4
    assert runmeta.eval_ids(ROOT / "data/cases/does-not-exist.json") == set()


def test_a_run_without_case_leaves_the_evaluation_cases_out(capsys):
    """Reached only through the default file list: they are skipped with a note, not an error."""
    m = _runner()
    got = {c["id"] for c in m.load_cases(None, None)}
    assert got and not (got & m.eval_ids())
    assert any(i.startswith("PRAC-") for i in got)
    assert "HELD BACK" in capsys.readouterr().out


def test_naming_an_evaluation_case_is_refused_without_eval():
    m = _runner()
    one = sorted(m.eval_ids())[0]
    with pytest.raises(SystemExit) as e:
        m.load_cases(None, [one])
    assert "--eval" in str(e.value) and one in str(e.value)
    # and through its own file, too
    with pytest.raises(SystemExit):
        m.load_cases(ROOT / "data/cases/aitx_final_patients.json", None)


def test_eval_flag_lets_them_through():
    m = _runner()
    got = {c["id"] for c in m.load_cases(None, None, include_eval=True)}
    assert m.eval_ids() <= got


def test_acceptance_refuses_evaluation_cases():
    with pytest.raises(SystemExit) as e:
        runmeta.refuse_eval_cases(["PRAC-GRIN2B", sorted(runmeta.eval_ids())[0]], "step 3x acceptance")
    assert "must not use the evaluation case" in str(e.value)
    runmeta.refuse_eval_cases(["PRAC-GRIN2B"])          # practice cases are fine


@pytest.mark.parametrize("name", ["3a", "3b", "3c", "3d", "3e"])
def test_every_step3_acceptance_script_calls_the_guard(name):
    src = (ROOT / "scripts" / f"acceptance_step{name}.py").read_text()
    assert "refuse_eval_cases" in src, f"acceptance_step{name}.py does not guard the evaluation cases"


@pytest.mark.parametrize("name", ["3a", "3b", "3c", "3d", "3e", "3_0"])
def test_no_step3_expectation_or_script_names_an_evaluation_case(name):
    held = runmeta.eval_ids()
    src = (ROOT / "scripts" / f"acceptance_step{name}.py").read_text()
    assert not [i for i in held if i in src], f"acceptance_step{name}.py names an evaluation case"
    spec = ROOT / "data" / "eval" / f"step{name}_expectations.json"
    if spec.exists():
        text = spec.read_text()
        assert not [i for i in held if i in text], f"step{name} expectations name an evaluation case"

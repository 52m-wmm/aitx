"""Blind machine check, record-resolvable: configured guideline URLs resolve, other URLs do not (2026-11-11)."""
import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "scripts" / "blind_machine_check.py"
_spec = importlib.util.spec_from_file_location("blind_machine_check", _p)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

IAP = "https://indianpediatrics.net/epub022022/RECOMM-00406.pdf"


def led(url):
    return {"evidence": [{"id": "e1", "section": "supportive_management", "source": {"type": "url", "id": url}}]}


def test_the_configured_guideline_urls_include_the_l4_guidelines():
    assert IAP in M.configured_guideline_urls()


def test_a_configured_guideline_url_resolves():
    assert M.check_records(led(IAP), online=False) == []


def test_any_other_url_still_fails():
    bad = M.check_records(led("https://example.org/some-page"), online=False)
    assert len(bad) == 1 and bad[0]["check"] == "record-resolvable"


def test_shaped_ids_unaffected():
    assert M.check_records({"evidence": [{"id": "e", "source": {"type": "pmid", "id": "38316953"}}]}, online=False) == []


def test_upstream_health_warns_on_zero(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(M.runmeta, "path", lambda step, cid, out=None: tmp_path / f"{cid}.json")
    (tmp_path / "X.json").write_text(json.dumps({"phenotypes": [], "patient_facts": {"age": {"quote": None}},
                                                 "primary": {"status": "resolved"}}))
    h = M.upstream_health("X")
    assert h["phenotypes"] == 0 and "no phenotypes" in h["warnings"] and "no diagnosis" not in h["warnings"]
    (tmp_path / "Y.json").write_text(json.dumps({"phenotypes": [{"status": "present"}],
                                                 "patient_facts": {"age": {"quote": "3 months"}},
                                                 "primary": {"status": "resolved"}}))
    assert M.upstream_health("Y")["warnings"] == []


def _req(cc=None):
    r = {"id": "r1", "result": "unknown", "patient_status": "unknown",
         "patient_fact": {"field": "source scope", "value": None, "quote": None, "step": None}}
    if cc:
        r["context_check"] = cc
    return {"actions": [{"label": "x", "requirements": [r]}], "missing_information": []}


def test_a_context_check_scope_or_limit_line_is_not_a_missing_variable():
    assert M.check_patient_facts(_req("scope")) == [] and M.check_patient_facts(_req("limit")) == []


def test_reverse_an_ordinary_unknown_line_must_be_listed_as_missing():
    assert M.check_patient_facts(_req()) and M.check_patient_facts(_req("degree"))


def test_a_not_recommended_line_needs_no_patient_quote():
    led = {"actions": [{"label": "x", "requirements": [{"id": "r1", "result": "fail", "patient_status": "does_not_satisfy",
                                                        "patient_fact": {"field": "source scope", "quote": None},
                                                        "context_check": "recommendation"}]}], "missing_information": []}
    assert M.check_patient_facts(led) == []
    led["actions"][0]["requirements"][0].pop("context_check")
    assert M.check_patient_facts(led)                      # reverse: an ordinary unmet line still needs its quote

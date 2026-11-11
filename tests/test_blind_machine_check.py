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

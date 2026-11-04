"""Link check of the 3.0 acceptance: PubMed through E-utilities, every other site by HTTP 200 (2026-11-04)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import acceptance_step3_0 as A  # noqa: E402


def test_pubmed_link_checked_through_esummary():
    assert A.check_url("https://pubmed.ncbi.nlm.nih.gov/16770791/") == \
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id=16770791"
    assert A.check_url("https://www.ncbi.nlm.nih.gov/books/NBK1250/") == "https://www.ncbi.nlm.nih.gov/books/NBK1250/"


def test_esummary_record_must_name_the_pmid_without_error():
    ok = json.dumps({"result": {"uids": ["16770791"], "16770791": {"uid": "16770791", "title": "x"}}})
    unknown = json.dumps({"result": {"uids": ["99999999999"], "99999999999": {"uid": "99999999999", "error": "cannot get document summary"}}})
    assert A.pubmed_record_ok(ok, "16770791")
    assert not A.pubmed_record_ok(unknown, "99999999999")
    assert not A.pubmed_record_ok("<html>Cookies must be enabled</html>", "16770791")


def test_url_ok_uses_esummary_for_pubmed_and_200_elsewhere(monkeypatch):
    seen = []

    def fetch(url):
        seen.append(url)
        if "esummary" in url:
            return json.dumps({"result": {"16770791": {"uid": "16770791"}}})
        return None if "bad" in url else "<html>"
    monkeypatch.setattr(A, "_fetch", fetch)
    assert A.url_ok("https://pubmed.ncbi.nlm.nih.gov/16770791/") and "esummary" in seen[-1]
    assert A.url_ok("https://omim.org/entry/1") and not A.url_ok("https://example.org/bad")


def test_links_only_replaces_only_the_link_item(tmp_path, monkeypatch):
    out = tmp_path / "a.json"
    led = {"evidence": [{"section": "background", "source": {"url": "https://pubmed.ncbi.nlm.nih.gov/1/"}}]}
    out.write_text(json.dumps({"failed": ["3 distinct source links resolve -> [x]", "other check"], "ledgers": {"P": led}}))
    monkeypatch.setattr(A, "OUT", out)
    monkeypatch.setattr(A, "url_ok", lambda u: True)
    assert A.links_only() == 1                                   # the other failure is kept
    assert json.loads(out.read_text())["failed"] == ["other check"]

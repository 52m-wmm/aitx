"""HTTP cache expiry per data source (step 3.0 contract, section 5)."""
import json
import time

import pytest

from aitx import http


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(http, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(http, "FORCE_REFRESH", set())
    monkeypatch.setattr(http, "_refreshed", set())
    calls = []

    class Resp:
        def __init__(self, url):
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return f"fresh {len(calls)}".encode()

    def fake_urlopen(req, timeout=30):
        calls.append(req.full_url)
        return Resp(req.full_url)
    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    return calls


def seed(url, accessed_at):
    path = http._key(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": url, "text": "cached", "accessed_at": accessed_at}))


CT = "https://clinicaltrials.gov/api/v2/studies?query.cond=x"
PM = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=x"


def test_trials_expire_after_one_day(cache):
    seed(CT, int(time.time()) - 2 * 3600)
    f = http.get(CT)
    assert f.text == "cached" and f.from_cache and cache == []          # 2 h old: still fresh
    seed(CT, int(time.time()) - 25 * 3600)
    f = http.get(CT)
    assert not f.from_cache and f.text.startswith("fresh") and cache == [CT]
    assert time.time() - f.accessed_at < 5                                # access time is the real refetch time


def test_other_sources_never_expire(cache):
    old = int(time.time()) - 400 * 24 * 3600
    seed(PM, old)
    f = http.get(PM)
    assert f.from_cache and f.accessed_at == old and cache == []        # accessed_at = the original fetch


def test_force_refresh_refetches_once_per_run(cache):
    seed(CT, int(time.time()) - 60)
    http.FORCE_REFRESH.add("https://clinicaltrials.gov/")
    assert not http.get(CT).from_cache                                     # refetched although fresh
    assert http.get(CT).from_cache and len(cache) == 1                    # not again within the same run
    seed(PM, int(time.time()) - 60)
    assert http.get(PM).from_cache                                         # other sources unaffected

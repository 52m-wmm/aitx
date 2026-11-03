"""HTTP GET with an on-disk cache, using only the standard library.

Every response is cached by URL so that reruns are fast, reproducible, and
the access time of each source is recorded (needed for the evidence ledger
and for the "sources manifest with snapshot date" the organizers ask for).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CACHE_DIR = Path(os.environ.get("AITX_CACHE_DIR", Path.cwd() / ".cache" / "http"))
USER_AGENT = "aitx-challenge-pipeline/0.1 (research)"

# Cache expiry per data source (step 3.0 contract, section 5): URL prefix -> max age in seconds.
# Sources not listed never expire (frozen at submission).
MAX_AGE = {
    "https://clinicaltrials.gov/": 24 * 3600,          # recruiting status and criteria change quickly
}
# URL prefixes to refetch once in this process regardless of age (run_pipeline --refresh-trials)
FORCE_REFRESH: set[str] = set()
_refreshed: set[str] = set()


def max_age(url: str) -> int | None:
    return next((age for prefix, age in MAX_AGE.items() if url.startswith(prefix)), None)


def _stale(url: str, accessed_at: int, now: float | None = None) -> bool:
    if any(url.startswith(p) for p in FORCE_REFRESH) and url not in _refreshed:
        return True
    age = max_age(url)
    return age is not None and (now or time.time()) - accessed_at > age


@dataclass
class Fetched:
    url: str
    text: str
    accessed_at: int      # Unix epoch seconds (UTC) of the original network fetch
    from_cache: bool


def _key(url: str, headers: dict | None = None) -> Path:
    k = url if not headers else url + "\n" + json.dumps(headers, sort_keys=True)
    return CACHE_DIR / (hashlib.sha256(k.encode()).hexdigest() + ".json")


def get(url: str, *, use_cache: bool = True, timeout: int = 30, retries: int = 3,
        headers: dict | None = None) -> Fetched:
    path = _key(url, headers)
    if use_cache and path.exists():
        d = json.loads(path.read_text())
        if not _stale(url, d["accessed_at"]):
            return Fetched(d["url"], d["text"], d["accessed_at"], True)

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read().decode("utf-8", errors="replace")
            accessed = int(time.time())
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"url": url, "text": text, "accessed_at": accessed}))
            _refreshed.add(url)
            return Fetched(url, text, accessed, False)
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                raise RuntimeError(f"HTTP {e.code} for {url}") from e
            last_err = e
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_err}")

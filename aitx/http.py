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
            return Fetched(url, text, accessed, False)
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                raise RuntimeError(f"HTTP {e.code} for {url}") from e
            last_err = e
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_err}")

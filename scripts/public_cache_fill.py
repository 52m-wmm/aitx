"""Missing-only requests for approved free public APIs; never refresh existing cache files."""
from __future__ import annotations
import hashlib
from http.client import HTTPException
import json
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from aitx import http

PREFIXES = (
    'https://rxnav.nlm.nih.gov/REST/',
    'https://api.fda.gov/drug/',
    'https://clinicaltrials.gov/api/',
    'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/',
    'https://api.platform.opentargets.org/api/v4/graphql',
    'https://www.ebi.ac.uk/chembl/api/data/',
)
LOCK = threading.Lock()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('unrecorded redirect refused: '+newurl)


def request(url, *, events, headers=None, body=None, timeout=60, retries=3, opener=None):
    payload = json.dumps(body, sort_keys=True) if body is not None else None
    key_url = url+'#'+hashlib.sha256(payload.encode()).hexdigest() if payload is not None else url
    path = http._key(key_url, headers)
    with LOCK:
        # Existing cached responses remain usable even when old; no request or write.
        if path.exists():
            return http.cached_response(json.loads(path.read_text()))
        if not any(url.startswith(p) for p in PREFIXES):
            raise ValueError('uncached endpoint outside authorized public APIs: '+url)
        opener = opener or urllib.request.build_opener(NoRedirect()).open
        for attempt in range(retries):
            event = {'url': url, 'at': time.time(), 'method': 'POST' if payload is not None else 'GET',
                     'reason': 'HTTP cache file absent', 'cache_path': str(path), 'attempt': attempt+1}
            if payload is not None:event['body_sha256'] = hashlib.sha256(payload.encode()).hexdigest()
            events(event)
            req = urllib.request.Request(url, data=payload.encode() if payload is not None else None,
                                         headers={'User-Agent': http.USER_AGENT, **({'Content-Type':'application/json'} if payload is not None else {}), **(headers or {})})
            try:
                with opener(req, timeout=timeout) as response:
                    content = response.read().decode('utf-8', errors='replace')
                    status = response.status
            except urllib.error.HTTPError as exc:
                content, status = exc.read().decode('utf-8', errors='replace'), exc.code
            except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, HTTPException) as exc:
                events(dict(event, outcome='transport_error', error=str(exc)))
                if attempt+1 == retries:raise
                time.sleep(1.5*(attempt+1));continue
            events(dict(event, outcome='response', http_status=status))
            if status == 429 or status >= 500:
                if attempt+1 == retries:raise RuntimeError(f'HTTP {status} for {url}')
                time.sleep(1.5*(attempt+1));continue
            if status not in (200, 400, 404):raise RuntimeError(f'HTTP {status} for {url}')
            record = {'url': url, 'text': content, 'accessed_at': int(time.time()), 'http_status': status}
            if payload is not None:record['body'] = payload
            if status >= 400:record['error'] = f'HTTP {status} for '+('POST ' if payload is not None else '')+url
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also refuses an external writer racing this process.
            with path.open('x') as stream:json.dump(record, stream)
            result = http.cached_response(record)
            return http.Fetched(result.url, result.text, result.accessed_at, False)
        raise ValueError('retries must be positive')

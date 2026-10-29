"""Downloader: resume after dropped connections, reject truncated files."""
import http.server
import threading
from pathlib import Path

import pytest

from aitx.disease import datasets as D

BODY = b"".join(f"gene{i}\tdisease{i}\n".encode() for i in range(5000))


class FlakyHandler(http.server.BaseHTTPRequestHandler):
    """Serves BODY with Range support; drops every response after `cut` bytes."""
    cut = 20000
    etag = '"v1"'
    requests: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        rng = self.headers.get("Range")
        FlakyHandler.requests.append((rng, self.headers.get("If-Range")))
        start = 0
        if rng and self.headers.get("If-Range") == self.etag:
            start = int(rng.split("=")[1].rstrip("-"))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(BODY) - 1}/{len(BODY)}")
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(len(BODY) - start))
        self.send_header("ETag", self.etag)
        self.end_headers()
        self.wfile.write(BODY[start:start + self.cut])  # then close: client sees IncompleteRead


@pytest.fixture
def server():
    FlakyHandler.requests = []
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FlakyHandler)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}/f.tsv"
    s.shutdown()


def ds(url, min_rows=100):
    return D.Dataset("t", url, "f.tsv", "tsv", min_rows, comment="", ragged=True)


def test_resumes_until_complete(server, tmp_path: Path):
    dest = tmp_path / "f.tsv"
    total = D._download(ds(server), dest, timeout=10)
    assert total == len(BODY)
    assert dest.read_bytes() == BODY
    assert FlakyHandler.requests[0] == (None, None)
    assert all(r[0] and r[1] == '"v1"' for r in FlakyHandler.requests[1:])
    assert not (tmp_path / "f.tsv.part").exists()


def test_changed_upstream_restarts(server, tmp_path: Path):
    dest = tmp_path / "f.tsv"
    (tmp_path / "f.tsv.part").write_bytes(b"stale-bytes")
    (tmp_path / "f.tsv.part.json").write_text('{"validator": "\\"old\\""}')
    D._download(ds(server), dest, timeout=10)
    assert dest.read_bytes() == BODY  # If-Range mismatch -> 200 -> stale bytes discarded


def test_gives_up_without_progress(server, tmp_path: Path):
    FlakyHandler.cut = 0
    try:
        with pytest.raises(Exception):
            D._download(ds(server), tmp_path / "f.tsv", timeout=10, max_resumes=3)
    finally:
        FlakyHandler.cut = 20000


def test_truncated_file_rejected(tmp_path: Path):
    p = tmp_path / "f.tsv"
    p.write_bytes(BODY[:30000])
    with pytest.raises(D.IntegrityError):
        D.validate(ds("x"), p, expected_bytes=len(BODY))
    with pytest.raises(D.IntegrityError):
        D.validate(ds("x", min_rows=4000), p)

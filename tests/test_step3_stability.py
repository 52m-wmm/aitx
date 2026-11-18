import json
import pytest
from aitx import http
from scripts import step3_stability as S


def test_frozen_http_replays_known_errors_and_never_fetches_missing(tmp_path,monkeypatch):
    monkeypatch.setattr(http,'CACHE_DIR',tmp_path/'http')
    monkeypatch.setattr(http,'get',http.get)
    path=http._key('https://example.test/known')
    snapshot=tmp_path/'snapshot.json'
    snapshot.write_text(json.dumps({'/old/cache/'+path.name:{'url':'https://example.test/known','error':'HTTP 404 for source'}}))
    S.fixed_http(tmp_path,snapshot)
    with pytest.raises(RuntimeError,match='HTTP 404'):
        http.get('https://example.test/known')
    with pytest.raises(S.FixedInputMissing,match='fixed database cache missing'):
        http.get('https://example.test/missing')

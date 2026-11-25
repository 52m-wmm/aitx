import io
import json
import urllib.error
import pytest
from aitx import http
from scripts.public_cache_fill import request

URL='https://api.fda.gov/drug/label.json?search=fixture'


def test_existing_expired_cache_is_never_requested_or_rewritten(tmp_path, monkeypatch):
    monkeypatch.setattr(http,'CACHE_DIR',tmp_path)
    url='https://clinicaltrials.gov/api/v2/studies/fixture'
    path=http._key(url);raw=json.dumps({'url':url,'text':'cached','accessed_at':1});path.write_text(raw)
    result=request(url,events=lambda e:pytest.fail('cache hit must not request'),opener=lambda *a,**k:pytest.fail('network'))
    assert result.text=='cached' and result.from_cache and path.read_text()==raw


def test_404_is_persisted_and_replayed_without_changing_transport_semantics(tmp_path, monkeypatch):
    monkeypatch.setattr(http,'CACHE_DIR',tmp_path);events=[];calls=[]
    def open404(req,**kwargs):
        calls.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url,404,'not found',{},io.BytesIO(b'{"error":{"code":"NOT_FOUND"}}'))
    with pytest.raises(RuntimeError,match='HTTP 404'):request(URL,events=events.append,opener=open404)
    with pytest.raises(RuntimeError,match='HTTP 404'):request(URL,events=events.append,opener=open404)
    monkeypatch.setattr(http.urllib.request,'urlopen',lambda *a,**k:pytest.fail('cached error must not request'))
    with pytest.raises(RuntimeError,match='HTTP 404'):http.get(URL)
    assert len(calls)==1 and events[0]['reason']=='HTTP cache file absent'
    assert json.loads(http._key(URL).read_text())['http_status']==404


def test_missing_deepseek_endpoint_is_refused_without_request(tmp_path, monkeypatch):
    monkeypatch.setattr(http,'CACHE_DIR',tmp_path)
    with pytest.raises(ValueError,match='outside authorized'):
        request('https://api.deepseek.com/chat/completions',events=lambda e:pytest.fail('must not request'))
    assert not list(tmp_path.iterdir())


def test_graphql_post_uses_body_cache_key_and_writes_once(tmp_path, monkeypatch):
    monkeypatch.setattr(http,'CACHE_DIR',tmp_path);calls=[]
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self):return b'{"data":{}}'
    def opened(req,**kwargs):calls.append(req.data);return Response()
    url='https://api.platform.opentargets.org/api/v4/graphql';body={'query':'fixture'}
    first=request(url,body=body,events=lambda e:None,opener=opened)
    second=request(url,body=body,events=lambda e:None,opener=opened)
    assert not first.from_cache and second.from_cache and len(calls)==1
    monkeypatch.setattr(http.urllib.request,'urlopen',lambda *a,**k:pytest.fail('cached POST must not request'))
    assert http.post_json(url,body).text=='{"data":{}}'


def test_socket_timeout_retries_are_each_logged_without_partial_cache(tmp_path, monkeypatch):
    import socket
    from scripts import public_cache_fill as F
    monkeypatch.setattr(http,'CACHE_DIR',tmp_path)
    monkeypatch.setattr(F.time,'sleep',lambda _:None)
    events=[];attempts=[]
    def timed_out(req,**kwargs):
        attempts.append(req.full_url)
        raise socket.timeout('fixture timeout')
    with pytest.raises(socket.timeout):request(URL,events=events.append,opener=timed_out,retries=2)
    assert len(attempts)==2
    assert len([e for e in events if 'outcome' not in e])==2
    assert not http._key(URL).exists()

import json
import pytest
from aitx import http,llm
from aitx.evidence import actions as A
from scripts.step3_preflight import frozen_io, probe_name, save_raw


def test_real_normalizer_cold_fda_is_reported_without_network(tmp_path):
    cache=tmp_path/'http';cache.mkdir()
    url=A.RXNAV+'/rxcui.json?name=trixhexyphenidyl&search=2'
    import hashlib
    (cache/(hashlib.sha256(url.encode()).hexdigest()+'.json')).write_text(json.dumps({'url':url,'text':'{"idGroup":{}}','accessed_at':1}))
    with frozen_io(cache,{}) as trace:
        result=probe_name('trixhexyphenidyl',trace)
        assert result['status']=='incomplete'
        assert trace[0]['rxcuIs']==[]
        assert trace[-1]['url'].startswith(A.OPENFDA_LABEL)
        assert trace[-1]['status']=='missing'
        with pytest.raises(LookupError):
            http.post_json('https://example.test',{})
        with pytest.raises(LookupError):
            llm.chat([])


def test_raw_actions_and_classification_survive_later_failure(tmp_path):
    answer={'content':json.dumps({'items':[{'name':'phrase','kind':'avoid','classification':'not_graded'}]}),'served_model':'test'}
    save_raw(tmp_path,'key',[{'role':'user','content':'fixed source'}],answer)
    with frozen_io(tmp_path,{}) as trace:
        assert probe_name('phrase',trace)['status']=='incomplete'
    p=tmp_path/'raw_extractions/key.json'
    d=json.loads(p.read_text())
    assert d['parsed']['items'][0]['classification']=='not_graded'
    assert d['complete'] is False and d['safety_validation']=='incomplete'
    assert not (tmp_path/'result.json').exists()


def test_offline_guard_blocks_lower_level_network(tmp_path):
    import socket
    import urllib.request
    with frozen_io(tmp_path,{}):
        with pytest.raises(LookupError,match='forbidden'):
            urllib.request.urlopen('https://example.test')
        with socket.socket() as sock:
            with pytest.raises(LookupError,match='forbidden'):
                sock.connect(('127.0.0.1',443))


def test_recorded_fda_negative_is_not_a_cache_gap(tmp_path):
    import urllib.parse
    rx=A.RXNAV+'/rxcui.json?'+urllib.parse.urlencode({'name':'phrase','search':2})
    fda=A.OPENFDA_LABEL+'?'+urllib.parse.urlencode({'search':'openfda.brand_name:"PHRASE"','limit':1})
    chem=A.CHEMBL_SEARCH+'?'+urllib.parse.urlencode({'q':'phrase','limit':10})
    def record(url,text): return {'url':url,'text':text,'accessed_at':1}
    snapshot={http._key(rx).name:record(rx,'{"idGroup":{}}'),
              http._key(fda).name:{'url':fda,'error':'HTTP 404 for source'},
              http._key(chem).name:record(chem,'{"molecules":[]}')}
    with frozen_io(tmp_path,snapshot) as trace:
        result=probe_name('phrase',trace)
    assert result['status']=='dependencies_available'
    assert result['normalization']['normalized'] is False
    assert trace[1]['recorded_error']=='HTTP 404 for source'

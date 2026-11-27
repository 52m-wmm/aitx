import json
from types import SimpleNamespace
from urllib.parse import parse_qs,urlparse
import pytest
from aitx import http
from aitx.disease import live as L,resolve as R
from tests.test_disease import _summary


def test_three_queries_merge_ids_and_keep_matching_rules(monkeypatch):
    terms=[];summary_ids=[]
    rows=[_summary('11010','NM_000531.6(OTC):c.386G>A (p.Arg129His)','Pathogenic',
                   rs='criteria provided, multiple submitters, no conflicts',
                   traits=[('OTC deficiency',[{'db_source':'MONDO','db_id':'MONDO:0010703'}])]),
          _summary('161330','NM_000531.6(OTC):c.385C>T (p.Arg129Cys)','Pathogenic')]
    def get(url,**kw):
        q=parse_qs(urlparse(url).query)
        if 'esearch' in url:
            term=q['term'][0];terms.append(term)
            ids=[] if term.startswith('NM_000531.5:') else ['161330','11010']
            body={'esearchresult':{'count':str(len(ids)),'idlist':ids}}
        else:
            summary_ids.extend(q['id'][0].split(','))
            body={'result':{'uids':['161330','11010'],**{r['uid']:r for r in rows}}}
        return http.Fetched(url,json.dumps(body),int(L.time.time()),True)
    monkeypatch.setattr(L,'_polite_get',get)
    monkeypatch.setattr(L,'_cds',lambda acc:'A'*1065)
    r=L.clinvar_lookup('NM_000531.5','c.386G>A',gene='OTC')
    assert terms==['NM_000531.5:c.386G>A','NM_000531:c.386G>A','OTC c.386G>A']
    assert summary_ids==['161330','11010']  # duplicate hits fetched only once
    assert [v.vcv for v in r.records]==['VCV000011010']
    assert r.records[0].match=='cds_identical_version' and r.records[0].stars==2
    assert [v['vcv'] for v in r.rejected]==['VCV000161330']
    records=[v.to_dict() for v in r.records]
    c=R.Candidate('MONDO:0010703','OTC')
    links=R.clinvar_links([{'query':r.query,'records':records}],[c],SimpleNamespace(to_mondo={}))
    assert links[c.key][0]['vcv']=='VCV000011010'


def test_all_three_searches_run_even_if_first_has_hit(monkeypatch):
    terms=[]
    def get(url,**kw):
        q=parse_qs(urlparse(url).query)
        if 'esearch' in url:
            terms.append(q['term'][0]);ids=['1'] if len(terms)==1 else ['2']
            body={'esearchresult':{'count':'1','idlist':ids}}
        else:
            assert q['id']==['1,2']
            rows=[_summary(i,'NM_1.1(G):c.1A>G') for i in ['1','2']]
            body={'result':{'uids':['1','2'],**{r['uid']:r for r in rows}}}
        return http.Fetched(url,json.dumps(body),int(L.time.time()),True)
    monkeypatch.setattr(L,'_polite_get',get)
    r=L.clinvar_lookup('NM_1.1','c.1A>G',gene='G')
    assert len(terms)==3 and len(r.records)==2


@pytest.mark.parametrize('age,empty,refresh',[(86400,True,True),(86399,True,False),(86401,False,False)])
def test_only_expired_empty_clinvar_search_refetched(tmp_path,monkeypatch,age,empty,refresh):
    now=2000000;monkeypatch.setattr(L.time,'time',lambda:now)
    monkeypatch.setattr(http,'CACHE_DIR',tmp_path)
    monkeypatch.setattr(L.time,'sleep',lambda _:None)
    url=L.EUTILS+'esearch.fcgi?db=clinvar&retmode=json&retmax=50&term=NM_1.1%3Ac.1A%3EG'
    body={'esearchresult':{'count':'0' if empty else '1','idlist':[] if empty else ['1']}}
    http._key(url).write_text(json.dumps({'url':url,'text':json.dumps(body),'accessed_at':now-age}))
    network=[]
    class Response:
        def __init__(self,text):self.text=text
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self):return self.text.encode()
    def open_url(req,timeout=30):
        network.append(req.full_url)
        if 'esummary' in req.full_url:
            r=_summary('1','NM_1.1(G):c.1A>G')
            data={'result':{'uids':['1'],'1':r}}
        else:data={'esearchresult':{'count':'0','idlist':[]}}
        return Response(json.dumps(data))
    monkeypatch.setattr(http.urllib.request,'urlopen',open_url)
    L.clinvar_lookup('NM_1.1','c.1A>G',gene='G')
    assert (url in network)==refresh
    saved=json.loads(http._key(url).read_text())
    assert saved['accessed_at']==(now if refresh else now-age)


def test_empty_result_all_queries_no_summary_and_no_negative_diagnosis(monkeypatch):
    calls=[]
    def get(url,**kw):
        calls.append(url);assert 'esearch' in url
        return http.Fetched(url,json.dumps({'esearchresult':{'count':'0','idlist':[]}}),int(L.time.time()),True)
    monkeypatch.setattr(L,'_polite_get',get)
    result=L.clinvar_lookup('NM_1.1','c.1A>G',gene='G')
    assert len(calls)==3 and result.status=='not_found' and result.records==[]


def test_pagination_is_not_silently_truncated(monkeypatch):
    def get(url,**kw):
        q=parse_qs(urlparse(url).query)
        if 'esearch' in url:
            start=int(q.get('retstart',['0'])[0]);ids=[str(i) for i in range(start+1,min(start+50,51)+1)]
            data={'esearchresult':{'count':'51','idlist':ids}}
        else:
            ids=q['id'][0].split(',');assert len(ids)==51
            rows=[_summary(i,'NM_1.1(G):c.1A>G') for i in ids]
            data={'result':{'uids':ids,**{r['uid']:r for r in rows}}}
        return http.Fetched(url,json.dumps(data),int(L.time.time()),True)
    monkeypatch.setattr(L,'_polite_get',get)
    r=L.clinvar_lookup('NM_1.1','c.1A>G',gene='G')
    assert len(r.searches)==6 and len(r.records)==51


def test_missing_or_inconsistent_search_response_fails(monkeypatch):
    for data in [{'esearchresult':{'count':'1','idlist':[]}}, {'esearchresult':{'count':'0'}}]:
        monkeypatch.setattr(L,'_polite_get',lambda url,**kw:http.Fetched(url,json.dumps(data),int(L.time.time()),True))
        with pytest.raises((ValueError,KeyError)):
            L.clinvar_lookup('NM_1.1','c.1A>G',gene='G')


@pytest.mark.parametrize('match,significance',[('version_mismatch','Pathogenic'),('exact','Uncertain significance'),('exact','Benign')])
def test_existing_pathogenicity_and_version_filters_still_apply(match,significance):
    rec={'match':match,'clinical_significance':significance,'traits':[{'generic':False,'xrefs':['MONDO:1']}]}
    links=R.clinvar_links([{'records':[rec]}],[R.Candidate('MONDO:1','G')],SimpleNamespace(to_mondo={}))
    assert not links and not rec['used_for_ranking'] and rec['mapped_candidates']==['MONDO:1']

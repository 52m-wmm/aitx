import pytest
from aitx.evidence import established as E


def test_structural_chunks_cover_every_character_once():
    text='Subheading: A\nParagraph 1: abc\nRow 1: [Treatment: X] [Condition: Y]\nParagraph 2: xyz\n'
    chunks=E.extraction_chunks(text,50)
    assert ''.join(c['text'] for c in chunks)==text
    assert chunks[0]['start']==0 and chunks[-1]['end']==len(text)
    assert all(a['end']==b['start'] for a,b in zip(chunks,chunks[1:]))
    assert all(c['end']-c['start']<=50 for c in chunks)
    assert any('Row 1: [Treatment: X] [Condition: Y]\n' in c['text'] for c in chunks)

def test_oversize_atomic_row_stops_instead_of_truncating():
    with pytest.raises(ValueError,match='unit'):E.extraction_chunks('Row 1: '+('x'*60),50)

def test_long_multisection_text_lossless():
    text=''.join('Paragraph '+str(i)+': '+('abc '*140)+'\n' for i in range(15))
    chunks=E.extraction_chunks(text)
    assert len(chunks)>1
    assert ''.join(c['text'] for c in chunks)==text
    assert all(len(c['text'])<=3500 for c in chunks)
    assert all(a['end']==b['start'] for a,b in zip(chunks,chunks[1:]))

def test_chunk_items_keep_real_call_provenance_for_existing_assembly(monkeypatch):
    seen=[]
    def fake(system,user,use_cache,what):
        seen.append(user)
        return {'items':[{'name':'same action','quote':user.split('\n',1)[1]}]}, {'call_id':str(len(seen))}
    monkeypatch.setattr(E,'_llm',fake)
    text='Paragraph 1: '+('a'*2000)+'\nParagraph 2: '+('b'*2000)+'\n'
    parsed,pb=E.extract_section('Management',text,True,'NBK1')
    assert len(seen)==2
    assert [x['_chunk_llm']['call_id'] for x in parsed['items']]==['1','2']
    assert ''.join(u.split('\n',1)[1] for u in seen)==text
    assert len(pb['chunk_calls'])==2

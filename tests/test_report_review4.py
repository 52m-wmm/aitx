import xml.etree.ElementTree as ET

from aitx.evidence import genereviews as G
from aitx.report import assemble as A,validate as V
from tests.test_report import act,build,ev,ledger,unk


def test_ranking_uses_section_and_source_order_not_status_or_name():
    actions=[act('drug:t2','existing_targeted_therapies','Z conditional','conditional'),
             act('drug:t1','existing_targeted_therapies','A applicable','applicable'),
             act('procedure:s','supportive_management','Support','applicable'),
             act('avoid:x','contraindications_precautions','Avoid X','applicable')]
    actions[0]['source_order']=[0,0,1];actions[1]['source_order']=[0,0,2]
    md,_=build(ledger(actions));ranking=md.split('**Ranking**:',1)[1].split('**Evidence table**',1)[0]
    assert ranking.index('Z conditional')<ranking.index('A applicable')<ranking.index('Support')
    assert 'Avoid X' not in ranking
    summary=md.split('- **Tier 1:**',1)[1].split('- **Tier 2:**',1)[0]
    assert summary.index('Z conditional')<summary.index('A applicable')<summary.index('Support')


def test_summary_includes_off_label_entry_when_there_is_no_trial():
    a=act('drug:q','off_label_expanded_access','coenzyme Q10','applicable')
    led=ledger([a]);md,_=build(led)
    summary=md.split('- **Tier 2:**',1)[1].split('- **Tier 3:**',1)[0]
    assert 'coenzyme Q10' in summary and 'not recorded' not in summary
    bad=md.replace(summary,'\n  - Source-backed priority action not recorded; unable to assess.\n',1)
    assert any('Summary Tier 2' in e for e in V.check_report(bad,led,'P'))


def test_hidden_actions_do_not_enter_summary_missing_information_or_safety_coverage():
    hidden=act('drug:h','supportive_management','hidden drug','not_applicable')
    shown=act('drug:s','supportive_management','shown drug','conditional',[unk('kidney function',field='kidney function')])
    led=ledger([hidden,shown]);led['missing_information']=[{'variable':'kidney function','affects':['shown drug','hidden drug']}]
    safety={'coverage':[{'drug':name,'interactions_checked':False,'contraindications_checked':False,'evidence_ids':['e1']}
                        for name in ('hidden drug','shown drug')]}
    md,_=A.assemble(led,{'id':'P'},lambda *args:None,safety)
    summary=md.split('## Summary',1)[1].split('## Tier 1:',1)[0]
    assert 'hidden drug' not in summary and 'shown drug' in summary


def test_superscript_citations_are_bracketed_without_changing_units_or_extraction(monkeypatch,tmp_path):
    path=tmp_path/'chapter.xml'
    path.write_text('<book><p>Consider riluzole (100 mg/d <sup>3</sup>), monitor tests.</p>'
                    '<p>Target 30 m<sup>2</sup> and 2 L/day<sup>4</sup>.</p></book>')
    monkeypatch.setattr(G,'extract_chapters',lambda ids:{'NBK-test':path});G._footnote_views.cache_clear()
    assert G._text(ET.parse(path).getroot()[0])=='Consider riluzole (100 mg/d 3), monitor tests.'
    assert G.display_quote('NBK-test','Consider riluzole (100 mg/d 3), monitor tests.')=='Consider riluzole (100 mg/d [3]), monitor tests.'
    assert G.display_quote('NBK-test','Target 30 m2 and 2 L/day4.')=='Target 30 m2 and 2 L/day [4].'
    G._footnote_views.cache_clear()


def test_report_uses_verified_display_quote_and_keeps_evidence_id():
    led=ledger([act('drug:r','supportive_management','riluzole','applicable')])
    led['evidence'][0]['quote']='Use 100 mg/d 3.';led['evidence'][0]['display_quote']='Use 100 mg/d [3].'
    md,_=build(led)
    assert 'Use 100 mg/d [3].' in md and '[E:e1]' in md
    assert not V.check_report(md,led,'P')
    led['evidence'][0]['display_quote']+=' It cures the disease.'
    assert any('display quote changes source content' in e for e in V.check_report(md,led,'P'))

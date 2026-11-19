import xml.etree.ElementTree as ET
from scripts.build_structure_maps import observe,TEMPLATES


def chapter(body):return ET.fromstring('<book-part-wrapper><book-part><book-part-meta><abstract><sec><title>Management</title><p>summary excluded</p></sec></abstract></book-part-meta><body><sec id="m"><title>Management</title>'+body+'</sec></body></book-part></book-part-wrapper>')

def test_disjoint_body_table_lists_and_template_units():
    root=chapter('<p>Free prose here.</p><p>'+TEMPLATES['ddid-intro']+'</p><list><list-item><p>Parent own.</p><list><list-item><p>Child only.</p></list-item></list></list-item></list><table-wrap id="t"><caption><p>Caption not body.</p></caption><table><thead><tr><th>Measure</th></tr></thead><tbody><tr><td><list><list-item><p>Table list text.</p></list-item></list></td></tr></tbody></table></table-wrap>')
    m=observe(root,'NBK1');c=m['counts']
    assert c['free_paragraphs']==1 and c['free_words']==3 and c['template_paragraphs']==1
    assert c['table_rows']==1 and c['list_items']==2 and c['table_internal_list_items']==1
    assert sorted(l['depth'] for l in m['lists'] if not l['in_table'])==[1,2]
    assert m['tables'][0]['columns']==['Measure']
    assert sum(u['words'] for u in m['units'] if u['kind']=='list item')==4
    anchors=[u['anchor'] for u in m['units']];assert len(anchors)==len(set(anchors))
    assert m==observe(root,'NBK1')


def test_atypical_header_and_missing_tbody_have_source_locations():
    m=observe(chapter('<table-wrap><table><thead><tr><td>Name</td></tr><tr><th>Detail</th></tr></thead><tr><td>Content</td></tr></table></table-wrap>'),'NBK2')
    assert m['tables'][0]['body_rows']==1 and m['tables'][0]['current_render_rows']==0
    assert any('outside tbody' in x['reason'] for x in m['issues'])
    assert any('multi-row' in x['reason'] for x in m['issues'])
    assert all(x['xpath'] and x['anchor'] for x in m['issues'])


def test_management_overview_heading_and_bold_context_not_double_counted():
    root=chapter('<p><bold>Adults.</bold></p><p><bold>Children.</bold> Their body text.</p><sec><title>Subsection</title><p>More.</p></sec>')
    m=observe(root,'NBK3')
    assert m['counts']['management_roots']==1 and m['counts']['bold_subheadings']==1
    assert m['counts']['paragraph_leadins']==1 and m['counts']['free_paragraphs']==2
    assert [h['title'] for h in m['headings'] if h['kind']=='section']==['Management','Subsection']

def test_inline_whitespace_matches_existing_parser_view():
    from scripts.build_structure_maps import own_text
    from aitx.evidence import genereviews as G
    p=ET.fromstring('<p>A<italic> gene </italic>has effects.</p>')
    assert own_text(p)==G._text(p)=='A gene has effects.'

def test_section_words_forms_rowspan_labels_hpo_and_review_markers():
    from types import SimpleNamespace
    from scripts.build_structure_maps import review_sections,pattern_of
    from aitx.evidence import genereviews as G
    root=chapter('<sec><title>Evaluations Following Initial Diagnosis</title><table-wrap><table><thead><tr><th>Concern</th><th>Measure</th></tr></thead><tbody><tr><td rowspan="2">Seizures</td><td>Test A</td></tr><tr><td>Test B</td></tr></tbody></table></table-wrap></sec><sec><title>Treatment</title><p><bold>Physical therapy.</bold> Supporting text.</p><list><list-item><p>One item.</p></list-item></list></sec>')
    ont=SimpleNamespace(exact_lookup=lambda t:['HP:1'] if t.lower()=='seizures' else [],terms={'HP:1':SimpleNamespace(label='Seizures')})
    sections=review_sections(root,'NBK4',ont,G._text)
    evaluation=next(s for s in sections if s['title'].startswith('Evaluations'))
    rows=evaluation['table_rows'][0]['rows']
    assert [r['row_label'] for r in rows]==['Seizures','Seizures']
    assert all(r['hpo']['match']=='是' for r in rows)
    assert evaluation['non_treatment_sections']==['Evaluations']
    treatment=next(s for s in sections if s['title']=='Treatment')
    assert treatment['bold_labels'][0]['text']=='Physical therapy.'
    assert treatment['bold_labels'][0]['hpo']['match']=='否'
    assert treatment['lists'][0]['items'][0]['text']=='One item.'
    assert treatment['words']==6
    assert pattern_of(sections)=='汇总表+标签段落'
    assert pattern_of([s for s in sections if not s['non_treatment_sections']])=='粗体标签+段落（无汇总表）'


def test_section_count_preserves_xml_block_word_boundaries():
    from scripts.build_structure_maps import structural_text
    assert structural_text(ET.fromstring('<td><p>First</p><p>Second</p></td>'))=='First Second'

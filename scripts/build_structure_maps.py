"""Observe cached GeneReviews Management XML. No pipeline execution, model calls or downloads."""
import hashlib,json,re,subprocess,sys
from collections import Counter,defaultdict
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aitx.disease import datasets as D
from aitx.evidence import genereviews as G
from scripts.status_diff import case_ids
OUT=ROOT/'docs/structure_maps'
TARGETS=('NBK493766','NBK1283','NBK1138')
LISTS={'list','def-list'};ITEMS={'list-item','def-item'}
TEMPLATES={
 'ddid-intro':'The following information represents typical management recommendations for individuals with developmental delay / intellectual disability',
 'early-intervention':'Referral to an early intervention program is recommended for access to occupational, physical, speech, and feeding therapy',
 'early-intervention-us':'early intervention is a federally funded program available in all states',
 'developmental-preschool':'In the US, developmental preschool through the local public school district is recommended',
 'iep-qualification':'an individualized education plan (IEP) is developed for those who qualify',
 'iep-services':"speech services will be provided in the IEP to the extent that the need affects the child's access to academic material",
 'dda-enrollment':'Developmental Disabilities Administration (DDA) enrollment is recommended',
 'feeding-oral-motor':'Assuming that the individual is safe to eat by mouth, feeding therapy',
 'aba':'Children may qualify for and benefit from interventions such as applied behavior analysis (ABA)',
}

def norm(t):return ' '.join(t.lower().split())
def words(t):return len(re.findall(r"\b\w+(?:[-’']\w+)*\b",t))
def matches(t):return [k for k,s in TEMPLATES.items() if norm(s) in norm(t)]

def own_text(e):
    def raw(node):
        parts=[node.text or '']
        for c in node:
            if c.tag not in LISTS|{'table-wrap','sec'}:parts.append((' ' if c.tag in {'p','label'} else '')+raw(c)+(' ' if c.tag in {'p','label'} else ''))
            parts.append(c.tail or '')
        return ''.join(parts)
    return re.sub(r'\s+',' ',raw(e)).strip()


def inventory():
    ids=case_ids()+[c['id'] for c in json.loads((ROOT/'data/cases/blind/20261108.json').read_text())]
    names={x+'.json' for x in ids}|{'step3-'+x+'.json' for x in ids}
    files=[ROOT/p for p in subprocess.run(['rg','--files','--hidden','--no-ignore','out'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.splitlines() if Path(p).name in names]
    files += [p for p in (ROOT/'runs/sessions').glob('*/*/step3.json') if p.parent.name in ids]
    uses=defaultdict(lambda:defaultdict(list));ledgers=[]
    for p in sorted(set(files)):
        d=json.loads(p.read_text())
        if isinstance(d,dict) and 'output' in d:d=d['output']
        if not isinstance(d,dict) or not all(k in d for k in ('patient_id','evidence','actions')):continue
        cid=d['patient_id']
        if cid not in ids:continue
        ledgers.append(str(p.relative_to(ROOT)));nbks={e['source']['id'] for e in d['evidence'] if e['kind']=='sourced' and e['source']['type']=='nbk'}
        if 'supportive_tiers' in d:
            for rec in d['supportive_tiers'].values():
                if 'chapters' in rec:nbks.update(rec['chapters'])
        for n in sorted(nbks):uses[n][cid].append(str(p.relative_to(ROOT)))
    # Canonical inputs are required for all 27 cases; archive absence is not a substitute.
    for cid in ids:
        p=ROOT/'out/step3'/(cid+'.json')
        if not p.exists():raise FileNotFoundError(p)
    return ids,dict(uses),ledgers


def observe(root,nbk):
    parents={c:p for p in root.iter() for c in p};paths={}
    def locate_tree(e,path):
        paths[e]=path;counts=Counter()
        for c in e:
            counts[c.tag]+=1;locate_tree(c,path+'/'+c.tag+'['+str(counts[c.tag])+']')
    locate_tree(root,'/'+root.tag+'[1]')
    def ancestors(e):
        while e in parents:
            e=parents[e];yield e
    def within(e,tags):return any(a.tag in tags for a in ancestors(e))
    def pos(e):return {'xpath':paths[e],'xml_id':e.attrib['id'] if 'id' in e.attrib else None,'anchor':nbk+'-'+hashlib.sha256(paths[e].encode()).hexdigest()[:14]}
    body=root.find('.//body')
    if body is None:raise ValueError('body not found')
    candidates=[e for e in body.iter('sec') if e.find('title') is not None and G._text(e.find('title')).lower().startswith('management')]
    roots=[e for e in candidates if not any(a in candidates for a in ancestors(e))]
    if not roots:raise ValueError('Management body section not found')
    nodes=[e for r in roots for e in r.iter()];active=set(nodes);headings=[];tables=[];lists=[];units=[];issues=[]
    def issue(e,reason):issues.append(dict(pos(e),tag=e.tag,reason=reason))
    def level(e):return sum(a.tag=='sec' and a in active for a in ancestors(e))+(e.tag=='sec')
    for e in nodes:
        if e.tag=='sec':
            title=e.find('title')
            if title is None:issue(e,'section without a title; current renderer cannot name this level')
            else:headings.append(dict(pos(e),level=level(e),kind='section',title=G._text(title)))
        if e.tag=='p' and not within(e,{'table-wrap'}|ITEMS):
            text=own_text(e);first=next(iter(e),None)
            lead=first is not None and first.tag=='bold' and not (e.text or '').strip()
            if lead:
                headings.append(dict(pos(first),level=level(e)+1,kind='bold-only subheading' if G._text(first)==G._text(e) else 'paragraph lead-in',title=G._text(first)))
            if lead and G._text(first)==G._text(e):continue
            if text:
                units.append(dict(pos(e),kind='template paragraph' if matches(text) else 'free paragraph',words=words(text),chars=len(text),templates=matches(text)))
            if e.find('.//list') is not None:issue(e,'list nested inside p: current sections_for_llm flattens it into paragraph text')
        if e.tag in LISTS:
            items=[c for c in e if c.tag in ITEMS];internal=within(e,{'table-wrap'})
            ls=dict(pos(e),kind=e.tag,list_type=e.attrib.get('list-type'),depth=1+sum(a.tag in LISTS for a in ancestors(e)),in_table=internal,items=[])
            for li in items:
                text=own_text(li);entry=dict(pos(li),words=words(text),chars=len(text),templates=matches(text));ls['items'].append(entry)
                if not internal:units.append(dict(entry,kind='list item'))
                if (li.text or '').strip() or any(c.tag not in {'p','list'} for c in li):issue(li,'list-item has content outside p/list; current list renderer ignores that content or structure')
            lists.append(ls)
            if e.tag=='def-list':issue(e,'definition list: current renderer has no list-item representation')
        if e.tag=='table-wrap':
            label=e.find('label');caption=e.find('caption');physical=[t for t in e.iter('table') if next((a for a in ancestors(t) if a.tag=='table-wrap'),None) is e]
            tab=dict(pos(e),label=G._text(label) if label is not None else None,caption=G._text(caption) if caption is not None else None,header_rows=[],rows=[],physical_tables=len(physical))
            if not physical:issue(e,'no XML table (possibly image-only): row/column structure unknown')
            for t in physical:
                for tr in t.iter('tr'):
                    if next(a for a in ancestors(tr) if a.tag=='table') is not t:continue
                    cells=[c for c in tr if c.tag in {'td','th'}]
                    if any(a.tag=='thead' for a in ancestors(tr)):
                        tab['header_rows'].append([{'text':G._text(c),'rowspan':c.attrib.get('rowspan'),'colspan':c.attrib.get('colspan')} for c in cells])
                    elif not any(a.tag=='tfoot' for a in ancestors(tr)):
                        tab['rows'].append(dict(pos(tr),cells=[dict(pos(c),rowspan=c.attrib.get('rowspan'),colspan=c.attrib.get('colspan')) for c in cells]))
                        if not any(a.tag=='tbody' for a in ancestors(tr)):issue(tr,'row outside tbody: current _table_rows does not render it')
            tab['columns']=[c['text'] for c in tab['header_rows'][-1]] if tab['header_rows'] else None
            tab['body_rows']=len(tab['rows']) if physical else None
            tab['current_render_rows']=sum(line.startswith('Row ') for line in G._table_rows(e).splitlines())
            if len(tab['header_rows'])>1:issue(e,'multi-row header: current renderer reduces header hierarchy to last row/fallback th list')
            if tab['columns'] is None:issue(e,'no declared header row; column names unknown')
            if any(c.tag=='td' for c in e.findall('.//thead/tr/td')):issue(e,'thead uses td: current renderer only takes th header text')
            if parents[e].tag not in {'sec','table-wrap-group'}:issue(e,'table in wrapper: current renderer may fall back to plain text instead of table rows')
            if tab['body_rows'] is not None and tab['body_rows']!=tab['current_render_rows']:issue(e,'observed body row count differs from current rendered rows')
            tables.append(tab)
    counts={'management_roots':len(roots),'section_headings':sum(h['kind']=='section' for h in headings),'bold_subheadings':sum(h['kind']=='bold-only subheading' for h in headings),'paragraph_leadins':sum(h['kind']=='paragraph lead-in' for h in headings),
            'tables':len(tables),'table_rows':sum(t['body_rows'] for t in tables if t['body_rows'] is not None),'unknown_table_rows':sum(t['body_rows'] is None for t in tables),
            'lists_outside_tables':sum(not l['in_table'] for l in lists),'list_items':sum(len(l['items']) for l in lists if not l['in_table']),'table_internal_list_items':sum(len(l['items']) for l in lists if l['in_table']),
            'free_paragraphs':sum(u['kind']=='free paragraph' for u in units),'free_words':sum(u['words'] for u in units if u['kind']=='free paragraph'),'free_chars':sum(u['chars'] for u in units if u['kind']=='free paragraph'),
            'template_paragraphs':sum(u['kind']=='template paragraph' for u in units),'template_hits':sum(bool(u['templates']) for u in units),'template_signatures':sum(len(u['templates']) for u in units),'issues':len(issues)}
    return {'counts':counts,'headings':headings,'tables':tables,'lists':lists,'units':units,'issues':issues}


def md(text):return str(text).replace('|','\\|').replace('\n',' ')
def source_loc(x):return '`'+x['xpath']+'`'+(' / XML id `'+x['xml_id']+'`' if x['xml_id'] else '')
def unit_anchor(x):return '<a id="'+x['anchor']+'"></a>'


def render_chapter(nbk,result,cases,path,title,sha):
    c=result['counts'];lines=[f'# {nbk} — {title}','',f'病例：{", ".join(sorted(cases))}。仅正文Management及其子节。',
        f'本章模式：**{result["pattern"]}**；Management自有正文合计：{result["management_words"]} words / {result["management_chars"]} chars。',
        f'排除指定非治疗标题后的结构模式：**{result["pattern_unflagged"]}**（仅统计视图，不确认其余内容都是治疗）。',
        f'来源：[GeneReviews]({G.BOOK_URL.format(nbk=nbk)})；本地XML：`{path.relative_to(ROOT)}`；SHA256：`{sha}`。',G.CREDIT,'',
        '统计口径见[index](index.md)。XPath针对该固定XML；每个单元的HTML anchor由NBK+XPath哈希生成，XML id另列。表内列表不重复计入独立列表项；模板命中段不计入自由正文。','',
        '## 统计','', '| 指标 | 数值 |','|---|---:|']
    lines += ['| '+k+' | '+str(v)+' |' for k,v in c.items()]
    lines+=['','## 标题树与上下文标记','']
    for h in result['headings']:lines.append('  '*max(0,h['level']-1)+'- '+unit_anchor(h)+f"L{h['level']} [{h['kind']}] **{md(h['title'])}** — "+source_loc(h))
    lines+=['','## 表格','']
    for i,t in enumerate(result['tables'],1):
        lines += [f"### {unit_anchor(t)}{i}. {md(t['label']) if t['label'] else '(无label)'} {md(t['caption']) if t['caption'] else '(无caption)'}",'',source_loc(t),'',f"数据行：{t['body_rows'] if t['body_rows'] is not None else '未知'}；当前_table_rows可呈现行数：{t['current_render_rows']}。",'', '表头各级（保留原始行/列跨度；未显式设置的span为XML默认1）：']
        for j,row in enumerate(t['header_rows'],1):lines.append('- header '+str(j)+': '+md(json.dumps(row,ensure_ascii=False)))
        if t['columns'] is None:lines.append('- 列名未知：XML无声明表头。')
        lines+=['','| 行 | 稳定位置 | 单元格位置及跨度 |','|---|---|---|']
        for j,row in enumerate(t['rows'],1):lines.append('| '+str(j)+' '+unit_anchor(row)+' | '+source_loc(row)+' | '+md('; '.join(cell['xpath'].rsplit('/',1)[-1]+f" (rowspan={cell['rowspan']}, colspan={cell['colspan']})" for cell in row['cells']))+' |')
    lines+=['','## 列表（包括表内嵌套列表，后者不计入独立列表项）','']
    for l in result['lists']:
        lines += [unit_anchor(l)+f"- depth={l['depth']}，type={md(l['list_type'])}，条目={len(l['items'])}，表内={l['in_table']} — "+source_loc(l)]
        for i,item in enumerate(l['items'],1):lines.append('  - '+unit_anchor(item)+f"item {i}，words={item['words']}，chars={item['chars']}，模板={','.join(item['templates']) or '无签名命中'} — "+source_loc(item))
    lines+=['','## 独占文本单元（自由正文 / 模板 / 表外列表项）','', '| 类型 | words / chars | 模板签名 | 位置 |','|---|---:|---|---|']
    for u in result['units']:lines.append('| '+(('[锚点](#'+u['anchor']+')') if u['kind']=='list item' else unit_anchor(u))+u['kind']+' | '+str(u['words'])+' / '+str(u['chars'])+' | '+(', '.join(u['templates']) or '—')+' | '+source_loc(u)+' |')
    lines+=['','## 无法按当前呈现器完整表示的结构','']
    lines += ['- '+x['reason']+' — '+source_loc(x) for x in result['issues']] or ['无已识别问题；这不是对所有可能XML语义的完整性证明。']
    return '\n'.join(lines)+'\n'


def hpo_label(text,ontology):
    if not text.strip():return {'match':'未知','review_hint':'源标签为空','hits':[]}
    cleaned=re.sub(r'\s*\[(?:\d+(?:[,–-]\d+)*|[a-z])\]','',text).strip(' .:;')
    whole=ontology.exact_lookup(cleaned)
    parts=[cleaned] if whole else [p.strip(' .:;') for p in re.split(r'\s*(?:/|;|,|\band\b|\bor\b)\s*',cleaned) if p.strip(' .:;')]
    hits=[{'part':part,'id':tid,'name':ontology.terms[tid].label} for part in parts for tid in ontology.exact_lookup(part)]
    return {'match':'是' if hits else '否','review_hint':'表现' if hits else '疑似治疗名','basis':'全标签名称/同义词精确匹配' if whole else '分隔成分精确匹配' if hits else '无精确词表命中','hits':hits,'not_a_clinical_classification':True}


def structural_text(e):
    blocks={'p','list','list-item','def-list','def-item','table-wrap','caption','tr','td','th','label','fn','break'}
    def raw(node):
        parts=[node.text or '']
        for child in node:
            sep=' ' if child.tag in blocks else ''
            parts.extend([sep,raw(child),sep,child.tail or ''])
        return ''.join(parts)
    return re.sub(r'\s+',' ',raw(e)).strip()


def review_sections(root,nbk,ontology,display):
    parents={c:p for p in root.iter() for c in p};paths={}
    def tree(e,path):
        paths[e]=path;counts=Counter()
        for c in e:counts[c.tag]+=1;tree(c,path+'/'+c.tag+'['+str(counts[c.tag])+']')
    tree(root,'/'+root.tag+'[1]')
    def ancestors(e):
        while e in parents:e=parents[e];yield e
    def pos(e):return {'xpath':paths[e],'xml_id':e.attrib.get('id'),'anchor':nbk+'-'+hashlib.sha256(paths[e].encode()).hexdigest()[:14]}
    body=root.find('.//body')
    if body is None:raise ValueError('body not found')
    candidates=[s for s in body.iter('sec') if s.find('title') is not None and G._text(s.find('title')).lower().startswith('management')]
    roots=[s for s in candidates if not any(a in candidates for a in ancestors(s))]
    nodes=[e for r in roots for e in r.iter()];sections={s:[] for s in nodes if s.tag=='sec'}
    for e in nodes:
        owner=e if e.tag=='sec' else next(a for a in ancestors(e) if a.tag=='sec')
        sections[owner].append(e)
    out=[]
    for sec,items in sections.items():
        titles=[G._text(s.find('title')) for s in reversed(list(ancestors(sec))) if s in sections and s.find('title') is not None]
        title=G._text(sec.find('title')) if sec.find('title') is not None else '(无标题)';titles.append(title)
        flags=[name for name,pattern in [('Pregnancy Management',r'pregnancy'),('Evaluations',r'evaluat'),('Surveillance',r'surveillance'),('Relatives',r'relatives'),('Therapies Under Investigation',r'under investigation')] if re.search(pattern,' / '.join(titles),re.I)]
        text=' '.join(structural_text(c) for c in sec if c.tag not in {'title','sec'})
        row=dict(pos(sec),title=title,path=' / '.join(titles),words=words(text),chars=len(text),non_treatment_sections=flags,forms=[],bold_labels=[],table_rows=[],lists=[])
        for e in items:
            in_table=any(a.tag=='table-wrap' for a in ancestors(e))
            if e.tag=='bold':
                p=parents[e];first=next(iter(p),None);lead=p.tag=='p' and first is e and not(p.text or '').strip()
                role='表格内粗体' if in_table else '独立粗体小标题' if lead and G._text(e)==G._text(p) else '段首粗体标签' if lead else '行内粗体（未确认是标签）'
                value=display(e);record=dict(pos(e),text=value,role=role,hpo=hpo_label(value,ontology) if ontology is not None else None)
                if lead:record['paragraph_text']=own_text(p)
                row['bold_labels'].append(record)
                if lead and not in_table:row['forms'].append('粗体标签段落')
            if e.tag=='p' and not any(a.tag in ITEMS|{'table-wrap'} for a in ancestors(e)) and own_text(e):
                row['forms'].append('套话' if matches(own_text(e)) else '自由正文')
            if e.tag in LISTS:
                li=[x for x in e if x.tag in ITEMS]
                row['lists'].append(dict(pos(e),in_table=in_table,depth=1+sum(a.tag in LISTS for a in ancestors(e)),items=[dict(pos(x),text=own_text(x),templates=matches(own_text(x))) for x in li]))
                if not in_table:row['forms'].append('列表')
            if e.tag=='table-wrap':
                row['forms'].append('汇总表');caption=e.find('caption');label=e.find('label');header_rows=[[display(c) for c in tr if c.tag in {'th','td'}] for tr in e.findall('.//thead/tr')]
                table=dict(pos(e),caption=G._text(caption) if caption is not None else None,label=G._text(label) if label is not None else None,header_rows=header_rows,rows=[])
                for table_el in e.iter('table'):
                    carry=None;remaining=0
                    for tr in table_el.iter('tr'):
                        if any(a.tag in {'thead','tfoot'} for a in ancestors(tr)):continue
                        if next(a for a in ancestors(tr) if a.tag=='table') is not table_el:continue
                        cells=[c for c in tr if c.tag in {'th','td'}]
                        if remaining:lab=carry;remaining-=1
                        else:
                            lab=cells[0] if cells else None
                            if lab is not None:carry=lab;remaining=int(lab.attrib.get('rowspan','1'))-1
                        label_text=display(lab) if lab is not None else ''
                        table['rows'].append(dict(pos(tr),row_label=label_text,row_label_position=pos(lab) if lab is not None else None,cells=[display(c) for c in cells],hpo=hpo_label(label_text,ontology) if ontology is not None else None))
                row['table_rows'].append(table)
        row['forms']=list(dict.fromkeys(row['forms'])) or ['仅子小节']
        out.append(row)
    return out


def pattern_of(sections):
    forms={f for s in sections for f in s['forms']}
    if '汇总表' in forms:return '汇总表+标签段落' if '粗体标签段落' in forms else '汇总表+正文/列表'
    if '粗体标签段落' in forms:return '粗体标签+段落（无汇总表）'
    if '列表' in forms:return '列表+正文（无汇总表/粗体标签）'
    return '无结构正文（无汇总表/粗体标签/列表）'


def render_review(sections):
    lines=['','## 逐小节审阅：字数、形式、标签及原文','', '字数为各sec自有内容（不含子sec和sec标题），包含列表、表格及表内脚注，词计数保留XML块边界避免相邻列表项粘词；这些字数按sec求和不会重复。粗体行内强调不擅自当作段首标签。表格行的匹配对象为源行标签（首列，按rowspan继承），不是整行治疗文字。','', '三章HPO附注只查本地词表名称/同义词及分隔成分：是→表现，否→疑似治疗名。未命中也可能是年龄、剂量、栏目或检查名；这是用户要求的审阅启发式，不是治疗分类，更不是路由规则。非治疗小节标签仅作本轮观察。','']
    def hint(h):
        if h is None:return '本章未做HPO附注'
        return h['match']+' → '+h['review_hint']+('；'+', '.join(x['id']+' '+x['name'] for x in h['hits']) if h['hits'] else '')
    for sec in sections:
        lines += ['### '+md(sec['path']),'',f"自有正文：{sec['words']} words / {sec['chars']} chars；形式：{' + '.join(sec['forms'])}。",'非治疗小节标记：'+(', '.join(sec['non_treatment_sections']) or '无指定标记（不等于已确认治疗）')+'。',source_loc(sec),'','粗体标签/强调：']
        for b in sec['bold_labels']:
            lines += ['- **'+md(b['text'])+'** ['+b['role']+'] — '+hint(b['hpo'])+'；'+source_loc(b)]
            if 'paragraph_text' in b and b['paragraph_text']!=b['text']:lines.append('  - 所在段原文：'+md(b['paragraph_text']))
        if not sec['bold_labels']:lines.append('- 无粗体单元。')
        for table in sec['table_rows']:
            lines+=['', '**'+md(table['label'])+' '+md(table['caption'])+'**','', '表头（每级原文）：'+md(json.dumps(table['header_rows'],ensure_ascii=False)), '', '| 行 | 源行标签 / HPO附注 | 原始单元格全文（序号为物理单元格，rowspan标签另列） | 位置 |','|---|---|---|---|']
            for i,tr in enumerate(table['rows'],1):lines.append('| '+str(i)+' | '+md(tr['row_label'])+' / '+md(hint(tr['hpo']))+' | '+md('；'.join(str(j)+': '+v for j,v in enumerate(tr['cells'],1)))+' | '+source_loc(tr)+' |')
        for li in sec['lists']:
            lines+=['',f"列表 depth={li['depth']}，表内={li['in_table']} — "+source_loc(li)]
            for i,it in enumerate(li['items'],1):lines.append('- '+str(i)+'. '+md(it['text'])+'；'+source_loc(it))
    return '\n'.join(lines)+'\n'


def main():
    ids,all_uses,ledgers=inventory();uses=all_uses;local={}
    for name in ('genereviews','genereviews_book','hpo_ontology'):
        metas=sorted((D.DATA_DIR/name).glob('*/meta.json'))
        if not metas:raise FileNotFoundError('cached dataset metadata missing: '+name)
        lf=D._load_meta(metas[-1].parent)
        if lf is None or not lf.path.exists():raise FileNotFoundError('cached dataset missing: '+name)
        local[name]=lf
    from aitx.disease.hpo import Ontology
    ontology=Ontology(local['hpo_ontology'])
    results={};failures=[];OUT.mkdir(parents=True,exist_ok=True)
    # Reuse the current parser's cached chapter loader. A stale date never triggers D.ensure's downloader.
    with patch.object(D,'ensure',lambda name:local[name]):
        paths=G.extract_chapters(sorted(uses))
        for nbk in sorted(uses):
            if nbk not in paths:
                failures.append({'nbk':nbk,'source':'cached book archive','reason':'chapter XML absent from cached archive'});continue
            path=paths[nbk]
            try:
                root=G.ET.parse(path).getroot();result=observe(root,nbk)
                result['section_review']=review_sections(root,nbk,ontology if nbk in TARGETS else None,lambda e:G.display_quote(nbk,G._text(e)))
            except (G.ET.ParseError,ValueError) as exc:
                failures.append({'nbk':nbk,'source':str(path.relative_to(ROOT)),'reason':str(exc)});continue
            title=G.chapter_title(nbk)
            if title is None:raise ValueError('chapter title missing: '+nbk)
            sha=hashlib.sha256(path.read_bytes()).hexdigest();result.update(title=title,path=str(path.relative_to(ROOT)),sha256=sha,cases=uses[nbk])
            result['pattern']=pattern_of(result['section_review'])
            result['pattern_unflagged']=pattern_of([s for s in result['section_review'] if not s['non_treatment_sections']])
            result['management_words']=sum(x['words'] for x in result['section_review'])
            result['management_chars']=sum(x['chars'] for x in result['section_review'])
            result['current_render_management_paths']=[p for p in G.sections_for_llm(nbk) if p.lower().startswith('management')]
            results[nbk]=result;(OUT/(nbk+'.md')).write_text(render_chapter(nbk,result,uses[nbk],path,title,sha)+render_review(result['section_review']))
    for failure in failures:
        (OUT/(failure['nbk']+'.md')).write_text('# '+failure['nbk']+' — 解析未完成\n\n'+json.dumps(failure,ensure_ascii=False,indent=2)+'\n')
    total=Counter()
    for r in results.values():total.update(r['counts'])
    no_chapter=[cid for cid in ids if not any(cid in cases for cases in uses.values())]
    lines=['# GeneReviews Management结构地图索引 v1.2','',f'按最新要求覆盖15例现有练习/复测及12例盲测实际用过的全部章节。只读核对27例的{len(ledgers)}份产物，NBK去重{len(uses)}章；成功{len(results)}，失败{len(failures)}。LLM/联网请求0、费用$0；三章HPO匹配只是审阅附注，不改变治疗或患者适用性判定。','',
        '## 范围与计数规则','', '- 15例沿用项目既有范围：official_examples.json排除延期DMD后的11例，加retest-20261112.json的4例；12例盲测来自20261108.json。不纳入正式评测病例。',
        '- 使用当前和历史执行产物的sourced NBK证据及已选supportive_tiers.chapters；不把基因索引候选、not_used章节或文中交叉引用当作已使用。来源追踪见manifest.json。',
        '- 只取正文body中以Management开头的标题树（含Management of Hereditary Ataxia）；排除abstract摘要中的同名小节。包括Management内的评估、监测等所有内容，不按治疗内容筛选。',
        '- 表格按table-wrap计，行数为XML非thead/tfoot数据行；列名与所有表头层级均保留。表内列表单列，不再计入表外列表项。',
        '- 自由正文只计不在表格/列表内、非bold-only标题且未命中模板签名的p。列表条目只计自身文本，剔除嵌套列表/表格；同段中有内嵌表格时只计表外文本。',
        '- 模板命中按文本单元去重，签名可在同单元命中多项；模板段不再计自由正文。列表中的模板仍属于列表，命中是注释，不能把各列简单相加当作文本总量。未命中不等于确定不是模板。',
        '- words用Unicode词边界、保留词内连字符/撇号；chars为当前解析器规范化空白后的字符数。没有重新计算临床内容分类。',
        '- anchor=NBK+XPath哈希，源XML SHA锁定版本，XML id若有则保留；完整原文在缓存XML位置，不复制整章正文。',
        '', '## 章节汇总','', '| NBK / 章节 | 病例 | 表格行 | 表外列表项 | 表内列表项 | 自由正文段 / words | 套话命中单元 | 全Management words | 模式 |','|---|---|---:|---:|---:|---:|---:|---:|---|']
    for n,r in results.items():
        c=r['counts'];lines.append(f"| [{n} {md(r['title'])}]({n}.md) | {', '.join(sorted(r['cases']))} | {c['table_rows']} | {c['list_items']} | {c['table_internal_list_items']} | {c['free_paragraphs']} / {c['free_words']} | {c['template_hits']} | {r['management_words']} | {r['pattern']} |")
    lines+=['','合计：`'+json.dumps(dict(total),ensure_ascii=False)+'`。','', '## 27例实际来源覆盖','', '| 病例 | 实际记录NBK |','|---|---|']
    for cid in ids:lines.append('| '+cid+' | '+(', '.join(n for n,cases in sorted(uses.items()) if cid in cases) or '现存执行产物未记录实际使用NBK；不推断该基因没有章节')+' |')
    lines+=['','## 套话观察签名（仅字符串匹配，无模板抽取实现）','']+[f'- `{k}`: {text}' for k,text in TEMPLATES.items()]
    lines+=['','[KMT2B / AGXT / Hereditary Ataxia对比](comparison.md) · [解析及结构限制清单](unrecognized.md)','',f'{len(no_chapter)}例现存产物没有实际使用NBK记录；不推断该基因没有GeneReviews。SFTPC抽样说明的NBK1230只属目录候选，未找到实际使用证据。等待审阅后再讨论切块/路由，本轮不实施优化。']
    patterns=Counter(r['pattern'] for r in results.values())
    lines+=['','## 章节模式（互斥、只看结构存在性，不用于路由）','','| 模式 | 章节数 | NBK |','|---|---:|---|']
    for kind,count in sorted(patterns.items()):lines.append('| '+kind+' | '+str(count)+' | '+', '.join(n for n,r in results.items() if r['pattern']==kind)+' |')
    if '无结构正文（无汇总表/粗体标签/列表）' not in patterns:lines.append('| 无结构正文（无汇总表/粗体标签/列表） | 0 | — |')
    lines+=['','模式判定：先看有无汇总表、再看有无段首/独立粗体标签，最后看表外列表；正文/套话只作为形式注记。不将行内加粗剂量或表内粗体当作标签段落。各章所有小节的字数/原文在逐小节审阅中。']
    reduced=Counter(r['pattern_unflagged'] for r in results.values())
    lines+=['','## 排除指定非治疗标题后的结构视图','','此视图只使用上文已标出的Pregnancy/Evaluations/Surveillance/Relatives/Under Investigation标题，不作其他内容判定，也不用于抽取。总体模式中的“汇总表”仅表示XML表格；评估/监测表不能因此视为治疗汇总表。','','| 模式 | 章节数 | NBK |','|---|---:|---|']
    for kind,count in sorted(reduced.items()):lines.append('| '+kind+' | '+str(count)+' | '+', '.join(n for n,r in results.items() if r['pattern_unflagged']==kind)+' |')
    (OUT/'index.md').write_text('\n'.join(lines)+'\n')
    compare=['# KMT2B、AGXT与Hereditary Ataxia的Management结构对比','', '| 项目 | KMT2B NBK493766 | AGXT NBK1283 | Hereditary Ataxia NBK1138 |','|---|---:|---:|---:|']
    for key in ('management_roots','section_headings','bold_subheadings','paragraph_leadins','tables','table_rows','lists_outside_tables','list_items','table_internal_list_items','free_paragraphs','free_words','free_chars','template_paragraphs','template_hits','issues'):
        compare.append('| '+key+' | '+' | '.join(str(results[n]['counts'][key]) if n in results else '未知（解析未完成）' for n in ('NBK493766','NBK1283','NBK1138'))+' |')
    compare+=['| 全Management words | '+' | '.join(str(results[n]['management_words']) for n in ('NBK493766','NBK1283','NBK1138'))+' |', '| 结构模式 | '+' | '.join(results[n]['pattern'] for n in ('NBK493766','NBK1283','NBK1138'))+' |']
    compare+=['| 排除指定非治疗标题后模式 | '+' | '.join(results[n]['pattern_unflagged'] for n in ('NBK493766','NBK1283','NBK1138'))+' |']
    compare+=['','这只是原文结构比较，不判断哪些段落属于治疗，不归因抽取性能，也不提出或实施流程优化。所有数值按索引的互斥文本归属和结构计数口径计算。']
    (OUT/'comparison.md').write_text('\n'.join(compare)+'\n')
    issue_lines=['# 解析失败及当前呈现器结构限制','',f'章节XML/Management解析失败：{len(failures)}；结构限制记录：{total["issues"]}。结构地图可以定位这些单元，并不表示XML本身损坏。未修复生产解析器。表内列表在当前行文本中被平铺、不保留项层级（本次共{total["table_internal_list_items"]}项）；其原始层级、项文本和全部位置另列于各章。','']
    issue_lines += ['- '+json.dumps(f,ensure_ascii=False) for f in failures]
    for n,r in results.items():
        for issue in r['issues']:issue_lines+=['- ['+n+']('+n+'.md) — '+issue['reason']+'；`'+r['path']+'`；'+source_loc(issue)+'；anchor `'+issue['anchor']+'`']
    (OUT/'unrecognized.md').write_text('\n'.join(issue_lines)+'\n')
    manifest={'cases':ids,'used_chapter_provenance':uses,'ledger_files':ledgers,'dataset_snapshots':{n:lf.manifest_entry() for n,lf in local.items()},'chapters':results,'failures':failures,'totals':dict(total),'patterns':dict(patterns),'patterns_excluding_marked_sections':dict(reduced),'model_calls':0,'network_calls':0,'pipeline_modified':False}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(ids),'ledgers':len(ledgers),'chapters':len(results),'failures':len(failures),'totals':dict(total),'no_recorded_chapter_cases':len(no_chapter),'patterns':dict(patterns),'patterns_excluding_marked_sections':dict(reduced)},ensure_ascii=False,indent=2))

if __name__=='__main__':main()

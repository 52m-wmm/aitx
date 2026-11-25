"""Read-only clinical trial view of saved Step 3 ledgers; no analysis or network."""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
e = html.escape
SECTION = 'clinical_trial_eligibility'
STATES = {'applicable': ('pass', '符合已评估标准'),
          'conditional': ('warn', '有条件 · 尚有未知'),
          'not_applicable': ('fail', '不符合'),
          'searched_none': ('', '检索无结果')}
RESULTS = {'pass': ('pass', '通过'), 'fail': ('fail', '不通过'),
           'unknown': ('warn', '未知'), 'not_assessed': ('', '未评估')}


def badge(value: str, labels: dict) -> str:
    cls, label = labels[value]
    return f'<span class="tag {cls}">{e(label)}</span>'


def stamp(value) -> str:
    return '未知' if value is None else datetime.fromtimestamp(value, timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def raw(label: str, value) -> str:
    return f'<details><summary>{e(label)}</summary><pre>{e(json.dumps(value, ensure_ascii=False, indent=2))}</pre></details>'


def requirement(row: dict, evidence: dict, branches: dict) -> str:
    fact = row['patient_fact']
    fact_text = '未知' if fact is None else ' · '.join(str(fact[k]) for k in ('field', 'value', 'quote') if fact.get(k) is not None) or '未知'
    ev = evidence[row['requirement_evidence']]
    kind = {'inclusion': '入组', 'exclusion': '排除'}[row['kind']]
    scope = '、'.join(branches[b] for b in row['applies_to'])
    return (f'<div class="trial-rule"><p>{badge(row["result"], RESULTS)} '
            f'<strong>{kind}标准</strong> <span class="muted">{e(scope)}</span></p>'
            f'<p class="trial-verbatim">{e(row["requirement"])}</p>'
            f'<p>病人事实：{e(fact_text)}</p><p>理由：{e(row["note"] or "未知")}</p>'
            f'<details><summary>原文证据 · {e(ev["id"])}</summary>'
            f'<blockquote class="trial-verbatim">{e(ev["quote"])}</blockquote>'
            f'<p>来源：{e(json.dumps(ev["source"], ensure_ascii=False))} · 获取于 {stamp(ev["accessed_at"])}</p>'
            f'</details>{raw("组合标准 / 单位情景", {k: row[k] for k in ("any_of", "details") if k in row}) if "any_of" in row or "details" in row else ""}</div>')


def saved_panel(case_id: str) -> str:
    path = ROOT / 'out' / 'step3' / f'{case_id}.json'
    if not path.exists():
        return '<p class="muted">此病例尚无 Step 3 账本，未运行临床试验检索。</p>'
    led = json.loads(path.read_text())
    actions = [a for a in led['actions'] if a['section'] == SECTION]
    searches = led['trial_searches']
    branches = {b['id']: b['diagnosis']['label'] if b['diagnosis'] else b['id'] for b in led['branches']}
    evidence = {v['id']: v for v in led['evidence']}
    dates = [s['queried_at'] for p in searches.values() for s in p['searches']]
    from aitx import runmeta
    freshness = runmeta.freshness(3, case_id, out=ROOT / 'out')
    stale = not freshness['fresh']
    expired = any(time.time() - d > 86400 for d in dates)
    parts = ['<div class="trial-view"><style>'
             '.trial-view{overflow-wrap:anywhere}.trial-view pre,.trial-verbatim{white-space:pre-wrap;overflow-wrap:anywhere}'
             '.trial-view summary{padding:10px 0;min-height:44px}.trial-view blockquote{margin:12px 0;padding:8px 14px;border-left:3px solid var(--line)}'
             '.trial-rule{border-top:1px solid var(--line);padding:8px 0}.trial-view h3{font-size:16px}'
             '.trial-meta{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}</style>',
             '<h3>临床试验 · 已保存结果</h3>',
             f'<p class="muted">账本生成：{stamp(led["_meta"]["created_at"])}；最近检索：{stamp(max(dates) if dates else None)}。'
             '显示已有判定；是否可报名仍需研究团队筛查。</p>']
    if stale or expired:
        parts.append('<div class="card"><strong>历史结果 · '
                     + ('账本已过期' if stale else '账本指纹未变')
                     + (' · 试验检索已超过 1 天' if expired else '')
                     + '</strong><p>以下招募状态与判定来自保存时的数据，当前状态未确认。</p></div>')
    if not led['ok']:
        parts.append('<p class="fail">账本自检未通过，请结合完整检查结果审阅。</p>' + raw('账本检查', led['checks']))
    for study_type, title in [('interventional', '干预试验'), ('observational', '观察研究'), (None, '其他 / 类型未知')]:
        group = [a for a in actions if a.get('nct') and
                 (a['study_type'] == study_type if study_type else a['study_type'] not in ('interventional', 'observational'))]
        if not group:
            continue
        parts.append(f'<details class="trial-group"><summary><strong>{title}</strong> <span class="muted">{len(group)} 项</span></summary>')
        for a in group:
            parts.append(f'<article class="card"><h3>{e(a["label"])}</h3><p>{e(a["title"])}</p>'
                         f'<div class="trial-meta"><a href="{e(a["url"])}" target="_blank" rel="noopener">{e(a["nct"])} ↗</a>'
                         f'<span>{e(a["overall_status"])}</span><span>期别：{e(" / ".join(a["phases"]) or "未登记")}</span></div>')
            for bid, status in a['status_by_branch'].items():
                parts.append(f'<p>{badge(status["status"], STATES)} {e(branches[bid])}<br>{e(status["reason"])}</p>')
            parts.append('</article>')
        parts.append('</details>')
    for a in actions:
        if not a.get('nct'):
            parts.append('<article class="card"><h3>检索无结果</h3>')
            parts.extend(f'<p>{e(evidence[eid]["claim"])}</p>' for eid in a['evidence_ids'])
            parts.append(raw('分支结论与证据引用', a) + '</article>')
    if not searches:
        parts.append('<p class="muted">账本未记录 3b 检索，不能认定没有相关试验。</p>')
    parts.append('<h3>检索范围与未纳入记录</h3><p class="muted">各分支分别计数；同一试验可能命中多个分支。</p>')
    for bid, plan in searches.items():
        parts.append(f'<details class="card"><summary>{e(branches[bid])} · 已分析 {len(plan["analysed"])} 项 · '
                     f'预筛不符合 {len(plan["ineligible"])} 项 · 过滤 {len(plan["excluded"])} 项 · '
                     f'超出上限 {len(plan["over_cap"])} 项</summary>')
        for s in plan['searches']:
            parts.append(f'<p>{e(json.dumps(s["query"], ensure_ascii=False))}<br>{stamp(s["queried_at"])} · '
                         f'返回总数：{e(str(s["total_count"]))} · <a href="{e(s["url"])}" target="_blank" rel="noopener">检索来源</a></p>')
        parts.append(f'<details><summary>被过滤 / 未招募记录及原因 · {len(plan["excluded"])} 项</summary>')
        for item in plan['excluded']:
            parts.append(f'<div class="trial-rule"><strong>{e(item["nct"])} · {e(item["title"])}</strong>'
                         f'<p>{e(item["status"])} · {e(item["reason"])}<br>{e(item["detail"])}</p></div>')
        parts.append('</details>')
        parts.append(raw('预筛不符合的试验', plan['ineligible']))
        parts.append(raw('超出逐条分析上限', plan['over_cap']))
        parts.append('</details>')
    parts.append('</div>')
    return '\n'.join(parts)


def cohort_label(row: dict) -> str:
    """Use the saved scope/heading, not a trial-specific cohort name."""
    heading = re.split(r'年龄|：|:', row['prerequisite'], maxsplit=1)[0].strip()
    label = heading if heading != row['prerequisite'] else row['scope']
    return re.sub(r'(?<=[\u4e00-\u9fff])(?=Part\b)', ' ', label)


def cohort_display(rows: list[dict]) -> dict:
    """Select display scope only; never produce or change a study decision."""
    alternatives = [r for r in rows if r['route'] == 'alternative']
    blocked = {r['scope'] for r in alternatives if r['status'] == 'conflict'}
    possible = [r for r in alternatives if r['status'] != 'conflict' and r['scope'] not in blocked]
    supported = [r for r in possible if r['status'] == 'confirmed']
    preferred = supported or (possible if len(possible) == 1 else [])
    scopes = {r['scope'] for r in preferred}
    all_scopes = {r['scope'] for r in alternatives}
    focused = [r for r in rows if r['scope'] in scopes or
               (r['route'] != 'alternative' and r['scope'] not in all_scopes)]
    return {'alternatives': alternatives, 'preferred': preferred,
            'focused': focused, 'supported': supported,
            'inactive': [r for r in alternatives if r['status'] == 'conflict']}


def prerequisite_label(row: dict) -> str:
    return {'满足原文所需的PH/PH1诊断及确认记录': '确认研究要求的PH/PH1诊断',
            'AGXT基因相关组成部分': '已提供AGXT变异信息',
            '能够且愿意提供同意/assent': '确认监护人同意及儿童知情赞同',
            '儿童路径：<18岁且有肾结石和/或肾钙质沉着': '未满18岁且有肾钙质沉着，儿童临床路径有直接支持'
            }.get(row['prerequisite'], row['prerequisite'])


def experiment_panel(case_id: str) -> str:
    path = ROOT / 'out' / '3b' / case_id / 'result.json'
    if not path.exists():
        return ''
    data = json.loads(path.read_text())
    if data['case_id'] != case_id or data['patient']['id'] != case_id:
        raise ValueError('Step 3b viewer data belongs to another case')
    candidates, excluded, counts = data['candidates'], data['excluded'], data['counts']
    from scripts.build_step3b_experiment_view import priority_key, CATEGORIES
    candidates = sorted(candidates, key=priority_key)
    therapeutic_count = sum(c['pathway']['therapeutic'] for c in candidates)
    labels = {'confirmed': ('pass', 'confirmed · 已确认'), 'unknown': ('warn', 'unknown · 未知'),
              'conflict': ('fail', 'conflict · 该队列不符合'), 'not_assessed': ('', 'not_assessed · 尚未完成核查')}
    parts = ['''<div class="trial-view experiment-trials"><style>
.experiment-trials{overflow-wrap:anywhere}.experiment-trials>h3{font-size:18px;margin:12px 0 4px}
.experiment-trials pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}
.experiment-trials summary{min-height:44px;padding:10px 0}.experiment-trials .experiment-metrics{display:flex;gap:28px;flex-wrap:wrap;margin:12px 0 6px;padding:10px 0}
.experiment-metrics strong{font-size:26px;line-height:1.2;margin-right:6px;color:var(--fg)}.experiment-metrics span{font-size:14px;color:var(--muted)}
.experiment-trials .screening-process{font-size:13px;border-bottom:1px solid var(--line);margin-bottom:12px}
.experiment-trials .screening-process>summary{color:var(--muted)}.experiment-trials .process-content{padding:0 4px 12px}
.experiment-trials .trial-group>summary{display:flex;gap:8px;align-items:center;font-size:16px}.experiment-trials .trial-group>summary:before{content:'›';color:var(--muted)}.experiment-trials .trial-group[open]>summary:before{transform:rotate(90deg)}
.experiment-trials .trial-group>summary{list-style:none}.experiment-trials .trial-group>summary::-webkit-details-marker{display:none}
.experiment-trials .study-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:0 0 14px}
.experiment-trials .study-card{background:var(--card);padding:13px 15px;border:1px solid var(--line);border-radius:6px;min-width:0}
.study-card .study-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}.experiment-trials .study-card h3{font-size:15px;line-height:1.45;margin:0 0 4px}.study-heading .recruitment{font-size:12px;white-space:nowrap;color:var(--muted)}
.study-card .nct-id{font-size:12px;color:var(--muted)}.study-card dl{margin:9px 0 6px;font-size:13px;line-height:1.65}.study-card dt{font-weight:600;margin-top:7px}.study-card dd{margin:2px 0 0}.study-card dd ul{margin:0;padding-left:18px}.study-card .known-label{color:var(--pass)}.study-card .pending-label{color:var(--warn)}.study-card .conflict-label{color:var(--fail)}.study-card .possible-cohorts{font-size:14px;color:var(--acc);margin:9px 0 5px}.study-card .cohort-note{font-size:12px;color:var(--muted);margin:5px 0}
.study-card .study-footer{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:9px;font-size:12px}.study-card .study-footer a{padding:5px 0;min-height:32px}.study-card .source-detail>summary{font-size:12px;color:var(--muted);padding:10px 0 2px}
.study-card .source-detail{border-top:1px solid var(--line);margin-top:5px}.experiment-trials blockquote{white-space:pre-wrap;overflow-wrap:anywhere;border-left:2px solid var(--line);padding:8px 10px;margin:8px 0;font-size:12px}
.experiment-trials .trial-rule{border-top:1px solid var(--line);padding:10px 0;font-size:13px}.experiment-trials .trial-rule h4{margin:8px 0}.experiment-trials .trial-rule p{margin:5px 0}.experiment-trials .official-name{font-size:12px;color:var(--muted)}
.experiment-trials .excluded-studies{border-top:1px solid var(--line);margin-top:10px}.experiment-trials .excluded-studies>summary{font-size:14px}.experiment-trials #app-rerun{margin:10px 0 0}.step3b-experiment-active main>h1{display:none}.step3b-experiment-active #step3>h2{margin-top:12px}
@media(max-width:760px){.experiment-trials .study-grid{grid-template-columns:1fr}.experiment-trials .experiment-metrics{gap:12px 20px}.experiment-metrics strong{font-size:23px}.experiment-metrics span{font-size:12px}}
</style><h3>临床试验 <span class="tag">实验结果</span></h3><p class="muted">候选仍需专业筛查；年龄或基因部分匹配，不代表完整入组资格已满足。</p><div class="experiment-metrics">''']
    formal = 'source_kind' in data and data['source_kind'] == 'formal_ledger'
    if formal:
        parts[0] = parts[0].replace('实验结果', '本次结果')
    for number, label in [(len(candidates), '项保留候选'), (therapeutic_count, '项治疗性干预研究'), (len(excluded), '项已排除研究' if formal else '项实验中已排除')]:
        parts.append(f'<div><strong>{number}</strong><span>{label}</span></div>')
    screened = len(candidates) + len(excluded)
    not_screened = counts['api_unique'] - screened
    parts.append('</div><details class="screening-process" id="trial-screening-process"><summary>筛选过程</summary><div class="process-content">'
                 f'<p><strong>去重后检索到 {counts["api_unique"]} 项研究</strong></p>'
                 f'<p>其中 {screened} 项进入本轮资格筛选；{not_screened} 项未进入资格筛选。</p>'
                 f'<p>资格筛选结果：排除 {len(excluded)} 项，保留 {len(candidates)} 项候选，仍需专业筛查。</p>'
                 '<details><summary>检索计数说明</summary>'
                 f'<p>多个检索词累计返回 {counts["api_query_returned_with_duplicates"]} 条记录（含重复），去重后为 {counts["api_unique"]} 项研究。'
                 '检索命中不代表该研究正在招募本病例，也不代表患者符合资格；招募状态、相关性及资格条件需要后续筛选。</p>'
                 f'<p>本轮由模型进一步核查 {counts["sent_to_deepseek"]} 项（包含已保存回答的复用）。'
                 '未进入资格筛选的记录及原因以原始检索记录为准。</p></details>'
                 '<div id="trial-process-tools"></div></div></details>')
    for rank, title in enumerate(CATEGORIES):
        group = [c for c in candidates if c['pathway']['category_rank'] == rank]
        if not group:
            continue
        parts.append(f'<details class="trial-group" open><summary><strong>{title}（{len(group)}）</strong></summary><div class="study-grid">')
        for c in group:
            nct = c['nct_id']
            rs = c['prerequisites']
            cohorts = cohort_display(rs)
            if cohorts['preferred']:
                confirmed = [r for r in cohorts['focused'] if r['status'] == 'confirmed'
                             and (r['route'] == 'alternative' or r['kind'] != 'age')]
                known = '；'.join(prerequisite_label(r) for r in confirmed) or '该路径的关键条件仍待确认。'
                relevant = [r for r in cohorts['focused'] if r['status'] == 'unknown']
                relevant.sort(key=lambda r: r['kind'] not in ('medical', 'conditional_medical'))
                pending = [prerequisite_label(r) for r in relevant[:4]]
            else:
                known, pending = c['card_known'], c['card_pending']
            status = {'RECRUITING': '招募中', 'NOT_YET_RECRUITING': '即将招募', 'ENROLLING_BY_INVITATION': '按邀请入组'}[c['status']]
            parts.append(f'<article class="study-card" id="trial-{nct}" data-decision="{e(c["decision"])}"><div class="study-heading"><div><h3>{e(c["display_name"])}</h3><span class="nct-id">{nct}</span></div><span class="recruitment">{status}</span></div>')
            if cohorts['preferred']:
                names = '、'.join(dict.fromkeys(cohort_label(r) for r in cohorts['preferred']))
                parts.append(f'<p class="possible-cohorts"><strong>可能适用：</strong>{e(names)}</p>'
                             '<p class="cohort-note">不同入组路径可选择；仍需确认该路径的其余条件。</p>')
            elif cohorts['alternatives']:
                parts.append('<p class="cohort-note">具体入组路径待确认；不同替代路径不需同时满足。</p>')
            parts.append(f'<dl><dt class="known-label">已知匹配</dt><dd>{e(known)}</dd><dt class="pending-label">待确认</dt><dd><ul>')
            parts.extend(f'<li>{e(v)}</li>' for v in pending)
            parts.append('</ul></dd>')
            for r in rs:
                if r['status'] == 'conflict' and r['route'] != 'alternative':
                    parts.append(f'<dt class="conflict-label">明确冲突 · 待复核</dt><dd>{e(r["prerequisite"])}</dd>')
            parts.append(f'</dl><p class="cohort-note">{e(c["pathway"]["status"])}<br>{e(c["pathway"]["cohort_note"])}</p>'
                         f'<div class="study-footer"><span class="muted">完整资格仍待专业筛查</span><a href="https://clinicaltrials.gov/study/{nct}" target="_blank" rel="noopener">官方详情 ↗</a></div>'
                         f'<details class="source-detail"><summary>原始证据与判断依据{f" · {len(rs)} 项" if rs else ""}</summary><p class="official-name">{e(c["title"])}</p>')
            if cohorts['inactive']:
                names = '、'.join(dict.fromkeys(cohort_label(r) for r in cohorts['inactive']))
                parts.append(f'<p class="cohort-note">{e(names)}不适用，原始冲突证据保留如下。此记录仅涉及对应替代路径，不改变研究候选结果。</p>')
            for r in rs:
                ev = '；'.join(v['quote'] for v in r['patient_evidence']) or '病例未提供足够信息，不等于未发生。'
                parts.append(f'<section class="trial-rule" data-status="{r["status"]}"><p>{badge(r["status"], labels)} <strong>{e(r["prerequisite"])}</strong></p>'
                             f'<p class="muted">适用范围：{e(r["scope"])}</p><p>招募条件原文：</p><blockquote>{e(r["trial_quote"])}</blockquote>'
                             f'<p>病例原文证据：{e(ev)}</p><p class="muted">{e(r["explanation"])}</p></section>')
            parts.append(raw('完整病例原文', data['patient']))
            parts.append('<details><summary>完整招募原文</summary><blockquote>' + e(c['eligibility_text']) + '</blockquote></details>')
            parts.append(raw('实验原始判断与复核记录', {k: v for k, v in c.items()
                         if k not in ('prerequisites', 'eligibility_text')}))
            parts.append('</details></article>')
        parts.append('</div></details>')
    parts.append(f'<details class="excluded-studies"><summary>{"已排除研究" if formal else "实验中已排除"}（{len(excluded)}）</summary>')
    for r in excluded:
        parts.append(f'<article class="card"><h3>{e(r["nct_id"])} · {e(r["title"])}</h3><p>{e(r["reason"])}</p>')
        for evidence in r['display_evidence']:
            parts.append(f'<blockquote>{e(evidence["trial_quote"])}</blockquote><p>病例原文：{e(evidence["patient_quote"])}</p>')
        parts.append(raw('原始排除记录', r) + '</article>')
    parts.append('</details></div>')
    if formal:
        parts = [part.replace('数据来自已保存的单病例实验和关键前提审阅。以下开发操作沿用viewer原有功能。', '数据来自本次正式临床试验账本；候选资格仍需研究团队筛查。') for part in parts]
    # Move existing controls, preserving their nodes/IDs/listeners; restore on other steps.
    parts.append('''<script>(function(){
const target=document.getElementById('trial-process-tools');
const items=['case-technical-info','app-rerun'].map(id=>document.getElementById(id)).filter(Boolean).map(node=>{const anchor=document.createComment('viewer-original-position');node.before(anchor);return {node,anchor}});
function place(){const hash=location.hash;const active=hash==='#panel-3b'||(hash==='#step3'&&document.getElementById('tab-3b').getAttribute('aria-selected')==='true');document.body.classList.toggle('step3b-experiment-active',active);items.forEach(({node,anchor})=>active?target.append(node):anchor.after(node))}
window.addEventListener('hashchange',place);place();
})();</script>''')
    return '\n'.join(parts)


def panel(case_id: str) -> str:
    ledger = ROOT/'out/step3'/f'{case_id}.json'
    exported = ROOT/'out/3b'/case_id/'result.json'
    if ledger.exists() and (not exported.exists() or ledger.stat().st_mtime_ns > exported.stat().st_mtime_ns):
        return saved_panel(case_id)
    experimental = experiment_panel(case_id)
    if experimental:
        return experimental
    return '<p class="muted">此病例尚未运行新版临床试验实验，暂无实验结果。</p>'

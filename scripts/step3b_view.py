"""Read-only clinical trial view of saved Step 3 ledgers; no analysis or network."""
from __future__ import annotations

import html
import json
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


def panel(case_id: str) -> str:
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

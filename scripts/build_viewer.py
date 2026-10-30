"""Step 2.5 review viewer: static HTML pages from out/step<N>/ results (no server, no LLM).

Usage:
    python scripts/build_viewer.py                          # Chinese UI (default)
    python scripts/build_viewer.py --lang en                # English UI
    python scripts/build_viewer.py --compare 20261030-1200  # compare with a named earlier snapshot

Writes out/review/<timestamp>[-en]/ (index.html, cases/<id>.html, compare.html, data/ copies of the
step outputs it was built from, review.json) and out/review/index.html listing all snapshots.
Snapshots are compared with the previous snapshot in the same language.
Every number shown is read from the step outputs; the page computes nothing beyond counting
and laying out. Views (design: Notion "Step 2.5", section 7.3.5):
  1 overview table             2 reasoning chain            3 variant card
  4 source-text highlight      5 candidate funnel           6 symptom x disease matrix
  7 score bars + ambiguity line  8 evidence tree (Step 3+; structure reserved)  9 run comparison
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitx import runmeta  # noqa: E402

OUT = ROOT / "out"
REVIEW = OUT / "review"
CLEAN_VALIDATION = {"AITX-00007"}
USED_VALIDATION = {"AITX-00011"}
e = html.escape
LANG = "zh"


def L(zh: str, en: str) -> str:
    """UI text in the selected language. Data from the result files is shown as is."""
    return en if LANG == "en" else zh


def step_names() -> dict[int, str]:
    return {1: L("变异解析", "Variant parsing"), 2: L("疾病归一化", "Disease resolution"),
            3: L("证据检索", "Evidence retrieval"), 4: L("报告合成", "Report synthesis"), 5: L("核查", "Verification")}


STEPS = (1, 2, 3, 4, 5)
GROUP_ORDER = ["practice", "validation_clean", "validation_used", "eval", "other"]


def group_label(g: str) -> str:
    return {"practice": L("练习", "Practice"), "validation_clean": L("验证（干净）", "Validation (clean)"),
            "validation_used": L("验证（已用于发现问题）", "Validation (used to find issues)"),
            "eval": L("评测", "Evaluation"), "other": L("其他", "Other")}[g]


def status_label(s: str) -> str:
    return {"resolved": L("已确定", "Resolved"), "ambiguous": L("有歧义", "Ambiguous"),
            "unresolved": L("未确定", "Unresolved")}.get(s, s)


def moi_label(s: str) -> str:
    return {"consistent": L("吻合", "consistent"), "conditional": L("条件吻合", "conditional"),
            "unknown": L("未知", "unknown"), "inconsistent": L("不吻合", "inconsistent")}.get(s, s)


def basis_label(s: str | None) -> str:
    return {"explicit": L("原文点名", "named in the text"), "clinvar": L("ClinVar 变异级证据", "ClinVar variant-level evidence"),
            "phenotype": L("症状分", "phenotype score"), "inheritance": L("遗传方式分层", "inheritance tier"),
            "only_candidate": L("唯一候选", "only candidate")}.get(s or "", s or "")


STATUS_CLS = {"resolved": "pass", "ambiguous": "warn", "unresolved": "fail"}


# ------------------------------------------------------------------ data model

def group_of(cid: str) -> str:
    if cid.startswith("PRAC-"):
        return "practice"
    if cid in CLEAN_VALIDATION:
        return "validation_clean"
    if cid in USED_VALIDATION:
        return "validation_used"
    if cid.startswith("AITX-4"):
        return "eval"
    return "other"


def step_status(k: int, r: dict | None) -> tuple[str, str]:
    """(pass | warn | fail | not_run, short text) for the reasoning chain."""
    if r is None:
        return "not_run", L("未运行", "not run")
    if k == 1:
        checks = [c for v in r["variants"] for c in v["checks"]]
        if any(c["status"] == "fail" for c in checks):
            return "fail", L("自检失败", "self-check failed")
        if any(c["status"] == "warn" for c in checks):
            return "warn", L("自检有警告", "self-check warnings")
        return "pass", L(f"{len(r['variants'])} 个变异，自检全过", f"{len(r['variants'])} variant(s), all checks pass")
    if k == 2:
        if any(c["status"] == "fail" for c in r["checks"]):
            return "fail", L("校验失败", "checks failed")
        st = r["primary"]["status"]
        return {"resolved": "pass", "ambiguous": "warn"}.get(st, "fail"), status_label(st)
    return ("pass" if r.get("ok", True) else "fail"), L("已运行", "ran")


def evidence_tree(s2: dict, s3: dict | None) -> dict:
    """View 8 data: diagnosis branch -> evidence layer -> section -> action -> evidence leaf.

    Step 3 fills `layers`; until then each diagnosis branch is present with empty layers.
    Leaf shape reserved: {claim, quote, source_url, source_id, accessed_at, applies_to}.
    `role` is a language-neutral code: primary | ambiguous_1 | ambiguous_2 | ambiguous_3.
    """
    p = s2["primary"]
    branches = []
    if p["id"]:
        branches.append({"diagnosis_id": p["id"], "label": p["label"],
                         "role": "primary" if p["status"] == "resolved" else "ambiguous_1", "layers": []})
        if p["status"] == "ambiguous":
            for i, a in enumerate(p["alternatives"][:2], 2):
                branches.append({"diagnosis_id": a["id"], "label": a["label"], "role": f"ambiguous_{i}", "layers": []})
    if s3:
        for b in branches:
            b["layers"] = (s3.get("tree") or {}).get(b["diagnosis_id"], [])
    return {"status": "filled" if s3 else "reserved", "branches": branches}


def load_case(cid: str) -> dict:
    steps = {}
    for k in STEPS:
        p = runmeta.path(k, cid)
        steps[k] = json.loads(p.read_text()) if p.exists() else None
    return {"id": cid, "group": group_of(cid), "steps": steps,
            "status": {k: step_status(k, steps[k]) for k in STEPS},
            "tree": evidence_tree(steps[2], steps[3]) if steps[2] else None}


def summary_row(c: dict) -> dict:
    """Language-neutral row (also stored in review.json for later comparisons)."""
    s1, s2 = c["steps"][1], c["steps"][2]
    p = s2["primary"]
    return {"id": c["id"], "group": c["group"],
            "variants": [f"{v['gene']} {v['variant_cdna']} ({v['zygosity']})" for v in s2["inheritance_evidence"]["variants"]],
            "primary": p["label"], "omim": p["omim"], "status": p["status"], "confidence": p.get("confidence"),
            "basis": p["basis"], "n_alternatives": len(p["alternatives"]),
            "phenotypes": [f"{'NOT ' if x['status'] == 'excluded' else ''}{x['label']}" for x in s2["phenotypes"]],
            "scores": {cc["key"]: cc["phenotype"]["score"] for cc in s2["candidates"] if cc.get("compete")},
            "problems": [f"step1 {ch['name']}: {ch['status']}" for v in (s1 or {}).get("variants", [])
                         for ch in v["checks"] if ch["status"] != "pass"]
            + [f"step2 {ch['name']}: {ch['status']}" for ch in s2["checks"] if ch["status"] != "pass"]}


# ------------------------------------------------------------------- html bits

CSS = """
:root{--bg:#fbfbfa;--fg:#1f2328;--muted:#656d76;--line:#d8dee4;--card:#fff;--pass:#1a7f37;--warn:#bf8700;
--fail:#cf222e;--grey:#8c959f;--acc:#0969da;--hl:#fff8c5;--hlx:#ffebe9;--bar:#54aeff;--barp:#0969da}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8d96a0;--line:#30363d;--card:#161b22;
--pass:#3fb950;--warn:#d29922;--fail:#f85149;--grey:#6e7681;--acc:#4493f8;--hl:#3b2e00;--hlx:#4b1113;--bar:#1f6feb;--barp:#4493f8}}
*{box-sizing:border-box}body{margin:0;font:14px/1.55 -apple-system,"PingFang SC","Helvetica Neue",sans-serif;
background:var(--bg);color:var(--fg)}main{max-width:1180px;margin:0 auto;padding:20px 16px 60px}
a{color:var(--acc)}h1{font-size:22px;margin:4px 0 2px}h2{font-size:17px;margin:28px 0 8px;padding-top:8px;
border-top:1px solid var(--line)}h3{font-size:14px;margin:14px 0 6px}.muted{color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:8px 0}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:5px 7px;
text-align:left;vertical-align:top}th{color:var(--muted);font-weight:600}.wrap{overflow-x:auto}
.tag{display:inline-block;padding:0 7px;border-radius:10px;font-size:12px;border:1px solid currentColor}
.pass{color:var(--pass)}.warn{color:var(--warn)}.fail{color:var(--fail)}.not_run{color:var(--grey)}
.chain{display:flex;gap:6px;align-items:stretch;flex-wrap:wrap}.node{flex:1;min-width:150px;border:2px solid currentColor;
border-radius:8px;padding:8px 10px;background:var(--card);text-decoration:none}.node b{display:block;color:var(--fg)}
.arrow{align-self:center;color:var(--muted)}.ctx{font-size:16px;line-height:2.1}
.hl{background:var(--hl);border-bottom:2px solid var(--warn);position:relative;cursor:help;padding:1px 2px}
.hl.exc{background:var(--hlx);border-color:var(--fail)}.tip{display:none;position:absolute;left:0;top:1.9em;z-index:9;
min-width:300px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:12.5px;
line-height:1.5;box-shadow:0 4px 14px rgba(0,0,0,.15)}.hl:hover .tip,.hl:focus .tip{display:block}
.funnel{display:flex;gap:8px;flex-wrap:wrap}.stage{flex:1;min-width:170px}.stage .n{font-size:24px;font-weight:700}
.bars .row{display:grid;grid-template-columns:minmax(150px,330px) 1fr 70px;gap:8px;align-items:center;margin:3px 0}
.track{position:relative;height:16px;background:rgba(127,127,127,.12);border-radius:3px}
.fill{position:absolute;left:0;top:0;bottom:0;background:var(--bar);border-radius:3px}.fill.p{background:var(--barp)}
.thr{position:absolute;top:-4px;bottom:-4px;width:0;border-left:2px dashed var(--fail)}
.mx td.c{text-align:center;font-variant-numeric:tabular-nums}.mx th.v{writing-mode:vertical-rl;transform:rotate(180deg);
max-height:180px;font-weight:500}details>summary{cursor:pointer}ul.tree{list-style:none;padding-left:18px;margin:4px 0}
ul.tree li{border-left:1px solid var(--line);padding-left:10px;margin:3px 0}code{font-size:12.5px}
"""


def page(title: str, body: str, depth: int = 0) -> str:
    up = "../" * depth
    return (f"<!doctype html><html lang='{LANG}'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>{e(title)}</title>"
            f"<style>{CSS}</style></head><body><main><p class='muted'><a href='{up}index.html'>{L('总表', 'Overview')}</a> · "
            f"<a href='{up}compare.html'>{L('版本对比', 'Run comparison')}</a></p>{body}</main></body></html>")


def tag(cls: str, text: str) -> str:
    return f"<span class='tag {cls}'>{e(text)}</span>"


def link(url: str | None, text: str) -> str:
    return f"<a href='{e(url)}' target='_blank' rel='noopener'>{e(text)}</a>" if url else e(text)


# ------------------------------------------------------------------ case views

def v_chain(c: dict) -> str:
    targets = {1: "#variant", 2: "#disease", 3: "#tree", 4: "#tree", 5: "#tree"}
    nodes = []
    for k, name in step_names().items():
        cls, txt = c["status"][k]
        nodes.append(f"<a class='node {cls}' href='{targets[k]}'><b>Step {k} {e(name)}</b>{e(txt)}</a>")
    return "<div class='chain'>" + "<span class='arrow'>→</span>".join(nodes) + "</div>"


def v_variant(s1: dict | None) -> str:
    if not s1:
        return f"<p class='muted'>{L('没有第 1 步输出。', 'No step 1 output.')}</p>"
    out = []
    for v in s1["variants"]:
        ex, nmd, mech = v["exon"], v["nmd"], v["mechanism_hypothesis"]
        checks = "".join(f"<tr><td>{tag(ch['status'], ch['status'])}</td><td>{e(ch['name'])}</td>"
                         f"<td>{e(ch['detail'])}</td></tr>" for ch in v["checks"])
        src = " · ".join(link(x.get("source"), x.get("what", L("来源", "source"))[:60]) for x in v.get("evidence", []))
        last = L("（最后一个）", " (last exon)") if ex.get("is_last_exon") else ""
        out.append(f"""<div class='card'><h3>{e(v['gene'])} {e(v['transcript'])} {e(v['variant_cdna'])}
 {e(v.get('variant_protein') or '')} {tag('pass' if v['ok'] else 'fail', L('自检全过', 'all checks pass') if v['ok'] else L('自检失败', 'self-check failed'))}</h3>
<table><tr><th>{L('类型', 'Class')}</th><td>{e(v['variant_class'])}</td><th>{L('合子状态', 'Zygosity')}</th><td>{e(v['zygosity'])}
 ({e(v['allelic_state'].get('note', ''))})</td></tr>
<tr><th>{L('外显子', 'Exon')}</th><td>{ex.get('number')} / {ex.get('total')}{e(last)}</td>
<th>{L('蛋白长度', 'Protein length')}</th><td>{v['protein_length']} aa</td></tr>
<tr><th>{L('首个受影响氨基酸', 'First affected residue')}</th><td>{v.get('first_affected_aa')}</td>
<th>{L('新终止位置', 'New stop position')}</th><td>{v.get('ptc_aa_position')}</td></tr>
<tr><th>{L('截短后长度', 'Truncated length')}</th><td>{v.get('truncated_protein_length')}
 ({L('保留比例', 'fraction retained')} {v.get('fraction_of_protein_retained')})</td>
<th>{L('NMD 预测', 'NMD prediction')}</th><td>{e(str(nmd.get('prediction')))} — {e(str(nmd.get('reason', '')))}</td></tr>
<tr><th>{L('机制初判', 'Mechanism hypothesis')}</th><td colspan='3'>{e(mech['hypothesis'])}
 ({L('置信度', 'confidence')} {e(mech['confidence'])}): {e(mech['basis'])}</td></tr>
</table><details><summary>{L('自检', 'Self-checks')} {len(v['checks'])}</summary><table>{checks}</table></details>
<p class='muted'>{L('来源', 'Sources')}: {src}</p></div>""")
    return "".join(out)


def _sample_marks(term: dict, samples: list[dict]) -> str:
    marks = []
    for i, smp in enumerate(samples, 1):
        ids = {t for t, st in smp["terms"] if st == term["status"]}
        name = L(f"抽样{i}", f"sample {i}")
        if term["hpo_id"] in ids:
            marks.append(f"{name} ✓")
        elif ids & set(term.get("merged_from", [])):
            marks.append(f"{name} ✓ " + L("（更具体的下级）", "(a more specific child)"))
        else:
            marks.append(f"{name} ✗")
    return "; ".join(marks)


def v_highlight(s2: dict, context: str) -> str:
    ex = s2["phenotype_extraction"]
    spans = []
    for p in s2["phenotypes"]:
        i = context.find(p["quote"])
        if i >= 0:
            spans.append((i, i + len(p["quote"]), p))
    spans.sort(key=lambda x: (x[0], -x[1]))
    parts, pos = [], 0
    for a, b, p in spans:
        if a < pos:
            continue
        onset = p.get("onset", {})
        tip = (f"<b>{e(p['hpo_id'])} {e(p['label'])}</b><br>"
               f"{L('明确没有', 'explicitly absent') if p['status'] == 'excluded' else L('存在', 'present')}; "
               f"{L('映射方式', 'mapping')}: {e(p.get('mapping', ''))}<br>"
               f"{L('投票', 'votes')} {p['votes']}/{len(ex['samples'])}: {e(_sample_marks(p, ex['samples']))}"
               + (f"<br>{L('合并了下级', 'merged children')}: {e(', '.join(p['merged_from']))}" if p.get("merged_from") else "")
               + (f"<br>{L('该症状起病', 'onset of this symptom')}: {e(str(onset.get('months_min')))}–{e(str(onset.get('months_max')))} "
                  + L("月", "months") if onset.get("months_min") is not None else ""))
        parts.append(e(context[pos:a]))
        parts.append(f"<span class='hl{' exc' if p['status'] == 'excluded' else ''}' tabindex='0'>"
                     f"{e(context[a:b])}<span class='tip'>{tip}</span></span>")
        pos = b
    parts.append(e(context[pos:]))
    facts = s2["patient_facts"]
    onset = s2.get("patient_onset") or {}
    rows = [(L("年龄（月）", "Age (months)"), facts["age"].get("months"), facts["age"].get("quote")),
            (L("性别", "Sex"), facts["sex"].get("value"), facts["sex"].get("quote")),
            (L("变异来源", "Variant origin"), facts["variant_origin"].get("value"), facts["variant_origin"].get("quote")),
            (L("家族史", "Family history"), facts["family_history"].get("statement"), facts["family_history"].get("quote")),
            (L("用于打分的起病年龄", "Onset used for scoring"),
             f"{onset.get('min')}–{onset.get('max')} {L('月', 'months')} ({onset.get('kind')})" if onset else L("未知", "unknown"),
             onset.get("quote"))]
    facts_html = "".join(f"<tr><th>{e(k)}</th><td>{e(str(v))}</td><td class='muted'>{e(str(q or ''))}</td></tr>"
                         for k, v, q in rows)
    other = "".join(f"<li>{e(u['quote'])} → {e(u.get('label') or '')} {e(u.get('hpo_id') or '')}: "
                    + L(f"只有 {u['votes']} 次抽样，未保留", f"only {u['votes']} sample(s), not kept") + "</li>"
                    for u in ex["unstable_phenotypes"])
    rej: dict = {}
    for r in ex["rejected_phenotypes"]:
        k = (r["quote"], (r.get("reasons") or ["?"])[-1])
        rej[k] = rej.get(k, 0) + 1
    rej_html = "".join(f"<li>{e(q)}: {e(why)} ({n}×)</li>" for (q, why), n in rej.items())
    legend = L("黄色 = 存在的症状，红色 = 明确没有；鼠标悬停看 HPO 术语和 3 次抽样结果。",
               "Yellow = present, red = explicitly absent; hover to see the HPO term and the three samples.")
    return (f"<div class='card ctx'>{''.join(parts)}</div><p class='muted'>{e(legend)}</p><table>{facts_html}</table>"
            + (f"<h3>{L('未进入结果的症状', 'Features not in the result')}</h3><ul>{other}{rej_html}</ul>" if other or rej_html else ""))


def v_funnel(s2: dict) -> str:
    allc = s2["candidates"] + s2["not_supported"]

    def reason_has(c, word):
        return any(word in r for r in c.get("exclusion_reasons", []))
    stage1 = [c for c in allc if not reason_has(c, "obsolete") and not reason_has(c, "Disputed")]
    stage2 = [c for c in stage1 if not reason_has(c, "inheritance")]
    stage3 = [c for c in stage2 if c.get("compete")]
    drop1 = [c for c in allc if c not in stage1]
    drop2 = [c for c in stage1 if c not in stage2]
    drop3 = [c for c in stage2 if c not in stage3]

    def why3(c):
        m = c.get("merge", {})
        if m.get("role") == "broader":
            return L(f"无症状注释的上级概念，并入 {', '.join(m.get('narrower', []))}",
                     f"parent concept without annotations, folded into {', '.join(m.get('narrower', []))}")
        if m.get("role") == "equivalent":
            return L(f"与 {', '.join(m.get('equivalent_to', []))} 等价", f"equivalent to {', '.join(m.get('equivalent_to', []))}")
        return L("其他", "other")
    tiers: dict = {}
    for c in stage3:
        tiers.setdefault(c["inheritance"]["result"], []).append(c)
    order = ["consistent", "conditional", "unknown", "inconsistent"]
    tier_html = "; ".join(f"{moi_label(k)} {len(v)}" for k, v in sorted(tiers.items(), key=lambda x: order.index(x[0])))
    names = "".join(f"<li>{e(c['label'])} <span class='muted'>{e(c['key'])}</span></li>" for c in stage3)
    li1 = "".join(f"<li>{e(c['label'])}: {e('; '.join(c['exclusion_reasons']))}</li>" for c in drop1)
    li2 = "".join(f"<li>{e(c['label'])}: {e(c['inheritance']['reason'])}</li>" for c in drop2)
    li3 = "".join(f"<li>{e(c['label'])}: {e(why3(c))}</li>" for c in drop3)
    return f"""<div class='funnel'>
<div class='card stage'><div class='muted'>{L('全部候选', 'All candidates')}</div><div class='n'>{len(allc)}</div>
<div class='muted'>{L('GenCC / ClinGen / HPO / Orphanet，按 MONDO 合并', 'GenCC / ClinGen / HPO / Orphanet, merged by MONDO')}</div></div>
<div class='card stage'><div class='muted'>{L('证据强度后', 'After evidence strength')}</div><div class='n'>{len(stage1)}</div>
<details><summary>{L(f'去掉 {len(drop1)} 个（作废术语或只有 Disputed/Refuted）', f'{len(drop1)} removed (obsolete, or only Disputed/Refuted)')}</summary><ul>{li1}</ul></details></div>
<div class='card stage'><div class='muted'>{L('遗传方式后', 'After inheritance')}</div><div class='n'>{len(stage2)}</div>
<details><summary>{L(f'去掉 {len(drop2)} 个（不吻合）', f'{len(drop2)} removed (inconsistent)')}</summary><ul>{li2}</ul></details></div>
<div class='card stage'><div class='muted'>{L('进入比较', 'Compared')}</div><div class='n'>{len(stage3)}</div>
<details><summary>{L(f'合并掉 {len(drop3)} 个', f'{len(drop3)} merged')}</summary><ul>{li3}</ul></details>
<div class='muted'>{L('按遗传方式分层', 'Inheritance tiers')}: {e(tier_html)}</div>
<details><summary>{L('名单', 'List')}</summary><ul>{names}</ul></details></div>
</div>"""


def _compared(s2: dict) -> list[dict]:
    cs = [c for c in s2["candidates"] if c.get("compete")]
    return sorted(cs, key=lambda c: (-(c["phenotype"]["score"] if c["phenotype"]["score"] is not None else -1e9), c["key"]))


def v_matrix(s2: dict) -> str:
    cs = _compared(s2)[:8]
    terms = list(s2["phenotypes"])
    if not cs or not terms:
        return f"<p class='muted'>{L('没有可比较的候选或症状。', 'No candidates or features to compare.')}</p>"
    head = "".join(f"<th class='v' title='{e(c['key'])}'>{e(c['label'][:48])}</th>" for c in cs)
    no_ann = L("无注释", "no annotations")
    rows = []
    for p in terms:
        cells = []
        for c in cs:
            ph = c["phenotype"]
            if ph["score"] is None:
                cells.append(f"<td class='c muted'>{no_ann}</td>")
                continue
            if p["status"] == "present":
                m = next((m for m in ph["matches"] if m["patient_term"] == p["hpo_id"]), None)
                if m and m["ic"] > 0:
                    shade = min(1.0, m["ic"] / 8)
                    tip = L(f"疾病注释 {m['disease_term']}，共同上级 {m['common_ancestor']}",
                            f"disease annotation {m['disease_term']}, common ancestor {m['common_ancestor']}")
                    exact = L("（同一术语）", " (same term)") if m["disease_term"] == p["hpo_id"] else ""
                    cells.append(f"<td class='c' title='{e(tip)}' style='background:rgba(9,105,218,{shade * 0.55:.2f})'>"
                                 f"{m['ic']}{e(exact)}</td>")
                else:
                    cells.append("<td class='c muted'>—</td>")
            else:
                pen = next((x for x in ph["penalties"] if x["patient_absent_term"] == p["hpo_id"]), None)
                cells.append(f"<td class='c fail' title='{e(L('疾病常见此症状，病人明确没有', 'common in the disease, explicitly absent in the patient'))}'>−{pen['penalty']}</td>"
                             if pen else "<td class='c muted'>—</td>")
        rows.append(f"<tr><td>{'NOT ' if p['status'] == 'excluded' else ''}{e(p['label'])} "
                    f"<span class='muted'>{e(p['hpo_id'])}</span></td>{''.join(cells)}</tr>")
    onset_row = "".join(f"<td class='c'>{e(str(c['phenotype'].get('onset', {}).get('result', '')))}"
                        + (f"<br>{c['phenotype']['onset']['adjustment']}" if c['phenotype'].get('onset', {}).get('adjustment') else "")
                        + "</td>" for c in cs)
    total = "".join(f"<td class='c'><b>{c['phenotype']['score'] if c['phenotype']['score'] is not None else '—'}</b></td>" for c in cs)
    note = L("格子里的数字 = 这个症状被该疾病的注释“解释”的程度（信息量 IC，越大越特异；蓝色越深越高）；"
             "“同一术语”表示疾病直接注释了这个症状，否则是通过共同上级匹配。红色负数 = 病人明确没有、但该病常见的症状带来的扣分。"
             "症状分 = 各症状得分的平均 − 扣分（含起病年龄扣分）。",
             "Each cell = how well the disease's annotations explain the feature (information content, IC; higher is "
             "more specific, darker blue). \"Same term\" = the disease is annotated with this exact feature; otherwise the "
             "match is through a common ancestor. Red negative = penalty for a feature common in the disease but explicitly "
             "absent in the patient. Score = mean of feature scores − penalties (including the onset penalty).")
    corner = L("病人症状 \\ 候选疾病", "Patient feature \\ candidate")
    return (f"<div class='wrap'><table class='mx'><tr><th>{corner}</th>{head}</tr>"
            f"{''.join(rows)}<tr><td class='muted'>{L('起病年龄', 'Onset')}</td>{onset_row}</tr>"
            f"<tr><td><b>{L('症状分', 'Score')}</b></td>{total}</tr></table></div><p class='muted'>{e(note)}</p>")


def v_bars(s2: dict) -> str:
    p = s2["primary"]
    cs = _compared(s2)
    scored = [c["phenotype"]["score"] for c in cs if c["phenotype"]["score"] is not None]
    if not scored:
        return f"<p class='muted'>{L('没有可比较的症状分。', 'No phenotype scores to compare.')}</p>"
    thr = p.get("ambiguity_threshold_score")
    top = max(max(scored), thr or 0, 1e-9)
    alt = {a["id"] for a in p["alternatives"]}
    rows = []
    for c in cs:
        s = c["phenotype"]["score"]
        role = "primary" if c["key"] == p["id"] else ("tied" if c["key"] in alt else "")
        role_tag = tag("pass", L("首选", "primary")) if role == "primary" else (tag("warn", L("并列", "tied")) if role else "")
        width = 0 if s is None or s <= 0 else 100 * s / top
        thr_html = f"<span class='thr' style='left:{100 * thr / top:.1f}%' title='{e(L('歧义线', 'ambiguity line'))} {thr}'></span>" if thr else ""
        cv = L("；有 ClinVar 支持", "; ClinVar support") if c["clinvar"] else ""
        rows.append(f"<div class='row'><div>{e(c['label'][:60])} {role_tag}"
                    f"<div class='muted'>{L('遗传方式', 'inheritance')}: {e(moi_label(c['inheritance']['result']))}{e(cv)}</div></div>"
                    f"<div class='track'><span class='fill{' p' if role == 'primary' else ''}' style='width:{width:.1f}%'></span>{thr_html}</div>"
                    f"<div>{s if s is not None else L('无注释', 'no annotations')}</div></div>")
    note = (L(f"红色虚线 = 歧义线 {thr}（首选得分 {p.get('primary_score')} × (1 − {p.get('ambiguity_gap')})）。"
              "同一遗传方式层内，得分超过这条线的候选与首选算作分不开。",
              f"Red dashed line = ambiguity line {thr} (primary score {p.get('primary_score')} × (1 − {p.get('ambiguity_gap')})). "
              "Within the same inheritance tier, a candidate above this line cannot be separated from the primary.")
            if thr else L("首选没有症状分，没有歧义线。", "The primary has no phenotype score, so there is no ambiguity line."))
    return f"<div class='bars'>{''.join(rows)}</div><p class='muted'>{e(note)}</p>"


def v_decision(s2: dict) -> str:
    p = s2["primary"]
    reasons = "".join(f"<li>{e(r)}</li>" for r in p["reasons"])
    notes = "".join(f"<li>{e(r)}</li>" for r in p.get("confidence_notes") or [])
    samples = "; ".join(f"{L(f'抽样{i}', f'sample {i}')}: {status_label(x['status'])} {e(str(x['id']))}"
                        for i, x in enumerate(p["per_sample"], 1))
    alts = "".join(f"<li>{e(a['label'])} <span class='muted'>{e(a['id'])}</span></li>" for a in p["alternatives"])
    exp = s2.get("explicit_diagnosis") or {}
    exp_html = ""
    if exp:
        ms = "".join(f"<li>{e(m['candidate'])}: " + ", ".join(f"{e(x['how'])} “{e(x['text'])}”" for x in m["evidence"]) + "</li>"
                     for m in exp.get("matches", []))
        sk = "".join(f"<li>{e(x['name'])}: {e(x['reason'])}</li>" for x in exp.get("skipped_names", []))
        al = "".join(f"<li class='fail'>{e(a)}</li>" for a in exp.get("alerts", []))
        exp_html = (f"<h3>{L('原文点名', 'Named in the text')}</h3><ul>{ms}{al}</ul>"
                    + (f"<details><summary>{L('当作症状、未当作诊断的名称', 'Names treated as symptoms, not diagnoses')}</summary><ul>{sk}</ul></details>" if sk else ""))
    omim = " ".join(link(f"https://omim.org/entry/{o.split(':')[1]}", o) for o in p["omim"])
    return f"""<div class='card'><b>{e(p['label'] or '—')}</b> {omim}
 {tag(STATUS_CLS[p['status']], status_label(p['status']))} {L('置信度', 'confidence')} {e(str(p.get('confidence')))} ·
 {L('依据', 'basis')}: {e(basis_label(p['basis']))}
<ul>{reasons}</ul>{f"<h3>{L('并列候选', 'Tied candidates')}</h3><ul>{alts}</ul>" if alts else ""}
{f"<h3>{L('置信度说明', 'Confidence notes')}</h3><ul>{notes}</ul>" if notes else ""}
<p class='muted'>{L('3 次抽样各自的结论', 'Result on each of the 3 samples')}: {samples}</p></div>{exp_html}"""


def v_clinvar(s2: dict) -> str:
    out = []
    yes, no = L("是", "yes"), L("否", "no")
    for r in s2["clinvar"]:
        recs = "".join(
            f"<tr><td>{link(x['url'], x['vcv'])}</td><td>{e(x['match'])}</td><td>{e(x['clinical_significance'])}</td>"
            f"<td>{x['stars']} ★</td><td>{e(x['last_evaluated'])}</td><td>{yes if x.get('used_for_ranking') else no}</td>"
            f"<td>{'; '.join(e(t['name']) + (' → ' + e(', '.join(t.get('mapped_candidates') or [])) if t.get('mapped_candidates') else '') for t in x['traits'] if not t['generic'])}</td></tr>"
            for x in r["records"])
        rej = "".join(f"<li>{e(x.get('vcv') or '')} {e(x.get('title') or '')}: {e(x['reason'])}</li>" for x in r["rejected"])
        n_rej = len(r["rejected"])
        rej_title = L(f"检索到但拒收的记录 {n_rej} 条", f"{n_rej} search hit(s) rejected")
        out.append(f"<h3>{e(r['query'])} — {e(r['status'])} {link(r.get('search_url'), L('检索', 'search'))}</h3>"
                   + (f"<div class='wrap'><table><tr><th>{L('记录', 'Record')}</th><th>{L('匹配', 'Match')}</th>"
                      f"<th>{L('临床意义', 'Significance')}</th><th>{L('星级', 'Stars')}</th><th>{L('评估日期', 'Evaluated')}</th>"
                      f"<th>{L('参与排序', 'Ranked')}</th><th>{L('关联疾病 → 候选', 'Conditions → candidates')}</th></tr>{recs}</table></div>"
                      if recs else f"<p class='muted'>{L('ClinVar 未收录。', 'Not in ClinVar.')}</p>")
                   + (f"<details><summary>{rej_title}</summary><ul>{rej}</ul></details>" if rej else ""))
    return "".join(out)


def v_candidates(s2: dict) -> str:
    rows = []
    for c in sorted(s2["candidates"] + s2["not_supported"], key=lambda c: c["key"]):
        val = c["validity"]
        subs = "; ".join(f"{x['submitter']} {x['classification']}" for x in val["submitters"][:8])
        omim = " ".join(link(o["url"], o["id"]) for o in c["omim"])
        state = (L("排除：", "excluded: ") + "; ".join(c["exclusion_reasons"])) if c.get("excluded") else (
            L("参与比较", "compared") if c.get("compete") else L("合并", "merged") + f" ({c.get('merge', {}).get('role')})")
        score = c["phenotype"]["score"] if c["phenotype"]["score"] is not None else L("无注释", "no annotations")
        rows.append(f"<tr><td>{e(c['label'])}<div class='muted'>{link(c.get('mondo_url'), c['key'])} {omim}</div></td>"
                    f"<td>{e(val['summary'])}<div class='muted'>{e(subs)}</div></td>"
                    f"<td>{e(moi_label(c['inheritance']['result']))}<div class='muted'>{e(c['inheritance']['reason'])}</div></td>"
                    f"<td>{score}</td><td>{e(state)}</td></tr>")
    summary = L(f"全部 {len(rows)} 个候选的明细（证据强度、遗传方式、得分、去向）",
                f"All {len(rows)} candidates (evidence strength, inheritance, score, outcome)")
    return (f"<details><summary>{e(summary)}</summary><div class='wrap'><table><tr><th>{L('疾病', 'Disease')}</th>"
            f"<th>{L('证据强度', 'Evidence')}</th><th>{L('遗传方式', 'Inheritance')}</th><th>{L('症状分', 'Score')}</th>"
            f"<th>{L('去向', 'Outcome')}</th></tr>{''.join(rows)}</table></div></details>")


def role_label(r: str) -> str:
    if r == "primary":
        return L("首选", "Primary")
    return L(f"歧义候选 {r.split('_')[1]}", f"Ambiguous candidate {r.split('_')[1]}")


def v_tree(c: dict) -> str:
    t = c["tree"]
    if not t:
        return ""
    placeholder = L("证据层级 → 章节 → 行动 → 证据叶子（原文片段 + 来源链接）：Step 3 运行后填入",
                    "evidence tier → section → action → evidence leaf (verbatim quote + source link): filled in by Step 3")
    items = []
    for b in t["branches"]:
        inner = "".join(f"<li>{e(json.dumps(layer, ensure_ascii=False)[:200])}</li>" for layer in b["layers"]) or \
            f"<li class='muted'>{e(placeholder)}</li>"
        items.append(f"<li><b>{e(role_label(b['role']))}</b>: {e(b['label'])} <span class='muted'>{e(b['diagnosis_id'])}</span>"
                     f"<ul class='tree'>{inner}</ul></li>")
    note = L("结构已预留，Step 3 尚未运行。", "Structure reserved; Step 3 has not run yet. ") if t["status"] == "reserved" else ""
    tail = L("报告里的条件语句将与这里的诊断分支一一对应。", "Conditional statements in the report will map one-to-one to these diagnosis branches.")
    return f"<ul class='tree'>{''.join(items)}</ul><p class='muted'>{e(note + tail)}</p>"


def v_sources(s2: dict) -> str:
    links = []
    for g, info in s2["gene_aliases"].items():
        aliases = ", ".join(info.get("aliases", []) + info.get("previous_symbols", []))
        links.append(f"<li>HGNC {e(g)}: {link(info.get('url'), info.get('hgnc_id') or g)}; {L('别名', 'aliases')} {e(aliases)}</li>")
    for g, chs in s2["genereviews"].items():
        for ch in chs:
            scope = L("该基因专章", "gene-specific chapter") if ch["scope"] == "single_gene" else L("综述章节", "overview chapter")
            links.append(f"<li>GeneReviews {e(g)}: {link(ch['url'], ch['title'])} ({e(scope)})</li>")
    for c in s2["candidates"]:
        for cg in c["validity"]["clingen"]:
            links.append(f"<li>ClinGen: {e(c['label'])} {e(cg['classification'])} {link(cg['report'], L('报告', 'report'))}</li>")
    manifest = "".join(f"<li>{link(m['url'], m['name'])} {L('快照', 'snapshot')} {e(m['snapshot'])}, {m['rows']} {L('行', 'rows')}</li>"
                       for m in s2["sources_manifest"])
    return f"<ul>{''.join(links)}</ul><details><summary>{L('整包数据快照', 'Bulk data snapshots')}</summary><ul>{manifest}</ul></details>"


def case_page(c: dict, context: str) -> str:
    s1, s2 = c["steps"][1], c["steps"][2]
    meta = s2.get("_meta", {})
    hpo = s2.get("hpo_version", "").split("/")[-2] if s2.get("hpo_version") else ""
    made = time.strftime("%Y-%m-%d %H:%M", time.localtime(meta.get("created_at", 0)))
    body = f"""<h1>{e(c['id'])} <span class='muted' style='font-size:14px'>{e(group_label(c['group']))}</span></h1>
<p class='muted'>{L(f"结果文件：第 2 步代码版本 {meta.get('code_commit', '?')}，生成于 {made}；HPO {hpo}",
                    f"Result files: step 2 code {meta.get('code_commit', '?')}, generated {made}; HPO {hpo}")}</p>
<h2>{L('推理链', 'Reasoning chain')}</h2>{v_chain(c)}
<h2 id='variant'>{L('Step 1 变异事实', 'Step 1 variant facts')}</h2>{v_variant(s1)}
<h2 id='disease'>{L('Step 2 结论', 'Step 2 conclusion')}</h2>{v_decision(s2)}
<h2>{L('症状从原文哪里来', 'Where each feature comes from in the text')}</h2>{v_highlight(s2, context)}
<h2>{L('候选疾病怎么被筛掉的', 'How candidates were filtered')}</h2>{v_funnel(s2)}{v_candidates(s2)}
<h2>{L('为什么这样判：症状 × 疾病', 'Why: features × diseases')}</h2>{v_matrix(s2)}
<h2>{L('得分与歧义线', 'Scores and the ambiguity line')}</h2>{v_bars(s2)}
<h2>{L('ClinVar 变异级证据', 'ClinVar variant-level evidence')}</h2>{v_clinvar(s2)}
<h2 id='tree'>{L('证据树（Step 3 起）', 'Evidence tree (from Step 3)')}</h2>{v_tree(c)}
<h2>{L('来源链接', 'Source links')}</h2>{v_sources(s2)}"""
    return page(f"{c['id']} {L('审查', 'review')}", body, depth=1)


# ------------------------------------------------------------- index, compare

def index_page(rows: list[dict], snap: str, commit: str) -> str:
    trs = []
    for r in rows:
        problems = "<br>".join(e(p) for p in r["problems"]) or f"<span class=muted>{L('无', 'none')}</span>"
        trs.append(f"<tr><td><a href='cases/{e(r['id'])}.html'>{e(r['id'])}</a></td><td>{e(group_label(r['group']))}</td>"
                   f"<td>{'<br>'.join(e(v) for v in r['variants'])}</td><td>{e(r['primary'] or '—')}"
                   f"<div class='muted'>{e(' '.join(r['omim']))}</div></td>"
                   f"<td>{tag(STATUS_CLS[r['status']], status_label(r['status']))}</td><td>{e(str(r['confidence']))}</td>"
                   f"<td>{e(basis_label(r['basis']))}</td><td>{r['n_alternatives']}</td><td class='fail'>{problems}</td></tr>")
    head = [L("病例", "Case"), L("分组", "Group"), L("变异", "Variants"), L("首选疾病", "Primary disease"), L("状态", "Status"),
            L("置信度", "Confidence"), L("依据", "Basis"), L("并列数", "Tied"), L("报错/警告", "Errors / warnings")]
    intro = L(f"快照 {snap} · 代码 {commit} · {len(rows)} 个病例。点病例编号看详情。",
              f"Snapshot {snap} · code {commit} · {len(rows)} cases. Click a case for details.")
    body = (f"<h1>{L('审查总表', 'Review overview')}</h1><p class='muted'>{e(intro)}</p><div class='wrap'><table><tr>"
            + "".join(f"<th>{h}</th>" for h in head) + f"</tr>{''.join(trs)}</table></div>")
    return page(L("审查总表", "Review overview"), body)


def compare_page(cur: list[dict], prev: list[dict] | None, snap: str, prev_snap: str | None) -> str:
    title = L("版本对比", "Run comparison")
    if prev is None:
        msg = L(f"快照 {snap} 是第一份快照，没有可对比的旧版本。下次生成时会自动和这一份对比，也可以用 --compare 指定。",
                f"Snapshot {snap} is the first one in this language; nothing to compare yet. The next build compares "
                "with it automatically, or pass --compare.")
        return page(title, f"<h1>{title}</h1><p class='muted'>{e(msg)}</p>")
    old = {r["id"]: r for r in prev}
    names = {"primary": L("首选", "primary"), "status": L("状态", "status"), "confidence": L("置信度", "confidence"),
             "basis": L("依据", "basis")}
    trs = []
    for r in cur:
        o = old.get(r["id"])
        if not o:
            trs.append(f"<tr><td>{e(r['id'])}</td><td>{L('新病例', 'new case')}</td></tr>")
            continue
        diffs = [f"{names[k]}: {e(str(o.get(k)))} → <b>{e(str(r.get(k)))}</b>" for k in names if o.get(k) != r.get(k)]
        po, pn = set(o["phenotypes"]), set(r["phenotypes"])
        if po != pn:
            none = L("无", "none")
            diffs.append(L("症状", "features") + f": {L('去掉', 'removed')} {e(', '.join(sorted(po - pn)) or none)}; "
                         f"{L('新增', 'added')} {e(', '.join(sorted(pn - po)) or none)}")
        sc = [f"{k} {o['scores'].get(k)} → {v}" for k, v in r["scores"].items() if o["scores"].get(k) != v]
        if sc:
            diffs.append(L("得分", "scores") + ": " + e("; ".join(sc[:6])) + (" …" if len(sc) > 6 else ""))
        same = f"<span class=muted>{L('无变化', 'no change')}</span>"
        trs.append(f"<tr><td><a href='cases/{e(r['id'])}.html'>{e(r['id'])}</a></td><td>{'<br>'.join(diffs) or same}</td></tr>")
    body = (f"<h1>{title}</h1><p class='muted'>{e(prev_snap)} → {e(snap)}</p>"
            f"<table><tr><th>{L('病例', 'Case')}</th><th>{L('变化', 'Changes')}</th></tr>{''.join(trs)}</table>")
    return page(title, body)


def snapshots_index() -> None:
    snaps = sorted([p.name for p in REVIEW.iterdir() if p.is_dir() and (p / "index.html").exists()], reverse=True)
    items = "".join(f"<li><a href='{s}/index.html'>{s}</a> {'English' if s.endswith('-en') else '中文'}</li>" for s in snaps)
    (REVIEW / "index.html").write_text(
        f"<!doctype html><html><head><meta charset='utf-8'><title>Review snapshots / 审查快照</title><style>{CSS}</style></head>"
        f"<body><main><h1>审查快照 / Review snapshots</h1><p class='muted'>新的在前 / newest first</p><ul>{items}</ul></main></body></html>")


# ----------------------------------------------------------------------- main

def contexts() -> dict[str, str]:
    out = {}
    for f in [ROOT / "data/cases/practice/official_examples.json", ROOT / "data/cases/aitx_final_patients.json",
              ROOT / "data/cases/validation/phase1_hf_unseen_genes.json"]:
        if f.exists():
            for c in json.loads(f.read_text()):
                out[c["id"]] = c["patient"].get("clinical_context", "")
    return out


def main() -> int:
    global LANG
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["zh", "en"], default="zh", help="UI language (default zh)")
    ap.add_argument("--compare", help="snapshot name under out/review/ to compare with (default: previous one, same language)")
    args = ap.parse_args()
    LANG = args.lang
    ids = sorted(p.stem for p in (OUT / "step2").glob("*.json") if p.stem != "sources_manifest")
    ctx = contexts()
    cases, problems = [], []
    for cid in ids:
        c = load_case(cid)
        if not c["steps"][2] or "_meta" not in c["steps"][2]:
            problems.append(f"{cid}: step 2 output has no provenance; regenerate with scripts/run_pipeline.py")
            continue
        cases.append(c)
    if problems:
        print("\n".join(problems))
    suffix = "-en" if LANG == "en" else ""
    snap = time.strftime("%Y%m%d-%H%M%S") + suffix
    d = REVIEW / snap
    (d / "cases").mkdir(parents=True, exist_ok=True)
    (d / "data").mkdir(exist_ok=True)
    rows = []
    for c in sorted(cases, key=lambda c: (GROUP_ORDER.index(c["group"]), c["id"])):
        (d / "cases" / f"{c['id']}.html").write_text(case_page(c, ctx.get(c["id"], "")))
        for k in STEPS:
            src = runmeta.path(k, c["id"])
            if src.exists():
                shutil.copy(src, d / "data" / f"step{k}-{c['id']}.json")
        rows.append(summary_row(c))
    commit = runmeta.code_commit()
    (d / "review.json").write_text(json.dumps({"schema": "review-v1", "snapshot": snap, "lang": LANG, "code_commit": commit,
                                               "cases": rows, "trees": {c["id"]: c["tree"] for c in cases}},
                                              indent=1, ensure_ascii=False))
    (d / "index.html").write_text(index_page(rows, snap, commit))

    def same_lang(name: str) -> bool:
        return name.endswith("-en") == (LANG == "en")
    prev_name = args.compare or next((p.name for p in sorted(REVIEW.iterdir(), reverse=True)
                                      if p.is_dir() and p.name != snap and same_lang(p.name)
                                      and (p / "review.json").exists()), None)
    prev = json.loads((REVIEW / prev_name / "review.json").read_text())["cases"] if prev_name else None
    (d / "compare.html").write_text(compare_page(rows, prev, snap, prev_name))
    snapshots_index()
    print(f"{len(rows)} case pages -> {d}/index.html")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

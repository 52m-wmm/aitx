"""Step 2.5 review viewer: static HTML pages from out/step<N>/ results (no server, no LLM).

Usage:
    python scripts/build_viewer.py                          # both languages; Chinese by default
    python scripts/build_viewer.py --lang en                # both languages; English by default
    python scripts/build_viewer.py --compare 20261030-1200  # compare with a named earlier snapshot

This is the static export. For live pages (auto-refresh, rerun buttons) run scripts/viewer_app.py,
which renders the same templates per request through render_page().

Writes out/review/<timestamp>/ (index, cases/<id>, compare pages in Chinese `X.html` and English
`X.en.html`, data/ copies of the step outputs it was built from, review.json) and
out/review/index.html listing all snapshots. Every page has a 中文 / EN switch that opens the
same page in the other language (keeping the section anchor) and remembers the choice in the
browser's localStorage; --lang only sets the default when no choice is stored.
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
sys.path.insert(0, str(ROOT / "scripts"))

from aitx import runmeta  # noqa: E402

OUT = ROOT / "out"
REVIEW = OUT / "review"
CLEAN_VALIDATION = {"AITX-00007"}
USED_VALIDATION = {"AITX-00011"}
e = html.escape
LANG = "zh"
DEFAULT_LANG = "zh"


def fn(base: str, lang: str | None = None) -> str:
    """File name of a page in a language: index -> index.html / index.en.html."""
    return f"{base}.en.html" if (lang or LANG) == "en" else f"{base}.html"


def L(zh: str, en: str) -> str:
    """UI text in the selected language. Data from the result files is shown as is."""
    return en if LANG == "en" else zh


def step_names() -> dict[int, str]:
    return {1: L("变异解析", "Variant parsing"), 2: L("疾病归一化", "Disease resolution"),
            3: L("证据检索", "Evidence retrieval"), 4: L("报告合成", "Report synthesis"), 5: L("核查", "Verification")}


STEPS = (1, 2, 3, 4, 5)
GROUP_ORDER = ["practice", "validation_clean", "validation_used", "blind", "eval", "other"]


def group_label(g: str) -> str:
    return {"practice": L("练习", "Practice"), "validation_clean": L("验证（干净）", "Validation (clean)"),
            "validation_used": L("验证（已用于发现问题）", "Validation (used to find issues)"),
            "blind": L("盲测", "Blind test"), "eval": L("评测", "Evaluation"), "other": L("其他", "Other")}[g]


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
    if cid.startswith("BLIND-"):
        return "blind"
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
    if k == 3:
        if not r.get("ok", True):
            return "fail", L("账本校验失败", "ledger checks failed")
        nb, nv = len(r.get("branches", [])), sum(x["status"] == "verified" for x in r.get("evidence", []))
        searched = sum(v == "searched" for v in (r.get("sections_status") or {}).values())
        return "pass", L(f"{nb} 个分支，{nv} 条已核对证据，已检索 {searched}/8 章节",
                         f"{nb} branch(es), {nv} verified items, {searched}/8 sections searched")
    return ("pass" if r.get("ok", True) else "fail"), L("已运行", "ran")


TIER_ORDER = ["established", "emerging", "hypothesized", "background"]


def evidence_tree(s2: dict, s3: dict | None) -> dict:
    """View 8 data: diagnosis branch -> evidence tier -> section -> action -> evidence leaf.

    With a step 3 ledger the tree is built from it (branches in branch_order, leaves = ledger items);
    without one, the step 2 diagnoses are shown with empty layers. Grouping only, no computation.
    """
    if not s3:
        p = s2["primary"]
        branches = []
        if p["id"]:
            branches.append({"diagnosis_id": p["id"], "label": p["label"],
                             "role": "primary" if p["status"] == "resolved" else "ambiguous_1", "layers": []})
            if p["status"] == "ambiguous":
                for i, a in enumerate(p["alternatives"][:2], 2):
                    branches.append({"diagnosis_id": a["id"], "label": a["label"], "role": f"ambiguous_{i}", "layers": []})
        return {"status": "reserved", "branches": branches}
    by_id = {b["id"]: b for b in s3["branches"]}
    branches = []
    for bid in s3.get("branch_order") or list(by_id):
        b = by_id[bid]
        items = [x for x in s3["evidence"] if bid in x["applies_to"]]
        layers = []
        for tier in TIER_ORDER:
            secs = []
            for sec in dict.fromkeys(x["section"] for x in items if x["tier"] == tier):
                acts: dict = {}
                for x in items:
                    if x["tier"] == tier and x["section"] == sec:
                        k = (x.get("action") or {}).get("key") or ""
                        acts.setdefault(k, {"action_key": k or None, "normalized": (x.get("action") or {}).get("normalized"),
                                            "leaves": []})["leaves"].append(x)
                secs.append({"section": sec, "status": s3["sections_status"].get(sec), "actions": list(acts.values())})
            if secs:
                layers.append({"tier": tier, "sections": secs})
        d = b.get("diagnosis") or {}
        branches.append({"diagnosis_id": bid, "label": d.get("label") or b.get("gene"), "role": b["role"],
                         "omim": d.get("omim") or [], "expanded_from": b.get("expanded_from"),
                         "not_expandable": b.get("not_expandable"), "promoted_by": b.get("promoted_by"), "layers": layers,
                         "assessment": [a for a in s3.get("branch_assessment", []) if a["branch"] == bid]})
    return {"status": "filled", "branches": branches, "dropped": s3.get("branches_dropped", []),
            "rules_applied": s3.get("rules_applied", []), "rules_skipped": s3.get("rules_skipped", []),
            "missing": s3.get("missing_information", []), "sections_status": s3.get("sections_status", {})}


def load_case(cid: str, out: Path | None = None) -> dict:
    steps = {}
    for k in STEPS:
        p = runmeta.path(k, cid, out or OUT)
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
svg.fig{width:100%;height:auto;display:block;margin:6px 0 2px;font-family:-apple-system,"PingFang SC",sans-serif}
svg.fig text{fill:var(--fg);font-size:12px}svg.fig text.m{fill:var(--muted);font-size:11px}
svg.fig text.mono{font-family:ui-monospace,Menlo,monospace;font-size:14px}
svg.fig .box{fill:var(--card);stroke:var(--line)}svg.fig .box.chg{fill:var(--hlx);stroke:var(--fail);stroke-width:2}
svg.fig .normal{fill:var(--barp)}svg.fig .garbled{fill:var(--warn)}svg.fig .lost{fill:none;stroke:var(--grey);stroke-dasharray:4 3}
svg.fig .del{fill:var(--hlx);stroke:var(--fail);stroke-width:1.5}svg.fig .mark{stroke:var(--fail);stroke-width:2.5;fill:var(--fail)}
svg.fig .stop{stroke:var(--fg);stroke-width:2.5}svg.fig .utr{fill:var(--grey);opacity:.55}svg.fig .cds{fill:var(--bar)}
svg.fig .jn{stroke:var(--grey);stroke-width:1.2}svg.fig .jn.dn{stroke:var(--warn);stroke-width:2}
svg.fig .jn.dn50{stroke:var(--fail);stroke-width:2.5}svg.fig .axis{stroke:var(--line)}
.figs h4{margin:12px 0 0;font-size:13px}.legend{font-size:12px;color:var(--muted)}
.mol3d{position:relative;width:100%;height:420px;border:1px solid var(--line);border-radius:8px;margin:6px 0;
background:var(--card)}.mol3d .ph{padding:16px;color:var(--muted)}.molbar{margin:4px 0;font-size:12.5px}
.acard{display:block;background:var(--card);border:1px solid var(--line);border-left:5px solid var(--grey);border-radius:8px;
padding:7px 10px;font-size:13px;min-width:0}.acard>summary{list-style:none}.acard>summary::-webkit-details-marker{display:none}
.acard.st-pass{border-left-color:var(--pass)}.acard.st-warn{border-left-color:var(--warn)}.acard.st-fail{border-left-color:var(--fail)}
.acard.st-mixed{border-left-color:var(--acc)}.acard[open]{grid-column:1 / -1 !important;box-shadow:0 2px 10px rgba(0,0,0,.12)}
.acard .abody{margin-top:8px;border-top:1px solid var(--line);padding-top:6px}.acard h4{margin:10px 0 4px;font-size:13px}
.acard blockquote{margin:4px 0;padding:4px 8px;border-left:3px solid var(--line);color:var(--fg)}ul.evl{padding-left:18px}
.tag.mixed{color:var(--acc)}h3.tier{margin:22px 0 4px;font-size:15px}h4.sec{margin:12px 0 6px;font-size:13.5px}
.bhead{position:sticky;top:0;z-index:5;background:var(--bg);padding:6px 0;border-bottom:1px solid var(--line);font-size:13px}
.miss{margin-top:6px}td.nw{white-space:nowrap}.badrow td{background:var(--hlx)}.hidden-acts{margin:6px 0}
@media (max-width:700px){div[style*="grid-template-columns"]{grid-template-columns:1fr !important}.acard{grid-column:auto !important}}
.legend i{display:inline-block;width:12px;height:10px;margin:0 4px 0 10px;vertical-align:middle;border-radius:2px}
"""


SWITCH_JS = """<script>
(function(){var KEY='aitx-review-lang',me=document.documentElement.lang,def='%s';
var sw=document.getElementById('langsw');
function other(){var p=location.pathname.split('/').pop();
 return me==='en'?p.replace(/\\.en\\.html$/,'.html'):p.replace(/\\.html$/,'.en.html');}
sw.addEventListener('click',function(ev){ev.preventDefault();
 try{localStorage.setItem(KEY,me==='en'?'zh':'en');}catch(x){}
 location.href=other()+location.hash;});
var want=def;try{want=localStorage.getItem(KEY)||def;}catch(x){}
if(want!==me){location.replace(other()+location.hash);}
})();</script>"""


def page(title: str, body: str, base: str, depth: int = 0) -> str:
    """base: this page's file name without extension (e.g. "index", "AITX-40003")."""
    up = "../" * depth
    switch = (f"<a id='langsw' href='{fn(base, 'zh' if LANG == 'en' else 'en')}' style='float:right'>"
              f"{'中文' if LANG == 'en' else 'EN'}</a>")
    return (f"<!doctype html><html lang='{LANG}'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>{e(title)}</title>"
            f"<style>{CSS}</style></head><body><main><p class='muted'>{switch}"
            f"<a href='{up}{fn('index')}'>{L('总表', 'Overview')}</a> · "
            f"<a href='{up}{fn('compare')}'>{L('版本对比', 'Run comparison')}</a> · "
            f"<a href='{up}{fn('acceptance')}'>{L('验收对照', 'Acceptance')}</a> "
            + "".join(f"<a href='{up}{fn('acceptance_' + k)}'>{k}</a> " for k in ACCEPT_STEPS)
            + f"· <a href='{up}{fn('blind')}'>{L('盲测', 'Blind test')}</a></p>{body}</main>"
            f"{SWITCH_JS % DEFAULT_LANG}</body></html>")


def tag(cls: str, text: str) -> str:
    return f"<span class='tag {cls}'>{e(text)}</span>"


def link(url: str | None, text: str) -> str:
    return f"<a href='{e(url)}' target='_blank' rel='noopener'>{e(text)}</a>" if url else e(text)


# ------------------------------------------------------------------ case views

def v_chain(c: dict) -> str:
    targets = {1: "#variant", 2: "#disease", 3: "#board", 4: "#board", 5: "#board"}
    nodes = []
    for k, name in step_names().items():
        cls, txt = c["status"][k]
        nodes.append(f"<a class='node {cls}' href='{targets[k]}'><b>Step {k} {e(name)}</b>{e(txt)}</a>")
    return "<div class='chain'>" + "<span class='arrow'>→</span>".join(nodes) + "</div>"


def _variant_lengths(v: dict) -> tuple[str, str, str, str, str, str]:
    """Display strings for the length / NMD rows; every number is read from the step 1 output."""
    nmd, na = v["nmd"], L("不适用", "n/a")
    tail = v.get("frameshift_tail_aa")
    if v.get("truncated_protein_length") is not None:
        total = f"{v['truncated_protein_length']} aa"
        if tail:
            total += " " + L(f"（含 {tail} 个移码后的乱码氨基酸）", f"(includes {tail} out-of-frame residues)")
    elif nmd.get("protein_extended_by_aa") is not None:
        total = L(f"比正常长 {nmd['protein_extended_by_aa']} aa", f"{nmd['protein_extended_by_aa']} aa longer than normal")
        if tail:
            total += " " + L(f"（变化后 {tail} 个氨基酸为移码乱码序列）", f"({tail} out-of-frame residues after the change)")
    else:
        total = na
    n, frac = v.get("normal_residues_retained"), v.get("fraction_of_protein_retained")
    kept = na if n is None else L(f"保留 {n} 个氨基酸（占正常长度 {frac:.1%}）", f"{n} aa ({frac:.1%} of normal)")
    if tail:
        kept += " " + L("，其后是移码乱码序列", "; followed by an out-of-frame sequence")
    cmp_ = (v.get("retranslation") or {}).get("comparison")
    if cmp_:
        verdict = {True: tag("pass", L("一致", "agree")), False: tag("fail", L("不一致", "disagree")),
                   None: tag("warn", L("未比对", "not compared"))}[cmp_["agree"]]
        retr = f"{verdict} {e(cmp_['what'])}: {L('输入', 'stated')} {e(str(cmp_['stated']))}，{L('计算得', 'computed')} {e(str(cmp_['computed']))}"
    else:
        retr = f"<span class=muted>{L('结果文件里没有（旧版 Step 1 输出）', 'not in the result file (older step 1 output)')}</span>"
    border = " " + tag("warn", L("临界", "borderline")) if nmd.get("borderline") else ""
    ptc_exon = "—" if nmd.get("ptc_exon") is None else f"{nmd['ptc_exon']} / {v['exon'].get('total')}"
    if nmd.get("ptc_exon") is None and nmd.get("prediction") == "not_applicable":
        ptc_exon = na
    reasons = e("; ".join(nmd.get("reasons") or []))
    return total, kept, retr, border, ptc_exon, reasons


# ------------------------------------------------------------ step 1 figures (SVG)
# All positions come from the step 1 output (retranslation, transcript_layout, nmd);
# the figures only scale them to pixels.

FIG_W = 760


def _svg(h: int, body: str, label: str) -> str:
    return (f"<svg class='fig' viewBox='0 0 {FIG_W} {h}' role='img' aria-label='{e(label)}' "
            f"xmlns='http://www.w3.org/2000/svg'>{body}</svg>")


def _txt(x: float, y: float, t: str, cls: str = "", anchor: str = "start") -> str:
    c = f" class='{cls}'" if cls else ""
    return f"<text x='{x:.1f}' y='{y:.1f}' text-anchor='{anchor}'{c}>{e(t)}</text>"


def fig_codons(v: dict) -> str:
    w = (v.get("retranslation") or {}).get("codon_window")
    if not w:
        return f"<p class='muted'>{L('无密码子数据（内含子变异或旧版输出）', 'no codon data (intronic variant or older output)')}</p>"
    ref, var = w["reference"], w["variant"]
    x0, cw, n = 92, 82, max(len(ref), len(var))
    h = 150
    parts = [_txt(8, 62, L("正常", "Normal")), _txt(8, 126, L("变异后", "Variant"))]
    for i in range(n):
        x = x0 + i * cw
        if i < len(ref):
            r = ref[i]
            hot = r["n"] == w["changed_codon"]
            parts.append(_txt(x + cw / 2 - 4, 18, f"#{r['n']}", "m", "middle"))
            parts.append(f"<rect class='box{' chg' if hot else ''}' x='{x}' y='28' width='{cw - 8}' height='44' rx='5'/>")
            parts.append(_txt(x + cw / 2 - 4, 48, r["codon"], "mono", "middle"))
            parts.append(_txt(x + cw / 2 - 4, 66, r["aa"], "m", "middle"))
        if i < len(var):
            c = var[i]
            parts.append(f"<rect class='box{' chg' if c['changed'] else ''}' x='{x}' y='92' width='{cw - 8}' height='44' rx='5'/>")
            parts.append(_txt(x + cw / 2 - 4, 112, c["codon"], "mono", "middle"))
            parts.append(_txt(x + cw / 2 - 4, 130, c["aa"], "m", "middle"))
    return _svg(h, "".join(parts), L("密码子对比", "Codon comparison"))


def fig_protein(v: dict) -> str:
    rt = v.get("retranslation") or {}
    L0 = v["protein_length"]
    nm = v.get("nmd") or {}
    ext = nm.get("protein_extended_by_aa")
    vlen = rt.get("variant_protein_length") or L0
    scale_max = max(L0, vlen)
    x0, wbar = 92, FIG_W - 92 - 24
    def X(aa: float) -> float:
        return x0 + wbar * aa / scale_max
    parts = [_txt(8, 34, L("正常", "Normal")), _txt(8, 90, L("变异后", "Variant")),
             f"<rect class='normal' x='{x0}' y='22' width='{X(L0) - x0:.1f}' height='16' rx='3'/>",
             _txt(x0, 56, "1", "m"), _txt(X(L0), 56, f"{L0} aa", "m", "end")]
    cls, kept, tail = v["variant_class"], v.get("normal_residues_retained"), v.get("frameshift_tail_aa")
    y = 78
    note = ""
    if cls in ("frameshift", "nonsense") and kept is not None:
        parts.append(f"<rect class='lost' x='{x0}' y='{y}' width='{X(L0) - x0:.1f}' height='16' rx='3'/>")
        parts.append(f"<rect class='normal' x='{x0}' y='{y}' width='{max(X(kept) - x0, 1.5):.1f}' height='16' rx='3'/>")
        if tail:
            parts.append(f"<rect class='garbled' x='{X(kept):.1f}' y='{y}' width='{max(X(kept + tail) - X(kept), 1.5):.1f}' height='16'/>")
        stop = v.get("ptc_aa_position")
        if stop:
            sx = X(stop - 1)
            parts.append(f"<line class='stop' x1='{sx:.1f}' y1='{y - 6}' x2='{sx:.1f}' y2='{y + 22}'/>")
            parts.append(_txt(min(sx + 4, FIG_W - 150), y + 36, L(f"终止（第 {stop} 位）", f"stop (residue {stop})")))
        if ext:
            note = L(f"比正常长 {ext} aa", f"{ext} aa longer than normal")
    elif cls == "missense" or cls == "start_lost":
        parts.append(f"<rect class='normal' x='{x0}' y='{y}' width='{X(L0) - x0:.1f}' height='16' rx='3'/>")
        pos = v.get("first_affected_aa") or 1
        fc = rt.get("first_changed_aa") or {}
        mx = X(pos - 0.5)
        parts.append(f"<line class='mark' x1='{mx:.1f}' y1='{y - 8}' x2='{mx:.1f}' y2='{y + 24}'/>")
        label = f"{fc.get('reference', '')}{pos}{fc.get('variant', '')}"
        parts.append(_txt(min(max(mx, x0 + 40), FIG_W - 60), y + 38, label, "", "middle"))
        if cls == "start_lost" and rt.get("next_inframe_met"):
            note = L(f"起始密码子丢失；下一个框内 Met 在第 {rt['next_inframe_met']} 位",
                     f"start codon lost; next in-frame Met at residue {rt['next_inframe_met']}")
    elif cls.startswith("inframe") and rt.get("reference_span"):
        a, b = rt["reference_span"]
        parts.append(f"<rect class='normal' x='{x0}' y='{y}' width='{X(L0) - x0:.1f}' height='16' rx='3'/>")
        if b >= a:
            parts.append(f"<rect class='del' x='{X(a - 1):.1f}' y='{y - 4}' width='{max(X(b) - X(a - 1), 2):.1f}' height='24'/>")
            parts.append(_txt(X((a + b) / 2), y + 38, L(f"缺失 {a}–{b}（{b - a + 1} aa）", f"deleted {a}–{b} ({b - a + 1} aa)"), "", "middle"))
        if rt.get("inserted"):
            ix = X(a - 0.5)
            parts.append(f"<line class='mark' x1='{ix:.1f}' y1='{y - 8}' x2='{ix:.1f}' y2='{y + 24}'/>")
            parts.append(_txt(ix, y - 12, L(f"插入 {rt['inserted']}", f"inserted {rt['inserted']}"), "", "middle"))
    else:
        parts.append(f"<rect class='normal' x='{x0}' y='{y}' width='{X(L0) - x0:.1f}' height='16' rx='3'/>")
    legend = (f"<div class='legend'><i style='background:var(--barp)'></i>{L('正常序列', 'normal sequence')}"
              f"<i style='background:var(--warn)'></i>{L('移码后的乱码序列', 'out-of-frame sequence')}"
              f"<i style='border:1px dashed var(--grey)'></i>{L('丢失部分', 'lost part')}"
              f"<i style='background:var(--fail)'></i>{L('改变位置', 'changed position')}"
              + (f" · <b>{e(note)}</b>" if note else "") + "</div>")
    return _svg(128, "".join(parts), L("蛋白长度条", "Protein length bar")) + legend


def fig_exons(v: dict) -> str:
    lay = v.get("transcript_layout") or {}
    if not lay.get("exons"):
        return f"<p class='muted'>{L('结果文件里没有外显子结构（旧版输出）', 'no exon structure in the result file (older output)')}</p>"
    total, (cs, ce) = lay["mrna_length"], lay["cds"]
    x0, wbar = 14, FIG_W - 28
    def X(pos: float) -> float:
        return x0 + wbar * (pos - 1) / total
    exons = lay["exons"]
    many = len(exons) > 20
    var_ex, stop_ex = (v.get("exon") or {}).get("number"), (v.get("nmd") or {}).get("ptc_exon")
    parts = []
    y = 48
    for ex in exons:
        s0, e0 = ex["start"], ex["end"]
        # UTR parts thin, coding part thick
        segs = [(s0, min(e0, cs - 1), "utr"), (max(s0, cs), min(e0, ce), "cds"), (max(s0, ce + 1), e0, "utr")]
        for a, b, kind in segs:
            if b >= a:
                hh = 22 if kind == "cds" else 10
                parts.append(f"<rect class='{kind}' x='{X(a):.2f}' y='{y + (22 - hh) / 2:.1f}' "
                             f"width='{max(X(b + 1) - X(a), 0.8):.2f}' height='{hh}'/>")
        n = ex["number"]
        if not many or n in (1, len(exons), var_ex, stop_ex) or n % 10 == 0:
            parts.append(_txt(X((s0 + e0) / 2), y + 40, str(n), "m", "middle"))
    for j in lay["junctions"]:
        cls = "jn dn50" if j["more_than_50nt_downstream"] else "jn dn" if j["downstream_of_new_stop"] else "jn"
        jx = X(j["mrna_position"] + 0.5)
        parts.append(f"<line class='{cls}' x1='{jx:.2f}' y1='{y - 6}' x2='{jx:.2f}' y2='{y + 28}'/>")
    if lay.get("variant_mrna"):
        vx = X(lay["variant_mrna"][0])
        parts.append(f"<path class='mark' d='M{vx - 6:.1f},{y - 22} L{vx + 6:.1f},{y - 22} L{vx:.1f},{y - 10} Z'/>")
        parts.append(_txt(min(max(vx, x0 + 40), FIG_W - 60), y - 28, L("变异", "variant"), "", "middle"))
    if lay.get("new_stop_mrna"):
        sx = X(lay["new_stop_mrna"])
        parts.append(f"<line class='stop' x1='{sx:.1f}' y1='{y - 4}' x2='{sx:.1f}' y2='{y + 58}'/>")
        parts.append(_txt(min(max(sx, x0 + 40), FIG_W - 70), y + 72, L("新终止", "new stop"), "", "middle"))
    nmd = v.get("nmd") or {}
    side = (f"<p><b>NMD: {e(str(nmd.get('prediction')))}</b> — {e('; '.join(nmd.get('reasons') or []))}</p>")
    legend = (f"<div class='legend'><i style='background:var(--bar)'></i>{L('编码区', 'coding')}"
              f"<i style='background:var(--grey);opacity:.55'></i>UTR"
              f"<i style='background:var(--grey)'></i>{L('拼接标记（外显子连接点）', 'splice junction')}"
              f"<i style='background:var(--warn)'></i>{L('新终止之后（≤50 nt）', 'after new stop (≤50 nt)')}"
              f"<i style='background:var(--fail)'></i>{L('新终止之后 >50 nt（会触发 NMD 的信号）', 'after new stop, >50 nt (NMD signal)')}"
              f" · {L(f'{len(exons)} 个外显子，按 NCBI 记录的真实长度按比例绘制', f'{len(exons)} exons, drawn to scale from the NCBI record')}</div>")
    return _svg(132, "".join(parts), L("外显子图", "Exon diagram")) + legend + side


def fig_structure(v: dict) -> str:
    """Section 4: AlphaFold facts from the step 1 output; the 3D view itself is added by viewer_app."""
    st = v.get("structure") or {}
    if not st or st.get("status") in ("skipped", "unavailable"):
        why = st.get("error") or L("结果文件里没有结构信息（旧版输出）", "no structure facts in the result file (older output)")
        return f"<p class='muted'>{L('没有可用的 AlphaFold 结构', 'No AlphaFold structure available')}: {e(why)}</p>"
    src = st["source"]
    trunc_note = ""
    if v.get("variant_class") in ("frameshift", "nonsense"):
        kept = v.get("fraction_of_protein_retained")
        if kept is not None and kept < 0.5:
            trunc_note = L("截短变异：蛋白大部分丢失，位置信息仅供参考", "truncating variant: most of the protein is lost; "
                           "position data for reference only")
        elif kept is not None:
            trunc_note = L(f"截短变异：正常序列保留 {kept:.0%}，之后的部分丢失或被替换，位置信息仅供参考",
                           f"truncating variant: {kept:.0%} of the normal sequence kept, the rest lost or replaced; "
                           "position data for reference only")
    note_html = f"<div>{tag('warn', trunc_note)}</div>" if trunc_note else ""
    af_page = f"https://alphafold.ebi.ac.uk/entry/{src['alphafold_isoform']}"
    when = time.strftime("%Y-%m-%d", time.gmtime(src["accessed_at"])) if src.get("accessed_at") else "?"
    rows = [(L("来源", "Source"), f"{link(af_page, src['alphafold_entry'])} · {L('模型版本', 'model')} v{e(str(src['model_version']))}"
             f" ({e(str(src.get('model_created') or '')[:10])}) · {link(src['pdb_url'], 'PDB')} · "
             f"{L('访问于', 'accessed')} {when} · UniProt {link('https://www.uniprot.org/uniprotkb/' + src['uniprot'], src['uniprot'])}")]
    notes = list(st.get("notes") or [])
    m = st.get("mapping") or {}
    if m:
        rows.append((L("位置映射", "Position mapping"), e(f"RefSeq {m['refseq_position']} → model {m['model_position']} ({m['method']})")
                     + (f"<div class='muted'>{e(m['note'])}</div>" if m.get("note") else "")))
    if st["status"] == "residue_not_in_model":
        rows.append((L("变异位置", "Variant residue"), tag("warn", L("不在模型中", "not in the model"))))
    pl = st.get("plddt")
    if pl:
        bad = "" if pl["reliable"] else " " + tag("fail", L("该区域结构预测不可靠", "structure prediction unreliable here"))
        rows.append((L("预测可信度 pLDDT", "Confidence (pLDDT)"), f"<b>{pl['value']}</b> ({e(pl['band'])}){bad}"))
    rsa = st.get("rsa")
    if rsa:
        cls = {"buried": L("埋在内部", "buried"), "exposed": L("暴露在表面", "exposed")}[rsa["class"]]
        extra = (" " + tag("warn", L("接近阈值", "borderline"))) if rsa.get("borderline") else ""
        extra += "" if rsa["reliable"] else " " + tag("fail", L("所在区域预测不可靠，仅供参考", "unreliable region"))
        rows.append((L("相对溶剂可及性 RSA", "Relative solvent accessibility"),
                     f"<b>{rsa['value']}</b> → {cls}{extra} <span class='muted'>(SASA {rsa['sasa_A2']} Å² / "
                     f"max {rsa['max_asa_A2']} Å²)</span>{note_html}<div class='muted'>{e(rsa['method'])}</div>"))
    nb = st.get("neighbours_8A")
    if nb is not None:
        rows.append((L("8 Å 内的邻居", "Neighbours within 8 Å"),
                     f"{len(nb)}: " + e(", ".join(f"{n['aa']}{n['position']}" for n in nb)) + note_html))
    if st.get("lost_model_range"):
        a, b = st["lost_model_range"]
        rows.append((L("丢失部分（模型编号）", "Lost part (model numbering)"), f"{a}–{b}"))
    for n in notes:
        rows.append((L("说明", "Note"), e(n)))
    table = "<table>" + "".join(f"<tr><th style='width:190px'>{h}</th><td>{d}</td></tr>" for h, d in rows) + "</table>"
    pos = (st.get("residue") or {}).get("model_position")
    data = {"file": src["local_file"], "pos": pos, "plddt": (pl or {}).get("value"),
            "neighbours": [n["position"] for n in (nb or [])], "lost": st.get("lost_model_range"),
            "label": f"{(st.get('residue') or {}).get('model_aa', '')}{pos or ''}",
            "whole": v.get("variant_class") in ("frameshift", "nonsense")}      # truncating: show the whole protein
    holder = (f"<div class='mol3d' data-mol='{e(json.dumps(data))}'><div class='ph'>"
              f"{L('3D 视图需要在本地应用中打开：python3 scripts/viewer_app.py', '3D view needs the local app: python3 scripts/viewer_app.py')}"
              f"</div></div>")
    return table + holder


def v_figures(v: dict) -> str:
    return (f"<div class='figs'><h4>{L('① 密码子对比（变异附近）', '1 Codons around the change')}</h4>{fig_codons(v)}"
            f"<h4>{L('② 蛋白长度（按比例）', '2 Protein length (to scale)')}</h4>{fig_protein(v)}"
            f"<h4>{L('③ 外显子与拼接标记（按比例）', '3 Exons and splice junctions (to scale)')}</h4>{fig_exons(v)}"
            f"<h4>{L('④ 3D 蛋白结构（AlphaFold 预测）', '4 3D protein structure (AlphaFold prediction)')}</h4>{fig_structure(v)}</div>")


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
        total_len, kept, retr, border, ptc_exon, reasons = _variant_lengths(v)
        out.append(f"""<div class='card'><h3>{e(v['gene'])} {e(v['transcript'])} {e(v['variant_cdna'])}
 {e(v.get('variant_protein') or '')} {tag('pass' if v['ok'] else 'fail', L('自检全过', 'all checks pass') if v['ok'] else L('自检失败', 'self-check failed'))}</h3>
<table><tr><th>{L('类型', 'Class')}</th><td>{e(v['variant_class'])}</td><th>{L('合子状态', 'Zygosity')}</th><td>{e(v['zygosity'])}
 ({e(v['allelic_state'].get('note', ''))})</td></tr>
<tr><th>{L('外显子', 'Exon')}</th><td>{ex.get('number')} / {ex.get('total')}{e(last)}</td>
<th>{L('蛋白长度', 'Protein length')}</th><td>{v['protein_length']} aa</td></tr>
<tr><th>{L('首个受影响氨基酸', 'First affected residue')}</th><td>{v.get('first_affected_aa')}</td>
<th>{L('新终止位置', 'New stop position')}</th><td>{v.get('ptc_aa_position')}</td></tr>
<tr><th>{L('截短后总长', 'Total length after change')}</th><td>{total_len}</td>
<th>{L('正常部分', 'Normal part kept')}</th><td>{kept}</td></tr>
<tr><th>{L('独立重新翻译', 'Independent re-translation')}</th><td colspan='3'>{retr}</td></tr>
<tr><th>{L('NMD 预测', 'NMD prediction')}</th><td colspan='3'>{e(str(nmd.get('prediction')))}{border}
 · {L('新终止所在外显子', 'exon of the new stop')}: {ptc_exon}<div class='muted'>{reasons}</div></td></tr>
<tr><th>{L('机制初判', 'Mechanism hypothesis')}</th><td colspan='3'>{e(mech['hypothesis'])}
 ({L('置信度', 'confidence')} {e(mech['confidence'])}): {e(mech['basis'])}</td></tr>
</table>{v_figures(v)}<details><summary>{L('自检', 'Self-checks')} {len(v['checks'])}</summary><table>{checks}</table></details>
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
               + (f"<br>{L('该症状起病', 'onset of this symptom')}: {e(_onset_text(onset))}" if onset.get("quote") else ""))
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
             (_onset_text({"months_min": onset.get("min"), "months_max": onset.get("max"), **onset})
              + (f" ({onset.get('kind')})" if onset.get("kind") == "age_upper_bound" else "")) if onset else L("未知", "unknown"),
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


def _onset_text(o: dict) -> str:
    """HPO onset term(s) + interval used for scoring + the age stated in the text (all read from the result)."""
    if o.get("months_min") is None and o.get("months_max") is None:
        return L("未能映射", "not mapped") + (f" — {'; '.join(o.get('reasons') or [])}" if o.get("reasons") else "")
    terms = ", ".join(t["label"] for t in o.get("hpo_onset") or [])
    hi = o.get("months_max")
    rng = f"{o.get('months_min')}–{hi if hi is not None else '∞'} " + L("月", "months")
    st = o.get("stated_months")
    said = (" · " + L("原文", "stated") + f" {st[0]}" + (f"–{st[1]}" if st[1] != st[0] else "") + " " + L("月", "months")) if st else ""
    return (f"{terms}（{rng}）" if terms else rng) + said


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
    if r == "gene_level":
        return L("基因级（诊断未定）", "Gene level (diagnosis unresolved)")
    return L(f"歧义候选 {r.split('_')[1]}", f"Ambiguous candidate {r.split('_')[1]}")


def tier_label(t: str) -> str:
    return {"established": L("已确立", "Established"), "emerging": L("新兴", "Emerging"),
            "hypothesized": L("假设性", "Hypothesized"), "background": L("背景事实", "Background")}.get(t, t)


def section_label(sec: str) -> str:
    return {"background": L("背景（诊断、变异、ClinVar、GeneReviews、规则）", "Background (diagnosis, variant, ClinVar, GeneReviews, rules)"),
            "existing_targeted_therapies": "Existing Targeted Therapies", "supportive_management": "Supportive Management",
            "contraindications_precautions": "Contraindications & Precautions",
            "clinical_trial_eligibility": "Clinical Trial Eligibility", "off_label_expanded_access": "Off-label / Expanded Access",
            "bespoke_therapies": "Bespoke Therapies", "drug_repurposing": "Drug Repurposing",
            "outcome_measures_ranking": "Outcome Measures & Ranking"}.get(sec, sec)


def _leaf(x: dict) -> str:
    st = tag({"verified": "pass", "rejected": "fail"}.get(x["status"], "warn"), x["status"])
    when = time.strftime("%Y-%m-%d", time.gmtime(x.get("accessed_at") or (x.get("search") or {}).get("queried_at") or 0))
    if x["kind"] == "negative":
        sr = x["search"]
        body = (f"{L('查过但没找到', 'searched, nothing found')}: {e(sr['database'])} “{e(sr['query'])}” "
                f"→ {sr['n_results']} {L('条', 'results')}, {L('排除', 'excluded')} {sr['n_excluded']} · {when}")
    elif x["kind"] == "reasoning":
        body = f"{L('推理，前提', 'reasoning from')}: {e(', '.join(x['premises']))}"
    else:
        src = x["source"]
        up = src.get("upstream") or {}
        q = str(x.get("quote", ""))
        if src.get("type") == "pipeline_fact" and len(q) > 1 and q[0] == q[-1] == '"':
            q = q[1:-1]                      # pipeline facts are quoted as JSON values; show the plain text
        body = (f"<q>{e(q[:160])}</q> — {link(src.get('url'), src.get('id', ''))}"
                + (f" ({e(up.get('type', ''))} {e(str(up.get('id', '')))})" if up else "") + f" · {when}")
    why = f"<div class='muted'>{e('; '.join(x['reasons']))}</div>" if x.get("reasons") else ""
    return f"<li>{st} {e(x['claim'])}<div class='muted'>{body}</div>{why}</li>"


def v_tree(c: dict) -> str:
    t = c["tree"]
    if not t:
        return ""
    if t["status"] == "reserved":
        items = "".join(f"<li><b>{e(role_label(b['role']))}</b>: {e(b['label'])} <span class='muted'>{e(b['diagnosis_id'])}</span></li>"
                        for b in t["branches"])
        return (f"<ul class='tree'>{items}</ul><p class='muted'>"
                f"{L('Step 3 尚未运行（用 run_pipeline.py --from-step 3 生成证据账本）。', 'Step 3 has not run yet (run_pipeline.py --from-step 3).')}</p>")
    out = []
    for b in t["branches"]:
        extra = ""
        if b.get("expanded_from"):
            extra += f" <span class='muted'>{L('由伞状概念展开', 'expanded from umbrella')} {e(b['expanded_from'])}</span>"
        if b.get("not_expandable"):
            extra += " " + tag("warn", L("伞状概念，无法展开", "umbrella, not expandable"))
        if b.get("promoted_by"):
            extra += " " + tag("pass", L("由规则提拔", "promoted by rule") + f" {b['promoted_by']}")
        for a in b.get("assessment") or []:
            extra += " " + tag("pass" if a["effect"] == "supports" else "warn",
                               (L("规则支持", "rule supports") if a["effect"] == "supports" else L("规则不支持", "rule argues against"))
                               + f" {a['rule_id']}")
        layers = []
        for layer in b["layers"]:
            secs = []
            for sec in layer["sections"]:
                acts = []
                for a in sec["actions"]:
                    leaves = "".join(_leaf(x) for x in a["leaves"])
                    if a["action_key"]:
                        warn = (" " + tag("warn", L("未标准化", "not normalized"))) if a.get("normalized") is False else ""
                        acts.append(f"<li><code>{e(a['action_key'])}</code>{warn}<ul class='tree'>{leaves}</ul></li>")
                    else:
                        acts.append(leaves)
                secs.append(f"<li><b>{e(section_label(sec['section']))}</b> <span class='muted'>({len(sec['actions'])})</span>"
                            f"<ul class='tree'>{''.join(acts)}</ul></li>")
            layers.append(f"<li><details{' open' if layer['tier'] != 'background' else ''}><summary><b>{e(tier_label(layer['tier']))}</b></summary>"
                          f"<ul class='tree'>{''.join(secs)}</ul></details></li>")
        out.append(f"<li><b>{e(role_label(b['role']))}</b>: {e(b['label'])} <span class='muted'>{e(b['diagnosis_id'])} "
                   f"{e(' '.join(b.get('omim') or []))}</span>{extra}<ul class='tree'>{''.join(layers)}</ul></li>")
    notes = []
    if t.get("dropped"):
        notes.append(f"<li>{L('超过 3 个分支而舍弃（按 Step 2 分数）', 'Dropped (more than 3 branches, by step 2 score)')}: "
                     + e(", ".join(f"{d['diagnosis']['label']} ({d['step2_score']})" for d in t["dropped"])) + "</li>")
    for r in t.get("rules_applied") or []:
        miss = f" · {L('规则涉及但不是分支的诊断', 'diagnoses named by the rule but not a branch')}: {', '.join(r['branches_not_present'])}" if r.get("branches_not_present") else ""
        blocked = "; ".join(f"{p['omim']}: {p['reason']}" for p in r.get("promotions") or [] if not p["promoted"])
        blocked = f" · {L('未提拔', 'not promoted')}: {blocked}" if blocked else ""
        notes.append(f"<li>{L('生效规则', 'Rule applied')} <code>{e(r['rule_id'])}</code> ({e(r['variant'])}): {e(r['statement'])}{e(miss)}{e(blocked)}</li>")
    for r in t.get("rules_skipped") or []:
        notes.append(f"<li>{L('未加载的规则', 'Rule not loaded')} <code>{e(str(r['rule_id']))}</code>: {e('; '.join(r['reasons']))}</li>")
    if t.get("missing"):
        notes.append(f"<li>{L('缺失信息', 'Missing information')}: "
                     + e("; ".join(f"{m['variable']} — {m['why_it_matters']}" for m in t["missing"])) + "</li>")
    pending = [s for s, st in (t.get("sections_status") or {}).items() if st != "searched"]
    if pending:
        notes.append(f"<li class='muted'>{L('尚未检索的章节（3a–3e 完成后填入）', 'Sections not searched yet (filled by 3a–3e)')}: "
                     + e(", ".join(section_label(x) for x in pending)) + "</li>")
    return f"<ul class='tree'>{''.join(out)}</ul><ul>{''.join(notes)}</ul>"


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


# ------------------------------------------------------------ action board (ledger 1.4)

ACT_ORDER = ["applicable", "conditional", "not_applicable", "searched_none"]
ACT_CLS = {"applicable": "pass", "conditional": "warn", "not_applicable": "fail", "searched_none": "not_run", "mixed": "mixed"}
ACCEPTANCE = OUT / "acceptance" / "step3a.json"      # written by scripts/acceptance_step3a.py
ACCEPT_STEPS = ("3b", "3c", "3d", "3e")               # the other acceptance pages, one generic layout
BLIND_OUT = OUT / "blind"                             # out/blind/<batch>/{sample,machine,recall}.json
BLIND_CASES = ROOT / "data" / "cases" / "blind"       # data/cases/blind/<batch>.json
BLIND_JUDGED = ROOT / "data" / "eval" / "blind"       # data/eval/blind/<batch>.json (the reviewer's verdicts)
VERDICTS = ("correct", "wrong", "missed", "unsure")
# blind-test groups (B1 split 2026-11-11: single-gene chapter vs overview only)
BLIND_GROUP_ORDER = ["A", "B1-L1", "B1-L2", "B1", "B2"]
BLIND_GROUP_LABEL = {"A": "A（Validator）", "B1-L1": "B1-L1 有专章", "B1-L2": "B1-L2 只有总论",
                     "B1": "B1（未分）", "B2": "B2 无章节"}


def act_label(s: str) -> str:
    return {"applicable": L("适用", "Applicable"), "conditional": L("有条件", "Conditional"),
            "not_applicable": L("不适用", "Not applicable"), "searched_none": L("查过无", "Searched, none found"),
            "mixed": L("各分支不同", "Differs by branch")}.get(s, s)


def result_label(r: str) -> str:
    return {"pass": L("满足", "Met"), "fail": L("不满足", "Not met"), "unknown": L("未知", "Unknown"),
            "not_assessed": L("筛选时评估", "Screening assessment")}.get(r, r)


def kind_label(k: str) -> str:
    return {"inclusion": L("入组", "Inclusion"), "exclusion": L("排除", "Exclusion"),
            "label_condition": L("说明书 / 指南条件", "Label / guideline condition"), "other": L("其他", "Other")}.get(k, k)


def pstatus_label(s: str) -> str:
    return {"satisfies": L("符合", "satisfies"), "does_not_satisfy": L("不符合", "does not satisfy"),
            "unknown": L("未知", "unknown"), "not_assessed": "—"}.get(s, s)


def _branch_cols(s3: dict) -> list[dict]:
    by_id = {b["id"]: b for b in s3["branches"]}
    return [by_id[b] for b in (s3.get("branch_order") or list(by_id))]


def _blabel(b: dict) -> str:
    return (b.get("diagnosis") or {}).get("label") or b.get("gene") or b["id"]


def _evidence_item(x: dict | None, eid: str) -> str:
    if not x:
        return f"<li class='fail'>{L('证据缺失', 'missing evidence')} <code>{e(eid)}</code></li>"
    st = tag({"verified": "pass", "rejected": "fail"}.get(x["status"], "warn"), x["status"])
    when = time.strftime("%Y-%m-%d", time.gmtime(x.get("accessed_at") or (x.get("search") or {}).get("queried_at") or 0))
    meta = []
    if x["kind"] == "negative":
        sr = x["search"]
        body = (f"{L('查过但没找到', 'searched, nothing found')}: {e(sr['database'])} “{e(sr['query'])}” → {sr['n_results']}, "
                f"{L('排除', 'excluded')} {sr['n_excluded']}")
    elif x["kind"] == "reasoning":
        body = f"{L('推理，前提', 'reasoning from')}: {e(', '.join(x['premises']))}"
    else:
        src = x["source"]
        body = f"<blockquote>{e(str(x.get('quote', '')))}</blockquote>"
        meta.append(link(src.get("url"), f"{src.get('type')} {src.get('id', '')}"))
        if src.get("brand"):
            meta.append(e(src["brand"]))
        if src.get("version"):
            meta.append(L(f"说明书版本 {src['version']}", f"label version {src['version']}"))
        if src.get("effective_date"):
            meta.append(L(f"生效 {src['effective_date']}", f"effective {src['effective_date']}"))
        if src.get("section"):
            meta.append(e(src["section"]))
    meta.append(L(f"获取 {when}", f"retrieved {when}"))
    pb = x.get("produced_by")
    if isinstance(pb, dict) and pb.get("prompt_version"):
        meta.append(e(f"{pb.get('served_model')} · {pb['prompt_version']}"))
    why = f"<div class='fail'>{e('; '.join(x['reasons']))}</div>" if x.get("reasons") else ""
    if x.get("quote_repaired"):
        qr = x["quote_repaired"]
        why += (f"<div class='warn'>{L('引用经代码修复', 'quote repaired by code')} ({e(qr.get('check', ''))})："
                f"{L('LLM 原抄写', 'LLM copy')} “{e(str(qr.get('llm_quote', '')))}”</div>")
    return (f"<li>{st} {e(x['claim'])}{body}<div class='muted'>{' · '.join(meta)}</div>{why}</li>")


def _req_table(a: dict, s3: dict, cols: list[dict]) -> str:
    if not a["requirements"]:
        return f"<p class='muted'>{L('没有需要核对的条件。', 'No conditions to check.')}</p>"
    multi = len(cols) > 1
    idx = {b["id"]: i + 1 for i, b in enumerate(cols)}
    rows = []
    alts = list(dict.fromkeys(r["alternative"] for r in a["requirements"] if r.get("alternative")))
    last = object()
    for r in sorted(a["requirements"], key=lambda r: (r.get("alternative") is not None, alts.index(r["alternative"]) if r.get("alternative") in alts else -1)):
        if alts and r.get("alternative") != last:          # rows of the source table: any one met is enough
            last = r.get("alternative")
            head_txt = (L("所有情况都需满足", "Applies in every case") if last is None
                        else L(f"情况 {alts.index(last) + 1}（满足其一即可）：", f"Alternative {alts.index(last) + 1} (any one is enough): ") + last)
            rows.append(f"<tr><td colspan='{6 if multi else 5}' class='muted'><b>{e(head_txt)}</b></td></tr>")
        pf = r.get("patient_fact") or {}
        fact = (f"{e(str(pf.get('value')))}<div class='muted'>“{e(str(pf['quote']))}” (step {pf.get('step')})</div>"
                if pf.get("quote") else f"<span class='muted'>{e(str(pf.get('field') or L('病例未提供', 'not in the case')))}</span>")
        cls = {"pass": "pass", "fail": "fail", "unknown": "warn", "not_assessed": "not_run"}.get(r["result"], "")
        br = f"<td>{e(', '.join(str(idx.get(b, b)) for b in r['applies_to']))}</td>" if multi else ""
        rows.append(f"<tr><td>{e(kind_label(r['kind']))}</td><td><q>{e(r['requirement'])}</q></td><td>{fact}</td>"
                    f"<td class='nw'>{e(pstatus_label(r['patient_status']))}</td><td class='nw'>{tag(cls, result_label(r['result']))}"
                    f"{('<div class=muted>' + e(r['note']) + '</div>') if r.get('note') else ''}</td>{br}</tr>")
    head = [L("类型", "Kind"), L("要求原文", "Requirement (verbatim)"), L("病人事实与原文引用", "Patient fact and quote"),
            L("病人", "Patient"), L("结果", "Result")] + ([L("分支", "Branch")] if multi else [])
    return "<div class='wrap'><table>" + "<tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>" + "".join(rows) + "</table></div>"


_MODALITY_CLASS = {"eligible": "ok", "likely_eligible": "ok", "unlikely_eligible": "cond", "not_eligible": "no",
                   "theoretically_possible": "ok", "not_applicable": "no", "unable_to_assess": "cond",
                   "not_graded": "cond"}


def _modality_card(a: dict, cols: list[dict], span: str = "") -> str:
    cls = _MODALITY_CLASS.get(a.get("classification"), "cond")
    bits = [f"<div class='muted'>{e(a['conclusion'])}</div>"]
    if a.get("criteria_met"):
        bits.append("<ul>" + "".join(f"<li>{e(x)}</li>" for x in a["criteria_met"]) + "</ul>")
    if a.get("unassessable_reason"):
        bits.append(f"<div class='muted'>{L('缺', 'missing')}: "
                    + "; ".join(e(x) for x in a["unassessable_reason"]) + "</div>")
    if a.get("exceptions"):
        bits.append("<div class='muted'>" + "<br>".join(e(x) for x in a["exceptions"]) + "</div>")
    return (f"<div class='card {span}'><div class='row'><b>{e(a['label'])}</b>"
            f"{tag(cls, e((a.get('classification') or '').replace('_', ' ')))}</div>" + "".join(bits) + "</div>")


def _card(a: dict, s3: dict, cols: list[dict], span: str = "") -> str:
    if a.get("modality"):                       # 3d: a modality judgement, not a per-patient action (2026-11-06)
        return _modality_card(a, cols, span)
    sts = {b: v["status"] for b, v in a["status_by_branch"].items()}
    overall = next(iter(set(sts.values()))) if len(set(sts.values())) == 1 else "mixed"
    reasons = {v["reason"] for v in a["status_by_branch"].values()}
    if len(cols) > 1 and (overall == "mixed" or len(reasons) > 1):
        idx = {b["id"]: i + 1 for i, b in enumerate(cols)}
        lines = "".join(f"<div>{tag(ACT_CLS[v['status']], f'{idx.get(b, b)} · ' + act_label(v['status']))} {e(v['reason'])}</div>"
                        for b, v in a["status_by_branch"].items())
    else:
        lines = f"<div>{tag(ACT_CLS[overall], act_label(overall))} {e(next(iter(reasons)) if reasons else '')}</div>"
    ev = {x["id"]: x for x in s3["evidence"]}
    note = f"<p class='muted'>{L('不写入报告', 'Not written to the report')}: {e(a.get('report_note', ''))}</p>" if a.get("report") is False else ""
    key = f"<code>{e(a['action_key'])}</code>" if a.get("action_key") else ""
    for fld, title in (("genereviews_notes", L("备注：GeneReviews 条件（以 FDA 说明书条件为准，不参与判定）",
                                               "Notes: GeneReviews conditions (the FDA label decides; not evaluated)")),
                       ("precautions", L("注意事项（说明书适应证以外章节的条件，不改变适用状态）",
                                         "Precautions (label conditions outside Indications and Usage; no effect on the status)")),
                       ("pregnancy_notes", L("备注：孕期条件（只用于孕期措施，不参与判定）",
                                             "Notes: pregnancy conditions (pregnancy measures only; not evaluated)"))):
        if a.get(fld):
            note += f"<p class='muted'>{title}</p><ul>" + "".join(f"<li>{e(t)}</li>" for t in a[fld]) + "</ul>"
    return (f"<details class='acard st-{ACT_CLS[overall]}'{span}><summary><b>{e(a['label'])}</b>{lines}</summary>"
            f"<div class='abody'>{note}<p class='muted'>{key}</p><h4>{L('条件核对', 'Condition check')}</h4>{_req_table(a, s3, cols)}"
            f"<h4>{L('证据', 'Evidence')}</h4><ul class='evl'>{''.join(_evidence_item(ev.get(i), i) for i in a['evidence_ids'])}</ul>"
            f"</div></details>")


def _span(a: dict, cols: list[dict]) -> str:
    if len(cols) == 1:
        return ""
    pos = [i for i, b in enumerate(cols) if b["id"] in a["applies_to"]]
    return f" style='grid-column:{min(pos) + 1} / {max(pos) + 2}'" if pos else ""


def v_board(s3: dict | None) -> str:
    """Action board: counts and missing information, then tier -> section rows of action cards, branches side by side.
    Shows the ledger's action records as they are; nothing is evaluated here."""
    if not s3:
        return f"<p class='muted'>{L('Step 3 尚未运行。', 'Step 3 has not run yet.')}</p>"
    cols = _branch_cols(s3)
    acts = s3.get("actions") or []
    shown = [a for a in acts if a.get("report") is not False]
    # 3d rows carry a modality verdict instead of a per-branch status, so they are counted separately
    counts = {s: sum(1 for a in shown for v in (a.get("status_by_branch") or {}).values() if v["status"] == s)
              for s in ACT_ORDER}
    n_modality = sum(1 for a in shown if a.get("modality"))
    hidden = len(acts) - len(shown)
    unit = L("（按 行动 × 分支 计）", " (action × branch)") if len(cols) > 1 else ""
    top = " ".join(f"{tag(ACT_CLS[s], act_label(s))} <b>{counts[s]}</b>" for s in ACT_ORDER)
    if n_modality:
        top += f" {tag('cond', L('手段判定', 'modality verdicts'))} <b>{n_modality}</b>"
    top += f" <span class='muted'>{unit}{L(f' · 不写入报告 {hidden}', f' · not reported {hidden}')}</span>"
    miss = s3.get("missing_information") or []
    miss_html = ("<details class='miss'><summary>" + L(f"缺失信息 {len(miss)} 项", f"Missing information: {len(miss)}") + "</summary><ul>"
                 + "".join(f"<li><b>{e(m['variable'])}</b> — {e(m['why_it_matters'])}</li>" for m in miss) + "</ul></details>") if miss else ""
    n = len(cols)
    # one branch: cards flow in as many columns as fit; several branches: one column per branch
    grid = ("display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px" if n == 1
            else f"display:grid;grid-template-columns:repeat({n},minmax(0,1fr));grid-auto-flow:row dense;gap:8px")
    head = "" if n == 1 else (f"<div class='bhead' style='{grid}'>" + "".join(
        f"<div><b>{i + 1} · {e(role_label(b['role']))}</b><br>{e(_blabel(b))}</div>" for i, b in enumerate(cols)) + "</div>")
    order = {s: i for i, s in enumerate(ACT_ORDER)}
    tiers, not_searched = [], []
    from aitx.evidence.ledger import SECTIONS
    for tier in ("established", "emerging", "hypothesized"):
        rows = []
        for sec in [s for s, t in SECTIONS.items() if t == tier]:
            here = [a for a in acts if a["section"] == sec]
            if (s3.get("sections_status") or {}).get(sec) != "searched" and not here:
                not_searched.append(sec)
                continue
            vis = sorted([a for a in here if a.get("report") is not False],
                         key=lambda a: (min([order.get(v["status"], 9) for v in
                                             (a.get("status_by_branch") or {}).values()] or [9]), a["label"].lower()))
            hid = [a for a in here if a.get("report") is False]
            cards = "".join(_card(a, s3, cols, _span(a, cols)) for a in vis) or f"<p class='muted'>{L('（无行动）', '(no actions)')}</p>"
            fold = (f"<details class='hidden-acts'><summary class='muted'>{L(f'不写入报告的条目 {len(hid)} 个', f'{len(hid)} items not written to the report')}</summary>"
                    f"<div style='{grid}'>{''.join(_card(a, s3, cols, _span(a, cols)) for a in hid)}</div></details>") if hid else ""
            rows.append(f"<h4 class='sec'>{e(section_label(sec))} <span class='muted'>({len(vis)})</span></h4>"
                        f"<div style='{grid}'>{cards}</div>{fold}")
        if rows:
            tiers.append(f"<h3 class='tier'>{e(tier_label(tier))}</h3>{''.join(rows)}")
    pend = (f"<p class='muted'>{L('尚未检索的章节', 'Sections not searched yet')}: "
            + e(", ".join(section_label(s) for s in not_searched)) + "</p>") if not_searched else ""
    return (f"<div class='card'>{top}{miss_html}</div>{head}{''.join(tiers)}{pend}")


def acceptance_page(res: dict | None) -> str:
    """Verified expectations next to the ledger results (scripts/acceptance_step3a.py output, shown as is)."""
    title = L("Step 3a 验收对照", "Step 3a acceptance")
    if not res:
        body = (f"<h1>{title}</h1><p class='muted'>{L('还没有验收结果。运行', 'No acceptance result yet. Run')} "
                f"<code>python3 scripts/acceptance_step3a.py</code>.</p>")
        return page(title, body, "acceptance")
    made = time.strftime("%Y-%m-%d %H:%M", time.localtime(res["created_at"]))
    overall = tag("pass" if res["ok"] else "fail", "PASS" if res["ok"] else "FAIL")
    crow = []
    for cid, m in res["cases"].items():
        lm = time.strftime("%Y-%m-%d %H:%M", time.localtime(m["created_at"] or 0)) if m["created_at"] else "—"
        chk = tag("pass", L("通过", "pass")) if m["ledger_ok"] else tag("fail", L("未通过", "failed") + ": " + ", ".join(m["failed_checks"]))
        crow.append(f"<tr><td><a href='cases/{e(fn(cid))}#board'>{e(cid)}</a></td><td>{e(lm)}</td><td>{e(str(m.get('code_commit')))}</td>"
                    f"<td>{e(', '.join(m['prompt_versions']) or '—')}</td><td>{e(str(m.get('schema_version')))}</td><td>{chk}</td></tr>")
    rows = []
    for r in res["rows"]:
        names = res["cases"].get(r["case"], {}).get("branches", {})
        acts = []
        if isinstance(r["actual"], dict) and r["actual"] and all(isinstance(v, dict) and "tier" in v for v in r["actual"].values()):
            for b, v in r["actual"].items():               # supportive fallback-chain record of a branch
                acts.append(f"<div><b>{e(names.get(b, b))}</b>: {L('层级', 'tier')} {e(str(v.get('tier')))} · "
                            f"{L('文献', 'literature')} {e(str(v.get('literature_count')))}"
                            + (f" · {L('停用', 'disabled')} {e(', '.join(v.get('disabled') or []))}" if v.get("disabled") else "")
                            + (f" · <span class='fail'>{e(str(v.get('literature_error')))}</span>" if v.get("literature_error") else "")
                            + "</div>")
        for a in (r["actual"] if isinstance(r["actual"], list) else []):
            if "status_by_branch" not in a:                 # an "absent" expectation lists what was found instead
                acts.append(f"<div><b>{e(a['label'])}</b> ({e(str(a.get('tier_source')))})</div>")
                continue
            sts = "; ".join(f"{act_label(v['status'])}" + (f" ({e(names.get(b, b))})" if len(names) > 1 else "")
                            + f" — {e(v['reason'])}" for b, v in a["status_by_branch"].items())
            unk = (f"<div class='muted'>{L('未知条件', 'unknown')}: " + e(" | ".join(a["unknown_requirements"])) + "</div>") if a["unknown_requirements"] else ""
            nr = f" {tag('not_run', L('不写入报告', 'not reported'))}" if a.get("report") is False else ""
            acts.append(f"<div><b>{e(a['label'])}</b>{nr}: {sts}{unk}</div>")
        actual = "".join(acts) or f"<span class='muted'>{L('未找到', 'not found')}</span>"
        mark = "<b class='pass'>✓</b>" if r["ok"] else f"<b class='fail'>✗</b> <span class='fail'>{e(r['problem'] or '')}</span>"
        s = r["source"]
        ver = " · ".join(x for x in (L(f"版本 {s['version']}", f"version {s['version']}") if s.get("version") else "",
                                     L(f"生效 {s['date']}", f"effective {s['date']}") if s.get("date") else "") if x)
        src = f"{link(s.get('url') or None, s['doc'])}<div class='muted'>{e(ver)}</div><q>{e(s['quote'])}</q>"
        sec = section_label(r["section"]) if r.get("section") else L("支持治疗兜底链", "supportive fallback chain")
        prov = (f"<div>{tag('warn', L('临时期望', 'provisional'))} <span class='muted'>{e(r['provisional'].get('reason', ''))} "
                f"{L('解除条件', 'lift when')}: {e(r['provisional'].get('lift_when', ''))}</span></div>") if r.get("provisional") else ""
        rows.append(f"<tr class='{'' if r['ok'] else 'badrow'}'><td>{e(r['what']['en' if LANG == 'en' else 'zh'])}"
                    f"<div class='muted'>{e(sec)}</div>{prov}</td><td>{actual}</td><td>{mark}</td><td>{src}</td></tr>")
    body = (f"<h1>{title} {overall}</h1><p class='muted'>"
            + L(f"{res['n_ok']}/{res['n']} 条期望成立 · 结果生成于 {made}（代码 {res['code_commit']}）· 期望核实于 {res['expectations_verified_on']}。"
                "本页只显示 scripts/acceptance_step3a.py 的输出，不做计算。",
                f"{res['n_ok']}/{res['n']} expectations hold · result made {made} (code {res['code_commit']}) · expectations verified "
                f"{res['expectations_verified_on']}. This page only shows the output of scripts/acceptance_step3a.py.")
            + f"</p><h2>{L('账本', 'Ledgers')}</h2><div class='wrap'><table><tr><th>{L('病例', 'Case')}</th><th>{L('生成时间', 'Made')}</th>"
            f"<th>{L('代码', 'Code')}</th><th>{L('提示词版本', 'Prompt')}</th><th>{L('账本结构', 'Schema')}</th><th>{L('账本校验', 'Ledger checks')}</th></tr>"
            + "".join(crow) + f"</table></div><h2>{L('期望与实际', 'Expected vs actual')}</h2><div class='wrap'><table><tr>"
            f"<th>{L('核实期望', 'Verified expectation')}</th><th>{L('账本实际', 'Ledger result')}</th><th></th><th>{L('期望出处', 'Source')}</th></tr>"
            + "".join(rows) + "</table></div>")
    return page(title, body, "acceptance")


def _compact(v, depth: int = 0) -> str:
    """A readable rendering of an acceptance row's `actual` value, whatever its shape."""
    if v is None or v == [] or v == {}:
        return f"<span class='muted'>{L('无', 'none')}</span>"
    if isinstance(v, dict):
        if depth > 1:
            return e(json.dumps(v, ensure_ascii=False)[:300])
        return "".join(f"<div><b>{e(str(k))}</b>: {_compact(x, depth + 1)}</div>" for k, x in v.items())
    if isinstance(v, list):
        if all(not isinstance(x, (dict, list)) for x in v):
            return e(", ".join(str(x) for x in v)[:400])
        return "".join(f"<div>{_compact(x, depth + 1)}</div>" for x in v[:12]) + (
            f"<div class='muted'>{L(f'另有 {len(v) - 12} 项', f'{len(v) - 12} more')}</div>" if len(v) > 12 else "")
    return e(str(v)[:400])


def acceptance_generic(step: str, res: dict | None) -> str:
    """Verified expectations next to the ledger results for step 3b-3e (scripts/acceptance_step<step>.py output,
    shown as is). One layout for all four, because their row shapes differ but every row has what / actual /
    ok / problem / source."""
    title = L(f"Step {step} 验收对照", f"Step {step} acceptance")
    if not res:
        body = (f"<h1>{title}</h1><p class='muted'>{L('还没有验收结果。运行', 'No acceptance result yet. Run')} "
                f"<code>python3 scripts/acceptance_step{step}.py</code>.</p>")
        return page(title, body, f"acceptance_{step}")
    made = time.strftime("%Y-%m-%d %H:%M", time.localtime(res.get("created_at", 0)))
    overall = tag("pass" if res.get("ok") else "fail", "PASS" if res.get("ok") else "FAIL")
    cases = res.get("cases") or {c: {"ledger_ok": ok} for c, ok in (res.get("ledgers_ok") or {}).items()}
    crow = []
    for cid, m in cases.items():
        fr = m.get("fresh") if isinstance(m, dict) else None
        fresh = "" if fr is None else (tag("pass", L("新鲜", "fresh")) if fr.get("fresh") else
                                       tag("warn", L("过期", "stale") + ": " + "; ".join(fr.get("reasons") or [])))
        ok = (m or {}).get("ledger_ok")
        chk = tag("pass", L("通过", "pass")) if ok else tag("fail", L("未通过", "failed"))
        crow.append(f"<tr><td><a href='cases/{e(fn(cid))}#board'>{e(cid)}</a></td><td>{chk}</td><td>{fresh}</td></tr>")
    rows = []
    for r in res.get("rows") or []:
        mark = ("<b class='pass'>✓</b>" if r.get("ok") else
                f"<b class='fail'>✗</b> <span class='{'warn' if r.get('stale') else 'fail'}'>{e(r.get('problem') or '')}</span>")
        src = r.get("source") or {}
        quote = f"<q>{e(src['quote'])}</q>" if src.get("quote") else ""
        what = (r.get("what") or {}).get("en" if LANG == "en" else "zh") or r.get("id")
        rows.append(f"<tr class='{'' if r.get('ok') else 'badrow'}'><td>{e(what)}<div class='muted'>{e(r.get('case', ''))}"
                    f" · {e(r.get('id', ''))}</div></td><td>{_compact(r.get('actual'))}</td><td>{mark}</td>"
                    f"<td>{link(src.get('url') or None, src.get('doc') or '')}{quote}</td></tr>")
    extra = ""
    if res.get("unassessable_summary"):
        u = res["unassessable_summary"]
        extra = (f"<h2>{L('无法评估统计', 'Unable-to-assess tally')}</h2><p>"
                 + L(f"{u.get('unassessable_rows')} / {u.get('judgements')} 条判定无法评估（{u.get('share_of_judgements')}）",
                     f"{u.get('unassessable_rows')} of {u.get('judgements')} judgements unassessable "
                     f"({u.get('share_of_judgements')})")
                 + "</p><ul>" + "".join(f"<li>{n} — {e(w)}</li>" for w, n in (u.get("by_reason") or {}).items()) + "</ul>")
    body = (f"<h1>{title} {overall}</h1><p class='muted'>"
            + L(f"{res.get('n_ok')}/{res.get('n')} 条期望成立 · 结果生成于 {made}（代码 {res.get('code_commit')}）。"
                f"本页只显示 scripts/acceptance_step{step}.py 的输出，不做计算。",
                f"{res.get('n_ok')}/{res.get('n')} expectations hold · result made {made} (code {res.get('code_commit')}). "
                f"This page only shows the output of scripts/acceptance_step{step}.py.")
            + f"</p><h2>{L('账本', 'Ledgers')}</h2><div class='wrap'><table><tr><th>{L('病例', 'Case')}</th>"
            f"<th>{L('账本校验', 'Ledger checks')}</th><th>{L('新鲜度', 'Freshness')}</th></tr>" + "".join(crow)
            + f"</table></div><h2>{L('期望与实际', 'Expected vs actual')}</h2><div class='wrap'><table><tr>"
            f"<th>{L('核实期望', 'Verified expectation')}</th><th>{L('账本实际', 'Ledger result')}</th><th></th>"
            f"<th>{L('期望出处', 'Source')}</th></tr>" + "".join(rows) + "</table></div>" + extra)
    return page(title, body, f"acceptance_{step}")


def load_acceptance_step(step: str) -> dict | None:
    p = OUT / "acceptance" / f"step{step}.json"
    return json.loads(p.read_text()) if p.exists() else None


# ------------------------------------------------------------------ blind test page

def blind_batches() -> list[str]:
    return sorted((p.name for p in BLIND_OUT.iterdir() if (p / "machine.json").exists()), reverse=True) \
        if BLIND_OUT.exists() else []


def entry_id(r: dict) -> str:
    """A stable id for one written entry: the same case, section, label and conclusion give the same id."""
    import hashlib
    key = "|".join([r.get("case", ""), r.get("section", ""), str(r.get("label") or ""), r.get("conclusion") or ""])
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def load_judged(batch: str) -> dict:
    p = BLIND_JUDGED / f"{batch}.json"
    return json.loads(p.read_text()) if p.exists() else {"schema": "blind-judged-v1", "batch": batch, "judgements": {}}


VERDICT_LABEL = {"correct": ("正确", "Correct"), "wrong": ("写错", "Wrong"), "missed": ("漏写", "Missed"),
                 "unsure": ("不确定", "Unsure")}


def _status_text(st) -> str:
    if isinstance(st, dict):
        return " / ".join(sorted({act_label(v) for v in st.values()}))
    return act_label(st) if st else ""


def blind_page(batch: str | None = None, live: bool = False) -> str:
    """Overview, entry-by-entry judging and recall detail for one blind-test batch.

    The verdicts are saved by scripts/viewer_app.py (POST /api/blind/<batch>/judge) to data/eval/blind/<batch>.json;
    the static export shows them read-only."""
    title = L("盲测", "Blind test")
    batches = blind_batches()
    batch = batch or (batches[0] if batches else None)
    if not batch:
        none = L("还没有盲测批次（out/blind/<批次>/machine.json）。", "No blind batch yet.")
        return page(title, f"<h1>{title}</h1><p class='muted'>{none}</p>", "blind")
    d = BLIND_OUT / batch
    machine = json.loads((d / "machine.json").read_text())
    recall = json.loads((d / "recall.json").read_text()) if (d / "recall.json").exists() else None
    sample = json.loads((d / "sample.json").read_text()) if (d / "sample.json").exists() else {}
    judged = load_judged(batch)["judgements"]
    cases_file = BLIND_CASES / f"{batch}.json"
    groups = {c["id"]: (c.get("blind") or {}).get("group", "?") for c in json.loads(cases_file.read_text())} \
        if cases_file.exists() else {}
    # B1 is split into L1 (single-gene chapter) and L2 (overview only), from sample.json (decision 2026-11-11)
    for c in sample.get("cases") or []:
        if c.get("subgroup"):
            groups[f"BLIND-{c['gene']}"] = c["subgroup"]
    wrong_by_case: dict[str, list[dict]] = {}
    for w in machine.get("machine_wrong") or []:
        wrong_by_case.setdefault(w["case"], []).append(w)
    rows_by_case: dict[str, list[dict]] = {}
    for r in machine.get("for_review") or []:
        rows_by_case.setdefault(r["case"], []).append(r)

    pending = L("待算", "pending")

    def recall_cell(cid: str, key: str) -> str:
        v = ((recall or {}).get("cases") or {}).get(cid, {}).get(key)
        if v is None:
            return f"<span class='muted'>{pending}</span>"
        if isinstance(v, dict) and v.get("rate") is not None:
            return e(f"{v['rate']:.0%}") + f" <span class='muted'>({v.get('hit')}/{v.get('of')})</span>"
        return e(str(v))

    ov = []
    per_group: dict[str, dict] = {}
    for cid, m in (machine.get("cases") or {}).items():
        ran = m.get("ran")
        mine = [judged[entry_id(r)] for r in rows_by_case.get(cid, []) if entry_id(r) in judged]
        n_wrong = sum(1 for j in mine if j["verdict"] == "wrong")
        n_missed = sum(1 for j in judged.values() if j.get("case") == cid and j["verdict"] == "missed")
        g = groups.get(cid, "?")
        t = per_group.setdefault(g, {"cases": 0, "ran": 0, "entries": 0, "machine": 0, "judged": 0, "wrong": 0,
                                     "missed": 0})
        t["cases"] += 1
        if ran:
            t["ran"] += 1
            t["entries"] += m.get("entries") or 0
            t["machine"] += m.get("machine_wrong") or 0
            t["judged"] += len(mine)
            t["wrong"] += n_wrong
            t["missed"] += n_missed
        link_case = f"<a href='cases/{e(fn(cid))}#board'>{e(cid)}</a>" if ran else e(cid)
        ov.append(f"<tr><td>{link_case}</td><td>{e(BLIND_GROUP_LABEL.get(g, g))}</td>"
                  + (f"<td>{m.get('entries')}</td><td>{m.get('machine_wrong')}</td>"
                     f"<td>{n_wrong} <span class='muted'>({len(mine)}/{m.get('entries')} {L('已判', 'judged')})</span></td>"
                     f"<td>{n_missed}</td>" if ran else f"<td colspan='4' class='muted'>{L('未跑', 'not run')}</td>")
                  + "".join(f"<td>{recall_cell(cid, k)}</td>" for k in ("genereviews", "trials", "fda")) + "</tr>")
    overview = (f"<div class='wrap'><table><tr><th>{L('病例', 'Case')}</th><th>{L('组', 'Group')}</th>"
                f"<th>{L('写出条数', 'Entries')}</th><th>{L('机器写错', 'Machine wrong')}</th><th>{L('人工写错', 'Human wrong')}</th>"
                f"<th>{L('漏写', 'Missed')}</th><th>{L('GeneReviews 覆盖率', 'GeneReviews coverage')}</th>"
                f"<th>{L('试验召回率', 'Trial recall')}</th><th>{L('FDA 靶向召回率', 'FDA targeted recall')}</th></tr>"
                + "".join(ov) + "</table></div>")
    by_group_rows = "".join(
        f"<tr><td>{e(BLIND_GROUP_LABEL.get(g, g))}</td><td>{t['ran']}/{t['cases']}</td><td>{t['entries']}</td>"
        f"<td>{t['machine']}</td><td>{t['wrong']} <span class='muted'>({t['judged']}/{t['entries']})</span></td>"
        f"<td>{t['missed']}</td></tr>"
        for g, t in sorted(per_group.items(), key=lambda kv: BLIND_GROUP_ORDER.index(kv[0])
                           if kv[0] in BLIND_GROUP_ORDER else 99))
    overview += (f"<h3>{L('按组统计（各组分开，不合并成总率）', 'By group (kept apart, never pooled)')}</h3>"
                 f"<div class='wrap'><table><tr><th>{L('组', 'Group')}</th><th>{L('已跑', 'Run')}</th>"
                 f"<th>{L('写出条数', 'Entries')}</th><th>{L('机器写错', 'Machine wrong')}</th>"
                 f"<th>{L('人工写错', 'Human wrong')}</th><th>{L('漏写', 'Missed')}</th></tr>{by_group_rows}</table></div>")

    can_save = live
    ro = L("这是静态快照，判定只能查看。要保存判定，请用实时查看页：python3 scripts/viewer_app.py",
           "Static snapshot: verdicts are read-only. To save them, use the live app: python3 scripts/viewer_app.py")
    note = "" if can_save else f"<p class='warn'>{ro}</p>"
    blocks = []
    for cid, rows in rows_by_case.items():
        mw = wrong_by_case.get(cid, [])
        by_sec: dict[str, list[dict]] = {}
        for r in rows:
            by_sec.setdefault(r["section"], []).append(r)
        secs = []
        for sec in sorted(by_sec, key=lambda x: (x == "supportive_management", x)):
            items = []
            for r in sorted(by_sec[sec], key=lambda r: r.get("label") or ""):
                eid = entry_id(r)
                j = judged.get(eid, {})
                hits = [w for w in mw if (w.get("action") or "").lower() in (str(r.get("label") or "").lower(),)]
                mcheck = (tag("fail", L("机器判定：写错", "machine: wrong")) + "".join(
                    f"<div class='fail'>[{e(w['check'])}] {e(w['detail'][:200])}</div>" for w in hits)) if hits \
                    else tag("pass", L("机器检查通过", "machine checks pass"))
                cites = "".join(
                    f"<div class='muted'>{e(c.get('type') or '')} {link(c.get('url') or None, c.get('id') or '')}"
                    f"{': <q>' + e(c['quote']) + '</q>' if c.get('quote') else ''}</div>" for c in r.get("cites") or [])
                radios = "".join(
                    f"<label><input type='radio' name='v-{eid}' value='{v}'{' checked' if j.get('verdict') == v else ''}"
                    f"{'' if can_save else ' disabled'}> {L(*VERDICT_LABEL[v])}</label> " for v in VERDICTS)
                form = (f"<div class='judge' data-eid='{eid}' data-case='{e(cid)}' data-section='{e(sec)}' "
                        f"data-label='{e(str(r.get('label') or ''))}'>{radios}"
                        f"<input class='note' type='text' placeholder='{L('备注', 'note')}' value='{e(j.get('note', ''))}'"
                        f"{'' if can_save else ' disabled'}>"
                        + (f" <button{'' if can_save else ' disabled'}>{L('保存', 'Save')}</button>" if can_save else "")
                        + (f" <span class='muted'>{L('已判', 'judged')} {e(time.strftime('%m-%d %H:%M', time.localtime(j['at'])))}</span>"
                           if j.get("at") else "") + "<span class='saved'></span></div>")
                items.append(f"<div class='card{' judged' if j else ''}'><div class='row'><b>{e(str(r.get('label') or ''))}</b> "
                             f"{tag('cond', _status_text(r.get('status')))} {mcheck}</div>"
                             + (f"<div>{e(r['conclusion'])}</div>" if r.get("conclusion") else "")
                             + cites + form + "</div>")
            secs.append(f"<details{' open' if sec != 'supportive_management' else ''}><summary>"
                        f"{e(section_label(sec))} ({len(by_sec[sec])})</summary>{''.join(items)}</details>")
        missed_here = [j for j in judged.values() if j.get("case") == cid and j["verdict"] == "missed"]
        ph = L("漏写条目（如：MAOI 与多巴胺激动剂相互作用）", "missed entry")
        add_missed = (f"<div class='judge missed-add' data-case='{e(cid)}' data-section='' data-label=''>"
                      f"<input class='label' type='text' placeholder='{ph}'>"
                      f"<input class='note' type='text' placeholder='{L('出处 / 备注', 'source / note')}'>"
                      f"<button>{L('记一条漏写', 'Add a missed entry')}</button><span class='saved'></span></div>") if can_save else ""
        listed = "".join(f"<li>{e(j.get('label', ''))} <span class='muted'>{e(j.get('note', ''))}</span></li>" for j in missed_here)
        blocks.append(f"<h3 id='case-{e(cid)}'>{e(cid)} <span class='muted'>{e(groups.get(cid, ''))}</span></h3>"
                      + "".join(secs) + f"<p><b>{L('漏写', 'Missed')}</b></p><ul>{listed or '<li class=muted>' + L('无', 'none') + '</li>'}</ul>"
                      + add_missed)

    if recall:
        rec = []
        for cid, m in (recall.get("cases") or {}).items():
            miss = "".join(f"<li>{e(x.get('item', ''))} <span class='muted'>— {e(x.get('cause', ''))}</span>"
                           f"{' ' + link(x.get('url'), L('来源', 'source')) if x.get('url') else ''}</li>"
                           for x in m.get("missed") or [])
            excl = "".join(f"<li>{e(x.get('item', ''))} <span class='muted'>— {e(x.get('rule', ''))}</span></li>"
                           for x in m.get("rule_excluded") or [])
            rec.append(f"<h3>{e(cid)}</h3><p><b>{L('漏掉的条目', 'Missed items')}</b></p><ul>{miss or '<li class=muted>—</li>'}</ul>"
                       f"<p><b>{L('规则有意排除', 'Excluded by a rule')}</b></p><ul>{excl or '<li class=muted>—</li>'}</ul>")
        recall_html = "".join(rec)
    else:
        nr = L("召回尚未计算（B 组全部跑完后统一计算，方案 docs/blind_recall_plan.md）。", "Recall not computed yet.")
        recall_html = f"<p class='muted'>{nr}</p>"

    frozen = sample.get("code_fingerprint", "")[:12]
    others = " ".join(f"<a href='?batch={e(b)}'>{e(b)}</a>" for b in batches if b != batch)
    stale = L("结果文件有更新。保存好正在写的备注后，点此刷新。", "Results changed. Save your notes, then click to reload.")
    body = (f"<div id='blind-page'></div><p id='blind-stale' class='warn' style='display:none;cursor:pointer' "
            f"onclick='location.reload()'>{stale}</p><h1>{title} · {e(batch)}</h1><p class='muted'>"
            + L(f"冻结指纹 {frozen} · 判定保存在 data/eval/blind/{batch}.json · 结论句保留报告原文（英文），"
                f"中文只用于界面与状态。", f"frozen fingerprint {frozen} · verdicts in data/eval/blind/{batch}.json")
            + (f" · {L('其他批次', 'other batches')}: {others}" if others else "") + "</p>"
            + f"<h2>{L('总览', 'Overview')}</h2>{overview}<h2>{L('逐条判定', 'Entry by entry')}</h2>{note}"
            + "".join(blocks) + f"<h2>{L('召回明细', 'Recall detail')}</h2>{recall_html}"
            + (BLIND_JS % json.dumps(batch) if can_save else ""))
    return page(title, body, "blind")


BLIND_JS = """<script>(function(){
var batch=%s;
function save(box, extra){
  var r=box.querySelector('input[type=radio]:checked');
  var body=Object.assign({entry_id:box.dataset.eid||'', case:box.dataset.case, section:box.dataset.section,
    label:box.dataset.label, verdict:r?r.value:'', note:(box.querySelector('.note')||{}).value||''}, extra||{});
  var out=box.querySelector('.saved'); out.textContent=' …';
  fetch('/api/blind/'+encodeURIComponent(batch)+'/judge',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)}).then(function(x){return x.json().then(function(j){return [x.ok,j];});})
    .then(function(p){out.textContent=p[0]?' ✓':' ✗ '+(p[1].detail||'');}).catch(function(){out.textContent=' ✗';});
}
document.querySelectorAll('.judge').forEach(function(box){
  var b=box.querySelector('button'); if(!b) return;
  b.addEventListener('click',function(ev){ev.preventDefault();
    if(box.classList.contains('missed-add')){
      var l=box.querySelector('.label').value; if(!l) return;
      save(box,{entry_id:'', verdict:'missed', label:l});
    } else save(box);
  });
});
})();</script>"""


def load_acceptance() -> dict | None:
    return json.loads(ACCEPTANCE.read_text()) if ACCEPTANCE.exists() else None


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
<h2 id='board'>{L('行动看板（Step 3 证据账本）', 'Action board (step 3 ledger)')}</h2>{v_board(c['steps'][3])}
<h2 id='tree'>{L('全景目录（证据树）', 'Full catalogue (evidence tree)')}</h2><details><summary>{L('展开：诊断分支 → 证据层级 → 章节 → 行动 → 证据', 'Expand: branch → tier → section → action → evidence')}</summary>{v_tree(c)}</details>
<h2>{L('来源链接', 'Source links')}</h2>{v_sources(s2)}"""
    return page(f"{c['id']} {L('审查', 'review')}", body, c["id"], depth=1)


# ------------------------------------------------------------- index, compare

def legend() -> str:
    """How to read the overview columns (mirrors resolve.select / resolve.confidence)."""
    items = [
        (L("分组", "Group"), L(
            "练习：官网 Phase 0 示例题（data/cases/practice/official_examples.json），可用于调试；"
            "验证（干净）：Phase 1 Hugging Face 数据集中练习和评测都没出现过的基因（AITX-00007 DDC），规则定稿前不看结果、不据此调规则；"
            "验证（已用于发现问题）：同来源，但已用来发现问题（AITX-00011 KCNT1），不再算留出集；"
            "评测：比赛的 4 个评测病例（data/cases/aitx_final_patients.json）。",
            "Practice: official Phase 0 examples (data/cases/practice/official_examples.json), fine for debugging. "
            "Validation (clean): a Phase 1 Hugging Face case whose gene appears in no practice or evaluation case "
            "(AITX-00007 DDC); rules are never tuned on it. Validation (used): same source, already used to find issues "
            "(AITX-00011 KCNT1), so no longer held out. Evaluation: the 4 challenge cases (data/cases/aitx_final_patients.json).")),
        (L("依据", "Basis"), L(
            "按优先级从高到低：原文点名（临床描述写出了疾病名或 OMIM/ORPHA 编号）> ClinVar 变异级证据（同一变异的 P/LP 记录关联到该病）"
            "> 遗传方式分层（只有它落在最好的遗传方式层）> 症状分（同一层里按 HPO 症状相似度比较）；"
            "唯一候选：排除后只剩这一个。前一级能定就不看后一级。",
            "Highest priority first: named in the text (disease name or OMIM/ORPHA number in the clinical text) > "
            "ClinVar variant-level evidence (P/LP record for this exact variant linked to the disease) > inheritance tier "
            "(the only candidate in the best inheritance tier) > phenotype score (HPO similarity within that tier). "
            "Only candidate: the only one left after exclusions. A lower level is used only if the higher ones do not decide.")),
        (L("置信度", "Confidence"), L(
            "检查三项：① 基因-疾病证据强度为 Definitive/Strong；② 遗传方式吻合；③ 选择依据明确（原文点名，或 ClinVar ≥2 星，"
            "或症状分领先 ≥20%）。三项全满足为 high，缺一项为 moderate，缺两项及以上为 low。另外：遗传方式只是条件吻合直接为 low；"
            "所选疾病没有症状注释时最高 moderate；按原文或 ClinVar 选出、但症状分落后最高分 ≥20% 时再降一级。",
            "Three checks: (1) gene-disease validity Definitive/Strong; (2) inheritance consistent; (3) clear basis "
            "(named in the text, ClinVar >= 2 stars, or phenotype lead >= 20%). All three: high; one missing: moderate; "
            "two or more missing: low. Also: conditional inheritance forces low; no phenotype annotations caps at moderate; "
            "chosen by text or ClinVar while its phenotype score trails the best by >= 20% drops one level.")),
        (L("状态", "Status"), L(
            "已确定：有唯一首选；有歧义：前几名差距小于 20%，或三次 LLM 抽样结果不一致，或 unknown 遗传方式的候选症状分高出 ≥20%，"
            "后续步骤要对每个并列诊断分别处理；未确定：没有合格候选。",
            "Resolved: one primary. Ambiguous: top candidates within 20%, LLM samples disagree, or an unknown-inheritance "
            "candidate scores >= 20% higher; later steps handle each tied diagnosis. Unresolved: no eligible candidate.")),
        (L("并列数", "Tied"), L(
            "与首选并列、需要一起考虑的其他候选个数（状态为“已确定”时为 0）。",
            "Number of other candidates tied with the primary and carried forward (0 when resolved).")),
    ]
    dl = "".join(f"<tr><th style='white-space:nowrap'>{h}</th><td>{e(t)}</td></tr>" for h, t in items)
    return f"<details open><summary>{L('怎么看这张表', 'How to read this table')}</summary><table>{dl}</table></details>"


def index_page(rows: list[dict], snap: str, commit: str) -> str:
    trs = []
    for r in rows:
        problems = "<br>".join(e(p) for p in r["problems"]) or f"<span class=muted>{L('无', 'none')}</span>"
        trs.append(f"<tr><td><a href='cases/{e(fn(r['id']))}'>{e(r['id'])}</a></td><td>{e(group_label(r['group']))}</td>"
                   f"<td>{'<br>'.join(e(v) for v in r['variants'])}</td><td>{e(r['primary'] or '—')}"
                   f"<div class='muted'>{e(' '.join(r['omim']))}</div></td>"
                   f"<td>{tag(STATUS_CLS[r['status']], status_label(r['status']))}</td><td>{e(str(r['confidence']))}</td>"
                   f"<td>{e(basis_label(r['basis']))}</td><td>{r['n_alternatives']}</td><td class='fail'>{problems}</td></tr>")
    head = [L("病例", "Case"), L("分组", "Group"), L("变异", "Variants"), L("首选疾病", "Primary disease"), L("状态", "Status"),
            L("置信度", "Confidence"), L("依据", "Basis"), L("并列数", "Tied"), L("报错/警告", "Errors / warnings")]
    intro = L(f"快照 {snap} · 代码 {commit} · {len(rows)} 个病例。点病例编号看详情。",
              f"Snapshot {snap} · code {commit} · {len(rows)} cases. Click a case for details.")
    acc = load_acceptance()
    acc_line = (f"<p class='card'>{L('Step 3a 验收对照', 'Step 3a acceptance')}: <a href='{fn('acceptance')}'>"
                + (f"{acc['n_ok']}/{acc['n']} " + L('条期望成立', 'expectations hold') + f" · {'PASS' if acc['ok'] else 'FAIL'}" if acc else L('尚未运行', 'not run yet'))
                + "</a></p>")
    body = (f"<h1>{L('审查总表', 'Review overview')}</h1><p class='muted'>{e(intro)}</p>{acc_line}{legend()}<div class='wrap'><table><tr>"
            + "".join(f"<th>{h}</th>" for h in head) + f"</tr>{''.join(trs)}</table></div>")
    return page(L("审查总表", "Review overview"), body, "index")


def compare_page(cur: list[dict], prev: list[dict] | None, snap: str, prev_snap: str | None) -> str:
    title = L("版本对比", "Run comparison")
    if prev is None:
        msg = L(f"快照 {snap} 是第一份快照，没有可对比的旧版本。下次生成时会自动和这一份对比，也可以用 --compare 指定。",
                f"Snapshot {snap} is the first one in this language; nothing to compare yet. The next build compares "
                "with it automatically, or pass --compare.")
        return page(title, f"<h1>{title}</h1><p class='muted'>{e(msg)}</p>", "compare")
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
        trs.append(f"<tr><td><a href='cases/{e(fn(r['id']))}'>{e(r['id'])}</a></td><td>{'<br>'.join(diffs) or same}</td></tr>")
    body = (f"<h1>{title}</h1><p class='muted'>{e(prev_snap)} → {e(snap)}</p>"
            f"<table><tr><th>{L('病例', 'Case')}</th><th>{L('变化', 'Changes')}</th></tr>{''.join(trs)}</table>")
    return page(title, body, "compare")


def snapshots_index() -> None:
    snaps = sorted([p.name for p in REVIEW.iterdir() if p.is_dir() and (p / "index.html").exists()], reverse=True)
    items = "".join(f"<li><a href='{s}/index.html'>{s}</a>{' (EN only)' if s.endswith('-en') else ''}</li>" for s in snaps)
    (REVIEW / "index.html").write_text(
        f"<!doctype html><html><head><meta charset='utf-8'><title>Review snapshots / 审查快照</title><style>{CSS}</style></head>"
        f"<body><main><h1>审查快照 / Review snapshots</h1><p class='muted'>新的在前 / newest first</p><ul>{items}</ul></main></body></html>")


# ----------------------------------------------------------------------- main

def contexts() -> dict[str, str]:
    """Clinical text per case: the case files, then any blind-test batch (data/cases/blind/<batch>.json), whose
    cases carry their description as `clinical_description`."""
    from run_pipeline import CASE_FILES
    out = {}
    for f in list(CASE_FILES) + sorted(BLIND_CASES.glob("*.json")):
        if f.exists():
            for c in json.loads(f.read_text()):
                pt = c.get("patient") or {}
                out.setdefault(c["id"], pt.get("clinical_context") or pt.get("clinical_description") or "")
    return out


def collect(out: Path | None = None) -> tuple[list[dict], list[str]]:
    """All cases with a step 2 output, in overview order, plus problems found while loading.

    `out`: an out/ directory (default the live one; an accepted archive's out/ for comparisons).
    Step status texts are in the current LANG (set LANG before calling)."""
    out = out or OUT
    ids = sorted(p.stem for p in (out / "step2").glob("*.json") if p.stem != "sources_manifest")
    cases, problems = [], []
    for cid in ids:
        c = load_case(cid, out)
        if not c["steps"][2] or "_meta" not in c["steps"][2]:
            problems.append(f"{cid}: step 2 output has no provenance; regenerate with scripts/run_pipeline.py")
            continue
        cases.append(c)
    return sorted(cases, key=lambda c: (GROUP_ORDER.index(c["group"]), c["id"])), problems


SNAPSHOTS = ROOT / ".cache" / "snapshots"      # archives written by scripts/tag_accepted.py


def accepted_archives() -> list[dict]:
    """Manifests of the accepted-version archives, newest first."""
    ms = [json.loads(p.read_text()) for p in SNAPSHOTS.glob("*/manifest.json")] if SNAPSHOTS.exists() else []
    return sorted(ms, key=lambda m: -m["created_at"])


def rows_from_archive(tag: str) -> list[dict] | None:
    d = SNAPSHOTS / tag / "out"
    if not d.exists():
        return None
    return [summary_row(c) for c in collect(d)[0]]


def compare_rows(against: str | None) -> tuple[list[dict] | None, str | None]:
    """(rows, label) to compare with: 'tag:<accepted tag>', a review snapshot name, or None = latest snapshot."""
    if against and against.startswith("tag:"):
        tag = against[4:]
        return rows_from_archive(tag), (L(f"验收版本 {tag}", f"accepted version {tag}") if rows_from_archive(tag) is not None else None)
    name = against or latest_snapshot()
    if name and (REVIEW / name / "review.json").exists():
        return json.loads((REVIEW / name / "review.json").read_text())["cases"], name
    return None, None


def compare_choices(current: str | None) -> str:
    """Links to the comparison bases (live app only)."""
    items = [(f"tag:{m['tag']}", L(f"验收 {m['tag']}", f"accepted {m['tag']}") + f" ({m['created'][:10]})")
             for m in accepted_archives()]
    snap = latest_snapshot()
    if snap:
        items.append((snap, L(f"最新快照 {snap}", f"latest snapshot {snap}")))
    links = [f"<b>{e(t)}</b>" if k == current else f"<a href='{fn('compare')}?against={e(k)}'>{e(t)}</a>" for k, t in items]
    return f"<p>{L('对比基准', 'Compare against')}: " + " · ".join(links) + "</p>" if links else ""


def latest_snapshot(exclude: str | None = None) -> str | None:
    if not REVIEW.exists():
        return None
    return next((p.name for p in sorted(REVIEW.iterdir(), reverse=True)
                 if p.is_dir() and p.name != exclude and (p / "review.json").exists()), None)


def render_page(rel: str, against: str | None = None) -> str | None:
    """Render one page live from out/ (paths as in a snapshot: index.html, cases/<id>.en.html, ...).

    against: comparison base for the compare page ('tag:<accepted tag>' or a review snapshot name).
    Used by scripts/viewer_app.py; None if there is no such page. Not thread-safe (LANG is global)."""
    global LANG
    LANG = "en" if rel.endswith(".en.html") else "zh"
    base = rel[:-len(".en.html")] if LANG == "en" else rel[:-len(".html")]
    ordered, _ = collect()
    if base.startswith("cases/"):
        c = next((c for c in ordered if c["id"] == base[len("cases/"):]), None)
        return case_page(c, contexts().get(c["id"], "")) if c else None
    rows = [summary_row(c) for c in ordered]
    live = L("实时（直接读取 out/）", "live (read from out/)")
    if base == "index":
        return index_page(rows, live, runmeta.code_commit())
    if base == "acceptance":
        return acceptance_page(load_acceptance())
    if base.startswith("acceptance_") and base[len("acceptance_"):] in ACCEPT_STEPS:
        step = base[len("acceptance_"):]
        return acceptance_generic(step, load_acceptance_step(step))
    if base == "blind":
        return blind_page(against, live=True)
    if base == "compare":
        prev, prev_name = compare_rows(against)
        out = compare_page(rows, prev, live, prev_name)
        return out.replace("</h1>", "</h1>" + compare_choices(against or latest_snapshot()), 1)
    return None


def main() -> int:
    global LANG, DEFAULT_LANG, REVIEW
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["zh", "en"], default="zh",
                    help="default UI language when the browser has no stored choice (both are always built)")
    ap.add_argument("--compare", help="snapshot name under out/review/ to compare with (default: previous one, same language)")
    ap.add_argument("--review-dir", type=Path, default=REVIEW, help="where snapshots go (default out/review)")
    ap.add_argument("--compare-accepted", metavar="TAG", help="compare with the archive of an accepted tag "
                                                             "(.cache/snapshots/<TAG>, made by scripts/tag_accepted.py)")
    args = ap.parse_args()
    DEFAULT_LANG = args.lang
    REVIEW = args.review_dir
    ctx = contexts()
    ordered, problems = collect()
    if problems:
        print("\n".join(problems))
    snap = time.strftime("%Y%m%d-%H%M%S")
    d = REVIEW / snap
    (d / "cases").mkdir(parents=True, exist_ok=True)
    (d / "data").mkdir(exist_ok=True)
    rows = [summary_row(c) for c in ordered]
    for c in ordered:
        for k in STEPS:
            src = runmeta.path(k, c["id"])
            if src.exists():
                shutil.copy(src, d / "data" / f"step{k}-{c['id']}.json")
    commit = runmeta.code_commit()
    (d / "review.json").write_text(json.dumps({"schema": "review-v1", "snapshot": snap, "code_commit": commit,
                                               "cases": rows, "trees": {c["id"]: c["tree"] for c in ordered}},
                                              indent=1, ensure_ascii=False))
    if args.compare_accepted:
        prev, prev_name = rows_from_archive(args.compare_accepted), f"accepted {args.compare_accepted}"
        if prev is None:
            print(f"no archive for {args.compare_accepted} under {SNAPSHOTS}")
            return 2
    else:
        prev_name = args.compare or latest_snapshot(exclude=snap)
        prev = json.loads((REVIEW / prev_name / "review.json").read_text())["cases"] if prev_name else None
    for lang in ("zh", "en"):
        LANG = lang
        for c in ordered:
            c["status"] = {k: step_status(k, c["steps"][k]) for k in STEPS}   # status text is language-dependent
            (d / "cases" / fn(c["id"])).write_text(case_page(c, ctx.get(c["id"], "")))
        (d / fn("index")).write_text(index_page(rows, snap, commit))
        (d / fn("compare")).write_text(compare_page(rows, prev, snap, prev_name))
        (d / fn("acceptance")).write_text(acceptance_page(load_acceptance()))
        for step in ACCEPT_STEPS:
            (d / fn(f"acceptance_{step}")).write_text(acceptance_generic(step, load_acceptance_step(step)))
        (d / fn("blind")).write_text(blind_page(live=False))
    snapshots_index()
    print(f"{len(rows)} cases x 2 languages -> {d}/index.html")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

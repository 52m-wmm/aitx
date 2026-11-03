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
            f"<a href='{up}{fn('compare')}'>{L('版本对比', 'Run comparison')}</a></p>{body}</main>"
            f"{SWITCH_JS % DEFAULT_LANG}</body></html>")


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
                     f"max {rsa['max_asa_A2']} Å²)</span><div class='muted'>{e(rsa['method'])}</div>"))
    nb = st.get("neighbours_8A")
    if nb is not None:
        rows.append((L("8 Å 内的邻居", "Neighbours within 8 Å"),
                     f"{len(nb)}: " + e(", ".join(f"{n['aa']}{n['position']}" for n in nb))))
    if st.get("lost_model_range"):
        a, b = st["lost_model_range"]
        rows.append((L("丢失部分（模型编号）", "Lost part (model numbering)"), f"{a}–{b}"))
    for n in notes:
        rows.append((L("说明", "Note"), e(n)))
    table = "<table>" + "".join(f"<tr><th style='width:190px'>{h}</th><td>{d}</td></tr>" for h, d in rows) + "</table>"
    pos = (st.get("residue") or {}).get("model_position")
    data = {"file": src["local_file"], "pos": pos, "plddt": (pl or {}).get("value"),
            "neighbours": [n["position"] for n in (nb or [])], "lost": st.get("lost_model_range"),
            "label": f"{(st.get('residue') or {}).get('model_aa', '')}{pos or ''}"}
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
    body = (f"<h1>{L('审查总表', 'Review overview')}</h1><p class='muted'>{e(intro)}</p>{legend()}<div class='wrap'><table><tr>"
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
    from run_pipeline import CASE_FILES
    out = {}
    for f in CASE_FILES:
        if f.exists():
            for c in json.loads(f.read_text()):
                out[c["id"]] = c["patient"].get("clinical_context", "")
    return out


def collect() -> tuple[list[dict], list[str]]:
    """All cases with a step 2 output, in overview order, plus problems found while loading.

    Step status texts are in the current LANG (set LANG before calling)."""
    ids = sorted(p.stem for p in (OUT / "step2").glob("*.json") if p.stem != "sources_manifest")
    cases, problems = [], []
    for cid in ids:
        c = load_case(cid)
        if not c["steps"][2] or "_meta" not in c["steps"][2]:
            problems.append(f"{cid}: step 2 output has no provenance; regenerate with scripts/run_pipeline.py")
            continue
        cases.append(c)
    return sorted(cases, key=lambda c: (GROUP_ORDER.index(c["group"]), c["id"])), problems


def latest_snapshot(exclude: str | None = None) -> str | None:
    if not REVIEW.exists():
        return None
    return next((p.name for p in sorted(REVIEW.iterdir(), reverse=True)
                 if p.is_dir() and p.name != exclude and (p / "review.json").exists()), None)


def render_page(rel: str) -> str | None:
    """Render one page live from out/ (paths as in a snapshot: index.html, cases/<id>.en.html, ...).

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
    if base == "compare":
        prev_name = latest_snapshot()
        prev = json.loads((REVIEW / prev_name / "review.json").read_text())["cases"] if prev_name else None
        return compare_page(rows, prev, live, prev_name)
    return None


def main() -> int:
    global LANG, DEFAULT_LANG, REVIEW
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["zh", "en"], default="zh",
                    help="default UI language when the browser has no stored choice (both are always built)")
    ap.add_argument("--compare", help="snapshot name under out/review/ to compare with (default: previous one, same language)")
    ap.add_argument("--review-dir", type=Path, default=REVIEW, help="where snapshots go (default out/review)")
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
    prev_name = args.compare or latest_snapshot(exclude=snap)
    prev = json.loads((REVIEW / prev_name / "review.json").read_text())["cases"] if prev_name else None
    for lang in ("zh", "en"):
        LANG = lang
        for c in ordered:
            c["status"] = {k: step_status(k, c["steps"][k]) for k in STEPS}   # status text is language-dependent
            (d / "cases" / fn(c["id"])).write_text(case_page(c, ctx.get(c["id"], "")))
        (d / fn("index")).write_text(index_page(rows, snap, commit))
        (d / fn("compare")).write_text(compare_page(rows, prev, snap, prev_name))
    snapshots_index()
    print(f"{len(rows)} cases x 2 languages -> {d}/index.html")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

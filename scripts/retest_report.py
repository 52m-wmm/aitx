"""Review sheet for the retest batch (fix-phase retest, 2026-11-12). Reads ledgers and the machine check; no LLM.

Writes docs/retest_20261112_review.md (Chinese): per case the diagnosis, every entry a reviewer must judge (status,
the source quote and its link), every change the context check made (to be judged as a catch or a harm), and for
THPO the trials the cancer rule excluded.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = "retest-20261112"
CASES = ["RETEST-CNNM4", "RETEST-EIF2B1", "RETEST-THPO", "RETEST-PFN1"]
SECTION_CN = {"existing_targeted_therapies": "Tier 1 已有靶向疗法", "supportive_management": "Tier 1 支持治疗",
              "contraindications_precautions": "Tier 1 禁忌与注意", "clinical_trial_eligibility": "Tier 2 临床试验",
              "off_label_expanded_access": "Tier 2 超说明书 / 扩展使用", "bespoke_therapies": "Tier 3 定制疗法",
              "drug_repurposing": "Tier 3 药物重定位"}
STATUS_CN = {"applicable": "适用", "conditional": "有条件", "not_applicable": "不适用", "searched_none": "检索无结果",
             "not_assessable": "无法评估"}
KIND_CN = {"scope": "范围（证据不是关于本病 / 证据来自动物或他基因）", "limit": "限定（只针对部分病人）",
           "exemption": "例外（禁忌里的豁免从句）", "degree": "程度（病人未达到原文程度）"}
TRIAL_ROWS = 25


def q(text: str, n: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= n else text[:n] + "…"


def link(src: dict) -> str:
    return src.get("url") or ""


def status(a: dict) -> tuple[str, str]:
    if "status_by_branch" not in a:                    # 3d / 3e judgements carry a classification instead
        c = a.get("classification") or "-"
        return STATUS_CN.get(c, c), a.get("conclusion") or a.get("failed_criterion") or ""
    st = list(a["status_by_branch"].values())[0]
    return STATUS_CN.get(st["status"], st["status"]), st.get("reason", "")


def case_section(cid: str, out: list[str]) -> dict:
    led = json.loads((ROOT / "out" / "step3" / f"{cid}.json").read_text())
    s2 = json.loads((ROOT / "out" / "step2" / f"{cid}.json").read_text())
    case = next(c for c in json.loads((ROOT / "data" / "cases" / "blind" / f"{BATCH}.json").read_text()) if c["id"] == cid)
    ev = {e["id"]: e for e in led["evidence"]}
    g = case["patient"]["genotype"][0]
    p = s2["primary"]
    out += [f"## {cid}（{case['blind']['group']}）", "",
            f"- 变异：{g['gene']} {g['transcript']} {g['variant_cdna']} {g['variant_protein']}（{g['zygosity']}），"
            f"ClinVar {case['blind']['clinvar']}",
            f"- 描述（{case['blind']['description_source']}）：{q(case['patient']['clinical_context'], 400)}",
            f"- Step 2 诊断：{p['status']} → {p['label']} {p['omim']}"
            + (f"；备选 {[a['label'] for a in p.get('alternatives') or []]}" if p.get("alternatives") else ""),
            f"- 账本检查：{'全部通过' if led['ok'] else '有失败'}"
            f"（fail {[c['name'] for c in led['checks'] if c['status'] == 'fail']}，"
            f"warn {[c['name'] for c in led['checks'] if c['status'] == 'warn']}）", ""]
    changes, n_judge = [], 0
    for sec, name in SECTION_CN.items():
        acts = [a for a in led["actions"] if a["section"] == sec]
        out.append(f"### {name}（{len(acts)} 条）")
        if not acts:
            out += ["（无）", ""]
            continue
        trials = sec == "clinical_trial_eligibility"
        shown = [a for a in acts if not trials or status(a)[0] in ("适用", "有条件")]
        if trials and len(shown) > TRIAL_ROWS:
            out.append(f"适用 / 有条件的试验 {len(shown)} 条，列前 {TRIAL_ROWS} 条；其余见账本。")
            shown = shown[:TRIAL_ROWS]
        for a in shown:
            st, why = status(a)
            n_judge += st != "检索无结果"
            srcs = [ev[i] for i in a.get("evidence_ids") or [] if i in ev and ev[i].get("kind") == "sourced"]
            out.append(f"- **{a['label']}** — {st}（{q(why, 120)}）")
            for e in srcs[:2]:
                out.append(f"  - 原文：\"{q(e.get('quote'))}\" [{e['source'].get('type')} {e['source'].get('id')}]({link(e['source'])})")
            for r in a.get("requirements") or []:
                if r.get("context_check"):
                    changes.append((a["label"], sec, KIND_CN.get(r["context_check"], r["context_check"]),
                                    r["requirement"], r["result"], r.get("note", "")))
            cc = a.get("context_check") or {}
            for na in cc.get("not_applied") or []:
                changes.append((a["label"], sec, "只记备注（说明书决定 / 另一段落成立）", na, "-", ""))
            for pr in a.get("precedents") or []:
                pc = pr.get("context_check") or {}
                if pr.get("subject") not in (None, "same") or pr.get("direction"):
                    changes.append((a["label"], sec, "3c 先例", f"PMID {pr.get('pmid')}: 病人 {pr.get('subject')}，"
                                    f"方向 {pr.get('direction')}", "-", ""))
        out.append("")
    for k, v in (led.get("offlabel_searches") or {}).items():
        for pr in v.get("not_treatment_precedents") or []:
            changes.append((pr.get("drug") or "?", "off_label_expanded_access", "核查判为非治疗先例（剔除）",
                            f"PMID {pr.get('pmid')}", "-", ""))
    out.append("### 上下文核查做出的改动（逐条判：抓住 / 误伤）")
    if not changes:
        out += ["（无）", ""]
    for lab, sec, kind, text, res, note in changes:
        out.append(f"- {lab}（{SECTION_CN.get(sec, sec)}）：{kind} — \"{q(text, 160)}\" → {res}"
                   + (f"；{q(note, 160)}" if note else ""))
    out.append("")
    return {"case": cid, "to_judge": n_judge, "checker_changes": len(changes), "led": led}


def thpo_excluded(led: dict, out: list[str]) -> None:
    out += ["## THPO：3b 被癌症规则排除的试验", ""]
    rows = []
    for ts in led["trial_searches"].values():
        for x in ts.get("excluded") or []:
            d = str(x.get("detail") or "")
            if "cancer" in d.lower() or "marker" in d.lower() or "tumour" in d.lower() or "tumor" in d.lower():
                rows.append(x)
    if not rows:
        out += ["（没有试验因癌症规则被排除）", ""]
    for x in rows:
        out.append(f"- [{x['nct']}]({x['url']}) {x['title']} — {x.get('status')}；{x.get('detail')}")
    other = [x for ts in led["trial_searches"].values() for x in ts.get("excluded") or [] if x not in rows]
    out += ["", f"其余被排除的试验 {len(other)} 条（相关性或状态等其他原因），见账本 `trial_searches`。", ""]


def main() -> int:
    out = ["# 复测 retest-20261112 审阅表", "",
           "由 `scripts/retest_report.py` 从账本生成；判定请写回判定文件。核查器的改动单列，逐条判断是抓住（改对了）还是误伤（改错了）。", ""]
    summary = []
    for cid in CASES:
        if (ROOT / "out" / "step3" / f"{cid}.json").exists():
            summary.append(case_section(cid, out))
    thpo = next((s for s in summary if s["case"] == "RETEST-THPO"), None)
    if thpo:
        thpo_excluded(thpo["led"], out)
    m = ROOT / "out" / "blind" / BATCH / "machine.json"
    if m.exists():
        out += ["## 机器检查", "", "```", q(m.read_text(), 4000), "```", ""]
    f = ROOT / "docs" / "retest_20261112_review.md"
    f.write_text("\n".join(out) + "\n")
    for s in summary:
        print(s["case"], "to judge", s["to_judge"], "checker changes", s["checker_changes"])
    print(f"-> {f.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

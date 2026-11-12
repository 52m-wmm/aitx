"""Tables for docs/local_model_comparison.md (experiment, 2026-11-12). Reads results only; calls nothing.

DeepSeek: out/context_check_validation.json (context-check-v3, reasoning_effort low, temperature 0).
Local:    out_alt/<label>/context_check_validation.json and out_alt/<label>/calls.jsonl.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "DeepSeek": ROOT / "out" / "context_check_validation.json",
    "Qwen t0": ROOT / "out_alt/qwen3.5-9b-mlx-4bit-t0/context_check_validation.json",
    "Qwen t0.7": ROOT / "out_alt/qwen3.5-9b-mlx-4bit-t0.7/context_check_validation.json",
    "MedGemma t0": ROOT / "out_alt/medgemma-1.5-4b-mlx-4bit-t0/context_check_validation.json",
    "MedGemma t0.7": ROOT / "out_alt/medgemma-1.5-4b-mlx-4bit-t0.7/context_check_validation.json",
}
CATEGORY = {"status": "3a 状态", "direction": "疗效方向", "treatment": "不良反应当先例", "subject": "先例病人基因/亚型"}


def load() -> dict:
    out = {}
    for name, p in RUNS.items():
        if p.exists():
            out[name] = json.loads(p.read_text())
    return out


def key(r):
    return (r["case"], r["label"])


def correct_call(r) -> bool:
    """The model got this entry right: a wrong entry caught, a correct entry not harmed."""
    return r["hit"] if r["verdict"] == "wrong" else not r["hit"]


def category(r) -> str:
    if r["verdict"] == "wrong":
        return CATEGORY[r["expect"][0]]
    return "正确条目 3a" if r["section"] != "off_label_expanded_access" else "正确条目 3c"


def unanimous(r) -> bool:
    return all(len(set(map(str, a["answers"]))) == 1 for chk in r["answers"] for a in chk.values())


def calls(name: str) -> dict:
    p = RUNS[name].parent / "calls.jsonl"
    if not p.exists():
        return {}
    rows = [json.loads(l) for l in p.read_text().splitlines()]
    ok = [r for r in rows if not r["error"]]
    return {"n": len(rows), "mean_s": sum(r["seconds"] for r in ok) / max(len(ok), 1),
            "bad_json": sum(r["bad_json"] for r in rows), "errors": sum(bool(r["error"]) for r in rows),
            "from_reasoning": sum(r.get("from_reasoning", False) for r in rows)}


def main() -> int:
    R = load()
    names = list(R)
    rows = {n: {key(r): r for r in R[n]["rows"]} for n in names}
    keys = list(rows["DeepSeek"])
    print("## 总体")
    for n in names:
        d = R[n]
        print(f"{n:14} caught {d['caught']}/{d['wrong']}  harmed {d['harmed']}/{d['correct']}  "
              f"caveats {len(d['caveats_on_correct'])}  calls {calls(n) or '-'}")
    print("\n## 按类别（对的条数/总数）")
    cats = sorted({category(rows['DeepSeek'][k]) for k in keys})
    for c in cats:
        ks = [k for k in keys if category(rows["DeepSeek"][k]) == c]
        print(f"{c:16} " + "  ".join(f"{n}: {sum(correct_call(rows[n][k]) for k in ks)}/{len(ks)}" for n in names))
    print("\n## 逐题（✓ 判对 / ✗ 判错）")
    print("| 病例 | 条目 | 判定 | " + " | ".join(names) + " |")
    for k in keys:
        r = rows["DeepSeek"][k]
        print(f"| {k[0]} | {k[1][:40]} | {category(r)} | "
              + " | ".join(("✓" if correct_call(rows[n][k]) else "✗ " + rows[n][k]["why"][:50]) for n in names) + " |")
    print("\n## 错在同一题（两两重合）")
    errs = {n: {k for k in keys if not correct_call(rows[n][k])} for n in names}
    for a, b in itertools.combinations(names, 2):
        both = errs[a] & errs[b]
        print(f"{a} ∩ {b}: {len(both)} 题（{a} 错 {len(errs[a])}，{b} 错 {len(errs[b])}）{sorted(x[1] for x in both)}")
    print("\n## 3 次投票一致")
    for n in names:
        u = [k for k in keys if unanimous(rows[n][k])]
        nu = [k for k in keys if k not in u]
        acc_u = sum(correct_call(rows[n][k]) for k in u)
        acc_n = sum(correct_call(rows[n][k]) for k in nu)
        print(f"{n:14} unanimous {len(u)}/{len(keys)} entries, right {acc_u}/{len(u)}; "
              f"split {len(nu)}, right {acc_n}/{len(nu) or 1}")
    print("\n## 级联：本地先判，有不一致的条目交给 DeepSeek")
    for n in [x for x in names if x != "DeepSeek"]:
        u = {k for k in keys if unanimous(rows[n][k])}
        res = {k: rows[n][k] if k in u else rows["DeepSeek"][k] for k in keys}
        sent = len(keys) - len(u)
        missed = [k[1] for k in keys if k in u and not correct_call(rows[n][k])]
        print(f"{n:14} sent to DeepSeek {sent}/{len(keys)} entries; right {sum(correct_call(r) for r in res.values())}/"
              f"{len(keys)}; local-unanimous but wrong: {missed}")
    print("\n## 交叉核查：改动（抓住或误伤）须两个模型都同意")
    for a, b in itertools.combinations(names, 2):
        right = 0
        for k in keys:
            hit = rows[a][k]["hit"] and rows[b][k]["hit"]        # the change is made only if both make it
            right += hit if rows[a][k]["verdict"] == "wrong" else not hit
        print(f"{a} & {b}: right {right}/{len(keys)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

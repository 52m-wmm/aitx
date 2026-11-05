# Step 3c 契约：待办（契约正文待写）

> 本文件收集写 3c（Off-label / Expanded-Access Therapies，新兴层）契约时必须纳入的事项。
> **已并入 `docs/step3c_contract.md` 草案第 1 版（2026-11-05）**：D-半乳糖 → 验收表；不沿用 L3 文献类型过滤 → 来源第 1 条。

## SLC35A2-CDG 的 D-半乳糖（2026-11-05 记录）

- **验收期望**：练习病例 PRAC-SLC35A2-ex7 / ex8 中，D-半乳糖出现在 Off-label / Expanded-Access 章节（新兴层），
  引用 PMID 32103184（Witters et al., *Genet Med* 2020；10 例开放标签研究）。原文：
  "Oral D-galactose supplementation results in clinical and biochemical improvement in SLC35A2-CDG."、
  "Oral galactose is well tolerated and shows promise as dietary therapy."
- 它**不进** 3a 的支持治疗（已确立层）。3a 已有对应期望 `ex7-no-galactose-supportive` / `ex8-no-galactose-supportive`。
- 证据强度要如实写：单臂、开放标签、10 例，不能写成已确立疗法。

## 文献检索不沿用 L3 的文献类型过滤（2026-11-05 记录）

- 支持治疗兜底链 L3 只检索综述、指南、共识、观察性 / 多中心研究（`fallback.PUB_TYPES`），目的是找"管理建议"。
- 3c 要找新兴疗法的**临床研究**，这类文章在 PubMed 上常只标 "Journal Article"（例如 PMID 32103184 只有
  Journal Article 和资助类标签），沿用 L3 的过滤就会漏掉。3c 的检索式另行设计；病例报告的处理方式在 3c 契约里单独规定。
- L3 与 3c 共用检索、摘要获取和开放获取判定模块（`aitx/evidence/fallback.py`：`abstracts_by_pmid`、`pmc_open_access_text`），只是检索式和过滤条件不同。

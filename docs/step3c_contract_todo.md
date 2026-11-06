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

## 盲测重点检查项：3c 检索排序规则（2026-11-05 记录）

以下规则是在验收病例（SLC35A2、GRIN2B、ANO10、AGXT）上逐步调出来的，有过拟合风险。后续盲测（新的练习病例、不看期望先跑）时要逐条检查：
- **背景词频率阈值**（`COMMON_SHARE = 0.15`）：在检索结果中出现比例超过 15% 的物质名不参与新药排序。阈值是对着 AGXT（calcium oxalate）、GRIN2B（glutamate）定的；检查真正的候选药会不会因为常见而被排到后面（ANO10 只有 6 篇时，CoQ10 本身就被算成背景词，靠篇数少才没漏掉）。
- **酶 / 蛋白名排除**：去掉酶名里的物质名（"glycolate oxidase" 里的 glycolate）。检查有没有误删真正的药物名，或漏删新的酶名写法。
- **按药轮流选取**（每种新药每轮一篇、标题提到的优先、上限 20）：检查候选药很多（> 20 种）时，有没有把有效证据最强的文献挤掉。
- **主要研究设计召回路径**（病例报告 / 临床试验 / 观察性研究另查 200 篇）：检查这条路径单独贡献了多少入选文献。
- **基因家族名算病人病因**（`gene_family`，前缀 ≥ 4 个字母）：这个长度阈值是为了让 GRIN2B 通过 L-serine 试验（PMID 38380699）这个**已知用例**才定的——4 个字母刚好让 GRIN、CACNA、KCNT 算家族，而把 ANO、SCN、COL、SLC 排除在外。盲测要检查：① 有没有因为阈值太松，把同家族别的基因的报告当成本病人的先例（例如 SCN2A 病人收到 SCN1A 的报告——SCN 只有 3 个字母，现在不会，但类似 CACNA1A / CACNA1C 这类会）；② 有没有因为阈值太紧而漏掉真正的家族试验。
- **基因符号与病因名词之间允许 3 个小写限定词**：同样是为通过上面那个用例放宽的，检查有没有把不相干的从句连起来。
- 每次盲测记录各步篇数（`offlabel_searches.*.steps`），与验收病例比较。


## 盲测重点检查项：3e 的排序权重（2026-11-06 记录）

3e 的候选排序（`repurposing.rank_key`）：有无实验证据 → 靶点层级（亚基 / 复合体 / 家族）→ 到达路径（同靶点 / 同通路）→ 物种（动物优于细胞，仅作并列时的次序）→ 临床阶段。上限 10 条，其中无实验证据的最多 3 条。
这组权重和两个上限都是对着 GRIN2B 这个已知用例定的（方向过滤后只剩 3 条候选，全是家族层级、全无实验证据）。盲测要检查：① 某个基因候选很多时，前 10 条是否仍是证据最强的；② "无实验证据最多 3 条"会不会把唯一有实验证据的候选挤掉（现在的实现是先按完整度排序再取，不应发生，但要验证）；③ 家族层级降权后，是否出现"整节只剩家族层级候选"的情况——若是，结论句要让读者看出证据底子薄。

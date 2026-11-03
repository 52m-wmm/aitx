# 第 1 步：变异解析（Variant Profile）

> 状态：**step1.1 已验收**（2026-11-03，tag `step1.1-accepted`：自检 6 独立重新翻译）。
> 当前输出 schema `variant-profile-v1.2`：v1.1 加自检 6；之后为查看页面补充长度拆分、外显子布局和 AlphaFold 结构事实（见文末"版本记录"）。

## 目的

把病例里的每个变异，翻译成后续步骤能直接使用的结构化事实。
这一步**不调用 LLM**，全部是确定性计算，结果可复现、可校验。

## 输入

病例 JSON（与比赛输入格式一致）：

```json
{"id": "AITX-40001",
 "patient": {"genotype": [{"gene": "ACTL6B", "transcript": "NM_016188.5",
   "variant_cdna": "c.1099dup", "variant_protein": "p.(Gln367ProfsTer48)",
   "zygosity": "homozygous"}],
  "clinical_context": "..."}}
```

## 数据源

- NCBI RefSeq 转录本记录（GenBank 格式，按输入里的转录本版本号精确获取）。
  一份记录里就包含：外显子边界、编码区（CDS）位置、mRNA 序列、蛋白序列。所有检查和推算都基于它。
- UniProt REST（按 RefSeq 蛋白编号查条目和对应的异构体）+ AlphaFold DB API 与 PDB 文件（预测结构）。
  只用于 `structure` 字段的背景事实，**不参与任何自检**；取不到时记录原因，不让第 1 步失败。
  结构文件缓存在 `.cache/alphafold/`，记录来源 URL、模型版本、访问时间和 sha256。
  离线测试设置 `AITX_SKIP_STRUCTURE=1` 跳过。

## 输出：VariantProfile（每个变异一个）

| 字段 | 含义 |
| --- | --- |
| `variant_class` | frameshift / nonsense / missense / start_lost / inframe_deletion / inframe_insertion / synonymous / splice / unknown |
| `protein_length` | 正常蛋白长度（氨基酸数） |
| `first_affected_aa` | 第一个受影响的氨基酸位置 |
| `ptc_aa_position` | 提前终止密码子的位置（仅移码、无义变异） |
| `exon` | 变异所在外显子：编号、总数、长度、编码部分占全部编码序列的比例 |
| `nmd` | NMD 预测：likely_triggers / likely_escapes / uncertain / not_applicable，附理由 |
| `mechanism_hypothesis` | 初步机制假设（LOF 等）与置信度，**仅供后续步骤参考，不是结论** |
| `allelic_state` | 纯合 / 杂合 / 半合子 → 等位基因层面的提示 |
| `checks` | 校验结果：参考碱基、参考氨基酸、密码子换算、c./p. 类型是否一致，以及自检 6（独立重新翻译） |
| `retranslation` | 自检 6 的独立计算结果：起始密码子、首个改变的氨基酸（位置、原来、变成）、实际终止位置、新蛋白长度与序列、缺失/插入的残基、变异附近 8 个密码子的正常/变异对照（`codon_window`），以及与输入 p. 写法的比对 `comparison` = {what, stated, computed, agree} |
| `normal_residues_retained` | 变化之前保留的正常氨基酸个数（截短后"正常部分"） |
| `frameshift_tail_aa` | 移码：变化之后、终止之前的乱码氨基酸个数 |
| `transcript_layout` | 按真实长度画外显子图用：外显子 mRNA 坐标、CDS、变异与新终止的 mRNA 位置、每个外显子连接点距新终止多少 nt（>50 nt 标出） |
| `structure` | AlphaFold 结构事实，见下节 |
| `evidence` | 数据来源 URL 与访问时间 |

## 自检 6：独立重新翻译（schema variant-profile-v1.1，step1.1）

不读 p. 写法，按 c. 写法直接修改 NCBI mRNA 序列，从起始密码子翻译到第一个终止密码子，再与正常蛋白比对
（最长公共前缀 + 最长公共后缀，中间剩下的就是改变；先取前缀使有歧义的缺失/插入落在最靠 3' 的位置，与 HGVS 一致）。
然后与输入的 p. 写法比对，不一致判 fail：

| 类型 | 比对内容 | fail 条件 | warn 条件 |
| --- | --- | --- | --- |
| 移码 | 终止位置（Ter 计数和绝对残基号） | 终止位置不同；p. 写 Ter? 而实际有终止，或反之 | 终止一致但首个新氨基酸或其位置不同 |
| 无义 | 终止位置 | 不同 | — |
| 错义 | 位置和新氨基酸，且只改变 1 个残基 | 不同 | — |
| 框内缺失 / 重复 / 插入 / delins | 缺失区间、插入的残基 | 不同 | — |
| 起始密码子丢失 | 起始密码子不再是 ATG | 不是 | 新密码子编码的氨基酸与 p. 写法不同 |
| 同义 | 蛋白不变 | 有变化 | — |
| 内含子 / 超出转录本 | 无法计算 | — | 一律 warn |

另外：用记录里的 mRNA 和 CDS 位置翻译出的正常蛋白必须与记录的 /translation 完全相同，否则 fail（说明坐标解析有问题，无法再核对）。
验收脚本还做反向验证：把每个变异的 p. 写法故意改错（终止 +1、换氨基酸、区间平移 1 位等），自检 6 必须判 fail。

## 结构事实 `structure`（AlphaFold，v1.2）

| 字段 | 含义 |
| --- | --- |
| `status` | ok / residue_not_in_model（模型是别的异构体且变异位置不在共同区段）/ unavailable（如 AlphaFold 无此蛋白）/ skipped |
| `source` | UniProt 编号与 RefSeq 对应的异构体、AlphaFold 条目和异构体、模型版本与日期、PDB URL、访问时间、本地文件、sha256、全蛋白平均 pLDDT |
| `mapping` | RefSeq 位置 → 模型位置。序列相同直接对应；不同异构体按相同序列区段映射，记录区段和到区段边缘的距离 |
| `plddt` | 变异位置的 AlphaFold 预测可信度（0–100）；< 70 为 `reliable: false`（该区域结构预测不可靠） |
| `rsa` | 相对溶剂可及性：Shrake–Rupley SASA（探针 1.4 Å，Bondi 半径，每原子 480 点，重原子，整个模型）÷ Tien et al. 2013 理论最大值；< 0.20 为 buried，否则 exposed；距阈值 0.05 内标 `borderline`；所在位置 pLDDT < 70 时 `reliable: false` |
| `neighbours_8A` | 任一重原子在 8 Å 内的残基（模型编号、氨基酸、最近距离） |
| `lost_model_range` | 截短变异丢失的部分（模型编号） |

说明：RSA 在单链模型上计算，不含伙伴蛋白、膜或配体的接触；低可信度区域在模型里常是伸展的链，读数会偏"暴露"。
这些只是背景事实，供后续步骤判断错义变异机制（例如埋在内部、可信度高的位置更可能影响折叠），本步骤不据此下结论。
实现已与 Biopython ShrakeRupley 交叉核对（AITX-40002/3/4 的 SASA 相差 6% 以内，分类相同）。

## 节点验收标准

1. 所有输入变异的 `checks` 没有 fail，自检 6 必须为 pass，反向验证全部判 fail；出现 fail 说明输入写法或转录本版本有问题，必须停下排查。
2. 官网示例中有标准答案的项目，计算结果必须一致：
   - KMT2B `c.8079delC`：位于末位外显子，**不会**触发 NMD（官方答案 No）
   - AGXT 蛋白长度 392（UniProt P21549）
   - CFTR `p.Phe508del`：框内缺失，不适用 NMD
3. 输出能被第 2 步直接读取，不需要人工修改。

## NMD 规则（规则版本 nmd-v1）

- 提前终止位于最后一个外显子 → 逃逸
- 移码越过正常终止密码子（新终止落在 3'UTR，蛋白变长）：同样按新终止的位置判断；`nmd.protein_extended_by_aa` 记录延长的氨基酸数，`truncated_protein_length` 置空
- 新终止超出转录本记录末端 → 不确定（没有终止密码子会走 non-stop decay，而不是 NMD）
- 位于最后一个外显子连接点上游 50 nt 以内 → 逃逸
- 位于编码区前 150 nt 以内 → 不确定（可能从下游重新起始翻译）
- 所在外显子长度超过 400 nt → 不确定
- 其余 → 很可能触发 NMD
- 距离 50 nt 阈值 ±6 nt 以内标记为临界

## 版本记录

| 版本 | 日期 | 内容 |
| --- | --- | --- |
| v1 | 2026-10-28 | 初版验收（当时未打标签） |
| v1.1 | 2026-11-03 | 自检 6：独立重新翻译 + 反向验证；15 个变异全部一致（tag `step1.1-accepted`） |
| v1.2 | 2026-11-03 | 只加字段、不改判断：`normal_residues_retained`、`frameshift_tail_aa`、`transcript_layout`、`codon_window.changed`、`structure`；Step 2 结果不受影响 |

练习病例集：PRAC-SLC35A2 已按官网拆成 PRAC-SLC35A2-ex7 / -ex8（2026-11-03），联网验收现为 16 个变异（4 评测 + 12 练习）。


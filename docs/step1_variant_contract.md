# 第 1 步：变异解析（Variant Profile）

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

NCBI RefSeq 转录本记录（GenBank 格式，按输入里的转录本版本号精确获取）。
一份记录里就包含：外显子边界、编码区（CDS）位置、mRNA 序列、蛋白序列。

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
| `checks` | 校验结果：参考碱基、参考氨基酸、密码子换算是否一致 |
| `evidence` | 数据来源 URL 与访问时间 |

## 节点验收标准

1. 所有输入变异的 `checks` 全部为 pass；出现 fail 说明输入写法或转录本版本有问题，必须停下排查。
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

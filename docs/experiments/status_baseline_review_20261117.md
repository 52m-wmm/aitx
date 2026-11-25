# 状态基线首次审阅记录（2026-11-17，待用户审核）

本轮只建立工具、只读历史基线和报告契约，不改临床判定，不升级 current。账本自身的 reason 不等于合理解释或用户批准。
历史来源为真实 `.cache/snapshots/step3a.2-accepted/`，提交 `652f6c8`，manifest 逐病例 SHA-256 已核对。覆盖 11 个现有练习病例；4 个 RETEST 当时尚未存在。11 例 input_fingerprint 均与当前一致，不能将差异归因于病人输入改变。
历史 409 个行动×分支项目，当前 790 个。工具输出：29 个状态变化、61 个原因/证据等细节变化、231 个新增、7 个删除，另有 157 个属于缺历史病例基线的项目。完整输出位于 `out/status_diff/initial-20261117/{snapshot.json,diff.json,diff.md}`。

## 29 项直接匹配的状态变化

其中 11 项降为 not_applicable：KMT2B 6 项，CFTR 5 项。单独 DBS 的历史状态是 conditional，GPi-DBS 和 subthalamic DBS 为 applicable。所有变化尚未批准升级。

| Case ID | Action | Branch | 旧 → 新 | 已定位原因与调查结论 |
| --- | --- | --- | --- | --- |
| PRAC-AGXT-c33dup | high oral fluid intake | MONDO:0009823 | conditional → applicable | 移除 Prevent crystal injury to kidneys 这一预防目的条件；Supportive Care 表第 1 行有明确原文，符合已批准目的规则。 |
| PRAC-AGXT-c508GA | high oral fluid intake | MONDO:0009823 | conditional → applicable | 移除 Prevent crystal injury to kidneys 这一预防目的条件；Supportive Care 表第 1 行有明确原文，符合已批准目的规则。 |
| PRAC-CFTR-F508del | Paxlovid | MONDO:0009061 | applicable → conditional | 说明书涉及 lumacaftor/ivacaftor 合用，病例未给当前用药，保守 conditional 有依据；目前记录为 source scope 的具体类型仍待审核。 |
| PRAC-CFTR-F508del | Dehydration | MONDO:0009061 | applicable → conditional | 同病 GeneReviews 管理/避免事项因 subject 分歧降为未知；已追到缓存投票，不能仅因短句未重复病名就认定不适用。潜在来源核查过度降级，待审核。 |
| PRAC-CFTR-F508del | Exposure to respiratory infections | MONDO:0009061 | applicable → conditional | 同病 GeneReviews 管理/避免事项因 subject 分歧降为未知；已追到缓存投票，不能仅因短句未重复病名就认定不适用。潜在来源核查过度降级，待审核。 |
| PRAC-CFTR-F508del | Fat-soluble vitamin supplements | MONDO:0009061 | applicable → not_applicable | 来源只限新生儿，15 岁明确不符。维生素/营养/胰酶另有一般条目仍 applicable，contact precautions 另有一般条目 conditional，不能统一回退为 applicable。 |
| PRAC-CFTR-F508del | Nutrient-dense food & supplements | MONDO:0009061 | applicable → not_applicable | 来源只限新生儿，15 岁明确不符。维生素/营养/胰酶另有一般条目仍 applicable，contact precautions 另有一般条目 conditional，不能统一回退为 applicable。 |
| PRAC-CFTR-F508del | Pancreatic enzyme replacement therapy | MONDO:0009061 | applicable → not_applicable | 来源只限新生儿，15 岁明确不符。维生素/营养/胰酶另有一般条目仍 applicable，contact precautions 另有一般条目 conditional，不能统一回退为 applicable。 |
| PRAC-CFTR-F508del | contact precautions | MONDO:0009061 | conditional → not_applicable | 来源只限新生儿，15 岁明确不符。维生素/营养/胰酶另有一般条目仍 applicable，contact precautions 另有一般条目 conditional，不能统一回退为 applicable。 |
| PRAC-CFTR-F508del | Postural drainage & percussion | MONDO:0009061 | conditional → not_applicable | 来源只限新生儿，15 岁明确不符。维生素/营养/胰酶另有一般条目仍 applicable，contact precautions 另有一般条目 conditional，不能统一回退为 applicable。 |
| PRAC-COL1A1 | secondhand smoke | MONDO:0030854 | applicable → conditional | 同病 GeneReviews 管理/避免事项因 subject 分歧降为未知；已追到缓存投票，不能仅因短句未重复病名就认定不适用。潜在来源核查过度降级，待审核。 |
| PRAC-COL1A1 | bone morphogenetic protein-2 | MONDO:0030854 | applicable → conditional | 原文为不同 OI 类型混合队列；缓存 evidence 全票 other_gene_or_subtype_patients 且 subject 分歧，保留来源范围未知，不等于病人已知不适用。 |
| PRAC-COL1A1 | braces | MONDO:0007522 | applicable → conditional | 严格 HPO 匹配后，病例未明确给出 joint instability / small joint instability，不能将相关关节表现默认等价；保留未知有依据。 |
| PRAC-COL1A1 | ring splints | MONDO:0007522 | applicable → conditional | 严格 HPO 匹配后，病例未明确给出 joint instability / small joint instability，不能将相关关节表现默认等价；保留未知有依据。 |
| PRAC-COL1A1 | wrist or wrist & thumb braces | MONDO:0007522 | applicable → conditional | 严格 HPO 匹配后，病例未明确给出 joint instability / small joint instability，不能将相关关节表现默认等价；保留未知有依据。 |
| PRAC-COL1A1 | physiotherapist | MONDO:0007522 | conditional → applicable | 另有普通物理/作业治疗来源，移除 prevent contractures... 目的后满足，孕期部分保留附注；reason 只指孕期章节有误导，应后续修来源理由。 |
| PRAC-COL1A1 | physiotherapist | MONDO:0030854 | conditional → applicable | 另有普通物理/作业治疗来源，移除 prevent contractures... 目的后满足，孕期部分保留附注；reason 只指孕期章节有误导，应后续修来源理由。 |
| PRAC-KMT2B | benzodiazepines | MONDO:0015004 | applicable → conditional | 病人已有 generalized dystonia 且 HPO 已满足；缓存 meets:r1 分歧却转成程度未达到，原文未要求新的程度阈值。潜在核查误伤，未改判。 |
| PRAC-KMT2B | trihexiphenidyl | MONDO:0015004 | applicable → conditional | 病人已有 generalized dystonia 且 HPO 已满足；缓存 meets:r1 分歧却转成程度未达到，原文未要求新的程度阈值。潜在核查误伤，未改判。 |
| PRAC-KMT2B | tetrabenazine | MONDO:0015004 | applicable → conditional | 病人已有 generalized dystonia 且 HPO 已满足；缓存 meets:r1 分歧却转成程度未达到，原文未要求新的程度阈值。潜在核查误伤，未改判。 |
| PRAC-KMT2B | trihexyphenidyl | MONDO:0015004 | conditional → not_applicable | R15 把 describes_use 写成推荐条件 fail，没有病人事实不符；违反用户新规则，是待修回归。 |
| PRAC-KMT2B | levodopa/carbidopa | MONDO:0015004 | conditional → not_applicable | R15 把 describes_use 写成推荐条件 fail，没有病人事实不符；违反用户新规则，是待修回归。 |
| PRAC-KMT2B | clonazepam | MONDO:0015004 | conditional → not_applicable | R15 把 describes_use 写成推荐条件 fail，没有病人事实不符；违反用户新规则，是待修回归。 |
| PRAC-KMT2B | levodopa | MONDO:0015004 | applicable → conditional | 病人已有 generalized dystonia 且 HPO 已满足；缓存 meets:r1 分歧却转成程度未达到，原文未要求新的程度阈值。潜在核查误伤，未改判。 |
| PRAC-KMT2B | Bilateral globus pallidus pars interna deep brain stimulation (GPi-DBS) | MONDO:0015004 | applicable → not_applicable | R15 把 describes_use 写成推荐条件 fail，没有病人事实不符；违反用户新规则，是待修回归。 |
| PRAC-KMT2B | Deep brain stimulation (DBS) | MONDO:0015004 | conditional → not_applicable | R15 把 describes_use 写成推荐条件 fail，没有病人事实不符；违反用户新规则，是待修回归。 |
| PRAC-KMT2B | subthalamic nucleus DBS | MONDO:0015004 | applicable → not_applicable | R15 把 describes_use 写成推荐条件 fail，没有病人事实不符；违反用户新规则，是待修回归。 |
| PRAC-OTC | Haloperidol | MONDO:0010703 | applicable → conditional | 同病 GeneReviews 管理/避免事项因 subject 分歧降为未知；已追到缓存投票，不能仅因短句未重复病名就认定不适用。潜在来源核查过度降级，待审核。 |
| PRAC-OTC | nitrogen-scavenging drugs | MONDO:0010703 | conditional → applicable | 移除 prevention of hyperammonemic episodes 这一预防目的条件，符合已批准目的规则。 |

## 结构性变化与未解释项目

- 84 个 bespoke、34 个 off-label、6 个 repurposing 新增项目发生在历史验收后新增步骤；其他新增条目也全部列出，不能因“后来新增”就自动认可判定。
- hypertonic saline 的旧键 drug:name:hypertonic saline 变为 drug:rxcui:9863，前后均 conditional，属规范化造成删除+新增；工具不靠模糊名称匹配隐去。
- NCT07414810、NCT07851831 现在位于 CFTR over_cap；NCT07653633 在两个 COL1A1 分支转入 over_cap，但仍在另一分支被逐条分析。这是分析范围变化，不是病人不适用。
- NCT01822834 可在旧 CF 缩写查询缓存找到，该查询已取消；当前全称/基因缓存不再返回。NCT07513051 也未在当前缓存返回，现有缓存不能完全解释，作为未解释的潜在召回差异保留，不冒称已结束或不相关。
- 61 项细节变化均涉及 Evidence ID，17 项同时改变 reason；旧/新 ID 全部保留，尚未逐条批准。
- 全部 485 个 diff 项仍未获升级批准；此记录只追因和标记，不替用户批准，不隐藏未解释项目。

## ANO10：只汇报，不改判

两项都来自 GeneReviews NBK1138 的混合病因 ataxia 管理表。riluzole 的 evidence 三票均为 other_gene_or_subtype_patients，代码加 source scope unknown 行，故 conditional；transcranial magnetic stimulation 的同一问题三票均为 this_disease_patients，Ataxia 条件已满足，故 applicable。
差异来自上下文核查对相近表述分类不一致，代码没有给这两种治疗设置不同的混合病因规则。本轮不改二者、不重问模型。

## 当前状态

current 与 historical 的 snapshot.json 字节相同，approvals.md 只有初始化说明，没有升级记录。用户审核本清单与完整 diff 后，才能决定哪些条目升级。

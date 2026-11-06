# Step 4 契约：待办（契约正文待写）

> 本文件收集写 Step 4 契约时必须纳入的事项。

## 支持治疗：L3 检索无结果时的报告写法（2026-11-05 记录）

- 某分支走到 L3、检索了文献但没有发现明确推荐时（账本 `supportive_tiers[分支].literature` 有检索记录，且没有 literature 层行动），
  报告的 Supportive Management 节要写明："已检索文献（检索式、日期、篇数），未发现明确的管理推荐"，
  并指向 Tier 2 的相关条目（例如 SLC35A2-CDG 的 D-半乳糖在 Off-label / Expanded-Access 节）。
- 如果随后落到 L4，节首仍按兜底链契约注明 "No disease-specific management recommendations were found; the following is symptomatic management."
- 不能把"没找到推荐"写成"不需要管理"。

## 3b：有条件试验按未知项数排序（2026-11-04 记录）

- Clinical Trial Eligibility 节中，"有条件适用"的试验按未知项数从少到多排序（审阅意见：Step 4 处理，3b 不改代码）。

## 3c：疗效方向与只有阴性报告的药物（2026-11-05 记录）

- 3c 行动带药物层面的疗效方向（阳性 / 阴性 / 结果不一致 / 未报告），以及逐篇先例的设计、病例数、疗效方向。
- 报告里要决定：只有阴性报告的药物（结论"已有报告无效，不推荐"）放在 Off-label 节的什么位置、怎么排序，是否同时在 Contraindications & Precautions 提示；结果不一致的如何并列写出阴性与阳性原文。
- 膳食补充剂类须带"非 FDA 批准药品，产品质量和剂量缺乏监管"。
- 同一药物同时在 3b 和 3c 时，两边互相注明"见对方章节"，不重复写内容。

## 3d 的排序字段（2026-11-05 决定）

"Outcome Measures & Ranking" 小节归 Step 4。3d 不做排序，只按分支 × 手段产出四个字段供 Step 4 使用：
- `classification`：三种 ASO 手段用 N1C 五级；其余手段用三档（理论上可行 / 不适用 / 无法评估）；
- `premises_complete`：该手段的前提是否齐全（有没有"无法评估"的前提）；
- `human_precedent`：有无人体先例（有则附 PMID）；
- `approved_or_in_trial`：该手段是否已有获批产品（3a）或在试产品（3b），附交叉引用。

Step 4 排序时要同时看 3c（老药新用）、3d（定制疗法）、3e（候选药）三节，所以排序规则不能放在任何一个子节点里。

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

## 同类多药都"适用"时的呈现（2026-11-09，盲测第一轮发现）

DDC 病例的已有靶向治疗节写出 11 条，其中司来吉兰、普拉克索等多个同类药（多巴胺激动剂、MAO-B 抑制剂）都判为"适用"。**报告必须写成可选方案（择一或按序试用），不能排成"全部使用"的清单**——后者在临床上是错的，而且会被评审当成优先级与校准不及格。
需要的信息 Step 3 已经有：同一章节内的行动、各自的来源小节、强度。Step 4 要决定分组依据（按药理类别还是按来源小节的并列关系）和措辞模板。

## 孕期专属证据的呈现（2026-11-09，同上）

3a 会把孕期小节的原文作为第二条引文挂在一般行动下（DDC 的司来吉兰、普拉克索引用了 "low dosages ... during pregnancy ... good safety profile"），账本里有 `pregnancy_notes` 标记但没有限定范围。**Step 4 打印引文时必须按 `pregnancy_notes` 把这类句子只放进孕期相关段落**，否则对非孕期患者就是误导。

## 已有靶向节为"无"时的交叉说明（2026-11-09，盲测第一轮发现）

KCNT1 病例的"已有靶向治疗"节写 `None found`，而支持治疗节里有奎尼丁——它临床上是 KNa1.1 通道阻滞剂、针对该基因的功能获得机制，只是 GeneReviews 章节没有 `Targeted Therapies` 小节、也没写出"作用于通道"这句话，所以按 3a 的老版章节规则归了支持治疗（规则 (ii) 前提不成立，详见 `out/blind/20261108/found_during_freeze.md` 第 8 节）。

**Step 4 要求**：当"已有靶向治疗"节为空、而支持治疗节里存在针对该分支分子机制的药物时，靶向节**写一句交叉说明**（如"没有获批的靶向疗法；支持治疗节中的奎尼丁在文献中按 KCNT1 通道机制使用，但 GeneReviews 未将其列为靶向治疗"），避免评审看到"靶向=无"就认为系统漏了。
判断依据不能靠 LLM 常识：用 3d 已经取到的疾病机制 + 该药在 3c/文献里的方向记录。

## 指向外部清单的禁忌条目（2026-11-11，盲测批次 2 发现）

GeneReviews 有时只给一个外部清单而不点名药物（MPZ / CMT 总论："Medications that are toxic or potentially toxic to persons with CMT … See the Charcot-Marie-Tooth Association website (pdf) for an up-to-date list."）。3a 把它记成一条禁忌行动"toxic or potentially toxic medications"。**Step 4 呈现时写成可操作的形式："用药前对照 CMT 协会的神经毒性药物清单"**，并附清单出处，而不是只写一个泛称。

## 写明来源更新日期（2026-11-11，盲测批次 3 发现）

SNRNP200 的 RP 总论（NBK1417）说 Argus II 视网膜假体"已获 FDA 批准、在临床使用"，但该器械约 2019–2020 年已停产（审阅人核实）。报告逐字引用了过时的来源。**Step 4 每条引用都要写明来源的最后更新日期**（GeneReviews 章节的 "Last Update"、说明书版本日期、试验登记的最后更新），**器械 / 产品类条目尤其要写**，并在来源早于一定年限时提示"可能已过时，请核实是否仍在供应"。

## 状态类标签写成具体动作（2026-11-11，盲测批次 4 发现）

RRM2B 的禁忌条目标签是 "catabolism"，原文是 "Catabolism should be prevented by minimizing preoperative fasting and administering intravenous glucose perioperatively during prolonged anesthesia"。只写 "catabolism" 看不出要做什么。**Step 4 呈现时把这类"要避免的状态"写成具体动作**：缩短术前禁食；长时间麻醉时围手术期静脉给葡萄糖；条件写在动作后面。

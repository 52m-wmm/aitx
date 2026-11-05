# 第 3c 步：超说明书 / 扩展使用（Off-label or Expanded-Access Therapies）

> 状态：**草案第 1 版，待审**（2026-11-05）。只有契约，没有代码；确认后再实现。
> 已并入 `docs/step3c_contract_todo.md` 的两条待办（D-半乳糖用例 → 验收；不沿用 L3 文献类型过滤 → 来源）。

## 目的

报告 Tier 2 的 "Off-label or Expanded-Access Therapies" 一节：**有人类用药先例、但没有获批用于本病**的疗法。
写错比不写更糟：这里每一条都要让读者看到"谁、多少人、什么设计、原文怎么说"，不能把个案写成疗效。

## 章节边界（同一药物只放一个章节，用 3.0 的行动键去重）

| 情况 | 章节 |
| --- | --- |
| 已获批用于本病（FDA 说明书适应证点名本病，或 3a 已收录） | 3a（Existing Targeted / Supportive） |
| 有正在招募或尚未开始招募的临床试验（3b 已收录该药 + 本病） | 3b |
| 有本病 / 本基因患者的用药先例，未获批用于本病 | **3c** |
| 只有机制依据（体外、动物、其他疾病），没有本病 / 本基因的人类先例 | 3e |

- 去重：3c 生成候选后，代码按行动键对照 3a、3b 的行动记录，已在前面章节的不再进 3c，并记录"已在 3a/3b"。
- 3c 内部同一药物多篇先例合并为一条行动，证据逐篇列出。

## "人类先例"的定义（代码判断，LLM 不判断）

1. **至少一名本病（或本基因）患者用过该药**，出处是可解析的 PMID（E-utilities esummary 核对）。
2. **同一疾病或同一基因**：引用句（或同一段）里要同时出现药名和本病名（含同义词，`label_names` 规则）或基因符号。
   机制相似的其他疾病不算，归 3e。
3. **病例报告在 3c 算有效先例**（与 L3 不同）。
4. **已撤稿的文献不算**：PubMed Publication Type 含 "Retracted Publication"，或有撤稿声明（`CommentsCorrections RefType="RetractionIn"`）的一律排除，记入阴性证据。
5. **只写了"可能有益 / 值得尝试"、没有实际用药的文献不算先例**（如 PMID 25182700："SCAR10 patients may benefit from CoQ10 supplementation"）。
6. **证据强度由代码按 PubMed 字段判断并记录**：
   - 设计：病例报告（Case Reports）/ 病例系列或观察性（Observational Study、多例描述）/ 开放标签或单臂（Clinical Trial、Clinical Trial Phase I–II，非随机）/ 对照研究（Randomized Controlled Trial、Controlled Clinical Trial）。
   - 病例数：LLM 逐字摘出报告病例数的句子，代码核对数字在引用里；本病（本基因）病例数与总数分开记（如 "24 例 GRIN 变异，其中 GRIN2B 12 例"）。
   - 无法判断设计或病例数时写"未说明"，不推断。

## 来源

1. **PubMed**（摘要 + PMC 开放获取全文），复用 `aitx/evidence/fallback.py` 的检索、摘要、开放获取判定和缓存。
   - 检索式：基因符号或病名（`label_names`）AND（treatment / therapy / supplementation / off-label / compassionate / case）等治疗词。
   - **不沿用 L3 的文献类型过滤**：临床研究在 PubMed 上常只标 "Journal Article"（PMID 32103184 就是如此）。
   - 每个分支取前 N 篇（拟 20），按相关度。
2. **ClinicalTrials.gov Expanded Access 记录**（`studyType=EXPANDED_ACCESS`，按病名与基因检索，复用 3b 的检索和相关性过滤）：
   状态为 AVAILABLE 的记录本身就是一条扩展使用途径；NO_LONGER_AVAILABLE / TEMPORARILY_NOT_AVAILABLE 记入阴性证据。
3. **药物在美国的批准状态**（任何适应证）从 FDA 说明书（openFDA）判断，复用 3a 的说明书检索：
   - 已获批（任何适应证）→ **超说明书用药**，记录说明书 set id、版本、批准的适应证；
   - 未获批 → 只有存在扩展使用途径（ClinicalTrials.gov Expanded Access 记录，或文献写明的同情用药 / 扩展使用项目）时才列，否则不列，记阴性证据；
   - 膳食补充剂 / 食品成分（D-半乳糖、L-丝氨酸、辅酶 Q10）的处理见待定问题 1。

## 核验

- LLM 只摘逐字引用：用药句、病例数句、结果句、剂量句、条件句。代码核对：
  - 引用逐字出现在已获取的文本（摘要或开放获取全文）里；
  - PMID 可解析，且不是撤稿文献；
  - 用药引用里同时出现药名和本病（或本基因）——不满足即不算先例；
  - 数字（病例数、剂量）在引用里。
- **疗效结论**走 3.0 支持度核查，结论句由代码按模板生成，**强度不能超过原文**：
  - 原文是 "shows promise"、"may"、"associated with" → 结论只能写"报告了改善 / 提示可能有益"，不能写"有效"；
  - 原文报告无效（如 PMID 32418144 "Stiripentol fails to lower plasma oxalate"）→ 必须原样写出，并与有效报告并列；
  - 摘要未报告结果、全文又不可获取 → 写"有用药记录，结果在可获取的文本中未报告"。
- **剂量**只作为"文献报告的用法"逐字引用（如 "oral l-serine (500 mg/kg/day in 4 doses)"），不写成推荐剂量，不换算。

## 对照病人

- 先例文献里的适用条件（年龄、变异类型、功能效应、肾功能等）由 LLM 逐字摘出，代码比较，复用 3a / 3b 的 `evaluate` 和"满足其一"、放宽从句、合子状态等已有规则；禁忌复用 3a 的说明书禁忌与注意事项（超说明书药物的说明书禁忌照样适用）。
- **变异功能效应**（功能缺失 / 功能获得）是新的条件类型：病例和 Step 1 都没有功能实验结果时一律 unknown（有条件）。
  Step 1 的 NMD 预测只作为背景写出，不据此判定功能缺失（例：GRIN2B p.Gln919Ter 位于最后一个外显子，预测逃逸 NMD，功能效应不能确定）。
- 缺信息 → 有条件，并进缺失信息表（按变量类型合并）。
- 遵守改动审批规则：**可能产生新的"不适用"的比较规则，先报再改**。

## 账本与校验

- 行动记录（`section: off_label_expanded_access`）增加：
  - `precedents`：每篇 {pmid, 设计, 本病 / 本基因病例数, 总病例数, 结果引用, 剂量引用, 是否开放获取全文, 撤稿检查结果}；
  - `regulatory`：{美国批准状态, 说明书 set id 与已批准适应证, 扩展使用途径（NCT 或文献）}；
  - `strength`：最强的一篇的设计与病例数（报告排序用）。
- 检索记录：PubMed 检索式、日期、总数、取回篇数；Expanded Access 检索；FDA 说明书检索。
- 阴性证据：没有任何先例的分支 → `searched_none`；被排除的文献逐篇写原因（撤稿 / 无实际用药 / 其他疾病 / 只有体外或动物）。
- 校验（不过则 fail）：

| 校验 | 内容 |
| --- | --- |
| 先例有效 | 每条 3c 行动至少一篇 PMID 可解析、未撤稿、引用里同时有药名和本病 / 本基因 |
| 去重 | 没有行动同时出现在 3a / 3b 与 3c |
| 强度如实 | 每篇先例有设计与病例数（或"未说明"）；结论句通过支持度核查，且不含强于原文的词 |
| 批准状态 | 每条行动有美国批准状态；未获批的有扩展使用途径记录 |
| 剂量 | 剂量只出现在逐字引用里，不出现在代码生成的结论句中 |

## 验收（只用练习病例；期望先人工核实原文，2026-11-05 已读下列摘要）

| 病例 | 期望 | 核实依据 |
| --- | --- | --- |
| PRAC-SLC35A2-ex7 / ex8 | D-半乳糖进 3c；证据强度：单臂、开放标签、10 例；结论不强于原文（"shows promise"） | PMID 32103184 摘要："Ten patients with SLC35A2-CDG were supplemented with oral D-galactose for 18 weeks…"；"Oral galactose is well tolerated and shows promise as dietary therapy." |
| PRAC-GRIN2B（p.Gln919Ter，杂合） | L-丝氨酸进 3c，**有条件**：适用于功能缺失型变异，本例功能效应未知（最后一个外显子的截短变异，预测逃逸 NMD）；证据：2A 期非随机开放标签单臂 24 例（GRIN2B 12 例），观察性 2 例 | PMID 38380699："the first non-randomized, open-label, single-arm trial (NCT04646447)…"、"Patients had GRIN2B, GRIN1 and GRIN2A variants (12, 6 and 5 cases, respectively)"；PMID 36758276（2 例，"treated experimentally… with oral l-serine (500 mg/kg/day in 4 doses)"）；随机 n-of-1 试验 PMID 41265180 摘要**尚未逐字核对**，核对后再决定是否写入 |
| PRAC-ANO10 | 辅酶 Q10 进 3c；先例：3 名同胞，不设盲用药；**结果在可获取的文本中未报告**（摘要未写，全文非开放获取） | PMID 30838263 摘要："Data also are provided on unblinded therapy with coenzyme Q10"；PMID 25182700 只写 "may benefit"，不单独算先例 |
| 反例：PRAC-GRIN2B / D-丝氨酸 | **不进 3c**：唯一的人体报告已撤稿 | PMID 28734458，PubMed 类型 "Retracted Publication"，撤稿声明 Biol Psychiatry 2018;83(8):715 |
| 反例：PRAC-GRIN2B / NMDA 受体正向变构调节剂（妥布霉素、孕烯醇酮硫酸盐等） | **不进 3c**（只有体外研究，归 3e） | PMID 32712275 摘要：在表达变异受体的体外系统中评估 |

另一个可选用例（未写入期望，供审定）：PRAC-AGXT-c33dup / 司替戊醇。有 PH1 患者用药先例且结果不一致
（PMID 32418144 同情用药无效："Stiripentol may not be useful to reduce P Ox in PH patients with advanced chronic kidney disease"），
已获 FDA 批准用于 Dravet 综合征 → 超说明书。适合检验"无效报告必须原样写出"。另两篇（34283403、36693470）的原文尚未核对。

## 费用与运行

每个分支：PubMed 检索 1 次 + 每篇文献 1 次 LLM 抽取（≤20 篇）+ 每条候选结论 1 次支持度核查。LLM 只在非高峰时段运行（`--offpeak-only`，每次调用前检查）。

## 待定问题

1. **膳食补充剂 / 食品成分**（D-半乳糖、L-丝氨酸、辅酶 Q10）：不是 FDA 批准的药品，也没有处方药说明书。
   按"未获批 → 只有存在扩展使用途径才列"的规则，它们都会被排除，与已定的 D-半乳糖用例冲突。
   建议：单列一类"可作为膳食补充剂获得"，报告注明"非 FDA 批准药品；文献中作为膳食补充使用"，并要求有可解析的先例 PMID；不作为处方药超说明书用药描述。
2. **同时有招募中试验与用药先例**（如 L-丝氨酸若有招募中的试验）：按边界放 3b。是否在 3b 条目里附上 3c 的先例证据（只作背景，不重复成行动）？建议附。
3. **变异功能效应**：Step 1 只有 NMD 预测，没有功能实验。建议一律 unknown，除非病例原文写明功能实验结果；是否同意把"功能缺失 / 功能获得"作为新的条件类型。
4. **检索篇数**：每分支取前 20 篇是否合适（L3 是 10 篇）；先例多的疾病（如 CF）可能截断，被截断的记入检索记录。
5. **司替戊醇（PH1）** 是否作为第 4 个验收用例（需先核对另两篇原文）。
6. **无效先例**：只有无效报告的药物是否仍列入 3c（建议列入并写明"报告无效"，因为它对临床决策有用；或改为只在 Contraindications & Precautions 里提示）。

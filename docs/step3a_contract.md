# 第 3a 步：已确立层（Existing Targeted Therapies / Supportive Management / Contraindications & Precautions）

> 状态：**草稿，待审**（2026-11-03）。审定后才写代码。依赖 3.0（`step3.0-accepted`）：证据账本、诊断分支、行动键（1.3）、
> 行动记录（1.4）、阴性证据（1.2）、支持度核查模块。

## 目的

为每个诊断分支找出报告 Tier 1 三个章节的行动，并逐条对照病人条件：

| 章节 | 放什么 | 不放什么 |
| --- | --- | --- |
| Existing Targeted Therapies | 已获批、或有指南支持、**针对分子缺陷或疾病机制**的疗法 | 只缓解症状的药；未获批也无指南支持的（→ 3c/3e） |
| Supportive Management | 针对症状和并发症的标准治疗（药物或操作） | **监测类建议**（模板明确排除）；针对分子缺陷的疗法 |
| Contraindications & Precautions | 因该变异或疾病而要避免或调整的药物、剂量、操作，含麻醉风险和相关药物相互作用 | 与该病无关的一般禁忌 |

## 数据源

| 来源 | 用途 | 访问方式 |
| --- | --- | --- |
| GeneReviews（本地存档，3.0 已下载） | Management 下各小节：Targeted Therapies、Treatment of Manifestations、Prevention of Primary Manifestations / Secondary Complications、**Agents/Circumstances to Avoid**、Pregnancy Management；**不用 Surveillance** | `aitx/evidence/genereviews.py`，逐字摘录，附版权声明和章节链接 |
| FDA 药品说明书（openFDA drug label API） | 获批适应症、适用年龄、变异要求、禁忌、儿科用药、特殊人群 | `api.fda.gov/drug/label.json`；按适应症文本检索（分支疾病名）和按药名检索；链接给 DailyMed（SPL set id） |
| ClinPGx / PharmGKB（CPIC、DPWG 指南注释） | 与病人基因相关的药物基因组学注意事项 | 按基因查询；没有则记阴性证据 |

全部经 `aitx.http`（缓存、记录访问时间），不过期，提交时冻结。只用 FDA 说明书（美国）；欧洲等地的批准不在范围内，
需要时由 3c（超说明书）以文献先例的形式处理（已知局限 1）。

## 流程（对每个分支、每个章节）

1. **找候选（召回）**
   - GeneReviews：取分支疾病对应章节的上述小节；LLM 从**代码给出的原文**中列出疗法和要避免的药物或操作，每项附逐字引用和小节名。
   - FDA 说明书：用分支疾病名的关键词检索适应症文本；对 GeneReviews 中出现的每个药名再检索说明书。
   - ClinPGx：按基因查指南注释。
2. **标准化**：每个行动用 3.0 的行动键（药物 RxNorm → openFDA → ChEMBL → 兜底名；操作类用受控类型）。
3. **放进哪个章节（代码规则，不由 LLM 决定）**
   - 说明书适应症**点名了该分支疾病**（或包含它的疾病类别，如 "urea cycle disorders"），或出现在 GeneReviews 的 "Targeted Therapies" 小节 → Existing Targeted。
   - 出现在 GeneReviews "Treatment of Manifestations" / "Prevention of …" 小节、且说明书适应症未点名该病 → Supportive Management。
   - 出现在 GeneReviews "Agents/Circumstances to Avoid"，或说明书禁忌 / 警告中点名该病，或 ClinPGx 指南针对该基因 → Contraindications & Precautions。
   - 同一行动只放一个章节（3.0 校验）：前两条同时成立时放 Existing Targeted。
   - 出自 "Surveillance" 小节、或 LLM 标为监测的条目一律不收。
4. **逐条核对要求（行动记录 1.4）**
   - LLM 只从说明书或 GeneReviews 原文中**逐字摘出要求句**（年龄、体重、肾功能、基因型 / 变异、合并症等），并标出它对应的病人事实字段。
   - **比较由代码做**：
     - 年龄：LLM 给出 `{field: age, op, value, unit}`，代码与 Step 2 的年龄比较；
     - 变异要求：LLM 给出说明书写的变异名，代码与 Step 1 的变异比对，支持三字母、单字母、传统名称（如 F508del ↔ p.Phe508del）的换算；
     - 合子状态、性别同理；
     - 病例里没有的事实（如 eGFR、体重）→ `unknown`，登记为缺失信息，状态为 `conditional`。
   - 每个分支各自得出 `applicable / not_applicable / conditional`，附一句英文理由。
5. **查过没找到**：某分支某章节没有任何行动 → `searched_none` 行 + 阴性证据（GeneReviews 小节不存在或为空、openFDA 返回 0 条等，记录检索词、时间、返回数量）。
6. **支持度核查**：每条行动的结论句（"Lumasiran is approved for PH1 in pediatric and adult patients"）用 3.0 的支持度核查模块对照其引用；
   不完全支持的行动停在 `candidate`，不进章节，并汇报。

LLM 只做两件事：从代码给出的原文中摘出疗法 / 要求，以及给出要求对应的事实字段和比较式；**来源、编号、比较结果都由代码给出**。

## 输出

写入同一份证据账本（`out/step3/<id>.json`）：三个章节的证据条目（`sourced` / `negative`）、行动记录（1.4，按分支给状态和逐条要求）、
新增的缺失信息；三个章节的 `sections_status` 置为 `searched`。查看页面的证据树自动显示这些内容（看板页面在 Step 3 全部完成后做）。

## 校验（在 3.0 校验之外）

| 校验 | 不过则 |
| --- | --- |
| Existing Targeted 的每个行动都有说明书适应症引用，或 GeneReviews "Targeted Therapies" 小节引用 | fail |
| 年龄、变异等要求逐字来自说明书或 GeneReviews；比较结果由代码算出（与 LLM 的说法无关） | fail |
| Supportive 里没有监测类条目、没有出自 Surveillance 小节的条目 | fail |
| 每个分支的三个章节都有行动或阴性证据 | fail |
| 行动结论句通过支持度核查，否则停在 candidate | 该条不进章节 |

## 验收

**离线测试**：章节归类规则；年龄比较（含"2 岁及以上""≥9 岁"等写法与月龄换算）；变异名换算（F508del、G170R ↔ p.Gly170Arg 等）；
未知事实 → conditional + 缺失信息；监测类条目被排除；阴性证据；同一行动不跨章节。

**联网验收（`scripts/acceptance_step3a.py`）**：期望答案**必须先从说明书或 GeneReviews 原文核实**，写进验收脚本时附出处。
下表是待核实的初稿（第 1 行已按现行说明书改正，见下）：

| 病例 | 期望 | 出处（待核实） |
| --- | --- | --- |
| PRAC-AGXT-c33dup（7 岁） | Lumasiran：Existing Targeted，applicable（说明书："pediatric and adult patients"）；Nedosiran：Existing Targeted，**conditional**（说明书："children 2 years of age and older … relatively preserved kidney function, e.g., eGFR ≥30"，eGFR 未知）；Pyridoxine：不适用于该移码变异（只对特定错义基因型有效） | Oxlumo、Rivfloza 说明书（2026-11-03 实测）；GeneReviews PH1（NBK1283） |
| PRAC-AGXT-c508GA（G170R，年龄未知） | Pyridoxine：Existing Targeted，applicable（G170R 为已知敏感基因型）；Lumasiran applicable；Nedosiran conditional（年龄、eGFR 未知） | GeneReviews PH1 |
| PRAC-CFTR-F508del（15 岁，纯合 F508del） | Elexacaftor/tezacaftor/ivacaftor：Existing Targeted，applicable | Trikafta 说明书 |
| PRAC-COL1A1 | Supportive 含 ascorbic acid（维生素 C）和 desmopressin（易瘀伤） | GeneReviews 相关 EDS 章节 |
| PRAC-OTC | 氮清除剂（sodium phenylbutyrate 等）在 Existing Targeted；valproic acid 在 Contraindications | 说明书（适应症 "urea cycle disorders"）；GeneReviews UCD |
| 评测病例 | 只做人工核对，不设期望 | — |

**计划变更**：Notion 中"Nedosiran 只批准 9 岁以上，7 岁病人不适用"与现行说明书不符（现为 2 岁及以上，且要求 eGFR ≥30）。
按现行说明书，7 岁 PH1 患者的 Nedosiran 应为 conditional（eGFR 未知），不是 not_applicable。

硬性项：上表练习病例全部符合（核实后的版本）；所有账本校验通过；每个 Existing Targeted 行动有说明书或 GeneReviews 原文；
支持度核查拦下的行动全部列出供审阅。

## 已知局限（预计）

1. 只看 FDA 说明书，不含 EMA 等其他地区的批准。
2. 说明书检索靠疾病名关键词，命名差异可能漏检；用 GeneReviews 中出现的药名做第二路检索来补。
3. 病例临床描述很短，多数实验室指标（eGFR、体重）未知，很多行动会是 conditional；这是如实反映，不是缺陷。

## 待定问题

1. **章节归类规则**（流程第 3 步）是否同意："说明书适应症点名该病或其所属类别，或 GeneReviews Targeted Therapies 小节"即 Existing Targeted。
2. **指南支持**的范围：目前只把 GeneReviews 当指南来源。是否需要加专业学会指南（如 CPIC 以外的临床指南）？加的话需要指定来源。
3. ClinPGx 是否纳入 3a，还是先只做 GeneReviews + 说明书。

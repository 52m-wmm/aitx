# 第 3a 步：已确立层（Existing Targeted Therapies / Supportive Management / Contraindications & Precautions）

> 状态：**草稿第 2 版，待审**（2026-11-03）。第 1 版的 3 个待定问题已按建议决定（文末）；新增：说明书版本记录（A）、
> 老版 GeneReviews 章节的归类规则与 Therapies Under Investigation 的排除（B）；验收期望已逐条对照原文核实。审定后才写代码。依赖 3.0（`step3.0-accepted`）：证据账本、诊断分支、行动键（1.3）、
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
| GeneReviews（本地存档，3.0 已下载） | Management 下各小节：Targeted Therapies、Treatment of Manifestations、Prevention of Primary Manifestations / Secondary Complications、**Agents/Circumstances to Avoid**、Pregnancy Management；**不用 Surveillance；不用 Therapies Under Investigation（留给 3b 临床试验 / 3c 超说明书）** | `aitx/evidence/genereviews.py`，逐字摘录，附版权声明和章节链接 |
| FDA 药品说明书（openFDA drug label API） | 获批适应症、适用年龄、变异要求、禁忌、儿科用药、特殊人群 | `api.fda.gov/drug/label.json`；按适应症文本检索（分支疾病名）和按药名检索；链接给 DailyMed（SPL set id）。**每条说明书证据记录 SPL set ID、版本号（`version`）和生效日期（`effective_time`）**；报告引用说明书时注明版本日期（如 "Rivfloza label, version 4, effective 2025-03-03"） |
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
   - 说明书适应症**点名了该分支疾病**（或包含它的疾病类别，如 "urea cycle disorders"），或出现在 GeneReviews 标题为 "Targeted Therapies" / "Targeted Therapy" 的小节
     （**按小节路径的任何一级判断**：新版章节常把它放在 Treatment of Manifestations 之下，如 PH1 的 "Management / Treatment of Manifestations / Targeted Therapies"）→ Existing Targeted。
   - **老版章节（Management 下没有任何 Targeted Therapies 小节）**：出现在 "Treatment of Manifestations" / "Prevention of Primary Manifestations" 的疗法，满足以下任一项归 Existing Targeted，否则归 Supportive：
     (i) 说明书适应症点名该病或其所属类别（如 OTC 章节没有 Targeted Therapies 小节，氮清除剂 Buphenyl 的适应症点名 "ornithine transcarbamylase (OTC)" 缺乏）；
     (ii) 章节原文**写明**它作用于缺陷的基因产物或疾病机制（如"作为 AGT 的辅因子、化学伴侣"）：LLM 摘出这句机制原文，代码核对逐字，并用支持度核查判断
     "该疗法作用于 <疾病> 的分子缺陷或疾病机制"这一项；只有核查结果为 supported 才归 Existing Targeted。
   - 出现在 GeneReviews "Treatment of Manifestations" / "Prevention of …" 小节、且不满足上面任一条 → Supportive Management。
   - 出自 "Therapies Under Investigation" 小节的条目不归 3a（留给 3b / 3c）。
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
下表各项已于 2026-11-03 对照原文核实（说明书取自 openFDA，GeneReviews 取自本地存档）：

| 病例 | 期望 | 出处（已核实） |
| --- | --- | --- |
| PRAC-AGXT-c33dup（7 岁，纯合移码） | Lumasiran：Existing Targeted，**applicable** | Oxlumo 说明书 v9（2025-12-01）："indicated for the treatment of primary hyperoxaluria type 1 (PH1) … in pediatric and adult patients" |
| 同上 | Nedosiran：Existing Targeted，**conditional（eGFR 未知）** | Rivfloza 说明书 v4（2025-03-03）："children 2 years of age and older and adults with primary hyperoxaluria type 1 (PH1) and relatively preserved kidney function, e.g., eGFR ≥30 mL/min/1.73 m2" |
| 同上 | Pyridoxine：Existing Targeted，**not_applicable**（移码不是错义变异） | GeneReviews PH1（NBK1283）"Management / Treatment of Manifestations / Targeted Therapies" 表 7："Persons w/missense AGXT variants, esp homozygotes for p.Phe152Ile, p.Gly170Arg, & p.Ile244Thr" |
| PRAC-AGXT-c508GA（纯合 p.Gly170Arg，年龄未知） | **Pyridoxine：Existing Targeted，applicable**（B 条的验收用例，见下） | 同上表 7；"Genotype-Phenotype Correlations"："Individuals homozygous for three pathogenic variants (p.Phe152Ile, p.Gly170Arg, or p.Ile244Thr) …" |
| 同上 | Lumasiran applicable；Nedosiran conditional（年龄、eGFR 均未知） | 同上两份说明书 |
| PRAC-CFTR-F508del（15 岁，纯合 F508del） | Elexacaftor/tezacaftor/ivacaftor：Existing Targeted，applicable | Trikafta 说明书 v23（2026-06-22）："aged 2 years and older … at least one variant in the … CFTR gene that is either responsive based on clinical and/or in vitro data (see Table 6)"；F508del 须在表 6 中由代码匹配 |
| PRAC-COL1A1（经典型 EDS 分支） | Supportive：ascorbic acid（维生素 C）、desmopressin | GeneReviews 经典型 EDS（NBK1244）"Management / Treatment of Manifestations"："Ascorbic acid (vitamin C) may ↓ easy bruising"；"DDAVP® (desmopressin) may be useful to normalize bleeding" |
| PRAC-OTC（3 个月男婴） | Sodium phenylbutyrate：Existing Targeted（老版章节规则 (i)）；Contraindications 含 valproate、haloperidol、systemic corticosteroids | Buphenyl 说明书 v9（2024-10-30）："urea cycle disorders involving deficiencies of … ornithine transcarbamylase (OTC)"；GeneReviews OTC 缺乏症（NBK154378）"Management / Agents/Circumstances to Avoid"："Avoid the following: Valproate Haloperidol … Systemic corticosteroids" |
| 评测病例 | 只做人工核对，不设期望 | — |

**B 条（老版章节）的验收说明**：本地存档中的 PH1 章节**已有** "Targeted Therapies" 小节（在 Treatment of Manifestations 之下），
所以 AGXT c.508G>A 的吡哆醇在真实数据上走的是"按小节路径任一级判断"这条路。老版章节规则 (ii) 另用离线测试覆盖：
构造一个没有 Targeted Therapies 小节、把吡哆醇写在 Treatment of Manifestations 并附机制原句的合成章节，期望归 Existing Targeted；
去掉机制原句后期望归 Supportive。真实数据上的老版章节规则由 PRAC-OTC（规则 (i)）验收。

**计划变更**（2026-11-03 确认）：Notion 中"Nedosiran 只批准 9 岁以上，7 岁病人不适用"与现行说明书不符（现为 2 岁及以上，且要求 eGFR ≥30）。
以现行说明书为准，7 岁 PH1 患者的 Nedosiran 期望为 conditional（eGFR 未知）。

硬性项：上表练习病例全部符合（核实后的版本）；所有账本校验通过；每个 Existing Targeted 行动有说明书或 GeneReviews 原文；
支持度核查拦下的行动全部列出供审阅。

## 已知局限（预计）

1. 只看 FDA 说明书，不含 EMA 等其他地区的批准。
2. 说明书检索靠疾病名关键词，命名差异可能漏检；用 GeneReviews 中出现的药名做第二路检索来补。
3. 病例临床描述很短，多数实验室指标（eGFR、体重）未知，很多行动会是 conditional；这是如实反映，不是缺陷。

## 已定决策（2026-11-03 审阅）

1. 章节归类规则按流程第 3 步（含老版章节规则）。
2. 指南来源暂时只用 GeneReviews，以后需要再加。
3. ClinPGx 纳入，只用于 Contraindications & Precautions；查不到记阴性证据。
4. 说明书证据记录 SPL set ID、版本号、生效日期，报告注明版本日期。
5. Therapies Under Investigation 不归 3a。

## 规则变更（2026-11-04，3a 验收第二次运行后批准）

第二次运行 13 条期望成立 9 条；以下 5 处按批准实施（规则只在代码里，提示词未改，`3a-v2` 不变）。

1. **引用修复。** LLM 引用不能逐字匹配时，代码在原文里找最接近的片段，满足以下全部条件才修复：
   - 相似度 ≥0.95；
   - 药名逐字出现在片段里；
   - 数字、比较符号（≥ ≤ < > = ± %）和否定词（not、no、non、without、never、none、nor、neither、cannot、unless、except）与原文片段逐个一致，只允许字母层面的抄写差异。

   修复后：
   - 引用改为原文片段；
   - 用该片段**重新调用一次 GeneReviews 摘取提示词**提取结构化条件，不沿用抄错的那句；
   - 重新提取的任何一条要求不能在片段里逐字找到，就整条丢弃（漏掉条件会让行动看起来无条件适用）；
   - 证据标记 `quote_repaired`（含 LLM 原抄写），看板显示"引用经代码修复"。

   反例（必须拒绝）："≥ 2" 对 "≥ 12"、"indicated" 对 "not indicated"。
2. **说明书条件优先。** 现有靶向治疗里的药物有一份**按第 3 条判为靶向**的 FDA 说明书时（只有这种说明书会提取条件），由说明书的条件决定状态；GeneReviews 的条件写入 `genereviews_notes`，在看板卡片上作为备注显示，不参与判定。
3. **说明书适应证按句子判断**（替代原来的"适应证文本里出现病名"）。只看含 "indicated" 的句子，跳过使用限制和 "not indicated / not recommended"。病名须以整词出现；"<X> deficiency" 也匹配同一分句中的 "deficiency/deficiencies of … <X>"。
   - 病名是所治疗的疾病（"indicated for the treatment / management of <病名>"，中间允许 "patients with" 之类）→ 现有靶向治疗。
   - 病名只是并发症或症状的背景 → 支持治疗。判断依据：
     - 病名前、最近的 "indicated / treatment of" 之后，出现 in、secondary to、due to、caused by、associated with 等；
     - 或病名后紧跟目的从句 "to improve / reduce / relieve / prevent …"，例如 Pulmozyme："patients with cystic fibrosis to improve pulmonary function"。
   - 其他情况不使用。
   - GeneReviews 列出的药物只会被说明书**升为**现有靶向治疗，前提是说明书通用名与该药完全一致（不能是复方）；否则保留 GeneReviews 证据。
4. **用全部病名查说明书。** 适应证和禁忌检索用分支的全部病名和同义词，跳过 4 个字符以下的名称和单词缩写（如 CF、OTCD）。按通用名查说明书也扩展到支持治疗里的药物。都是普通接口调用。
5. **输出截断。** `finish_reason=length` 时只重试一次，上限提到 32768；仍然截断就报错，不再原样重试。重试结果连同实际参数缓存。

   实施中发现（同日，AGXT 两例从缓存重跑）：Rivfloza 的适应证 "indicated to lower urinary oxalate levels in children … with PH1" 按第 3 条读作支持治疗类，没有提取条件；如果仍按"有说明书证据"处理，GeneReviews 的 eGFR、年龄条件会被转成备注，nedosiran 被误判为适用。已改为只有靶向类说明书才决定条件，并补回归测试。曾试过把 "in children … with" 视为人群而非并发症背景，但会把 "lung infections in patients with CF" 误判为靶向，已撤回，没有采用。

# 第 3a 步：已确立层（Existing Targeted Therapies / Supportive Management / Contraindications & Precautions）


> 2026-11-25 当前结构接入：8000 XML估算tokens触发递归章节拆分；超大叶章节再按粗体主题或完整表格分组，分为只读上下文与可选择正文。整块含上下文最多16000估算tokens，超限报错，不切碎表格。只有结构块附加上下文提示，普通小章节输入不变。模型选中只读上下文时报错，原答保存，不补修重试。页面保持完整原表并高亮选中节点，保留合并单元格；每来源章节显示最新批次，选中不等于医学适用。CLI/页面最多4并发，整批章节顺序执行以保持全局上限。11例16组合109块仅离线准备，未付费执行；费用预留与预计实付必须区分。记录 `out/step3a-production-structure-20261125/README.txt`。

> 当前代码核对（2026-11-25）：入口为 `scripts/run_step3a.py`，调用 `source_selection.prepare/run`，产出原文节点选择结果。`step3a.add_established` 明确停止：Action/Ledger 适配尚未接入，不能运行完整 Step3。
> 下文保留旧账本设计和历史修订，供未完成适配参考；旧 `3a-v5/v6.1`、9000字符窗口和旧实验状态不代表当前实现。本文未重新核验历史审批，不产生新的授权。

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
| GeneReviews（本地存档，3.0 已下载） | Management 下各小节：Targeted Therapies、Treatment of Manifestations、Prevention of Primary Manifestations / Secondary Complications、**Agents/Circumstances to Avoid**、Pregnancy Management（仅同名行动附注，不独立建行动或缺失信息）；**不用 Surveillance；不用 Therapies Under Investigation（留给 3b 临床试验 / 3c 超说明书）** | `aitx/evidence/genereviews.py`，逐字摘录，附版权声明和章节链接 |
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

### 设计变更：章节归类和适用条件分开判断（2026-11-04，替代上面第 2 条的限制和第 3 条的分章节作用）

**理由：** 章节按作用机制归类，交给 GeneReviews 的专家分类；说明书只提供条件，不负责分类。

- **章节（靶向 / 支持）**
  - GeneReviews 收录的行动由 GeneReviews 决定：出现在 Targeted Therapies 小节，或按老版规则 (ii) 经支持度核查确认作用于机制 → 靶向；出现在 Treatment of Manifestations 等小节 → 支持。
  - 说明书不再把 GeneReviews 收录的药升为靶向。流程第 3 步的老版规则 (i) 对 GeneReviews 收录的药不再适用。
  - 只有 GeneReviews 未收录的药，才用第 3 条的句式规则决定章节。
- **适用条件**
  - 说明书适应证句只要点名了该病，就提取该说明书的条件，由它决定适用状态。句式不限，"treatment of …" 和 "to lower / improve …" 都算。
  - GeneReviews 的条件写入 `genereviews_notes` 作为备注。
  - 撤掉"只有判为靶向的说明书才决定条件"的限制。
  - 禁忌类说明书不提供条件。
  - 支持治疗的"针对某症状"（manifestation）不是用药资格条件，仍参与判定：症状未报告时为有条件适用。
- **验收：**
  - nedosiran 为靶向，条件取自 Rivfloza 说明书（≥2 岁、eGFR ≥30）；AGXT 7 岁 → 有条件（eGFR 未知）。
  - Pulmozyme（dornase alfa）为支持治疗。
- **待定（已由下面的修正解决）：** 验收期望 `otc-phenylbutyrate` 为靶向。

### 修正与补充（2026-11-04，第三次运行后批准）

1. **对上面"GeneReviews 决定章节"的修正：只适用于新版章节。**
   - 新版章节指有 Targeted Therapies 小节的章节，由 GeneReviews 决定它所收录行动的章节。
   - 老版章节（没有这个小节）里的疗法仍按老版规则判断：
     - (i) 说明书适应证句按第 3 条读作治疗该病本身 → 靶向；
     - (ii) 章节原文写明作用于分子缺陷，且通过支持度核查 → 靶向；
     - 否则 → 支持。
   - 例子：OTC 章节是老版，苯丁酸钠的说明书治疗"urea cycle disorders involving deficiencies of … ornithine transcarbamylase" → 靶向，期望保持不变。
   - 代码里每条发现带来源类型：`gr_new` / `gr_old` / `label`，见 `place()`。
2. **合子状态。** 变异要求原文里有合子状态词（homozygous / heterozygous / hemizygous / compound）时：
   - 病人的合子状态必须一致，不一致 → 不满足；
   - 病人合子状态未知 → 未知；
   - 杂合要求还写了"& / + / and a …"第二个等位基因 → 未知（第二个等位基因不比较）；
   - LLM 把变异名填进合子状态的值时，改用原文里的合子状态词。
3. **多行基因型组合：任一行满足即适用。**
   - GeneReviews 表格里同一个药的每一行（每条引用）是一组"情况"，账本要求行带 `alternative` 字段，结构版本升到 `evidence-ledger-v3`。
   - 判定规则：
     - 共同条件对所有组都适用；
     - 任一组满足 → 适用；否则取最好的一组；
     - 理由写出满足的那一组的条件；
     - 没有条件的行（泛泛提到）不会让有条件的行失效：只要有一组带条件，无条件的行就不单独成组。
   - 由说明书决定条件时，每份说明书是一组；GeneReviews 的"针对的症状"作为共同条件。
   - 看板按组显示，标注"满足其一即可"。
4. **复方药检索说明书。** 用其中一个成分检索，再按全部成分完全一致筛选。原因：用 "Elexacaftor/tezacaftor/ivacaftor" 整串检索，返回 0 条。
5. **只有说明书来源的支持治疗。** 把适应证句作为"针对的症状 / 并发症"条件。症状未报告时为有条件适用，缺失信息合并到"manifestations not reported"一行。

### 第四次运行后的修改（2026-11-04 批准）

1. **变异只在要求原文和它引用的表格里查找。** 要求原文写了 "see Table N" 时，只在说明书的 Table N 里找（从 "Table N:" 标题到下一个表格标题）；其他情况判为未知，不再搜索整份说明书。
   - 起因：Kalydeco 只在临床试验描述里提到 F508del，代码却因此判 ivacaftor 的"对 ivacaftor 有反应的变异"为满足，但 F508del 对 ivacaftor 单药没有反应。
2. **说明书条件按所在章节区分。**
   - Indications and Usage 里的条件（年龄、基因型、器官功能等）是资格条件，决定适用状态。例如 Rivfloza 的 eGFR ≥30 写在适应证句里，所以 nedosiran 判为有条件适用。
   - 其他章节（Dosage and Administration、Warnings and Precautions、Contraindications、Use in Specific Populations 等）里的条件是安全注意事项：不改变适用状态，不进缺失信息表，写入 `precautions`，在卡片上显示为"注意事项"。
   - 例外：病例里已知病人有该情况，且原文是"不应 / 避免 / 禁用"之类的措辞时，判为不适用（记为排除型要求行）。
   - 例子：Trikafta 的"Should not be used in patients with severe hepatic impairment"在 Dosage and Administration 里，ETI 判为适用，并带这条注意事项。
3. **要求原文中的 "or" 拆成多个情况。** 任一情况满足 → 满足；没有满足、但有无法判断的情况 → 未知；全部不满足 → 不满足。
   - 只拆变异、变异类型、合子状态这几类要求。
   - "or older / or younger / or more / or less" 等不拆。

### 第五轮修改（2026-11-04 批准，提示词 `3a-v5`）

1. **段首限定。** GeneReviews 段落开头的引导语（段首的粗体，如 "Ages 0-3 years."）和小标题（只有粗体的段落），作为该段所有内容的条件上下文交给提取，处理方式和表格行表头相同。
   - LLM 看到的每段写作 "Paragraph k [context: 小标题; 引导语]: 原文"。
   - 紧跟在带限定段落之后的列表继承这个限定。
   - 核验只在该段的范围内进行（`genereviews.paragraph_scope`），不跨段。
   - 起因：KMT2B 的早期干预缺了 "Ages 0-3 years" 这个条件。
2. **漏抽覆盖检查。** Management 小节里，每个表格行必须对应至少一个抽出的行动（行动的逐字引用落在该行某个格子里）。
   - 没有对应的行，由代码单独再调用一次 LLM，只抽这一行（`ROW_SYSTEM`），并允许回答"无治疗内容"（纯监测、评估或信息）。
   - 补抽结果写入账本 `reextracted_rows`（行、原文、抽出条数、是否无治疗内容、理由、模型）。
   - 验收输出报告每个病例的补抽行数。
   - 起因：v4 漏抽了 PH1 支持治疗表第 4 行的 "Use IV fluid if needed"。
3. **`--offpeak-only` 改为每次 LLM 调用前都检查。**
   - 启动时的 `peak.guard()` 设置环境标志，`extract._cached_chat` 每次真实调用前执行 `peak.check_before_call()`。
   - 一旦进入高峰时段就抛出 `PeakHours`：`run_pipeline.py` 保留已写出的病例，正在跑的病例不写，退出码 3；`acceptance_step3_0.py` 同样退出码 3。

### 放宽从句（2026-11-05 批准）

- 要求原文**紧跟在放宽词之后**时（including / incl / even in / also in / regardless of 等，如 "incl those w/advanced CKD or kidney failure"），它是在扩大适用人群，不是条件，由代码丢弃（`broadening_word`、`drop_broadening`）。
- **边界一**：丢弃后该行动必须仍有主条件（针对的症状、孕期标记不算主条件）。没有主条件时，按原样保留并在账本 `dropped_conditions` 里报警（`warning: true`，规则 `BROADENING_ALARM`）。每次丢弃都记原文、放宽词和规则。
- **边界二**：收窄词（excluding / except / other than / unless 等）不在此列，照旧作为条件。反向测试覆盖这四种写法。
- 起因：PH1 表第 1 行 "… in all persons w/1 or 2 missense AGXT pathogenic variants, incl those w/advanced CKD or kidney failure" 让吡哆醇被判为"肾功能未知 → 有条件适用"。同时修了 "1 or 2" 被按 or 拆开的错误。


## 验收新鲜度（2026-11-05）

验收脚本只给新鲜输出计分：代码指纹、病例输入指纹或上游输出指纹与当前不一致的病例判"过期"，不计分，整体不通过。规则见 3c 契约第 14 条，实现 `aitx/runmeta.py` 的 `freshness`。

## 点名人群的小标题（2026-11-15，用户批准）

- 章节路径各级及条目所在段落 / 列表 / 表格前的小标题若点名人群（Affected Males、Heterozygous Females、Female carriers、Adults、Children、Infants 等），该标题是下面每条行动的条件；代码补齐，不依赖 LLM 是否抽出。
- 性别 / 年龄未知 → 有条件；明确满足 → 该条件满足；明确不符 → 不适用（B 类已批准）。年龄复用既有 `agebands` 保守边界，有争议区间保持未知。
- 明写的合子状态按现有基因型比较；未知合子状态不能判满足。人群的其他限定（如 carriers）保留未知，不只凭性别推定。条件仍挂在本条来源选项，FDA 说明书决定条件的既有优先规则不变。
- 标题原文独立记证据，出处带 `population heading`；相邻小标题不串用。去掉“预防骨折”这个目的，不去掉同条的 Affected Males 和 Bone health。
- 起因：DMD 双膦酸盐位于 Supportive Care / Affected Males，原先可能漏掉男性限定。测试 `tests/test_established.py`：两条行动均继承、性别 / 年龄满足与未知 / 相反、段落和表格范围、相邻标题不继承、目的移除后的保留条件。
- COL1A1 交替体位不加代码规则，留给本次重跑的上下文核查，单独汇报是否抽到婴儿限定。

## 使用情境与报告截断修正（2026-11-16，用户批准）

- 使用情境只描述病人状态或使用时机（如 low GFR、during vomiting）；“when A replaces B”这类机制说明不作为条件。
- 情境来自该条目自己的治疗表格行 / 段落及列表项；能定位治疗表格行时，不从其他药物段落里对该行动的顺带提及借条件。AGXT 肝移植因此删除误取自吡哆醇段落的机制说明，其余 GFR 等真实条件保留。
- 引文和条件不在词中间硬截断：情境提取取消 90 字符切断；报告缩略按完整单词，完整内容保留在账本。
- 正反测试覆盖机制说明排除、病人状态和时机保留、其他段落引用不串用、长情境和长单词。

## 推荐引文与表现条件分开（2026-11-16，AGXT 二次审阅）

冲击波碎石的原始抽取 `manifestation` 为“Calcium oxalate monohydrate stones”，本来正确；错误在 `_records` 的推荐引文替换分支：它把未知表现行的 `requirement` 和 `requirement_evidence` 一并替换成推荐句。现只将推荐句提升为支持引文、原疗效局限句保留为 caution，表现条件及其独立证据保持原样。不用推荐句充当 manifestation，也不改 HPO 匹配规则。正反测试 `tests/test_established.py`。

## 2026-11-18 已批准修订：kind 保留规则 v1.0

- 模型输出的类型不可识别、或 therapy 不在受控词表中时，不得仅因此删除候选；先按名称中可明确识别的介入类型映射。
- fluid intake / hydration 映射 diet，IV / intravenous fluids 等操作映射 procedure，明确器具名映射 device；既有受控康复类型不变。
- 无法映射则保留 resolved kind=other，并记录原 kind、类型待核查标记及 unknown 的类型条件，不默认适用。该条件来自代码，不冒充已完成的模型核查。
- 目标性语句、评估转诊、行政服务等误抽若落入 unknown kind，仍保留为待核查候选，不能据此认定新增已确立疗法。既有目的/章节/孕期/来源核查规则不因类型恢复而作废。
- 缺少 kind 或空名称仍是输入错误，直接停止。
- action_key 原句锚点与三票合并方案尚在审阅，未以本附录授权实施或真实调用。

## 2026-11-18 已批准设计、仅审计：来源原句锚点 v1.0

- 锚点哈希仅依赖来源ID、原始章节路径、规范化原句全文；与模型claim/旧action_key/病例分支独立，现有Evidence ID不改。
- 同句槽位用行动名称在原句中首次字面匹配的字符偏移确定，不按模型枚举顺序；不能字面定位、多源句冲突或槽位碰撞的条目单列，不强制映射。
- 有RxCUI药物保留RxCUI；药物类别及非药物提出原句锚点，药物归一化未确认者明确标注。
- 当前只允许生成旧→新提案和未决清单；映射表和未决项未经用户审阅不得切换正式key或更新Accepted Baseline。

## 2026-11-18 锚点审计补充 v2.0（正式切换仍待审核）

- 可锚定单位为完整句、完整表格单元格、完整列表项；后二者无终止标点也有效。
- 限定在该行动证据引文覆盖的单位，引用多处取同一来源文档内最早位置，不用模型顺序。
- 所选单位内无名称字面匹配：锚点+规范化名称，标name_dependent；来源读器/章节未覆盖：来源类型及ID+规范化名称，标name_dependent。
- 无法确定统一来源顺序、单位或存在身份冲突时保留旧key；不自动建立同义等价或跨文档优先级。
- 当前只读审计规则已实现；审核前不切换Ledger key、Evidence ID或Accepted。三票抽取仍只是方案与费用估计，不由本附录授权真实调用。

## 2026-11-18 正式Key启用 v1.0（不升级医学Accepted）

- 用户已批准319条身份映射，经全对象逆映射及不同旧身份不合并检查后启用；252条现有行动记录换key，65条RxCUI与2条保留旧key不变。
- `data/action_key_registry.json`保存固定审批映射、name_dependent与归一化未确认列表；Evidence ID及整份证据保留历史身份出处，不重算。
- 临床计算保持原身份，在Ledger序列化出口应用别名，报告药物类型读取可逆别名，避免前缀改变导致漏药。未审批的新候选不靠名称强配已批准行动。
- 本次15例回归只要求Key外所有内容不变；未刷新医学判定、未更新Accepted。三票真实抽取另行报价和授权。

## 2026-11-19 零费用阶段：3a-v6待真实验证

3a-v6记录章节人群限定由既有population_requirements代码处理；LLM只抽行动原句/完整本行明确条件，不从标题或跨段推断。风险理由和预防目标不是现患表现。未真实调用，不声称效果已验证。Evidence ID公式/原文不变，context-check-v3缓存键仅对问题中action claim大小写/空白规范化；原始输入、源文、患者事实和其他问题不得规范化。旧键缓存不静默覆盖迁移，历史响应仍保留，规范化不构成新核查结果。三票仍shadow，少数医学条件保留；无Accepted升级。

## 2026-11-19 v6截断处理：3a-v6.1 + 无损分块

仅缩短v6新增规则的文字，含义保持；原句/完整表行条件、代码人群小标题、风险理由不等于现患。生产源抽取按GR结构原子行切块，正文上限3500字符，逐字符连续覆盖，不再截取前9000；完整段/表行超过上限报错而非切碎丢失。每块保存真实调用出处，再交原有行动合并规则。此次授权真实试跑只KMT2B、四源分7块、$0.06含重试，非高峰先查余额；不补核查/其他Step、不改Accepted。分块与Prompt精简共同干预，单票不能证明稳定性通过。

## 2026-11-19 examples结构归并（$0，Prompt仍为3a-v6.1）

同原句明确的X (e.g., A, B) / X such as A, B以X为行动，A/B记录examples成员，不单列，不是可互换药物同义词，不改RxCUI。仅字面可定位结构归并，保留完整原句、各成员原始抽取与限制；不能由某个成员的kind/条件推出整个X的type/资格。没有独立parent抽取时kind未知，成员条件待审，阻止无条件适用。正式报告引用原句、列examples及Evidence ID。当前仅shadow/离线，不刷新正式Ledger或Accepted；新旧三票统一应用相同后处理。

停止标准见docs/step3a_v6_1_stop_criteria.md v1.0，用户已明确：单票医学缺口不阻断第三票，只有运行异常阻断。KMT2B新增两票各独立$0.035帽，重试计入；无异常直接第三票。达标后才单独报价AGXT，之后才决定工程冻结。未达标进入known_limitations，不自动改Prompt；冻结不代表医学审核通过。

## 2026-11-20 结构阶段2：条件成对指认提示词冻结

按用户授权的定向回归通过后，冻结 **`3a-identify-condition-pairs-v1`**，完整提示词、SHA及参数见 [step3a_identify_prompt.json](step3a_identify_prompt.json)。这冻结的是阶段2候选指认接口；生产默认抽取仍为已验收 `3a-v5`，旧 v6.1 路径只供实验及后续兜底。没有升级任何医学 Accepted 或 current。

输入为所属标签/表格行上下文、编号句子 S、候选治疗 T（治疗标签本身提供为 T0）；输出每句：

```json
{"S1":{"actions":["T1","T2"],"conditions":[{"T":"T1","words":"限定原词"}],"roles":["action","condition"]}}
```

- 每个 condition 必须有且只有一个给定 T；缺失、多个或未知 T 均为格式错误。不得把本句限制分发给所有同句治疗。
- words 必须是本句中忽略大小写后的连续子串，代码复制原文原始写法；不忽略空白、不删词、不跨句拼接，失败计格式错误。句子全文和来源标识均由代码复制，模型不生成 source_id。
- `_new` 名称沿用已批准的忽略大小写与空白子串校验，复制原写法；没有给定 T 的 action 仍可 needs_review，不默认为格式错。缺条件不等于无条件适用。
- `thinking.type=disabled`、max_tokens=1024、temperature=0、JSON 对象；三票对每个 `(T, words)` 原词对分别多数，不以角色与 T 的笛卡尔积创建关联。不同边界或不同源文的限制不合并；少数票保留。
- 三份答复中的格式失败票不参与条件计数，也不作为反对票；至少两份有效票的相同原词对即可形成2/3多数，不另加“必须三份都有效”的门槛。少于两份有效票不形成多数；三票一致率仅在三份均有效的句子上另算，原始格式失败记录不改成有效。
- GeneReviews 的 nedosiran **>30** 与 FDA 标签 **≥30** 按各自来源引用，不改写或互相覆盖，不能据此自行改变患者状态。
- 推荐/描述/无效及条件是否构成病人资格仍交既有上下文核查。上下文核查保持 reasoning_effort=low / max_tokens=16384，不属于本轮指认调用。

本轮只验证 AGXT 7 组受影响句子、KMT2B 抗胆碱药和 IEP/21 岁两段：27/27 答复有效、零格式错/截断，三个关联 must_checks 和独立来源检查通过。全部 12 句有完整三票，7 句原词/角色/行动全部一致；其余原词范围及标签差异保留，冻结不表示所有临床语义均已审核。15例全量及表格待判单元尚未执行，仅报价。完整结果见 定向回归报告（历史资料已清理）。

### 2026-11-20 全量后续：原队列完成，整体未验收

用户另行批准$0.20后，340题/1020次全部完成，费用$0.078656796。615有效、405格式错、零截断；298份仅多顶层type字段的规范化副本只作零费用诊断，原票不改。KMT2B/AGXT指定检查均通过，但这不覆盖其他协议错误。

另确认输入编排未将部分同行备注编号为源句，至少43个Accepted名称涉及35个表格单元格。应补源句编号和候选挂接，不得将words校验放宽到任意上下文而假装原题已覆盖。补题尚未调用，不重跑整批、不进入阶段3，不将冻结提示词等同于全量或医学验收通过。当前完整结果及补题清单见 全量报告（历史资料已清理）。

### 2026-11-20 免费格式兼容与输入修复

按用户授权忽略输出顶层额外`type`；冻结SYSTEM、版本与生成参数不变。历史原答复保持不动，副本可解开明确T包装、迁移句内`_new`并按原词校验、唯一定位原句及恢复显式条件对的角色标签；不补临床漏句、不推断缺失T、不改条件原词约束。XML证实的无正文导航单列，不计抽取成功。

表格补题把完整同行所有列编号为S，保留每句列头/列语义/XPath及整行上下文；43个已有Accepted名称的字面原词仅作候选，不算模型召回。临床正文或T列表改变的题重新三票；标签/引用片段由代码单列后，临床正文编号与T映射不变的题只补失败票、复用重校验通过的有效票。未执行补题或上下文核查，未进入Phase 3；剩余69份格式失败及增量报价见修复报告（历史资料已清理）。

### 2026-11-20 获批增量完成，Phase 2仍待验收

167次增量全部返回，费用$0.022004031计入原任务累计$0.100660827。新增102有效/65失败，合并1030/1095有效；43项严格多数指认24，17项仅原始提案，2项名称形式差异保留待映射，不自动升级别名或医学Accepted。冻结提示词及所有原词/T归属约束不变，缺S不填none。未加跑、未进Phase 3；完整失败项、Accepted对照和status_diff见增量验收报告（历史资料已清理）。

### 2026-11-20 $0输入和逐句校验修复，模型继续暂停

背景与待判正文分开，已批准的列条件/目的/类别和源XML引用单列，真实正文及未知标签不删。候选先用既有词典/规则和逐字缓存提案编号；原T/新T分开，不能用新T补正旧答复或把未问正文的旧行标签答案改挂到新S。按句复用未改动的validate和majority，漏S仍未知、非法条件仍错；同批其他合法S可独立投票。旧整题统计和原答复不改，临床判定规则、生产默认及上下文核查不动。

新输入只准备，未发模型；43项严格名称多数41、2变体映射待审，仍35处正文未知，不宣称Phase 2完成。有效率分母及全部缺口、Accepted对照和完整status_diff见本轮验收报告（历史资料已清理）。

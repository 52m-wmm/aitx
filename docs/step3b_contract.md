# 第 3b 步：临床试验（Clinical Trial Eligibility）

> 状态：**草稿，待审**（2026-11-03）。审定后才写代码。依赖 3.0（证据账本、诊断分支、行动键 `trial:NCT…`、
> 行动记录 1.4、阴性证据 1.2、缓存过期）与 3a 的病人事实比较代码。资料核查只调用了 ClinicalTrials.gov 接口，未调用 LLM。

## 目的

为每个诊断分支找出**正在招募**（RECRUITING）或**尚未开始招募**（NOT_YET_RECRUITING）的临床试验，
并把入组和排除标准**逐条拆开**，对照病人事实得出每个分支的适用状态（applicable / not_applicable / conditional），
给出不满足或无法判断的具体条目。对应模板 Tier 2 "Clinical Trial Eligibility"：
"which inclusion criteria the patient meets …, which criteria cannot be assessed from the case, and any exclusion that would disqualify them"。

## 数据源

ClinicalTrials.gov API v2（`https://clinicaltrials.gov/api/v2/studies`），经 `aitx.http`：
- **缓存最多 1 天**（3.0 已实现）；正式生成报告前用 `run_pipeline.py --refresh-trials` 强制重新获取。
- 每次检索记录：完整请求 URL、检索词、过滤条件、查询时间、`totalCount`（接口返回的总数，用 `countTotal=true`）。
- 证据链接：`https://clinicaltrials.gov/study/<NCT>`；记录 `lastUpdatePostDate`（报告注明"登记记录更新于 …"）。
- 用到的字段：NCTId、BriefTitle、Acronym、OverallStatus、Phase、StudyType、Condition、Keyword、InterventionName、
  MinimumAge、MaximumAge、Sex、HealthyVolunteers、EligibilityCriteria、LastUpdatePostDate。

## 流程（对每个分支）

1. **检索（召回）**
   - 按疾病：`query.cond` = 分支疾病的标准名和同义词（最多 3 个）；
   - 按基因：`query.term` = 基因符号（基因靶向试验常只写基因，如 "SLC35A2-CDG"）；
   - `filter.overallStatus=RECRUITING,NOT_YET_RECRUITING`；分页取完全部结果（`pageSize=100` + `nextPageToken`）。
2. **相关性过滤（代码）**：试验登记的 Condition 或 Keyword 必须点名该分支疾病（标准名或同义词）或基因符号。
   实测需要：按 "ornithine transcarbamylase deficiency" 检索会混进缩写同为 "OTC" 的食管癌手术试验和慢性肾病研究；
   囊性纤维化 183 个在招募试验中，有疾病列表不含 CF 的分枝杆菌感染试验和列了十几种病的检验方法研究。
   被过滤的试验记入阴性证据的 `excluded`（附原因）。
3. **结构化预筛（代码）**：用登记的 MinimumAge / MaximumAge 与病人年龄比、Sex 与病人性别比、只招健康志愿者的排除。
   病人年龄或性别未知 → 保留，状态最多为 conditional。
4. **排序与上限**：通过预筛的试验按（基因或疾病专一程度：Condition 只列该病的优先 → 干预性试验优先 → 期别 3>2>1 → 更新日期近）排序，
   每个分支取前 **K 个**做逐条分析（默认 K=10，见待定问题 4）；其余列为"已找到、未逐条分析（超出上限）"，附 NCT 编号。
5. **逐条拆分标准（代码 + LLM）**
   - 代码按 "Inclusion Criteria" / "Exclusion Criteria" 标题和条目符号（`*`、`-`、`1.`）把 EligibilityCriteria 拆成逐条原文。
   - LLM 只把**每一条原文**映射成结构化字段：`{field, op, value, unit}`，字段 ∈ 年龄、性别、诊断、基因 / 变异、变异类型、
     化验值（`analyte` + 数值 + 单位）、肾功能、肝功能、体重、出生胎龄、既往 / 当前治疗、妊娠 / 避孕、行政类（知情同意、依从性、能到访）、其他。
     LLM 不判断病人是否符合。
   - **比较由代码做**（复用 3a 的 `evaluate`，并扩展化验值、胎龄、既往治疗）：病例里没有的事实 → unknown。
     入组条目"符合 → 通过"，排除条目"符合 → 不通过"（3.0 契约 1.4 规则 3）。
6. **病人事实补充**：Step 2 只抽了年龄、性别、起病、家族史等。试验标准常涉及**化验值、出生胎龄、当前用药、既往治疗、合并症**。
   3b 增加一次抽取（与 Step 2 相同原则：LLM 只给原文引用和数值，代码核对引用逐字存在、数字出现在引用里），结果写入账本的 `patient_context.extra_facts`。
7. **行动记录**：每个试验一条（`trial:NCT…`），按分支给状态和理由（如 "excluded: Hemoglobin < 7"，"depends on: eGFR"），
   逐条列出入组 / 排除标准及结果；基因靶向试验适用于该基因的全部分支，疾病试验适用于其 Condition 点名的分支。
8. **查过没找到**：某分支没有任何通过过滤的试验 → `searched_none` + 阴性证据（检索词、时间、`totalCount`、被过滤的试验及原因）。

## 校验（在 3.0 校验之外）

| 校验 | 不过则 |
| --- | --- |
| 进入章节的试验状态均为 RECRUITING / NOT_YET_RECRUITING（以本次获取的记录为准） | fail |
| 每条标准逐字来自该试验的 EligibilityCriteria；结果由代码算出 | fail |
| 年龄、性别的预筛与登记字段一致 | fail |
| 每个分支有试验行动或阴性证据；被过滤 / 超出上限的试验都有记录 | fail |
| 检索记录完整（URL、时间、totalCount）；缓存不超过 1 天 | fail |

## 验收（期望先对照登记原文核实，下表已于 2026-11-03 核实）

| 病例 | 期望 | 出处 |
| --- | --- | --- |
| PRAC-SLC35A2-ex7（年龄未知） | AVTX-801 试验 NCT05402384（NOT_YET_RECRUITING）出现在章节中，状态 conditional（年龄、血红蛋白未知） | 登记记录：年龄 1 Month 以上；排除 "Hemoglobin \< 7 mg/dL" |
| PRAC-SLC35A2-ex8（2 个月，"Hemoglobin 5"） | NCT05402384：年龄条目通过；血红蛋白排除条目的结果见**待定问题 3**（单位） | 同上；病例原文 "Hemoglobin 5"（无单位） |
| PRAC-AGXT-c33dup（7 岁） | 在招募的 PH1 试验中，ABO-101（NCT06839235，6–64 岁）、YOLT-203（NCT07587021，≥6 岁）年龄条目通过；DCR-PHXC（NCT04580420，Condition 含 ESRD）中要求终末期肾病的条目为 unknown | 登记记录 |
| PRAC-CFTR-F508del（15 岁） | 相关性过滤后数量与原因有记录；逐条分析不超过 K 个；Condition 不含 CF 的试验被过滤 | 检索实测：CF 在招募 183 个 |
| PRAC-OTC | ARCT-810（NCT06488313）要求年龄 ≥12 岁，3 个月男婴 → not_applicable；OTC-HOPE（DTX301，NCT05345171）现为 ACTIVE_NOT_RECRUITING，**不进入章节** | 登记记录（2026-11-03） |
| 评测病例 | 只做人工核对 | — |

**计划变更**：Phase 0 示例中"OTC-HOPE 试验因胎龄不合格"的考点，在当前登记中该试验已不再招募，不能作为在招募试验的验收用例；
胎龄条目的比较改由离线测试覆盖。

## 费用与运行

每个分支逐条分析至多 K 个试验，每个试验一次 LLM 调用（标准映射）+ 每个病例一次事实补充抽取。全部 LLM 调用只在非高峰时段运行
（`--offpeak-only`），检索与过滤不受限制。

## 待定问题

1. **观察性研究**（样本库、登记、自然史研究）：建议**只把干预性试验放入本章节**；观察性研究记入账本背景证据，不作为行动。
2. **行政类条目**（知情同意、愿意遵守方案、能按时随访）：建议标为"筛选时评估"，**不参与状态计算**，也不进缺失信息
   （否则所有试验都会是 conditional）。需要在 3.0 账本中为这类条目增加结果值 `not_assessed`。
3. **化验值单位**：病例 "Hemoglobin 5" 无单位，登记写 "\< 7 mg/dL"（按常识应为 g/dL，疑似登记笔误）。
   建议：单位缺失或不一致时**不推断**，结果为 unknown，理由写明"单位不明：若为 g/dL 则符合排除标准"，状态 conditional。
   这样 ex8 不会得出 Phase 0 示例的"不合格"，但不会写错。
4. **每个分支逐条分析的上限 K**：建议 10；超出部分列出 NCT 编号与预筛结果，不做逐条分析。
5. **病人事实补充**放在 3b（建议），还是回到 Step 2 统一抽取（需要改 Step 2 契约并重新验收）。

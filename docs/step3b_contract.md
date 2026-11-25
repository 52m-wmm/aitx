# Step 3b 当前架构（2026-11-25重构）

**当前验收进度：3b架构整理完成，仅PRAC-OTC已完整缓存重跑并显示最新批次；尚未跑全病例。OTC为21项研究、7候选/14排除，15自检通过/1既有警告/0失败，新增模型调用0。不得将此次整理标为全病例验收完成。**

当前只有一条生产链：**检索 → 完整上下文冲突初筛 → Python核验 → Ledger组装 → 缓存发布 → 页面读取**。
没有另建legacy包，没有旧逐条条件映射入口。重构沿用原生产Conflict-Only行为，不宣称恢复旧映射器的全部条件解释能力。

| 文件 | 职责 |
|---|---|
| `aitx/step3/b/pipeline.py` | 对外 `add_trials` / `refresh_trials`；上游事实、按分支检索、4并发模型请求、调用组装器；刷新冻结其他步骤 |
| `aitx/step3/b/screening.py` | 检索计划、完整请求构造、原文/适用范围冲突核验；不写Ledger、不调用模型 |
| `aitx/step3/b/rules.py` | 新流程实际使用的确定性规则；13个函数AST与改前一致，无模型调用 |
| `aitx/step3/b/records.py` | 唯一试验落账实现；已核验冲突、未知项、证据与多分支合并 |
| `aitx/step3/b/results.py` | 运行状态、改前快照、缓存归档和正式结果发布 |
| `aitx/step3/b/presentation.py` | 已保存Ledger转页面卡片，不重新判断 |
| `aitx/evidence/trials.py` | CT.gov传输/解析及共享匹配排序函数；旧plan_branch及祖先遍历入口已删 |

依赖方向：results → pipeline → screening/rules/records；records → screening/rules；presentation只读取结果。生产模块不依赖scripts或旧实验。

入口仍为 `scripts/refresh_step3b.py --case <病例> --cache-only`。
`--cache-only`只禁止新LLM调用，沿用HTTP缓存行为，不代表严格断网。
完整Step3调用改为`aitx.step3.b.pipeline.add_trials`；完整Step3仍受3a Ledger适配尚未完成限制。
独立3b刷新仍需已有账本，不重跑其他步骤。

结果存放：`.cache/step3b/<病例>/<UTC批次>/`，包括`execution.json`、`case-input.json`、`previous-ledger.json`、`ledger.json`、`result.json`。
成功通过账本自检、生成卡片后才发布`out/step3/<病例>.json`。异常向调用方抛出，最新批次显示失败而不回退旧结果。
页面按started_at读取最新缓存批次，文件监听自动刷新。原导入缓存、HTTP/模型缓存、正式结果及历史记录未改。

保留的行为：原Prompt/版本/参数、模型请求序列化、缺失事实为未知、未证实冲突不排除、无冲突不等于完整资格满足。
13个现役规则函数逐一AST相同；8组改前冻结账本对照完全一致；模型冲突引用/替代路径/未知、其他步骤冻结、失败保存有离线测试。
本次没有真实模型调用、没有正式病例重跑，不构成医学准确率或全病例验收。

旧实现退役：criteria的逐条映射/比较链、旧_record、旧限额检索/祖先遍历、依赖旧实现的5个历史实验/回放脚本。
旧专属测试退出活动测试集；现役原文校验/前言/分子靶点测试移植保留，报告测试保留。
原源码和专属测试保存在`out/step3b-rebuild-20261125/before/`，逐项清单`retired.json`。没有把旧测试退役称作旧缺陷修复。

审计：`out/step3b-rebuild-20261125/`，含改前账本快照、冻结对照、完整current对比输出、测试、文件保护哈希。
current基线开工前已缺失，无法完成该项对比，不重建/升级基线。

## 历史契约（旧逐条映射实现，供已保存结果追溯）

以下为旧版本的决策与验收记录，不能作为当前Conflict-Only实现已满足这些验收项的证明。


# 第 3b 步：临床试验（Clinical Trial Eligibility）

> 当前代码已有 `trial_records.add_trials → trial_screening.add_trials` 路径。以下“当前生产入口”说明与旧设计分开；早期草稿状态不表示现在尚无代码。代码存在不等于整体Step3已完成或本轮已验收。

## 当前生产入口（2026-11-25）

`trial_records.add_trials` 已切换至 `trial_screening.add_trials`，使用已测试的四轴 Conflict-Only Prompt。
完整原始病例与完整 EligibilityCriteria（含前言）送入模型；temperature=0、JSON、thinking disabled，最大并发4。
疾病及最近疾病家族检索开放研究，保存整个 protocolSection；不使用下述旧版相关性过滤和K=10裁剪。
Python核验双引文、替代队列及可独立确认的冲突；缺事实或冲突逻辑未确认时保留candidate并注明人工核查。
年龄未知不排除，正文与API年龄范围不一致时待核实；前言明确的当前招募限制独立比较。
单基因靶点互斥继续执行。对临床史等尚无确定性核验器的冲突，仅复用与完整输入和原始冲突绑定的已有人工审查，否则保留复核。
没有硬冲突不代表完整资格满足：账本保留unknown，不输出最终入组合格。
`add_mapped_trials` 仅保留为旧版回归接口。以下逐条映射设计为历史说明，不能当作当前默认。

## 目的

为每个诊断分支找出**正在招募**（RECRUITING）或**尚未开始招募**（NOT_YET_RECRUITING）的临床研究
（干预性试验在前，观察性研究——自然史、登记、样本库——在后并标明研究类型），
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
   - **不加状态过滤**，分页取完全部结果（`pageSize=100` + `nextPageToken`），由代码按 OverallStatus 分开：
     RECRUITING / NOT_YET_RECRUITING 进入后续步骤；其他状态（ACTIVE_NOT_RECRUITING、COMPLETED、TERMINATED 等）记入阴性证据的
     `excluded`，原因写明状态（只列相关性过滤后仍点名该病或基因的研究，按更新日期取最近 50 个，总数照记）。
     实测：OTC 缺乏症全部状态共 61 个，在招募 12 个（干预性 4、观察性 8），OTC-HOPE（NCT05345171）以 ACTIVE_NOT_RECRUITING 出现在被排除列表中。
2. **相关性过滤（代码）**：试验登记的 Condition 或 Keyword 必须点名该分支疾病（标准名或同义词）或基因符号。
   实测需要：按 "ornithine transcarbamylase deficiency" 检索会混进缩写同为 "OTC" 的食管癌手术试验和慢性肾病研究；
   囊性纤维化 183 个在招募试验中，有疾病列表不含 CF 的分枝杆菌感染试验和列了十几种病的检验方法研究。
   被过滤的试验记入阴性证据的 `excluded`（附原因）。
3. **结构化预筛（代码）**：用登记的 MinimumAge / MaximumAge 与病人年龄比、Sex 与病人性别比、只招健康志愿者的排除。
   病人年龄或性别未知 → 保留，状态最多为 conditional。
4. **排序与上限**：通过预筛的研究按（干预性在前、观察性在后 → 基因或疾病专一程度：Condition 只列该病的优先 → 期别 3>2>1 → 更新日期近）排序，
   每个分支取前 **K = 10 个**做逐条分析；其余列为"已找到、未逐条分析（超出上限）"，附 NCT 编号和预筛结果。
   行动记录写明研究类型（`study_type`: interventional / observational），报告中观察性研究排在干预性试验之后并标明类型。
5. **逐条拆分标准（代码 + LLM）**
   - 代码按 "Inclusion Criteria" / "Exclusion Criteria" 标题和条目符号（`*`、`-`、`1.`）把 EligibilityCriteria 拆成逐条原文。
   - LLM 只把**每一条原文**映射成结构化字段：`{field, op, value, unit}`，字段 ∈ 年龄、性别、诊断、基因 / 变异、变异类型、
     化验值（`analyte` + 数值 + 单位）、肾功能、肝功能、体重、出生胎龄、既往 / 当前治疗、妊娠 / 避孕、行政类（知情同意、依从性、能到访）、其他。
     LLM 不判断病人是否符合。
   - **比较由代码做**（复用 3a 的 `evaluate`，并扩展化验值、胎龄、既往治疗）：病例里没有的事实 → unknown。
     入组条目"符合 → 通过"，排除条目"符合 → 不通过"（3.0 契约 1.4 规则 3）。
   - **行政类条目**（知情同意、愿意遵守方案、能按时随访等）：结果为 `not_assessed`（"screening assessment"），
     **不参与适用状态计算，不进缺失信息**；需在 3.0 账本中增加这一结果值（`status_from` 忽略它，校验允许它）。
   - **化验值的单位**（2026-11-03 决定）：配置文件 `config/lab_plausible_ranges.json` 列出常见化验值在各单位下的**生理合理范围**和换算系数，
     每条附出处（权威参考范围来源，写代码前逐条核实）。规则：
     · 病例数值没写单位：逐个单位检查，**只有一种单位能得到生理上合理的数值** → 采用该单位，并在证据和报告中**明确写出这个假设**
       （如 "Hemoglobin 5 interpreted as g/dL: the only physiologically plausible unit"）；两种以上都合理 → unknown，状态 conditional。
     · 登记标准里的单位**明显不合理**（如 "Hemoglobin \< 7 mg/dL"，7 mg/dL 不可能是活人的血红蛋白）：同样按合理范围理解成唯一合理的单位并注明。
     · 单位都确定后，代码换算到同一单位再比较。
6. **病人事实补充**（通用模块 `aitx/evidence/patient_facts.py`，3b 起各子节点复用）：Step 2 只抽了年龄、性别、起病、家族史等。
   试验标准常涉及**化验值、出生胎龄、当前用药、既往治疗、合并症**。每个病例抽取一次（与 Step 2 相同原则：LLM 只给原文引用和数值，
   代码核对引用逐字存在、数字出现在引用里；单位按上面的规则处理），结果写入账本的 `patient_context.extra_facts` 并缓存，后续子节点直接读取。
7. **行动记录**：每个试验一条（`trial:NCT…`），按分支给状态和理由（如 "excluded: Hemoglobin < 7"，"depends on: eGFR"），
   逐条列出入组 / 排除标准及结果；基因靶向试验适用于该基因的全部分支，疾病试验适用于其 Condition 点名的分支。
8. **查过没找到**：某分支没有任何通过过滤的试验 → `searched_none` + 阴性证据（检索词、时间、`totalCount`、被过滤的试验及原因）。

## 校验（在 3.0 校验之外）

| 校验 | 不过则 |
| --- | --- |
| 进入章节的研究状态均为 RECRUITING / NOT_YET_RECRUITING（以本次获取的记录为准）；其他状态的相关研究都在阴性证据的被排除列表中 | fail |
| 行政类条目结果为 not_assessed 且不影响状态；化验值的单位假设都写进了证据 | fail |
| 每条标准逐字来自该试验的 EligibilityCriteria；结果由代码算出 | fail |
| 年龄、性别的预筛与登记字段一致 | fail |
| 每个分支有试验行动或阴性证据；被过滤 / 超出上限的试验都有记录 | fail |
| 检索记录完整（URL、时间、totalCount）；缓存不超过 1 天 | fail |

## 验收（期望先对照登记原文核实，下表已于 2026-11-03 核实）

| 病例 | 期望 | 出处 |
| --- | --- | --- |
| PRAC-SLC35A2-ex7（年龄未知） | AVTX-801 试验 NCT05402384（NOT_YET_RECRUITING）出现在章节中，状态 conditional（年龄、血红蛋白未知） | 登记记录：年龄 1 Month 以上；排除 "Hemoglobin \< 7 mg/dL" |
| PRAC-SLC35A2-ex8（2 个月，"Hemoglobin 5"） | NCT05402384：年龄条目通过；排除条目 "Hemoglobin \< 7 mg/dL" 的登记单位不合理，在同一量纲内理解为 g/dL（注明）；病例 "Hemoglobin 5" 没写单位，g/dL 与 mmol/L 都合理 → **conditional**，报告分别写明两种情况：按 g/dL（5 \< 7，符合排除标准，不能入组）、按 mmol/L 为未知（换算系数未核实；2026-11-04 修改，见下方待办）。**与官网 Phase 0 答案（不能入组）不同**，原因见下方计划变更 | 同上；病例原文 "Hemoglobin 5"（无单位） |
| PRAC-AGXT-c33dup（7 岁） | 在招募的 PH1 试验中，ABO-101（NCT06839235，6–64 岁）、YOLT-203（NCT07587021，≥6 岁）年龄条目通过；DCR-PHXC（NCT04580420，Condition 含 ESRD）中要求终末期肾病的条目为 unknown | 登记记录 |
| PRAC-CFTR-F508del（15 岁） | 相关性过滤后数量与原因有记录；逐条分析不超过 K 个；Condition 不含 CF 的试验被过滤 | 检索实测：CF 在招募 183 个 |
| PRAC-OTC | ARCT-810（NCT06488313）要求年龄 ≥12 岁，3 个月男婴 → not_applicable；OTC-HOPE（DTX301，NCT05345171）现为 ACTIVE_NOT_RECRUITING：**不列为可报名试验**，出现在阴性证据的被排除列表中（原因：状态） | 登记记录（2026-11-03）；不加状态过滤的检索实测 |
| 评测病例 | 只做人工核对 | — |

**计划变更**：Phase 0 示例中"OTC-HOPE 试验因胎龄不合格"的考点，在当前登记中该试验已不再招募，不能作为在招募试验的验收用例；
胎龄条目的比较改由离线测试覆盖。

**计划变更（2026-11-03 决定）**：ex8 的期望由 not_applicable 改为 conditional。血红蛋白在临床上也以 mmol/L 报告（如荷兰），
"Hemoglobin 5" 按 mmol/L 约为 8.1 g/dL，同样生理合理；按决定 3（两种以上单位合理 → conditional），不能假定 g/dL。
官网 Phase 0 示例默认按 g/dL 理解而判为不能入组；本系统不做这个未经证实的假设，改为在报告中分别写出两种情况（`labs.scenarios`）。
登记单位不合理时只在**同一量纲**内重新理解（mg/dL ↔ g/dL ↔ g/L；mmol/L 等摩尔单位之间），因为质量单位与摩尔单位的混用不是笔误式错误。
化验值合理范围在 ABIM 参考值表核实填入之前一律"待核实 → 判为未知"，此时 ex8 的血红蛋白条目同样为 unknown（状态 conditional）。

**化验值单位规则（2026-11-03 决定，`config/lab_plausible_ranges.json` + `aitx/evidence/labs.py`）**

| 规则 | 内容 | 依据 |
| --- | --- | --- |
| 参考范围 | ABIM Laboratory Test Reference Ranges（2026 年 1 月版）的成人参考范围，配置中注明版本、页码、原文行；PDF 放在 `docs/reference/`，不进仓库 | 公开的权威参考范围表 |
| 合理范围 | 参考范围下限 ÷10 到上限 ×10（换算到标准单位） | 病理值通常偏离正常范围数倍以内，单位笔误通常 ≥100 倍（mg ↔ g 为 1000 倍），两者在 ×10 处能分开 |
| 登记单位不合理时改读 | 只改读成同一量纲、换算倍数 ≥100 倍、且落入合理范围的唯一单位，并写明假设；否则 unknown | 只纠正笔误式错误；g/dL ↔ g/L（10 倍）、mg/dL ↔ µmol/L（肌酐约 88 倍）这类差距可能是真实病理值，不改读 |
| 病例数值没写单位 | 合理单位唯一时采用并写明假设；两个以上、或有换算系数未核实的单位无法排除时 → unknown，报告按单位分别写出结论 | 决定 3 |
| 换算系数未核实 | 该单位既不能被假定，也不能被排除 | 写错比不写更糟 |

**待办（2026-11-04）**：找到血红蛋白 mmol/L 换算系数的权威出处（如 AMA Manual of Style 的 SI 换算表或同等来源），核实后写入配置，再按登记原文阈值（"Hemoglobin \< 7 mg/dL"）重新推导 ex8 的 mmol/L 情形期望。在此之前 ex8 期望为：总体有条件适用；g/dL → 符合排除标准；mmol/L → 未知（理由：换算系数未核实）。代码不使用未核实的系数。

**已知局限**：透析病人的肌酐（>13 mg/dL）、高氨血症危象的血氨（>约 411 µmol/L）等真实的极端值会超出 ×10 上限，此时判为 unknown（状态 conditional），**不会判错**，只是少给一个结论。
血红蛋白的 mmol/L 换算系数尚无可引用的权威出处：AMA Manual of Style SI 换算表（第 11 版）只列 g/dL → g/L，二手资料存在 0.6206（按单体）和 0.155（按四聚体）两种约定，因此保持待核实；
在此期间，没写单位的血红蛋白数值至少有 g/dL 与"mmol/L（未核实）"两种可能，一律为 unknown。

## 费用与运行

每个分支逐条分析至多 10 个研究，每个研究一次 LLM 调用（标准映射）+ 每个病例一次事实补充抽取。LLM 并发上限 16（DeepSeek 上限 2500）。
全部 LLM 调用只在非高峰时段运行（`--offpeak-only`），检索与过滤不受限制。

## 已定决策（2026-11-03 审阅）

1. **观察性研究**（自然史、登记、样本库）放进本章节，排在干预性试验之后，标明研究类型。
2. **行政类条目**标为"筛选时评估"（`not_assessed`），不参与适用状态计算，不进缺失信息。
3. **化验值单位**：按生理合理范围表推断唯一合理单位并明确写出假设；两种以上合理才判 conditional，报告分别写出各单位下的结论；登记单位明显不合理时在同一量纲内同样处理并注明。
4. **每分支逐条分析上限 10 个**。
5. **病人事实补充**在 3b 做，写成通用模块 `aitx/evidence/patient_facts.py` 供后续子节点复用。
6. OTC-HOPE 不再招募：期望改为"不列为可报名试验"，记录为因状态排除的阴性证据。

## 实现细则（2026-11-04 批准）

**病人事实（`aitx/evidence/patient_facts.py`）**
- 描述里没有提到的事实（是否参加过其他试验、用药、既往治疗等）不出现在列表里，任何使用方都按 unknown 处理。
- 只有原文明确否认时才算"无"（`absent`），引用里必须有否定词（no / not / never / none / without / denies / negative for 等）；"normal"同样要求原文有 normal / unremarkable 之类的词。
- 化验、用药、既往治疗、合并症的名称必须出现在引用里。
- 反向测试：LLM 把"Enrolled in trial …"标为"未参加"，或把"Seizures since birth"标为肝功能正常，都会被丢弃。

**派生值（`aitx/evidence/derived.py`）**：只用公开公式，所有输入都必须在病例里。缺任何输入就是 unknown，不补身高、体重、种族或默认年龄。
- eGFR，≥18 岁：CKD-EPI 2021 肌酐方程（不含种族），Inker LA et al., *N Engl J Med* 2021;385:1737–1749。
- eGFR，<18 岁：床旁 Schwartz 公式 0.413 × 身高（cm）/ 血肌酐（mg/dL），Schwartz GJ et al., *J Am Soc Nephrol* 2009;20:629–637。必须有病例给出的身高。
- 血肌酐先按化验单位规则换算到 mg/dL；单位无法确定时不计算。

**标准映射（`aitx/evidence/criteria.py`，提示词 `3b-criteria-v1`）**
- 代码按标题和条目符号拆分条目，入组 / 排除由标题决定。
- LLM 对每条给出一个或多个映射：事实类型 + 比较符 + 阈值 + 单位，并附该条原文的逐字引用。
- 代码核验，不过即作为"无法映射"处理：
  - 引用逐字出现在该条里；
  - 每个阈值数字出现在引用里；
  - 比较符与原文一致（≥ / at least / or older 与 > / more than / older than 区分）；
  - 单位按整词出现（"g/dL" 不等于 "mg/dL"）。
- 比较一律由代码完成。年龄用登记的结构化字段（minimumAge / maximumAge）作为要求行；普通文字年龄队列不能产生排除。2026-11-23 用户批准的例外：前言中经过原文核验、范围明确的当前招募限制可以产生 fail（见文末）。文字年龄条款按 Step 2 年龄比较，同一条目的上下界同时满足才确认 Inclusion met；不能确认匹配的分组保留 Unable to assess，不产生排除。已有分组识别只可确认满足，不能产生排除。
- 结果规则：
  - 入组条款不满足 → 不适用；排除条款满足 → 不适用。
  - 任何一条 unknown → 有条件适用，并在缺失信息里列出缺什么。
  - 行政类条款 → `not_assessed`（"screening assessment"），不影响状态。
  - 无法映射或核验不过的条款 → `not_assessed`（"not mapped; shown verbatim"），原文照显，不影响状态（账本校验允许这两种备注）。
- "满足其一"：只有同时满足两个条件才按组处理——LLM 标了组，且代码拆出的父条目原文含 "one of / any of / either"。组内任一满足即满足；没有满足、但有未知的 → 未知；全部不满足 → 不满足。每组合成一行，子项列在 `any_of`。
- 孕期：男性或 12 岁以下 → 不在孕期（排除条款通过），避孕要求不适用；其他情况 → unknown。

**行动记录（`aitx/evidence/trial_records.py`）**
- 每个试验一条 `trial:NCT…`，带研究类型、状态、期别、相关性依据、每条要求行及其逐字证据。
- 被登记年龄 / 性别排除的试验，不调用 LLM，直接判为不适用。
- 每个分支的检索记录、被过滤的研究（附原因）、超出上限的研究写入账本 `trial_searches`。
- 没有试验的分支：`searched_none` + 阴性证据。
- 验收脚本 `scripts/acceptance_step3b.py`。


## 验收新鲜度（2026-11-05）

验收脚本只给新鲜输出计分：代码指纹、病例输入指纹或上游输出指纹与当前不一致的病例判"过期"，不计分，整体不通过。规则见 3c 契约第 14 条，实现 `aitx/runmeta.py` 的 `freshness`。


## 短缩写不得单独作为病名证据（2026-11-11，盲测后修复 N1）

**规则**：大写短缩写（一个词、无小写字母、字母不超过 5 个，可含数字和连字符：LS、LSS、CMT、PH1、CHNG6、STISS）
1. **不作为 CT.gov 检索词**：`query.cond` 只用前 3 个非缩写病名（原来是前 3 个病名，缩写也占名额）；
2. **不单独作为相关依据**：只靠缩写命中的试验，同一记录的标题 / Conditions / Keywords 里还必须有全称（或长同义词），或者基因作为病人病因出现（`gene_names_condition`，癌症语境和标志物用法不算），才算相关；相关性记录里写 `corroborated_by`；
3. 只靠缩写命中而被排除的试验，排除理由写明"only the short abbreviation 'X' matched …"。

**起因**：盲测 LRPPRC（病名 Leigh syndrome / LS / LSS），10 条试验 9 条靠缩写进来——小细胞肺癌 "LS-SCLC"、HIV 抗体 "3BNC117-LS"、"Lumbar Spinal Stenosis (LSS)"（阅读规则 R10）。

**影响（练习病例，缓存重跑 + DMD 1 次新映射调用）**：
- DMD：已写出的试验 ROXA-BN-HD（NCT06917950）原来是靠关键词 "Bone Mineral Density (BMD)" 命中 Becker 分支的——**修掉了一条原有的写错**；腾出的名额由 "Duchenne Electronic Health Record Study"（NCT07609394）补上。
- CFTR：两条原判"不符合"的试验（只靠 "CF" 命中）被排除。
- NF1：22 个只靠 "NF1"（肿瘤突变）命中的肿瘤研究被排除，均未写出。
- **召回代价**：只写缩写、不写全称的真实研究也会被排除——AGXT 的 Rare Kidney Stone Consortium 登记（只写 "PH1"）、DMD 的跌倒风险研究和瑞士神经肌肉病登记（只写 "DMD"）。三者原本都没写出（不在前 10 或未招募），报告不变，但召回会降。
- 盲测 LRPPRC（缓存重放）：9 条无关试验不再被检索到；相关试验由 1 条变为 6 条（TTI-0102 和 5 个 Leigh 综合征登记 / 研究），原来被无关试验挤出了前 10。
- 3a–3e 验收全部通过（30/30、8/8、7/7、8/8、5/5）。

**审批**：B 类（排除原收入的试验），按盲测后修复计划 v1.0 已批准。测试：`tests/test_trial_abbrev.py`（24 条，含正反向）。

## 基因型类入组标准由代码对照病人基因型（2026-11-11，盲测后修复 D2 第 1 点，用户批准）

病人报告的基因型是已知事实。基因型类标准（`genetic_confirmation` / `variant` / `variant_class` / `zygosity`）里**写明了基因、且都不是病人的基因**时，判"不满足"，理由写"the criterion requires <基因>; the patient's reported variant is in <基因>"。基因符号须是 GenCC 收录的 HGNC 符号（Step 2 已下载的数据集）、整词、大小写一致。
**不由这条规则判定的**（保持原来的判断，通常为未知）：标准里没写基因（"genetic confirmation of CMT"）；写了病人的基因（"MPZ or PMP22"）；否定或不要求（"there will not be a requirement for confirmed CDKN2A/B deletion"）；肿瘤 / 体细胞语境（"Tumor positive for … BRAF alteration"）；"或"连接的选项里有一项是病名（"confirmed diagnosis of CDG or NGLY1 deficiency"——CDG 包含病人的 SLC35A2-CDG）。
**同一试验逐行列出的基因选项**（DEEPTYPE："mutation in SLC16A2" / "mutation in THRA" / "abnormal fT3/fT4 ratio"）：只要有一条基因型标准写了病人的基因，其余"要求别的基因"的行视为备选项，记 not_assessed（`ALTERNATIVE_GENE_NOTE`），不决定状态、也不列入缺失信息。
**起因**：盲测 MPZ 病人进了要求 PMP22 重复（CMT1A）的试验（判"有条件"）和 CMT4J 专用试验。
**现有账本离线扫描（未重跑）**：会改为"不满足"的——MPZ 的 NCT07140614（PMP22 ×2）、ELP-02（FIG4，CMT4J）、EQUIVIB-CMT（"PMP22 gene duplication"，该试验只收 CMT1A）；THRA 的 DEEPTYPE 中 SLC16A2 行按备选项处理。扫描中发现并加了守卫的误判：NF1 的否定句和肿瘤突变句、SLC35A2 的"CDG or NGLY1 deficiency"。
**D2 其余各点**：第 3 点（3c 先例病人的基因 / 亚型）由上下文核查完成；第 4 点（亚型专用试验）D1 修正诊断后由病名匹配自然排除，不另加规则；**第 2 点（多病种试验里挂在别的病种亚组下的标准）未做**——按架构原则 2（上下文核查完成后冻结新增的语义类代码规则），**2026-11-11 用户决定：不写代码规则，作为 3b 上下文核查清单中的一个问题处理**（3b 接入上下文核查时一并加测试集条目）。
**判定更正（2026-11-11）**：EQUIVIB-CMT 盲测时判"正确（一般性 CMT 试验）"，用户更正为写错——该试验只收 CMT1A。
**测试**：`tests/test_criteria_genotype.py`。

## 子型同时用上一级疾病名检索（2026-11-12 用户决定，2026-11-13 补正）
诊断是某病的具体亚型时，沿 MONDO 往上最多 3 级（OLS4 `parents`），名字去掉遗传方式词（familial / hereditary / inherited / autosomal / dominant / recessive / X-linked）后恰好是子型名开头的上级，加入检索名（`trial_searches.<分支>.parent_names`）；"运动神经元病"这类宽泛分组不会加入。只收其他基因的试验由基因型规则判不满足。属放宽。测试 `tests/test_trial_parent_names.py`。只收健康志愿者的试验：以病人报告的致病变异为"不满足"的依据（`tests/test_criteria.py`）。

## 诊断已确定时的诊断类与基因确诊类标准（2026-11-15 用户批准）
Step 2 主诊断已确定（resolved）、该分支基因带病人的变异、病人自己那条变异的 ClinVar 记录为致病 / 可能致病（`trial_records.confirmed`）时：入组条件点名本病（含其缩写）或其上一级疾病（"definitive diagnosis of Primary Hyperoxaluria"、"Documentation of PH1"）判满足；"基因确诊"类条件（没有点名其他基因）判满足；排除条件点名上一级疾病的其他亚型（"primary hyperoxaluria type 2 or type 3"）判不满足（不排除）。测试 `tests/test_criteria.py`。

## 多疾病诊断清单（2026-11-16，用户批准沿用诊断规则与满足其一分组）

- 同级相邻、逐行“Diagnosis of …”的入组疾病选项，按一个诊断清单送入既有 `combine` / `any_of`：满足任一诊断选项即满足该清单，不要求病人同时得全部疾病。分组引文保留登记原文的完整连续片段，每个选项保留原文与判断。显式要求同时满足的嵌套条目、and / both 及其他类型条件不按此分组；其他条件照常判断。
- 沿用已批准的确诊门槛；未确诊、或没有匹配到任何已知诊断时，不默认满足。RKSC 的“do not have A, B, C …”排除标准，在已确诊所列之一时不成立，而不是新增缺失诊断。
- ProRKS 的诊断选项、RKSC 的正反向诊断判断可由现有映射缓存直接重算，提示词不变。测试覆盖命中、未知、不相关诊断、明确要求同时满足、排除标准的反向情形。

## 已满足的诊断队列不再依赖其他队列（2026-11-16 三次审阅）

- 多个根级诊断队列各自带“one of the following”确认条件时，先在每个队列内判断必需项，再按满足其一合并队列，保留各队列完整原文与 all_of / any_of 判断。已有一个队列满足，其他队列的未知项不再挂到当前病人。显式要求并存疾病、没有诊断映射或缺确认资料时，不把未知默认成满足。
- “subtype (type 1, 2 or 3)”这种抽取片段，在完整标准明确对应本病、病人确诊子型又在原文列出的选项中时满足；未确诊或未列到该子型保持未知。原映射缓存不变；测试覆盖嵌套队列、分支、未知与未列子型。


## 缓存映射语境与年龄范围修正（2026-11-17，用户批准）

- 根因：注册原始条款的拆分完整；缓存 LLM 映射只摘了例外或残片，之后沿用父条款的 exclusion 类型。NCT06511349 的 bilirubin/Gilbert 与 INR/warfarin 放行例外随完整排除条款保留，整条无法可靠组合比较时为 unknown；不把放行部分单独当排除项。既往 / 当前治疗、妊娠等被截断条目恢复本条原文；恢复文本必须是登记来源（还原 Markdown 转义后）的连续逐字子串，不拼接、不改写，不改提示词或缓存键。
- 年龄规则统一在比较结果汇总处实施，不新增标题模式。文字年龄同一条目内所有边界同时满足时才确认 Inclusion met；其余为 Unable to assess。原年龄组识别保留为确认满足的辅助，不得产生 Known exclusion。只有 minimumAge / maximumAge 的结构化总范围可产生年龄排除；年龄未知仍为未知。病人年龄已知而所属组未确认时，缺的是分组判定，不把已知年龄列为缺失年龄。
- AGXT / NCT06839235（7 岁）及 CFTR / NCT06654752（15 岁）补真实缓存条款回归；另测总范围之外、年龄未知及已识别组全部不匹配，防止文字年龄排除回归。缓存预检对 15 例、186 个试验逐条对比 Known exclusions（含重复次数），新增为 0。正式缓存重跑后再次对比；有新增即停止，不自动放宽其他临床条件。


## 前言当前招募限制（2026-11-23 用户批准）

标题前所有非空区块保留为 enrollment_note；不得因是前言而跳过比较。对范围明确的当前招募限制，经原文、数字、比较符、单位核验后与患者硬事实比较；不满足的入组限制或满足的关闭招募限制生成 fail，有完整原句和来源 Evidence ID。任一共同硬条件 fail 优先于 unknown，试验分支必须为 not_applicable。普通正文年龄队列仍不能单独产生排除。

首版本仅确定性解析完整的显式当前年龄（年/月）或性别限制，复用既有核验、年龄换算和账本状态函数。旧正文模型缓存与提示词不改，前言单独处理。未解析队列、历史或条件语境、患者事实缺失均为未知，不猜范围、不默认通过。完整条款保留，unknown 不算医学验收通过。

PHYOX7 的当前招募前言 under 6 years 与 7-year-old 冲突；正文历史 6–11 岁队列通过不能覆盖该 fail。年龄未知病例保持 conditional；5 岁只通过此条，不表示整项试验适用。195 项相关离线测试、15 例账本自检通过；本轮 1 状态变化、9 详情变化，完整 current diff 和快照见 docs/experiments/step3b_enrollment_note_fix_20261123.md。基线未升级。


## 患者本人、亲属与替代队列（2026-11-23 用户批准）

诊断及基因确认条件须保留原始完整条款和父项主体。患者本人确诊或携带变异不能证明亲属确诊、亲属基因确认或家族史；缺明确亲属事实时保留 unknown。

本人和亲属仅在官方组／队列说明明确为替代人群、病种对应且不存在强制同时满足的正文约束时，引用完整组说明并复用 Ledger alternative 逻辑。已满足本人队列不被未知亲属队列阻塞；共同排除条件仍可产生 fail。不能根据列表顺序、模型标签或患者本人病名猜测 OR。未来检索保留 ArmGroupLabel/ArmGroupDescription，缺组说明时不默认存在替代关系。正文提示词与旧模型票不变。

Biobank 两例亲属行 pass→unknown，已有本人诊断队列仍 pass，添加明确来源的患者／亲属 alternatives；共同排除条款 unknown 保留，整项仍 conditional。209相关离线通过，对改前2详情、0状态变化；完整diff、快照和来源见 docs/experiments/step3b_biobank_subject_fix_20261123.md。基线未升级。

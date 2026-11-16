# 第 3.0 步：证据账本与公共基础（Evidence Ledger）

> 状态：**已验收**（2026-11-03，tag `step3.0-accepted`）。修订：4 个待定问题已决定（文末"已定决策"）；新增阴性结果证据（1.2 节）、
> "同一行动"判定规则（1.3 节）。
> 合并了 `docs/step3_contract_todo.md` 的全部事项；Notion 施工方案 7.4 节"3.0 证据账本要求"。

## 目的

Step 3 要为报告模板中 Summary 之外的 8 个章节分别找证据（3a–3e 五个子节点）。3.0 不检索任何章节的证据，
只定下它们共用的东西，让后面每个子节点"往同一个账本里记账"：

1. **证据账本**：统一的证据格式和校验规则。每条论断都能追到一条具体记录（URL / PMID / NCT / NBK / SPL setid）
   和其中逐字的原文片段，或者明确标为"推理"并列出它依据的其他证据。
2. **诊断分支**：Step 2 有歧义时，对排名前列的诊断（最多 3 个）分别建分支，证据标明适用于哪些分支，
   报告据此写条件语句；伞状概念先展开到具体疾病。
3. **病人背景**：直接沿用 Step 1 的变异事实和 Step 2 的病人事实，不重新提取；登记"缺了会改变建议的病人信息"。
4. **基因特有规则层**：带文献出处的基因级规则（第一批：DMD 读码框、SPTLC1 表型与变异区域）。
5. **数据新鲜度**：按数据源设置 HTTP 缓存过期时间；ClinicalTrials.gov 最多 1 天，正式生成报告前强制刷新。

类比：3.0 是数据库的表结构和约束（schema + constraints），3a–3e 是往表里写数据的各个服务。

## 输入

| 来源 | 用到的字段 |
| --- | --- |
| `out/step1/<id>.json` | `variant_class`、`nmd`、`exon`、`ptc_aa_position`、`fraction_of_protein_retained`、`retranslation`、`structure`、`allelic_state`、`mechanism_hypothesis`（只作背景，不当结论） |
| `out/step2/<id>.json` | `primary`（status、id、alternatives、confidence、reasons）、`candidates`（MONDO / OMIM / Orphanet、`validity`、`inheritance`、`clinvar_info`、`phenotype.score`）、`phenotypes`、`patient_facts`、`patient_onset`、`genereviews`、`clinvar` |
| 病例 JSON | `clinical_context`（只用于核对引用，不再提取） |

两份上游输出都通过 `runmeta` 校验来源指纹，过期就报 STALE（沿用现有机制）。

## 输出：EvidenceLedger（每个病人一份，`out/step3/<id>.json`）

```json
{
  "schema_version": "evidence-ledger-v3",   // v2（2026-11-03）：要求结果新增 not_assessed；v3（2026-11-04）：要求行可带 alternative（任一组满足即适用，见 1.4）
  "patient_id": "AITX-40003",
  "branches": [ ... ],            // 诊断分支，见第 2 节
  "patient_context": { ... },     // 第 3 节
  "missing_information": [ ... ], // 第 3 节
  "rules_applied": [ ... ],       // 第 4 节
  "evidence": [ ... ],            // 第 1 节；3.0 只写背景类证据，3a–3e 往里加
  "sections": {                   // Summary 之外的 8 个章节 -> 证据 id 列表；3.0 全部为空
    "existing_targeted_therapies": [], "supportive_management": [], "contraindications_precautions": [],
    "clinical_trial_eligibility": [], "off_label_expanded_access": [],
    "bespoke_therapies": [], "drug_repurposing": [], "outcome_measures_ranking": []
  },
  "checks": [ ... ],
  "_meta": { ... }                // runmeta：输入指纹、上游指纹、代码版本
}
```

## 1. 证据条目（evidence item）

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `id` | 稳定编号：来源 id + 论断 + 适用分支 的哈希前 12 位 | 同一证据重跑得到同一 id |
| `kind` | `sourced`（有来源原文）/ `reasoning`（推理）/ `negative`（查过但没找到，见 1.2） | 见下 |
| `claim` | 一句话论断（英文，报告语言）；查看页面另显示中文说明 | 不能为空 |
| `section` | 模板章节之一，或 `background`（诊断、变异机制等背景，不单独成为报告里的行动） | 枚举 |
| `tier` | `established` / `emerging` / `hypothesized` / `background`，由 `section` 决定，不单独指定 | 代码推出 |
| `action` | 标准化的行动键，按 1.3 节规则生成（如 `drug:rxcui:<成分编号>`、`trial:NCT<8 位数字>`、`aso_exon_skipping:DMD|exon51`）；背景和阴性证据为 null | 见 1.3 |
| `applies_to` | 适用的诊断分支 id 列表；适用于全部分支时写全 | 必须是本账本 `branches` 的子集 |
| `source` | `{type, id, url}`；type ∈ url / pmid / nct / nbk / spl_setid / clinvar_vcv / omim / mondo / orphanet / hpo / refseq / alphafold / clingen / pipeline_fact | `sourced` 必填；id 必须符合该类型的格式 |
| `quote` | 来源原文中**逐字**的片段，支撑这条论断 | `sourced` 必填，由代码在抓取到的原文里核对 |
| `quote_verified` | 代码核对结果 | false 的条目不能进入任何章节 |
| `accessed_at` | 来源实际抓取时间（Unix 秒，取 HTTP 缓存记录的真实访问时间） | `sourced` 必填 |
| `premises` | `reasoning` 依据的证据 id 列表 | `reasoning` 必填，且都必须存在、已核对 |
| `conditions` | 适用条件：`[{variable, op, value, patient_value, known}]`，如 `age_years >= 9` | 用于写条件语句（见第 3 节） |
| `produced_by` | `code` 或 `{llm: 模型名, served_model, prompt_version}` | LLM 产出必须记录服务端实际模型名 |
| `retrieved_by` | 产生它的模块和查询（如 `3b ctgov query=...`） | 便于复现 |
| `status` | `candidate` / `verified` / `rejected`（附原因） | 只有 `verified` 能进章节 |

**规则：**

1. **来源只能来自代码抓取**。LLM 可以从代码给出的原文里摘句子、写 `claim`，但不能提出来源、URL 或编号
   （与 Step 2 "LLM 只选、编号由代码给"同一原则）。
2. **引用必须逐字**：`quote` 在该来源的已抓取原文中逐字存在（大小写和空白规范化后比较），否则 `rejected`。
3. **推理也要有据**：`reasoning` 条目的每个前提必须是本账本中已核对的证据；推理本身记录 `produced_by`。
   Step 1 / Step 2 的确定性事实（如"新终止落在最后一个外显子"）作为 `sourced` 证据入账，来源是 RefSeq / HPO 等记录，
   引用的是结果文件里的字段值（类型 `pipeline_fact`，指向 `out/stepN` 的字段路径和上游数据源）。
4. **同一行动只放一个章节**：同一 `action` 在不同 `section` 出现时，3.0 的校验报 fail；
   放哪个章节由分层规则决定（已获批 → 已确立；有人类用药先例 → Off-label；无先例只有机制 → Drug Repurposing；
   已获批且针对该变异的 ASO 不得出现在 Bespoke）。分层规则在 3a–3e 里实现，3.0 只做唯一性校验。
5. **"写错比不写更糟"**：任何一项校验不过的证据只能是 `candidate` 或 `rejected`，不会进章节；
   宁可章节为空，并用阴性结果证据说明"查了哪里、怎么查的、没找到"（1.2 节）。

### 1.2 阴性结果证据（`kind = negative`）

记录"查过但没找到"，对应评分的**完整性**维度：报告里某章节写"无"时，必须引用这类证据，说明查了什么。

| 字段 | 含义 |
| --- | --- |
| `section`、`applies_to` | 这次检索针对的章节和诊断分支 |
| `search.database` | 数据源（如 `clinicaltrials.gov`、`pubmed`、`dailymed`、`chembl`） |
| `search.endpoint` | 实际请求的 URL（含参数） |
| `search.query` | 发出的检索词原文（逐字，与请求一致） |
| `search.filters` | 过滤条件（如招募状态 RECRUITING / NOT_YET_RECRUITING、物种、语种） |
| `search.queried_at` | 实际查询时间（Unix 秒，取 HTTP 缓存记录的真实请求时间） |
| `search.n_results` | 数据源返回的记录数（代码从响应里读出，不是 LLM 填写） |
| `search.n_excluded` / `excluded` | 返回了记录、但逐条排除时：排除的记录 id 和排除理由（每条理由本身是证据） |
| `claim` | 一句英文陈述，如 "No recruiting or not-yet-recruiting trials for SPTLC1 or HSAN1 were found on ClinicalTrials.gov (searched 2026-11-03)." |

**规则：**

1. 阴性证据**只由代码生成**，来自真实的检索记录；LLM 不能写阴性证据，也不能改 `n_results`。
2. `n_results` 必须与缓存里那次响应的记录数一致（代码核对）；`queried_at` 必须是那次请求的真实时间。
3. **某章节对某分支没有任何 `verified` 行动时，该章节对该分支至少有一条 `verified` 的阴性证据**，否则校验 fail
   （报告不能在没有检索记录的情况下写"无"）。
4. "找到了但都不适用"（如试验找到 3 个、病人都不符合）不是"没找到"：每个试验各自作为证据入账并写明不符合的入组条件；
   阴性证据只汇总检索本身（`n_results = 3`，`n_excluded = 3`，`excluded` 指向那 3 条证据）。
5. 有缓存过期要求的数据源（ClinicalTrials.gov 1 天），阴性证据随缓存一起过期，正式生成报告前重新检索。

### 1.3 "同一行动"的判定（`action` 键）

同一行动只能出现在一个章节（规则 4）。为此每个行动先标准化成一个键，**键相同即视为同一行动**，与写法、商品名、剂量无关。

| 行动类别 | 键 | 判定规则 |
| --- | --- | --- |
| 药物（已上市） | `drug:rxcui:<成分 RxCUI，多成分按数字排序后用 + 连接>` | 名称按顺序解析到**成分**（RxNorm TTY = IN）：① RxNav 按名称精确查找，得到的概念（含 MIN 复方、PIN 盐形式、SCD / SBD 产品）展开到成分；② 查不到时用 openFDA 药品说明书把**美国商品名**换成通用名，再走 ①；③ 都查不到再看下一行。商品名与通用名同键；剂量、给药途径、方案不同仍同键（具体剂量写在 `claim` 里）；**复方与单方不同键**（成分集合不同） |
| 药物（无 RxNorm，如研发中的化合物） | `drug:chembl:<ChEMBL 母体分子编号，多成分同上>` | 用 ChEMBL 的 parent molecule（盐归到母体）。只有 RxNorm 查不到时才用 ChEMBL，保证同一药物总得到同一种键 |
| 药物（都查不到） | `drug:name:<标准化通用名>`，`normalized = false` | **兜底键**（2026-11-03 审阅修改）：名称转小写、去掉标点和多余空白、去掉盐型后缀（hydrochloride、hcl、sodium、potassium、calcium、magnesium、sulfate / sulphate、mesylate、maleate、acetate、citrate、tartrate、phosphate、succinate、besylate、fumarate、bromide、chloride 等受控列表），复方按 `/`、`+`、`,`、`and` 拆开后排序用 `+` 连接。**允许进入报告章节**，但证据记录 `normalized: false`，查看页面显示"未标准化"警告。理由：只在欧洲等地上市的药、早期研发化合物可能查不到编号，全部挡掉会损害完整性 |
| 临床试验 | `trial:NCT<8 位数字>` | 按 NCT 编号 |
| 非药物疗法 | `<类型>:<靶点>[|<限定>]` | 类型取自受控列表（下表）；靶点：分子类疗法用 HGNC 基因符号，器官类用器官名（受控列表），饮食和对症措施用受控的方案名；位置特异的策略加限定（外显子号、变异 c. 写法） |
| 实现某种策略的药物 | 主键是 `drug:…`，另加 `implements: <策略键>` | 如 eteplirsen 的 `implements = aso_exon_skipping:DMD|exon51`。唯一性校验**同时比较主键和 implements**，所以"已获批的外显子 51 跳跃 ASO"在 Existing Targeted、"可开发的外显子 51 跳跃 ASO"在 Bespoke 会被判为同一行动 |

非药物疗法的类型（受控列表，扩充需改代码并补测试）：
`aso_splice_modulation`、`aso_exon_skipping`、`aso_knockdown_allele_specific`、`aso_knockdown_total`、`sirna`、
`gene_replacement`、`base_editing`、`prime_editing`、`gene_editing_other`、`cell_therapy`、`organ_transplant`、
`diet`、`procedure`、`supportive_measure`。

**单元测试用例**（离线，RxNav / openFDA / ChEMBL 响应用录好的固定数据；表中编号均于 2026-11-03 用真实接口核对过）：

| # | 输入 A | 输入 B | 期望 |
| --- | --- | --- | --- |
| 1 | Trikafta | elexacaftor / tezacaftor / ivacaftor | 同一行动（Trikafta 不在 RxNorm 名称里，经 openFDA 换成通用名；复方 MIN 2257010 → 成分 1243041 + 1999382 + 2256951） |
| 2 | Trikafta | ELEXACAFTOR/IVACAFTOR/TEZACAFTOR（顺序、大小写不同） | 同一行动 |
| 2b | Kaftrio（欧洲商品名） | — | 兜底键 `drug:name:kaftrio`，`normalized = false`，可进章节（RxNorm、openFDA、ChEMBL 都查不到，2026-11-03 实测） |
| 3 | Trikafta | ivacaftor（Kalydeco） | 不同（复方 ≠ 单方） |
| 4 | Oxlumo | lumasiran | 同一行动（RxCUI 2467154 → 成分 2467140） |
| 5 | lumasiran | nedosiran | 不同 |
| 6 | pyridoxine hydrochloride | pyridoxine | 同一行动（盐归到成分：RxCUI 203164 → 成分 684879） |
| 7 | lumasiran 3 mg/kg monthly | lumasiran quarterly | 同一行动（剂量方案不影响） |
| 8 | trial NCT01234567 在两个章节 | — | 校验 fail |
| 9 | eteplirsen（Existing Targeted） | 外显子 51 跳跃 ASO（Bespoke） | 同一行动（implements），校验 fail |
| 10 | 外显子 51 跳跃 ASO | 外显子 53 跳跃 ASO | 不同（限定不同） |
| 11 | SPTLC1 等位基因特异敲低 | SPTLC1 整体敲低 | 不同（类型不同） |
| 12 | liver transplantation | combined liver–kidney transplantation | 不同（靶点器官集合不同） |
| 13 | 查不到的研发代号 "ABC-123 hydrochloride" | "abc-123" | 同一行动（兜底键都是 `drug:name:abc-123`，`normalized = false`） |
| 13b | 查不到的 "Foo sodium / Bar" | "bar + foo" | 同一行动（去盐型、拆复方、排序：`drug:name:bar+foo`） |
| 13c | 兜底键 `drug:name:kaftrio` 在两个章节 | — | 校验 fail（兜底键同样参与唯一性校验） |
| 13d | 兜底键药物进入章节 | — | 允许，`normalized = false`；查看页面显示"未标准化"警告 |
| 14 | 同一药物在同一章节有两条证据（两个来源） | — | 允许（同一行动多条证据） |

### 1.4 行动记录（`actions`，行动看板用；3a 起每个子节点必须填写）

Step 3 完成后，查看页面以"行动看板"为主视图（树状图保留为折叠的全景目录）。为此账本里每个行动除证据条目外，
还有一条行动记录（2026-11-03 审阅补充；看板页面在 Step 3 全部完成后再做）：

| 字段 | 含义 |
| --- | --- |
| `action_key` | 1.3 节的行动键；`searched_none` 行为 null |
| `section`、`label` | 所属章节；显示名（英文，如 "Lumasiran"） |
| `applies_to` | 适用的诊断分支（有歧义时看板并排对比各分支） |
| `status_by_branch` | 每个分支一项：`{status, reason}`。status ∈ `applicable` / `not_applicable` / `conditional` / `searched_none`；reason 是一句简短英文理由（如 "approved only for age ≥ 9"） |
| `requirements` | 条件核对，**每条要求一行**（临床试验的入组、排除标准逐条拆开）：`{id, kind: inclusion / exclusion / label_condition / other, requirement: 要求原文（逐字）, requirement_evidence: 证据 id, applies_to, patient_fact: {field, value, quote, step} 或 null, patient_status: satisfies / does_not_satisfy / unknown / not_assessed, result: pass / fail / unknown / not_assessed, note}` |
| `evidence_ids` | 支撑这个行动的证据条目 |

**规则（3.0 的校验，第 8 节）：**

1. `requirement` 必须逐字出现在 `requirement_evidence` 那条已核对证据的引用里（要求原文可追溯到说明书、试验登记记录等）。
2. `patient_fact` 只能来自 Step 1 / Step 2 的结果，带原文引用；病例没写的事实为 null，`patient_status = unknown`。
3. `result` 由代码推出，不由 LLM 填：入组 / 说明书条件 / 其他要求 `satisfies → pass`、`does_not_satisfy → fail`；
   **排除标准反过来**：`satisfies → fail`（病人符合排除标准即不合格）、`does_not_satisfy → pass`；`unknown → unknown`。
   `not_assessed → not_assessed`（账本 v2，3b 契约决定 2）：试验的行政类条目（知情同意、依从性、能按时随访），留给试验筛选时评估；
   只用于入组 / 排除条目，`note` 必须是 "screening assessment"，`patient_fact` 为 null。
4. 状态与逐条结果一致：某分支下有任何 `fail` → `not_applicable`；没有 `fail` 但有 `unknown` → `conditional`；
   全部 `pass`（或没有要求）→ `applicable`；`not_assessed` 不参与计算；`searched_none` 只用于没有找到行动的章节，必须引用阴性证据（1.2 节）。
5. 结果为 `unknown` 的要求（`not_assessed` 不算），其 `patient_fact.field` 必须登记在 `missing_information` 里（Summary 的缺失信息由此生成）。
6. `applies_to`、`status_by_branch` 的键都必须是本账本的分支；`status_by_branch` 覆盖 `applies_to` 的每个分支。

## 2. 诊断分支（branches）

| Step 2 状态 | 分支 |
| --- | --- |
| `resolved` | 1 个分支：首选诊断 |
| `ambiguous` | 首选 + `alternatives`，按 Step 2 顺序，**最多 3 个** |
| `unresolved` | 1 个"基因级"分支：只用基因和变异事实，不假定具体疾病；报告里明说诊断未定 |

每个分支：`{id, role: primary | ambiguous_N | gene_level, diagnosis: {mondo, label, omim[], orphanet[]}, gene,
why: Step 2 的理由, step2_score, specific: bool, expanded_from}`。

**伞状概念展开**：分支对应的疾病没有 OMIM 编号，或在 Step 2 被标为归类概念（`specific = false`）时，
展开到 Step 2 已记录的、与本基因关联的下级具体疾病（候选的 `merge.narrower_competing`，这些下级本身就在候选表里，带 OMIM 和分数），
不另调外部接口；没有下级可展开时保留原分支并注明"无法展开"。展开结果替换原分支并记录 `expanded_from`；展开后仍超过 3 个分支时，按 Step 2 分数取前 3 个，其余列入 `branches_dropped` 并说明原因。
例：AITX-40003 的"juvenile amyotrophic lateral sclerosis"（MONDO:0017593，无 OMIM，Step 2 标为 specific）
的 `merge.narrower_competing` 是 ALS27（MONDO:0859529，OMIM 620285），应展开到 ALS27。

**证据与分支**：每条证据的 `applies_to` 写明适用的分支。只适用于部分分支的行动，报告写成条件语句
（"If the diagnosis is X, then …"）。适用于全部分支的写成不带诊断条件的行动。

**分支裁决**（已定）：**不删除任何分支**，也不修改 Step 2 的输出。基因特有规则（第 4 节）可以影响分支的**排序和措辞**：
3.0 记录 `branch_assessment: [{branch, rule_id, effect: supports | argues_against, evidence_ids}]`，
并据此给出 `branch_order`（有规则支持的分支排前，同等时按 Step 2 顺序）；报告可写"文献证据更支持 X"并附出处，
但所有分支保留，各分支的条件语句照写。

**规则提拔分支**（2026-11-03 审阅修改）：规则支持的疾病若不在分支里，可以提拔它成为分支，条件全部满足才提拔：
1. 该疾病在 **Step 2 的候选集合**中（候选表里有、未被排除）；规则只能指向候选集合，不能引入新疾病；
2. 支持它的规则已加载（来源引用核对通过、未被否决、内容未被改动）；
3. 仍受**最多 3 个分支**限制：已满 3 个时不提拔，记录 `promotion_blocked`（原因：分支已满），**不删除原有分支**；
4. 账本记录 `promoted_by: <规则 id>`，分支理由写明"由规则提拔"及规则陈述；提拔先于背景证据入账，提拔出的分支同样获得诊断背景证据。

验收用例：练习病例 PRAC-DMD-del（框内缺失）。如果读码框规则成立，贝克型（OMIM 300376）应作为分支出现，且杜氏型分支仍保留。

## 3. 病人背景与缺失信息

`patient_context` 直接复制上游字段并保留引用：年龄（月）、性别、起病（HPO 起病术语和区间）、变异来源、家族史、
症状（HPO，存在 / 排除）、每个变异的 Step 1 事实摘要。**不重新调用 LLM 提取。**

`missing_information`：会改变建议、但病例里没有的病人信息登记表：`[{variable, why_it_matters, affects: [evidence ids], asked_by}]`。
3.0 定格式并登记通用项（如年龄未知、性别未知、变异来源未知）；3a–3e 在发现条件时追加（如胎龄、体重、肝肾功能）。
`conditions` 中 `known = false` 的变量必须出现在此表里，Summary 的"Missing information"由它生成。

## 4. 基因特有规则层

规则是**数据，不是代码**：`data/rules/<GENE>.json`，每条规则：

```json
{"id": "DMD-reading-frame-1", "gene": "DMD", "version": 1,
 "applies_when": {"variant_class": ["inframe_deletion"], "...": "条件只用 Step 1 字段"},
 "statement": "In-frame deletions in DMD are usually associated with Becker rather than Duchenne muscular dystrophy",
 "effect": {"type": "diagnosis", "supports": ["OMIM:300376"], "argues_against": ["OMIM:310200"]},
 "exceptions": "已知例外原文（如有）",
 "sources": [{"type": "pmid", "id": "...", "quote": "逐字原文", "quote_verified": true, "accessed_at": 0}],
 "strength": "established | reported | weak",
 "status": "draft | verified"}
```

**规则：**

1. 每条规则至少一个来源，且 `quote` 由代码在抓取到的摘要或全文中逐字核对；核对不过的规则不加载。
2. 规则必须写成**基因级的通用陈述**，条件只引用 Step 1 的变异事实（变异类型、位置、读码框、所在区域），
   不能写成针对某个病例的结论；不能从评测病例的"期望答案"反推规则。
3. 规则生效时产生 `background` 证据（来源即规则的文献）和 `branch_assessment`，并可按第 2 节"规则提拔分支"的条件提拔分支；
   结果只汇报，不据此调分数或阈值。**强度为 weak 的规则只作背景证据**，不参与分支排序和提拔（2026-11-03 决定）。
4. **第一批规则（3.0 内完成调研）**：
   - **DMD 读码框**：框内缺失倾向 Becker、移码倾向 Duchenne，包括已知例外（读码框规则的符合率）。练习病例 PRAC-DMD-del 是验证用例。
   - **SPTLC1 表型与变异区域**：HSAN1 与 ALS27 的致病变异是否分布在蛋白不同区域，Leu39 落在哪个区域。
     **如果文献不支持"区域决定表型"，就记录为"查过、不成立"（带出处），不建规则。**
     Step 1 的 AlphaFold 事实（pLDDT、RSA、邻居）只作背景，区域划分以文献为准。
5. **规则由系统起草，人只能否决**（已定）：
   - 范围：对 Step 2 候选疾病涉及的**所有基因**执行同一调研流程，不只评测基因。
   - 流程：代码按基因和候选疾病检索 PubMed / GeneReviews → LLM 只从抓取到的原文中摘出候选规则和逐字引用 → 代码核对引用和条件格式 →
     通过的规则 `status = verified`，写入 `data/rules/<GENE>.json`。
   - 人工审查只能否决，不能改写内容。否决时在规则文件里记录 `review: {decision: "vetoed", by, at, reason}`，被否决的规则不加载但保留在文件中；
     未否决的规则 `review.decision = "not_reviewed"` 或 `"accepted"`。
   - 每条规则记录起草所用的检索（数据源、检索词、时间、返回数量）和 LLM 的服务端模型名、提示词版本，可复现。
   - **自动支持度核查**（2026-11-03 审阅补充）：每条规则起草后，用一次独立的 LLM 调用（`aitx/evidence/support_check.py`，
     通用模块，Step 5 复用）逐项判断引用原文是否支持该规则的每个条件、结论和适用范围（supported / partially_supported /
     not_supported；总体结论由代码汇总：全部 supported 才算支持）。不完全支持的规则 `status = pending_review`，不加载，
     汇报给审阅人；审阅人可以否决，或写明理由后接受（`review.decision = "accepted"`），但不能改内容。
     规则与审阅的对应按内容身份（陈述、条件、结论、引用）匹配，重新起草不会丢失审阅结论。
     反向测试：被人工否决的 NF1-1、CFTR-1 必须被核查独立拦下（验收硬性项）。
   - **核查的维护方式：提示词稳定 + 测试集积累**（2026-11-03 决定）：
     · 核查提示词只含几条通用判定原则（只依据原文；条件可以是原文的特例、不能更宽；结论强度不得超过原文——比例差异不能推出排除或偏好、
       个例不能推出一般规律、相关不能推出因果；病名可用标准名或同义词），带版本号；不再为个别规则增加专门语句，也不放示例。
     · 判定方式：条件合为一项；每条独立核查 3 次，每项 3 次全为 supported 才算支持。
     · 回归测试集 `data/eval/support_check_regression.json`：所有人工审阅过的规则（接受 → 应支持，否决 → 应拦下，附理由）
       自动收录（起草脚本、3.0 验收运行时），只追加不删除；测试集用例不得出现在提示词中（自动检查）。
     · 改提示词或判定方式前，先跑 `scripts/eval_support_check.py`，报告准确率、误放（应拦下却放行）、误拦（应支持却拦下）；
       误放比误拦严重，任一变差即不采用。验收硬性项：回归集误放为 0。
     · 记录：v4（含两个具体示例）7 例准确率 0.857、误放 0、误拦 1（DMD-1）；v5（只留通用原则）结果相同，采用 v5。

## 5. 数据源与缓存

| 数据源 | HTTP 缓存过期 | 说明 |
| --- | --- | --- |
| RxNav、openFDA、ChEMBL（行动标准化，1.3 节） | 不过期 | 提交时统一冻结 |
| ClinicalTrials.gov API v2 | **1 天** | `--refresh-trials` 强制重新抓取；正式生成报告前必须带此参数，证据记录实际访问时间 |
| 其他（PubMed、GeneReviews、DailyMed、FDA、ClinVar、OLS4、HGNC、UniProt、AlphaFold 等） | 不过期 | 提交时统一冻结 |
| 整包数据（HPO、GenCC、ClinGen、Orphanet 等） | 7 天刷新（现状） | 提交时固定 `AITX_DATASET_SNAPSHOT` |

实现：`aitx/http.py` 增加按 URL 前缀匹配的过期表（`max_age`），过期即重新抓取并覆盖；缓存条目已有 `accessed_at`，
证据的 `accessed_at` 一律取它（缓存命中时是当初真实抓取的时间，不是本次运行时间）。
提交时 HTTP 缓存、LLM 缓存随提交保存，数据源清单附快照日期。LLM 缓存规则沿用 Step 2（键含模型、地址、提示词版本、正文、抽样序号）。

## 6. 3.0 自身产出的证据

3.0 不做章节检索，只把已有的确定性事实入账，作为后续推理的前提（全部 `section = background`）：

- 诊断：每个分支的 MONDO / OMIM 记录、Step 2 的选择理由和置信度（来源：MONDO / OMIM / ClinGen / GenCC 记录）。
- 变异：Step 1 的类型、NMD 结论及理由、外显子、截短位置、自检 6 结果、AlphaFold 事实（来源：RefSeq、AlphaFold）。
- ClinVar：精确匹配记录（含冲突记录及其关联疾病，`clinvar_info`），作为背景传给报告。
- GeneReviews：每个分支对应的章节链接（NBK），供 3a 检索管理章节。
- 规则：第 4 节生效的规则。

## 7. 查看页面接入

证据树取代现在 `build_viewer.evidence_tree()` 的预留结构，层级不变：
**诊断分支 → 证据层级 → 章节 → 行动 → 证据叶子**（claim、quote、来源链接、访问时间、applies_to、状态）。
3.0 完成时树里只有分支和背景证据；每个 3a–3e 子节点验收时，其证据必须能在树里看到（Notion 7.4"可视化接入"）。
页面只展示，不计算。

## 8. 校验（`checks`，每份账本都跑）

| 校验 | 不过则 |
| --- | --- |
| schema：字段齐全、枚举合法、`tier` 与 `section` 一致 | fail |
| `sourced` 证据：来源 id 格式合法、有 `accessed_at`、`quote_verified = true` | 该条 `rejected` |
| `reasoning` 证据：前提都存在且已核对 | 该条 `rejected` |
| `applies_to` ⊆ `branches` | fail |
| 同一行动不跨章节（主键或 `implements` 相同即同一行动，1.3 节） | fail |
| 药物行动有键；用兜底键的标 `normalized = false`（查看页面警告，不阻止进章节） | warn |
| 某章节对某分支没有 verified 行动时，有 verified 的阴性证据 | fail |
| 阴性证据的 `n_results` 与缓存响应一致、`queried_at` 为真实请求时间 | 该条 `rejected` |
| 被否决的规则没有被加载 | fail |
| 行动记录：要求原文可追溯、`result` 与 `patient_status` / `kind` 一致、各分支状态与逐条结果一致、未知事实已登记为缺失信息、分支键合法（1.4 节） | fail |
| `conditions` 中未知变量都在 `missing_information` 里 | fail |
| 伞状分支已展开或注明无法展开 | fail |
| 加载的规则都有核对过的来源 | 该规则不加载，记 warn |
| LLM 产出记录了服务端模型名和提示词版本 | fail |
| 上游输出指纹一致（runmeta） | STALE |

## 9. 验收标准

**离线测试**：账本 schema；引用核对（假来源原文，正例和反例）；1.3 节的 14 个"同一行动"用例；
阴性证据（`n_results` 与响应不一致 → rejected；章节为空且无阴性证据 → fail；"找到但都不适用"按规则 4 记录）；
规则文件（被否决的不加载、否决理由必填、人工不能改内容即 `review` 之外的字段与系统起草版本的哈希一致）；`id` 稳定；分支构建（resolved / ambiguous / unresolved，
最多 3 个，伞状展开，展开后超过 3 个的截断）；`applies_to` 子集校验；同一行动跨章节报错；规则加载器拒绝无来源 / 引用不符的规则；
规则条件只读 Step 1 字段；HTTP 缓存过期（ClinicalTrials.gov 1 天，其他不过期，`--refresh-trials` 强制刷新）；
`accessed_at` 取缓存里的真实抓取时间。每个修复照旧补测试并做反向验证。

**联网验收（`scripts/acceptance_step3_0.py`）**：

| 层级 | 标准 |
| --- | --- |
| 硬性 | 18 个病例都生成账本，全部校验通过；`--from-step 3` 能复用 Step 1/2 输出 |
| 硬性 | 分支：COL1A1、DMD 等 ambiguous 练习病例分支数 = min(候选数, 3)；有伞状概念的分支都已展开或注明原因 |
| 硬性 | 背景证据的引用 100% 逐字核对通过；来源链接可解析（HTTP 200 或已知的需登录页）。PubMed 链接改用 NCBI 官方 E-utilities（esummary）确认记录存在（2026-11-04 起）：PubMed 网站对所有自动化访问启用了 Cookie / 人机验证页面（HTTP 203），验收不绕过它；报告里仍使用 pubmed.ncbi.nlm.nih.gov 网址；其他网站仍要求 HTTP 200。只重查链接：`python3 scripts/acceptance_step3_0.py --links-only`（读取上次完整运行保存的账本，不调用 LLM） |
| 硬性 | 第一批规则：加载的每条规则都有核对过的文献引用；DMD 读码框规则在 PRAC-DMD-del 上生效，贝克型被提拔为分支、杜氏型分支保留（若规则调研结论为不成立，则改为汇报，不算通过） |
| 硬性 | ClinicalTrials.gov 缓存过期和强制刷新在真实 API 上验证一次 |
| 人工审查 | 查看页面上每个病例的证据树（分支 + 背景证据）；40003 的分支展开结果和 SPTLC1 调研结论（**只汇报，不据此调参**） |

## 10. 不在 3.0 范围

章节检索与判断（3a–3e）、报告写作（Step 4）、论断是否被来源支持的语义核查（Step 5）。

## 已定决策（2026-11-03 审阅）

1. **基因特有规则由系统起草**：对 Step 2 候选疾病涉及的所有基因执行同一流程；人只能否决，否决理由写入规则文件（第 4 节规则 5）。
2. **不删分支**：规则只影响分支排序和措辞（"文献证据更支持 X"并附出处），所有分支保留，条件语句照写（第 2 节）。
3. **保留基因级分支**：Step 2 为 `unresolved` 时建一个只用基因和变异事实的分支。
4. **`claim` 用英文**，查看页面另配中文说明。
5. 审阅补充：**阴性结果证据**（1.2 节）；**"同一行动"按标准化标识判定**（1.3 节）。
6. 药物查不到编号时用**标准化通用名兜底键**，`normalized = false`，允许进章节、页面警告（1.3 节）。
   已知局限：查不到的商品名（如 Kaftrio）无法换成通用名，与其通用名的键不同，跨章节重复时唯一性校验发现不了；靠页面警告提醒人工留意。

## 跨章节可能重复的标记（2026-11-11，盲测后修复 N3）

账本新增 `possible_duplicates`：在 3a 三节与 3c 之间，**同一行动键**出现在两节，或**同一来源**里两条标签的实词一条包含另一条、且中心词相同（"UV-blocking sunglasses" / "UV-A and UV-B blocking sunglasses"），记为可能重复（kind `cross_section`）。**只标记，不删除**，由 Step 4 只写一次并交叉引用。现有账本离线扫描：SNRNP200 墨镜（真重复）；NF1 "radiotherapy" 两节同名、OTC "glycerol phenylbutyrate" / "phenylbutyrate"（不同产品，误标）——由 Step 4 审阅。测试：`tests/test_duplicates.py`。

## 半合子性别推断（2026-11-16，用户批准）

病例原文明写性别时以原文为准。仅在原文性别未知、HGNC 明确基因位置在 X 染色体、Step 1 合子状态为 hemizygous 时推断男性。常染色体基因、其他合子状态或染色体位置未知均不推断。原始 Step 2 事实保持原文提取结果；Step 3 把合子状态和 HGNC 位置作为已验证前提，另记 reasoning 证据，病人上下文和条件引用标记为推断，不能冒充原文。

支持核查“假拦 3/17”不是本轮新增：`out/archive/step3-fix-accepted-20261115/acc_acceptance_step3_0.log` 已有同样结果。三条为 DMD-1（读码框的结论 / 范围被过严判定）、CLAIM-GEMIN5-COQ10（未把上下文中的病人身份连到改善结论）、CLAIM-RRM2B-VALPROATE-CORRECT（未把“限于例外”与病种 / 一般避免的上下文连接）。本轮不改其提示词或决策方法。

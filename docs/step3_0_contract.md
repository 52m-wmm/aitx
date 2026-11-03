# 第 3.0 步：证据账本与公共基础（Evidence Ledger）

> 状态：**草稿，待审**（2026-11-03）。审定后才写代码。
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
  "schema_version": "evidence-ledger-v1",
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
| `kind` | `sourced`（有来源原文）/ `reasoning`（推理） | 见下 |
| `claim` | 一句话论断（英文，可直接进报告） | 不能为空 |
| `section` | 模板章节之一，或 `background`（诊断、变异机制等背景，不单独成为报告里的行动） | 枚举 |
| `tier` | `established` / `emerging` / `hypothesized` / `background`，由 `section` 决定，不单独指定 | 代码推出 |
| `action` | 可执行的行动键（如 `drug:lumasiran`、`trial:NCT01234567`、`strategy:exon_skipping_aso`）；背景证据为 null | 见"同一行动只放一个章节" |
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
   宁可章节为空并说明"查了哪里、没找到"（这类说明也作为证据入账，`kind = reasoning`，前提是检索记录）。

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

**分支裁决**：基因特有规则（第 4 节）可以支持或排除某个分支，但**不修改 Step 2 的输出**。
3.0 只记录 `branch_assessment: [{branch, rule_id, effect: supports | argues_against, evidence_ids}]`；
分支是否删除由报告阶段按证据强度写成措辞（"favours X"），不在 3.0 里硬删。

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
3. 规则生效时产生 `background` 证据（来源即规则的文献）和 `branch_assessment`；结果只汇报，不据此调分数或阈值。
4. **第一批规则（3.0 内完成调研）**：
   - **DMD 读码框**：框内缺失倾向 Becker、移码倾向 Duchenne，包括已知例外（读码框规则的符合率）。练习病例 PRAC-DMD-del 是验证用例。
   - **SPTLC1 表型与变异区域**：HSAN1 与 ALS27 的致病变异是否分布在蛋白不同区域，Leu39 落在哪个区域。
     **如果文献不支持"区域决定表型"，就记录为"查过、不成立"（带出处），不建规则。**
     Step 1 的 AlphaFold 事实（pLDDT、RSA、邻居）只作背景，区域划分以文献为准。
5. 谁来起草规则：见文末"待定问题 1"。

## 5. 数据源与缓存

| 数据源 | HTTP 缓存过期 | 说明 |
| --- | --- | --- |
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
| 同一 `action` 不跨章节 | fail |
| `conditions` 中未知变量都在 `missing_information` 里 | fail |
| 伞状分支已展开或注明无法展开 | fail |
| 加载的规则都有核对过的来源 | 该规则不加载，记 warn |
| LLM 产出记录了服务端模型名和提示词版本 | fail |
| 上游输出指纹一致（runmeta） | STALE |

## 9. 验收标准

**离线测试**：账本 schema；引用核对（假来源原文，正例和反例）；`id` 稳定；分支构建（resolved / ambiguous / unresolved，
最多 3 个，伞状展开，展开后超过 3 个的截断）；`applies_to` 子集校验；同一行动跨章节报错；规则加载器拒绝无来源 / 引用不符的规则；
规则条件只读 Step 1 字段；HTTP 缓存过期（ClinicalTrials.gov 1 天，其他不过期，`--refresh-trials` 强制刷新）；
`accessed_at` 取缓存里的真实抓取时间。每个修复照旧补测试并做反向验证。

**联网验收（`scripts/acceptance_step3_0.py`）**：

| 层级 | 标准 |
| --- | --- |
| 硬性 | 18 个病例都生成账本，全部校验通过；`--from-step 3` 能复用 Step 1/2 输出 |
| 硬性 | 分支：COL1A1、DMD 等 ambiguous 练习病例分支数 = min(候选数, 3)；有伞状概念的分支都已展开或注明原因 |
| 硬性 | 背景证据的引用 100% 逐字核对通过；来源链接可解析（HTTP 200 或已知的需登录页） |
| 硬性 | 第一批规则：加载的每条规则都有核对过的文献引用；DMD 规则在 PRAC-DMD-del 上生效 |
| 硬性 | ClinicalTrials.gov 缓存过期和强制刷新在真实 API 上验证一次 |
| 人工审查 | 查看页面上每个病例的证据树（分支 + 背景证据）；40003 的分支展开结果和 SPTLC1 调研结论（**只汇报，不据此调参**） |

## 10. 不在 3.0 范围

章节检索与判断（3a–3e）、报告写作（Step 4）、论断是否被来源支持的语义核查（Step 5）。

## 待定问题（请审阅时决定）

1. **基因特有规则由谁起草**。报告必须由系统生成、不能人工编辑；规则库是系统的一部分，但人手写针对评测基因（SPTLC1）的规则，
   可能被看作人工干预或对评测病例过拟合。可选：
   - (a) **系统起草**：代码按基因检索 PubMed / GeneReviews，LLM 从抓取到的原文中摘出候选规则和逐字引用，代码核对引用；
     人只审查、只能否决（不能改写内容）。所有基因同一流程，不只评测基因。**建议采用。**
   - (b) 人工整理规则，附出处。最快，但有上面的风险。
2. **分支裁决的力度**：第 2 节写的是"规则只影响措辞，不删分支"。是否允许强证据（如 strength = established 的规则）直接删分支？建议不允许，保留条件语句。
3. **`unresolved` 时的基因级分支**：是否需要（目前 18 个病例没有 unresolved）。建议保留，防止报告缺章节。
4. 证据 `claim` 用英文（报告语言），查看页面另显示中文说明。是否同意。

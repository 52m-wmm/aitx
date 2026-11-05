# 支持治疗兜底链（Supportive Management fallback）

> 状态：**第 2 版，已批准实现**（2026-11-04）。第 1 版审阅意见已并入：按分支执行、L4 补漏例外、L3 只用开放获取文本；待定问题已决定（文末）。
> 范围：3a 的 Supportive Management 章节（Existing Targeted 与 Contraindications 不变）。

## 目的

现在只有 GeneReviews 有该病专章时才会有支持治疗。没有专章的病例（如练习病例 SLC35A2-CDG），这一节只有"查过没找到"，
但专家评审要求的"完整性"和"临床实用性"恰恰在这种病例上最需要内容。兜底链按证据由强到弱逐层查找，
**每条建议都标明它来自哪一层**，让读者知道它是"本病的专家建议"还是"同类疾病的通用建议"或"对症处理"。

## 兜底链（按顺序；上一层有结果就不往下走，见"何时下沉"）

**按诊断分支逐个执行。** 每个分支单独走一遍兜底链，同一病例的不同分支可以落在不同层
（如一个分支有专章用 L1，另一个分支只有总论用 L2）。层级、下沉原因、阴性证据都按分支记录。

| 层 | 条件 | 来源 | 报告中的层级标注 |
| --- | --- | --- | --- |
| L1 专章 | GeneReviews 有该诊断（或其直接上位病）的专章 | 该章 Management 各小节（现有 3a 流程） | 无额外标注 |
| L2 总论 | 没有专章，但有覆盖它的疾病群总论（Overview，如 "Hereditary Ataxia Overview"、"Congenital Disorders of Glycosylation Overview"） | 总论的 Management / Treatment 小节 | "疾病群通用建议（来自 <总论名>，非本病专章）" |
| L3 文献 | 既无专章也无总论 | PubMed：该基因 / 疾病的综述、队列研究、共识或指南中的管理建议（与 3c 共用检索模块） | "来自文献（<文献类型>，<PMID>）" |
| L4 对症 | 前三层都没有可用建议 | 病人**已报告症状**对应的症状指南（如癫痫、发育迟缓、喂养困难） | 节首注明 "No disease-specific management recommendations were found; the following is symptomatic management." |

**何时下沉**（每个分支分别判断）：一层"有结果"指至少一条通过引用核验和支持度核查的建议。
- L1 / L2 有结果时不查 L3；**L3 只在 L1、L2 都没有结果时查**。
- L4 在 L1–L3 都没有结果时，针对病人已报告的所有症状（Step 2 的 present 表型）。
- **例外（L4 补漏）**：上层有结果时，病人已报告、但上层**没有任何行动覆盖**的症状，单独走 L4。
  "覆盖"由代码判断：上层某行动的"针对的症状"（manifestation）条件与该症状按 HPO 匹配（同一术语或其上下位），即为覆盖。
  补漏的 L4 行动同样标注"对症处理"，并写明它补的是哪个症状。
- 任何情况下都不为未报告的症状写对症处理。
同一行动在多层出现时只写一次，用最高层的来源，较低层的来源作为补充证据附上。

## 每层的来源要求与核验

**L1 专章**：不变（3a 契约）。

**L2 总论**
- 章节匹配：章节标题或 GeneReviews 的疾病列表中含该诊断所属的疾病群，由 LLM 从**代码给出的编号列表**里选，代码核对编号存在；
  只选 Overview 类章节（标题含 "Overview"），且该章节的基因列表或病种表**逐字点名**该基因或该病（代码核对）。点不到名的总论不用。
- 抽取：与 L1 相同的提示词和逐字核验；每条证据记录 `tier_source: "overview"` 和总论 NBK 号。
- 总论中针对**其他具体病种**的建议（"In X, …"）不能用于本病：抽取时保留所在行 / 句的病种限定，代码检查限定的病种是否为本病或疾病群整体，否则丢弃。

**L3 文献**
- 文本范围：**只用 PubMed 摘要和 PMC 开放获取（Open Access）子集的全文**。不是开放获取的全文一律不获取，不绕过任何访问限制（登录、付费墙、人机验证）。
  某篇文献是否在开放获取子集，用 E-utilities efetch（PMC 允许自动获取的接口之一）取 PMC 记录判断：带正文且许可证为 Creative Commons / open-access 才算开放获取，许可证原文记进账本。PMC OA Web Service 已于 2026 年停用（pmc.ncbi.nlm.nih.gov/tools/oa-service，2026-11-05 核对）。单篇文献判定失败时记为未知，只用摘要，不中断整个 L3。
- 检索：PubMed E-utilities（esearch + efetch 摘要），检索式 = 基因符号 AND（疾病名或同义词）AND 文献类型过滤
  （Review、Practice Guideline、Consensus Development Conference、观察性 / 队列研究），按相关度取前 N 篇（拟 N = 10），检索式、时间、总数写入检索记录。
  与 3c 共用同一个检索模块和缓存（3c 契约将引用本节）。
- 抽取：只用摘要或 PMC 开放获取全文中**明确写出的管理建议**（"we recommend …"、"patients should be monitored / treated with …"），
  LLM 逐字摘句，代码核对引用逐字在已获取的文本中、PMID 可解析（E-utilities esummary）。
- 支持度核查：每条建议用 3.0 的支持度核查判断"该文献建议对 <本病> 患者采取 <行动>"；只有 supported 才进章节。
- 病例报告（单个病人）不作为管理建议的来源；文献类型由 PubMed 的 Publication Type 字段决定，代码判断。
- 标注：`tier_source: "literature"`、文献类型、PMID、发表年份；报告中按文献类型从强到弱排列（指南 / 共识 > 综述 > 队列）。

**L4 对症**
- 症状来源：Step 2 中 status = present 的 HPO 表型，按 HPO 映射到症状类别（癫痫、发育迟缓 / 智力障碍、肌张力异常、喂养困难、听力、视力等）。
- 指南来源：每个症状类别配置一份**可引用的公开指南**（配置文件 `config/symptom_guidelines.json`：指南名称、发布机构、版本 / 年份、URL 或 PMID、
  使用的段落），写代码前逐条人工核实；没有配置指南的症状不写。
- **选源优先级**：① 国际学会（ILAE、ESPGHAN 等）→ ② 美国学会（AAP、AAN、AES 等）→ ③ 其他国家机构（NICE、IAP 等）。
  只选管理 / 干预类指南（支持治疗不含监测、筛查）。只有前两级确实没有可用的指南时才用第 ③ 级，并在配置中写明理由。
- 引用核验：引用逐字出自配置的指南文本（本地存档或可获取的页面）。
- **自动抓取被拒的指南（HTTP 403、人机验证）**：
  - 由人工在浏览器打开公开页面，核对拟用段落。不绕过任何验证。
  - 核对过的段落原文、核实日期、网址存本地 `.cache/guidelines/<指南编号>/verified.json`（不进仓库），作为 L4 引用核验的依据。
    配置里记录该文件的 sha256。
  - Step 5 的链接检查对这类来源标"人工核实（日期）"，不要求自动 HTTP 200。
  - 原因与 PubMed 那条相同（3.0 契约验收表）：这些网站对自动化访问启用了访问防护，例如 NICE、UCL Discovery 返回 403，
    AAP 出版社页面用 Cloudflare 人机验证。自动检查拿到的只是拦截页，不能说明链接失效，而验收不绕过防护。
  - 有开放获取存档或官方接口的，优先用它们自动核验，例如 PMC / E-utilities、作者接受稿。
- 标注：`tier_source: "symptomatic"`；报告节首加上面的说明句；每条注明对应的病人症状及其 Step 2 引用。

## 新增行动类型 `therapy`

- 物理治疗、作业治疗、言语 / 语言治疗、早期干预、喂养治疗等康复类行动，行动键 `therapy:<类型>`，受控类型表：
  `physical_therapy`、`occupational_therapy`、`speech_language_therapy`、`early_intervention`、`feeding_therapy`、`other_rehabilitation`。
- 归类由代码按受控词表（含常见写法："PT"、"physiotherapy"、"OT"、"speech therapy"、"SLP"；缩写只认大写）判断，LLM 只给原文名称。
- **已在 3a 实施（2026-11-04，提示词 `3a-v4`）**：
  - "转介去接受治疗"（早期干预、物理 / 作业 / 言语治疗、喂养治疗等）作为行动保留，归 `therapy:<类型>`。
  - "转介去做评估或咨询"（专科评估、遗传咨询、随访）仍排除。
  - LLM 标为 therapy、但对不上词表的条目不收。
  - 胸部物理治疗（气道廓清）是操作，不归 therapy。
  - 代码在 `aitx/evidence/actions.py`（`THERAPY_TYPES`、`NOT_THERAPY`、`therapy_type`）。
- 现有 3a 中被归为 `supportive_measure` 的同类行动改用 `therapy` 键；同类行动在多层或多处出现时按行动键合并（与 3a 小修第 4 条的同义合并一致）。
- 适用条件：通常以"针对的症状"（manifestation）为条件，与现有支持治疗相同。

## 账本与报告

- 每条支持治疗证据增加 `tier_source`（`chapter` / `overview` / `literature` / `symptomatic`）；行动记录增加 `tier_source`（取其证据中最高层）。
- 章节级记录每层是否查过、结果数量和下沉原因（如 "no GeneReviews chapter or overview names SLC35A2-CDG"），写入 `sections_status` 的补充字段，
  供报告的节首说明使用；查过没找到的层留阴性证据（检索词、时间、返回数）。
- Step 5 报告组装时：L2 / L3 / L4 的行动分别带层级标注，不与 L1 的行动混排。

## 校验（在 3.0、3a 校验之外）

| 校验 | 不过则 |
| --- | --- |
| 每条支持治疗行动有 `tier_source`，且与其证据来源类型一致 | fail |
| 每个分支各自记录层级；某分支 L1 或 L2 有结果时，该分支没有查 L3 | fail |
| L4 行动要么属于前三层都无结果的分支，要么补的是上层没有覆盖的 present 症状（记录补的是哪个症状，以及为什么判为未覆盖） | fail |
| L3 证据的文本来自摘要或 PMC 开放获取全文（记录 OA 判断结果） | fail |
| L2 证据所在总论逐字点名该基因或该病；L3 证据的 PMID 可解析、文献类型不是单病例报告、支持度核查为 supported | fail |
| L4 每条对应一个 Step 2 present 表型，且指南出自配置表（配置中每份指南已人工核实原文和出处）；自动抓取被拒的来源有本地核实记录（段落、日期、网址，sha256 与配置一致） | fail |
| 每个分支的支持治疗章节有行动或阴性证据，阴性证据覆盖查过的每一层 | fail |

## 验收（练习病例；不用评测病例；期望先人工核实再写入）

| 病例 | 期望 | 核实方式 |
| --- | --- | --- |
| PRAC-AGXT-c33dup | L1 专章（NBK1283）；不查 L2–L4；支持治疗与现在一致 | 现有 3a 验收 |
| PRAC-ANO10 | 现在命中的 NBK1138 是 "Hereditary Ataxia Overview"（总论）：应标为 L2"疾病群通用建议"，不再当作专章 | 人工核对 NBK1138 的标题与基因表 |
| PRAC-SLC35A2-ex7 / ex8 | 无专章、无点名 SLC35A2 的总论（待人工核对 CDG 总论是否点名 SLC35A2；若点名则为 L2）→ L3 文献：至少一条来自 SLC35A2-CDG 综述或队列研究的管理建议（如癫痫、喂养、发育支持），PMID 可解析 | 人工检索 PubMed 并核对原文后写入期望 |
| L4 对症 | 练习病例都能在前三层找到内容时，L4 只用离线测试覆盖（造一个无章节、无文献的病例）；不为未报告的症状写对症处理 | 离线测试 |

## 已定决策（2026-11-04 审阅）

1. L3 每个分支取前 10 篇；文本只用摘要和 PMC 开放获取全文。
2. L4 首批症状：癫痫、发育迟缓 / 智力障碍、喂养困难。每份指南先人工核实原文和出处，写进配置前先把配置清单交审阅。
3. L1 与 L2 并存（有专章，同时有总论）时，不取总论的通用建议。

## 实现记录（2026-11-05）

- 代码：`aitx/evidence/fallback.py`（判层、L3 检索、L4 配置与补漏、校验），在 `established.add_established` 中按分支执行（`supportive_fallback`）。
- L1 / L2 判层用 Step 2 的 GeneReviews 章节元数据（`scope`：single_gene → L1，multi_gene → L2）。总论的基因列表来自 GeneReviews 索引（`genereviews.chapter_genes`）。总论里点名本章其他基因的建议不用，丢弃记录在 `dropped_conditions`。
- 账本新增 `supportive_tiers`（每个分支的层级、所用章节、L3 检索记录、补漏或对症的症状），以及支持治疗行动的 `tier_source`、`for_symptom`。新校验 `supportive_tiers_consistent`。
- L3 检索服务出错时（如 NCBI 返回 500）记录错误，不做任何推断。
- L4 配置表 `config/symptom_guidelines.json` 还没建（等指南清单审定），所以目前 L4 只记录需要补漏的症状，不生成行动。
- 离线测试：`tests/test_fallback.py`，14 条，含反向用例。

### 覆盖判断修改（2026-11-05）

上层的覆盖范围（决定哪些 present 症状要走 L4 补漏）改为两条：
1. 行动"针对的症状"与病人症状按 HPO 上下位关系匹配，向上、向下都算：同一术语、上位术语或下位术语。
2. 分支所用专章或总论的治疗类管理小节（`mgmt_sections`，不含监测、初诊评估、亲属评估、在研疗法）的正文中，写出了该症状的 HPO 名称或同义词，即算已覆盖。整词匹配；短的大写缩写（如 CKD）区分大小写。结果记在 `supportive_tiers[分支].covered_by_chapter_text`。

起因：AGXT 有专章，但"肾钙质沉着""慢性肾病"被判为未覆盖。专章 Supportive Care 和 Targeted Therapies 小节其实写了 "Nephrocalcinosis"、"chronic kidney disease (CKD)"。反向测试：专章没提到的症状（如癫痫发作）仍判为未覆盖。

### L4 配置与总论判定（2026-11-05）

- **配置** `config/symptom_guidelines.json` 已按审定写入，每份指南写明级别、出处、版本 / 现行状态，第 ③ 级写明理由。本地核实记录在 `.cache/guidelines/<编号>/verified.json`（不进仓库），sha256 写在配置里。
  - 癫痫：AES 2016 癫痫持续状态指南（②；AES 官网仍列为现行，新版在制定中），推荐带使用情境 "seizures lasting at least 5 minutes"，判为有条件；AAN/AES 2018（②；2024-10-19 复审确认），药物推荐只在病例写明对应发作类型时使用（配置的 `hpo` 限定为失神发作）；NICE NG217（③，理由：一般管理在 ①② 级没有现行指南）。
  - 发育迟缓 / 智力障碍：**不启用**（`enabled: false`）。AAP 2013 核实前不用 IAP 临时代替。
  - 喂养困难：ESPGHAN 2017（①），3 条推荐，其中 2 条带使用情境。
- **新增配置项**：类别 `enabled`；推荐 `hpo`（只对病人已有的该症状或其下位症状使用）；推荐 `requires`（使用情境，原文逐字，判为有条件）。
- **总论判定改为按章节原文标题**（契约原文"标题含 Overview"）。实现时曾按基因数判断，把"Classic Ehlers-Danlos Syndrome"（3 个基因）误标为总论；现在按标题判断，取不到标题时才退回按基因数。
- **新发现的候选（未写入配置）**：AES 官网列出 "American Epilepsy Society Clinical Practice Guideline: Infantile Epilepsy"（2026 年 4 月）。这是第 ② 级的婴儿癫痫管理指南，待核实原文后再决定是否加入。

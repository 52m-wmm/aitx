# 第 2 步：疾病归一化（Disease Resolution）

> 状态：**已验收**（2026-10-28，`--fresh-llm` 硬性项全过，tag `step2-accepted`）。曾按审查意见修订为 v2；v2.1–v2.4 补充规则和已知局限见文末。
> step2.1（v2.5）：否定词规则、起病年龄映射到 HPO 起病术语、难题测试集，见文末 v2.5 一节；验收结果见该节。

## 目的

回答"这个病人得的是哪种病"，并给出可核验的标准编号。

一个基因常常对应好几种病（ITPR1 有 3 种，SPTLC1 有 2 种），所以这一步不能只按基因查表，
要结合病人的**症状**和**遗传方式**，从候选里选出最符合的一个，或者明确说"无法确定"。

软件类比：基因是一个函数名，疾病是它的多个重载；第 2 步根据"实参"（症状、杂合/纯合、是否新发）
做重载决议，决议不唯一时报歧义，而不是随便挑一个。

## 输入

1. 病例 JSON（同第 1 步），用到 `genotype` 和 `clinical_context`
2. 第 1 步输出的 VariantProfile 列表（用到 `gene`、`transcript`、`variant_cdna`、`zygosity`、`variant_class`、`allelic_state`）

## 数据源（全部免费、无需注册）

| 数据源 | 用途 | 获取方式 | 许可 |
| --- | --- | --- | --- |
| **GenCC** 提交导出 | 基因–疾病关联 + 证据强度 + 遗传方式，汇总了 ClinGen、G2P、PanelApp、Orphanet、Ambry 等多家机构 | `search.thegencc.org/download/action/submissions-export-tsv`（约 26 MB） | CC0 |
| **ClinGen** 基因–疾病有效性 | 最权威的证据强度评级，带在线报告链接 | `search.clinicalgenome.org/kb/gene-validity/download`（CSV） | CC0 |
| **HPO** `genes_to_disease.txt` | 基因 → OMIM / Orphanet 疾病编号（补充 GenCC 没收录的） | HPO GitHub release | HPO 许可（免费，需署名） |
| **HPO** `phenotype.hpoa` | 每种疾病的典型症状列表（HPO 术语）+ 遗传方式 | 同上 | 同上 |
| **HPO** `hp.json` | 症状术语本体：术语编号、名称、同义词、上下级关系 | `purl.obolibrary.org/obo/hp.json` | 同上 |
| **MONDO** SSSOM 映射 | 疾病编号互转（MONDO ↔ OMIM ↔ Orphanet）和标准名称 | `purl.obolibrary.org/obo/mondo/mappings/mondo.sssom.tsv` | CC BY 4.0 |
| **Orphanet** product6 | 基因–疾病关联类型，含机制提示，例如"致病突变（功能丧失）" | `orphadata.com/data/xml/en_product6.xml` | CC BY 4.0 |
| **GeneReviews** 索引 | 基因 → GeneReviews 章节（NBK 编号） | `ftp.ncbi.nlm.nih.gov/pub/GeneReviews/GRshortname_NBKid_genesymbol_dzname.txt` | NCBI 公开 |
| **OMIM** `mim2gene.txt` | 核对 OMIM 编号确实存在且类型正确（基因条目 / 表型条目） | `omim.org/static/omim/data/mim2gene.txt` | OMIM 免费文件 |
| **ClinVar**（实时 API） | 变异级证据：该变异的临床意义、星级、关联疾病 | NCBI E-utilities `esearch` / `esummary`（db=clinvar） | 公有领域 |
| **MONDO**（实时 API，经 EBI OLS4） | 候选疾病的同义词，供原文点名匹配和第 3 步检索 | `www.ebi.ac.uk/ols4/api/ontologies/mondo/terms?obo_id=...` | CC BY 4.0 |
| **HGNC**（实时 API） | 基因别名、旧名、HGNC/NCBI/OMIM 基因编号 | `rest.genenames.org/fetch/symbol/<基因>` | CC0 |

**OMIM 的限制**：OMIM API 需要 key（已实测无 key 返回 400），omim.org 页面不允许抓取。
因此 OMIM 只作为**编号**使用（编号来自 GenCC / HPO / MONDO，并用 `mim2gene.txt` 核对），
报告里引用 `https://omim.org/entry/<编号>`；疾病名称用 MONDO 标准名，不使用 OMIM 原文。

### 快照与完整性（实测发现的必要措施）

ClinVar、OLS4、HGNC 是实时 API，按第 1 步的方式缓存（记录 URL 和访问时间）。
其余数据源只提供整包文件下载，没有逐条查询的接口，与"优先用实时 API"的约定不同。处理方式：

- 下载到 `.cache/datasets/<名称>/<日期>/`，写一份清单 `sources_manifest.json`：URL、下载时间、字节数、sha256、行数
- **下载后必须做完整性校验**：探测时 GenCC、HPO、`hp.json` 都出现过返回 200 但文件被截断的情况。
  校验项：与 `Content-Length` 一致；完整解析成功（JSON 能 load、TSV 列数一致）；行数不低于下限
- 校验失败 → 重新下载；仍失败 → 整步报错停止，**不允许用残缺数据继续**
- 开发期快照超过 7 天自动刷新；正式提交时冻结一份快照，清单随提交保存

## 处理流程

### 1. 收集候选疾病（确定性）

对每个基因，取 GenCC + ClinGen + HPO + Orphanet 的全部关联，用 MONDO 映射合并成同一疾病
（同一种病在不同来源里编号不同），每个候选保留全部交叉编号（MONDO / OMIM / Orphanet）。

**硬规则：最终结果里的疾病只能来自这个候选集合。** LLM 不得提出候选集合以外的疾病。

### 2. 基因–疾病证据强度（确定性）

- 有 ClinGen 评级时以 ClinGen 为准；否则看 GenCC 各提交机构的评级
- 强度顺序：Definitive > Strong > Moderate > Limited > Disputed > Refuted
- Orphanet 在 GenCC 里统一标为 Supportive（未分级），只算"有关联"，不算强度
- 输出：汇总强度、ClinGen 评级（如有）、每家机构的原始评级（保留分歧，不抹平）
- 只有 Limited / Disputed / Refuted 的候选：标记，不作为首选

### 2b. ClinVar 变异级证据（确定性）

用 `转录本:c.写法` 查询 ClinVar（例如 `NM_005639.3:c.1103T>C`），对每条命中记录做**精确匹配校验**：
记录里的转录本和 c. 写法必须与输入完全一致（`c.8079delC` 与 `c.8079del` 这类等价写法先规范化再比）。

> 实测：查 ITPR1 `c.100G>A` 会同时返回相邻的另一个变异 `c.101A>G (p.Asp34Gly)`，不校验就会引用错记录。

转录本版本不同但 c. 写法相同的记录：标记 `version_mismatch`，可以记录但不参与排序。

每条匹配记录输出：VCV 编号与链接、临床意义（Pathogenic / Likely pathogenic / VUS / …）、
审核状态与星级、最后评估日期、关联疾病（名称 + 交叉编号）。

星级按 ClinVar 官方对照：practice guideline = 4；reviewed by expert panel = 3；
criteria provided, multiple submitters, no conflicts = 2；criteria provided, single submitter 或
conflicting classifications = 1；no assertion criteria / no classification = 0。

**关联疾病映射到候选集合**：用 MONDO / OMIM / Orphanet / MedGen 交叉编号对上候选。
`not provided`、`Inborn genetic diseases`、`See cases` 这类泛称**不算**疾病关联（实测 ITPR1 记录就是 `not provided`）。

**参与排序的条件**：临床意义为 Pathogenic 或 Likely pathogenic，**且**关联疾病在候选集合内。
VUS、良性或疾病对不上的记录只作为信息保留。

查不到记录是正常结果（实测 ACTL6B、SPTLC1、KMT2B 的变异 ClinVar 均无收录），记为 `not_found`。

### 3. 遗传方式是否吻合（确定性）

候选疾病的遗传方式（AD 常显 / AR 常隐 / X 连锁等，来自 GenCC、ClinGen、HPO）对照病人：

| 病人情况 | 候选是 AR | 候选是 AD | 候选是 X 连锁 |
| --- | --- | --- | --- |
| 纯合 | 吻合 | 可能（AD 病很少见纯合），标记 | 视性别 |
| 杂合，只报告了一个变异 | **条件吻合**：需要另一个等位基因上还有变异，报告中必须写成条件语句 | 吻合 | 女性：可能 |
| 半合子（男性 X 染色体） | — | — | 吻合 |

`clinical_context` 里出现 "de novo" 或 "trio ... de novo" 时记录为新发变异，作为支持 AD 的证据。
结果分为 `consistent` / `conditional` / `inconsistent` / `unknown`，附理由。
`inconsistent` 的候选移到"不支持"列表，**不删除**，供审查。

### 4. 症状匹配

**4a. 提取病人症状 → HPO 术语**（唯一用到 LLM 的地方）

- LLM 从 `clinical_context` 提出 `(HPO 编号, 原文引用片段, 存在/明确否认)`
- 确定性校验，任一项不过就丢弃该条并记录：
  - 编号在 `hp.json` 中存在且未作废
  - 引用片段在原文中逐字存在
  - 术语名称或同义词与片段有合理的词面重叠（防止编号张冠李戴）
- 否定要识别：例如 SYT1 病例 "without overt seizures" 应记为**明确没有**癫痫
- 调用参数：temperature 0，记录服务端返回的模型名，响应写入缓存（同一快照重跑结果一致）

**4b. 原文点名的诊断**

正则识别 `OMIM #618218` 一类写法，并用候选疾病的标准名和 MONDO 同义词在原文里做匹配
（实测 SYT1 病例原文写 "Baker Gordon Syndrome"，MONDO 同义词是 "Baker-Gordon syndrome"，规范化大小写和连字符后匹配）。
点名的疾病如果在候选集合里，直接作为强证据；**不在候选集合里则报警，不采纳**（防止输入写错时照抄）。

**4c. 打分（确定性）**

- 病人术语与疾病术语按 HPO 层级上溯匹配（"局灶性癫痫"也能匹配到"癫痫"），
  稀有症状权重更高（权重 = 信息量 IC，按 `phenotype.hpoa` 的注释频率计算）
- 病人"明确没有"的症状，如果是疾病的常见症状，扣分
- 疾病在 `phenotype.hpoa` 里**没有症状注释**时（实测 ACTL6B 的 DEE76 就没有），分数记为 `null`
  并注明"无注释数据"，**不当作 0 分**

### 5. 排序与选择（确定性）

1. 排除：遗传方式 `inconsistent` 的候选；只有 Disputed / Refuted 证据的候选。
   **Limited 不排除**，只降低置信度（罕见病里新近描述的疾病证据常常有限，排除会误删正确答案）
2. 按优先级选首选：
   1. 原文点名且通过校验的疾病
   2. ClinVar 变异级关联（P/LP 且在候选集合内）；有多个时取星级高的，星级相同则继续看症状分
   3. 症状分排序；第一名与第二名差距小于阈值（初值 20%，只在练习病例上调）→ 状态 `ambiguous`，列出前几名
3. 只剩一个候选 → 首选，但症状分为 `null` 时置信度最高只到 `moderate`
4. 上一级的证据与下一级冲突时（例如 ClinVar 关联的疾病症状分明显落后）：仍按优先级选，
   但置信度降一级，并在理由中写明冲突

置信度：

- `high`：证据 Definitive/Strong + 遗传方式 consistent + 首选依据明确（原文点名、ClinVar ≥2 星 P/LP，或症状分明显领先）
- `moderate`：缺其中一项；或证据强度只有 Moderate / Limited
- `low`：缺两项及以上，或遗传方式只是 conditional

### 6. 附加信息（确定性，传给后续步骤）

- **GeneReviews**：按基因查章节，记录 NBK 编号、标题、链接，并标明是**该基因专章**还是**综述章节**。
  例如 ITPR1 只在 "Hereditary Ataxia" 综述里，而 SPTLC1 有专章
- **Orphanet 机制提示**：关联类型里的 "loss of function / gain of function" 原样传给第 3 步，附来源，
  第 2 步不据此下结论
- **检索用同义词**：每个候选疾病的标准名 + MONDO 同义词（OLS4）；基因的 HGNC 别名和旧名
  （例如 SYT1 → P65、SYT、SVP65）。第 3 步用来检索文献和试验，避免因写法不同漏检

### 7. 病人基本事实 `patient_facts`（LLM 提取 + 逐字校验）

| 事实 | 取值 | 说明 |
| --- | --- | --- |
| 年龄 | 换算成**月** | "3-year-old" → 36；"18-month-old" → 18；"3-month-old" → 3 |
| 起病年龄 | 月或区间 | "first months of life" → 区间 0–6，标记为近似 |
| 性别 | male / female / unknown | |
| 是否新发 | de_novo / inherited / unknown | |
| 家族史 | 原文陈述或 unknown | |

每项附原文引用片段并**逐字校验**；引用不存在 → 该项置为 `unknown`。原文没提 → `unknown`，**不推测**。
年龄换算由代码完成（LLM 只给数字和单位），换算规则写死在代码里并有单元测试。
性别也用于遗传方式判断（X 连锁）。

## 输出：DiseaseResolution（每个病人一份）

| 字段 | 含义 |
| --- | --- |
| `schema_version` | `disease-resolution-v1` |
| `patient_id` | 病例编号 |
| `phenotypes` | 病人症状：HPO 编号、名称、原文引用、存在/明确否认、校验结果 |
| `explicit_diagnosis` | 原文点名的诊断及校验结果；没有则为 `null` |
| `patient_facts` | 年龄（月）、起病年龄、性别、是否新发、家族史，每项附原文引用和校验结果 |
| `inheritance_evidence` | 合子状态，以及取自 `patient_facts` 的新发、性别 |
| `clinvar` | 每个变异的 ClinVar 结果：`found` / `not_found` / `version_mismatch`，匹配记录的 VCV 编号、链接、临床意义、星级、评估日期、关联疾病及其映射到的候选 |
| `candidates` | 候选疾病列表，每个含：MONDO/OMIM/Orphanet 编号、标准名、证据强度（汇总 + 各机构原始评级）、遗传方式及吻合结论、ClinVar 变异级关联（如有）、症状分（含匹配和未匹配的术语）、Orphanet 机制提示、GeneReviews、`synonyms`（MONDO 同义词）、来源 |
| `gene_aliases` | 每个基因的 HGNC 编号、别名、旧名 |
| `not_supported` | 被排除的候选及排除理由 |
| `primary` | 首选疾病编号、`status`（`resolved` / `ambiguous` / `unresolved`）、`confidence`、首选依据（`explicit` / `clinvar` / `phenotype` / `only_candidate`）、理由列表 |
| `checks` | 校验结果（见验收标准） |
| `evidence` | 每条结论对应的来源：文件 URL + 快照日期 + 行号或记录编号，或 OMIM/ClinGen/GeneReviews 的网页链接 |

后续步骤只能使用 `primary.status = resolved` 的疾病写确定性结论；`ambiguous` 时报告必须写成条件语句
（"若为 X，则……；若为 Y，则……"）。

## 节点验收标准

**防过拟合原则**：硬性的"标准答案"只用练习病例；4 个评测病例只检查结构和数据完整性，
它们的首选结果列为人工核对项（SOFT）。

### HARD（必须全部通过）

1. 全部数据文件通过完整性校验，清单完整
2. 每个候选编号都能在源文件中找到：OMIM 编号在 `mim2gene.txt` 中是表型条目，MONDO 编号在映射文件中存在
3. 每个 HPO 术语有效，引用片段在原文中逐字存在
4. 没有候选集合以外的疾病出现在输出里
5. 练习病例中答案明确的，首选必须一致且 `status = resolved`：

| 病例 | 期望首选 | 依据 |
| --- | --- | --- |
| PRAC-AGXT-c33dup、PRAC-AGXT-c508GA | 原发性高草酸尿症 1 型，OMIM 259900 | 唯一高强度关联 + 肾钙质沉着 |
| PRAC-CFTR-F508del | 囊性纤维化，OMIM 219700 | 原文点名 |
| PRAC-OTC | OTC 缺乏症，OMIM 311250 | 半合子男婴 + 高氨血症 |
| PRAC-KMT2B | 肌张力障碍 28 型，OMIM 617284 | 儿童期起病全身性肌张力障碍 |
| PRAC-ANO10 | 常隐脊髓小脑共济失调 10 型，OMIM 613728 | 纯合 + 共济失调 |
| PRAC-NF1 | 1 型神经纤维瘤病，OMIM 162200 | MPNST + 嗜铬细胞瘤 |

6. 两个"陷阱"病例不能给出过度自信的结论：
   - PRAC-COL1A1：症状是关节过度活动、皮肤过度伸展、易瘀伤（像 EDS）。EDS 类疾病必须在候选中，并且
     **排在成骨不全之前**，或者状态为 `ambiguous` 且两者都列出
   - PRAC-DMD-del：杜氏（OMIM 310200）和贝克（OMIM 300376）两者都必须在候选里
7. ClinVar 精确匹配：每条被采用的 ClinVar 记录，转录本和 c. 写法都与输入一致
   （ITPR1 不得采用 `c.101A>G` 那条）；练习病例 PRAC-CFTR-F508del 必须查到 P/LP 记录且关联到囊性纤维化
8. `patient_facts` 每项引用都逐字存在于原文；练习病例：PRAC-OTC 年龄 3 个月、男性

### SOFT（打印出来人工核对）

- PRAC-DMD-del 的首选（框内缺失按经验更倾向贝克型，见开放问题 2）
- PRAC-GRIN2B：智力障碍 6 型（613970）还是 DEE27（616139）
- PRAC-SLC35A2-ex7：原文点名 SLC35A2-CDG，应采纳
- PRAC-SLC35A2-ex8：首选及置信度（原文未点名诊断）
- 4 个评测病例的首选、状态与理由。预期参考，**不作为硬性答案**：
  - AITX-40001 ACTL6B 纯合：DEE76（618468）；常显的 618470 应因遗传方式被降级
  - AITX-40002 ITPR1 新发杂合：SCA29（117360）；Gillespie 综合征需要无虹膜，原文未提
  - AITX-40003 SPTLC1：HSAN1（162400）与青少年 ALS27（620285）都应在候选里，
    原文同时有感觉丧失和体重下降、Gowers 征，可能是 `ambiguous`
  - AITX-40004 SYT1：原文点名 BAGOS（618218），应校验通过并采纳
- 每个病例提取到的 HPO 术语列表

### 稳定性

- **有缓存**：同一快照、同一 LLM 缓存下重跑，输出必须完全一致（HARD）
- **无缓存**：关闭 LLM 缓存连续调用 3 次，报告症状提取（HPO 术语集合）和首选结果的一致性
  - 评测病例的首选必须 3 次一致；不一致 → 该病例 `primary.status` 标为 `ambiguous`，理由写明"多次运行结果不稳定"
  - 症状提取的差异（多出或缺少的术语）逐条列出，供调整提示词

### 其他

- 输出能被第 3 步直接读取，不需要人工修改

## 已定决策（2026-10-28 审查）

1. 症状提取：LLM 提取 + 确定性校验
2. 基因特有的基因型–表型规则（DMD 读码框、SPTLC1 区域等）放到第 3/4 步，带文献证据；第 2 步只做通用规则并如实报告歧义
3. OMIM API key 已在申请，v1 不依赖
4. 歧义阈值只在练习病例上调，不在评测病例上调

## 实现中的补充规则（v2.1，2026-10-28，待审）

写代码和跑练习病例时发现契约没写清楚的地方，按下面的方式处理。每条都有离线测试覆盖。

| # | 情况 | 处理 | 触发它的实例 |
| --- | --- | --- | --- |
| 1 | 遗传方式与症状分谁先 | 第 5 步的症状分排序**在遗传方式分层之内**进行：`consistent` 层 > `conditional` 层 > `unknown` 层。`unknown`（没有遗传方式记录、线粒体等）**不等于** `inconsistent`：不排除，只排在后面。最佳层只剩一个候选时，首选依据记为新增值 `inheritance` | ACTL6B 纯合：常隐 DEE76 排在常显 618470 前 |
| 2 | 归类术语（无 OMIM/Orphanet 编号、无症状注释，如 "complex neurodevelopmental disorder"） | 保留在候选里，但同一比较池中有具体疾病时**不参与首选比较**，理由中列出 | KMT2B、AGXT、DMD |
| 3 | ClinVar 记录用的转录本版本与输入不同 | 取两个版本的序列比对：变化位于 CDS 内且两版 CDS **逐字相同** → `cds_identical_version`，视同精确匹配参与排序；否则仍是 `version_mismatch` | CFTR F508del：ClinVar 记在 NM_000492.3，输入是 .4，CDS 4443 nt 完全相同 |
| 4 | ClinVar 组合记录（单倍型 / 复合，如 `c.[1521_1523del;3080T>C]`） | 只接受**单变异**记录，组合记录列入 `rejected` | CFTR 检索返回 16 条，其中有 F508del 组合记录 |
| 5 | ClinVar 疾病映射到候选 | 疾病带 MONDO 编号时**只用 MONDO 编号**映射（ClinVar 常给亚型附上伞状 Orphanet 编号）；该 MONDO 不是候选本身时，映射到以它为**祖先**的候选（经 OLS4 层级），但若覆盖该基因全部候选则不映射 | COL1A1：记录同时列 "Ehlers-Danlos syndrome"（MONDO:0020066），映射到经典型 EDS 等 |
| 6 | 原文点名匹配 | 原文带明确编号（`OMIM #nnnnnn`、`ORPHA:nnn`）时**编号永远优先**，不受下一条限制，且优先于任何名称匹配；按名称匹配时，名称同时是 HPO 症状术语则当作**症状**不当作诊断（记入 `skipped_names`）；基因符号和别名不算 | NF1 原文 "Pheochromocytoma" 是症状；SYT1 原文 "OMIM #618218" |
| 7 | 症状注释来源 | 候选的症状注释取其 **OMIM 和 Orphanet** 编号注释的并集 | 经典型 EDS 只在 ORPHA:287 下有注释 |
| 8 | LLM 抽样 | 每个病例固定 3 次调用（temperature 0，分别缓存），术语与事实按**多数票**；首选分别在 3 份抽样上重算，不一致则改为 `ambiguous`。推理模型 `max_tokens` 用 16384，被截断或空的回答**不写缓存**并重试 | AITX-40003 一份抽样选了 ALS27，另两份选 HSAN1 |
| 9 | LLM 给的 HPO 编号错、名称对 | 编号校验不过时，按 LLM 给的名称或引用片段做 HPO 精确名称匹配，仍须满足词面重叠 | "very thin" 被给成 HP:0001989（实为 Fetal akinesia sequence），已拒收 |
| 10 | `ambiguous` 时 `primary.id` | 填排名第一的候选作参考，并列项在 `alternatives`；置信度固定为 `low`。后续步骤只看 `status` | |
| 11 | 数据下载 | 断线后按 HTTP Range 续传（带 If-Range，文件更新则从头下）；完整性校验不变 | 连接常在 ~10 MB 处断开 |

## v2.2 修改（2026-10-28 第二轮审查意见）

| # | 规则 | 说明 |
| --- | --- | --- |
| 12 | **起病年龄参与打分** | 病人起病年龄取自 `patient_facts.onset`（月）；没有时用当前年龄作上限（起病 ≤ 年龄）。疾病起病年龄取 `phenotype.hpoa` 中 aspect C 且属于 HPO Onset 分支（HP:0003674）的注释，按 HPO 定义换算成月份区间（如 Infantile 1–12 月、Juvenile 5–15 岁）；未列出的子术语取最近的已列出祖先。两区间有重叠（病人区间放宽 ±25% 并加 1 个月容差）→ 加 0.5；无重叠 → 减 1.0；任一方未知 → 不加不减。只有年龄上限时只在明显不符（疾病最早起病晚于当前年龄）时减分，不加分。**不作为一票否决**。原始分与调整后分数都写入输出（`score_before_onset`、`onset`） |
| 13 | **合并嵌套或等价候选** | 共享 OMIM / Orphanet / UMLS 编号的候选视为等价，合并为一组，代表优先选有症状注释的；在 MONDO 层级上是另一合格候选祖先的候选标为 `broader`，并入下级的组，**不参与首选比较**（显式点名除外）。同一上级下的兄弟疾病仍各自成组。例外：有症状注释的上级不并入**全都没有注释**的下级（否则下级无法打分）。输出字段 `merge`（group / role / narrower / equivalent_to）和 `compete` |
| 14 | **unknown 遗传方式的保险** | 最佳层为 `consistent` 时，若某个 `unknown` 候选的症状分比首选高出歧义阈值（20%）以上，状态改为 `ambiguous` 并列出两者。`conditional` 不在此规则内 |
| 15 | **ClinVar 非排序记录保留** | 冲突（Conflicting）、VUS、版本不符等不参与排序的记录，其关联疾病照常映射，并写入对应候选的 `clinvar_info`（含不参与排序的原因），供后续步骤使用 |

验证集：官方 Hugging Face `aitxchallenge/Phase1_Model_Validator` 中未出现在练习/评测病例的基因只有 DDC、KCNT1 两个
（`data/cases/validation/phase1_hf_unseen_genes.json`）。KCNT1 已被用来发现问题（v2.2 的第 12、13 条），
**不再算留出验证集**；只有 DDC（AITX-00007）是干净的验证病例。

## v2.3 修改（2026-10-28 第三轮审查意见）

| # | 规则 | 说明 |
| --- | --- | --- |
| 13′ | **合并只针对归类概念**（替换 13 中的嵌套部分） | 上级候选**有自己的症状注释**，说明它本身是一种疾病，与下级作为独立候选**平等竞争，不合并**（输出 `merge.narrower_competing`）。只有**没有症状注释**的上级才按归类概念并入下级、不参与比较。等价合并（共享编号）不变 |
| 12′ | **起病年龄只扣分、不加分**（替换 12 中的加分） | 对得上不加分（`result = match`，`adjustment = 0`），明显矛盾才扣 1.0。消除"有起病年龄注释的疾病占便宜"的偏差 |
| 16 | **整体起病年龄的提取收紧** | `patient_facts.onset` 只记原文明确说明的**疾病或主要表现**的起病时间；只针对某个症状的时间（如 "around 10 years of age began losing weight"）记在该症状条目的 `onset` 上，不当作整体起病年龄，也不参与打分。提示词版本 `step2-extract-v2`。这一条靠 LLM 遵守，代码只做逐字和换算校验 |

第 12′、16 条是看了评测病例 AITX-40003 后决定的；判断依据是规则是否公平，不以任何病例的排序结果调参数。

## v2.4 修改（2026-10-28 第四轮审查意见）：症状提取改为"LLM 只选、编号由代码给"

与疾病选择同一原则：**LLM 不写任何 HPO 编号**。替换第 4a 节的"LLM 提出编号 + 词面重叠校验"和补充规则第 9 条。

| # | 规则 | 说明 |
| --- | --- | --- |
| 17 | **两段式提取** | 第一段：LLM 只给原文引用、症状的标准医学描述、至多 3 个其他医学名称（`alternatives`）、存在/否认、可选的该症状起病时间。代码映射：依次用**原文引用**、描述、其他名称去精确匹配 HPO 名称、同义词和**旧名**（来自 HPO 2022-10-05、2024-04-26 两个历史版本，以及已作废术语指向的替代术语；复数形式也算），唯一命中即采用。第二段：匹配不上时，代码用描述、其他名称和原文做词法检索（BM25），取最接近的至多 10 个表型术语，LLM 按序号选一个或选"都不对"；只能选代码列出的候选。**删除词面重叠校验** |
| 18 | **投票按层级合并** | 3 次抽样中，某术语的支持数 = 含该术语或其下级术语的抽样数（同一存在/否认状态）。支持数 ≥ 2 的保留，并只保留其中最具体的层级（不保留下面还有已保留术语的上级）。输出 `merged_from` |
| 19 | **首发症状的起病时间** | LLM 标记 `presenting`，代码核对该症状所在句子在它之前有 "presented / presenting / first sign / initial symptom" 一类表述；核对通过且整体起病年龄为空时，该症状的起病时间作为整体起病年龄（`source = presenting symptom`） |
| 20 | **症状提取测试集** | `data/eval/hpo_extraction_gold.json`：练习病例和 Phase 1 validator 病例（不含 4 个评测病例和干净验证病例 DDC）的 13 段描述，24 个正例片段 + 8 个反例片段（诊断名、年龄、正常结果、行政信息），共 32 条。正例可列多个可接受编号。每次运行先用代码核实所有编号在 hp.json 中存在、未作废、属于表型分支，再报告精确率、召回率和逐条假阳性（`scripts/eval_extraction.py`，并已接入验收脚本） |

v2.4 实现时发现并修正的通用问题（由评测病例 AITX-40003/40004 暴露，修正不针对任何排序结果）：检索只用单一描述时词汇缺口大
（"Emaciation" 不是任何 HPO 术语的名称，"Ophthalmic abnormalities" 只检索到眼动脉术语）→ 加入 `alternatives` 做查询扩展；
描述去掉了限定词时会匹配到更泛的术语 → 精确匹配先试原文引用；被否认的症状 LLM 有时不肯映射 → 第二段提示词说明"否认的症状仍映射到症状本身"。

## 已知局限（v2.4，v2.5 更新）

1. **症状测试集偏简单**：练习病例的描述几乎都是标准术语的罗列，没有否认、口语化描述和多句叙述（这些只出现在评测病例里）。
   当前精确率、召回率都是 1.0（24/24，0 假阳性），**很可能高估**真实水平。
2. **词法检索有词汇缺口**：检索不理解语义，口语描述需要靠 LLM 给出的医学名称才能命中；仍可能出现正确术语不在候选里、
   LLM 只能选"都不对"的情况（AITX-40003 的 "caloric intake is poor" 目前三次都没有映射）。
3. **整体起病年龄依赖 LLM 选对引用**：v2.5 起数字和区间由代码给出（规则 24），同一表述总是得到同一区间；
   但哪句话算"整体起病"仍由 LLM 判断，代码只核对引用逐字存在和首发症状表述。
4. **症状注释的粒度决定部分排序**：DMD 练习病例中，杜氏型注释了 "Progressive muscle weakness" 而贝克型没有，
   于是杜氏型明显领先、贝克型不再列为并列项（两者仍都在候选中）。读码框等基因特有规则按已定决策放在第 3/4 步。
5. **同一疾病的不同编号**在 MONDO 中既非上下级、又不共享编号时不会合并（KCNT1 的 EIMFS 与 DEE14），仍互相制造歧义。
6. **有编号但无症状注释的具体疾病**无法打分，只能使结果变为歧义（如 DMD 病例的非综合征性 X 连锁智力障碍）。
7. **ClinVar** 的临床意义是变异级汇总，不是逐个疾病的；一条记录列出多个疾病时，全部关联疾病都得到同等支持。
   评测病例 ACTL6B、SPTLC1 的变异 ClinVar 未收录（已用 c./p. 多种写法核实）。
8. **起病年龄注释稀疏**，且只扣分不加分，区分力有限。
9. **unknown 遗传方式的保险**只在最佳层为 `consistent` 时生效，不覆盖 `conditional`。
10. **3 次抽样**仍可能不一致（如 AITX-40003、DMD），此时按规则降为 `ambiguous`；`--fresh-llm` 的结果可能与缓存不同。
11. ~~漏提 CBAVD~~（2026-11-03 发现，v2.5 已修复，见规则 22）。
12. **LLM 选的描述层级偏宽时，投票保留宽的一层**：如 "keeps getting chest infections" 3 次里 2 次被描述成不带"反复"的 Chest infection。
13. **起病年龄解析只覆盖常见英文写法**（数字 + 单位、"age N"、"day N"、范围、时期名称）；其他写法记为未知，不会猜。

## v2.5 修改（step2.1，2026-11-03）：否定词规则、起病年龄映射、难题测试集

提示词版本 `step2-extract-v5`（与起病年龄改造一起改，缓存只失效一次）。

| # | 规则 | 说明 |
| --- | --- | --- |
| 21 | **难题测试集** | `data/eval/hpo_extraction_hard.json`：改写练习病例得到的 6 段描述、21 个正例片段（口语化 10、多句叙述 6、否认 4、缩写 1，含 CBAVD），编号经代码核实。与旧测试集分开报告，按难点类型分别报告召回率；只测不设门槛 |
| 22 | **缺失类术语例外** | 标为"存在"、但原文引用含否定词的条目，不再在映射前直接拒绝；映射后看**映射到的 HPO 术语本身是否表示缺失**（名称或同义词含 absent / absence / aplasia / agenesis / lack / missing / no / without / none，或该否定词本身就是术语名称的一部分）。是则保留（"born without the vas deferens" → Absent vas deferens 存在），否则拒绝（"no seizures" 标成存在 → Seizure 不是缺失类 → 拒绝）。判断依据是映射到的术语，不是原文 |
| 23 | **否定词表扩充** | 加入 never、normal、unremarkable、ruled out。定义："明确说某个具体功能、器官或检查正常 = 对应异常为排除"（"hearing is normal" → Hearing impairment 排除）。比较句（"further than normal"、"above / below / beyond normal"）是在说异常，不算否定。旧测试集 AITX-00010 的 "Normal liver labs" 由反例改为"排除的肝功能异常"，文件内注明原因 |
| 24 | **起病年龄由代码映射到 HPO 起病术语** | LLM 只给起病描述的原文引用，不再给数字。代码：原文里写了年龄（"at 8 months"、"around age 6"、"day 3"、"between 2 and 4 years"、"first 6 months of life"）→ 解析成月数，放进 HPO 定义区间包含它的起病术语（范围取覆盖到的全部术语）；写的是时期名称（"since birth"、"in infancy"、"childhood"、"adolescence"）→ 对应术语。用于打分的区间一律用 **HPO 定义的区间**（`hpo.ONSET_LEAVES` / `ONSET_MONTHS`），原文的数字只记录在 `stated_months`。映射不上 → 起病年龄未知并注明原因。验收脚本核对术语表的编号和名称与 hp.json 一致 |

**语义检索暂不做**（2026-11-03 决定）：改进后两个测试集剩下的唯一漏提（"keeps getting chest infections"）不是检索不到正确术语，
而是 LLM 在 3 次抽样中有 2 次把描述写成不带"反复"的 Chest infection，精确匹配到更宽的 Respiratory tract infection，投票保留了多数的层级。
只有出现确实"检索不到正确术语"的漏提时，才提出语义检索方案。

测试集结果：

| 测试集 | 改进前 精确率 / 召回率 / 假阳性 | 改进后 |
| --- | --- | --- |
| 旧测试集 | 1.0 / 29/30 / 0 | 1.0 / 31/31 / 0（新增 "Normal liver labs" 排除一条） |
| 难题集 | 0.938 / 16/21 / 1 | 0.95 / 20/21 / 1（否认 2/4 → 4/4，口语化 7/10 → 9/10） |

**验收**（2026-11-03，tag `step2.1-accepted`）：`--fresh-llm` 硬性项全过；旧测试集 1.0 / 31/31 / 0；难题集 0.952 / 20/21 / 1
（不用缓存时 KMT2B 足内翻那条被映射成 Gait disturbance，属抽样差异，难题集不设门槛）。
诊断变化（与改进前比，只汇报、未据此调参）：只有 AITX-40003。新增 "caloric intake is poor" → Feeding difficulties（3/3 抽样），
未注释该症状的候选平均分下降，ALS27 跌出 20% 歧义区间；同时 unknown 遗传方式的"青少年 ALS"（伞状概念）比最佳 consistent 候选高 31%，
触发 unknown 保险列为并列。状态仍为 ambiguous / low，HSAN1 与青少年 ALS 两个方向都保留；伞状概念展开到 ALS27 已列入 3.0 待办。
其余病例诊断不变；起病区间改为 HPO 定义（如 KMT2B "childhood-onset" 12–216 → 12–60 月，40004 "8 months" → Infantile 1–12 月）。

**LLM 并发**（2026-11-03，step2.1 之后）：同一病例的 3 条抽样链（第一段调用 + 自己的第二段选择）并行，验收与测试集评估中多个病例并行；
全局上限 `AITX_LLM_CONCURRENCY`（默认 16；2026-11-03 由 4 调高）。不改变任何规则和输出：缓存键、抽样序号不变，按序汇总；
已核对 18 个病例用缓存重跑与串行结果逐字节一致，验收"缓存重跑一致"硬性项通过。

## Step 2 局限改进（step2.1）完成情况

1. 难题测试集：完成（规则 21）。
2. 起病年龄映射：完成（规则 24）。混合语义检索：暂不做，原因见上。
3. CBAVD 漏提：根因是否定词规则误删（不是 LLM 漏提、也不是检索），已修复（规则 22），两个测试集都已召回。
4. 基因特有规则（DMD 读码框、SPTLC1 表型与区域）：移到 Step 3.0，见 `docs/step3_0_contract.md`。

## Step 2 待办（2026-11-03 记录，不阻塞 3.0）

1. **疾病分组参与竞争**：AITX-40001 的候选里，"undetermined early-onset epileptic encephalopathy"（MONDO:0018614）和
   "syndromic intellectual disability"（MONDO:0000508）是 Orphanet 的疾病分组、不是具体疾病，但前者因有症状注释而参与了比较。
   "有无症状注释"不足以判断是否具体疾病；拟改用数据库自身的分类（Orphanet 疾病类型、MONDO 的 grouping 标记）。
   **先统计**全部病例中有多少候选属于这种情况、是否影响任何病例的状态（特别是 40002、40003 的并列项），再提方案，审定后改。
   - 统计（2026-11-03，61 个参与比较的候选）：Orphanet 与 MONDO 自身的分类**都没有**把上述两个例子标为分组
     （MONDO:0018614 在 Orphanet 是 Disease、MONDO 子集 ordo_disorder；MONDO:0000508 无 Orphanet、无分组标记）。
     关联基因数能区分它们（66、54 个基因），但也会命中囊性纤维化（GenCC 19 个基因）等具体疾病，需要拍阈值。
     40002、40003 的并列项不受影响；练习病例 DMD 的并列项"非综合征性 X 连锁智力障碍"（31 个基因，Orphanet 病因亚型）受影响。
   - **决定：(a) + (c)，不用基因数阈值**。(a) 只按数据库标记判定分组：Orphanet DisorderGroup = "Group of disorders"
     或 MONDO 子集 `ordo_group_of_disorders`；被标为分组的候选不参与比较（有无症状注释都一样），`specific = false`，
     输出 `grouping` 字段写明依据。(c) 其余宽泛概念在 3.0 作为伞状分支处理（展开、无法展开时标注、报告措辞上区分）。
   - **已实现**：18 个病例的诊断结论全部不变；被标为分组的 2 个候选（AITX-00011 MONDO:0020072、DMD MONDO:0016106）原本就未参与比较。
2. **"ranked above N candidates"的计数**只计进入比较的候选（已实现；40001 由 4 改为 2）。


## 病人描述读不到时报错停止（2026-11-11，盲测后修复 O1）

病人描述只从 `patient.clinical_context` 读，统一经过 `aitx/caseinput.py` 的 `clinical_context(case)`：字段缺失、不是文本或只有空白时抛 `MissingDescription`，不再默认空串继续。`run_pipeline.py` 在跑任何一步之前先检查所有选中的病例，有问题就逐条打印 `[INPUT]` 并以退出码 5 结束（3 = 高峰时段，4 = 当日预算）。
**起因**：盲测 B 组的病例文件把描述写成了 `clinical_description`，流水线读到空串，10 个病例在没有描述的情况下跑完，没有任何警告（`docs/experiments/blind_test_results.md` 事故一节）。
测试：`tests/test_caseinput.py`（缺字段 / 错字段名 / 空串 / 空白 / None；`run_pipeline.py` 在第一步之前停下；仓库里所有病例文件都可读）。

## 原文点名的病种群让位给 ClinVar 指向的更具体疾病（2026-11-11，盲测后修复 D1，用户批准）

**规则**：临床文本点名的疾病（`explicit`）在 MONDO 中**包含** ClinVar 把本变异指向的另一个候选疾病时，取那个更具体的疾病；两者无上下位关系、或原文点名的更具体、或 ClinVar 没有链接时，仍以原文为准。多个被包含的候选按 ClinVar 星级、再按表型分数取。选择结果的 basis 仍为 `explicit`，另记 `refined_from`（原文点名的疾病），理由写明两者和 ClinVar 记录。
**层级来源**：MONDO 祖先由 OLS4 的 `hierarchicalAncestors` 取得（`live.mondo_ancestors`，Step 2 原有的数据源，走 HTTP 缓存）；OLS 不可用时不做细化，原文点名的疾病照旧。
**起因**：盲测 B1 的描述取自 GeneReviews 总论首段，点名的是病种群（Leigh 综合征谱系、CMT），Step 2 因"文本点名优先"选了更宽的名字，压过了 ClinVar 指向的 LRPPRC 法裔加拿大型和 CMT1B，随后引入了亚型不符的试验（CMT4J）。已核对：OLS 中 MONDO:0009069（法裔加拿大型）的祖先含 MONDO:0009723（Leigh 综合征），MONDO:0007307（CMT1B）的祖先含 MONDO:0015626（CMT），反向不成立。
**测试**：`tests/test_diagnosis_refine.py`（两个盲测例子；反向：无上下位关系、原文更具体、无 ClinVar 链接、无层级时都不变；多个被包含者取星级高的）。
**验收**：Step 2 验收与 `acceptance_eval_cases.py --eval`（确认 4 个评测病例诊断不变）留到修复全部写完后的统一重跑。

## "或"表述的表型为"可能存在"（2026-11-12 用户决定）
引文前后是"normal / unaffected / typical / absent / none / no + or"一类的二选一表述（"development is normal or mildly delayed"）时，表型状态记为 `possible`（`possible_because` 记原文短语），由代码按原文判定。诊断排序仍按存在计；下游对应条目判"有条件"并列入缺失信息"finding stated only as possible"。测试 `tests/test_possible_findings.py`、`tests/test_established.py`。属放宽。


## 2026-11-26 HPO 候选召回修复（离线，正式结果未刷新）

先完成各票原始症状抽取，再分别映射。仅对已通过原文校验、原文片段逐字相同且 present/excluded 相同的症状，将其他票按原精确匹配规则命中的 HPO 术语补入词法检索候选。既有精确匹配（含多候选精确命中）路径不变；候选最多仍为 10 个，新增候选优先、旧候选相对顺序不变。候选记录 query_sources（抽样序号、描述、备选名称和精确命中方式）。没有病例、基因或目标术语特例。

共享的只是候选，不共享已接受的映射或投票，不把一票复制为多数。系统提示词、逐票编号选择协议、HPO 投票和疾病选择规则不改；候选列表变化改变完整请求缓存键，旧编号回答不得移用。原始抽取独立，映射阶段的候选现已共享，因此不得将这三次映射宣传为完全独立的稳定性证据。

18 个官方病例复用现有原答离线检查：16 例完整抽取与改前逐字段相同；AITX-40003 两票补入 Decreased body weight，AITX-40004 两票补入 Abnormal eye morphology（仅候选，不代表认可具体语义）。4 个新选择请求无缓存，真实映射未完成，不生成新诊断、不称修复后诊断仍歧义或已确定。正式结果、账本、缓存、基线均未更新。完整输入/输出和 diff：out/step2-hpo-mapping-20261126/。

## 2026-11-26 第一轮临床事实重构（待人工审核）

抽取入口 `aitx/disease/extract.py::extract` 改为一次结构化抽取（`step2-clinical-v6`），必要时再进行一次 HPO 候选选词。没有三票、多数聚合或父子术语多数覆盖；`n != 1` 明确报错。沿用现有缓存/费用记录、原文检查、年龄和起病换算、HPO 精确匹配及候选检索。删除跨样本查询共享；单项 alternatives 仍作为同义查询。

原生事实保存在 `patient_facts.clinical`：

- `phenotypes`：`present / absent / possible / unknown`，`scope=patient/general/unknown`；保留 quote、症状级 onset、severity、course、原回答 source_status、映射失败原因及冲突。`valid` 仅表示 HPO 映射是否通过，不表示临床确定性。
- `facts`：原抽取的年龄、整体起病、性别、变异来源、家族史，逐项带状态/主体和原文。
- `items`：diagnosis、demographic、history、treatment、lab、trial_status；保留原数字或逐字文本值、原单位、时间引用。缺单位保持 null，不调用检验解释或推断单位；空列表只表示没有记录。
- `background`：百科/综述原句及主体说明；`source_text` 保存完整输入，`produced_by` 保存抽取调用来源。

原下游接口继续使用五类 `patient_facts` 标量和 `phenotypes`：只有 scope=patient 且明确 present/absent 的、有效映射的表型进入兼容视图，absent 在该旧接口拼写为 excluded。possible、unknown、综述、主体未知、阳性/阴性冲突均不进入确定事实视图。旧视图保留 votes=1、merged_from=[] 仅为现有查看页字段兼容，不再执行投票。疾病召回、评分、裁决、Step3 代码未修改；新增完整事实不会自动替换 Step3 自己的 extra_facts。

模型只承担文本语义抽取和非精确 HPO 选词。程序要求完整结构、正确状态/主体枚举和逐字原文；缺字段、无效引用、无效数值/单位、缺失/非法 HPO 选择均抛错停止，不填默认值掩盖格式失败。有效的 null 选词保留为未映射事实，不是阴性。主体分类仍取决于模型，一次观察不能证明所有混合文段均可靠。

验收原答、原文对照、完整日志、改前快照和 status_diff 见 `out/step2-clinical-facts-20261126/`。正式输出与基线不刷新；current 基线在开工前已缺失，保留完整错误，不重建/promote。

## 2026-11-27 第二轮 G2P 与 MICA B3（隔离验收，待审）

直接 G2P 官方 CSV 加入现有 datasets/sources/Resources；按同基因及疾病 ID 挂接 candidates.g2p_evidence，顶层 g2p_records 保留未挂接记录。保留原始等位要求、机制及 inferred 等证据边界和来源，patient_variant_mechanism 为 unknown。不参与召回、权重或排除。

评分入口要求原生 scope=patient、valid 且明确 present/absent；possible/unknown/general 不计阳性或阴性。B3=B1（明确频率0的单条阳性注释不参与匹配）+B2（仅精确或祖先—后代关系贡献）。其他 IC、分母、罚分、起病及权重/阈值不变。旧文档“possible按存在计”在此被取代。

多个同层候选若仅靠 MICA 分差得出 resolved，保留排名但改为 ambiguous；同星 ClinVar 竞争亦适用，明确诊断/唯一候选路径不变。原20%比较阈值未调整。G2P不证明患者变异机制，MICA不单独确认诊断。

四例复用第一轮临床抽取、固定原数据做 baseline/g2p-only/b3-only/combined 对照。完整候选、来源、判断差异、SVG及status_diff输出：out/step2-round2-20261127/README.md。正式结果/页面/基线不刷新；Step1、Step3及L1–L4未改。

## 2026-11-27 第三轮 Step1 分子衔接（待审、未刷新正式输出）

主流水线原已传Step1；独立step2_disease入口现复用runmeta加载Step1。按病例、基因、完整转录本和cDNA唯一匹配，缺字段/身份不符报错；合子状态/蛋白描述矛盾及Step1检查失败保留conflicting，不作为确定遗传事实。

molecular_evidence区分reported/sequence_derived与predicted。Step1未提供致病性预测，明确unknown，不用pLDDT/RSA替代。合子状态进入既有遗传分层；molecular_assessment逐G2P记录核对等位要求、机制及restricted mutation set。错义及NMD not_applicable不能确证/排除LoF；截短+likely_triggers及Step1 LoF假设仅predicted_compatible。不同G2P记录是替代路径；缺第二等位、相位或受限集合成员证据保留条件。

选择函数实际读取分子筛查：G2P条件未确认时，非明确临床诊断/非变异特异ClinVar路径不能仅靠遗传分层或唯一候选升级resolved，保留同基因竞争；输入分子矛盾亦阻止确定结论。临床诊断保留独立依据，不因机制尚未知直接否认。无新硬排除、无分数加权、不把预测改成证实。四例候选/分数/首位/状态不变，依据新增，详见out/step2-round3-20261127/README.md及完整diff。Step1分析、Step3及L1–L4未改。

## 2026-11-27 第四轮 L1–L4 统一输出契约（待审核）

`pipeline.run_case` 在现有选择、自检、证据列表完成后，调用 `output.build_layers(case, step1, out)` 写入同一Step2 JSON的 `layers`，版本 `step2-l1-l4-v1`。旧字段不删除，不另建跨步骤账本，不改Step3读取。纯组装不查网、不抽取、不评分、不裁决，禁止由输出层强行确定唯一亚型。

- L1：完整原文、native clinical、旧patient_facts/phenotypes及来源、报告genotype、完整Step1及分子证据。旧抽取没有clinical时明确null并标legacy覆盖缺口，不补patient主体或四态。
- L2：已有记录的大类候选、独立确证大类未知状态、患者原文诊断及完整原primary。疾病名字匹配保留为旧派生记录，不冒作已报告诊断；resolved明确是既有算法状态，不新增医学确证。无已存大类证据时不从基因/标签/首位推断。
- L3：所有candidates及原not_supported完整保留，不仅输出primary.alternatives。支持/反对/待核实为原证据索引，保留每条原记录。零匹配/零扣分不当反证；机制预测张力标prediction而不是确定矛盾或新排除。
- L4：NMD及机制假设、致病性预测缺口、G2P原始记录、逐候选机制路径/Orphanet提示。疾病层机制及inferred不变患者机制事实，后者仍unknown。

所有内部ref以layers自身为JSON Pointer根；sources_manifest/evidence原引用完整保留。输出构造复制值，不修改输入或判断结果；没有新增运行时校验层。验收及完整中文四例结果：out/step2-round4-20261127/README.md。15常规+2定向离线通过组装一致性；原有PFN1/THPO MONDO warn保留。未升级13例旧临床抽取，未刷新正式基线。

## 2026-11-27 ClinVar 三路召回与空缓存有效期（待审核）

clinvar_lookup接收gene，完整转录本+cDNA、无版本转录本+cDNA、Gene+cDNA三路均执行，Variation ID合并去重后获取摘要。查询超过50条时分页，缺失/不完整响应报错，不能静默截断。原变异身份、CDS版本等价、P/LP过滤、疾病映射逻辑不改。查询元数据保存为clinvar[].searches，search_url仍保留首个完整转录本查询兼容字段。

仅ClinVar ESearch空idlist缓存24小时有效，到期经原HTTP接口重新获取；非空ClinVar及其他数据源策略不变，http.py未改。OTC11010接受为cds_identical_version（Pathogenic，2星），161330为其他变异被拒。L3新增患者变异证据，L4机制unknown不因Pathogenic改变。

第四轮17例冻结资源/临床/Step1回放：只有OTC新增可接受ClinVar支持；其他16例完整L1–L4不变，COL1A1扩展查询额外BMP1命中正确拒绝。17例分数、候选集合及primary不变。原共享缓存、正式输出/基线不刷新；回归原答及完整diff：out/clinvar-recall-fix-20261127/README.md。

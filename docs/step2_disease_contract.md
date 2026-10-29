# 第 2 步：疾病归一化（Disease Resolution）

> 状态：**已批准**（2026-10-28 审查，按审查意见修订为 v2）。

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
- PRAC-SLC35A2：首选及置信度
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
| 1 | 遗传方式与症状分谁先 | 第 5 步的症状分排序**在遗传方式分层之内**进行：`consistent` 层 > `conditional` 层 > `unknown` 层。最佳层只剩一个候选时，首选依据记为新增值 `inheritance` | ACTL6B 纯合：常隐 DEE76 排在常显 618470 前 |
| 2 | 归类术语（无 OMIM/Orphanet 编号、无症状注释，如 "complex neurodevelopmental disorder"） | 保留在候选里，但同一比较池中有具体疾病时**不参与首选比较**，理由中列出 | KMT2B、AGXT、DMD |
| 3 | ClinVar 记录用的转录本版本与输入不同 | 取两个版本的序列比对：变化位于 CDS 内且两版 CDS **逐字相同** → `cds_identical_version`，视同精确匹配参与排序；否则仍是 `version_mismatch` | CFTR F508del：ClinVar 记在 NM_000492.3，输入是 .4，CDS 4443 nt 完全相同 |
| 4 | ClinVar 组合记录（单倍型 / 复合，如 `c.[1521_1523del;3080T>C]`） | 只接受**单变异**记录，组合记录列入 `rejected` | CFTR 检索返回 16 条，其中有 F508del 组合记录 |
| 5 | ClinVar 疾病映射到候选 | 疾病带 MONDO 编号时**只用 MONDO 编号**映射（ClinVar 常给亚型附上伞状 Orphanet 编号）；该 MONDO 不是候选本身时，映射到以它为**祖先**的候选（经 OLS4 层级），但若覆盖该基因全部候选则不映射 | COL1A1：记录同时列 "Ehlers-Danlos syndrome"（MONDO:0020066），映射到经典型 EDS 等 |
| 6 | 原文点名匹配 | 名称同时是 HPO 症状术语时，当作**症状**不当作诊断（记入 `skipped_names`）；基因符号和别名不算 | NF1 原文 "Pheochromocytoma" 是症状 |
| 7 | 症状注释来源 | 候选的症状注释取其 **OMIM 和 Orphanet** 编号注释的并集 | 经典型 EDS 只在 ORPHA:287 下有注释 |
| 8 | LLM 抽样 | 每个病例固定 3 次调用（temperature 0，分别缓存），术语与事实按**多数票**；首选分别在 3 份抽样上重算，不一致则改为 `ambiguous`。推理模型 `max_tokens` 用 16384，被截断或空的回答**不写缓存**并重试 | AITX-40003 一份抽样选了 ALS27，另两份选 HSAN1 |
| 9 | LLM 给的 HPO 编号错、名称对 | 编号校验不过时，按 LLM 给的名称或引用片段做 HPO 精确名称匹配，仍须满足词面重叠 | "very thin" 被给成 HP:0001989（实为 Fetal akinesia sequence），已拒收 |
| 10 | `ambiguous` 时 `primary.id` | 填排名第一的候选作参考，并列项在 `alternatives`；置信度固定为 `low`。后续步骤只看 `status` | |
| 11 | 数据下载 | 断线后按 HTTP Range 续传（带 If-Range，文件更新则从头下）；完整性校验不变 | 连接常在 ~10 MB 处断开 |

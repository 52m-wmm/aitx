# Step 3d 契约：定制疗法（Tier 3 · Bespoke Therapies）——草案 v0.1（待审，只写契约，未实现）

> 2026-11-05 起草。本草案不改任何代码。下面的验收期望都是**提议**，要先人工核实原文才能写进 `data/eval/`。
> "写错比不写更糟"：3d 写的都是假设性层（hypothetical）的内容，**只给分子层面的可行性判断**，不说"推荐"。病情、个人情况和伦理评估不在范围内，交给治疗评估小组（见第 6 节）。

## 1. 范围与边界

- **3d 做什么**：对每个诊断分支、每种定制疗法手段，给出一个**分级结论 + 理由**。理由必须引用 Step 1 的变异事实（字段路径）和有出处的疾病机制，不能只有一句话。
- **手段清单**（每个分支逐一评估，没有一种可以省略。不适用也要写出"不适用 + 理由"）：
  1. ASO 剪接纠正（splice correction）
  2. ASO 典型外显子跳跃（canonical exon skipping）
  3. RNA 敲低：等位基因特异（allele-specific）或总量（total），ASO / siRNA
  4. 上调正常拷贝（upregulation from the WT allele：如 TANGO / NMD 外显子靶向、uORF、天然反义转录本）
  5. 基因替代（AAV）
  6. 碱基编辑 / 先导编辑（base editing / prime editing）
- **不归 3d 的（不重复，只交叉引用 `see_also`）**：
  - **已获批**的、针对该基因或该变异的 ASO / siRNA / AAV / 编辑产品，归 **3a**（已确立层）：适用条件按说明书判断，例如 DMD 的外显子跳跃 ASO、AGXT 的 lumasiran / nedosiran、DMD 的 delandistrogene moxeparvovec。
  - **正在试验**的，归 **3b**（临床试验）。
  - 3d 对同一手段只写一句"已有获批 / 试验中产品，见 3a / 3b"，再加上该产品不覆盖本病人时的理由（例如外显子不对）。**同一行动不跨章节重复**。
  - 小分子老药新用归 3c，体外 / 动物研究的候选药归 3e。

## 2. 依据（都已用 NCBI E-utilities 核对书目信息，存 `.cache/n1c/`）

| 用途 | 出处 | 核对情况 |
| --- | --- | --- |
| 三种 ASO 手段的五级分类与判定流程 | **N1C VARIANT guidelines** v1.0：Cheerie D, et al. Consensus guidelines for assessing eligibility of pathogenic DNA variants for antisense oligonucleotide treatments. *Am J Hum Genet* 2025. PMID 40139194，PMC12120168（CC BY） | ✅ 正文已取（efetch，开放获取）。五级分类定义逐字见正文 "Classification terms" 节。**详细判定流程在补充材料 Data S1（mmc1.pdf），E-utilities 拿不到，下载需你同意（见待定问题 2）** |
| 上调正常拷贝：只给评估思路、不分级 | 同上，正文："Assessment strategies are provided for upregulation from the WT allele, but classifications toward eligibility are not defined because this area of ASO therapeutics is less established to date." | ✅ 逐字 |
| 只评估变异层面，不含病情、个人因素 | 同上，正文："For a full assessment beyond the variant, disease- and individual-specific clinical factors have to also be taken into consideration … which is beyond the scope of these guidelines." | ✅ 逐字 |
| ASO 的疾病与组织适用性（背景） | Lauffer MC, van Roon-Mom W, Aartsma-Rus A; N=1 Collaborative. *Commun Med (Lond)* 2024. PMID 38182878 | ✅ 摘要 |
| 个体化 ASO 的病人评估框架（第 6 节） | Schüle R, et al. (1M1M). *Mol Ther Nucleic Acids* 2025. PMID 40727088 | ✅ 摘要 |
| N-of-1 外显子跳跃 ASO 的设计与体外测试 | Aartsma-Rus A, et al. *Nucleic Acid Ther* 2023. PMID 36516128 | ✅ 摘要 |
| AAV 包装容量 | Wu Z, Yang H, Colosi P. Effect of genome size on AAV vector packaging. *Mol Ther* 2010. PMID 19904234："packaged AAV vector genomes never exceeded 5.2 kb in length" | ✅ 摘要逐字 |

- 4.7 kb 是野生型 AAV 基因组的大小，按你的要求作为判断阈值。Wu 2010 的 5.2 kb 是实测上限，只在理由里注明，不当作阈值。

## 3. 每种手段的判定（代码判定为主；LLM 只用来从来源里抽取机制原文，抽取后过支持度核查）

### 共同前提（缺任何一项 → "无法评估"，并写明缺什么）

| 前提 | 来自 | 说明 |
| --- | --- | --- |
| 变异类型、位置、外显子、NMD 预测 | Step 1：`variant_class`、`exon.*`、`nmd.prediction`、`transcript_layout` | 确定性计算 |
| 合子状态、正常拷贝有几份 | Step 1：`allelic_state.copies_affected`、`zygosity` | 半合子 / 纯合 = 没有正常拷贝 |
| **疾病机制**（功能丧失 / 单倍剂量不足 / 功能获得 / 显性负效应） | **必须有出处**：GeneReviews 的 Molecular Genetics / Genotype-Phenotype 节，逐字引用 + 支持度核查。Step 1 的 `mechanism_hypothesis` 只是假设，**不能单独作为依据** | 没有出处 → 依赖机制的手段都判"无法评估"（N1C："no information on the pathomechanism is available" → unable to assess） |
| 受累组织 | Step 2 的 HPO 表型，再对应到器官系统 | 决定递送路径（见基因替代） |

### 3.1 ASO 剪接纠正
- 只评估**改变剪接**的变异：剪接位点变异、深内含子变异、或有证据新建 / 破坏剪接位点的外显子变异。
- Step 1 目前**不预测剪接**。所以：
  - 剪接类变异 → "无法评估：需要 RNA 层面证据（患者 RNA 测序或剪接预测）"；
  - 其他类型（错义、无义、移码等）→ "不适用：没有证据表明该变异影响剪接"。理由要写清楚：这是基于 Step 1 没有剪接证据，不是证明它不影响剪接。
- 是否接入剪接预测工具，见待定问题 1。
- 已有针对**同一变异**的剪接纠正 ASO（临床或临床前）→ "eligible"（N1C 定义），但要附上那项研究。

### 3.2 ASO 典型外显子跳跃
代码逐条检查，任一条不满足 → 结论 + 是哪一条：
1. 疾病机制是功能丧失，且**截短蛋白可能保留功能**。后者要有基因层面的证据：健康人中天然存在该外显子缺失或跳跃，或实验证明跳跃后蛋白仍有功能（N1C 对 "eligible" 的要求）。没有这种证据，最多判 "likely eligible"（只满足分子条件）。
2. 变异在一个**内部外显子**里：不是第一个或最后一个外显子，也不是单外显子基因（N1C 举例：单外显子基因"not eligible"）。用 `exon.number`、`exon.total`、`exon.is_last_exon` 判断。
3. **跳过该外显子后阅读框不变**：外显子编码长度 `exon.coding_nt` 是 3 的倍数。不是 3 的倍数时，只有和相邻外显子一起跳（多外显子跳跃）才可能保持阅读框，这时判 "unlikely eligible"，并写出需要一起跳的外显子组合。
4. 大片段缺失：先看缺失本身是否已经保持阅读框（Step 1 `retranslation.same_frame_after_change`）。已经保持 → "不适用：阅读框已经保留，外显子跳跃的目的（恢复阅读框）不存在"。
5. 已获批的外显子跳跃 ASO：按说明书判断（归 3a）。不覆盖该病人的外显子时，3d 写"已获批产品针对第 N 号外显子，本病人的缺失不适用"。

### 3.3 RNA 敲低
- **总量敲低**：只用于功能获得 / 显性负效应，且该基因的总量下降可以耐受。N1C 的 "not eligible" 例子是剂量受严格调控的基因。剂量证据用 gnomAD pLI 或 ClinGen 单倍剂量不足评分（需新增查询，见待定问题 4）。单倍剂量不足或功能丧失疾病 → "不适用：敲低会进一步减少功能"。
- **等位基因特异敲低**：只用于杂合的显性负效应 / 功能获得变异，并需要能区分两个等位基因的靶点（变异本身，或同一等位上的常见 SNP）。Step 1 只有致病变异本身。用变异本身作靶点，判 "likely eligible（分子条件）"；用 SNP 作靶点，判 "无法评估：需要单倍型信息"。
- 纯合 / 半合子：没有正常等位基因 → 等位基因特异敲低不适用。

### 3.4 上调正常拷贝
- 前提：杂合、有一份正常拷贝（`copies_affected == 1` 且不是半合子），疾病机制有出处地写明是单倍剂量不足。
- N1C v1.0 **不对这一手段分级**。所以 3d 只写"可考虑的策略 + 前提是否满足"，**不给 eligible 之类的等级**。
- 基因是否有已知的 uORF、NMD 外显子或天然反义转录本，需查 N1C 的 Table S2 汇总表（mmc4.xlsx，下载需同意，见待定问题 2）。查不到时写"未查到上调靶点"。

### 3.5 基因替代（AAV）
- 只用于功能丧失 / 单倍剂量不足。功能获得 / 显性负效应 → "不适用：补一份正常拷贝不能消除异常蛋白的作用"，并写出机制出处。
- **容量**：CDS 长度由 Step 1 `transcript_layout.cds` 计算。
  - CDS > 4.7 kb → "超出 AAV 容量（约 4.7 kb，Wu 2010 实测上限 5.2 kb），全长 cDNA 无法装入单个载体"。可写"截短版本或双载体是另一类研发问题"，但不展开、不推荐。
  - CDS ≤ 4.7 kb → "CDS 本身可装入；启动子和 polyA 等元件是否放得下，取决于具体设计（未计算）"。**不编元件大小**。
- **靶组织递送**：受累组织来自 Step 2 表型，只写事实。例如：中枢神经系统需要鞘内或脑室给药，或用能穿越血脑屏障的衣壳；肝脏是 AAV 的常见靶器官；全身肌肉需要大剂量静脉给药。每条都要有出处，没有出处就不写。
- 已获批 / 试验中的 AAV 产品 → 3a / 3b，3d 只做交叉引用。

### 3.6 碱基编辑 / 先导编辑
- 代码由 HGVS 判断修正这个变异需要哪种碱基转换：
  - 转换型单碱基（C↔T、A↔G，在编码链或互补链上）→ 理论上可由碱基编辑器修正：C>T 用 ABE（腺嘌呤编辑器）改回，G>A 也用 ABE（在互补链上），T>C、A>G 用 CBE（胞嘧啶编辑器）；
  - 颠换型单碱基、小插入 / 缺失 → 只有先导编辑理论上可行；
  - 大片段缺失 → 两者都不适用。
- **PAM 与编辑窗口、旁观者编辑**需要基因组序列才能判断。是否计算见待定问题 5；不计算时写"是否有合适的 PAM 未评估"。
- 临床状态如实写：体内个体化碱基编辑只有极少数个案先例。先例要用 PubMed 检索、能解析到记录才写，不凭记忆写。

### 分级用词
- 三种 ASO 手段用 N1C 五级：eligible / likely eligible / unlikely eligible / not eligible / unable to assess，定义逐字取自 N1C。
- 其他手段 N1C 没有分级。3d 用三档描述：**理论上可行（分子条件满足）/ 不适用（附理由）/ 无法评估（缺什么）**。不借用 N1C 的等级名，以免看起来像有共识标准。

## 4. 账本记录

- 新章节 `bespoke_therapies`。每个分支 × 每种手段一条记录：
  - `modality`、`classification`；
  - `premises`：每条前提的 Step 1 字段路径和值，或有出处的机制引用；
  - `failed_criterion`（不适用时）、`missing`（无法评估时）、`see_also`（3a / 3b 交叉引用）、`sources`。
- 理由写成推理条目（reasoning），前提必须是已核实的证据，沿用 Step 3.0 的 `reasoning_premises_verified` 校验。
- 新增校验：
  - 每个分支 6 种手段都有记录；
  - 结论用词不超出依据（不出现 recommended / effective / proven）；
  - 3d 不出现 3a / 3b 已有的产品作为独立行动；
  - 每条"不适用"都能指出是哪一条判定没过。

## 5. 验收（只用练习病例；下列期望是提议，**写入前逐条人工核实原文**）

| 提议 ID | 病例 | 期望 | 依据（待核实） |
| --- | --- | --- | --- |
| dmd-skip-inframe | PRAC-DMD-del（c.7544_9286del，外显子 52–63 缺失，半合子） | 外显子跳跃：不适用。缺失已保持阅读框（`retranslation.same_frame_after_change = true`）；已获批的外显子跳跃 ASO（如针对第 51、53、45 号外显子）不覆盖本病人，3d 只做交叉引用 | Step 1 事实；获批产品说明书（3a 已检索） |
| dmd-aav-size | PRAC-DMD-del | 基因替代：全长 CDS 11,058 nt，超出 AAV 容量。获批的微型抗肌萎缩蛋白基因治疗按说明书在 3a 判断，3d 只做交叉引用 | Step 1 `transcript_layout.cds`；Wu 2010 |
| col1a1-knockdown | PRAC-COL1A1（c.1678G>A p.Gly560Ser，杂合，三螺旋区甘氨酸替换） | 等位基因特异敲低：likely eligible（分子条件），**前提是 GeneReviews 写明甘氨酸替换是显性负效应**；基因替代：不适用（显性负效应）；总量敲低：不适用（I 型胶原单倍剂量不足本身致病） | GeneReviews OI 章节机制段落（待逐字核对） |
| col1a1-base-edit | PRAC-COL1A1 | 碱基编辑：G>A 转换，理论上可用 ABE 修正；PAM 未评估；无临床先例（以 PubMed 检索为准） | Step 1 `variant_cdna` |
| kmt2b-upregulation | PRAC-KMT2B（c.8079delC，最后一个外显子，预测逃逸 NMD，杂合） | 总量 / 等位基因特异敲低：不适用（单倍剂量不足，**需机制出处**）；上调正常拷贝：前提满足（杂合 + 单倍剂量不足），不分级；基因替代：CDS 8,148 nt，超出容量 | GeneReviews KMT2B 机制段落（待核对）；Step 1 |
| agxt-aav-fits | PRAC-AGXT-c33dup（c.33dup，纯合，第 1 号外显子） | 基因替代：CDS 1,179 nt，本身可装入，靶器官为肝；外显子跳跃：不适用（第一个外显子）；碱基编辑：不适用（插入），先导编辑理论上可行；RNAi 获批药物在 3a，3d 不重复 | Step 1；3a 已有 lumasiran 期望 |
| otc-hemi | PRAC-OTC（c.386G>A p.Arg129His，半合子） | 等位基因特异敲低 / 上调正常拷贝：不适用（半合子，没有正常拷贝）；碱基编辑：G>A，理论上 ABE；AAV / mRNA 试验在 3b，只做交叉引用 | Step 1 `allelic_state`；3b 期望 |
| mechanism-missing | 任一机制来源没写明的病例（如 NF1 p.Leu1243Pro） | 依赖机制的手段判"无法评估：疾病机制无出处"，**不能用 Step 1 的 `mechanism_hypothesis` 代替** | 反向验证 |

反向验证（离线测试）：
- 把 `exon.coding_nt` 改成非 3 的倍数，外显子跳跃应降为 unlikely eligible；
- 把机制引用删掉，所有依赖机制的手段都应变成"无法评估"；
- 纯合病例不能出现等位基因特异敲低的"likely eligible"；
- CDS = 4,701 nt 应判"超出容量"，4,700 nt 应判"可装入"。

## 6. 病人层面的评估（只列出，不判定）
按 1M1M 框架（PMID 40727088），每个分支的 3d 结尾列出需要治疗评估小组考虑的因素：疾病进展速度、可逆性、目标组织能否到达、个人获益与风险。**3d 不对这些下结论**，只写"需评估"。病例里已有的相关事实（年龄、病程）可引用。

## 7. 费用与运行
- 大部分判定是确定性计算。LLM 只用在两处：机制原文抽取（每个分支 1 次，加支持度核查），以及先例检索结果筛选（沿用 3c 的两步检索方式）。
- 按非高峰规则运行。

## 8. 待定问题

1. **剪接预测**：是否接入剪接预测（如 SpliceAI 的公开查询服务）？不接的话，剪接纠正几乎总是"不适用 / 无法评估"。接入就是新的外部数据源，需要另立契约。
2. **下载 N1C 补充材料**：Data S1（判定流程 PDF）和 Table S2（上调靶点汇总，xlsx）。都是 CC BY 开放获取，来自 PMC 或期刊网站，放 `.cache/n1c/`、不进仓库。要你同意。没有 Data S1，3.1–3.3 的细则只能按正文和本草案的规则执行，与 N1C 原版可能有出入。
3. **机制出处的优先级**：GeneReviews → ClinGen / GenCC 机制字段 → 文献？只用 GeneReviews 最稳，但有些基因的章节没写机制。
4. **基因剂量耐受数据**（总量敲低用）：是否接入 gnomAD pLI 和 ClinGen 单倍剂量不足评分（都是公开下载）？
5. **碱基编辑的 PAM 与编辑窗口**：要不要取 RefSeq 基因组序列来计算？计算可以确定性完成，但会多出 Cas 变体、编辑窗口等需要约定的参数。不计算就一律写"未评估"。
6. **非 ASO 手段的分级**：用三档描述（本草案的做法），还是也套用五级？
7. **"Outcome Measures & Ranking" 小节**归 3d 还是 Step 4？本草案只提供排序要用的字段（分级、前提是否齐全、有无先例），不做排序。
8. **嵌合 / X 染色体失活**（如 SLC35A2 女性杂合）：正常拷贝是否表达，取决于 X 失活。是一律写"无法评估：取决于 X 失活"，还是另有规则？
9. **3d 与 3e 的分界**：已有体外 ASO 研究、但没进入临床的，算 3d 的先例，还是 3e 的候选？

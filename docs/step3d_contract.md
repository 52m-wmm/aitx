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
| 三种 ASO 手段的五级分类与判定流程 | **N1C VARIANT guidelines** v1.0：Cheerie D, et al. Consensus guidelines for assessing eligibility of pathogenic DNA variants for antisense oligonucleotide treatments. *Am J Hum Genet* 2025. PMID 40139194，PMC12120168（CC BY） | ✅ 正文已取（efetch，开放获取）。五级分类定义逐字见正文 "Classification terms" 节。详细判定流程在补充材料 **Data S1**（mmc1.pdf，约 2400 行）：2026-11-05 经 **Europe PMC 官方补充材料接口**取得（`https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12120168/supplementaryFiles`），存 `.cache/n1c/supp/`。PMC 自己的 bin 路径返回人机验证式的中间页，未绕过。Data S1 的判定细则已并入下面第 3 节 |
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
- **已知局限（2026-11-05 决定）**：暂不接入剪接预测。因此 3.1 几乎总是"不适用"或"无法评估"，报告里要如实写明这是本系统的局限，不是"该变异不影响剪接"的证据。N1C 的 Data S1 也要求剪接判定以 RNA 层面证据（RNA-seq、qPCR）为准："please note that in silico predictions are not to be used as substitutes for RNAseq and qPCR data"（逐字）——所以即便以后接入预测，也只能当线索，不能当结论。
- 已有针对**同一变异**的剪接纠正 ASO（临床或临床前）→ "eligible"（N1C 定义），但要附上那项研究。

### 3.2 ASO 典型外显子跳跃（细则取自 N1C Data S1 "Section A"，逐条引用）

N1C 的判定对象是**外显子**，不是单个变异："While splicing assessments are based on the variant, evaluating the potential for exon skipping are based on the exon, thus an exon skipping approach is applicable to all variants within that exon."（逐字）所以结论按外显子给出，再套到病人的变异上。

代码逐条检查，任一条不满足 → 结论 + 是哪一条：

| # | 判定 | N1C 原文（逐字） | Step 1 字段 | 不满足时 |
| --- | --- | --- | --- | --- |
| 1 | 不能是第一个或最后一个**编码**外显子；单编码外显子基因直接排除 | "The first and last coding exons are usually not eligible for exon skipping as this would lead to the loss of the start or stop codon."；"genes containing exactly one coding exon are not eligible and are disqualified from further analysis" | `transcript_layout.cds` + `transcript_layout.exons` 算出哪些外显子含编码序列（**注意 UTR**：转录本的第一 / 最后一个外显子不一定是编码外显子） | not eligible |
| 2 | 外显子编码长度须为 3 的倍数 | "Out-of-frame exons (containing a number of base pairs not divisible by 3) should be classified as "not eligible" in the case of LoF variants where relevant restoration of the reading frame is the aim." | `exon.coding_nt % 3` | not eligible（例外见下） |
| 3 | 相位 1-1 / 2-2 的框内外显子：跳过后两侧外显子拼接**不得**形成终止密码子 | "Assessors should evaluate whether joining the adjacent exons would form an in-frame stop codon, coded by either a TAA, TAG, or TGA … If this is the case, the exon is not eligible for exon skipping" | 由 Step 1 的 mRNA 序列和 `transcript_layout.exons` 确定性计算（拼接后的新密码子） | not eligible |
| 4 | 外显子编码的蛋白比例 ≤ 10% | "skipping an exon that encodes for more than 10% of the protein is considered "unlikely eligible", and obtaining functional evidence is the expected next step"；公式 "Exon size as coding region in % = (exon length in bp/3) / length of the protein in aa *100" | `exon.coding_nt`、`protein_length` | >10% → unlikely eligible；>10% **且**跨一个以上非重复结构域 → not eligible |
| 5 | 结构域：该外显子不编码关键功能域 | 同上一行的"not eligible"条件 | 需要 UniProt 结构域注释（Step 1 已取 UniProt 号，尚未取结构域）→ 暂判"无法评估：结构域未查"，见待定问题 10 | — |
| 6 | 天然跳跃 / 框内缺失的证据 | "If full-length exon skipping has been observed in individuals who do not show signs of the disease in question … the exon is eligible for exon skipping."；反之"If full exon skipping has been observed and validated and is disease-causing (pathogenic variant), this exon … is not eligible" | 需检索 ClinVar / gnomAD / PubMed；证据须是 RNA-seq 或 qPCR 验证过的 | 有致病性跳跃证据 → not eligible；健康人中存在 → eligible；都没有 → 继续按分子条件判 likely / unlikely |

**例外（N1C 明确列出，逐字要点）**：移码外显子在"最后或倒数第二个外显子内产生终止密码子且蛋白仍有残余功能"时理论上可行；功能获得 / 显性负效应变异可以用跳跃来降低转录本量（归 3.3）；相邻移码外显子一起跳可以恢复阅读框（"designing an ASO that skips two consecutive exons or multiple ASOs may prove to be a challenge"）；已有整个移码外显子缺失时，跳邻近外显子可恢复阅读框；第一个编码外显子在"附近存在框内起始密码子"时理论上可跳。这些都只能判到 unlikely eligible，并写明依据的是哪一条例外。

**大片段缺失**：先看缺失本身是否已保持阅读框（Step 1 `retranslation.same_frame_after_change`）。已保持 → "不适用：阅读框已经保留，外显子跳跃的目的（恢复阅读框）不存在"。

**已获批的外显子跳跃 ASO**：按说明书判断（归 3a）。不覆盖本病人的外显子时，3d 写"已获批产品针对第 N 号外显子，本病人的变异不适用"。

### 3.3 RNA 敲低
- **总量敲低**：只用于功能获得 / 显性负效应（N1C："Variants to be considered for knockdown approaches using gapmer ASOs or siRNA are toxic GoF and DN variants and copy number gains."）。
  - **剂量敏感性阈值（N1C Data S1 "Section B"，逐字）**："Typically, a pLI score of equal to or greater than 0.9, the top three deciles of LOEUF scores, or a ClinGen haploinsufficiency score of 3 (sufficient evidence) indicates haploinsufficiency being a cause of disease"。N1C 把 ClinGen 的人工评定列为最高级证据："We consider a curation from a reputable, independent source, such as the ClinGen consortium, the highest level of evidence for dosage sensitivity."
  - 单倍剂量不足成立时，N1C 仍留一个口子："a knockdown approach should only be considered if the disease caused by haploinsufficiency is less severe than the disorder associated with the GoF or DN variants"。**这一步要比较两种病的严重程度，属于临床判断，3d 不做**：只写"单倍剂量不足成立，总量敲低需要临床比较两种表型的严重程度（超出本节范围）"。
  - 数据来源见待定问题 4（pLI / LOEUF / ClinGen 评分都要新增查询）。查不到 → "无法评估：剂量敏感性未查"。
- **等位基因特异敲低**：只用于杂合的显性负效应 / 功能获得变异（N1C："it is critical that an ASO is designed to specifically target the DN allele while keeping the wildtype product intact"），靶点是变异本身或同一等位上的常见 SNP。Step 1 只有致病变异本身：用变异本身作靶点 → "likely eligible（分子条件）"；需要 SNP → "无法评估：需要单倍型（phasing）信息"。
- 纯合 / 半合子：没有正常等位基因 → 等位基因特异敲低不适用。X 连锁男性按 N1C 要特别说明："downregulation of a gene on the X or Y chromosome can lead to a complete loss of the gene function"。
- **已有同基因敲低 ASO 时仍算 eligible**（N1C 明确）："The gene is still "eligible" for knockdown according to the criteria outlined in Table 5 even if the already available ASO is not suitable for the individual under assessment." 3d 要写明"需为该病人重新设计"。

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

## 8. 待定问题（2026-11-05 更新：第 1、2 条已决定，其余 7 条附建议）

**已决定**
1. ~~剪接预测~~：**暂不接入**，记为已知局限（见 3.1）。
2. ~~下载 N1C 补充材料~~：**已同意并取得**（Europe PMC 官方接口，存 `.cache/n1c/supp/`）。Data S1 的细则已并入第 3 节；Table S2（上调靶点汇总表，mmc4.xlsx）留待 3.4 实现时读取。

**待你决定（7 条，每条附我的建议）**

| # | 问题 | 要点 | 我的建议 |
| --- | --- | --- | --- |
| 3 | **疾病机制的出处优先级** | 依赖机制的手段（敲低、基因替代、上调）必须先知道是功能丧失 / 单倍剂量不足 / 功能获得 / 显性负效应。候选来源：① GeneReviews 的 Molecular Genetics 段落；② ClinGen / GenCC 的机制字段；③ 文献 | **按 ①→②→③ 的顺序，取到第一个明确写出机制的就停**，并把出处和逐字引用记进账本；三者都没有 → "无法评估"。理由：① 已经在本地归档、引用能逐字核对，和 3a 用的是同一套来源；② 是结构化字段，适合做代码判定但覆盖面有限；③ 最容易过度解读（单个家系的推论），所以放最后，且只接受综述或指南性质的表述。不要让 LLM 在没有这三者时"推断"机制 |
| 4 | **基因剂量数据**（总量敲低用） | N1C 给了明确阈值：pLI ≥ 0.9、LOEUF 前三个十分位、ClinGen 单倍剂量不足评分 3 | **接入 ClinGen 的单倍剂量不足评分 + gnomAD 的 pLI / LOEUF**，三者都记录、按 N1C 原文的阈值判定，并以 ClinGen 的人工评定为准（N1C 自己就这么说）。两个来源都是公开批量下载，和现有的 GRAS、RxNorm 本地清单做法一致（下载一次、记 sha256、不进仓库）。查不到就写"无法评估"，不要用 pLI 的经验值替代 |
| 5 | **碱基编辑的 PAM 与编辑窗口** | 要判断"有没有合适的 PAM"需要基因组序列；还要约定 Cas 变体、编辑窗口宽度、旁观者编辑的容忍度 | **暂不计算，一律写"是否存在合适的 PAM 未评估"**。理由：参数（用哪种 Cas、窗口多宽、允许几个旁观者编辑）都是会影响结论的人为选择，一旦写死就等于我们在替临床做判断；而且 Step 1 现在只取 mRNA 序列，不取基因组序列和内含子，接入是另一个数据源。先把"需要哪种编辑器"这一层确定性结论做对（这一层只靠 HGVS 就能判），把 PAM 留给后续节点 |
| 6 | **非 ASO 手段的分级用词** | 三种 ASO 手段用 N1C 五级；基因替代、碱基编辑、上调正常拷贝没有共识标准 | **不套用 N1C 的五级**，用"理论上可行（分子条件满足）/ 不适用（附理由）/ 无法评估（缺什么）"三档。理由：五级是 N1C 对三种 ASO 手段专门定义的，借来用在基因替代上会让读者以为也有国际共识——这正是"写错比不写更糟"要避免的。N1C 自己对上调正常拷贝就**拒绝**分级（"classifications toward eligibility are not defined because this area of ASO therapeutics is less established to date"），我们照做 |
| 7 | **"Outcome Measures & Ranking" 小节归谁** | 官方模板里这一小节在 Tier 3 | **归 Step 4（报告组装）**，3d 只负责产出排序需要的字段：分级、前提是否齐全、有无人体先例、是否已有获批 / 在试产品。理由：排序要同时看 3c（老药新用）、3d（定制疗法）、3e（候选药）三节的内容，放在任何一个子节点里都会只看到自己那一部分。已记在 `docs/step4_contract_todo.md` |
| 8 | **嵌合 / X 染色体失活**（如 SLC35A2 女性杂合、体细胞嵌合） | 正常拷贝到底表达多少，取决于 X 失活比例或嵌合比例；这会直接影响"上调正常拷贝"和"等位基因特异敲低"是否成立 | **一律判"无法评估：取决于 X 失活（或嵌合比例），病例未提供"**，并在缺失信息里列出这一项（和 3a / 3b 处理缺信息的方式一致）。N1C 也只说"it should be considered how X inactivation will affect gene dosage"，没给判定规则。例外：病例明确给出了偏斜失活或嵌合比例的检测结果时，才按该结果判断 |
| 9 | **3d 与 3e 的分界** | 已有体外 ASO 研究、但没进入临床的候选 | **按"手段"分，不按"证据阶段"分**：只要是 ASO / 基因替代 / 编辑这类为该变异定制的手段，无论证据停在体外还是已有个案，都在 3d 写，证据强度如实标注（体外 / 动物 / 个案）；3e 留给**小分子或已上市药物**的体外筛选结果（如 GRIN2B 的 NMDA 受体调节剂）。理由：N1C 的 "eligible" 判定本来就把临床前功能证据算进来（"pre-clinical data is sufficient"），把体外 ASO 研究踢到 3e 会让 3d 判不出 eligible |
| 10 | **结构域注释**（新增，来自 Data S1） | 外显子跳跃的第 5 条判定要知道该外显子编不编关键结构域，N1C 还要求区分"非重复结构域" | **接入 UniProt 的结构域注释**（Step 1 已经取了 UniProt 号和 AlphaFold 模型，加一个结构域字段的成本很低），拿不到就判"无法评估：结构域未查"，**不要**用"蛋白比例 ≤10%"替代这一条——N1C 把它们列为两条独立判定 |

> 第 3、4、10 条都是"要不要再接一个公开数据源"，彼此独立，可以分批决定。第 5 条如果以后要做，建议单独立契约。

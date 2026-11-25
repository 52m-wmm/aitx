# Step 3d 契约：定制疗法（Tier 3 · Bespoke Therapies）——设计与历史修订

> 当前已有实现：`aitx/evidence/bespoke.py:add_bespoke`。下文包含历史提案、验收期望与修订，不能仅凭文件存在认定全部已批准、已实现或已验收。

本节只给分子层面的可行性判断，不把假设性内容写成推荐；病情、个人情况和伦理评估交由治疗评估小组。验收提议需人工核实原文后才能写进评测数据。

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

## 8. 待定问题的处置（2026-11-05 审阅定稿）

### 已决定并执行
| # | 问题 | 决定 |
| --- | --- | --- |
| 1 | 剪接预测 | **暂不接入**，记为已知局限（见 3.1）。3.1 的结论几乎总是"不适用"或"无法评估"，报告里要写明这是系统局限，不是"该变异不影响剪接"的证据 |
| 2 | N1C 补充材料 | **已同意并取得**（Europe PMC 官方接口，存 `.cache/n1c/supp/`）。Data S1 细则已并入第 3 节；Table S2 留待 3.4 用 |
| 5 | 碱基编辑的 PAM 与编辑窗口 | **暂不计算**，一律写"是否存在合适的 PAM 未评估"。只给"需要哪种编辑器"这一层确定性结论（只靠 HGVS 可判） |
| 6 | 非 ASO 手段的分级用词 | **不套用 N1C 五级**。三种 ASO 手段用 N1C 五级；其余用三档："理论上可行（分子条件满足）/ 不适用（附理由）/ 无法评估（缺什么）"。上调正常拷贝按 N1C 自己的做法不分级 |
| 7 | "Outcome Measures & Ranking" 小节 | **归 Step 4**。3d 只产出排序需要的字段：`classification`、`premises_complete`（前提是否齐全）、`human_precedent`（有无人体先例）、`approved_or_in_trial`（是否已有获批 / 在试产品）。已记进 `docs/step4_contract.md` |
| 8 | 嵌合 / X 染色体失活 | 一律判"无法评估：取决于 X 失活（或嵌合比例），病例未提供"，并列进缺失信息。只有病例明确给出偏斜失活或嵌合比例的检测结果时才按结果判断 |
| 9 | 3d 与 3e 的分界 | **按手段分，不按证据阶段分**：为该变异定制的手段（ASO / 基因替代 / 编辑）都在 3d，证据强度如实标注（体外 / 动物 / 个案）；3e 留给小分子或已上市药物的体外筛选结果 |

### 暂缓接入的三个数据源（2026-11-05 决定）

**决定**：第 3、4、10 条暂不接入新数据源。依赖这些数据的判定**一律判"无法评估"并写明缺什么**，同时把缺口列进账本的缺失信息（和 3a / 3b 处理缺信息的方式一致）。

| # | 数据源 | 现阶段怎么做 | 解除条件 |
| --- | --- | --- | --- |
| 3 | 疾病机制的出处 | **只用已在本地归档的 GeneReviews**（Molecular Genetics / Genotype-Phenotype 段落，逐字引用 + 支持度核查）。取不到 → "无法评估：疾病机制在 GeneReviews 中未写明"。**不让 LLM 在没有来源时推断机制**；Step 1 的 `mechanism_hypothesis` 也不能当依据。备查的完整优先级（将来若接入）：① GeneReviews → ② ClinGen / GenCC 的机制字段 → ③ 文献（只接受综述或指南性质的表述，取到第一个明确写出机制的就停） | 3d 跑出结果后，统计因"机制未写明"而无法评估的条数和占比；占比高到影响报告可用性时，再决定是否接入 ② 和 ③ |
| 4 | 基因剂量数据（pLI / LOEUF / ClinGen 单倍剂量不足评分） | 总量敲低的剂量敏感性一律"无法评估：剂量敏感性未查"。**不用 pLI 的经验值或 LLM 判断替代** | 同上：按统计结果决定。接入时按 N1C 原文阈值（pLI ≥ 0.9、LOEUF 前三个十分位、ClinGen 评分 3），以 ClinGen 人工评定为准 |
| 10 | UniProt 结构域注释 | 外显子跳跃的"结构域"判定一律"无法评估：结构域未查"。**不用"编码蛋白比例 ≤ 10%"替代**——N1C 把两者列为独立判定，所以该外显子即使比例合格，也只能到 likely eligible，不能因为比例合格就说结构域没问题 | 同上。Step 1 已有 UniProt 号，接入成本低 |

**统计要求**：3d 的账本按手段记录 `unassessable_reason`，验收脚本汇总每种原因的条数和占比（`out/acceptance/step3d.json` 的 `unassessable_summary`），作为上面三条解除条件的依据。

## 9. 实现（2026-11-05）

- 模块 `aitx/evidence/bespoke.py`，离线测试 `tests/test_bespoke.py`（先写测试，31 条），验收脚本 `scripts/acceptance_step3d.py`，期望 `data/eval/step3d_expectations.json`（8 条，逐条核实原文）。
- 账本：章节 `bespoke_therapies`（已在 `ledger.SECTIONS` 里，层级 hypothesized）；每个分支 × 6 种手段一条记录；另记 `bespoke_mechanism`（每个分支的机制、逐字引用、出处）和 `bespoke_unassessable`（每条"无法评估"及缺的输入）。校验 `bespoke_consistent`：六种手段齐全且各只判一次、分级用词不越界（N1C 五级只给三种 ASO 手段）、"无法评估"必须说明缺什么、负面结论必须指出没过哪一条、结论不得出现 recommended / effective / proven 等词、用到机制的判定必须引用机制证据。
- 确定性计算（无 LLM）：编码外显子与相位（跳过 UTR-only 外显子）、跳过后新密码子是否为终止密码子（用本地缓存的 RefSeq 序列算，不联网）、外显子占蛋白比例、AAV 容量、编辑器类型、X 失活提示。
- LLM 只用于从 GeneReviews 段落抽机制（提示词 `3d-mech-v1`，每分支按 `Molecular Genetics / Molecular Pathogenesis` → `Molecular Genetics` → `Clinical Characteristics / Genotype-Phenotype Correlations` 顺序试），引用必须逐字在该段落里，否则机制视为未知。
- 已核对的真实行为（离线、用本地缓存）：DMD c.7544_9286del → 外显子跳跃"不适用（阅读框已保留）"、基因替代"不适用（CDS 11,055 nt）"、编辑"不适用（大片段缺失）"；KMT2B → 最后一个编码外显子；AGXT c.33dup → 第一个编码外显子、先导编辑；COL1A1 → 碱基编辑（G>A 转换）、外显子 25 占蛋白 2.3% 但结构域未查 → 无法评估。

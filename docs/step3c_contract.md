# 第 3c 步：超说明书 / 扩展使用（Off-label or Expanded-Access Therapies）

> 当前已有实现：`aitx/evidence/offlabel.py:add_offlabel`。本文保留设计与历史修订；本轮仅核对代码存在，未重新验收医学规则或确认历史审批。原独立待办已合并到本文末尾。

## 目的

报告 Tier 2 的 "Off-label or Expanded-Access Therapies" 一节：**有人类用药先例、但没有获批用于本病**的疗法。
写错比不写更糟：这里每一条都要让读者看到"谁、多少人、什么设计、原文怎么说"，不能把个案写成疗效。

## 章节边界（同一药物只放一个章节，用 3.0 的行动键去重）

| 情况 | 章节 |
| --- | --- |
| 已获批用于本病（FDA 说明书适应证点名本病，或 3a 已收录） | 3a（Existing Targeted / Supportive） |
| 有正在招募或尚未开始招募的临床试验（3b 已收录该药 + 本病） | 3b |
| 有本病 / 本基因患者的用药先例，未获批用于本病 | **3c** |
| 只有机制依据（体外、动物、其他疾病），没有本病 / 本基因的人类先例 | 3e |

- 去重：3c 生成候选后，代码按行动键对照 3a、3b 的行动记录，已在前面章节的不再进 3c，并记录"已在 3a/3b"。
- **同时有招募中试验和用药先例**（决定 2）：
  - 药物只能经试验获得 → 只放 3b，先例作为该试验条目的支持证据附上（不单独成 3c 行动）；
  - 试验外也可获得（已获批的超说明书用药、膳食补充剂、扩展使用项目）→ 3b 和 3c 都列，行动键不同（`trial:NCT…` 与药物键），
    两边互相注明"见对方章节"，内容不重复写。
- 3c 内部同一药物多篇先例合并为一条行动，证据逐篇列出。

## "人类先例"的定义（代码判断，LLM 不判断）

1. **至少一名本病（或本基因）患者用过该药**，出处是可解析的 PMID（E-utilities esummary 核对）。
2. **同一疾病或同一基因**：引用句（或同一段）里要同时出现药名和本病名（含同义词，`label_names` 规则）或基因符号。
   机制相似的其他疾病不算，归 3e。
3. **病例报告在 3c 算有效先例**（与 L3 不同）。
4. **已撤稿的文献不算**：PubMed Publication Type 含 "Retracted Publication"，或有撤稿声明（`CommentsCorrections RefType="RetractionIn"`）的一律排除，记入阴性证据。
5. **只写了"可能有益 / 值得尝试"、没有实际用药的文献不算先例**（如 PMID 25182700："SCAR10 patients may benefit from CoQ10 supplementation"）。
6. **证据强度由代码按 PubMed 字段判断并记录**：
   - 设计：病例报告（Case Reports）/ 病例系列或观察性（Observational Study、多例描述）/ 开放标签或单臂（Clinical Trial、Clinical Trial Phase I–II，非随机）/ 对照研究（Randomized Controlled Trial、Controlled Clinical Trial）。
   - 病例数：LLM 逐字摘出报告病例数的句子，代码核对数字在引用里；本病（本基因）病例数与总数分开记（如 "24 例 GRIN 变异，其中 GRIN2B 12 例"）。
   - 无法判断设计或病例数时写"未说明"，不推断。
7. **疗效方向**（每篇一个，由支持度核查过的结果引用决定；决定 6）：阳性 / 阴性 / 不一致（同一篇内）/ 未报告 / 合并用药无法单独归因
   （例：PMID 36693470 司替戊醇与 lumasiran 同用）。
   **药物层面汇总**（2026-11-05 确认，按此顺序判定，先命中先用）：
   1. 有阳性也有阴性 → **结果不一致**；
   2. 无阳性、有阴性 → **已有报告无效**（结论"已有报告无效，不推荐"）；
   3. 有阳性、无阴性 → **报告了改善**（结论强度不超过原文）；
   4. 只有"合并用药无法单独归因"或"未报告" → **疗效证据不足**。
8. **原文不可获取的文献**（无摘要、全文非开放获取，如 PMID 34283403）不能作为先例，记入检索记录"无可获取文本"。

## 来源

1. **PubMed**（摘要 + PMC 开放获取全文），复用 `aitx/evidence/fallback.py` 的检索、摘要、开放获取判定和缓存。
   - 检索式：基因符号或病名（`label_names`）AND（treatment / therapy / supplementation / off-label / compassionate / case）等治疗词。
   - **不沿用 L3 的文献类型过滤**：临床研究在 PubMed 上常只标 "Journal Article"（PMID 32103184 就是如此）。
   - 每个分支取前 20 篇（决定 4），按相关度；账本记检索总数，总数超过 20 时标"已截断"。
2. **ClinicalTrials.gov Expanded Access 记录**（`studyType=EXPANDED_ACCESS`，按病名与基因检索，复用 3b 的检索和相关性过滤）：
   状态为 AVAILABLE 的记录本身就是一条扩展使用途径；NO_LONGER_AVAILABLE / TEMPORARILY_NOT_AVAILABLE 记入阴性证据。
3. **药物在美国的批准状态**（任何适应证）从 FDA 说明书（openFDA）判断，复用 3a 的说明书检索：
   - 已获批（任何适应证）→ **超说明书用药**，记录说明书 set id、版本、批准的适应证；
   - 未获批 → 只有存在扩展使用途径（ClinicalTrials.gov Expanded Access 记录，或文献写明的同情用药 / 扩展使用项目）时才列，否则不列，记阴性证据；
   - **膳食补充剂 / 食品成分**（D-半乳糖、L-丝氨酸、辅酶 Q10；决定 1）：单列一类"可作为膳食补充剂获得"，**仍须有人类先例**；
     报告注明"非 FDA 批准药品，产品质量和剂量缺乏监管"。是否属于补充剂由代码按受控名单判断（名单写进配置并注明出处），LLM 不判断。

## 核验

- LLM 只摘逐字引用：用药句、病例数句、结果句、剂量句、条件句。代码核对：
  - 引用逐字出现在已获取的文本（摘要或开放获取全文）里；
  - PMID 可解析，且不是撤稿文献；
  - 用药引用里同时出现药名和本病（或本基因）——不满足即不算先例；
  - 数字（病例数、剂量）在引用里。
- **疗效结论**走 3.0 支持度核查，结论句由代码按模板生成，**强度不能超过原文**：
  - 原文是 "shows promise"、"may"、"associated with" → 结论只能写"报告了改善 / 提示可能有益"，不能写"有效"；
  - 原文报告无效（如 PMID 32418144 "Stiripentol fails to lower plasma oxalate"）→ 必须原样写出，并与有效报告并列；
  - 摘要未报告结果、全文又不可获取 → 写"有用药记录，结果在可获取的文本中未报告"。
  - **只有阴性报告的药物也列入**（决定 6），结论写成"已有报告无效，不推荐"，并引用阴性原文；报告中的呈现方式由 Step 4 决定（已记入 Step 4 待办）。
- **剂量**只作为"文献报告的用法"逐字引用（如 "oral l-serine (500 mg/kg/day in 4 doses)"），不写成推荐剂量，不换算。

## 对照病人

- 先例文献里的适用条件（年龄、变异类型、功能效应、肾功能等）由 LLM 逐字摘出，代码比较，复用 3a / 3b 的 `evaluate` 和"满足其一"、放宽从句、合子状态等已有规则；禁忌复用 3a 的说明书禁忌与注意事项（超说明书药物的说明书禁忌照样适用）。
- **变异功能效应**（功能缺失 / 功能获得）是新的条件类型（决定 3），按三档判断：
  1. Step 1 预测**触发 NMD 的截短变异**，或**整基因缺失** → 判为功能缺失，标为**推理证据**（前提：Step 1 的 NMD 预测；不是功能实验）；
  2. **错义变异**和**预测逃逸 NMD 的截短变异** → 未知（有条件），除非病例原文或 ClinVar 记录里有功能实验结果
     （例：GRIN2B p.Gln919Ter 位于最后一个外显子，预测逃逸 NMD → 未知）；
  3. 判为**功能获得**、且药物对功能获得型可能有害（如 L-丝氨酸用于 GRIN 功能获得型）→ 会产生"不适用"，**这条规则实现前先报审**，
     未批准前一律按未知处理。
- 缺信息 → 有条件，并进缺失信息表（按变量类型合并）。
- 遵守改动审批规则：**可能产生新的"不适用"的比较规则，先报再改**。

## 账本与校验

- 行动记录（`section: off_label_expanded_access`）增加：
  - `precedents`：每篇 {pmid, 设计, 本病 / 本基因病例数, 总病例数, 结果引用, **疗效方向**, 剂量引用, 是否开放获取全文, 撤稿检查结果}；
  - `efficacy_direction`：药物层面汇总（阳性 / 阴性 / 结果不一致 / 未报告）；
  - `product_class`：处方药（已获批，超说明书）/ 未获批药物（经扩展使用）/ 膳食补充剂；
  - `regulatory`：{美国批准状态, 说明书 set id 与已批准适应证, 扩展使用途径（NCT 或文献）}；
  - `strength`：最强的一篇的设计与病例数（报告排序用）。
- 检索记录：PubMed 检索式、日期、总数、取回篇数、是否"已截断"；Expanded Access 检索；FDA 说明书检索；无可获取文本的文献。
- 阴性证据：没有任何先例的分支 → `searched_none`；被排除的文献逐篇写原因（撤稿 / 无实际用药 / 其他疾病 / 只有体外或动物）。
- 校验（不过则 fail）：

| 校验 | 内容 |
| --- | --- |
| 先例有效 | 每条 3c 行动至少一篇 PMID 可解析、未撤稿、引用里同时有药名和本病 / 本基因 |
| 去重 | 没有行动同时出现在 3a / 3b 与 3c |
| 强度如实 | 每篇先例有设计与病例数（或"未说明"）；结论句通过支持度核查，且不含强于原文的词 |
| 批准状态 | 每条行动有美国批准状态；未获批的有扩展使用途径记录 |
| 剂量 | 剂量只出现在逐字引用里，不出现在代码生成的结论句中 |
| 疗效方向 | 每篇先例有疗效方向；药物汇总按上面四条的顺序由代码算出；"已有报告无效"的结论句为"已有报告无效，不推荐" |
| 补充剂 | 膳食补充剂类行动带"非 FDA 批准药品，产品质量和剂量缺乏监管"说明，且有人类先例 |
| 3b / 3c 互注 | 同一药物同时出现在 3b 和 3c 时，两边都有指向对方的注明 |

## 验收（只用练习病例；期望先人工核实原文，2026-11-05 已读下列摘要）

| 病例 | 期望 | 核实依据 |
| --- | --- | --- |
| PRAC-SLC35A2-ex7 / ex8 | D-半乳糖进 3c；证据强度：单臂、开放标签、10 例；结论不强于原文（"shows promise"） | PMID 32103184 摘要："Ten patients with SLC35A2-CDG were supplemented with oral D-galactose for 18 weeks…"；"Oral galactose is well tolerated and shows promise as dietary therapy." |
| PRAC-GRIN2B（p.Gln919Ter，杂合） | L-丝氨酸进 3c，**有条件**：适用于功能缺失型变异，本例功能效应未知（最后一个外显子的截短变异，预测逃逸 NMD）；证据：2A 期非随机开放标签单臂 24 例（GRIN2B 12 例），观察性 2 例 | PMID 38380699："the first non-randomized, open-label, single-arm trial (NCT04646447)…"、"Patients had GRIN2B, GRIN1 and GRIN2A variants (12, 6 and 5 cases, respectively)"；PMID 36758276（2 例，"treated experimentally… with oral l-serine (500 mg/kg/day in 4 doses)"）；随机 n-of-1 试验 PMID 41265180 摘要**尚未逐字核对**，核对后再决定是否写入 |
| PRAC-ANO10 | 辅酶 Q10 进 3c；先例：3 名同胞，不设盲用药；**结果在可获取的文本中未报告**（摘要未写，全文非开放获取） | PMID 30838263 摘要："Data also are provided on unblinded therapy with coenzyme Q10"；PMID 25182700 只写 "may benefit"，不单独算先例 |
| 反例：PRAC-GRIN2B / D-丝氨酸 | **不进 3c**：唯一的人体报告已撤稿 | PMID 28734458，PubMed 类型 "Retracted Publication"，撤稿声明 Biol Psychiatry 2018;83(8):715 |
| 反例：PRAC-GRIN2B / NMDA 受体正向变构调节剂（妥布霉素、孕烯醇酮硫酸盐等） | **不进 3c**（只有体外研究，归 3e） | PMID 32712275 摘要：在表达变异受体的体外系统中评估 |

| PRAC-AGXT-c33dup / 司替戊醇 | 进 3c，**超说明书**（FDA 批准用于 Dravet 综合征）；疗效汇总**已有报告无效**，写明"没有支持有效的证据（1 篇阴性，1 篇合并 lumasiran 无法归因）"，不写"不一致" | PMID 32418144（病例报告，同情用药，依赖透析的婴儿）："Stiripentol may not be useful to reduce P Ox in PH patients with advanced chronic kidney disease" → 阴性；PMID 36693470（病例报告，51 岁移植后）："He received stiripentol and lumasiran without adverse events… kidney biopsy showed a complete regression of oxalate crystals"；"Further studies are needed to assess whether this strategy is effective" → 合并用药，无法单独归因；PMID 34283403 无摘要、无开放获取全文 → 不能作为先例，记"无可获取文本"；PMID 31451300 为评论、无摘要 → 同上 |

## 费用与运行

每个分支：PubMed 检索 1 次 + 每篇文献 1 次 LLM 抽取（≤20 篇）+ 每条候选结论 1 次支持度核查。LLM 只在非高峰时段运行（`--offpeak-only`，每次调用前检查）。

## 已定决策（2026-11-05 审阅）

1. 膳食补充剂单列"可作为膳食补充剂获得"，仍须有人类先例；报告注明"非 FDA 批准药品，产品质量和剂量缺乏监管"。
2. 同时有招募中试验和先例：只能经试验获得 → 只放 3b，先例附为支持证据；试验外也可获得 → 3b、3c 都列（行动键不同），互相注明，不重复写内容。
3. 新增功能效应条件，三档（见"对照病人"）；判为功能获得且药物可能有害（产生"不适用"）的规则先报再改。
4. 每分支 20 篇；账本记检索总数，超出标"已截断"。
5. PH1 / 司替戊醇作为第 4 个用例；按汇总规则第 2 条，期望为"已有报告无效"：没有支持有效的证据（1 篇阴性，1 篇合并 lumasiran 无法归因）。
6. 只有阴性报告的药物也列，证据有"疗效方向"字段；只有阴性的写成"已有报告无效，不推荐"。报告呈现方式记入 Step 4 待办。

## 修改（2026-11-05，第 2 版确认后）

1. **准入只看人类先例；获取途径改为描述字段**，由代码判定，依次为：FDA 批准药物（openFDA 说明书）/ 膳食补充剂（NIH ODS DSLD，受控名单审定后生效）/ 食品物质（FDA GRAS 通告库，本地导出，`.cache/fda_gras/`，文件内记有更新与下载日期）/ 扩展使用（ClinicalTrials.gov AVAILABLE 记录）/ 只能经试验获得 / 未确认。
   - "只能经试验获得" = 有招募中的试验含该药，且前四类都不成立 → 放 3b，先例附上；
   - 其余进 3c；"未确认"的注明 "Access route not confirmed; confirm with the treating physician."；补充剂和食品物质注明"非 FDA 批准药品，产品质量和剂量缺乏监管"。
   - GRAS 只决定获取途径这一栏，按物质名精确匹配（"serine endopeptidase" 不算 L-丝氨酸）。
2. **病例数核对不上时写"未说明"，不再丢弃整条先例**（PMID 30838263 曾因此被丢弃）。
3. **32103184 的设计**：PubMed 只标 Journal Article，摘要无设计词；全文 PMC7275909 是作者稿，不在开放获取子集，当前不用（作者稿是否加为可用来源待审），因此设计为"原文未说明"，病例数 10。原期望的"单臂、开放标签"是未经原文核实的推断。
4. **已知局限：20 篇上限会截断大病种**。PH1 检索 355 篇（只看病例报告 / 试验 / 观察性也有 64 篇），两篇司替戊醇病例报告排在 20 名之后，没有读到；账本标"已截断"。是否放宽上限待审。
5. **用来源别名去重**（2026-11-05 实施中发现）：RxNorm 把 "vitamin B6"（42954）和 pyridoxine（684879）编成不同代码，"vitamin B6" 因此进了 3c，与 3a 的吡哆醇重复。现在只要 Tier 1 行动的证据原文在**行动名紧随的括号里**写出该名称（如 GeneReviews "Pyridoxine (vitamin B6 analog)"），就视为同一行动，不进 3c，决定记录里附原文；句中其他位置出现的名称不算。同一篇文献只算一条先例。

## 修改（2026-11-05，第二批决定）

1. **补充剂受控名单已批准**（`config/supplements.json`，出处 NIH ODS DSLD）：L-丝氨酸、辅酶 Q10 列入；D-半乳糖不列，获取途径保持"未确认"。别名只收确定同义的写法（"serine" 不作为 L-丝氨酸的别名）。
2. **两步检索**（替代单纯的 20 篇上限）：
   - 第 1 步：按相关度取前 200 篇的摘要（只用 E-utilities，不调 LLM），代码用药物词典（RxNorm 全部成分名，RxNav allconcepts，本地缓存；加补充剂名单；排除水、钠、葡萄糖等普遍物质）筛出标题或摘要里出现具体药名的文献。
   - 第 2 步：筛出的文献里，含"Tier 1 以外的新药名"的排在前面，其余按相关度；最多 20 篇交给 LLM 抽取。
   - 账本记每步数量：命中总数、筛查篇数、含药名篇数、来自综述参考文献的篇数、交给 LLM 的篇数。
3. **PMC 作者稿可用**（L3 与 3c 都适用）：PMC 记录带正文，且有知识共享许可、PMC 作者稿标记（`pmc-prop-manuscript`）或开放获取标记之一即可用；依据写进许可字段（如 "[PMC author manuscript] …"）。许可原文见 PMC 版权声明页："available free to read, text mine, and for other uses consistent with the principles of Fair Use."
4. **综述不算先例，只作线索**：PubMed 类型为 Review / Systematic Review / Meta-Analysis 的文献不交给 LLM 抽先例，在账本里记为背景（`reviews`，role = background）；用 E-utilities elink（pubmed_pubmed_refs）取其参考文献，原始报告中标题或摘要同时出现本病（或本基因）和药名的进入候选池，以原始报告为先例；原始报告拿不到原文的不算。
5. **两步检索的补充**（实施中发现，均为放宽）：
   - 第 1 步加一路检索：同一检索式限定 Case Reports / Clinical Trial / Observational Study / "case series"，取前 200 篇，与主检索合并后筛查（只增加召回，不是过滤）。起因：PH1 两篇司替戊醇病例报告在主检索里排在 200 名之后。
   - 排序时"新药名" = 出现在 RxNorm 处方药品（SCD / SBD）名称里的成分或补充剂名单，不在 Tier 1，且不是池中常见词（出现在超过 15% 的筛查摘要里的物质视为该病背景，如 PH1 的乙醇酸、丙氨酸、草酸钙）；标题里出现新药名的排在更前。筛查本身仍用完整成分词典。
   - 病名或基因可以出现在用药引用或病例数引用里（两句都逐字核对）。起因：PMID 38380699 的用药句只写 "GRIN … variants"，GRIN2B 在病例数句里。
6. **人类先例的"同一基因"要写明是患者的遗传病**（收紧，2026-11-05 实施中发现）：只出现基因符号不够，基因要带变异 / 突变 / 缺乏 / -related / 患者 / 携带者等上下文；提到癌症或肿瘤、但没提本病名的引用一律不算。起因：AGXT 在结直肠癌文献里作为表达标志物出现，贝伐珠单抗、奥沙利铂、西妥昔单抗、5-氟尿嘧啶被误收进 3c。
7. **用药引用不含病名时，文章标题同时写明药名和本病（或带上下文的基因）也算**（放宽）：如 PMID 36758276 标题 "Evidence for effect of l-serine, a novel therapy for GRIN2B-related neurodevelopmental disorder"。
8. **疗效方向的支持度核查同时给出用药引用和结果引用**（同一篇文献，两句都逐字核对）：结果句常不重复药名（PMID 32103184 "SLC35A2-CDG patients demonstrated improvements…"），只看结果句会被判"未提到该药"。
9. **交给 LLM 的 20 篇怎么选**（2026-11-05 实施中逐步定下）：
   - 酶或蛋白名里的物质名不算药名（"glycolate oxidase"、"alanine:glyoxylate aminotransferase"）；
   - 既没有摘要、也没有 PMC 记录的文献读不到原文，不占名额，记入"无可获取文本"；
   - 按新药名**轮流**选：每种新药名每轮各取一篇（标题提到该药的优先），一轮完了再取第二篇，直到 20 篇；只提到 Tier 1 药物或背景物质的文献排最后。这样 20 个名额覆盖尽量多的候选药物，不会被某一种药或噪声词占满，也不偏向罕见或常见药物。
10. **麻醉、镇静、操作或诊断用药不算治疗先例**（收紧；提示词 `3c-v2`）。起因："Anesthesia was induced and maintained with sevoflurane"（PH1 患儿手术麻醉）被收进了 3c。
11. **疗效方向的核查论断不再预设"多名患者"**（`direction_claim`）。起因：原论断写成"patients with X improved / … in patients with X"，三次判定对每一篇**单病例报告**都答"部分支持：只有一名婴儿，不是患者普遍"，所以任何病例报告都得不到方向，司替戊醇（32418144，"we did not observe a decrease in P Ox … stopped administration"）只能落到"证据不足"。现改为"the patient or patients with X described in this report"。病例数另记在 `n_disease`，不进论断，结论句也照常写出依据的篇数。
    - 性质：让核查能确认原文本来就写了的结果（未知 → 确定的"报告无效"或"报告改善"）。这只是"写清原文说了什么"，不涉及适用 / 不适用判定。司替戊醇的期望已在审阅中定为"没有支持有效的证据"，这次改动正是为了让它成立。
    - 离线测试：`test_direction_claim_does_not_require_several_patients`。反向验证：STS（40432890）的引文没写出患者是 PH1，仍判"不支持"，方向保持 not_reported；贝伐珠单抗、碳酸镧见下条待定。
    - **待定（未改）**：正向论断写的是"患者改善"，而负向论断写的是"没达到预期效果"，两者不对称。贝伐珠单抗（33737053，眼部病变对治疗有反应）和碳酸镧（34258537，血浆草酸明显下降）的原文只说某个具体指标或并发症好转，核查答"部分支持：不是整体改善"，所以仍是 not_reported。要不要把正向论断改成"报告中所测的指标或并发症好转"，并把指标写进记录（报告里只能说"血浆草酸下降"，不能说"患者改善"），等审阅决定。
12. **阳性结论只写"所测指标或并发症改善"**（2026-11-05 决定；提示词 `3c-v3`）。抽取时多取 `outcome_measure`（结果句里所测或观察到的指标，逐字，必须在 `outcome_quote` 里，否则视为未给出）。阳性核查论断改为"After receiving X, <指标> improved in the patient or patients …"；没有给出指标时写"an outcome measured or observed improved"。结论句写"Improvement has been reported in <指标>"；没有指标时写"an outcome the source does not name"，**不写"患者好转"**。阴性论断不变。
    - 测试：`test_outcome_measure_is_kept_only_inside_the_outcome_quote`、`test_positive_claim_is_about_the_measure_not_the_patient`、`test_improvement_conclusion_names_what_improved`。
13. **针对特定并发症的用药带"针对的症状"条件**（2026-11-05 决定）。抽取时多取 `target_quote`（文献说明该药是用于某个并发症或症状而非疾病本身时，逐字；不在原文里的整条否决）。**所有**先例都写明针对的并发症时，每个不同的并发症记一条条件（`target_symptom: true`），几个并发症之间是"任一满足即可"的关系（alternative）；只要有一个先例是治疗疾病本身，就不加这个条件。
    - 病人是否有该症状：沿用 3a 的 HPO 上下位匹配（`established.manifestation_status`）。有 → 满足；没报告 → 未知（有条件），记入缺失信息"manifestation"。
    - **病例明确否认该症状 → 不适用**（2026-11-05 批准）。按病人事实的否定核验规则（同 3b 契约"病人事实"：引用里必须有否定词，`patient_facts.DENIAL`）：Step 2 标为"无"、且病例原文引用含 no / not / never / without / denies 等词，才判"不满足"；标为"无"但引用里没有否定词 → 当作没提到（有条件，备注 `UNVERIFIED_ABSENT_NOTE`），不用这条事实。
    - 测试：`test_target_quote_must_be_verbatim`、`test_target_status`（明确否认 → 不满足；反向：没有否定词或没有引用 → 未知）、`test_target_lines`（明确否认 → 不适用、不记缺失信息；有一个先例治疗疾病本身 → 不加条件；两个并发症 → 互为替代）。
14. **验收只计新鲜输出**（2026-11-05 批准，3a / 3b / 3c 验收脚本同用 `runmeta.freshness`）。输出的 `_meta` 新增 `code_fingerprint`（`aitx/`、`config/`、`scripts/run_pipeline.py` 下所有受版本管理或新建文件内容的 sha256，未提交的改动也能区分）。下列任一情况判"过期"，该病例的期望**不计分**、整体不通过：没有输出；没有代码指纹（本检查之前生成）；代码指纹与当前不一致；病例输入指纹不一致；上游 Step 1 / Step 2 输出文件在此后改变。测试 `tests/test_freshness.py`。
15. **基因家族名可以代表病人的遗传病因**（2026-11-06，`gene_family`）。起因：L-serine 的 2A 期试验（PMID 38380699）把入组人群写成 "patients aged 2-18 years with GRIN loss-of-function pathogenic variants"，标题写 "GRIN-related encephalopathy"，GRIN2B 只出现在摘要别处；按原规则这篇被判"引文既没提疾病也没提基因"，GRIN2B 病人因此拿不到这条先例。
    - 规则：基因符号中被第一个数字截断的字母前缀，**且至少 4 个字母**，才算家族名（GRIN2B → GRIN、CACNA1A → CACNA、KCNT1 → KCNT；ANO10、SCN2A、COL1A1、SLC35A2、AGXT 没有家族名）。家族名只在与完整符号相同的"基因作为病人病因"句式里才算（"GRIN variants"、"GRIN-related encephalopathy"），单纯提到不算，癌症语境照旧排除。
    - 同时放宽句式：基因符号与病因名词之间允许最多 3 个**小写**限定词（"GRIN2B loss-of-function pathogenic variants"）。只允许小写，避免把另一个基因符号吞进来。
    - 性质：放宽收录（会多出先例、可能新增有条件条目），不会产生新的"不适用"。按审批规则先做后报。
    - 测试：`test_gene_family_only_for_long_prefixes`、`test_family_counts_only_as_the_patients_condition`（含反向：裸提及、别的家族、癌症语境、前缀过短都不算）；`test_gene_may_be_named_in_the_patient_count_quote` 的反向用例改为"别的基因家族"，并注明原用例为何不再适用。

## 跨分支同一药物合并（2026-11-11，盲测后修复 N4）

同一药物（同一行动键）在多个诊断分支各生成了 3c 行动时：各分支的先例**一致**（同样的文章、同样的方向和对象判定）→ 合并为一条行动（`applies_to`、`status_by_branch` 合并，要求行重新编号，记 `merged_branches`）；**不一致** → 保持分开，互相标 `same_action_other_branches`，并记入账本 `possible_duplicates`（kind `cross_branch`），由 Step 4 决定呈现。起因：SFTPC 的甲泼尼龙在两个分支各写了一条（同一篇 PMID 33179299）。不一致的例子：GRIN2B 的美金刚，两个分支的病名不同，上下文核查对同一篇文章给了不同方向（not_reported / mixed）。测试：`tests/test_duplicates.py`。

## 先例病人的年龄、性别是先例描述，不是条件（2026-11-15 用户决定）
LLM 抽出的先例条件里 `field` 为 age / sex 的（"17-month-old infant"、"37-year-old man"）不再作为本病人的条件行，改记在先例的 `demographics`。测试 `tests/test_offlabel.py`。

## 先例变异描述与阴性结果引文（2026-11-16 用户决定）

- 先例条件中 `variant` / `variant_class` 同样只描述先例病人，改记为 `precedents.patient_description`，不限制当前病人，也不列缺失信息；功能机制限制 `variant_function` 照旧保留。实际例子：STS 的 AGXT c.823_824dup 不是本病人的必需变异；针对的并发症仍是条件。
- 聚合为 reported_ineffective 的药物，为负向先例另记逐字核实的 `outcome_quote` 证据，给药证据仍保留。报告优先完整引用结果句，而不是只引给药句。没有改疗效方向或 LLM 提示词；正反测试 `tests/test_offlabel.py`、`tests/test_report.py`。


## 历史待核对事项（由原独立待办合并）

以下保留原始问题，完成状态需逐项对照当前代码与验收结果核实；不把旧建议自动当作现行规则。与正文已明确修订的规则冲突时，旧建议不覆盖后续决定。

## 盲测重点检查项：3c 检索排序规则（2026-11-05 记录）

以下规则是在验收病例（SLC35A2、GRIN2B、ANO10、AGXT）上逐步调出来的，有过拟合风险。后续盲测（新的练习病例、不看期望先跑）时要逐条检查：
- **背景词频率阈值**（`COMMON_SHARE = 0.15`）：在检索结果中出现比例超过 15% 的物质名不参与新药排序。阈值是对着 AGXT（calcium oxalate）、GRIN2B（glutamate）定的；检查真正的候选药会不会因为常见而被排到后面（ANO10 只有 6 篇时，CoQ10 本身就被算成背景词，靠篇数少才没漏掉）。
- **酶 / 蛋白名排除**：去掉酶名里的物质名（"glycolate oxidase" 里的 glycolate）。检查有没有误删真正的药物名，或漏删新的酶名写法。
- **按药轮流选取**（每种新药每轮一篇、标题提到的优先、上限 20）：检查候选药很多（> 20 种）时，有没有把有效证据最强的文献挤掉。
- **主要研究设计召回路径**（病例报告 / 临床试验 / 观察性研究另查 200 篇）：检查这条路径单独贡献了多少入选文献。
- **基因家族名算病人病因**（`gene_family`，前缀 ≥ 4 个字母）：这个长度阈值是为了让 GRIN2B 通过 L-serine 试验（PMID 38380699）这个**已知用例**才定的——4 个字母刚好让 GRIN、CACNA、KCNT 算家族，而把 ANO、SCN、COL、SLC 排除在外。盲测要检查：① 有没有因为阈值太松，把同家族别的基因的报告当成本病人的先例（例如 SCN2A 病人收到 SCN1A 的报告——SCN 只有 3 个字母，现在不会，但类似 CACNA1A / CACNA1C 这类会）；② 有没有因为阈值太紧而漏掉真正的家族试验。
- **基因符号与病因名词之间允许 3 个小写限定词**：同样是为通过上面那个用例放宽的，检查有没有把不相干的从句连起来。
- 每次盲测记录各步篇数（`offlabel_searches.*.steps`），与验收病例比较。


## 盲测重点检查项：3e 的排序权重（2026-11-06 记录）

3e 的候选排序（`repurposing.rank_key`）：有无实验证据 → 靶点层级（亚基 / 复合体 / 家族）→ 到达路径（同靶点 / 同通路）→ 物种（动物优于细胞，仅作并列时的次序）→ 临床阶段。上限 10 条，其中无实验证据的最多 3 条。
这组权重和两个上限都是对着 GRIN2B 这个已知用例定的（方向过滤后只剩 3 条候选，全是家族层级、全无实验证据）。盲测要检查：① 某个基因候选很多时，前 10 条是否仍是证据最强的；② "无实验证据最多 3 条"会不会把唯一有实验证据的候选挤掉（现在的实现是先按完整度排序再取，不应发生，但要验证）；③ 家族层级降权后，是否出现"整节只剩家族层级候选"的情况——若是，结论句要让读者看出证据底子薄。


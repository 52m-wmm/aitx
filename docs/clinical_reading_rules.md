# 医学文献阅读规则（v1.0，2026-11-11）

> 这是**怎么读**来源的规则，不是医学知识。全部从盲测批次 20261108 的写错里提炼，每条都有盲测里的真实例子。
> 用途：
> 1. **Step 3 语义核查（上下文核查）提示词的依据**——核查项按这里的规则拆（见 `docs/post_blind_fix_plan.md` 第二节）；提示词只写原则，不放这里的例子（测试集案例不得进提示词，`eval_support_check.py` 的泄漏检查会拦）。
> 2. **审查输出时的清单**——人工或 Claude 审查任何一份报告 / 账本时逐条过一遍。
> 例子的格式：**原文片段** / **正确读法** / **错误读法**（流水线当时的读法）/ **测试集条目**。测试集指 `data/eval/support_check_regression.json`（`CLAIM-*`、`SAME-*`），或标明的离线测试文件；"待补"表示修复时要补成案例。

## 规则一览

| # | 规则 | 盲测例子 |
| --- | --- | --- |
| R1 | 基因出现在记录里，要分清它是病人的**病因**还是**肿瘤标志物 / 检测指标** | LRPPRC 结直肠癌试验 |
| R2 | 表格行只对**该行所属的病种 / 亚型 / 基因**成立 | Leigh 总论表 7 的生物素、硫胺素 |
| R3 | **他基因、他亚型、他物种**的证据不能直接套用到本病人 | 避免强光、西地那非、PXT3003、PMP22 试验、CMT4J 试验 |
| R4 | **不良反应报告不是治疗先例** | 伏立康唑 |
| R5 | 禁忌语境里的例外从句是**豁免**，不是触发条件（极性相反） | 丙戊酸 |
| R6 | 条件的**程度不可放大或缩小** | 碳酸氢钠"明显酸中毒" |
| R7 | 判断一句话要看**完整上下文**，孤立一句不够 | GEMIN5 辅酶 Q10、FOXF1 长综述、艾地苯醌 |
| R8 | 原文报告了改善，不能写成"没有证据表明有效"；证据少就说证据少 | 核黄素、生酮乳剂、毛果芸香碱、甲泼尼龙 |
| R9 | 原文有人群限定的建议，**保留限定**写成有条件，不丢弃也不泛化 | FOXF1 肺移植 |
| R10 | **短缩写不能单独作为病名证据** | LS-SCLC、3BNC117-LS、LSS |
| R11 | 换了说法的**同一行动**只算一条，不在两节各写一次 | 防紫外线墨镜 |
| R12 | 多病种试验里**挂在某亚组下的入组标准**只对该亚组生效 | Acti-Adult "seropositive"（待判） |
| R13 | 原文点名的**病种群**不等于诊断；有更具体的、与之相容的证据时取更具体的 | Leigh 综合征 vs 法裔加拿大型；CMT vs CMT1B |

---

## R1 基因作为病因 vs 标志物
**规则**：记录里出现病人的基因符号，只有当它是**受试者 / 病人的致病原因**时才算与病人相关；作为肿瘤标志物、表达水平、检测阳性等出现时与病人无关。
- **原文片段**：试验 NCT07337551 "Gossypol Acetate + FOLFIRI + Bev in mCRC With TP53-Mutant and **LRPPRC Positive**"
- **正确读法**：LRPPRC 在这里是结直肠癌的肿瘤标志物，试验与 Leigh 综合征病人无关。
- **错误读法**：Conditions / Keywords 里有 LRPPRC → 判为相关，列给线粒体病病人（批次 1，写错 2 条）。
- **测试**：`tests/test_gene_context.py`（癌症语境与标志物用法被拒；KCNT1 / GRIN2B / OTC 罕见病试验靠基因仍被收）。

## R2 表格行所属亚型
**规则**：总论里按病种 / 亚型 / 基因分行的表格，每一行的建议只对该行点名的病种成立；先看这一行的病种列，再看建议列。
- **原文片段**：Leigh 综合征谱系总论（NBK320989）表 7，病种列 "Biotin-thiamine-responsive basal ganglia disease (thiamine transporter-2 deficiency)"，同一行的治疗列给出生物素和硫胺素
- **正确读法**：生物素、硫胺素是生物素-硫胺素反应性基底节病的疗法，不适用于 LRPPRC 病人。
- **错误读法**：作为 LRPPRC 病人的"已有靶向治疗"写出（批次 1，写错 4 条，含辅酶 Q10、生酮饮食）；修复中还出现过"引文只有一个词 Thiamine，恰好也在病种格里"导致该行没被检查的回归。
- **测试**：`tests/test_gene_context.py`（别的病种行被丢、本基因行和本病行被留、一词引文落在病种格里仍被丢）。

## R3 他基因 / 他亚型 / 他物种的证据不可套用
**规则**：证据所说的人群（基因、亚型、物种）与本病人不同时，不能当作本病人的证据；最多作为"有条件 / 假设性"，并写明证据来自谁。原文没说明先例病人的基因时，写"未说明"，不当作同基因。
- **例 1** 原文（RP 总论 NBK1417）："Increased exposure to light has been demonstrated to accelerate progression **in animal models** of retinitis pigmentosa, particularly those with pathogenic variants in the gene encoding **rhodopsin** …; thus, avoidance of bright light and use of UV-blocking sunglasses are recommended for all individuals with …"
  - 正确：依据是动物模型、主要是视紫红质基因；对 SNRNP200 病人是有条件的建议。
  - 错误：禁忌"避免强光"判为**适用**（已确立层）。
  - 测试：`CLAIM-SNRNP200-BRIGHT-LIGHT`。
- **例 2** 原文（PMID 41819105）："… sildenafil citrate (Revatio®) in six LS patients carrying different **MT-ATP6** variants"
  - 正确：先例来自 MT-ATP6 相关 Leigh 综合征，不是 LRPPRC；注明来源基因、降为有条件。
  - 错误：作为 LRPPRC 病人的老药新用先例。测试：待补。
- **例 3** 原文（PMID 25519680）："80 adult patients with mild-to-moderate **CMT1A** received … PXT3003"
  - 正确：CMT1A（PMP22 重复）专用，MPZ（CMT1B）病人不适用。错误：列为 MPZ 病人的老药新用。测试：待补。
- **例 4** 试验 NCT07140614 入组标准："verified documentation of genetic testing showing **duplication of the PMP22 gene**"
  - 正确：病人是 MPZ 变异，不满足。错误：判为"有条件"。测试：待补（代码对照基因型，`docs/post_blind_fix_plan.md` D2）。
- **例 5** 试验 "Study of Intrathecal ELP-02 for Charcot-Marie-Tooth Disease **Type 4J**"
  - 正确：CMT4J 专用，MPZ 病人不适用。错误：诊断变宽成"CMT"后收入。测试：待补。
- **例 6**（待判）原文（PMID 19101701）："successful treatment of **a patient with Leigh syndrome** using idebenone"——摘要没写病人的基因。正确读法：先例病人基因未说明，不能当作 LRPPRC 先例；写"先例病人基因未说明"。

## R4 不良反应报告 ≠ 治疗先例
**规则**：文献里"病人用过某药"不等于"该药被用来治疗本病"。先看用药目的：为治疗本病或其表现而用，才是治疗先例；因别的适应证用药、结果是加重或诱发，是**不良反应报告**，只能作为注意事项候选（单个病例写"注意：有个案报告用后加重"，注明个案，不写成禁忌）。
- **原文片段**（PMID 18837430）："We report a case of vincristine related neuropathy that was **exacerbated by voriconazole** in a patient with previously undiagnosed, X-linked CMT."
- **正确读法**：伏立康唑（抗真菌药）加重了 CMT 病人的神经病变——有害报告，可作注意事项候选（个案）。
- **错误读法**：列为老药新用，状态"适用"。
- **测试**：`CLAIM-MPZ-VORICONAZOLE-ADVERSE`。

## R5 禁忌语境例外从句极性
**规则**：在"应避免 / 禁忌"的语境里，"only in / unless / except / other than" 引出的是**豁免**（什么情况下可以不避免），方向与支持治疗语境相反；禁忌本身按一般规则判。
- **原文片段**（RRM2B 专章 NBK195854，Agents/Circumstances to Avoid）："Valproic acid should be used **only in exceptional circumstances**."
- **正确读法**：一般应避免丙戊酸；特殊情况是豁免。
- **错误读法**：禁忌"取决于：特殊情况"（有条件）——读成了"特殊情况下才避免"。
- **测试**：`CLAIM-RRM2B-VALPROATE-INVERTED`（期望不支持）、`CLAIM-RRM2B-VALPROATE-CORRECT`（期望支持）。

## R6 条件程度不可放大
**规则**：原文条件带程度词（significant、severe、refractory、prolonged）时，病人事实必须达到同一程度才算满足；相关但程度未知的事实（某指标升高）只能判"有条件"。
- **原文片段**（Leigh 总论 NBK320989）："Sodium bicarbonate or sodium citrate for **significant acidosis**"
- **正确读法**：病人只有"血乳酸升高"，不等于明显酸中毒 → 有条件。
- **错误读法**：碳酸氢钠、枸橼酸钠判为"适用"。
- **测试**：待补。

## R7 核查需要完整上下文
**规则**：判断一句话是否支持某个读法时，要同时看这句话所在的小节标题、段落、表格表头、文章题目和摘要其他句子；只给孤立一句，核查会因"看不到"而判错（过宽或过窄）。
- **例 1** 原文（PMID 38316953）："We treated two of these patients with oral Coenzyme Q10 (CoQ10), which resulted in neurological improvements …"；病人身份在另一句："compound heterozygosity at the GEMIN5 gene in both cases"，题目也写了 GEMIN5。
  - 正确：两名 GEMIN5 病人用后神经症状改善——报告了改善（个案，不是疗效证明）。
  - 错误：核查只看第一句，3 次一致"部分支持"（看不到病人是谁）→ 方向记为未报告 → 写成"没有证据表明有效"。
  - 测试：`CLAIM-GEMIN5-COQ10`（带上下文时期望支持）。
- **例 2** FOXF1：一篇 2026 年新生儿遗传性呼吸衰竭的管理综述，全文 35 000 字，送给模型的 12 000 字窗口里 ACDMPV 出现 0 次——本病那一节被截掉，抽取 0 条。正确做法：先选含本病名的小节。测试：待补（窗口选择的离线测试）。

## R8 不把"报告了改善"写成"没有证据表明有效"
**规则**：原文报告了改善 / 缓解时，结论写"有报告改善（个案 / 小样本，不是疗效证明）"；证据少就说"现有报告不足以判断疗效"，不写"没有证据表明有效"——后者与原文矛盾。
- **原文片段**：核黄素（PMID 10230482）"regression of neurological impairment under treatment by riboflavin"；静脉生酮乳剂（PMID 10457398）"resulted in rapid clinical and biochemical improvement"；毛果芸香碱（PMID 1191103）"received symptomatic relief"；甲泼尼龙（PMID 33179299）"pulse treatment improves ProSP-C trafficking"。
- **正确读法**：均为"有报告改善"，并注明证据规模。
- **错误读法**：都写成 "Use has been reported, but there is no evidence that it is effective."（盲测中共 6 次）。
- **测试**：`CLAIM-GEMIN5-COQ10`；其余待补。

## R9 有人群限定的建议保留限定
**规则**：原文只对部分病人（较轻 / 较重 / 某年龄段）给出的建议，写成有条件、条件取原文；不能因为"不是对所有病人"就丢弃，也不能去掉限定写成一般建议。
- **原文片段**（PMID 40869921）："Some patients with a **milder form** of ACDMPV exhibit longer survival and, in these cases, lung transplantation may be a potential option"
- **正确读法**：病情较轻的 ACDMPV 病人可考虑肺移植（有条件）。
- **错误读法**：核查论断写成无条件的"文章推荐肺移植"，判部分支持后整条丢弃。
- **测试**：待补。

## R10 短缩写不能单独作为病名证据
**规则**：大写短缩写（≤ 5 个字母）不单独用于检索或匹配；同一记录里必须同时出现全称（或长同义词）或基因名才算命中。
- **原文片段**：Conditions "Limited-stage Small Cell Lung Cancer (**LS**-SCLC)"、Keywords "3BNC117-**LS**"、Conditions "Lumbar Spinal Stenosis (**LSS**)"
- **正确读法**：这里的 LS / LSS 与 Leigh 综合征（LS、LSS）无关。
- **错误读法**：作为 Leigh 综合征的同义词命中，9 条无关试验（肺癌、HIV、腰椎管狭窄）进了 LRPPRC 病人的报告。
- **测试**：待补（`docs/post_blind_fix_plan.md` N1）。

## R11 换说法的同一行动只算一条
**规则**：同一来源、同一句话里的同一措施，即使在两节用了不同说法，也是同一个行动；只在一节写，另一节交叉引用。
- **原文片段**（NBK1417）："… avoidance of bright light and use of **UV-blocking sunglasses** are recommended"；另一句 "use of **UV-A and UV-B blocking sunglasses** is recommended"
- **正确读法**：同一行动（戴防紫外线墨镜），写一次。
- **错误读法**：禁忌节和支持治疗节各写一条。
- **测试**：`SAME-SNRNP200-UV-SUNGLASSES`（目前只列不计分）。

## R12 多病种试验的亚组标准只对该亚组生效（待判）
**规则**：一个试验同时招多种病时，挂在某个病种标题下的入组标准只约束那一种病的受试者。
- **原文片段**（NCT07136844 Acti-Adult，Conditions 含 CMT、重症肌无力等 12 种）："**Myasthenic patients** should be seropositive, and … MGFA class II to IV."
- **正确读法**：这条只约束重症肌无力受试者，对 CMT 病人不适用。
- **错误读法**：作为本病人的入组要求列出，判为未知。
- **测试**：待补。

## R13 病种群名不等于诊断
**规则**：临床文本点名的是一个病种群（Leigh 综合征谱系、CMT），而 ClinVar 等证据指向群内一个更具体的病时，取更具体的；两者无上下位关系时以原文为准。
- **原文片段**（B1 描述，取自 GeneReviews 总论首段）："Nuclear gene-encoded **Leigh syndrome spectrum** (LSS) is a continuum …"；ClinVar VCV000003110（2 星）把 LRPPRC p.Ala354Val 链到 "Congenital lactic acidosis, Saguenay-Lac-Saint-Jean type"。
- **正确读法**：诊断取法裔加拿大型（Leigh 综合征谱系的一员）。
- **错误读法**：按"文本点名优先"取了 Leigh 综合征，随后引入了只看病种群名的试验与 CMT4J 等亚型不符的条目。
- **测试**：待补（`docs/post_blind_fix_plan.md` D1，含"无上下位关系时以原文为准"的反例）。

---

## R14 合并行动按段落分别核查（2026-11-12）
同一行动的依据来自几个段落（例如"新生儿"表和"所有病人"表、正文摘要与表格行）时，每个段落的限定只约束它自己的那份依据：任一段落的依据对病人成立，这条行动就按该段落判定；不能拿一个段落的限定去否定另一个段落面向所有病人的建议。
- 正例（修复前写错）：CFTR，15 岁 F508del 纯合。"airway clearance"合并了 Management 摘要的"Newborns – … airway clearance instruction"和表 6b（Individuals with Cystic Fibrosis）第 1 行"Airway clearance to aid in mucus clearance"；核查只看了新生儿段落，"Newborns"限定把整条行动判成不适用。通便药（表 6a 第 7 行 / 表 6b 第 10 行）、补盐同理。
- 反例：只有新生儿段落依据的条目（"Postural drainage & percussion"，表 6a 第 2 行"Teach parent/caregiver airway clearance"）对 15 岁病人仍为不适用。
- 测试：`tests/test_established.py`（通用段落恢复状态；只有新生儿段落仍不适用；各段落都有限定时任一满足即适用）。

## R15 描述用法或报告无效不是推荐（2026-11-12）
**规则**：原文说"病人常常使用 X"或"X 的试验没有显示效果"，是描述用法或报告无效，不是推荐；这样的 X 不能作为支持治疗或靶向疗法写进报告。只有原文建议使用、或把它列为管理选项时才算推荐。
- **原文片段**（复测 PFN1，GeneReviews ALS 总论 NBK1450 "Symptom Management"）："Individuals with ALS commonly supplement their diets with vitamin E, vitamin C, B vitamins, selenium, zinc, coenzyme Q10 …"；"In a Cochrane Review … significant differences in longevity, muscle strength, or functional rating scales over time were not identified."
- **正确读法**：这些补充剂与抗氧化剂不是推荐措施，条目判不适用、留在账本、不写进报告。
- **错误读法**：13 种补充剂被列为"适用"的支持治疗（Tier 1 写错，用户 2026-11-12 判定）。
- **反例**：同一章节"Medications such as baclofen and benzodiazepines can help relieve spasticity and muscle cramps"是推荐，保持原状态。
- **测试**：`tests/test_context_check.py`（全票"描述用法 / 报告无效"才算非推荐；反向：分歧、推荐、未说明都不改）、`tests/test_established.py`（非推荐 → 不适用并留账本；反向：推荐不变、禁忌节与说明书决定的药不问）。

## 审查清单（逐条过）

审查一份报告或账本时，对每个条目问：
1. 引用里的基因是病人的病因吗？（R1）
2. 这条来自表格行吗？那一行写的是哪个病种？（R2）
3. 证据说的是谁——同基因、同亚型、人类吗？没写就记"未说明"。（R3）
4. 用药目的是治疗本病吗？还是别的适应证、结果是加重？（R4）
5. 在禁忌节吗？条件是触发还是豁免？（R5）
6. 条件有程度词吗？病人事实达到那个程度了吗？（R6）
7. 我看到的是完整上下文还是孤立一句？病人身份、小节标题、表头都看了吗？（R7）
8. 结论措辞和原文的方向一致吗？（R8）
9. 原文有没有"部分病人 / 较轻 / 某年龄"的限定？保留了吗？（R9）
10. 命中靠的是短缩写吗？同一记录里有全称或基因名吗？（R10）
11. 同一行动有没有换个说法在别的节又出现？（R11）
12. 试验标准是不是挂在别的病种亚组下？（R12）
13. 诊断是病种群名吗？有没有更具体的、相容的证据？（R13）
14. 这条行动的依据来自几个段落吗？限定是不是只属于其中一个段落？（R14）
15. 原文是在推荐，还是只说病人常用、或者报告试验无效？（R15）

## 维护

- 新的写错先归到已有规则；归不进去才新增规则，并附盲测或验收中的真实例子。
- 每条规则至少一个测试集案例（正向）和一个反向案例；"待补"在对应修复完成时补齐。
- 规则改动记在文末，写明日期和起因。

## 变更记录
- v1.0（2026-11-11）：由盲测批次 20261108 的写错提炼，13 条。
- v1.1（2026-11-12）：新增 R14（合并行动按段落分别核查），起因 CFTR 气道廓清 / 通便药 / 补盐。
- v1.2（2026-11-12）：新增 R15（描述用法或报告无效不是推荐），起因复测 PFN1 的 13 种补充剂。

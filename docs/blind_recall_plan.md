# 盲测的机械召回评估——方案草案 v0.1（2026-11-10，只写方案，未实现）

> 目的：人工判定只能看"写出来的条目对不对"，看不出"该写没写"。这一项用**不调用 LLM 的确定性脚本**，对每个盲测病例从三个结构化来源列出"应该出现的条目"，再和报告比对，量出漏写。
> 范围：GeneReviews 管理章节（3a 覆盖率）、ClinicalTrials.gov（3b 召回率）、FDA 说明书（3a 靶向节召回率）。**文献类（3c、L3）不做机械召回**，继续人工审查。
> 脚本 `scripts/blind_mechanical_recall.py`，**不在冻结范围**；只读调用冻结模块里的现成函数（相关性规则、行解析等），不改它们。B 组全部跑完后，对 12 个病例一起算，结果写进 `docs/blind_test_results.md`。
> 和评测病例完全隔离：脚本开头调用 `runmeta.refuse_eval_cases`。

## 1. GeneReviews → 3a 覆盖率

**参考集怎么来（确定性）**
- 章节：Step 2 给该病例分配的 GeneReviews 章节（`step2.genereviews[gene]`），就是 3a 实际读的那几章。
- 小节：Management 下的 `Treatment of Manifestations`（含其下各子节）、`Targeted Therapies`、`Prevention of Primary Manifestations`、`Prevention of Secondary Complications`、`Agents/Circumstances to Avoid`、`Pregnancy Management`。
  **排除**：`Evaluations Following Initial Diagnosis`、`Surveillance`、`Evaluation of Relatives at Risk`、`Therapies Under Investigation`（与 3a 契约一致：最后这节留给 3b/3c）。
- 条目单位（三种都计）：
  - **表格行**：每个表格行算一条（用 3a 自己的 `GR.sections_for_llm` 渲染，和 3a 看到的完全一样）；
  - **列表项**：每个列表项算一条；
  - **段落**：按句切分，**含治疗动作词**（treat / give / administer / supplement / avoid / therapy / medication / surgery / transplant / referral to … therapy / diet 等受控词表）的句子各算一条。
- **排除评估 / 监测类**：条目里只有 monitor / surveillance / evaluate / assessment / screening / follow-up / referral for evaluation 这类词、没有治疗动作词的，不计入参考集，但列在附表里供核对。

**怎么算"覆盖"**
- 一条参考条目算"已覆盖"：3a 账本里有一条已核实证据的引文**逐字出现在该条目里**（或该条目逐字出现在某条引文里）。这是机械判定，和账本的 `quote_in` 用同一个函数。
- **被规则有意排除的不算漏写**，单独计"规则排除"：账本 `dropped_conditions` 里记过的（另一病种的表格行、总论里点名别的基因、目的从句等）。它们从分母里拿掉，但逐条列出规则名，方便核对规则本身有没有误杀。

**输出**
- 覆盖率 = 已覆盖 / （参考条目 − 规则排除）；按小节、按条目类型（表格行 / 列表 / 段落）分别给。
- 次级指标：参考条目里能用 RxNorm 词表认出的**药名**，按药算覆盖率（一行可能有好几个药，行被覆盖不等于每个药都被写了）。
- **漏写清单**，每条标注可能原因（按能机械判定的顺序）：
  1. **该行/句从未产出行动**：抽取漏了（账本的 `reextracted_rows` 里也没有它）；
  2. **补抽过但仍无行动**：`reextracted_rows` 里有、标了 `no_treatment`——抽取判它"不是治疗"，需人工看判得对不对；
  3. **产出了行动但被丢弃**：在 `dropped_conditions` 以外的地方没了（例如合并、去重），需人工看；
  4. **条目只在另一个章节里**：同一药在报告里出现了、但引用的是别的小节（算覆盖，不算漏写，但标注）。

## 2. ClinicalTrials.gov → 3b 召回率

**参考集**
- 用 Step 2 给出的**病名和同义词**（与 3b 用的同一份名单）直接查 CT.gov API v2：`query.cond=<名>`，`filter.overallStatus=RECRUITING|NOT_YET_RECRUITING`。**不用基因符号查**（基因查询正是刚修掉的癌症试验混入的来源）。
- 所有返回结果再过 **3b 同一套相关性规则**（`trials.relevance`），通过的才进参考集——这保证"相关"的定义和 3b 一致。

**怎么算**
- 召回率 = 参考集中、出现在 3b 账本 `trial_searches` 的 `analysed ∪ over_cap ∪ ineligible` 里的比例。
- 分两级报：**"看见了"**（上面三者之一）和**"分析了"**（只算 `analysed`）。3b 每个分支最多逐条分析 10 个，超出的进 `over_cap`——这一级的差就是上限造成的损失。

**漏写清单的可能原因**
1. 3b 的检索根本没返回它（检索式构造问题，例如同义词没用上）；
2. 返回了但被相关性规则排除（**本方案用同一规则，所以这一项按定义不会出现**——见下面"循环性"）；
3. 被状态过滤（查询时已限定招募中，理论上不会，出现就说明两次查询之间状态变了，标"时间差"）；
4. 进了 `over_cap`：没漏但没分析；
5. 进了 `ineligible`：登记的年龄 / 性别把病人排除了（不算漏写，单列）。

**循环性要说清楚**：参考集用的是 3b 自己的相关性规则，所以这一项量的是**检索和上限造成的遗漏**，**量不出相关性规则本身的错误**（规则把相关试验判成不相关，参考集里也不会有它）。相关性规则的错误只能靠人工审查——批次 1 的结直肠癌试验就是人工抓到的。

## 3. FDA 说明书 → 3a 靶向节召回率

**参考集**
- openFDA 说明书接口：`indications_and_usage` 里出现该病名或同义词（短语精确匹配）的全部说明书。
- 病名匹配用 3a 自己的 `label_names`（含所属疾病类别，如 "urea cycle disorders"），和 3a 规则 (i) 一致。
- 每份说明书经 `actions.drug_key` 标准化成 RxNorm 成分键，同成分的多份说明书合并成一个药。
- 用 3a 的 `indication_role` 把每个药分成"靶向"（适应证治的是这个病）和"支持"（适应证治的是该病的某个症状，如"seizures associated with …"）。

**怎么算**
- **靶向召回率** = 参考集中"靶向"角色的药、出现在报告"已有靶向治疗"节的比例。
- 附带两项：出现在报告但在**别的节**（多半是支持治疗）→ 标"章节不同"，不算漏写；"支持"角色的药在报告任一节出现的比例，单独列。

**漏写清单的可能原因**
1. 说明书没被 3a 检索到（3a 查说明书的病名集合不同）；
2. 被检索到但适应证角色判定不同（3a 判成支持或不相关）；
3. GeneReviews 已收录该药、按 2026-11-05 的决定"说明书不再把 GeneReviews 收录的药升为靶向"——这是**有意的**，单列"规则使然"。

## 4. 产出

- `out/blind/<批次>/recall.json`：每个病例三项的参考集、命中、漏写清单（含原因标注和原文链接）。
- `docs/blind_test_results.md` 新增一节：12 个病例的三项召回率表（按 A / B1 / B2 分栏，因为 B2 没有 GeneReviews 章节，第 1 项对 B2 不适用），以及漏写清单的汇总（按原因分类计数）。
- 费用：**0 LLM 调用**。CT.gov 与 openFDA 是免费接口，走现有缓存。

## 5. 待你决定

1. **GeneReviews 条目单位**：按"表格行 / 列表项 / 含治疗动作词的句子"计（本方案），还是只按表格行计（更干净但会漏掉散文里的治疗建议）？我建议本方案，三种单位分开报。
2. **规则有意排除的条目**：从分母里拿掉并单列（本方案），还是留在分母里算未覆盖？我建议拿掉——否则修对了的规则（比如刚加的"另一病种表格行"）会被算成漏写。
3. **CT.gov 参考集要不要加基因查询**：本方案只用病名。可以另加一栏"只靠基因查到、且过了新相关性规则的试验"，用来观察修复后的基因路径是否还会漏掉真正相关的罕见病试验（例如登记里只写基因、不写病名的试验）。
4. **FDA 的病名匹配是否包含疾病类别**（"urea cycle disorders" 这种）：本方案包含，与 3a 规则 (i) 一致。
5. **B2 的 GeneReviews 一项**：B2 按定义没有章节，第 1 项写"不适用"，还是改用 GeneReviews 里**提到**该基因的其他章节（如果有）？我建议写"不适用"，保持 B1/B2 的对比干净。

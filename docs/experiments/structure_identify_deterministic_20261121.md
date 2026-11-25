# Step 3a Phase 2：确定性正文补齐与9项名称恢复（2026-11-21）

本轮$0，模型/API调用0。补5个药名对应的4处编号正文，应用另4项已确认结构/缓存处理；15项名称映射、13种未知表头和3项医学语义问题不自动应用。医学规则、Ledger、Baseline、行动ID和key均未改，不进入Phase 3。

## 5项输入覆盖：5/5，来自4处原文

| 名称 | 新输入单元 | S/T | 原文 |
|---|---:|---|---|
| dantrolene | 365 | S1/T1 | Baclofen, tizanidine, or dantrolene may relieve muscle spasms & spasticity. |
| tizanidine | 365 | S1/T2 | 与上一项同句，不重复创建正文 |
| tramadol | 366 | S1/T1 | Tramadol w/acetaminophen & NSAID or COX-2 inhibitor before resorting to other opioids (Nausea is the most common side effect.) |
| topical capsaicin | 367 | S1/T1 | Topical capsaicin is of questionable utility but is safe. |
| topical lidocaine | 368 | S1/T1 | Topical lidocaine (cream or patch) may be useful for localized pain. |

新输入直接消费既有XML解析器保存的表格单元，原句完整进入S编号；不再因为同一行已有Baclofen等行动而漏掉其他单元。每份保留章节、路由、行ID、列号/多级列名、单元格/文本XPath、列表祖先、完整同行各列和列表树，范围与备注不丢弃。

候选仅由本次批准的原词和阳性本地RxNorm缓存建立；没有把句中其他风险名称都当成新治疗T。各项`condition_status=unknown`、`recommendation_status=not_determined`，模型答复为not_requested。药名被识别不等于推荐，capsaicin的questionable utility等文字原样保留，未作疗效新结论。

原365份准备输入/721条正文逐条保留；新增4份准备输入/4条正文后为**369份、725条正文**。新单元是离线来源记录，没有生成模型票、调用计划或待付费执行入口，旧S/T和缓存答复不重绑、不追认为新输入的票。

[5项覆盖及全文](../../out/structure-identify-deterministic-20261121/5-drug-input-coverage.md) · [完整来源、范围及RxNorm证据](../../out/structure-identify-deterministic-20261121/5-drug-input-coverage.json) · [4份新增编号输入](../../out/structure-identify-deterministic-20261121/supplemental-inputs.json) · [完整准备输入](../../out/structure-identify-deterministic-20261121/prepared-inputs.json)。

## 应用4项已确认结构/缓存处理

| 项目 | 已做处理 | 保留的边界 |
|---|---|---|
| 骨健康相关物质/药物父类别 | 在已编号的Management/Agents to Avoid原句中保留父类，不仅保留例药steroids | 完整父类原句和例药缓存分别保存，不把steroids旧票当父类模型票，不判患者适用 |
| acetaminophen | 用既有阳性RxNorm及原文确认药名，单列正确来源候选 | 保留4,000 mg daily in 3-4 divided doses全文；不把旧“Acetaminophen: 4”答复改写或追认为正确剂量抽取 |
| Vitamin D | 从既有Vitamin D & calcium supplementation组合来源及本地RxNorm保留名称 | 不把组合缓存改写成单药三票，原用途和范围保留 |
| calcium | 同上，从组合来源和阳性本地缓存保留名称 | 共用证据不算两个独立临床确认，剂量/适用性仍未知 |

这4项无需重发原句。正确候选独立记录，历史输入、坏名称、旧票和多数结果不修改；不增加疾病专用规则或全局名称重写。

## Accepted名称对齐与剩余未知

- 名称对照**230→239/264（+9）**，增加的是5个补齐正文药名与4项已确认来源名称。
- 仍有**18项名称待审：15项映射＋3项人工医学语义**；另外6项既定设计排除和1项既定AAC别名不变。
- 原43项目标集合仍为**43/43＝41严格同名多数＋2获批来源映射**。新增9项不是新模型多数，不能加到41的三票计数中。
- 原264条对照的case_id、action_id、原名称和全部clinical source_refs保持一致。名称验收状态变化不是医学状态变化，正式Ledger没有写入。

[9项确定性来源候选及旧缓存依据](../../out/structure-identify-deterministic-20261121/deterministic-source-candidates.json) · [新名称对照](../../out/structure-identify-deterministic-20261121/accepted-alignment.json) · [43项覆盖](../../out/structure-identify-deterministic-20261121/43-name-coverage.json)。

### 15项名称映射：逐项建议，均未应用

包括AGXT广义药物类别表述、ANO10 OT/PT、CFTR营养/泻剂/ART、伤口闭合名称、ASM、共享speech therapy、冷热/增稠喂养、营养热量表述、Botox品牌/父类别关系等。每项附原句、XPath、现有缓存和建议边界，不扩大名称映射或源范围。

[15项逐项建议与依据](../../out/structure-identify-deterministic-20261121/pending-15-name-mappings.md) · [原始证据JSON](../../out/structure-identify-deterministic-20261121/pending-15-name-mappings.json)。未再追加别名或合并ID。

### 13种未知表头：逐项建议，均未应用

涵盖Mechanism、Weight、两种年龄剂量列、System、Body Weight、Age (yrs)、三类蛋白摄入量、Deficiency、Administration、Disorder。建议区分机制详情、剂量/营养分层、评估分组、给药详情及来源疾病/基因范围；保留原路由和矩阵关系，不将剂量分层或源范围自动判为病人满足。

[13项原文例子、路由和建议](../../out/structure-identify-deterministic-20261121/pending-13-headers.md) · [全部原文位置JSON](../../out/structure-identify-deterministic-20261121/pending-13-headers.json)。解析器中这些unknown保持不变，等待审核。

### 3项医学语义：继续人工待审

1. CFTR鼻/窦症状的宽泛手术表述，与Management中Sinus surgery/Polypectomy的范围关系。
2. CFTR肠梗阻的surgical management，与consult surgery/surgeon for intervention不是自动同义。
3. COL1A1 physiotherapist与治疗服务的身份/来源关系；EDS直写转诊的句子在孕期，不能补成普通独立行动。

[三项原文、缓存及具体问题](../../out/structure-identify-deterministic-20261121/manual-3-semantics.json)。不调用AI、不自动改来源策略；NF1一般处理原则备注继续保留，不补跑。

临床范围、患者条件、风险、推荐性质和技术解释没有由本轮名称恢复变成确定结论；未运行上下文核查，Phase 2不宣称全面验收。

## 最小代码及离线验证

在原[句子准备模块](../../scripts/experiments/structure_identify_sentence_repair.py)增加`number_table_unit`，直接给已有解析单元编号，复用原句切分和完整行上下文；新增[本轮离线编排脚本](../../scripts/experiments/structure_identify_deterministic_repair.py)消费已审核清单及本地缓存，没有模型/API执行入口。没有改生产医学规则、原classify、提示词或核查器。

新增[两项必要测试](../../tests/test_structure_identify_deterministic_repair.py)：已有行动的同行仍能编号其他原文且保留列表/位置；真实数据离线恢复5/4和9项名称、不改原输入/账本对照，并保留15/13/3待审边界。

全量离线**1406通过**。跨日后GeneReviews索引触发原7天TTL，第一次测试的外连尝试被socket拦截，未发出API请求；失败日志保留在[tests-unpinned-date.log](../../out/structure-identify-deterministic-20261121/tests-unpinned-date.log)。只在测试进程用原ensure的today参数固定已验收数据日期2026-11-20重放，生产日期/TTL未改、缓存未刷新；阻断下载仅创建的空目录已恢复。外网仍禁止，仅允许测试本机服务器。[最终测试日志](../../out/structure-identify-deterministic-20261121/tests.log)。

旧答复、既有实验产物、runs、正式.cache、正式输出及全部baseline逐文件SHA不变。改前详细快照已存，本轮详细前后diff为**0**，对current185项既有变化逐条相同。

- [对current完整status_diff](../../out/structure-identify-deterministic-20261121/status-diff-full.txt)
- [本轮前后完整status_diff](../../out/structure-identify-deterministic-20261121/status-diff-since-before.txt)
- [覆盖、来源、ID/key及保护范围核验](../../out/structure-identify-deterministic-20261121/verification.json)

本轮$0、原累计仍$0.100842897。不修改或升级Baseline，不处理四个正式评测病例，不进入Phase 3。

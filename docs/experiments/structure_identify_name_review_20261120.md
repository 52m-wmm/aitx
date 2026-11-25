# Phase 2：共享名称及两项别名映射审核稿（$0）

本轮模型/外部API调用0，费用$0。NF1句子已按用户决定在新来源复核记录中保留为**一般处理原则备注**，不再补跑、不作为新增具体治疗；没有改写旧三票、医学规则、正式Ledger或baseline。[用户决定记录及原句](../../out/structure-identify-name-review-20261120/NF1-user-disposition.json)。

下面四项均为**建议，尚未应用**。本轮不修改词表aliases、名称判定代码、行动key或Accepted记录。

## 1. OI共享名称：建议对齐已有两个候选

原文（NBK1295，Treatment of Manifestations，列表项3）：

> Physical and occupational therapy should be initiated to increase bone stability, improve mobility, prevent contractures and head and spinal deformity, and improve aerobic fitness and muscle strength.

现有候选：本轮来源记录中的组合名`Physical and occupational therapy`；阶段1同章已有`physical therapy`和`occupational therapy`。同章另有连续原词：

> Physical therapy is one of the most significant therapeutic modalities for individuals with OI.

**建议映射：**组合来源分别关联`physical therapy`和`occupational therapy`两个已有候选。前者共享末尾名词therapy，后者在原句中连续出现。组合短语保留为来源分组，不作为第三个独立行动。physical therapy也有同章连续原词支持，不必让模型再生成非连续引文。

原句和另一段证据各保留原位置、条件与用途；不能将重建名称冒充本句逐字引文，也不能用另一段的有效票追认旧失败答复。**不建议自动把physical therapy映射成physiotherapist**：前者服务、后者提供者名称，尚非本次获批别名。

这项主要补共享证据的身份关联，不增加两个新的治疗概念；OI两个名称在现有候选中已存在，因此不能据此宣称解决了Accepted的physiotherapist缺口。

## 2. KMT2B共享名称：建议分为两个类别引用

原文（NBK493766，Treatment of Manifestations，首段）：

> A movement disorder specialist should be involved at an early stage to discuss pharmacologic and surgical treatment options.

现有候选/来源：

- 独立服务行动：`A movement disorder specialist should be involved at an early stage`。
- 类别组合：`pharmacologic and surgical treatment options`。
- 阶段1已有`surgical treatment`候选，同章另有粗体标签`Pharmacologic treatment of dystonia`，后者仍保持原先待审状态。

**建议映射：**类别组合拆为`pharmacologic treatment`和`surgical treatment`两个类别引用；surgical一项可指向现有同名候选。保留原组合引文，不将重建的pharmacologic treatment冒充本句连续原词。

不把两个类别当作两个新具体方案，不据此推断药物或DBS；不把泛称pharmacologic treatment直接合并为范围更窄的Pharmacologic treatment of dystonia。`at an early stage`继续随专科参与原句，不附给两个类别，更不改成患者资格。

## 3. pancreatic enzyme replacement：建议同源长短名称对齐

原文（NBK1250，Supportive Care，两张表治疗列的独立列表项）：

> Pancreatic enzyme replacement therapy

现有候选/身份：

| 名称 | 当前identity |
|---|---|
| Accepted短名：pancreatic enzyme replacement | term:pancreatic enzyme replacement |
| 原文和有效多数长名：Pancreatic enzyme replacement therapy | term:pancreatic enzyme replacement therapy |

两张表的来源都已定位，并各有对应有效多数记录（valid_vote_count=3）。现在待审是**名称身份没有对齐**，不是模型没抽到。

**建议映射：**在本章这些已核对来源的名称对照中，长名关联短名；展示和证据仍保留完整长名。不是全局删除therapy规则，不合并两个已有Accepted行动ID，不改key、不改状态。

## 4. contact precautions：建议核心名称对齐、保留括号细节

原文（NBK1250，Supportive Care，Infection行，两张表）：

> Use contact precautions (gown & gloves) for every encounter by every clinician.

现有候选/身份：

| 名称 | 当前identity |
|---|---|
| Accepted短名：contact precautions | term:contact precautions |
| 原文及有效多数名：Contact precautions (gown & gloves) | term:contact precautions (gown & gloves) |

两处来源均有对应有效多数记录（valid_vote_count=3）。**建议映射：**本次已核对来源中的带括号名称关联核心名contact precautions；gown & gloves以及for every encounter by every clinician原样保留为实施详情，不删成无条件陈述。

不是全局删括号规则，也不合并现有Accepted记录或更改医疗状态。两份原文位置分别保留，不能把同一次抽取当成两个独立确认。

## 为什么只建议来源名称对齐

上述两对长短名在现有行动词表中本来就各有独立条目，aliases为空，现有identity不同。直接给全局词表互加同名alias会涉及覆盖和跨来源合并，本轮没有这样做。

建议审批范围仅为**本次已核对来源的名称关联/验收对照**。不是合并账本行动、改医疗条件、迁移key或升级baseline的授权。

[四项完整建议、现有候选、原句XPath和缓存多数依据](../../out/structure-identify-name-review-20261120/mapping-proposals.json)。

## Phase 2剩余缺口汇总

| 类别 | 当前情况 | 边界 |
|---|---|---|
| NF1单句指认 | 用户已决定作为一般原则备注保留，停止补跑 | 不形成新增具体治疗，不改旧票 |
| 本次名称审核 | **4项建议待审核**：OI、KMT2B、两项别名 | 本轮0项应用 |
| 新增指认调用队列 | **0项已安排/需在本轮执行** | 不等于所有语义已验收 |
| 原35处来源缺口 | 原文35/35保留、31处表格关系恢复；XML真实丢文0 | 来源保留不等于条件、风险全部确定 |
| 43项名称 | 原文43/43；41严格同名多数＋2别名待审 | 若两项别名获批，可为41严格＋2映射＝43对齐，不能改称43项严格同名多数 |
| Accepted名称对照 | 228/264找到候选名，29待审、6设计排除、1既定AAC别名 | 29包含本次两个别名，不能再相加；若仅批准两个别名，预期待审29→27，未应用 |
| 未识别列名 | **13种表头组合**仍有待审记录 | 含不同路由，不等于13个治疗漏抽 |
| 条件、患者适用性、推荐及风险 | 原文已保留，但未运行新的上下文核查或收集其全部缓存缺口 | 无法给出新增付费核查请求数；不自动执行 |
| 技术/药代细节和共享标准名 | 仍保留未解决解释；既有核查器不计算技术参数或发现标准名 | 不借“已交核查器”宣称解决 |

29项名称待审是现有验收对照的口径，**不是29条已证实正文漏抽，也不是29个LLM补跑任务**。其中可能有已保留的来源行动尚未建立名称关联；除本次4项外，本轮没有进一步裁决这些名称。

[29项逐病例完整名单](../../out/structure-identify-name-review-20261120/accepted-name-pending.md)、[原始对照记录](../../out/structure-identify-name-review-20261120/accepted-name-pending.json)、[13种未知表头](../../out/structure-identify-name-review-20261120/unknown-headers.md)。

历史失败答复保持原样，结构挂接和名称建议不追认其有效性，不重新混算成功率。Phase 2尚未全量验收；本轮不进入Phase 3、不处理正式评测病例。

## 离线核验与状态

本轮仅新增审核数据和文档，没有改生产代码、医学规则、词表、正式Ledger或baseline。按冻结XML SHA、原XPath、现有词表身份和有效缓存原文核对；NF1备注决定单独记录，旧三票不改。

原任务累计仍$0.100842897，本轮$0，不因余额继续调用。改前详细快照已保存，前后详细status_diff为0，对current仍185项既有变化且逐条相同。

- [对current完整status_diff](../../out/structure-identify-name-review-20261120/status-diff-full.txt)
- [本轮前后完整status_diff](../../out/structure-identify-name-review-20261120/status-diff-since-before.txt)
- [旧答复、缓存、账本及baseline保护核验](../../out/structure-identify-name-review-20261120/verification.json)

四项建议先交用户审核，不自动应用映射或进行后续调用。

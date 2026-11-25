# 阶段2：段落指认设计与KMT2B扩大验证（2026-11-19）

> 历史设计参考：对应旧结构抽取实验已退役，本文不定义当前生产接口，也不恢复历史调用授权。与Step3后续适配有关的设计和未核实问题暂保留；当前入口见 [3a说明](step3a_contract.md)。

## 2026-11-20 全量获批队列已完成，阶段2待修复/验收

用户批准$0.20后，340题/1020次三票全部完成，费用$0.078656796，无截断/传输失败/缺usage/高峰调用。615按冻结协议有效、405格式错误，其中298仅顶层type元数据；副本免费规范化可913有效、仍107其他错误，未修改原判定。指定KMT2B/AGXT检查均通过，但整体未通过。

同时确认报价队列漏了部分备注列编号，至少43个Accepted名称涉及35个未编号表格单元格。已整理补题与type规范化清单，未追加模型请求或进入阶段3。后续不得通过任意上下文匹配放宽words本句校验来掩盖输入缺口。完整结论、逐例/Accepted清单与原始三票见全量报告（历史资料已清理）；下面是先前设计与报价/定向回归记录，不代表全量已验收。

## 历史授权记录：条件成对格式（2026-11-20回归通过并冻结）

用户批准仅重跑 AGXT 多治疗且有关联范围问题的句子及原缺 T 两票所在段落、KMT2B 抗胆碱药和 IEP/21 岁两段，共 9 题/12 句/27 次三票请求，新的合计上限 $0.02，仅非高峰。不是重跑 AGXT/KMT2B 全例。

每句输出 `{"actions":["T1"],"conditions":[{"T":"T1","words":"限定原词"}],"roles":["action","condition"]}`。每个 condition 只能有一个给定 T；words 仅忽略大小写做本句子串校验，由代码复制原始写法。缺 T、多个 T、原词不存在均为格式错误。各 `(T, words)` 成对计三票多数，不再把角色和所有 T 做笛卡尔积。新名称仍使用既有 `_new` 协议；未知不视为无条件适用。

本轮版本 `3a-identify-condition-pairs-v1`，冻结输入在 [plan.json](../out/structure-identify-pairs-20261119/plan.json)；27/27有效、零截断/格式错误，AGXT missense仅关联pyridoxine、KMT2B两项回归及独立来源检查全部通过。已写入[提示词冻结记录](step3a_identify_prompt.json)及[3a契约](step3a_contract.md)。AGXT urologist 段的原文 `consultation with a urologist` 显式提供为候选，避免要求模型给不存在的 T。

nedosiran 的 [来源分列](../out/structure-identify-pairs-20261119/nedosiran-source-pairs.json) 保留 GeneReviews `>30` 与现有 FDA 标签证据 `≥30`，不合并或改写边界、不改患者适用性，不为这项来源核对增加模型调用。生产 v5、上下文核查 low/16384 及原提取兜底不变。

本轮完整结果与15例报价（历史资料已清理）：已知$0.002283054，四次无usage传输失败预留$0.005228500，预算上界$0.007511554<$0.02。全量报价含256段及84个未被段落覆盖的待判单位，340题/1020次；按两例实测校准预计$0.13–0.15，建议硬上限$0.20。表格追加题尚未付费实测，网络无usage预留可能导致提前停止；全量尚未授权或执行。

## 本轮获批修订与结果

用户已审阅 KMT2B 并授权：只重跑受影响的 5 段（三票），通过后启动 AGXT 全部待判段落（三票），共用新的 $0.03 硬上限，仅非高峰。旧实验保留，不重跑其余 27 段，不再发 low 对照；下文旧版结果是历史记录。

新协议每句返回 `{"roles":["action","condition"],"T":["T0"]}`，允许多角色，condition 必须关联给定的 T；三票按角色—T 成对多数。治疗名标签提供为 T0。ABA 的实际粗体上下文为表现类标签，因此 T0 取正文明确出现的 `applied behavior analysis (ABA)`，不把表现误当治疗。transition 段另列原文 `IEP services`，检验至 21 岁限定关联该服务而非 transition plan。

AAC 原句确为 `Alternative means of communication (e.g., augmentative and alternative communication [AAC])`。旧输出实际尚未生成独立父类，现按获批 e.g. 规则登记父类及别名，不伪称旧版已覆盖。孕期四项、AFO/walkers 的设计性排除在对齐表登记；不改变账本适用性。

AGXT 源文的 nedosiran 肾功能界限是 **eGFR >30**，并非用户简写的 ≥30。保留原句，边界差异单列待审，不能静默改写。

冻结输入与执行状态：[本轮计划](../out/structure-identify-v2-20261119/plan.json)、[对齐登记](../out/structure-identify-v2-20261119/alignment-registration.md)。生产 v5 与上下文核查 low/16384 不变。

授权范围已完成：完整报告（历史资料已清理）。KMT2B 新 15/15 有效、五项修复检查通过；AGXT 178/180 有效、零截断，指定名称/原句覆盖，但两份缺 condition 所属 T，且多角色共用 T 列表会把局部限定挂到其他治疗（AGXT 总述句已出现）。7 句多目标条件关联单列待审，不判整体通过，不扩大到 15 例。最小后续方向是每角色独立列 T；本轮未修改冻结提示词、未追加请求。

已知费用 $0.010441770；一次无 usage 的 TLS 失败保留 $0.001225600，合计预算上界 $0.011667370 < $0.03，全部非高峰。全量 1369 离线通过，正式输出前后 diff 0，对 current 185 项既有差异未变。

旧单位抽取方案停止；不再使用逐单位复制引文/source_id的提问。指认默认候选为non-thinking，正式3a仍是已验收v5，所有实验仅写shadow产物。上下文核查保持`reasoning_effort=low, max_tokens=16384`，没有修改或调用该核查器来填补本实验的漏项。

## 历史接口

代码先过滤无正文的粗体/列表标题、固定来源套话及词典已经确定且没有条件线索的简单句。KMT2B原37段，过滤5段，留下32题、58句。[逐段过滤理由](../out/structure-identify-20261119/filtered.json)与[冻结的扩大验证输入](../out/structure-identify-validation-20261119/KMT2B/jobs.json)保留全部原文。

每题为一个段落，输入编号句子S1..Sn和词典/固定模板已找到的候选T1..Tm，附所属标签。模型只返回每句`action / condition / detail / none`及关联T编号；词典未列出的表面词用`_new`附句号与名称。推荐、描述、无效及患者适用性留给现有上下文核查，不在此题判定。原文由代码按S复制，不让模型复制引文或输出source_id。

请求参数是`thinking: {type: disabled}, max_tokens:1024`；保留的low对照使用`thinking:{type:enabled}, reasoning_effort:low, max_tokens:1024`。默认仅作用于指认实验，不改变全局模型或上下文核查配置。

按用户续跑修订：`_new`只忽略大小写和空白做子串匹配，再复制原文原始写法；不允许删词、改词或跨句拼接。原模型JSON保留，规范化输出另存。`action`既无T编号也无新词，标`needs_review`，不算格式错误。已返回的格式失败答案只离线重校验，不重发。

三票按角色及每个关联分别多数，少数票、未达多数、格式失败均保留，不默认通过；同一小节同身份合并，证据原句和条件作用域分开。主标签只有一个，因此混合行动/条件句的条件可能未被独立指认：本次confirmed diagnosis已出现这一限制。保留整句不等于条件已识别。

## 文档核实与单段实测

[官方API文档](https://api-docs.deepseek.com/api/create-chat-completion/)说明`thinking.type=disabled`或`reasoning_effort=none`可关闭思考，显式thinking参数优先。[官方价格](https://api-docs.deepseek.com/quick_start/pricing/)列明deepseek-flash对应V4.1-Flash-1017，两种模式使用同一Flash费率：非高峰每百万输入冷缓存$0.15、命中$0.003、输出$0.60。费用按返回usage计算。

先前同一段两次实测：non-thinking $0.00008310、low $0.00028005，两者均未截断，标签同为S1 action→T1、S2 condition→T1。low另外列出`Anticholinergics`，不能称所有输出完全等价。该段角色标签符合预先保存的参考；它不能代表全例质量。两份有效实测复用为扩大验证各模式的第一票。

## 扩大验证的实际结果

用户授权两例合计上限$0.05、仅非高峰；续跑改为仅non-thinking三票，已完成low保留参考，AGXT必须等用户审阅KMT2B。现已完成KMT2B 32题×3=96份non-thinking答案；low保留8份，不再补其余24份。

- non-thinking：无截断，86/96答案完整有效，10份格式/引用失败。1份_new删掉原句中间词，9份把`_new`放进T编号位置；本轮不擅自放宽协议。
- 58句中50句具备三份完整有效答案，49/50角色与关联全票一致，即98%；不能把另外8句算作一致。单句另有少数票，逐票明细可审阅。
- 2句形成多数needs_review；逐样本共7次标记、涉及3个源句位置，均未按格式错误处理。
- 合并清单31个名称候选、4条显式条件关联；这些不是31个临床推荐。Accepted 25个行动名称中18个对齐、7个未命名，原因逐项列出。
- IEP、504、DDA、DBS名称召回保留；抗胆碱药confirmed diagnosis原句随action保留，但没有独立condition关联，该must_check未通过。

[完整验证及清单](../out/structure-identify-validation-20261119/KMT2B/analysis.md)、[三票多数新表面词](../out/structure-identify-validation-20261119/KMT2B/new-names.json)、[所有逐票新词提案（含未通过格式者）](../out/structure-identify-validation-20261119/KMT2B/new-names-all-proposals.json)、[needs_review](../out/structure-identify-validation-20261119/KMT2B/needs-review.json)。

已知费用合计$0.00646368（含两份复用实测）。TLS握手失败和按用户续跑调整中断的在途请求均保留了预留：无usage预留合计$0.002468，预算计入上界$0.00893168，未超$0.05。不能把缺usage当0或把上界称为精确实付。先前已停止的2048-token单位实测$0.00188145属于旧方案，另记，不混入本轮上限。

AGXT未启动；不报15例全量价格，不自动扩大。剩余角色/关联与新词问题待用户看KMT2B结果后再决定。未改正式账本、基线或任何临床状态。

最新完整验证、续跑规则、费用及交付以扩大验证报告（历史资料已清理）为准。主流程96份non-thinking答复，已有8份low仅保留参考；不再补low，AGXT不自动启动。

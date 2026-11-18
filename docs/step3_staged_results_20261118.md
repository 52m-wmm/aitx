# 分阶段 Step 3 实验记录 v1.0 — 2026-11-18

## 当前结论

**尚不能给出 AGXT/KMT2B 成对稳定性结论：完整独立运行 0/4。** 两次 AGXT 尝试都在 3a 因固定外部响应夹具缺项停止，尚未到完整账本，自检/成对对比均不能计为通过。KMT2B 的独立两次执行尚未开始；此前独立批准的增量刷新已经完成并发布。

已停止所有付费执行，等待明确是否允许“仅 RxNav 药名归一化查询联网”的冻结边界；不是预算已耗尽。没有自动修改判定规则或 Accepted Baseline，也没有选择某次有利结果。

## 1. CFTR 的 $0 HPO 扰动实验

见 `docs/cftr_hpo_sensitivity_20261118.md`。正常输入缓存回放与正式账本原有状态 Diff 为0。泛化HPO输入下，可比较的非上下文条件无变化；132组3a上下文核查缺缓存，3c未完成。原始Diff的51个not_tested标记与3项未生成的超说明书行动都属于未测，不是临床状态变化。CFTR两次真实Step3未执行。

带详细字段的工具输出在 `out/status_diff/staged-step3-20261118/cftr-normal-detailed/` 与 `cftr-generalized-detailed/`；JSON包含classification、条件、引用和核查投票。临时未测账本没有发布到正式输出。

## 2. KMT2B 增量刷新及固定输入

正式账本 `out/step3/PRAC-KMT2B.json` 已发布，来源为 `runs/step3-stability-20261118/kmt2b-publish/` 的完整缓存复核；Ledger自检无fail、KMT2B专属3a验收5/5、freshness为true。Step1/2原文件未改。完整输入、来源、代码指纹在独立实验 manifest 中固定，并保留刷新前后两份账本。

刷新前后状态工具输出：2项DBS not_applicable→conditional，4项孕期独立行动删除，4项药物reason文字改变且状态不变。均为此前已批准的R15/孕期处理与分歧文字修正，不是本次稳定性采样的新临床规则。没有新增不适用。

- `out/status_diff/staged-step3-20261118/kmt2b-published-since-before/`：相对刷新前的完整Diff。
- `out/status_diff/staged-step3-20261118/kmt2b-published-current/`：相对Accepted current的15例完整Diff；其中既有COL1A1待审及RETEST缺基线仍单列。
- `runs/step3-stability-20261118/kmt2b-publish/3a_acceptance.json`：5项专属验收。

## 3. 独立运行的两次中断及费用

| 尝试 | 有usage响应数 | 增量已知费用 | 停止原因 |
| --- | --- | --- | --- |
| 初始固定夹具 | 13 | $0.039876528 | RxNav缺少`name=Nedosiran&search=2`查询键；已有nedosiran/NEDOSIRAN响应均为2675287。 |
| 大小写别名夹具v2 | 12 | $0.043761663 | 新行动名`vitamin C intake that exceeds the recommended allowance`触发未预存查询。 |
| 合计 | **25** | **$0.083638191** | 完整运行0/4，不具备成对比较前提。 |

实际调用中两次出现16384输出截断，均按原策略只重试一次到32768，额外调用与费用均保留。25个响应均有usage、模型均返回deepseek-flash，高峰0次；这些是25个实际请求，不是25次完整Step3。

第一次只做了输入夹具处理：NLM[官方文档](https://lhncbc.nlm.nih.gov/RxNav/APIs/api-RxNorm.findRxcuiByString.html)明确查询参数不区分大小写；依据已有且一致的RxNav响应补充1043个大小写别名，返回正文与原访问时间不变，没有获取新临床资料或改变代码。v2固定5234份响应。原13次失败尝试完整保留，并把日志/费用带入同一个$0.50总账，未重置预算。

第二个缺口不适用大小写等价。停止后只读核实原查询，RxNav返回`{"idGroup":{}}`，原始记录在 `runs/step3-staged-050-v2-20261118/missing_lookup_audit.json`，**没有写入测量用冻结夹具**。不能擅自把整句归一化成vitamin C，也不能把外部输入缺失当成临床不适用。它显示新LLM行动名会改变下游实体归一化查询；严格固定预存URL集合时可能无法覆盖这些新查询。

因此，本轮行动集合、classification、条件、Evidence IDs、核查投票的成对变化数均为**未测**，不能报0变化或稳定。代码、Prompt、模型参数未改；官方模型文档对应V4.1-Flash-1017，服务端只返回deepseek-flash别名，无法独立验证权重版本。

## 4. $0 预检与待澄清边界

`runs/step3-fixture-preflight-20261118/` 仅用于零费用预检：复用已有与失败尝试已产生的响应，核实后续外部查询，不作为独立真实运行。预检记录107份HTTP响应，但遇到新的引文修复LLM请求缺缓存，3a/3c未测，不能声称已证明夹具完整。

待用户决定：

- 保持所有外部响应预存冻结，继续只做$0夹具工作，不恢复真实调用；或
- 仅允许RxNav药名归一化新查询只读联网并存档/记录数据库版本，其他文献、试验、说明书仍冻结；这放宽原始冻结边界，须明确同意后才可执行。剩余预算仍为$0.416361809，不能借其他额度或自动增加。

## 5. 独立预算与余额

| 项目 | 已知费用 | 实付未知的保守预留 | 预算记账 / 上限 |
| --- | --- | --- | --- |
| 评测Step2（已完成） | $0.068315367 | $0 | $0.068315367 / $0.10 |
| KMT2B增量刷新（已完成） | $0.007798854 | $0.012302650（一次TLS中断） | $0.020101504 / $0.06 |
| 本轮独立Step3（未完成） | $0.083638191 | $0 | $0.083638191 / $0.50 |

执行前用[DeepSeek余额接口](https://api-docs.deepseek.com/api/get-user-balance/)核实，返回账户可用、19.44 CNY；未把人民币余额直接当美元余额。余额原始返回见 `runs/step3-stability-20261118/balance_before_staged.json`。三项分别记账，原$1.20整体授权已被最新分阶段决定替代，CFTR真实执行未启动。

## 6. 工具和版本完整性

status_diff.py新增可选`--detailed`，在双方快照均有详细字段时比较classification、条件、引用及核查投票；旧Accepted快照缺这些字段时明确unavailable，不补成空数组或0变化。重复的同一次核查摘要去重，缺票记未测，不计为分歧。原默认状态/原因/ID对比仍保留，未更改历史基线格式。

工具最终离线1251项通过；未改任何aitx生产代码。两个实验 manifest 的冻结代码/输入哈希核对一致；原69个正式文件仅KMT2B的获批刷新有变化，Step2/Step4及Accepted current保持原哈希，评测病例没有Step3输出。

原始失败尝试、请求、费用、固定输入：`runs/step3-staged-050-20261118/` 与 `runs/step3-staged-050-v2-20261118/`。两目录的`stability_summary.json`都明确成对比较不可用，不能作为已通过基线。

# 四个评测病例 Step 2 稳定性补测 — 2026-11-18

**20/20 轮完成，诊断与最终 HPO 稳定性通过。** 每例固定 5 次独立真实执行、每次原三票；没有挑选、追加或丢弃任何轮次，未修改诊断规则、Prompt、模型参数或正式输出。仅观察评测病例稳定性，没有用它们调参，也没有执行其 Step 3。

| 病例 | 首选 | 首选一致性 | 状态（五次均相同） | 分支 / 疾病候选集合变化 | 最终 HPO 变化 |
| --- | --- | --- | --- | --- | --- |
| AITX-40001 | Developmental and epileptic encephalopathy 76（MONDO:0032768） | 5/5 | resolved | 0 | 0 |
| **AITX-40002** | **Spinocerebellar ataxia 29（MONDO:0007298）** | **5/5** | **ambiguous** | **0** | **0** |
| **AITX-40003** | **Hereditary sensory and autonomic neuropathy type 1（MONDO:0018213）** | **5/5** | **ambiguous** | **0** | **0** |
| AITX-40004 | Infantile hypotonia-oculomotor anomalies-hyperkinetic movements-developmental delay syndrome（MONDO:0033864） | 5/5 | resolved | 0 | 0 |

每轮内部三票的诊断 ID / 状态也全部一致，合计 60 份诊断无分歧。40002 始终保留 MONDO:0008795、MONDO:0011694 两个备选；40003 始终保留 MONDO:0008086、MONDO:0017593 两个备选。相对固定历史参照，Top 1 / 分支 / 状态变化同样为零。ambiguous 表示仍保留诊断歧义；首选稳定不等于已确诊。

## 分层差异及原因

每例 5 轮共 10 对比较，四例合计 40 对，完整字段 Diff 全部保留。

- **最终 HPO（ID + 状态）**：40 对全部相同，疾病候选集合、最终分支与诊断状态同样全部相同。
- **初始症状原句跨度/状态**：40001/40002/40003/40004 分别有 9/10、10/10、10/10、4/10 对不同，主要为截取跨度和拆分粒度、个别漏提或描述/同义词变化。这是原始抽取层波动，不能当成最终 HPO 或诊断变化。
- **内部三票 HPO**：40003 有 9/10 对存在差异，例如个别票在 HP:0002936 / HP:0003474 间变化，体重项也有漏提或层级差异；既有多数票和层级合并后最终集合保持一致。其他三例的三票 HPO 集合在各轮之间一致。
- **模型选词**：40002/40003 原始选词回答分别有 9/10、10/10 对不同，但部分输入候选列表/特征编号随初始抽取变化，不能直接算成固定输入下的选词错误。按完全相同请求键分组，40001/40002/40004 分别有 3、3、5 组重复选词输入，组内选择分歧均为 0；40003 没有可重复比较的完全相同选词输入组，无法单独估计其纯选词随机性。
- **病人事实**：40002 的 6/10 对有原文跨度差异，variant_origin.quote 从 `de novo` 变为 `de novo variant`；结构化值始终为 de_novo，年龄、性别等含义未变。其余三例事实记录无变化。

所有原始回答和差异均保留，没有为了消除差异重跑或改规则。`summary.json` 中 `hpo_changed` 比较完整记录（含措辞）；最终 HPO 语义统计以 `difference_metrics.json` 的 `hpo_semantic_changed` 为准。

## 费用、版本与隔离

**119 次真实请求 = 60 次初始抽取 + 59 次选词**，无响应缓存复用、无重试、高峰调用 0、usage 缺失 0。此前预计 115 次，实际选词多 4 次，仍在事前 60–120 次正常范围内；没有新增完整执行轮次。

API 返回用量计费总计 **$0.068315367 / $0.10**，剩余 $0.031684633。缓存输入 token 47,089、未命中输入 25,034、输出 107,365（已含推理 88,990，不重复加算）。逐轮及逐请求费用见下方产物；未把本次费用混入旧练习病例 $0.32 试验或 KMT2B 额度。

与练习病例实验相同：原 Step 2 生产代码、Prompt `step2-extract-v5`、temperature=0、max_tokens=16384 和三票策略；按病例原数据清单锁定数据库/HPO 与 36 份 HTTP 响应，逐轮独立空响应缓存并显式绕过读取。nohup+caffeinate、仅非高峰、串行，逐请求最大费用预留；实验累计上限不跨日重置。

接口与所有响应模型均为官方 `deepseek-flash`；报价时官方文档对应 DeepSeek-V4.1-Flash-1017，但服务端仅披露别名，未独立验证权重版本。生产代码/输入指纹全部一致，69 个正式 Step 2/3/4 及行动 current 文件哈希不变，未覆盖四例正式 Step 2 输出，未修改或升级既有基线。离线 **1248 项通过**。

## 完整产物

- `out/acceptance/step2_eval_stability_20261118.json`：汇总、每轮首选/分支/三票、HPO、费用。
- `runs/step2-eval-stability-20261118/executions/<case>/<1..5>/`：每次完整结果、抽取、原始回答、完整 Prompt/候选、三票、费用、对参照的完整 Diff。
- 同目录的 `complete_comparisons.json`：40 对完整字段/原始回答/选词/三票 Diff；`votes_and_reasons.json`、`difference_metrics.json`、`per_round_costs.json` 分层统计。
- `fixed_inputs.json`、`fixed_http.json`、`proposal.json`、`executed_script.py`、`artifacts_sha256.json`：固定输入与执行版本指纹。

本结论仅为四个评测病例在固定来源下的稳定性观察，不评判诊断准确率。按用户最新安排，先完成 Step 2；已批准的六次完整 Step 3（独立上限 $1.20）**尚未启动，等待后续安排**，旧自动任务仍暂停。

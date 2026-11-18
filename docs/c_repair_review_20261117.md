# 已批准基线升级与 C 修复复核（2026-11-17）

本轮真实 DeepSeek 请求 0 次，费用 $0。正式基线只升级用户已经批准的 A/B/D/E，C 修复结果不自动升级；4 个 RETEST 首个基线仍等本轮报告审核通过。

## 1. 先升级已批准项目

实际通过 `scripts/promote_baseline.py` 升级 151 个 diff 项：A 5、B 5、D 11、E 后续步骤新增 124、hypertonic saline 键规范化 2、over_cap 删除 4。current 从 409 行成为 529 行，批准人与逐项理由追加在 `baselines/approvals.md`；历史只读文件没有改动。

升级先于临床修复：升级提交 `58dd09f`，C 与第四轮呈现实现 `3661184`，DBS 显示回归补正 `e1b7f56`。没有将 C、61 项证据细节、另外两项 COL1A1 小关节 HPO 状态变化、其他待审新增/删除或 RETEST 缺基线项目混入批准。

## 2. KMT2B 的 C 六项修复

以下为当前代码直接生成的 **3a 专项结果**，不是已经完成整例重跑。分支均为 MONDO:0015004。

| Action | 新 current 基线 | 修前实际账本 | 3a 修复结果 | 原因 |
| --- | --- | --- | --- | --- |
| GPi-DBS | applicable | not_applicable | conditional | R15 describes_use 只产生 unknown；显示 `source describes use; no explicit recommendation`。 |
| subthalamic nucleus DBS | applicable | not_applicable | conditional | 同上；病人事实未明确不符，不能用来源措辞强弱排除。 |
| Deep brain stimulation (DBS) | conditional | not_applicable | 不再独立生成 | 本条只有 Pregnancy Management 来源；普通段落的 GPi/subthalamic 仍独立显示。 |
| clonazepam | conditional | not_applicable | 不再独立生成 | 仅孕期来源，不能独立产生行动、条件或缺失信息。 |
| levodopa/carbidopa | conditional | not_applicable | 不再独立生成 | 同上；普通 levodopa 项仍保留。 |
| trihexyphenidyl | conditional | not_applicable | 不再独立生成 | 同上；普通段落的 trihexiphenidyl 拼写项仍保留，不擅自合并不同键。 |

两种 DBS 原本因 `narrower_than` 指向被移除的孕期总类而隐藏，现仅在总类实际存在时才隐藏子项。新增验收明确检查 conditional、未知理由和 reported=true；分支用实际诊断 dystonia 28 匹配，不能把基因名当作实际诊断文字。3a 专项账本自检及 KMT2B 五项验收 5/5 通过，完整文件见 `runs/baseline-approved-20261117/KMT2B-3a-only.json`。

KMT2B 苯二氮䓬类、trihexiphenidyl、tetrabenazine、levodopa 四项状态仍为 conditional；reason、核查说明改为 `check votes disagreed; unknown`，不再解释成病人程度未达到。ANO10 riluzole/TMS 保留原判定，只与这四项一起记录在稳定性观察集中，没有新增病例判定规则。

## 3. 两个不能假报完成的依赖

### KMT2B 3c：缺缓存，完整账本没有覆盖

孕期独立四项从 Tier 1 消失后，3c 的“已确立药物”清单改变，PubMed 候选优先顺序改变。新选中的 PMID 35418819、37168666、31388109 没有相同请求缓存；旧两篇抽取仍命中。第一篇新请求在预算检查前端退出码 4 停止，未发出真实请求，原 KMT2B 正式账本保持原字节。

只读盘点确认至少缺 3 次文章抽取。按项目现有非高峰费率、每次 max_tokens=16384 和请求输入上限估算，这三次最大费用预留合计约 $0.033746；新药后续核查次数必须等抽取后才能知道，这个数字不是整例重跑报价。用户本轮预算仍是 $0，因此不调用模型、不伪造或重新标记缓存，不把 3a 通过说成整例通过。

### COL1A1 physiotherapist：与“只改文字不改状态”冲突，候选已隔离

移除孕期段落的判定作用后，两分支 MONDO:0007522、MONDO:0030854 的候选状态均为 applicable → conditional。普通物理治疗段落的现有缓存 subject 三票为 no、recommendation 三票为 not_stated；旧 applicable 是因为合并的孕期段落没有额外条件，覆盖了普通段落的 source-scope unknown。不是病人信息改变，也不是本次新模型调用。

这不符合用户明确的“physiotherapist 只改 reason、不改状态”。候选完整文件隔离在 `runs/baseline-approved-20261117/COL1A1-unapproved-candidate.json`；正式账本已从改前备份逐字恢复。未将 unknown 改为满足以凑回 applicable，未添加 COL1A1 特例。已请求用户裁决保留 applicable 并暂缓此例刷新，或批准两分支 conditional；未收到批准前不发布该候选、不升级基线。

## 4. 免费核查与证据 ID

- 两项试验当前均 RECRUITING，但 NCT01822834 是 Non-CF/NTM 且明确排除 CF，NCT07513051 是新生儿呼吸窘迫、CF-CPAP 指 constant flow CPAP；均不是该 CFTR 病例的召回缺口，不改检索。注册页与原始 API 响应见 `docs/trial_recall_audit_20261117.md`。
- 61 项 Evidence ID 差异不是算法迁移：18 项仅增加证据，43 项涉及原文/声明/证据集合变化；旧 ID 都能用现行算法重算一致。能按同源同句配对的 11 个唯一旧→新 ID 都有身份字段变化（适用分支），其余不能伪造一对一映射。因此未按“仅算法迁移”批量批准。详表见 `docs/evidence_id_audit_20261117.md` 与运行目录中的 `evidence_id_audit.json`。
- ID 算法和身份输入冻结；黄金向量覆盖 sourced/reasoning/negative，同来源原文及相同身份上下文在不同抓取时间、producer、retrieved_by 下保持同 ID。没有为本轮重跑改 ID 生成方式。

## 5. 报告契约与交付范围

报告遵循 `docs/step4_contract.md` v2.0：来源顺序 Ranking/Tier 1 Summary、正文与 Summary 一致、实际显示行动才进入缺失信息/安全核对、脚注 `[n]`、可读枚举、重复 Note/NCT 清理已实现。AGXT 与 ANO10 已重新生成并通过格式及 Step 5。KMT2B 完整报告保留旧版本，不能宣称已交付第四轮新报告；3a 修复先以专项账本和 diff 供审核。

原 DMD 延期继续有效：**DMD 因性别推断改动而过期，待下次影响 DMD 的改动时一并重跑**。3.0 完整脚本会重建该病例并需要未缓存核查，本轮不启动；评测病例只验 Step 1/2，不运行 Step 3 及之后。所有新尝试只走缓存与零预算；长任务用 nohup+caffeinate。缓存重放未传会在启动即拦住缓存的 CLI `--offpeak-only`，真实请求前的高峰保护保留。

## 6. 最终可运行范围与 diff

- `.venv/bin/python -m pytest -q`：**1238/1238**。14 例完整缓存尝试成功，COL1A1 隔离恢复后正式新鲜账本为 **13/15**；KMT2B 正式文件原字节未改，另有 3a 专项 5/5 通过。所有本轮保留正式账本和隔离候选的自检均无 fail。
- Step 1/2 与评测 `--eval` 的 Step 1/2 PASS；3b **8/8**、3c **7/7**、3e **5/5**；正式 3a **25/32、FAIL**（KMT2B 5、COL1A1 2 项过期未计分），3d **2/8、FAIL**（DMD 2、KMT2B 1、COL1A1 3 项过期未计分）；3.0 deferred。支持核查仍是假拦 **3/17**、假放 0，没有新增规则。
- AGXT 报告 **58,773 bytes**、ANO10 **17,692 bytes**，两份格式与 Step 5 PASS。KMT2B 完整报告未刷新；不能将现存旧报告当成修复后版本。`submission.json` 只包含本轮实际生成的这两例。
- 15 例 **186** 项试验的 Known exclusions 与改前相同，新增 **0**；隔离的 COL1A1 候选也无新增。候选相较改前新增 not_applicable **0**。
- 默认 current 对正式文件的 CLI 工具输出：`out/status_diff/c-repair-20261117/canonical/`，含状态变化 8、细节变化 58、新增 106、删除 14、缺历史基线 157。KMT2B 与 COL1A1 原账本被保留，故这里仍包含尚未发布修复的历史状态；不是已完成修复的最终临床账本。
- C 修复审阅输出：`out/status_diff/c-repair-20261117/review/`，用同一工具函数生成，明确加入 **KMT2B 3a 专项**与**隔离的 COL1A1 候选**。对 current：状态变化 6（KMT2B DBS 2、待裁决 physiotherapist 2、历史待审小关节 HPO 2）、细节变化 61、新增 106、删除 22、RETEST 缺历史基线 157。这个混合范围只用于审阅，**不是整例新鲜账本，也不是可直接升级的候选基线**。
- 对改前实际快照的补充输出：`out/status_diff/c-repair-20261117/since-before/`，20 项状态变化、20 个孕期独立项删除、5 项细节变化。20 项状态变化为 KMT2B 2、RETEST-EIF2B1 corticosteroids 的 3 分支、RETEST-PFN1 13 项（均 R15 来源措辞放宽），以及未批准的 physiotherapist 2。5 项细节为 KMT2B 4 项仅改 reason，另 CFTR modulator therapy 移除孕期条件引用的 Evidence ID `8ce6ab5c0c7d`，状态不变、同名行动孕期原文仍保留为附注。全部逐条解释见 `review/analysis.md`，没有把 reason 本身当作批准。
- 完整验收汇总：`out/acceptance/c_repair_review_20261117.json`。current 与历史 SHA、DMD 原文件 SHA 已核对，未运行评测 Step 3 及以后；全部尝试合计 **真实 DeepSeek 请求 0 次，费用 $0**。尚待用户裁决 physiotherapist 联动及后续 C diff，不以本记录自行批准任何变化。

## 7. 用户批准 physiotherapist 更正后的继续运行（2026-11-17，覆盖上节该例的等待状态）

用户明确批准两个分支 applicable → conditional，并撤销此前此例“只改文字不改状态”的要求：旧 applicable 依赖孕期段落，对本病人无效；以普通来源的核查结果为准。

- 正式 COL1A1 账本已完成缓存重跑、发布且新鲜。MONDO:0007522（经典型 EDS）、MONDO:0030854（OI/EDS 联合型）的 reason 分别指明 **GeneReviews NBK1295 / Management / Treatment of Manifestations 对该诊断分支的适用范围尚未确认**，显示 `source-scope check unknown`。普通来源未记录额外的年龄、表现程度等病人条件，未补写成“不满足”的临床阈值；孕期原文仅保留同名附注。
- 使用 `promote_baseline.py` 仅升级这两行，差异字段只有 status/reason，Evidence ID 不变；current SHA 从 `eecc4996…` 变为 `43f31989…`，仍 529 行。`baselines/approvals.md` 已追加日期、批准人、提交号 `26a54c5`、两个变化及撤销旧要求的原因。基线升级提交 `79e93d6`。其他 C / 61 项证据细节 / RETEST 首个基线未获本次批准，未纳入。
- 离线 **1240/1240**；新增正反测试直接经过普通/孕期混合来源的真实 3a 判定路径，覆盖两个诊断分支的 unknown 来源理由，以及普通来源已确认时仍 applicable。没有添加 COL1A1 病例特例、改提示词、改 ID 生成方式或调用模型。
- 14 例完整缓存重跑均成功，正式新鲜账本 **14/15**；KMT2B 原正式账本保留，3a 只读专项仍 **5/5**。本次相较改前正式快照仅有 **physiotherapist 两个已批准状态变化**和四个纯孕期独立项移除（tranexamic acid、oxytocin、cesarean section、episiotomy，遵循此前批准的通用孕期规则），没有其他状态或证据 ID 变化。
- Step 1/2、评测 Step 1/2、3b **8/8**、3c **7/7**、3e **5/5** PASS；正式 3a **27/32、FAIL**（仅 KMT2B 5 项过期未计分），3d **5/8、FAIL**（DMD 2、KMT2B 1 项过期未计分），3.0 继续延期。不是全套通过。15 例 **186** 项试验 Known exclusions 完全一致、新增 **0**；新增 not_applicable **0**。
- AGXT / ANO10 报告已再次生成，大小仍 58,773 / 17,692 bytes，格式及 Step 5 PASS。KMT2B 完整 3c 仍缺三篇文章缓存，没有新调用授权，不重写其原账本或生成假称新鲜的完整报告。DMD 原延期决定继续有效，原文件逐字未动；评测病例未运行 Step 3 及之后。
- 对新 current 的正式工具输出 `out/status_diff/col1a1-approved-20261117/canonical/`；对本次改前实际结果的补充输出 `since-before/`。KMT2B 只读 3a 的 C 审阅输出在 `review/`，不再包含隔离 COL1A1 候选：对 current 的直接状态变化为 4（KMT2B 两种 DBS、历史待审 small-joint HPO 两项），其他差异逐项保留。审阅快照仍不是整例新鲜 KMT2B 账本或可直接升级的候选。
- 最新验收汇总 `out/acceptance/col1a1_approved_20261117.json`，运行及升级批准文件在 `runs/col1a1-approved-20261117/`。此次全部尝试 **真实 DeepSeek 请求 0 次，费用 $0**；cache-only、零预算、请求前非高峰保护始终有效，长任务 nohup+caffeinate。缓存未传启动即拦缓存的 CLI `--offpeak-only`。历史基线与其他未批准项目保持原样。

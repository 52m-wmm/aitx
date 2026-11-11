# 项目背景（给 Claude Code 的交接说明）

## 比赛

SAIL AI-Tx Challenge 最终赛：Actionability Report Generation。
官网 https://aitxchallenge.org/ ，提交页 https://aitxchallenge.org/models/ ，教程 https://aitxchallenge.org/tutorial/

- 输入：虚拟患者 JSON（基因变异列表 + 临床描述），见 `data/cases/aitx_final_patients.json`（4 个评测病例 AITX-40001 至 40004）
- 输出：每个病例一份 markdown 治疗可行性报告，组成一个 JSON 数组 `[{id, report_markdown}]` 上传
- 报告必须按顺序包含官方模板的全部章节：Summary；Tier 1（Existing Targeted Therapies / Supportive Management / Contraindications & Precautions）；Tier 2（Clinical Trial Eligibility / Off-label or Expanded-Access Therapies）；Tier 3（Bespoke Therapies / Drug Repurposing / Outcome Measures & Ranking）
- 硬规则：每条论断都要有可验证来源或推理；缺信息时写条件语句；同一行动不跨章节重复
- 评分：专家组人工评审，五个维度：事实准确性、完整性、证据与论证、优先级与校准、临床实用性。**写错比不写更糟**
- 截止 2026-12-01；报告必须由系统生成，**不能人工编辑**

## 用词约定（避免混淆）

- **参赛组**：Tier 1 ≤32B / Tier 2 ≤500B / Tier 3 不限（按模型总参数，开源权重）
- **证据层级**：报告里的已确立 / 新兴 / 假设性三层，每份报告三层都要写

## 已定决策

- 模型接口统一（`aitx/llm.py`，OpenAI 兼容，换模型只改环境变量）
- 开发期用 DeepSeek-V4.1-Flash-1017（官方 API 名 `deepseek-flash`，763B，属于参赛组 Tier 3）
- 对照：DeepSeek-V4-Flash-0423（284B，Tier 2，第三方平台调用）；第 4 周按同一评分标准对比后决定报哪个组
- 每次 LLM 调用记录服务端实际返回的模型名，防止别名被悄悄切换；跨接口复用缓存要求服务端模型名**完全一致**，并记录服务商
- 当天 LLM 费用上限 `AITX_LLM_BUDGET_USD`（默认 0.3 美元），每次调用前检查，超了就停下并保留已完成部分（退出码 4）
- **花钱规矩（2026-11-11，剩余预算约 \$2）**：每日上限恢复 \$0.3，不再临时提高；**任何 LLM 运行预计超过 \$0.1，先报价（调用次数 × 实测单价），等用户确认再跑**。修复阶段中间只跑离线测试，全部修复写完后练习病例全量重跑、验收一次，跑前报价。
- 优先用实时 API 获取数据，引用必须能解析到具体记录（URL / accession）

## 改动审批规则（2026-11-05）

- **只会把判定结果放宽成"有条件"的改动**（如把某条要求改判为"未知"），可以先做后报。
- **可能产生新的"不适用"（或把未知变成确定的满足 / 不满足）的改动**，先报给用户确认，再改。
- 无论哪种，都要补离线测试和反向验证，并在契约里记下原因。

## 开发方式

按节点逐步构建，**每个节点有契约文档（docs/）、离线测试（tests/）和联网验收脚本（scripts/acceptance_*.py），验收通过才进入下一步。**

**新章节首次接入流水线，先用 1 个病例小规模试跑**（2026-11-06 定）：确认账本能完整写出（`out/step3/<病例>.json` 真的落盘）、`checks` 里没有 fail，再跑其余病例。
起因：3d 首次接入时，新行动行缺 `status_by_branch`，账本在每个病例的最后一步抛 `KeyError`，12 个病例的 LLM 调用全部白花（约 \$0.19），一条输出都没写出来。
同理适用于：改动账本结构、新增校验、换提示词版本。小规模试跑用缓存（`AITX_LLM_CACHE_ONLY=1`）能跑通的部分先跑，必须联网的那一步再放非高峰。

| 步骤 | 内容 | 状态 |
| --- | --- | --- |
| 1 | 变异解析（确定性，无 LLM） | ✅ step1.1 已验收（2026-11-03，tag `step1.1-accepted`）：自检 6 独立重新翻译，16 个变异全部一致、反向验证全 fail；输出 schema v1.2 另含外显子布局和 AlphaFold 结构事实（pLDDT、RSA、8 Å 邻居） |
| 2 | 疾病归一化（基因 → OMIM / GenCC / GeneReviews） | ✅ 已验收（2026-10-28，tag `step2-accepted`）：`--fresh-llm` 硬性项全过；离线测试 135 个全过；症状提取测试集 32 条精确率/召回率 1.0（集合偏简单）；剩余问题见契约“已知局限” |
| 2.5 | 审查用查看页面 | ✅ 本地 Web 应用 `scripts/viewer_app.py`（FastAPI，127.0.0.1:8765，实时刷新、页面上重跑、运行记录）+ 静态导出 `scripts/build_viewer.py`；前端二期（Step 1 平面三图、3D 结构）完成 |
| 2.1 | Step 2 局限改进 | ✅ 已验收（2026-11-03，tag `step2.1-accepted`）：难题测试集、缺失类术语否定规则（修复 CBAVD）、起病年龄由代码映射到 HPO 起病术语；语义检索暂缓（剩余漏提不是检索问题）。详见 Step 2 契约 v2.5 |
| 3.0 | 证据账本与公共基础 | ✅ 已验收（2026-11-03，tag `step3.0-accepted`）：联网验收硬性项全过；规则 16 基因起草、独立支持度核查。规则现状（2026-11-06 审阅后，审阅表 `docs/rules_review_2026-11-05.md`）：共 15 条，**4 条已加载、11 条已否决、0 条待审**。COL1A1-1/2/3/4 收窄条件后重跑支持度核查仍卡在"结论"与"适用范围"，COL1A1-6 是"often lead to"，2026-11-06 一并否决："报告过 / 常常"不足以支撑"指向某个病"，涉及外显子丢失与剪接的又依赖 Step 1 不做的剪接预测；不新增提示型规则。契约 `docs/step3_0_contract.md` |
| 3a | 已确立层（Existing Targeted / Supportive / Contraindications） | ✅ 已验收（2026-11-04，tag `step3a-accepted`）；补充修复（提示词 `3a-v5`：表格行与段首限定作条件、治疗类转介、漏抽补抽、放宽从句、按变量合并缺失信息等）✅ 已验收（2026-11-05，tag `step3a.1-accepted`）：6 个练习病例 20/20 核实期望成立。规则变更见 3a 契约文末 |
| 3b | 临床试验 | ✅ 已验收（2026-11-05，tag `step3b-accepted`）：5 个练习病例 8/8 核实期望成立；逐条标准映射（LLM 映射、代码核验与比较）、病人事实模块、eGFR 公式（与 NKF 计算器核对）。契约 `docs/step3b_contract.md` |
| 3c | 老药新用 / 扩展使用（Off-label & Expanded Access） | ✅ 已验收（2026-11-06，tag `step3c-accepted`）：5 个练习病例 7/7 核实期望成立、全部新鲜输出、账本校验全过。契约 `docs/step3c_contract.md`（规则变更见文末 1–15 条） |
| 3d | 定制疗法（Bespoke Therapies） | ✅ 已验收（2026-11-08，tag `step3d-accepted`）：12 个练习病例 8/8 核实期望成立、全部新鲜输出。48 条判定中 12 条"无法评估"（25%）：PAM 5、结构域 3、天然跳跃证据 3、上调靶点 1——全是审阅决定暂缓接入的数据源，**没有一条因机制取不到**（GeneReviews 供得上）。契约 `docs/step3d_contract.md` |
| 3e | 药物重定位（Drug Repurposing） | ✅ 已验收（2026-11-08，tag `step3e-accepted`）：5/5 核实期望成立。12 个练习病例里只有 GRIN2B 产出候选（62 条机制记录排除 56 条，全因方向相反；保留 NEBOGLAMINE / RAPASTINEL / APIMOSTINEL，均标注"对本亚基选择性未知"）；DMD 的外显子跳跃 ASO 按药物类型转交 3d；其余基因在 Open Targets 无药物记录，整节留"检索无结果"负面证据。契约 `docs/step3e_contract.md` |
| 盲测 | 在未调过参的病例上量写错 / 漏写 / 有条件率 | **批次 20261108 已跑完（2026-11-11），进入修复阶段**：修复计划 `docs/post_blind_fix_plan.md`（审阅通过后开工）；结果与事故记录 `docs/blind_test_results.md`（B 组前 4 批因病例文件字段名写错、在无描述条件下运行，已修工具并全部重跑）。方案 `docs/blind_test_plan.md`（v0.2，2026-11-08）；机械召回评估方案 `docs/blind_recall_plan.md`（v1.0 定稿，2026-11-10，B 组跑完后统一计算）：A 组 2 个（Phase 1 Validator）+ B 组 10 个（5 个有 GeneReviews 专章、5 个只有 GenCC Definitive 评级，后者的临床描述由代码按 HPO 表型合成并标注）；抽样规则写死可复现，抽到的基因先过目；机器先判六项可机判的检查，其余列给审阅人；**盲测期间冻结代码**；写错率偏高的处理顺序已定（先通用修复 → 换新一批验证 → 3a 必须修好或降为有条件才能进 Step 4，3d/3e 降级措辞或整节写无法评估）。约 \$0.5，待充值后执行 |
| 4 | 报告组装（按官方模板生成 markdown、格式校验、引用核验） | 未开始 |
| 5 | 对照病人条件 + 报告组装 + 格式校验 + 引用核验 | 未开始 |

## 医学文献阅读规则（2026-11-11）

`docs/clinical_reading_rules.md`：**怎么读来源**的规则（不是医学知识），从盲测写错中提炼，每条附盲测正反例和测试集条目。两个用途：
- Step 3 语义核查（上下文核查）提示词的依据——提示词只写原则，规则里的例子不得进提示词（测试集泄漏检查会拦）；
- **审查任何报告 / 账本输出时，逐条过文末的审查清单**（基因是病因还是标志物、表格行所属亚型、他基因 / 他亚型 / 他物种证据、不良反应≠治疗先例、禁忌例外从句极性、条件程度不放大、完整上下文等）。
新的写错先归到已有规则，归不进去才新增规则。

## 练习与验收数据

`data/cases/practice/official_examples.json`：官网 Phase 0 的 12 个示例病例，临床描述逐字取自官网（2026-11-03 核对；SLC35A2 拆为 ex7 / ex8），部分有标准答案（例如 KMT2B c.8079delC 不触发 NMD）。
开发调试优先用这些练习病例，最后才跑 4 个评测病例，避免过拟合。

### 评测病例的保险（2026-11-08）

**起因**：一条不带 `--case` 的 `run_pipeline.py --from-step 3` 按 `CASE_FILES` 跑了全部文件，把 AITX-40001/40002/40003 的 step 3 输出重新生成了（40004 保持 11-03 的旧文件）。跑它们本身不算过拟合，**看它们的输出并据此调代码才算**；当时已立即停掉进程，没有读这三个文件的内容。
**处置**：`out/step3/AITX-4000{1,2,3,4}.json` 四个文件已删除，回到"评测病例未跑"的状态（step 3 之后没有任何产物，最近的查看页导出是 11-05，早于这次误跑）。`out/step1`、`out/step2` 下评测病例的旧输出保留——它们是确定性变异解析和疾病归一化，不含治疗内容。
**保险**：
- `run_pipeline.py` 不带 `--eval` 时**跳过**评测病例并打印 `[HELD BACK]`；**点名**跑（`--case AITX-4000x` 或直接给它们的文件）会被拒绝并提示用 `--eval`；评测病例的 id 从它们自己的文件读，不靠名字猜。
- 所有 step 3 验收脚本（3.0 / 3a / 3b / 3c / 3d / 3e）调用 `runmeta.refuse_eval_cases`，碰到评测病例直接退出；`acceptance_step3_0.py` 里原来打印 AITX-40003 分支的那段已删除。
- 测试 `tests/test_eval_holdback.py`（含静态检查：任何 step 3 验收脚本或期望文件都不许出现评测病例 id）。
- **Step 1 / Step 2 的评测病例期望已挪走**（2026-11-08 决定）：这些期望当年是按公开数据库记录（RefSeq、UniProt、OMIM、ClinVar）定的，所以保留，但移到 `scripts/acceptance_eval_cases.py`，**只有加 `--eval` 才会运行**；`acceptance_step1.py` / `acceptance_step2.py` 现在只读练习病例并调用 `refuse_eval_cases`。期望内容和出处存 `data/eval/eval_case_expectations.json`。
  - 被一起挪走的还有 Step 2 的一条硬检查（"同一基因里另一个变异不得用于排序"，原来写在 AITX-40002 上）。**常规 Step 2 验收因此少了精确匹配的反向检查**，正向检查（CFTR 的 P/LP 记录链到 CF）仍在。待补一个练习病例的等价反向用例。
  - `acceptance_eval_cases.py` 的 Step 2 部分只读 `out/step2/` 已有输出，自己不跑流水线、不调 LLM。

## 用户背景

用户是 agent / RAG 工程师，非生物专业。解释生物概念时用软件类比，用中文交流。

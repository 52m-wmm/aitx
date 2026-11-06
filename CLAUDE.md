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
| 3.0 | 证据账本与公共基础 | ✅ 已验收（2026-11-03，tag `step3.0-accepted`）：联网验收硬性项全过；规则 16 基因起草、独立支持度核查。规则现状（2026-11-05 复核，审阅表 `docs/rules_review_2026-11-05.md`）：4 条已加载、6 条已否决、**5 条待审（全是 COL1A1）**，其中 COL1A1-1/2/3/4 已按审阅收窄条件、支持度核查待重跑。契约 `docs/step3_0_contract.md` |
| 3a | 已确立层（Existing Targeted / Supportive / Contraindications） | ✅ 已验收（2026-11-04，tag `step3a-accepted`）；补充修复（提示词 `3a-v5`：表格行与段首限定作条件、治疗类转介、漏抽补抽、放宽从句、按变量合并缺失信息等）✅ 已验收（2026-11-05，tag `step3a.1-accepted`）：6 个练习病例 20/20 核实期望成立。规则变更见 3a 契约文末 |
| 3b | 临床试验 | ✅ 已验收（2026-11-05，tag `step3b-accepted`）：5 个练习病例 8/8 核实期望成立；逐条标准映射（LLM 映射、代码核验与比较）、病人事实模块、eGFR 公式（与 NKF 计算器核对）。契约 `docs/step3b_contract.md` |
| 3c | 老药新用 / 扩展使用（Off-label & Expanded Access） | ✅ 已验收（2026-11-06，tag `step3c-accepted`）：5 个练习病例 7/7 核实期望成立、全部新鲜输出、账本校验全过。契约 `docs/step3c_contract.md`（规则变更见文末 1–15 条） |
| 3d | 定制疗法（Bespoke Therapies） | 实现完成（`aitx/evidence/bespoke.py`，6 种手段逐一判定），离线测试 36 条；验收 2/8 成立、6 条因输出过期未计分（预算上限截断，明天补跑）。首轮统计：24 条判定中 10 条"无法评估"（41.7%），全部落在外显子跳跃（结构域、天然跳跃证据）和碱基编辑（PAM），都是审阅决定暂缓接入的数据源。契约 `docs/step3d_contract.md` |
| 3e | 药物重定位（Drug Repurposing，体外 / 动物证据） | 契约草案 `docs/step3e_contract.md`（v0.1，三个数据源已当场验证），8 个待定问题待审 |
| 4 | 查现成方案（FDA 说明书、ClinicalTrials.gov API v2、PubMed） | 未开始 |
| 5 | 对照病人条件 + 报告组装 + 格式校验 + 引用核验 | 未开始 |

## 练习与验收数据

`data/cases/practice/official_examples.json`：官网 Phase 0 的 12 个示例病例，临床描述逐字取自官网（2026-11-03 核对；SLC35A2 拆为 ex7 / ex8），部分有标准答案（例如 KMT2B c.8079delC 不触发 NMD）。
开发调试优先用这些练习病例，最后才跑 4 个评测病例，避免过拟合。

## 用户背景

用户是 agent / RAG 工程师，非生物专业。解释生物概念时用软件类比，用中文交流。

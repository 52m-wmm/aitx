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
- 每次 LLM 调用记录服务端实际返回的模型名，防止别名被悄悄切换
- 优先用实时 API 获取数据，引用必须能解析到具体记录（URL / accession）

## 开发方式

按节点逐步构建，**每个节点有契约文档（docs/）、离线测试（tests/）和联网验收脚本（scripts/acceptance_*.py），验收通过才进入下一步。**

| 步骤 | 内容 | 状态 |
| --- | --- | --- |
| 1 | 变异解析（确定性，无 LLM） | 完成：离线测试 49 个全过，联网验收全部 HARD 通过（2026-10-28） |
| 2 | 疾病归一化（基因 → OMIM / GenCC / GeneReviews） | ✅ 已验收（2026-10-28，tag `step2-accepted`）：`--fresh-llm` 硬性项全过；离线测试 135 个全过；症状提取测试集 32 条精确率/召回率 1.0（集合偏简单）；剩余问题见契约“已知局限” |
| 3 | 疗法匹配（变异机制 → 适用的治疗思路） | 下一步 |
| 4 | 查现成方案（FDA 说明书、ClinicalTrials.gov API v2、PubMed） | 未开始 |
| 5 | 对照病人条件 + 报告组装 + 格式校验 + 引用核验 | 未开始 |

## 练习与验收数据

`data/cases/practice/official_examples.json`：官网 Phase 0 示例病例，部分有标准答案（例如 KMT2B c.8079delC 不触发 NMD）。
开发调试优先用这些练习病例，最后才跑 4 个评测病例，避免过拟合。

## 用户背景

用户是 agent / RAG 工程师，非生物专业。解释生物概念时用软件类比，用中文交流。

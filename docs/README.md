# 项目文档

开工先读 [CLAUDE.md](../CLAUDE.md) 和 [AGENTS.md](../AGENTS.md)。本目录保存功能设计、未完成事项和必要审核记录。文档不等于代码现状，历史记载不自动构成当前授权。

当前 Step3 尚未完成：3a 使用 source_selection 选择 XML 节点并回填原文，Ledger 适配仍待实现。结构阶段设计保留供后续参考，不代表已完成或医学验收通过。

## 文档使用规则

- 功能设计回答“应该如何工作”；实现状态需对照代码和有效验收结果。
- 同一事项只保留一个主要出处，待办随对应功能文档维护。
- 历史提案、实验结果、已批准规则分开阅读；文件中的“用户批准”字样不能代替可核对的原始批准记录。
- 文档清理不改变医学规则、判定、账本或基线，也不把未知事项标记为已完成。

## 功能设计与契约参考

| 阶段 | 契约 |
|---|---|
| Step 1 变异 | [step1_variant_contract](step1_variant_contract.md) |
| Step 2 疾病归一化 | [step2_disease_contract](step2_disease_contract.md) |
| Step 3 公共证据账本 | [step3_0_contract](step3_0_contract.md) |
| Step 3a 已确立治疗 | [step3a_contract](step3a_contract.md) |
| 无章节支持治疗兜底 | [supportive_fallback_contract](supportive_fallback_contract.md) |
| Step 3b 临床试验 | [step3b_contract](step3b_contract.md) |
| Step 3c 老药 / 扩展使用 | [step3c_contract](step3c_contract.md) |
| Step 3d 定制疗法 | [step3d_contract](step3d_contract.md) |
| Step 3e 重定位 | [step3e_contract](step3e_contract.md) |
| 上下文核查 | [context_check_contract](context_check_contract.md) |
| Step 4 / 5 报告与确定性校验 | [step4_contract](step4_contract.md) |

## 规则与未完成事项

- [临床阅读规则](clinical_reading_rules.md)、[上下文核查](context_check_contract.md)、[已知限制](known_limitations.md)。
- [基因规则批准与否决记录](rules_review_2026-11-05.md)、[基线批准记录](../baselines/approvals.md)。
- 历史设计参考：[3a阶段1](step3a_structure_phase1_contract.md)、[阶段2](step3a_structure_phase2_design.md)、[行动词表](structure_action_terms.md)。均不代表当前接口。
- 3c与报告待核对事项已分别合并至对应契约末尾，不再单独维护重复待办。
- [盲测设计](blind_test_plan.md)、[召回计划](blind_recall_plan.md)、[盲测后修复计划](post_blind_fix_plan.md)。
- [指南候选](l4_symptom_guidelines_candidates.md)、[补充剂候选](supplement_list_candidates.md)。
- [3b查看页完成记录](step3b_viewer_completion.md)。

## 审核与历史

[保留的Step3审核及基线依据](experiments/README.md)。名称、来源匹配不等于临床适用；候选修复不等于正式发布。

旧过程报告、结构地图、旧清理报告和已合并待办已移出工作文档。历史记录中的旧路径仅用于追溯当时的工作；不恢复旧代码、调用授权或已删除输出。

## Step 3 代码位置

- `aitx/step3/a/ledger_adapter.py`：完整账本适配尚未接入，调用时明确报错。
- `aitx/step3/a/source_selection.py`：分块、请求预算、最多4并发执行、原始回答保存和XML原文回填。
- `aitx/step3/a/results.py`：导入既有审核结果，不调用模型。
- `aitx/viewer/step3a.py`：读取结果、生成原文展示HTML。
- `aitx/llm_cost.py`：共享费用计算及请求预算预留。
- `scripts/run_step3a.py`、`scripts/import_step3a_result.py`、`scripts/llm_cost.py`：命令行入口；`scripts/step3a_view.py`仅保留兼容导入。

病例页通过 `scripts/build_viewer.py` 调用正式3a渲染模块。整个Viewer服务本次未迁移；原文选择仍未自动转换成最终治疗报告。

Step3a 操作：`run_step3a.py recover --output <批次目录>` 只使用已保存响应离线恢复；`run_step3a.py run --resume --output <批次目录> --concurrency 4 --max-cost-usd <本轮总上限>` 只执行尚未请求的分块。有请求但无响应的分块不会自动重试。Viewer自动显示最新运行批次、完成数量和失败原因，并提供对应独立入口；当前批次不完整时不退回旧结果。

- `aitx/step3/b/`：`screening.py` 当前筛选、`criteria.py` 条件判定、`records.py` 局部刷新与历史回放；提示词同目录保存。
- `aitx/step3/pipeline.py`：Step 3 总编排，当前仍受 3a 未接入限制。
- `aitx/evidence/`：共享账本、患者匹配、数据检索和暂未迁移的 3c/3d/3e；`trials.py` 被多个步骤共用。

### 3a 数据保存与当前批次

- 批次原始资料与运行结果保存到 `runs/step3a/<病例ID>/<批次ID>/`。现有两份 OTC 批次已迁入，文件内容不变；内部历史路径作为当时运行记录保留。
- 页面自动展示最新批次：已执行批次按首个请求时间排序，尚未执行的准备批次按 plan.json 修改时间排序。`out/current.json` 仅保留为命令行默认操作批次，不影响页面。
- `prepare --case-id ... --cases ... --xml ...` 默认新建 UTC 时间戳批次，也可显式指定 `--output`。新准备批次自动出现在页面，明确标注尚未执行。
- `python scripts/run_step3a.py select --case-id PRAC-OTC --batch PRAC-OTC-rerun-c4-20261125` 指定命令行默认操作批次；页面仍自动显示最新批次。
- `recover --case-id ...`、`run --case-id ...` 使用当前索引；仍支持显式 `--output`。真实执行需要既有预算授权。完成批次的离线恢复直接返回，保留文件；重跑须创建新批次。
- 本轮仅整理 3a。3b、正式账本、历史实验及 `.cache/datasets/` 暂留原位，不清理 HTTP/LLM 缓存。

页面 Step 1/2 直接读取当前结果；3b 比较当前账本与导出结果的保存时间；3c–3e 展示当前账本的保存记录；Step 4 展示当前报告，Step 5 若无保存结果明确未知。页面文件监听包含报告 Markdown；最新保存不代表已按最新上游重算或审核通过。

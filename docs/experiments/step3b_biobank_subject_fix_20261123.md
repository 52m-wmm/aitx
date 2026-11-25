# 3b Biobank 患者／亲属主体修复（2026-11-23）

## 授权与范围

用户授权继续修第二个问题：本人确诊不能满足亲属条件，明确替代队列按 OR 处理。第一项 PHYOX7 的全部修复和已发布结果保留；不升级 baseline。

## 根因与修复

`criteria.evaluate` 的已确诊快捷路径只检查病名，旧缓存将“Relative of someone with confirmed primary hyperoxaluria…”映射成 diagnosis 后，患者本人的 AGXT 致病变异使其错误通过。

现在用原始完整条款（包括父项主体）检查患者／亲属范围，再执行诊断或基因比较。亲属或明确家族史条款不能凭患者自己的诊断、变异判为满足；缺少明确关联的亲属事实时为 unknown。保留模型原票与映射，不重新解释其他复杂的个人史／家族史混合排除条款。

本人／亲属 OR 必须有来源明确的队列描述，不凭列表顺序或病名猜测。ClinicalTrials.gov 官方元数据确认 ArmGroupLabel、ArmGroupDescription 字段；`trials.FIELDS` 增加这两个字段，`flat` 保留 population_groups。未来检索 URL 因字段变化而改变；本轮不重新检索试验、不改写现有 HTTP/LLM 缓存。

Biobank 的旧检索缓存未保存组描述，本轮复用上轮审查已独立保存的官方 API 全记录 `out/step3b-background-audit-20261123/NCT02026388.json`。脚本核对 NCT 身份及 eligibilityCriteria 与旧检索缓存全文一致。引用原句：

> Diagnosis of Primary Hyperoxaluria, or a family member of someone with this diagnosis.

原字段 `/protocolSection/armsInterventionsModule/armGroups/0/description`。通过已有 sourced 构造器保存 verified 证据 `d888e182b64b`，两例均引用该证据；不把队列说明伪作病例事实。

复用 Ledger 已有 `alternative`、`status_of` 和报告未知项筛选。已满足的本人队列不会被未知亲属队列阻塞，共同要求仍适用、共同 fail 仍优先。若队列来源缺失、关系含糊、无对应病种、嵌套强制条件或资格正文明确要求全部满足，则不自动套用 OR。复合诊断组已经有满足项时，只用该满足项对应的队列证据，不给其他未知诊断补同义或归属。

## 验证

真实比较路径先复现 pass 错误，回归修复后 209 项相关离线测试通过：本人/亲属/家族史、基因确认、模型引文缩短但完整条款为亲属、父项主体继承、来源缺失/矛盾、已满足诊断选项、本人 OR 亲属、共同排除优先、来源引用及报告不把已解决的替代项列为缺失信息。前言招募限制和所有原 3b 相关回归继续通过。

15 例缓存离线回放脚本 `scripts/experiments/apply_trial_subject_review.py` 在 socket 和 LLM 被阻断的进程中完成。模型调用 0、费用 $0；仅核对官方 API 字段元数据，临床来源复用既存缓存及独立官方记录。

## 实际结果

只修改 PRAC-AGXT-c33dup、PRAC-AGXT-c508GA 的 NCT02026388：

| 要求 | 改前 | 改后 |
| --- | --- | --- |
| r1：确诊患者的亲属 | pass，误引本人诊断 | unknown，缺亲属事实；relative 替代队列 |
| r4：本人诊断队列 | pass | pass，patient 替代队列；已有 PH 队列满足 |
| r2：未满足相关疾病入组标准的结石患者排除条款 | unknown | 原样保留 |
| r3：同意／配合要求 | not_assessed | 原样保留 |

两例试验总状态仍为 conditional：共同的 r2 尚未判定，而非要求患者同时满足亲属队列。本轮没有把它升级为 applicable。

所有行动 ID/key、全部旧要求 ID/原文/原 Evidence ID、所有旧证据内容、其余行动、第一项 PHYOX7 和82前言要求完全保留。每例新增1条队列说明证据，r1 修改主体结果，r1/r4 增加明确来源的 alternative 元数据。15例账本自检均通过；两例更新写回 out/step3。旧 _meta 时间/代码指纹不变，仅增加 subject_review_update，不声称整例刷新或新鲜；Step4/5报告未重建。

## 完整 status_diff 输出

改前对 current（15例，770行）：

```json
{"status_changed":3,"details_changed":12,"action_added":18,"action_removed":4,"baseline_missing":157}
```

发布后对改前（15例，770行）：

```json
{"details_changed":2}
```

发布后对 `baselines/current/snapshot.json`（15例，770行）：

```json
{"details_changed":14,"status_changed":3,"action_added":18,"action_removed":4,"baseline_missing":157}
```

缺基线病例仍为 RETEST-CNNM4 / RETEST-EIF2B1 / RETEST-PFN1 / RETEST-THPO。原有194项差异逐项完全相同，只新增两个 Biobank 详情条目，共196项；没有本轮状态变化、行动增删或未知转成确定患者事实。

完整逐条输出在 `out/step3b-biobank-subject-fix-20261123/`：

- `before-ledgers/`、`before/snapshot.json`、`before/diff.md`、`before/diff.json`：改前快照和完整 current diff。
- `published-vs-before/diff.md`、`published-vs-before/diff.json`：本轮全部变化。
- `published-vs-current/diff.md`、`published-vs-current/diff.json`、`published-vs-current/snapshot.json`：对 current 的完整输出。
- `subject-changes.json`：两条完整旧/新行动；`field-preservation.json`：15例全字段保护；`protected-before.json`：改前生产输出/基线哈希；`publication.json`：发布范围。

所有 baseline 与 approvals 原字节不变，无 promote。未运行评测病例、DMD、新模型调用或其他步骤。

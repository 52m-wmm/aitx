# 3b 前言当前招募限制修复（2026-11-23）

用户本轮只授权第一个问题：保留并比较前言的显式当前招募限制，硬条件 fail 优先于 unknown；Biobank 主体问题不处理。

## 规则与实现

- `trials.split_criteria` 将标题前原文标为 `enrollment_note`，保留 `pre1…` ID、原词与树关系，正文 ID 不变。
- `criteria.enrollment_note_lines` 独立读取原始前言，不依赖旧 LLM 缓存是否含该行。原正文提示词、版本和输入保持不变。
- 当前确定性语法识别 only enrolling / recruiting / accepting、open only to、closed to 的完整显式限制；支持带单位的年/月年龄上下界、闭区间及明确性别人群。数字、比较符、单位复用 `check_mapping` 核验，单位换算复用 `trials.age_months`。没有 NCT 专用规则。
- 未知年龄、条件句、历史描述、未解析队列、复合 OR、多行队列范围均保留未知，不假定患者属于某队列。其他无法解释的前言逐条保留为未知要求，不能当作已核验医学条件。
- 前言结果在普通年龄队列保守降级逻辑之后加入，沿用 `requirement_result`、`status_from`、`status_of`；任一共同硬条件 fail，试验分支为 not_applicable，不被 unknown 改回 conditional。
- `trial_records._record` 保存完整连续原句与 verified 引用；前言的 produced_by 为 code。若前言为决定性失败，理由保留完整原句，避免截掉年龄数字。

## 验证

先在真实 `_record` 路径复现：PHYOX7 前言 Requirement 缺失，回归测试 StopIteration。修复后使用原年龄队列映射确认正文年龄通过也不能盖过前言 fail。

195 项相关离线测试通过，覆盖 5/6/7 岁、年龄未知、下限、范围、月份、closed to 极性、空白、性别未知、历史/否定/条件/队列范围、证据引用及 fail 优先级。普通正文年龄队列测试保留；三处旧测试补齐原文输入，不默认空文本。

15 例改前完整账本在 `before-ledgers/`，全部生产输出与基线改前哈希在 `protected-before.json`。离线更新脚本 `scripts/experiments/apply_trial_enrollment_notes.py` 在 socket 与 LLM 调用被阻断的进程中完成，不调用模型、不联网、不刷新缓存。

## 实际账本变化

15 例中 5 例变动，共 10 个病例×试验条目追加 82 条原文前言要求：1 fail、81 unknown。未知不表示新的已验收患者条件。所有旧行动/key、所有旧要求行（含 ID）、所有旧证据内容与 ID 逐项保持；无行动新增/删除。

只有 PRAC-AGXT-c33dup 的 PHYOX7 状态 conditional → not_applicable：r38 的完整原文明确当前只招募 <6 岁，而病人原文 7-year-old。AGXT-c508GA 年龄未知，同一条款保持 unknown、试验仍 conditional。

| 病例 | 试验 | 改前 | 改后 | 解释 |
| --- | --- | --- | --- | --- |
| PRAC-AGXT-c33dup | trial:NCT04580420 | conditional | not_applicable | 新增当前年龄限制 fail；7 岁不满足 <6 岁 |
| PRAC-AGXT-c33dup | trial:NCT06465472 | conditional | conditional | 补入此前跳过的前言；未解析范围/事实保持未知，状态不变 |
| PRAC-AGXT-c508GA | trial:NCT04580420 | conditional | conditional | 补入此前跳过的前言；未解析范围/事实保持未知，状态不变 |
| PRAC-AGXT-c508GA | trial:NCT06465472 | conditional | conditional | 补入此前跳过的前言；未解析范围/事实保持未知，状态不变 |
| PRAC-CFTR-F508del | trial:NCT03921060 | not_applicable | not_applicable | 补入此前跳过的前言；未解析范围/事实保持未知，状态不变 |
| PRAC-CFTR-F508del | trial:NCT05704036 | not_applicable | not_applicable | 补入此前跳过的前言；未解析范围/事实保持未知，状态不变 |
| PRAC-CFTR-F508del | trial:NCT06429176 | not_applicable | not_applicable | 补入此前跳过的前言；未解析范围/事实保持未知，状态不变 |
| PRAC-CFTR-F508del | trial:NCT07628530 | not_applicable | not_applicable | 补入此前跳过的前言；未解析范围/事实保持未知，状态不变 |
| PRAC-GRIN2B | trial:NCT07723976 | conditional | conditional | 补入此前跳过的前言；未解析范围/事实保持未知，状态不变 |
| RETEST-PFN1 | trial:NCT04302870 | conditional | conditional | 补入此前跳过的前言；未解析范围/事实保持未知，状态不变 |

其余前言来自 Screening Criteria、子研究/队列和未使用标准标题的注册正文；本轮只保留来源及未知，不按猜测补年龄、诊断、用药或队列适用。Biobank 两例行动整条不变。

## 完整 status_diff 输出

改前相对 `baselines/current/snapshot.json`：

```json
{"cases":15,"rows":770,"baseline_missing_cases":["RETEST-CNNM4","RETEST-EIF2B1","RETEST-PFN1","RETEST-THPO"],"changes":{"action_added":18,"details_changed":4,"action_removed":4,"status_changed":2,"baseline_missing":157}}
```

发布后相对改前：

```json
{"cases":15,"rows":770,"baseline_missing_cases":[],"changes":{"status_changed":1,"details_changed":9}}
```

发布后相对 `baselines/current/snapshot.json`：

```json
{"cases":15,"rows":770,"baseline_missing_cases":["RETEST-CNNM4","RETEST-EIF2B1","RETEST-PFN1","RETEST-THPO"],"changes":{"status_changed":3,"details_changed":12,"action_added":18,"action_removed":4,"baseline_missing":157}}
```

完整逐项输出（不是以上汇总）位于 `out/step3b-enrollment-note-fix-20261123/`：

- 改前：`before/diff.md`、`before/diff.json`、`before/snapshot.json`。
- 本轮全部变化：`published-vs-before/diff.md`、`published-vs-before/diff.json`、`published-vs-before/snapshot.json`。
- 对 current 的完整输出：`published-vs-current/diff.md`、`published-vs-current/diff.json`、`published-vs-current/snapshot.json`。
- 全字段保护：`field-preservation.json`；全部前言及新 Requirement：`note-changes.json`；发布清单：`publication.json`。

相对 current 原有 185 项差异键全部仍在；本轮新增 9 个差异键，RETEST-PFN1 的另一项原已在缺基线 157 项中，其来源详情更新但仍缺基线。因此 current 总差异为 194，不是 195；不是新产生 3 条状态变化，原有 2 条未变，本轮仅 1 条。

## 发布边界

已将经过检查的 5 例 note-only 结果写回 out/step3，页面可读取“不符合”与完整年龄理由。旧 _meta 代码/上游/输入指纹和生成时间未伪改，只另记 enrollment_note_update；仍是历史账本，不等于当前代码整例刷新。没有重跑 3a/3c–3e、Step 4/5 或评测病例，也没有升级任何基线或写批准记录。后续正式报告若使用这些结果须另行重建验证。

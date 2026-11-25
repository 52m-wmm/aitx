# STOP PEDS 队列最小修复（2026-11-23，仅离线候选）

用户已批准此前方案；只修 NCT06654752，使用现有缓存，不联网、不调用模型，不发布正式账本，不升级基线。

## 实现范围

- `config/reviewed_trial_cohorts.json` 明确登记本次人工核对的六条原文与队列归属，不通用推断其他研究的队列。
- `criteria.reviewed_cohort_lines` 在已有比较后，只转换上述来源绑定的六条条款。复用现有 `alternative/status_of`：队列内 AND，队列间 OR，共同要求仍共同适用；共同 fail 仍优先导致 not_applicable。
- inc2 完整比较 [6,19)，inc3 完整比较 [3,6)，单位均为原文 years，换算为患者月龄。没有放宽 `check_mapping/sign_ok`；旧 LLM 原始回答、接受/拒绝结果完全不变。
- 15 岁病例仅保留 main 与 non-HEMT 活动路径。preschool 全部相关原文保留在 `details.reviewed_cohort.inactive_cohorts` 审计记录，不参与当前要求汇总。
- 年龄未知保留所有候选路径的年龄 unknown。没有任何年龄路径匹配时，也保留 unknown 供审核，不新增普通正文年龄的全局排除；结构化 registry 总年龄预筛规则不变。
- inc9 的 HEMT ≥3 个月不能靠“当前用药存在”证明，保留完整条款 unknown。inc10 的遗传型适用性、停药时间、未来计划和另外两种药物限制作为一条完整 unknown，不把旧四条平铺映射当作证明。
- inc11 肺功能操作能力、inc12 ppFEV1 同源条件分别绑定 main/non-HEMT；不加到 preschool。

本次刻意不实现通用疗程或非 HEMT 复合逻辑推理。这两条仍需完整病例信息和后续人工/代码核验，不能把 unknown 当作已经完成医学筛查。其他共同条件及既存问题（例如 exc7 原未评估的静脉抗菌治疗次数）保持原样，不在本次范围。

## 专项回归与真实缓存回放

回归先红：原 `lines_for` 没有 `alternative`，年龄队列测试以 KeyError 失败。修复后仅运行：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_stop_peds_cohorts.py
9 passed in 0.06s
```

覆盖15岁、5岁、3岁/6岁边界、19岁无匹配路径、年龄未知、仅 HEMT 存在不能证明疗程/非 HEMT、可满足主队列不被另一队列未知阻塞、共同硬排除优先，以及原文变化/缺身份/其他研究不套用审核规则。聚合测试中主队列全满足为明确标注的合成探针，不是对真实患者的新结论。

`out/step3b-stop-peds-fix-20261123/replay.py` 重放真实缓存，socket 与 llm.chat 均阻断，`_llm` 仅返回既存缓存回答。执行生产 `map_study/_record`，未调用任何新模型：

- 原始缓存 `.cache/llm/5bf6c353d49e3a1f23b605e18bd88bcf02de1d4615ecf56afa38f34fdae82e1c.json`；源文本取已冻结 `out/step3b-cftr-replay-20261123/frozen-studies.json` 的本研究。
- 重新校验映射与原保存映射完全相等，包括被拒的年龄下界；完整区间由本次已审核规则处理。
- 原26条活动要求变25条：移除活动 preschool 年龄1条、inc10四条合成完整1条、main/non-HEMT 年龄/肺功能能力/ppFEV1各增加1条路径副本，净减1。完整源文和旧证据保留。
- 所有非六条范围内的要求除局部顺序ID外逐字段相等；CF诊断两行均保持 pass，共同排除条款逐字段不变。
- 当前 main 与 non-HEMT 各4条队列要求；年龄均 pass，HEMT/非 HEMT、肺功能能力、ppFEV1 均 unknown。最终仍 conditional，reason 也与原来一致。
- 要求ID由原 `_record` 顺序生成，部分后续 r 编号移动。`requirement-correspondence.json` 给出旧行到新行的 item/队列/结果对照，不能按 r 编号误认为更换条件。
- 候选仅替换该研究行动；保留旧 provenance、行动key、所有旧证据及其他行动。合并本研究活动路径的缺失信息，移除其不再活动的 preschool 缺失贡献，其他行动的共同缺失条目保留。
- 整例候选 Ledger 自检15项 pass、1项既有 drug_keys_normalized warn、0 fail；该警告及详情与改前完全相同。其他研究仅按字节复制用于标准差异工具读取，未重新检索、映射或回归。

## 完整 diff 与保护核验

全部产物在 `out/step3b-stop-peds-fix-20261123/`：

| 文件 | 内容 |
| --- | --- |
| `before-ledgers/`、`before/snapshot.json` | 改前正式输出备份及15个已批准病例的标准快照 |
| `stop-peds-replay.json` | 原26条/新25条完整研究行动、inactive审计原文和16项自检 |
| `requirement-correspondence.json` | 全部旧要求行到新行/队列的对应 |
| `full-ledger.diff` | CFTR候选相对改前正式账本的完整字段级文本diff（含metadata、缺失信息、自检） |
| `scoped-code.patch` | 仅本次 criteria helper、配置、测试的代码diff，排除工作区先前改动 |
| `candidate-vs-before/diff.md`、`diff.json`、`snapshot.json` | 本轮候选完整标准diff，仅 STOP PEDS 详情1项 |
| `candidate-vs-current/diff.md`、`diff.json`、`snapshot.json` | 候选对 baselines/current 完整197项输出 |
| `formal-after-vs-before/diff.md`、`diff.json` | 正式账本前后diff0 |
| `formal-vs-current/diff.md`、`diff.json`、`snapshot.json` | 正式账本对 current 完整196项既存输出 |
| `protected-before.json`、`preservation-check.json` | 5831个正式账本、基线文件和既存LLM缓存SHA保持；旧196项差异逐项保留 |

标准工具均带 `--detailed`。完整汇总：

```json
{"cases":15,"rows":770,"baseline_missing_cases":[],"changes":{"details_changed":1}}
```

```json
{"cases":15,"rows":770,"baseline_missing_cases":["RETEST-CNNM4","RETEST-EIF2B1","RETEST-PFN1","RETEST-THPO"],"changes":{"details_changed":15,"status_changed":3,"action_added":18,"action_removed":4,"baseline_missing":157}}
```

```json
{"cases":15,"rows":770,"baseline_missing_cases":[],"changes":{}}
```

```json
{"cases":15,"rows":770,"baseline_missing_cases":["RETEST-CNNM4","RETEST-EIF2B1","RETEST-PFN1","RETEST-THPO"],"changes":{"details_changed":14,"status_changed":3,"action_added":18,"action_removed":4,"baseline_missing":157}}
```

候选对current的原196项变化全部逐项相等，唯一新增是 PRAC-CFTR-F508del / trial:NCT06654752 的 details_changed。3项状态变化和其他增删/缺基线均为改前已有，不能算本轮新变化。本轮没有新增状态变化。ETI上轮候选没有发布，本轮也没有把ETI候选混入正式基础。

正式 `out/step3/`、全部 `baselines/`（含批准记录）与旧LLM缓存哈希保持。只写独立candidate-ledgers和审计产物；没有promote、模型调用、网络请求或整例新鲜度声明。代码规则已保存，正式账本仍保持改前状态。

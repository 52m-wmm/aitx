# ENACT 条件遗漏最小修复（2026-11-23，仅离线候选）

用户批准仅修 ENACT NCT07148739 的五条已确认临床条款。只使用现有缓存，不联网、不调用模型；正式账本、基线和批准记录不写回。

## 根因与实现

原始模型回答13个片段，代码接受8个、拒绝5个。拒绝后的4条完整临床条件变成 not_assessed，被汇总忽略；inc5虽保留FEV1片段，抗生素时间窗及完整逻辑没有进入最终要求。

复用已有 `reviewed_rejected_lines`，在 `config/reviewed_trial_rejections.json` 追加5条本次人工批准的 NCT、item、完整原文和 fact/quote/reason。仅这些记录使用 `replace: true`，通过 `lines_for` 原位替换条款；原ETI追加处理不变。没有另建比较引擎或放宽校验。

| 原要求 | 修复前 | 修复后 |
| --- | --- | --- |
| r6 / inc4：三联CFTR调节剂稳定剂量至少two weeks | not_assessed | 完整原文unknown，记录threshold 2 not in the quote |
| r7 / inc5：肺病稳定性、急性FEV1下降、额外抗生素及4周窗口 | 仅FEV1片段unknown | 完整原句unknown，保留no、OR、4周窗口及抗生素片段拒绝原因 |
| r8 / exc1：4周内显著非意愿体重下降 | not_assessed | 完整原文unknown，记录比较符拒绝原因 |
| r11 / exc3：6个月内酒精或物质滥用史 | not_assessed | 完整原文unknown，记录比较符拒绝原因 |
| r12 / exc4：研究性干预试验28天或5半衰期取更长者 | not_assessed | 完整原文unknown，保留完整时间逻辑及拒绝原因 |

四条原文已经完整的要求沿用原证据ID；r7新完整原文增加1条verified/quote_verified证据，produced_by=code；全部旧证据逐字段保留。修复仅在原文和已审核拒绝签名精确匹配且尚未有效映射时生效；其他研究、源文变化、伪造/非审核拒绝不自动成为有效医学条件。重复拒绝不会增加重复要求。

原check_mapping/sign_ok、数字/单位规则、模型提示词及缓存键均不变。two weeks没有被错误当作已验证数值，用药存在也不能证明稳定剂量和疗程；不把within或复杂时间窗简单改成通用<=，不自行解释inc5原文OR的临床含义。

## ENACT专项离线回归

`tests/test_enact_criteria.py` 内嵌本研究冻结原文和原始模型回答，不依赖网络。先红：r6仍为not_assessed。修复后仅运行该专项：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_enact_criteria.py
6 passed in 0.25s
```

覆盖五条原位unknown、完整引文和拒绝原因、原8接受/5拒绝结果不变、CF诊断与基因型保留、行政知情同意仍not_assessed、其他unknown通过也不能掩盖这五条、仅用药存在不能证明疗程、重复拒绝去重，以及研究身份/完整原文/拒绝签名边界。测试socket与llm.chat均阻断，_llm仅返回冻结回答。

`out/step3b-enact-fix-20261123/replay.py` 另读取原缓存回放生产 map_study 和 _record：

- 原始LLM缓存 `.cache/llm/08a5c0b0ef1fdd8516fdceb5977785c23c7ad8e2d053ca4bdc570ad597d66f26.json`，原文取既存 frozen-studies.json 的本研究。
- 阻断socket/llm.chat，只将缓存回答提供给映射校验；新映射结果与旧保存映射完全相等。
- 原13条→新13条，所有r编号保留，五条范围外的8条要求逐字段完全相等；诊断、基因型、年龄、男性妊娠/哺乳结果及其他已有要求不变。
- 最终仍conditional；reason由 `depends on: lab; other` 变为 `depends on: other; other trial criteria`。此变化来自r7不再伪装成普通单点lab比较，五条完整临床要求均作为待核实条件。
- 候选只替换ENACT行动，其他行动、旧证据、provenance和supporting_precedents全保留。合并本研究最新缺失信息，其余行动共享的缺失信息保留。
- 候选整例自检15 pass、1既有drug_keys_normalized warn、0 fail。警告与改前相同，与本轮ENACT无关。

未重新运行其他研究；其余14个已批准病例仅字节复制供标准diff读取。ETI和STOP PEDS此前候选均未混入本轮正式基础。

## 完整diff与保护核验

产物目录：`out/step3b-enact-fix-20261123/`。

- `before/snapshot.json`、`before-ledgers/`、`before-code/`：改前快照、正式输出备份、本次修改前的两个代码/配置文件。
- `enact-replay.json`：原/新ENACT完整行动、状态、拒绝结果复现标记、自检。
- `requirement-correspondence.json`：全部13条旧/新要求对应。
- `full-ledger.diff`：CFTR候选相对改前的完整字段级文本diff，含缺失信息、新证据、checks和候选元数据。
- `scoped-code.patch`：仅本轮criteria修改、审核配置新增和ENACT专项测试，排除工作区先前改动。
- `candidate-vs-before/diff.md`、`diff.json`、`snapshot.json`：本轮候选完整标准diff，只有ENACT详情1项。
- `candidate-vs-current/diff.md`、`diff.json`、`snapshot.json`：候选对baselines/current完整197项差异。
- `formal-after-vs-before/diff.md`、`diff.json`：正式账本前后diff0。
- `formal-vs-current/diff.md`、`diff.json`、`snapshot.json`：正式对current完整196项既存差异。
- `protected-before.json`、`preservation-check.json`：10053个正式账本/全部baseline/旧HTTP及LLM缓存文件SHA保持；旧196项标准差异逐项保留，唯一新增ENACT详情。

以上status_diff均带 `--detailed`。完整标准输出汇总：

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

原196项差异在候选对current中逐项完全保留，新增仅PRAC-CFTR-F508del / trial:NCT07148739 的details_changed。原3项状态差异、增删和缺基线不属于本轮。没有新增状态变化或未解释变化。

正式账本与全部baseline（含批准记录）保持原字节；只保存独立candidate-ledgers，_meta原时间/指纹保留，另标test_only，不声称整例刷新。没有promote、模型调用、网络请求或其他研究回归。

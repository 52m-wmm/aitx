# ETI 已审核拒绝片段保留（2026-11-23）

用户批准最小修复，范围仅NCT07809867的inc1。现有校验规则保持；CF诊断pass保持；被拒而尚未处理的必要条件以unknown保留原文及拒绝原因。其他rejected不能自动当作有效医学条件。仅ETI专项离线回归，不调用模型，不修改正式账本或baseline。

## 改动

- config/reviewed_trial_rejections.json：人工已确认的ETI条款记录，精确绑定NCT、inc1、完整原文及两个已确认的fact/quote/reason。此记录不是通用“所有rejected有效”的规则，也不是baseline批准。
- criteria.reviewed_rejected_lines：仅匹配上述记录仍未被有效映射处理的拒绝片段，追加一条完整条款unknown；重复拒绝不会产生额外要求，同fact/quote已有有效映射时不重复补unknown。不同试验、原文变更、伪造片段不套用本次确认。
- 原check_mapping、sign_ok、数字/单位核验、提示词、版本、模型旧票均不变。>=8仍以comparison not as written被拒，one对应1仍以threshold not in quote被拒。
- 新行追加在原有行之后，旧要求ID不移位；证据使用原完整连续原句，produced_by=code。复用既有requirement/evidence/unknown及账本自检机制，没有新增架构或校验层。

## 回归及缓存核验

tests/test_eti_partial_mapping.py先复现缺失unknown的失败，修复后仅运行该ETI专项：5 passed。覆盖诊断保持pass、两个拒绝原因不变、完整条款unknown、伪造rejected不采纳、重复拒绝不膨胀、已接受片段不重复保留、试验及原文范围约束。

另在socket、llm.chat均被阻断的进程中读取原始缓存，重放当前map_study和_record；_llm仅替换为缓存已有回答，无模型请求。重新验证的映射结果与原缓存装配结果完全相同：该inc1一条接受、两条拒绝。

真实候选仅变化PRAC-CFTR-F508del的NCT07809867：

- 原12条Requirement逐字全等，r2 CF诊断仍pass。
- 新增r13 inclusion/unknown，完整引用原inc1；details.reviewed_rejections保留F508del与ETI稳态条件的原文和各自拒绝原因。
- 新增verified、quote_verified的证据4cf0fa2b17f2。
- 总状态仍conditional；reason补充other trial criteria，不把错误>=8放行，也不因诊断pass让必要用药条件消失。
- 所有旧行动ID/key、旧证据、3c追加字段、旧provenance保持；其他研究不运行、不改写。

候选整例Ledger自检通过。只保存candidate-ledgers/，未写回out/step3，旧_meta生成时间/指纹保持，另标test_only更新元数据，不称整例刷新。

## 完整status_diff与保护核验

所有文件位于out/step3b-eti-rejected-fix-20261123：

- before-ledgers/、before/snapshot.json：改前完整快照。
- eti-replay.json：旧/新ETI行动、新r13、证据与自检。
- preservation-check.json、protected-before.json：正式账本、全部baseline和LLM缓存改前后哈希一致；候选旧要求/证据全等。
- candidate-vs-before/diff.md、diff.json、snapshot.json：本轮候选完整变化，仅details_changed=1，无状态增删变化。
- candidate-vs-current/diff.md、diff.json、snapshot.json：候选相对baselines/current完整197项，原196项保留，增加ETI详情1项。
- formal-after-vs-before/diff.md、diff.json：正式账本改前后diff0。
- formal-vs-current/diff.md、diff.json、snapshot.json：正式账本相对current完整196项既存差异。

标准输出汇总：

```json
{"cases":15,"rows":770,"baseline_missing_cases":[],"changes":{"details_changed":1}}
```

```json
{"cases":15,"rows":770,"baseline_missing_cases":["RETEST-CNNM4","RETEST-EIF2B1","RETEST-PFN1","RETEST-THPO"],"changes":{"details_changed":15,"status_changed":3,"action_added":18,"action_removed":4,"baseline_missing":157}}
```

```json
{"cases":15,"rows":770,"baseline_missing_cases":[],"changes":{}}
```

正式对current仍为14详情/3状态/18新增/4删除/157缺基线。本轮没有基线升级或批准记录改动，模型0/联网0/$0。STOP PEDS、ENACT和其他CFTR问题保持待处理，不在本次范围。

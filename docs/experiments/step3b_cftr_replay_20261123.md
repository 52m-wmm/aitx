# PRAC-CFTR-F508del：3b 缓存重放与原文核对（2026-11-23）

## 结论

3b 历史缓存重放成功，检索分组、排序、上限与115条试验核心行动均可复现；原文／病例逻辑核对未通过，发现4类缺口。本轮只检查，不修改临床规则、正式账本或基线，不把“结果一致”当成“结果正确”。

## 病例依据

15岁男性；CFTR c.1521_1523del p.Phe508del 纯合，Step2诊断分支为囊性纤维化。原文有慢性呼吸道症状、反复感染、胰腺外分泌不足并接受酶替代、CBAVD。未提供 HEMT/ETI 用药、用药时长、肺功能、培养结果、近期静脉抗生素／激素、近期急性加重、体重等入组信息。不能将胰酶替代当作 CFTR 调节剂治疗，也不能将反复感染当作本次急性加重或指定病原体阳性。

## 实际执行与边界

没有运行整个 Step1–5 流水线，也没有刷新 ClinicalTrials.gov。读取正式保存的 Step1/2、既有HTTP检索响应和旧LLM响应，通过当前生产代码执行：

1. 10个原分析试验逐个调用 `criteria.map_study(use_cache=True)`，10/10缓存命中；真实模型调用0、费用$0。缓存命中写入现有会话日志。
2. 用冻结响应作为T.search输入，真实 `trials.plan_branch` 重新执行相关性、预筛、排序及K上限。对比原trial_searches完全一致。
3. 当前 `trial_records._record` 重建10个逐条分析及105个预筛不符合行动，真实Ledger自检无fail；正文比较过程封锁socket和LLM调用。
4. 对比生产记录的全部 `_record` 核心字段，差异0。3c追加的supporting_precedents及原provenance不属于本次重建输出，未删除或覆盖它们；原正式文件完全不写。

这验证的是已有临床来源快照；本轮没有取得当前招募状态／队列变化。官方浏览页面返回的是动态外壳，未将其当作新的临床记录内容。

## 检索结果

| 分类 | 数量 |
| --- | ---: |
| 去重返回 | 1810 |
| 逐条分析 | 10 |
| 预筛不符合 | 105 |
| 超出K上限，未逐条分析 | 59 |
| 相关性／登记状态过滤 | 1636 |

分类合计1810，无新增／遗漏分组差异。105项预筛失败均与冻结登记字段和病例事实一致：104有年龄冲突、3有性别冲突，2项重叠；另1项仅女性条件排除（NCT05704036）。这里不是105项都因年龄排除。

最终115条行动：10 conditional，105 not_applicable，没有applicable。

10项逐条分析为 NCT07809867、NCT05548283、NCT07148739、NCT06364176、NCT07485543、NCT03587961、NCT06339593、NCT07930221、NCT06654752、NCT07903792。只分析前10项，不声称59项超上限研究已核验。

## 问题1：同一条款的部分映射失败，必要条件没有生成要求行

NCT07809867（ETI药代研究）：原文inc1同时要求CF诊断、至少一个F508del以及已接受ETI至稳态（8天）。模型映射中“one”对应数值1被校验拒绝，稳态8天被映射成>=8而原文比较符校验不接受；拒绝本身不能绕过。问题是同一inc1的CF诊断片段仍被接受，于是整条未映射fallback没有运行。最终只有诊断行，没有F508del/ETI用药时长的Requirement；当前理由里的current medication来自排除项的相互作用药物，不代表该入组用药要求已处理。

病例没有提供ETI治疗史，这个关键缺口应当保留未知而不是消失。本轮没有修复或补判。

## 问题2：STOP PEDS 多队列仍被平铺

NCT06654752原文年龄：主队列/non-HEMT为6至<19岁，学龄前为3至<6岁。15岁符合前者，学龄前不是该患者应补充信息的队列。然而r3仍是共同unknown。主队列HEMT至少3个月（r7）与non-HEMT独立资格及用药路径（r8–r11）都作为共同条件，未形成队列选择。

此外6至<19的下界>=6映射被拒绝（当前范围校验不支持to后紧跟<），r2只保留了<19的上界比较；本例15岁的年龄结论与原文一致，但不能据此证明双边界校验完整。

诊断及已知基因型可以支持部分基础条件；HEMT、用药时长、ppFEV1≥50%、可重复肺功能检查、近期抗生素／激素／培养等未提供，应保留未知。总体conditional可以与缺失数据相容，但不等于队列逻辑已验收。

官方原文链接：https://clinicaltrials.gov/study/NCT06654752；实际核查依据为frozen-studies.json中的缓存原文。

## 问题3：临床条件映射失败后变成not_assessed，被状态计算忽略

- ENACT NCT07148739 r6：稳定三联CFTR调节剂至少two weeks，数字单词导致拒绝；该关键入组条件变成not_assessed。另有近期体重下降、其他试验等排除要求未映射。
- STOP360AG NCT05548283 r6：规定时段内至少one次Pa阳性培养，映射拒绝后not_assessed。
- STOP PEDS NCT06654752 r23：近12个月Three次及以上IV抗生素治疗急性加重，映射拒绝后not_assessed。
- BMD003 NCT07485543 r30：近期吸入药械试验或CFTR调节剂，未映射后not_assessed。

这些是医学筛查条件，不能与知情同意等行政项混为一谈。现有契约允许未映射原文not_assessed，因此重放忠实复现，但实际筛查完整性存在缺陷。其他未知项使当前总体仍conditional，不能用这一总体状态掩盖遗漏。

## 问题4：注册排除段否定表述的极性待审

STOP360AG NCT05548283的Exclusion段写有“Participant is not pregnant”、No known renal impairment等否定表述。r7按男性事实直接pass，未解决“否定句放在排除段”的极性与注册写法歧义。需要审查完整来源，既不能盲目反转产生新排除，也不能当成已经核实的通过。

## 完整证据与差异输出

`out/step3b-cftr-replay-20261123/`：

- before-ledgers/：改前15例完整账本；protected-before.json：正式输出与全部baseline哈希。
- frozen-studies.json：已有检索响应对应的1810项登记内容；mapped/：10项真实缓存映射及所有rejected原因。
- replayed-trials.json：115条实际重建的3b行动、引用、缺失信息与自检；不是整例Step3新账本。
- replay-action-changes.json：核心行动差异为空数组；plan-replay-comparison.json：分类与原计划一致。
- audit-findings.json：病例依据、计数、10项分析摘要与4项问题。
- after-vs-before/diff.md、diff.json：本轮正式账本差异0。
- after-vs-current/diff.md、diff.json、snapshot.json：对baselines/current完整196项既有差异。

status_diff完整命令输出汇总：

```json
{"cases":15,"rows":770,"baseline_missing_cases":[],"changes":{}}
```

```json
{"cases":15,"rows":770,"baseline_missing_cases":["RETEST-CNNM4","RETEST-EIF2B1","RETEST-PFN1","RETEST-THPO"],"changes":{"details_changed":14,"status_changed":3,"action_added":18,"action_removed":4,"baseline_missing":157}}
```

生产输出与baseline逐文件哈希均与改前一致，0新增临床状态变化，无promote、无新模型调用、未运行评测Step3+。后续应分别修复完整条款覆盖、队列作用域与未映射临床条件语义，不能直接宣称这例通过医学验收。

# STOP PEDS 完整上下文实验（2026-11-24，待用户审核）

本轮仅 NCT06654752，一次真实 DeepSeek 请求。用户启动前明确要求非高峰运行；实际启动时高峰窗口为空。没有重新检索临床记录，没有其他病例模型请求，没有修改生产临床流程、正式账本或基线。

## 结论

完整原文输入后，模型输出20条条件、24条原文层级记录，识别main、non-HEMT、preschool三个队列。六条人工已审核的队列专属条款，模型归属均与原文审核一致（6/6，仅本例六条，不是整体医学准确率）。两组年龄均为完整半开区间[6,19)、[3,6)。

18条条件通过当前原文引用/结构机械核验；2条被拒并保留unknown，不继续患者比较。模型保留了更多关系，但完整结构化仍未通过验收：否定不是独立NOT节点，一些时间窗只留在原句里。不能据此宣称全部医学条件完整或正式3b已修好。

## 输入和执行边界

- `eligibility-original.txt`是先前已冻结缓存中本研究EligibilityCriteria的原字节全文。`messages.json`用户消息完整包含该字符串，不经split_criteria、去标题或丢弃嵌套条款。保留Markdown反斜杠、编号、缩进、空行。
- 当前STOP原文没有前言。因此本次实证完整标题和嵌套上下文路径，不能声称已验证“有前言”案例。提示词要求保留前言，未来若来源有前言同样直接输入全文。
- 旧生产items_for_llm会排除preamble，输出编号+kind+text；虽然旧输入保留Age等标题文字，但不提供parent/level和原始缩进。新实验不依赖此预切分结果。
- 模型只收到试验原文，不提供患者病史、年龄、基因型或旧审核队列表；输出不包含患者资格结论。
- Python在收到回答后才读取现有CFTR患者事实和旧缓存做计算/比较。人工审核表仅用于事后对照，没有作为模型答案提示。
- 实验脚本独立放在scripts/experiments/stop_peds_full_context.py，未接入生产criteria或试验账本装配入口。

服务端实际返回`deepseek-flash`；temperature0，thinking disabled，max_tokens8192，finish_reason stop。原始usage：1227输入token（冷缓存1227、命中0），4795输出token，总6022。按项目非高峰费率核算$0.00306105，不是另行核验供应商账单。只一次请求、没有网络/格式/长度自动重试；所有原始回答保留。

## 三个队列对照

| 来源条款 | 旧缓存 | 本轮模型归属 | 本例Python结果 |
| --- | --- | --- | --- |
| main/non-HEMT：6至<19岁 | >=6映射被拒，只余<19；无队列alternative | main、non-HEMT；[6,19)完整 | 两路径年龄pass |
| preschool：3至<6岁 | >=3映射被拒；15岁仍留普通unknown | 仅preschool；[3,6)完整 | 15岁不在preschool年龄路径 |
| HEMT至少3个月 | 无队列绑定 | main、preschool | unknown，病例没有稳定用药疗程事实 |
| 非HEMT复合资格 | 四条药物片段平铺 | 仅non-HEMT，部分AND/OR结构 | 结构核验拒绝，整条unknown |
| 可重复肺功能操作 | 无队列绑定 | main、non-HEMT | unknown，不施加给preschool |
| ppFEV1≥50% | 无队列绑定 | main、non-HEMT | unknown，不施加给preschool |

本例计算：main conditional、non-HEMT conditional、preschool路径not_applicable（年龄不符），跨可选队列汇总仍conditional。这里只排除一条候选队列，不是将整项研究改成不适用。共同条件继续同时约束两个可行队列。

原正式研究行动26条要求且所有条款无alternative；本轮20条是结构树记录，包含9排除、8入组、1行政、2重新筛查规则，内部28个atom、6个all、2个any、0个not。计数粒度不同，不能用26→20宣称减少重复或提高召回。

## 两条拒绝与仍存在的结构缺口

### CF诊断组合条款

模型表达了“CF表现 AND（汗氯≥60 OR 两个致病CFTR变异）”，但把有编号、缩进、换行的原文拼成单行引用。当前实验要求字符连续原文，因此拒绝整个组合并保留unknown。

这是引用格式问题，未发现该处新造医学内容：现有ledger.quote_in的空白归一匹配会通过。没有为让结果通过而改写回答或事后放松本轮严格引用规则。原始模型JSON保持原样。

### non-HEMT否定结构

模型把大体逻辑表达为：

`(基因型不适合HEMT OR (未服HEMT至少3个月 AND 明年不计划启动)) AND 两种其他调节剂停用至少3个月`。

但“不适合”和“无计划”被编码为comparison==、value=0，原文没有数字0，当前数值来源核验因此拒绝。这是未约定的布尔编码与数值schema冲突，不能将0当成真实医学阈值或患者事实。回答没有独立NOT节点。

此外，第二支中的“eligible”没有独立原子条件，两种药物的or及否定范围仍压在一个duration atom里，不能说该复合条件已完整可计算。整条保留unknown；没有把既有CFTR基因型直接当作HEMT适用或不适用。

### 其他局限

- 14天内近期抗生素/全身激素、12个月培养史和ABPA用药等窗口保留在引用文字或name中，并非全部变为独立时间比较字段。
- Three or more IV-treated PEx被识别为value3，原文Three保留且通过引用数字核验；患者近12个月次数仍未知。
- 两条≥21天可重新筛查规则单独记录为rescreen_rule（not_assessed审计规则），没有变成所有患者必须满足的普通入组要求，也没有当作当前排除条件的无条件豁免。
- 慢性抗生素中other than azithromycin保留为完整引用/变量名称，没有展开药物集合例外比较，仍unknown。
- 同意/依从性记录为行政；短信和互联网能力仍为入组unknown。
- 原临床条款的文字均可在模型条件引用中找到对应；两个纯标题不进入活动条件、仍保留outline。文字覆盖不代表每个临床子条件都已独立抽出或逻辑正确。

## Python核验与结果保留

核验源引用、父子引用包含关系、节点类型、AND/OR/NOT结构、条件ID、队列引用、阈值与单位来源、完整年龄区间。仅对通过核验且有现成完整比较器的表达式进行患者比较；其余unknown。

初次严格整体验证在CF引用处报错停止，已原样保留执行状态。随后只调整独立实验分析器，对已知ValueError逐条记录rejected并保留unknown，继续报告其他可验证条件；不捕获缺字段KeyError继续填默认值、不修改原始回答、不重新调用模型。该变化是实验离线分析，不是医学条款放行或生产修复。

本轮专项离线检查5 passed。新增检查确保引用不匹配、原文无数字0时不进行患者比较而保留unknown。其他病例不运行。

## 审核材料和完整差异

目录 `out/step3b-stop-peds-full-context-20261123/` 沿用准备日期；实际调用及本报告为2026-11-24。

- `messages.json`、`eligibility-original.txt`、`plan.json`：完整输入、独立提示词、参数和源SHA。
- `response.json`、`parsed.json`：唯一真实原始回答、原始模型结构，不覆盖不改写。
- `comparison.json`：20条模型原文及结构、18通过/2拒绝、每条Python轨迹、三个队列、原26条完整要求、原条款覆盖和6条归属逐项对照。
- `experiment-diff.json`：逐来源条款的旧映射、旧拒绝、旧要求与新结构对应，以及年龄/疗程/否定审阅点。
- `old-vs-new-structure.diff`：旧缓存映射对象对新模型对象的完整文本diff（schema不同，仅审计，非生产补丁）。
- `cost.json`：本次唯一调用的模型、原usage、非高峰费用核算。
- `execution-state.json`：最终离线分析完成、模型1次、等待用户审核；保留最初严格失败信息。
- `preservation-check.json`：正式账本、全部baseline和旧HTTP/LLM缓存SHA保持。相对准备前仅已获授权的aitx/llm.py密钥变量改名不同，不是本轮临床逻辑改动。
- `formal-after-vs-before/diff.md`、`diff.json`、`snapshot.json`：正式前后完整diff0。
- `formal-vs-current/diff.md`、`diff.json`、`snapshot.json`：正式对current完整196项既存差异，14详情/3状态/18新增/4删除/157缺基线，本轮无新增。

没有把独立结构结果写回正式账本或此前STOP候选，也没有升级基线。只完成本例实验与差异报告，停在用户审核点；不自动重发修正提示词、不扩展其他案例、不接生产。

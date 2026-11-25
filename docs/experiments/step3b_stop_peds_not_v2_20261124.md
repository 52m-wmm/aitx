# STOP PEDS non-HEMT 显式NOT实验v2（2026-11-24，待审核）

## 结论

本轮只允许并执行1次真实DeepSeek非高峰调用，未自动重试。布尔0/1问题已在本候选中消失；两个OR分支、正向HEMT资格、HEMT停用至少3个月、未来一年无启动计划均得到明确结构。整体仍未修复完成：两种药物没有分别输出独立NOT/时间窗，而且第二种药物子引用不是原文。整条non-HEMT严格核验仍拒绝，患者结果unknown。

## 实际输入及改动范围

独立脚本scripts/experiments/stop_peds_nonhemt_not.py复用上一版实验工具，仅在本进程设置独立OUT、实验Prompt和核验函数；没有修改aitx或生产入口，也没有覆盖上次实验文件。User消息与上次逐字相同，完整包含EligibilityCriteria（原标题、缩进、编号、嵌套、空行、Markdown转义）。没有传入患者病例。System追加禁止布尔数值编码、正向资格、独立药物否定、NOT绑定时间窗等明确要求；这是针对既知问题的定向提示词实验，不是盲测。

本来源仍没有前言，不能据本例证明有前言病例的改进。模型只结构化条件；患者结果由Python对照原有事实计算，不能确认者unknown。

## non-HEMT逐项比较

| 检查项 | 上次 | 本次 | 结论 |
| --- | --- | --- | --- |
| 用0表示不适合/无计划 | 两个==0原子 | 0处，相关原子value=null | 本候选已修复 |
| 显式NOT | 0个 | 4个 | 有改善；全部五个预期独立否定节点尚未齐备 |
| 两个OR分支 | 已有OR，但第二支缺正向资格 | 保留OR两支，第二支有eligible原子 | 改善 |
| 基因型资格 | 不适合用0；正向资格遗漏 | NOT(基于CFTR基因型具备资格)；第二支eligible | 正向资格恢复；第二支依上下文承接基因型依据 |
| HEMT停用至少3个月 | 否定藏在duration名称中 | NOT(期间发生用药)，NOT自带>=3个月lookback | 引用与本例窗口规则核验通过；病例历史未知 |
| 未来一年无启动计划 | plan==0，时间只在文字里 | NOT(plan)，NOT自带within1 year future窗口 | 引用/窗口核验通过；value1是实际一年时间量，不是true |
| 两种药物的独立否定 | 一个duration名称 | NOT(A OR B)，共用>=3个月窗口 | 未按要求分别产生NOT(A)、NOT(B)及各自窗口 |
| 第二种药物引用 | 原完整句保留在扁平节点 | 子引用taking lumacaftor-ivacaftor | 不是原文连续片段，拒绝 |
| 整条non-HEMT | rejected / unknown | rejected / unknown | 未整体修复 |

新候选的逻辑轮廓（仅概括，原始JSON保持不变）：

```text
AND(
  OR(
    NOT(基于CFTR基因型具备HEMT资格),
    AND(
      具备HEMT资格,
      NOT(入组前至少3个月窗口中发生HEMT使用),
      NOT(计划在未来一年启动HEMT)
    )
  ),
  NOT(至少3个月窗口中发生tezacaftor-ivacaftor OR lumacaftor-ivacaftor使用)
)
```

两个药物采用同一时间窗时，NOT(A OR B)在三值逻辑下也与NOT(A) AND NOT(B)等价。因此此处不能笼统说模型逻辑反了；但它没有满足本次明确要求的独立药物节点/各自时间范围，且存在真实引文错误。不能以德摩根等价为由绕过引用核验。

原文只有“taking tezacaftor-ivacaftor or lumacaftor-ivacaftor”，没有再写一次“taking lumacaftor-ivacaftor”。模型为第二种药物补全了共享谓词，语义可以理解，引用却不再逐字。下一步可以考虑用各自药物名作短原文引用、完整父句保留共享谓词，再分别绑定NOT和窗口；本轮没有改写模型回答或发第二次请求。

## Python核验与患者结果

- 核验条件及表达式引用、父子引用包含、节点关系、数字/单位来源和队列引用，继续沿用上一版机械检查。
- v2对布尔原子要求value=null；NOT时间窗必须引用本例原文at least3 months或next year，保持lookback/future、单位和比较关系。anchor=enrollment来自本研究语境，不是每个子句都逐字含有enrollment；不能把它误当成完全由字符串核验得出的医学结论。
- 四个NOT子树中，基因型资格、HEMT停用窗口、未来用药计划三棵通过局部机械核验；两种药物组合子树因子引文不匹配被拒。根条件因此unknown，未执行其患者比较。
- 停药史和未来计划等病例均未提供，不推断有或无。离线检查确认NOT(unknown)仍是unknown，不把NOT(用药时长>=3个月)当作三个月完整无用药史。
- 本例仍为main conditional、non-HEMT conditional、preschool年龄路径不符；整项仍conditional。没有写入正式状态。

## 全部20条与上次逐条比较

verified/rejected仅指当前引用和schema机械核验，不能当作医学正确率；unknown并不等于患者不符合。

| 条件ID | 上次核验/结果 | 本次核验/结果 |
| --- | --- | --- |
| inc_age_main_nonhemt | verified / pass | verified / pass |
| inc_age_preschool | verified / fail | verified / fail |
| inc_cf_diagnosis | rejected / unknown | rejected / unknown |
| inc_consent | verified / not_assessed | verified / not_assessed |
| inc_hemt_main_preschool | verified / unknown | rejected / unknown |
| inc_nonhemt_hemt_status | rejected / unknown | rejected / unknown |
| inc_spirometry | verified / unknown | verified / unknown |
| inc_ppfev1 | verified / unknown | verified / unknown |
| inc_text_internet | verified / unknown | verified / unknown |
| exc_investigator_judgment | verified / unknown | verified / unknown |
| exc_acute_antibiotics | verified / unknown | rejected / unknown |
| rescreen_acute_antibiotics | verified / not_assessed | verified / not_assessed |
| exc_systemic_corticosteroids | verified / unknown | rejected / unknown |
| rescreen_systemic_corticosteroids | verified / not_assessed | verified / not_assessed |
| exc_solid_organ_transplant | verified / unknown | verified / unknown |
| exc_mycobacterium_abscessus | verified / unknown | rejected / unknown |
| exc_ntm_antibiotics | verified / unknown | verified / unknown |
| exc_pex | verified / unknown | verified / unknown |
| exc_chronic_oral_antibiotics | verified / unknown | verified / unknown |
| exc_abpa_corticosteroids | verified / unknown | rejected / unknown |

本次13 verified / 7 rejected；上次18 / 2。除了non-HEMT仍拒绝外，需明确记录其他变化：

1. CF组合引用：本次顶层完整来源含编号和换行，但内部AND/OR父节点只引用标题，子条件引用超出父引用范围，仍拒绝；并未借此次实验解决CF问题。
2. 主队列/学龄前HEMT>=3个月被标为medication并携带数值3，未按v2要求把布尔用药与疗程拆开。v2布尔字段限制拒绝它。这是字段类型/schema问题，不是把真实时长3误认为原文没有的0/1。
3. 四条近期用药/培养/ABPA历史的原子comparison输出within，超出了原子schema枚举（within仅在新增window里允许），均拒绝unknown。模型保留了更多时间信息，却放到了不支持的字段。

因此18→13既涉及全量回答的变化，也涉及v2更明确的类型规则，不是直接可比的医学准确率。没有放宽规则或对答案做人工补丁来制造通过结果。

六条已审核队列归属仍均正确；本轮condition.quote新增原始列表序号，旧离线对照脚本一开始按完全相等定位失败。已只修正实验对照定位，允许在完整引用中查找原条款（保留编号前缀），没有改写模型引用或重发请求。详见cohort_scope_comparison。原始模型JSON和上次全部实验文件保持原字节。

## 执行、费用及保护

4项本轮专项离线检查通过：禁止布尔数值、完整lookback范围校验、未来一年范围、NOT未知仍未知和完整原文输入路径。未扩展其他病例。

实际服务模型deepseek-flash，temperature0，thinking disabled，max_tokens8192，finish_reason stop。1761输入token（命中384、未命中1377），5415输出，总7176；按项目非高峰费率计算$0.003456702，并非另行核验供应商账单。仅一次LLM请求，不自动重试。

10146个受保护文件（生产aitx/config、正式账本、全部baseline、旧HTTP/LLM缓存和上次实验文件）SHA均不变。正式前后status_diff为0；相对current完整196既存项逐项保持：14详情/3状态/18新增/4删除/157缺基线。本轮没有新增生产状态或条款变化，不promote、不写批准记录。

## 审核产物

`out/step3b-stop-peds-not-v2-20261124/`：

- messages.json、plan.json、eligibility-original.txt：实际输入与参数；prompt-v1-vs-v2.diff为完整提示词差异。
- response.json、parsed.json：唯一原始回答，不修改。
- comparison.json：全20条引用/结构/核验状态/患者计算轨迹和队列结果。
- nonhemt-comparison.json、logic-audit.json、not-node-validation.json：新旧non-HEMT逐项比较、关系审阅及四个NOT子树核验。
- all-condition-comparison.json：全20条旧/新对象、核验结果、拒绝理由与患者结果逐条对照。
- previous-vs-v2.diff：两次模型结构的完整文本diff。
- cost.json、execution-state.json：费用和等待审核状态。
- protected-before.json、preservation-check.json：保护核验。
- formal-after-vs-before/、formal-vs-current/：完整标准status_diff的JSON/Markdown/快照。

结论为部分改善、未整体修复。实验完成后停止，等待用户审核；没有继续改正式流程或补调模型。

# STOP PEDS两药否定与时间范围：v4聚焦实验（2026-11-24，待审核）

## 结论

**仅这一条，本次模型候选通过了原有Python核验器：两种药物分别为显式NOT，各自绑定入组前至少3个月窗口，引用逐字匹配，AND/OR关系保留。**

这是本例、该条款的结构核验通过，不是证明患者符合，也不是整个non-HEMT或Step3b完成医学验收。患者这两种药物的完整近期使用史没有提供，仍unknown；NOT(unknown)仍unknown。

## 实际输入与单次调用

仍使用原完整EligibilityCriteria，保留编号、标题、缩进、空行和嵌套；User消息与上一轮完全相同。仅提取末尾两种药物条款，没有提取其他条件，没有发送患者病例。

在上一轮System后追加具体节点格式：每个原子必须op:atom、窗口直接位于每个NOT节点、原式NOT也必须有窗口、原子仅引用药物名、AND连接另放attachment。只改独立实验提示词；复用上一轮scripts/experiments/stop_peds_drug_windows.py的同一个verify函数，**未修改或放宽核验器，也没有改写原始模型JSON**。执行器在独立out目录run.py，不进入生产调用路径。

本次一次真实非高峰deepseek-flash调用，无自动重试。1461输入token（命中256、未命中1205），554输出，总2015；按项目非高峰费率$0.000513918，非独立核验的供应商账单。

## 这一条的实际结构

原文逐字引用：

> and also not taking tezacaftor-ivacaftor or lumacaftor-ivacaftor for at least 3 months

候选保留两种视图，原始JSON见parsed.json：

```text
source_expression:
  NOT [window: 入组前至少3个月] (
    tezacaftor-ivacaftor使用 OR lumacaftor-ivacaftor使用
  )

independent_expression:
  AND(
    NOT [window: 入组前至少3个月] (tezacaftor-ivacaftor使用),
    NOT [window: 入组前至少3个月] (lumacaftor-ivacaftor使用)
  )

attachment: AND，原文连接词 and also
```

这表达完整窗口内没有发生任一药物使用，而不是NOT(用药持续时间>=3个月)，也不是仅判断当前是否用药。

| 条件 | 原子引用 | 否定与时间范围 | Python结果 |
| --- | --- | --- | --- |
| tezacaftor-ivacaftor | 原文药物名逐字引用 | 独立NOT；lookback；>=3 months；enrollment锚点 | unknown |
| lumacaftor-ivacaftor | 原文药物名逐字引用 | 独立NOT；lookback；>=3 months；enrollment锚点 | unknown |

每个NOT的完整父引用均采用同一段原始共同条款，window引用for at least 3 months。每个原子只引用药物名字，未编造第二次taking，也未拼接来源。四个原子（原式2个、独立式2个）均有op:atom，布尔value均为null，无0/1编码。

enrollment锚点来自完整研究语境和本次要求，孤立末句并没有逐字写enrollment；不声称这一锚点单靠末句字符串就证明了。原文>=3个月、单位及NOT窗口位置均已核验。

## 与v1、v2及上一轮v3对比

| 项目 | v1 | v2 | 上轮v3 | 本轮v4 |
| --- | --- | --- | --- | --- |
| 两药否定 | 合在duration名称里 | 一个NOT(A OR B) | 已有两个独立NOT | 两个独立NOT |
| 原文OR | 藏在原子名称中 | 有显式OR | 保留原式OR及独立AND | 保留原式OR及独立AND |
| 各自时间范围 | 未独立绑定NOT | 组合窗口 | 放在正向原子，源式没有窗口 | 三个NOT均绑定一致窗口 |
| 逐字引用 | 完整句保留 | taking lumacaftor引用非原文 | 引用通过 | 引用通过 |
| 原子op字段 | 原子格式具备但逻辑不完整 | 有 | 四个均缺 | 四个均有atom |
| 本条结构可接受 | 未完成 | 未完成 | 未完成 | 本次通过原核验器 |

这仅反映定向Prompt实验对本条已知缺陷的修复，不是泛化准确率，也不扩展到其他用药窗口或病例。

## 核验、保护与产物

沿用六项专项离线检查全部通过，覆盖未知保留、引用错误、错误时间窗、丢失原OR、缺op、窗口挂错节点。实际候选另外通过完整引用、树结构、独立两药、时间字段一致性和AND连接检查。

10196个受保护文件（生产aitx/config、正式账本、全部baseline、旧HTTP/LLM缓存和前三轮实验文件）SHA全等。正式前后完整status_diff0；相对current的196项既存差异逐项不变：14详情/3状态/18新增/4删除/157缺基线。没有修改正式流程、账本、基线或批准记录。

产物在out/step3b-stop-peds-drug-windows-v4-20261124/：

- messages.json、eligibility-original.txt、plan.json：实际完整输入与参数。
- response.json、parsed.json：本次唯一原始模型回答。
- comparison.json：原核验器结果、两个药物的unknown轨迹和v1/v2原始对象。
- v1-v2-v3-v4-focused.json：四轮仅这两药的原始结构对照。
- v3-vs-v4-model.diff、v3-vs-v4-prompt.diff：上一轮到本次完整结构与Prompt差异。
- quote-audit.json、cost.json、preservation-check.json、execution-state.json：引用、费用、保护和等待审核记录。
- formal-after-vs-before/、formal-vs-current/：完整标准diff。

只报告这一条结构通过，患者实际满足情况仍未知。已停止，等待审核，不扩展其他问题，不补调模型。

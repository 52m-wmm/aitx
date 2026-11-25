# STOP PEDS两种药物否定与窗口：聚焦实验（2026-11-24，待审核）

## 这一条是否正确

**尚不能判为结构正确。原文引用及独立药物拆分已改善，机器可执行的结构和时间作用域仍未通过。**

这次只提取non-HEMT末尾两种药物条款，没有分析其他入组/排除问题。完整EligibilityCriteria原字节作为上下文；模型未收到患者病例。一次真实非高峰deepseek-flash调用，无自动重试。原始候选不改写。

原文：

> and also not taking tezacaftor-ivacaftor or lumacaftor-ivacaftor for at least 3 months

## 逐项核验

| 项目 | 本次结果 |
| --- | --- |
| 原文引用逐字、连续 | 所有quote均为原文连续子串，通过 |
| 两个药物独立识别 | 两个独立NOT，各有自己的药物原子，通过文字识别 |
| 原文OR及否定 | 保留NOT(A OR B)，源式外有单子节点AND包装；未把原文OR直接误换为AND |
| 与前面资格分支的连接 | attachment=all、connector_quote=and also，均有来源支持 |
| 独立等价形式 | 输出AND(NOT(A),NOT(B))，同一窗口下符合德摩根关系 |
| 两药时间字段 | 各有lookback、>=3、months、anchor=enrollment，quote为for at least3 months的原文写法 |
| 时间作用域 | 两个window挂在正向medication原子上，不在约定的NOT节点；源式NOT(A OR B)完全没有window，失败 |
| 原子节点类型 | 源式两个、独立式两个药物节点均缺op:atom，共4处，失败 |
| 患者用药事实 | 未提供，unknown；没有补充服药/停药事实或生成资格结论 |

每个独立药物节点的quote现在只是对应药物名，父NOT引用完整共同条款。两种药物可以共享同一段原文，不必也不允许人工拼出第二句“not taking某药for3months”。这次已消除v2中taking lumacaftor-ivacaftor不是原文的问题。

窗口挂在正向原子上并不自动证明医学逻辑相反：如果另行定义“原子=该窗口内发生用药”，NOT也可表达无使用。但本次约定是NOT节点绑定完整窗口，当前Python没有实现另一套隐式语义；而源式没有任何窗口，不能证明源式与独立式在时间范围上等价。因此不能放行，也没有自动挪动字段或补齐op。

anchor=enrollment为完整试验语境下的解释；孤立末句只有for at least3 months，不逐字包含enrollment。不能把该锚点说成仅通过末句字符串就完全核验成立。患者实际近期用药史仍未知。

## 与v1、v2对比（仅这一条）

| 检查项 | v1 | v2 | 本次聚焦版本 |
| --- | --- | --- | --- |
| 两种药物 | 合在一个duration名称中 | 两个药物在一个OR中 | 两个独立药物NOT |
| 否定 | 藏在名称中，无NOT | NOT(A OR B) | 原式NOT(A OR B)，另给AND(NOT(A),NOT(B)) |
| 引用 | 原完整句保留 | 第二药物补写taking，非逐字 | 所有quote逐字通过 |
| 时间范围 | >=3个月藏在duration原子 | 组合NOT共享窗口 | 各自有>=3个月窗口，但挂错层级；源式缺窗口 |
| 可执行结构 | 未完整表达 | 引用失败 | 缺原子op、窗口作用域未满足约定 |
| 本轮结论 | 未完成 | 未完成 | 部分改善，仍未完成 |

首个严格核验报错为cohort字段使用non-HEMT cohort，而检查器预期ID non-HEMT。该标签语义正确，本身不构成医学错误。没有靠这一标签错误就结束判断：额外只读审计逐条检查了全部引用、4个原子及时间窗，确认上述实质结构缺口。原始回答没有被改名或补字段后冒充模型正确输出。

## Python检查、费用与边界

6项专项离线测试通过：有效独立NOT、未知事实不转确定结论、引文拼接、错误窗口、原OR丢失、缺原子op、窗口挂错节点等核心模式。测试中的人工树不是模型实验结果。真实候选保留unknown，不调用患者比较推断实际服药状态。

实际usage：1097输入（冷缓存1097）、537输出，总1634；按项目非高峰费率$0.00048675。只一次模型调用，没有补调、自动修复候选或扩展其他条件。

10173个受保护文件（生产aitx/config、正式账本、全部基线、旧HTTP/LLM缓存、v1/v2实验文件）SHA完全保持。正式前后完整status_diff0；对current原196项逐项保持：14详情/3状态/18新增/4删除/157缺基线。未写正式账本、基线或批准记录。

产物：out/step3b-stop-peds-drug-windows-20261124/。

- messages.json、eligibility-original.txt、plan.json：实际完整输入和单次调用参数。
- response.json、parsed.json：原始回答，不修改。
- focused-audit.json：全部逐字引用检查、缺op清单、每个药物窗口和作用域检查。
- v1-v2-v3-focused.json：仅两种药物相关的三轮原始结构对比。
- comparison.json：严格核验结果和旧non-HEMT原始对象，未生成患者资格。
- cost.json、execution-state.json、preservation-check.json：费用、停止待审核、保护核验。
- formal-after-vs-before/、formal-vs-current/：完整标准diff。

本轮结束，等待用户审核。不自动补第2次模型请求，不扩展其他问题。

# KMT2B 3a-v6单票初步验证：预算保护停止 v1.0

本次未完成新版Prompt验证。真实请求已停止，未自动追加预算或续跑。只执行授权的新源抽取，未调用上下文核查、同义合并、AGXT或其他Step，未修改临床规则、正式Ledger及Accepted。

## 执行及费用

2026-11-19太平洋时间06:31:43起，非高峰，nohup+caffeinate。执行前DeepSeek账户可用、余额17.71 CNY。仅新版3a-v6系统Prompt替换，四份user来源输入与旧版逐字相同，deepseek-flash、temperature0、原16384输出参数不变；代码/输入SHA在execution_proposal.json冻结。Alias背后权重未独立验证。

| 请求 | 结果 | 已知费用 |
|---|---|---:|
| Management | 完成，0条，与旧版空段一致 | $0.000088302 |
| Treatment of Manifestations | 16384输出tokens处截断，未取得可用行动抽取 | $0.010076004 |
| 必要32768重试 | 请求前被预算拦下，没有发送 | $0 |
| DD/ID、Pregnancy来源 | 未执行 | $0 |

两次真实请求、无响应缓存复用、实际重试0、peak0、usage全部完整，合计 **$0.010164306**。本次$0.03剩余$0.019835694；32768重试需要最大费用预留 **$0.021575200**，超过余额，故停止。不能用预测均价或缓存折扣替代上限预留。截断请求usage显示completion_tokens=16384、reasoning_tokens=16384，没有可用于本轮比较的完整JSON；生产抽取器不缓存截断结果，费用日志保留该请求。不能把截断或未执行当作空行动结果。

KMT2B本阶段累计$0.052796658，仍低于$0.08；旧$0.50实验累计$0.268869501，余$0.231130499。上级余额并不授权突破本次$0.03上限，且本次剩余也不自动授权其他执行。费用以usage计，不以余额接口结算延迟判断。

## 对照结果：尚未测得

| 审阅问题 | 本轮结论 |
|---|---|
| GPi-DBS、subthalamic DBS召回 | 未测；核心来源没有完整响应 |
| 504、DDA、具体辅助器具 | 未测；不得把未执行/截断认作遗漏 |
| 旧42组语义分歧中解决或改善的数量 | 未知；42组逐项标not_tested，不能报告解决0项或42项未改善 |
| chest physical therapy感染风险误抽 | 未测 |
| influenza immunizations感染风险误抽 | 未测 |
| prophylactic antibiotics感染风险误抽 | 未测 |
| 新增、遗漏、范围改变的条件 | 无有效完整比较；未测，不判医学新增/删除 |

comparison.json保留42组原始条件及Evidence ID，并为3个风险案例逐项记录结果null、comparison_valid=false。保留原文，不以旧多数票或本轮缺响应判定医学正确性。完成的唯一空Management段不能证明新版Prompt修复有效或无效。此次既未通过初步验证，也不构成稳定性验收。

## 留存及保护

实验目录runs/kmt2b-v6-one-vote-20261119：四源冻结输入、授权、余额、成功响应、usage、预算预留/结算、停止状态、逐项比较与final_summary.json。停止时sources_completed=1、complete_step3a=false。一次成功响应对应session成功调用记录；费用日志有两次物理请求，不能只数成功缓存记录算费用。

status_diff/since-before完整输出变化0；accepted-current保留既有未升级差异。15份正式Ledger及全部历史/current基线SHA核对不变。没有运行生产组装或修改Evidence ID，没有把临时结果写入临床报告。scripts/compare_kmt2b_v6.py只读已有文件，完整源不足时禁止把缺失当作行动/条件遗漏；不发网络或模型请求。

已停止付费，不自动提高token预算、不改变医学规则来完成本轮。后续如何继续需用户另行安排；本报告不申请扩大预算。

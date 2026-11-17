# 两项试验召回审计（2026-11-17，$0、未调模型）

直接读取 ClinicalTrials.gov 注册记录对应的 API v2，完整响应保存在 `runs/baseline-approved-20261117/NCT*.live.json`，核验汇总见同目录 `live_trials.json`。未修改流水线检索或临床判定，也未覆盖流水线 HTTP 缓存。

| NCT | 当前登记招募状态 | 登记疾病 | 进一步核对 | 结论 |
| --- | --- | --- | --- | --- |
| [NCT01822834](https://clinicaltrials.gov/study/NCT01822834) | RECRUITING | Non-CF Bronchiectasis；Nontuberculosis Mycobacteria (NTM) | 年龄 18–120 岁；排除条款明确为 CF Bronchiectasis | 不是 15 岁 CFTR 病例的召回缺口。历史 CF 缩写查询将 Non-CF 混入。 |
| [NCT07513051](https://clinicaltrials.gov/study/NCT07513051) | RECRUITING | Neonatal Respiratory Distress | 年龄 72 小时–10 周；入组为胎龄 ≤32 周、NICU 中接受 CPAP 的新生儿。关键词包含 CF-CPAP（Constant flow CPAP）。 | 不是 CFTR/囊性纤维化试验，也不是该病例召回缺口；CF-CPAP 可解释缩写噪声。 |

两者“仍招募”不等于与该病例相关。没有证据要求恢复为可报名 CFTR 试验，本轮不改检索逻辑。注册记录最后更新日分别为 2022-03-22、2026-06-23，与本次核验日分开记录，未将旧更新日当成本次核验日。

来源：[NCT01822834 API](https://clinicaltrials.gov/api/v2/studies/NCT01822834)、[NCT07513051 API](https://clinicaltrials.gov/api/v2/studies/NCT07513051)。

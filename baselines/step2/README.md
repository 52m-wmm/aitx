# Step 2 独立稳定性观测基线

当前版本见 `current.json`。`stability-20261118/` 冻结四个练习病例各五次独立真实执行的全部观测，而不是选某次结果为金标准。

验收范围为诊断稳定性；CFTR 第三轮存在已解释的症状抽取/HPO 波动，状态为 `diagnostic_stability_pass_with_documented_extraction_variability`。不代表症状提取完全一致或已证明整体准确率。

生产代码、Prompt、参数、数据及实验产物哈希见 manifest，完整结果路径见验收文档 `docs/step2_stability_acceptance_20261118.md`。本目录与行动账本的 `baselines/current/` 分开，未替换正式 Step 2 输出；后续版本应另建目录，保留本次全部观测。

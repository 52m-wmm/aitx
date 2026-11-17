# Baseline approvals

2026-11-17 初始化：按用户本轮明确指示，`current/snapshot.json` 与
`historical/step3a.2-accepted/snapshot.json` 字节完全一致。
这只是历史基线的复制，**不批准当前账本中的任何变化**，没有执行升级。
历史版本覆盖现有 15 例中的 11 例，4 例 RETEST 尚未存在，明确记为缺少历史基线。

后续升级必须由用户逐条批准 diff 后执行 `scripts/promote_baseline.py`。
脚本在此追加日期、提交号、批准人、总体理由及每条变化的批准清单与理由，保留已有记录。
尚无升级记录。

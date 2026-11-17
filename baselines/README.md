# 状态基线（v1）

- `historical/step3a.2-accepted/snapshot.json`：从真实历史验收存档生成，保留来源提交、存档 manifest 摘要和逐病例账本 SHA-256；只读，永不覆盖。
- `current/snapshot.json`：默认比较基线。本轮仅初始化为 historical 的逐字副本，不含对当前账本变化的认可。
- `approvals.md`：只追加升级批准记录。账本自己给出的 reason 不等于合理解释或用户批准。

对象固定为 11 个练习病例（DMD 按已批准决定延期）与 4 个 RETEST，共 15 例；不读取评测病例的 Step 3。
历史基线只有 11 例；4 个 RETEST 的旧状态不存在，不能替换为 unknown、applicable 或 not_applicable。
工具将其列为 `baseline_missing`，并保留完整当前快照，供后续 15 例比较使用。

## 修改前后运行

```sh
.venv/bin/python scripts/status_diff.py --output-dir out/status_diff/before-change
# 修改账本 / 判定代码、通过离线测试，再按已批准范围缓存重生成账本
.venv/bin/python scripts/status_diff.py --output-dir out/status_diff/after-change
# 可同时比较改前版本，但不能代替对 current 的必需比较
.venv/bin/python scripts/status_diff.py --compare out/status_diff/before-change/snapshot.json --output-dir out/status_diff/before-vs-after
```

每次输出 `snapshot.json`、`diff.json`、`diff.md`。默认比较 current；
指定 `--compare step3a.2-accepted` 可单独比较历史基线。
每行按病例、章节、稳定行动键、诊断分支匹配；无结果记录按章节区分。
同一键有多条账本记录时保留所有状态与证据，不覆盖、不擅自合成适用结论。
既无适用等级又明确为 hypothesis 的记录标为 ungraded；没有分配分支的记录保留 branch=null，二者都不是病人不适用。
新增 / 删除、状态、原因、证据 ID、合并记录数和名称变化均列出。
`needs_review` 表示待调查，不因为存在账本理由就自动认可；无法解释的变化视为潜在缺陷。

## 批准与升级

用户逐条审核实际 diff 后，建立批准文件。下例仅说明格式，`approved: false` 无法升级：

```json
{
  "date": "2026-11-17",
  "commit": "完整的当前 HEAD 提交号",
  "approver": "实际批准人",
  "reason": "用户批准本次升级的总体理由",
  "baseline_sha256": "diff.json 中的 baseline_sha256",
  "candidate_sha256": "diff.json 中的 candidate_sha256",
  "approved_changes": [
    {"change_id": "diff.json 中逐条列出的 change_id", "approved": false, "reason": "逐条批准理由"}
  ]
}
```

只有明确获得对应批准后才能填入 `approved: true`，不得由代理自行批准。然后运行：

```sh
.venv/bin/python scripts/promote_baseline.py --candidate out/status_diff/after-change/snapshot.json --approval path/to/approval.json
```

脚本重新计算 diff，要求每个 change_id 精确覆盖且逐条批准，校验基线 / 候选 SHA-256、提交号、批准人和理由。
验证失败不会修改 current 或批准记录。先追加批准记录，再原子替换 current；历史目录从不写入。
未获批准的变化不得进入 current，不运行 promote 来掩盖回归。

2026-11-17 首次部分升级已按用户审核完成：A 5、B 5、D 11，及 E 的 124 个后续步骤新增、2 个 hypertonic saline 键规范化、4 个 over_cap 记录，共 151 项。current 为明确批准行组成的复合快照（529 行），不是某一次完整账本的逐字替代；provenance 和 approved_live_component 保留来源。C、61 项证据细节、其他未批准新增/删除及 RETEST 首个基线均未纳入。完整批准清单见 approvals.md；后续修复仍须对这个新 current 出 diff。

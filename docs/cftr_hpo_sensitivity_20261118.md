# CFTR 泛化 HPO 缓存实验 — 2026-11-18

**真实 LLM 调用 0、费用 $0。** 已把 Step 2 第3轮完整结果（HP:0005425→HP:0002719）送入隔离的 Step 3，固定代码和同一份外部响应。正式 CFTR 账本、Step 2 输出、规则和 Accepted Baseline 均未改。

正常输入的完整缓存回放与正式账本在 status_diff.py 中差异为 0；因此后续 Diff 不混入代码升级的旧变化。

## 可测结果

对两次回放共有行动的非上下文条件，逐一比较 requirement、patient_fact、patient_status、result：**没有发现因本次 HPO 泛化而改变的确定性条件/适用结果**。疾病分支相同；3b、3d、3e 的本次可比较结果无变化。未将未知认作满足或不满足。

这不代表端到端稳定：上下文核查把整个病人摘要放入请求，HPO/描述变化使大量请求键变化，不能借用旧票。

## 未测部分与原始 Diff

- **132 组 3a 上下文核查**缺新输入对应缓存，明确记录 not tested，不生成替代票。相关 **51 个行动×分支**在隔离比较中标为未测，保存了核查前的确定性暂定结果；这些不是“有条件→适用”或临床状态变化。
- **3c 首个新上下文核查缺缓存**，该步骤未完成；临时账本少了 tobramycin、Prolastin、riociguat 三项。这三项是未测/未生成，不是确认删除、撤回或不适用。
- status_diff.py 原始输出为 **51 项状态→not_tested、3 项行动缺失**，均由未测机制产生，不能报成54项HPO导致的真实变化，也不能据此升级基线。

当前能确认的只是可比较确定性条件未变；需真实核查才能判断其余部分。CFTR 两次独立真实 Step 3 仍暂缓，未动用任何付费额度。

## 产物

- `runs/step3-stability-20261118/cftr-normal/`：正常输入完整缓存回放、输入、原文和请求盘点。
- `runs/step3-stability-20261118/cftr-generalized/`：泛化输入、未测核查明细、临时结果及每步完成情况。临时结果的 not_tested 是实验覆盖标记，不是生产 Ledger 的适用分类，不可发布为正式账本。
- `runs/step3-stability-20261118/cftr_condition_changes.json`：确定性条件比较清单（空列表）。
- `out/status_diff/stability-followup-20261118/cftr-hpo-sensitivity/{snapshot.json,diff.json,diff.md}`：两输入完整原始对比；对应 `cftr-normal-current/` 和 `cftr-generalized-current/` 为对 Accepted current 的全量输出，原有待审变化与本次实验标记必须分开。

没有改变临床规则、自动修复、补写证据或升级任何 Accepted Baseline。

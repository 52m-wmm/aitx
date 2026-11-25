# 隔离实验与历史回放

本索引按当前磁盘文件更新（2026-11-25）。Step 3 尚在开发；新 3a 来源选择到 Ledger 的适配未完成，不能运行完整 Step 3。

这些脚本保留隔离实验和重放用途；存在文件不表示已有运行授权。历史预算不延续。旧冻结记录中的路径属于当时版本，需配合其源码快照，不改写 runs、缓存或基线中的历史记录。

| 文件 | 用途 |
|---|---|
| [migrate_current_keys_offline.py](migrate_current_keys_offline.py) | User-authorized offline key-only baseline mapping; never copies live clinical fields. |
| [regress_action_key_switch.py](regress_action_key_switch.py) | Exact 15-case key-only offline regression against migration backups; no APIs. |
| [rescreen_molecular_targets.py](rescreen_molecular_targets.py) | Recheck saved candidate studies with the approved single-target rule; no API or LLM calls. |
| [retest_report.py](retest_report.py) | Review sheet for the retest batch (fix-phase retest, 2026-11-12). Reads ledgers and the machine check; no LLM. |
| [step3b_conflict_screening_mvp.py](step3b_conflict_screening_mvp.py) | Independent Step 3b screening comparison; default is prepare-only, --run makes paid calls. |
| [switch_action_keys.py](switch_action_keys.py) | Apply approved key aliases with complete backups and exact inverse regression; no APIs. |

旧3b逐条映射回放及STOP PEDS结构实验运行器已随生产重构退役。原源码、专属测试和删除清单保存在 `out/step3b-rebuild-20261125/before/` 与 `retired.json`；历史输入/模型回答/审阅结果未删除。

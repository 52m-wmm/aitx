# 隔离实验与历史回放

本索引按当前磁盘文件更新（2026-11-25）。Step 3 尚在开发；新 3a 来源选择到 Ledger 的适配未完成，不能运行完整 Step 3。

这些脚本保留隔离实验和重放用途；存在文件不表示已有运行授权。历史预算不延续。旧冻结记录中的路径属于当时版本，需配合其源码快照，不改写 runs、缓存或基线中的历史记录。

| 文件 | 用途 |
|---|---|
| [apply_trial_enrollment_notes.py](apply_trial_enrollment_notes.py) | Offline note-only replay of the 15 saved ledgers; writes a new review directory, never a baseline. |
| [apply_trial_subject_review.py](apply_trial_subject_review.py) | Offline subject correction and source-proven cohort OR; preserve saved body extraction and IDs. |
| [migrate_current_keys_offline.py](migrate_current_keys_offline.py) | User-authorized offline key-only baseline mapping; never copies live clinical fields. |
| [regress_action_key_switch.py](regress_action_key_switch.py) | Exact 15-case key-only offline regression against migration backups; no APIs. |
| [rescreen_molecular_targets.py](rescreen_molecular_targets.py) | Recheck saved candidate studies with the approved single-target rule; no API or LLM calls. |
| [retest_report.py](retest_report.py) | Review sheet for the retest batch (fix-phase retest, 2026-11-12). Reads ledgers and the machine check; no LLM. |
| [step3b_conflict_screening_mvp.py](step3b_conflict_screening_mvp.py) | Independent Step 3b screening comparison; default is prepare-only, --run makes paid calls. |
| [stop_peds_drug_windows.py](stop_peds_drug_windows.py) | One focused STOP PEDS medication-negation experiment with full source context. |
| [stop_peds_full_context.py](stop_peds_full_context.py) | One STOP PEDS full-context experiment. No production imports are modified or outputs published. |
| [stop_peds_nonhemt_not.py](stop_peds_nonhemt_not.py) | STOP PEDS NOT v2: one full-context request, offline comparison, no production writes. |
| [switch_action_keys.py](switch_action_keys.py) | Apply approved key aliases with complete backups and exact inverse regression; no APIs. |

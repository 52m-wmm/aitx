# 运行入口与工具

本索引按当前磁盘文件更新（2026-11-25）。Step 3 尚在开发；新 3a 来源选择到 Ledger 的适配未完成，不能运行完整 Step 3。

当前入口：run_pipeline.py（Step 1/2）、run_step3a.py（独立来源选择）、refresh_step3b.py（已有账本的 3b 局部刷新）、viewer_app.py（查看）、build_report.py / validate_report.py（已有账本报告）。

[隔离实验与历史回放](experiments/README.md) 单独列出。

| 文件 | 用途 |
|---|---|
| [acceptance_eval_cases.py](acceptance_eval_cases.py) | Acceptance expectations that are written against the four evaluation cases (--eval only). |
| [acceptance_step1.py](acceptance_step1.py) | Online acceptance test for step 1 (run where NCBI is reachable). |
| [acceptance_step2.py](acceptance_step2.py) | Online acceptance test for step 2 (needs network and AITX_LLM_API_KEY). |
| [acceptance_step3_0.py](acceptance_step3_0.py) | Online acceptance for step 3.0 (evidence ledger skeleton; contract docs/step3_0_contract.md, section 9). |
| [acceptance_step3b.py](acceptance_step3b.py) | Step 3b acceptance (docs/step3b_contract.md, 验收): verified expectations vs the step 3 ledgers in out/step3. |
| [acceptance_step3c.py](acceptance_step3c.py) | Step 3c acceptance (docs/step3c_contract.md): verified expectations vs the step 3 ledgers. No LLM, no network. |
| [acceptance_step3d.py](acceptance_step3d.py) | Step 3d acceptance (docs/step3d_contract.md): verified expectations vs the 3d rows in out/step3. |
| [acceptance_step3e.py](acceptance_step3e.py) | Step 3e acceptance (docs/step3e_contract.md): verified expectations vs the 3e rows in out/step3. |
| [analyze_step2_stability.py](analyze_step2_stability.py) | Report all pre-registered runs without choosing a favourable result. |
| [analyze_step3_stability.py](analyze_step3_stability.py) | Offline complete/partial Step 3 comparisons; never promotes a baseline. |
| [audit_code_usage.py](audit_code_usage.py) | Conservative AST reference inventory; no imports/execution of the analysed code. |
| [blind_machine_check.py](blind_machine_check.py) | Machine judging for a blind-test batch (docs/blind_test_plan.md section 3). Deterministic, no LLM. |
| [build_blind_cases.py](build_blind_cases.py) | Turn out/blind/<batch>/sample.json into a case file the pipeline can run. Deterministic, no LLM. |
| [build_report.py](build_report.py) | Step 4: build reports from the ledgers (contract docs/step4_contract.md v1.0). No LLM. |
| [build_step3b_experiment_view.py](build_step3b_experiment_view.py) | Export one completed experiment for the viewer. Never runs screening or writes ledgers. |
| [build_viewer.py](build_viewer.py) | Case Viewer and static export for Steps 1–5, with Step 3a source selection. |
| [draft_rules.py](draft_rules.py) | Draft gene-specific rules for every gene in the step 2 results (step 3.0 contract, section 4). |
| [dry_run_quote.py](dry_run_quote.py) | Quote a rerun from the LLM cache alone (no paid call, nothing written to out/). 2026-11-12. |
| [eval_extraction.py](eval_extraction.py) | Symptom extraction test set: precision / recall of step-2 phenotype extraction. |
| [eval_support_check.py](eval_support_check.py) | Regression set for the support check (aitx/evidence/support_check.py). |
| [import_step3a_result.py](import_step3a_result.py) | Archive an already reviewed source-selection result into the viewer's standard output directory. |
| [llm_cost.py](llm_cost.py) | LLM token use and cost from runs/llm_calls.jsonl (every real call is logged there with its usage). |
| [promote_baseline.py](promote_baseline.py) | Promote an explicitly approved candidate; never alter historical baselines. |
| [public_cache_fill.py](public_cache_fill.py) | Missing-only requests for approved free public APIs; never refresh existing cache files. |
| [recheck_rules.py](recheck_rules.py) | Run the support check again on rules whose conditions were narrowed by hand, without redrafting them. |
| [refresh_step3b.py](refresh_step3b.py) | Refresh formal Step 3b while preserving the saved outputs of the other Step 3 sections. |
| [run_blind_batch.sh](run_blind_batch.sh) | zsh 批处理入口；调用主流水线，包含时间与预算保护。 |
| [run_pipeline.py](run_pipeline.py) | Run the pipeline end to end, or restart from any step using earlier outputs on disk. |
| [run_practice_rerun.sh](run_practice_rerun.sh) | zsh 批处理入口；调用主流水线，包含时间与预算保护。 |
| [run_step3a.py](run_step3a.py) | Prepare/run the source-selection Step 3a backend without running other pipeline steps. |
| [sample_blind_cases.py](sample_blind_cases.py) | Draw the blind-test cases (docs/blind_test_plan.md). Deterministic, no LLM. |
| [sample_retest_cases.py](sample_retest_cases.py) | Draw and build the retest cases (fix-phase retest, user decision 2026-11-12). Deterministic, no LLM. |
| [status_diff.py](status_diff.py) | Offline action x branch snapshots. Never writes a baseline; promotion requires explicit approvals. |
| [step1_variant.py](step1_variant.py) | Step 1 CLI: patient case JSON -> VariantProfile JSON. |
| [step2_disease.py](step2_disease.py) | Step 2 CLI: patient case JSON -> DiseaseResolution JSON. |
| [step2_stability.py](step2_stability.py) | Independent Step 2 experiment; production rules and outputs remain untouched. |
| [step3_preflight.py](step3_preflight.py) | Offline dependency audit of saved Step 3 extractions. Never invokes a model. |
| [step3_stability.py](step3_stability.py) | Isolated Step 3 refresh, cache sensitivity, and cache-only quote inventory. |
| [step3a_view.py](step3a_view.py) | 兼容导入入口；正式3a渲染在 aitx/viewer/step3a.py。 |
| [step3b_view.py](step3b_view.py) | Read-only clinical trial view of saved Step 3 ledgers; no analysis or network. |
| [tag_accepted.py](tag_accepted.py) | Tag an accepted version and archive the results it was accepted on. |
| [validate_report.py](validate_report.py) | Step 5 deterministic report checks. No LLM or network. Run: --case PRAC-AGXT-c33dup. |
| [viewer_app.py](viewer_app.py) | Local review web app: the Step 2.5 pages rendered live from out/, with reruns. |

Step 3 实现在 `aitx/step3/a/`、`aitx/step3/b/`，总编排在 `aitx/step3/pipeline.py`。本次目录迁移保留上述命令及参数，3c/3d/3e 与共享模块暂留 `aitx/evidence/`。

### 3a 数据保存与当前批次

- 批次原始资料与运行结果保存到 `runs/step3a/<病例ID>/<批次ID>/`。现有两份 OTC 批次已迁入，文件内容不变；内部历史路径作为当时运行记录保留。
- 页面自动展示最新批次：已执行批次按首个请求时间排序，尚未执行的准备批次按 plan.json 修改时间排序。`out/current.json` 仅保留为命令行默认操作批次，不影响页面。
- `prepare --case-id ... --cases ... --xml ...` 默认新建 UTC 时间戳批次，也可显式指定 `--output`。新准备批次自动出现在页面，明确标注尚未执行。
- `python scripts/run_step3a.py select --case-id PRAC-OTC --batch PRAC-OTC-rerun-c4-20261125` 指定命令行默认操作批次；页面仍自动显示最新批次。
- `recover --case-id ...`、`run --case-id ...` 使用当前索引；仍支持显式 `--output`。真实执行需要既有预算授权。完成批次的离线恢复直接返回，保留文件；重跑须创建新批次。
- 本轮仅整理 3a。3b、正式账本、历史实验及 `.cache/datasets/` 暂留原位，不清理 HTTP/LLM 缓存。

页面 Step 1/2 直接读取当前结果；3b 比较当前账本与导出结果的保存时间；3c–3e 展示当前账本的保存记录；Step 4 展示当前报告，Step 5 若无保存结果明确未知。页面文件监听包含报告 Markdown；最新保存不代表已按最新上游重算或审核通过。

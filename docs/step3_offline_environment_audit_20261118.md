# Step 3 $0 测试环境审计 v1.0 — 2026-11-18

## 结论

四次历史中断均可由原始回答及冻结HTTP响应离线复现。不是FDA返回了临床否定结果，而是请求的响应根本不在夹具中。真实调用0、费用$0；原独立实验累计$0.216072843，剩余$0.283927157保留，不重启付费执行。临床规则和Accepted Baseline未改。

## 完整调用链及四次中断

`step3_stability.main → pipeline.add_established（导入的established实现）→ established.add_established → actions.drug_key → strip_dose/strip_abbrev → rxnorm_ingredients → _json → fixed_http`：RxNav已缓存，返回无匹配；继而 `openfda_generic → _json → fixed_http` 请求新FDA品牌URL，抛出FixedInputMissing。异常未被_json的RuntimeError/ValueError捕获，终止3a。完整原始Traceback保存在各preflight.json的original_call_chain中。

`drug_key`后续还有generic→RxNorm、逐成分RxNorm、ChEMBL、文本fallback路径；本次在FDA缺口处停止，不能假定更后面的依赖已覆盖。FDA在这条链上用于品牌归一化，不代表已完成说明书安全检查。

| 病例/轮次 | 模型原始名称 | RxCUI | FDA缓存Key |
|---|---|---|---|
| PRAC-AGXT-c33dup / 1 | vitamin C intake exceeding recommended daily allowance | 无匹配 `[]` | `cbf9383b42616e2c0a38fee8db4b7f09240535013bd6b76b2ac1c7b99d2504af.json` |
| PRAC-AGXT-c33dup / 2 | high doses of nonsteroidal anti-inflammatory drugs (NSAIDs) or any pharmacologic agent that can compromise kidney function | 无匹配 `[]` | `f4ffd9d7d5a716f324cd28da604f123336f0487d0d1414d5711be4adf35fd5e5.json` |
| PRAC-KMT2B / 1 | trixhexyphenidyl | 无匹配 `[]` | `23e8489723cf5b6497eb0fca7c9f63b784b652339bb2e7304b25a712207e2b58.json` |
| PRAC-KMT2B / 2 | trixhexyphenidyl | 无匹配 `[]` | `23e8489723cf5b6497eb0fca7c9f63b784b652339bb2e7304b25a712207e2b58.json` |

每条原始LLM缓存Key、RxNav缓存Key、完整查询URL、来源段落和返回匹配ID，均在下列逐次清单中：

### PRAC-AGXT-c33dup / 1
- 原始响应Key：`e8df158345ef2b33ee738529e42483426debb0e55c00b2b8384061aaf38ca8d0`
- RxNav URL：`https://rxnav.nlm.nih.gov/REST/rxcui.json?name=vitamin+C+intake+exceeding+recommended+allowance&search=2`
- RxNav Key：`c630890de29f1904b2162c1ccf67e548a98cae9512b8b24e39ad355aa2f67e09.json`
- FDA URL：`https://api.fda.gov/drug/label.json?search=openfda.brand_name%3A%22VITAMIN+C+INTAKE+EXCEEDING+RECOMMENDED+ALLOWANCE%22&limit=1`
- FDA Key：`cbf9383b42616e2c0a38fee8db4b7f09240535013bd6b76b2ac1c7b99d2504af.json`

### PRAC-AGXT-c33dup / 2
- 原始响应Key：`e8df158345ef2b33ee738529e42483426debb0e55c00b2b8384061aaf38ca8d0`
- RxNav URL：`https://rxnav.nlm.nih.gov/REST/rxcui.json?name=high+doses+of+nonsteroidal+anti-inflammatory+drugs+or+any+pharmacologic+agent+that+can+compromise+kidney+function&search=2`
- RxNav Key：`7b4e930933a60b11f803db0f53db80b5fdddd1169172025079df8d536a17e1af.json`
- FDA URL：`https://api.fda.gov/drug/label.json?search=openfda.brand_name%3A%22HIGH+DOSES+OF+NONSTEROIDAL+ANTI-INFLAMMATORY+DRUGS+OR+ANY+PHARMACOLOGIC+AGENT+THAT+CAN+COMPROMISE+KIDNEY+FUNCTION%22&limit=1`
- FDA Key：`f4ffd9d7d5a716f324cd28da604f123336f0487d0d1414d5711be4adf35fd5e5.json`

### PRAC-KMT2B / 1
- 原始响应Key：`3f1738d1010e7749578e63da8b32d5f5111d4b77f04af5d6274a638222cac5b0`
- RxNav URL：`https://rxnav.nlm.nih.gov/REST/rxcui.json?name=trixhexyphenidyl&search=2`
- RxNav Key：`13c7619b9e4034e302d0404315d4c097f8bdb3ca9e3508ed05153135f15b135b.json`
- FDA URL：`https://api.fda.gov/drug/label.json?search=openfda.brand_name%3A%22TRIXHEXYPHENIDYL%22&limit=1`
- FDA Key：`23e8489723cf5b6497eb0fca7c9f63b784b652339bb2e7304b25a712207e2b58.json`

### PRAC-KMT2B / 2
- 原始响应Key：`3f1738d1010e7749578e63da8b32d5f5111d4b77f04af5d6274a638222cac5b0`
- RxNav URL：`https://rxnav.nlm.nih.gov/REST/rxcui.json?name=trixhexyphenidyl&search=2`
- RxNav Key：`13c7619b9e4034e302d0404315d4c097f8bdb3ca9e3508ed05153135f15b135b.json`
- FDA URL：`https://api.fda.gov/drug/label.json?search=openfda.brand_name%3A%22TRIXHEXYPHENIDYL%22&limit=1`
- FDA Key：`23e8489723cf5b6497eb0fca7c9f63b784b652339bb2e7304b25a712207e2b58.json`

## 区分抽取变化、归一化变化和覆盖不足

1. AGXT：历史原始抽取为“Intake of vitamin C that exceeds the recommended daily allowance”，新抽取为“vitamin C intake exceeding recommended daily allowance”；strip_dose按既有规则去掉daily。另一次把NSAID注意事项与“any pharmacologic agent…”合为一个name。属于同源文本的命名/粒度变化，不足以证明临床行动新增。
2. KMT2B：历史同提示抽取trihexyphenidyl，新两次为trixhexyphenidyl；后者确实出现在Pregnancy Management来源。是抽取拼写差异，不是本轮归一化算法变更，也不自动认定模型幻觉。归一化先于孕期独立项过滤，故最终可能只应作附注的候选仍先触发查询。未修拼写或改变过滤规则。
3. 四次实际中断对应3个唯一FDA查询；另查出AGXT第1次中后续候选“pharmacologic agent that can compromise kidney function”的第4个唯一查询缺失。共5条候选记录、4个唯一URL。全部是夹具未收录该精确URL，不是已缓存的404，也未伪造空响应。
4. 初步按所有drug/avoid候选保守扫描得到14条；按真实分支仅drug或Agents/Circumstances to Avoid段的avoid收窄后为5条。其余9条不符合这处归一化入口，不能当真实阻断。quote修复和后续来源范围过滤仍未模拟，故清单是入口依赖检查，不是最终收集行动集合。

## 拟修方案及本轮已实施的环境工具

- 新建scripts/step3_preflight.py，逐条回放保存的模型回答，把原始候选按生产入口送入真实drug_key，GET/POST仅能取指定快照和campaign/http。缺一项即记录incomplete，继续审计其他候选；命令最终退出2，付费执行不得以此作为就绪。已有404照原错误回放，不与缺缓存混淆。
- 同时封锁llm.chat、urllib.request.urlopen、socket连接，禁止隐式API调用；没有source环境变量、余额查询或任何版本联网。回放不刷新过期响应，不读取共享HTTP新数据，不写原夹具。历史LLM共享缓存仅用于只读同提示对照，不作为独立运行。
- scripts/step3_stability.py在每个已接受模型回答返回后、任何归一化之前，立即写raw_extractions/<key>.json：原始响应、Prompt、解析内容及模型已有分类字段原样保存，complete=false、safety_validation=incomplete。3a目前只产kind（drug/avoid等），没有最终临床classification时明确未生成，不从kind臆造。分类若存在会原样保留。
- 任一阶段异常退出在finally写incomplete.json与现有checkpoint，不生成result.json；后续比较仅能比较raw字段，不算完整Step3。四次历史回答已补导出到新审计目录，原实验目录未改。
- 不修改临床判定或跳过FDA；不靠捕获缺缓存后返回空对象让流程继续。旧实验manifest保留不改，脚本更新后任何未来执行必须重新冻结实验工具版本。

## Preflight边界及后续门禁设计

已知候选：开始任何付费运行前，用历史回答和固定HTTP夹具执行此Preflight；当前失败，应保持停止。后续若另获授权补齐夹具，重新冻结并再次检查，不能只补报错的第一个URL。
未知候选：模型名称输出是开放集合，单靠运行前检查不可能证明全部未来依赖已覆盖。应先持久化新的抽取回答，再做依赖门禁，缺缓存就留下原始比较结果并停止安全/下游阶段；不要为绕过门禁改临床规则。该限制需在重新运行方案中先明确，当前没有声称能保证四次完整完成。
完整3b–3e依赖：本轮没有生成这些阶段的新输出，因此该工具不证明其缓存完备。原固定HTTP保护继续逐请求抛错。若未来要保证端到端不因新输出缺响应而停止，需要明确封闭候选及完整依赖快照范围；这可能改变实验定义，须另行审阅，本轮未实施。

## 离线验证

- 历史四次停止URL全部复现并核对RxNav无匹配、FDA Key；5条候选依赖缺口，Preflight退出2（正确阻止开跑）。
- 回归测试覆盖真实drug_key缺FDA、已有FDA404后继续ChEMBL、原始分类保留、urllib/socket/LLM禁止访问。
- 测试及最终保护文件哈希另见审计目录；完整Step3仍0/4，临床稳定性仍未测。

复现命令（输出目录必须新建）：
```sh
.venv/bin/python scripts/step3_preflight.py --campaign runs/step3-staged-050-v3-20261118 --out runs/step3-offline-audit-new
```

产物：runs/step3-offline-audit-v2-20261118/summary.json、各病例/轮次preflight.json及raw_extractions/；assertions.json给出四次核对结果，protected_sha256.json保存正式输出和全部基线的哈希。

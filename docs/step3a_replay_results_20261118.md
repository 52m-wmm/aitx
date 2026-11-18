# Step 3a 四次原始回答回放与报价 v1.0 — 2026-11-18

## 执行边界与结论

实际模型调用0、模型费用$0，剩余$0.283927157未动。使用指定审计目录四份独立raw_extractions，不挑选回答；原生产3a抽取后归一化、来源组装、条件计算、孕期过滤路径未改，不运行3b–3e。正式输出和全部基线114份文件哈希不变。

四次均走到3a组装末端，但各缺1次同义项合并模型响应。实验只保留未合并的候选清单并标记incomplete，不伪造合并答案。上下文缺缓存时只保留生产代码得出的确定性条件，最终状态标待核查；不得当成完整Step3a通过。历史已命中的核查照原缓存使用；缺票从不冒充一致。缺少合并可能改变后续核查Prompt与条目数量，所以本次数量/报价不是将来调用数承诺。

## 分三类统计

单位是审计对齐后的“行动组”；同一行动的文字/键与条件同时变化时归第三类，避免重复计数。2→1的注意事项合并算一组。第三类包含抽取条件文本/结构、原始kind和确定性状态的差异，尚未核查，不是获确认的临床状态改变。仅语法变化（If、Persons w/、诊断名重复等）在同源引文支持下人工归第一类，该对齐清单只用于本报告，未写入临床规则。

| 回放 | 收集行动数 | 仅措辞/键表示差异 | 行动记录增减 | 状态/条件/类型差异（待核查） |
|---|---:|---:|---|---:|
| PRAC-AGXT-c33dup × 1 | 21 | 10 | +0 / −2 | 1 |
| PRAC-AGXT-c33dup × 2 | 22 | 6 | +0 / −0 | 5 |
| PRAC-KMT2B × 1 | 20 | 0 | +1 / −2 | 9 |
| PRAC-KMT2B × 2 | 21 | 0 | +0 / −0 | 9 |

召回差异及原因：
- AGXT第1次：high oral fluid intake、intravenous fluids被新回答列为kind=therapy；生产受控词表不认这两种therapy，过滤后缺失。这是清单真实缺项，不是改名；未修规则。
- KMT2B第1次：adaptive aids新增，原ankle-foot orthoses和walkers未单列。属于收集粒度由具体器具变为总称；记录层面+1/−2，不证明临床治疗范围真有新增。
- AGXT第2次NSAID和任何影响肾功能药物由两项合成一项，按同源注意事项对齐到一组，不冒充一增两删。
- influenza immunizations由drug变procedure，两次均列第三类类型差异，临床行动本身没有消失。

有意义的待核查变化样例：
- AGXT第1次胃造瘘：Infants or small children → Small children，婴儿范围丢失。
- AGXT第2次腹膜透析：新增oxalosis条件，确定性applicable→conditional；pyrophosphate又把calcium oxalate crystal formation放进表现条件，IV fluid新增重复呕吐/腹泻条件，均未核查，未修规则。
- KMT2B两次多种康复条目新增Developmental Delay / Intellectual Disability、IEP前提；speech-language therapy确定性applicable→conditional，第2次walkers/ankle-foot orthoses也新增ambulation条件。这些是抽取范围差异，不把缺核查引起的not_tested转换算临床回归。

完整逐项旧/新条件、确定性状态及分类依据在analysis.json的changes；各次actions.md为行动列表，replay.json含引文/Evidence IDs/条件。status_diff.py同时输出对当前正式账本的canonical比较、对Accepted current的current比较，路径out/status_diff/step3a-replay-v2-20261118/<case>/<round>/{canonical,current}/。pending状态、证据文字/ID变化均原样保留；不能把这些工具原始计数当成上表已解释分类。

## 因措辞或归类改变action_key的条目

| 回放 | 原key | 新key |
|---|---|---|
| PRAC-AGXT-c33dup/1 | `drug:name:pyrophosphate-containing solutions` | `drug:rxcui:1364533` |
| PRAC-AGXT-c33dup/1 | `supportive_measure:foods_high_in_oxalate` | `supportive_measure:large_intake_of_foods_high_in_oxalate` |
| PRAC-AGXT-c33dup/1 | `supportive_measure:pharmacologic_agents_that_can_compromise_kidney_function` | `supportive_measure:pharmacologic_agent_that_can_compromise_kidney_function` |
| PRAC-AGXT-c33dup/1 | `supportive_measure:intake_of_vitamin_c_that_exceeds_the_recommended_daily_allowance` | `supportive_measure:vitamin_c_intake_exceeding_recommended_daily_allowance` |
| PRAC-AGXT-c33dup/2 | `procedure:intravenous_fluids` | `procedure:iv_fluid` |
| PRAC-AGXT-c33dup/2 | `supportive_measure:nonsteroidal_anti_inflammatory_drugs_nsaids`; `supportive_measure:pharmacologic_agents_that_can_compromise_kidney_function` | `supportive_measure:high_doses_of_nonsteroidal_anti_inflammatory_drugs_nsaids_or_any_pharmacologic_agent_that_can_compromise_kidney_function` |
| PRAC-AGXT-c33dup/2 | `supportive_measure:foods_high_in_oxalate` | `supportive_measure:large_intake_of_foods_high_in_oxalate` |
| PRAC-KMT2B/1 | `drug:name:influenza immunizations` | `procedure:influenza_immunizations` |
| PRAC-KMT2B/2 | `drug:name:influenza immunizations` | `procedure:influenza_immunizations` |

pyrophosphate是原制剂措辞与成分键的差异，待确认是否允许等同整个制剂；本报告仅以同一源行作比较对齐，未据此修改身份键或临床适用性。其他大小写/同key措辞变化也在changes中。

## 免费公共接口与失败记录

已知4个唯一openFDA URL均已实际请求，返回404，响应错误存于首次回放目录下本地http及public_requests.json；两次KMT2B查询同一个URL，因此共5次FDA请求。随后AGXT两次出现新的ChEMBL查询，但请求失败、没有可用响应。第二轮记录了完整失败类型；不是查无药物。生产_json会捕获这类RuntimeError并继续文本fallback，实验保留此行为但明确为归一化未确认，所有候选仍incomplete。没有伪造ChEMBL阴性记录。

当前可复核的完整公共请求/失败历史在runs/step3a-replay-v2-20261118/<case>/<round>/public_history.json；合并后的本地http保存FDA记录和ChEMBL失败记录。首次探索曾未记录被生产_json吞掉的部分ChEMBL失败，不能给出它们准确重试/网络次数；已说明并用第二轮显式日志补足可复核结果，没有额外模型费用。正式HTTP缓存未写入，D.ensure使用冻结数据版本，不刷新已有文献或说明书。

## 待核查报价（未执行）

| 回放 | 未缓存上下文请求 | 同义合并请求 | 历史均价估算 |
|---|---:|---:|
| PRAC-AGXT-c33dup/1 | 45 | 1 | $0.02450 |
| PRAC-AGXT-c33dup/2 | 42 | 1 | $0.02305 |
| PRAC-KMT2B/1 | 51 | 1 | $0.02740 |
| PRAC-KMT2B/2 | 45 | 1 | $0.02450 |

合计183次上下文请求（61组三票）+4次合并=$0.09945，约$0.10，重试/合并后新Prompt或后续limit检查另计。跨回放按完全相同Key去重为156次上下文+4合并，约$0.08642；共享补齐缓存属于回放补核查，不能称为四次独立真实稳定性。

报价依据：同官方deepseek-flash历史真实usage，context-check-v3最近200份均价$0.00048246/请求；3a-v5现有69份均价$0.00279004/请求，按既定非高峰费率重算。样本、时间、来源逐项在analysis.json/cost_samples。只返回模型别名，权重版本仍不可独立证明。请求预算预留不是估价：逐请求按max_tokens最大费用保留，不能把所有预留简单相加当作实际成本。

## 下一阶段3a独立稳定性方案，等待批准

推荐KMT2B ×2次，从空LLM响应缓存开始，固定两份独立命名空间，只做3a抽取+核查，冻结当前代码/Prompt/模型别名/患者输入和本轮公共接口快照。观察到每次150/156请求（合计294核查+12抽取/合并），按均价$0.1753，含截断重试及变化缓冲报价$0.18–$0.23。硬上限直接使用剩余$0.283927157，不因用户口语四舍五入$0.284而多花。只在非高峰，开始前核实余额，逐请求预留，额度不够即停；不补跑挑选结果，不改规则/基线。

备选AGXT ×2：观察343请求（315核查+28抽取/合并），按均价$0.2301，含重试报价$0.25–$0.28，剩余额度内风险更高。两病例各2次按均价已约$0.4054，未计重试，不能在本额度内承诺。

本次不自动补齐上述待核查请求，也不启动任一真实独立运行。两个提案都包含同义项合并；新输出仍可能增加调用，报价不是保证次数。若选定方案后安全/外部请求仍无可用响应，保留不完整标记，不宣称完整验收通过。

## 验证

免费响应固化后，AGXT第1次另做纯离线重复回放，模型禁用，公共接口禁止联网；行动/条件列表和待核查Key集合完全一致，新增公共请求0。全量离线1260项通过（13.17秒），114份正式输出/基线保护哈希保持不变。

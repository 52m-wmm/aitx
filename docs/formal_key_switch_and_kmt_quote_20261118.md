# 正式Action Key切换与15例离线验收 v1.0 — 2026-11-18

> 后续状态（2026-11-19）：用户批准$0.08后将执行范围缩为一票。现已完成4次请求、费用$0.022005876并停止，另一票未运行、须等新批准。详细结果见 [单票报告](kmt2b_one_new_vote_20261119.md)。下文报价保留为历史依据，不能作为继续调用的授权。

## 已完成的切换

迁移前检查了当前15例所有行动的身份等价关系、319条审批映射的双向单射及全对象逆映射。不同旧key没有因新key而误合并，原同一旧key的引用没有拆开。65 RxCUI、203锚点+偏移、49 name_dependent、2保留旧key的审批方案原样使用，不继续优化规则。

252条行动记录的正式key已切换，未改状态、分类、条件、引用或Evidence ID。旧→新及name_dependent/归一化未确认标记保存在data/action_key_registry.json；审定原表仍在runs/action-anchor-supplement-final-20261118/mapping.tsv。未登记的新候选不会借名称别名强行归到已批准行动，先保留旧身份供后续单列审阅，本次没有扩大审批映射。

### 兼容性与证据不变

- 临床计算继续使用原身份，在Ledger序列化出口应用已批准别名；同一对象多次序列化不改内存中的临床数据。3b–3e内部查重/医学规则保持原行为，未执行这些阶段。
- 只转换action_key/key/implements等确切机器引用，整份evidence数组原样保留，包括其中历史action.key出处；既有Evidence ID函数未改、不重算ID。
- 报告的药物识别改为查询可逆别名，避免药物类别迁移为锚点后丢失drug:前缀导致安全清单漏项。这是身份兼容，非新增医学判断。
- 模块和迁移工具：aitx/evidence/action_identity.py、scripts/switch_action_keys.py。正式别名表active=true；回滚后只关闭向新key导出，仍能解释归档中的新key。

## 15例验收

| 病例 | key变化的行动记录 | 结果 |
|---|---:|---|
| PRAC-AGXT-c33dup | 18 | PASS |
| PRAC-AGXT-c508GA | 18 | PASS |
| PRAC-ANO10 | 11 | PASS |
| PRAC-CFTR-F508del | 42 | PASS |
| PRAC-COL1A1 | 52 | PASS |
| PRAC-GRIN2B | 8 | PASS |
| PRAC-KMT2B | 17 | PASS |
| PRAC-NF1 | 9 | PASS |
| PRAC-OTC | 36 | PASS |
| PRAC-SLC35A2-ex7 | 5 | PASS |
| PRAC-SLC35A2-ex8 | 5 | PASS |
| RETEST-CNNM4 | 0 | PASS |
| RETEST-EIF2B1 | 15 | PASS |
| RETEST-PFN1 | 16 | PASS |
| RETEST-THPO | 0 | PASS |

15/15均通过：
- 当前JSON按逆映射还原后与备份整对象严格相等；行动数量/顺序、标签、classification、status、全部条件及其分组、缺失信息均不变。
- evidence数组逐项完全相等，Evidence ID及所有引用不变；非key字段变化0。
- 药物安全覆盖清单一致，Step4仅在隔离测试中呈现的Markdown逐字相同，trace逆映射后相同；未重新写任何正式Step4报告。日期提供器两边均仅使用来源内已存effective_date，其余日期为未知，未联网补日期。
- 15例均演练了临时副本恢复原始备份字节；独立单元测试还调用真实rollback逻辑，验证部分应用可恢复、后续未知修改会拒绝覆盖。
- 离线全量1282项通过（12.86秒）；真实模型/公共联网0、本轮费用$0。

### DBS专项

GPi-DBS与subthalamic nucleus DBS仍位于支持治疗，均conditional，原因source describes use; no explicit recommendation；迁移前后状态与Evidence IDs完全相同：

- Bilateral globus pallidus pars interna deep brain stimulation (GPi-DBS)：f79048a6b89a
- subthalamic nucleus DBS：435f3d2889a1

无行动遗漏，Key切换没有产生条件或Evidence ID差异，没有引入投票；当前既有“仅描述使用”的临床解释未改。泛称DBS的孕期句只作附注，不重新创建孕期独立行动。

## current与历史基线

历史基线和Accepted current全部只读、SHA不变，没有升级Approved/Accepted。
本轮对改前正式账本的key-normalized diff为0。原始diff及归一化diff：out/status_diff/formal-key-switch-20261118/{since-before-raw,since-before-normalized,current-raw,current-normalized}/。

canonical与Accepted之间仍有此前记录的既存差异，数量{"action_added": 18, "details_changed": 4, "action_removed": 4, "status_changed": 2, "baseline_missing": 157}。已逐条断言切换前后对current的这些差异完全相同；本轮没有新增或擅自抹平。这里157项baseline_missing是未建立首个基线的RETEST条目，不是新增临床行动；2项状态差异是之前R15修复，不能算本轮Key切换引起。

## 回滚

备份：runs/formal-key-switch-20261118/before/<case>.json（原始字节），manifest.json记录改前/改后SHA及基线SHA，registry.json保存应用的别名。以下命令尚未对正式输出执行，仅测试过隔离副本：

```sh
.venv/bin/python scripts/switch_action_keys.py rollback --out runs/formal-key-switch-20261118
```

它恢复15例原始字节并禁用向新key导出；若发现迁移后其他未知修改则停止、不覆盖。无需改动任何历史基线。当前切换保持有效，未回滚。

## KMT2B下一步：仅报价，尚未获准调用

目标是只观察Step3a新增两票抽取，不上线新的医学多数决规则，也不执行3b–3e。已有首票取自当前账本所用的4份原始响应，固定输入逐字保存在runs/kmt2b-call-approval-20261118/first_vote_source_records.json。原首票是历史真实响应的复用，不冒充本轮新调用。

### 精确输入数量与同输入实测费用

四份输入各新增两次独立真实抽取，**8个首发请求**；temperature=0、原3a-v5 Prompt/全部参数不变，输出上限16384，沿用截断时一次32768重试。两次新票用独立响应缓存/日志，强制绕过响应缓存；固定患者Step1/2、来源文本/数据库响应、规则和别名表，不因新增输出隐式联网。

| 来源输入 | 新增首发数 | 按同输入历史均价的两份完成响应估价 |
|---|---:|---:|
| Management | 2 | $0.000169656 |
| Management / Treatment of Manifestations | 2 | $0.018859356 |
| Management / Treatment of Manifestations / Developmental Delay / Intellectual Disability Management Issues | 2 | $0.018184080 |
| Management / Pregnancy Management | 2 | $0.006519924 |

8份完成响应估价 **$0.043733016**；相同4输入的两轮历史执行共有2次截断重试，实付 **$0.020082222**（含输入费用，不只估输出）。扣除不需要新调用的章选择后，两轮实测合计 **$0.063815238**，即约 **$0.064**。按历史重试形状参考10个实际请求；只有8个首发数是固定计划，不能承诺未来输出token或重试次数。

**拟定本次硬上限$0.08，从剩余$0.283927157内扣，不是新开总预算。** 逐请求按最大费用预留；单次base预留约$0.0107–$0.0117，截断重试预留约$0.0205–$0.0215，额度不足就停止并保留已完成输出，不为凑一致再跑。缺usage/传输实付未知按该请求预留计，不按0。只有在获得批准后才非高峰执行，执行前查DeepSeek余额；服务端必须返回deepseek-flash，文档版本DeepSeek-V4.1-Flash-1017，不能独立核验底层权重。

### 报价范围与未测边界

这份$0.08只申请8个新增源抽取及必要重试；章选择/归一化/引文修复/同义合并/上下文核查均只读缓存，缺缓存就标待核查、不追加真实调用。因此不能把此报价解释成“完整核查后的3a全套通过价”。
已先用当前相同规则$0重组首票：26个行动记录，其中5项是此前kind修复恢复的待核查候选，不是模型不稳定新增；同义合并1次、上下文30次缺缓存，仍incomplete。两个DBS的确定性状态仍conditional，已有key和Evidence IDs与正式迁移后账本相同。后续三票均按同一当前规则组装，避免把首票旧规则与新票新规则混比。

### 输出与归因

- 三份原始抽取逐项列出DBS、遗漏/新增、kind、quote、manifestation和conditions；三票并集/多数/分歧只在实验分析中记录，不写正式Ledger或Accepted。
- 每票按固定规则缓存组装，缺新核查明确未测。原始模型未提出该行动/条件为抽取差异；原始存在但组装丢失、路由错误或同输入状态不一致，归后处理/分类问题。缺核查不冒称分类错误。
- Key映射之外的Evidence ID变化逐条分解来源引文、模型claim、输入类型或原键变化；不把ID变化一律当新证据。
- 用status_diff.py出三份实验的两两/对首票对照，同时列原始与别名归一化视图；已批准映射外新候选单列，不强配到不同临床行动。
- 既有目的/孕期/来源规则的合法过滤单列，不误报后处理错误；只对违反既有契约的丢失/分类判定认定为代码问题。跨票差异本身不自动等于医学错误。
- 任何关键差异先报告根因，不自动修医学规则、筛选“更一致”的一票或更新Accepted。

本报告提交时尚无本次新增模型调用，剩余额度未动；等待对上述单病例限定范围的单独批准。

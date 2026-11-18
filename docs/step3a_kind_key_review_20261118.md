# 3a kind修复、身份键约束与三票方案 v1.0 — 2026-11-18

> 后续决定：用户已批准独立原句锚点的审计设计，但明确未审前不切换key。最新319条提案与107条未决项见 docs/action_anchor_audit_20261118.md；下文保留设计获批前的历史结果。

## 当前完成范围

本次真实模型调用0、联网0、费用$0；剩余$0.283927157不动。第1项代码修复与15例缓存审计已完成；第2项发现现有ID依赖和RxCUI缺失两处实质约束，已提出替代方案等待用户选择，尚未迁移key。第3项仅方案和报价，不实现三票，不执行调用。正式账本和Accepted Baseline未改。

## 1. kind不再静默丢弃

已知drug/procedure/diet/device/avoid和可识别的therapy保留原路由；词表外therapy或未知kind优先按名称中的明确类型线索归入diet/procedure/device（如fluid intake、IV fluids、brace），药物类型同义词归drug；无法映射为other、kind_review_pending=true，并增加由代码产生的类型待核查unknown条件。该条件不是伪造模型核查结果，不把other默认为适用；明确的病人事实比较仍保留原规则。缺kind/空名称等格式错误直接抛错。

该变化也会保留诊断评估转诊、目标性语句、行政服务等误抽候选为other待核查；不能把这些当作新增已确立建议。原NOT_A_THERAPY通用栏目名及Pregnancy Management只作附注规则保留。known avoid在非avoid节被过滤属于既有章节路由，单独报告，本轮不改变它。

15例审计覆盖选定章节全部60个主抽取输入及触发的行补抽缓存，无缺缓存；对原过滤条件逐条重现，发现34条病例×抽取候选（含重复源/同病例重复项）。这些是确实走过旧过滤分支的记录，不等于34个完全未被其他来源覆盖的临床行动。已有名称/引文重叠只列可能覆盖关系，不能据此证明等同。另34条known avoid章节过滤记录单列，不能混入未知kind修复数。4例没有选用GeneReviews章节，该路径为0，不代表所有文献回退链都无遗漏；文献回退原本就不使用此词表过滤。

| 病例 | 被旧kind规则过滤的候选 |
|---|---|
| PRAC-AGXT-c33dup | Maintain high urine volume |
| PRAC-AGXT-c508GA | Maintain high urine volume |
| PRAC-ANO10 | inpatient rehab; psychotherapy; neuropsychological rehab; cognitive & behavioral therapy; Goal Management Training |
| PRAC-CFTR-F508del | nutrition management; Routine vaccinations; ART; Psychotherapy; early mobilization（孕期附注） |
| PRAC-COL1A1 | physiotherapeutic program; non-weight-bearing muscular exercise |
| PRAC-GRIN2B | IEP; applied behavior analysis (ABA) |
| PRAC-KMT2B | tailored exercise program; applied behavior analysis (ABA); individualized education plan (IEP); 504 plan; Developmental Disabilities Administration (DDA) enrollment |
| PRAC-NF1 | chemotherapy; chemotherapy |
| PRAC-OTC | ammonia scavenger therapy; high glucose infusion rate; home-based services; individualized education plan (IEP); 504 plan; applied behavior analysis (ABA) |
| PRAC-SLC35A2-ex7 | 0 |
| PRAC-SLC35A2-ex8 | 0 |
| RETEST-CNNM4 | 0 |
| RETEST-EIF2B1 | 0 |
| RETEST-PFN1 | multidisciplinary team; Individualized moderate-intensity endurance-type exercises for the trunk and limbs; noninvasive ventilation (NIV); ventilatory support; Hospice care |
| RETEST-THPO | 0 |

完整原句、kind、拟映射类型、缓存Key、是否孕期、现有账本可能覆盖项见previously_discarded_kind_candidates.json；这些条目尚未整例刷新到正式账本。

## 2. action_key的两个约束（等待明确）

- 当前Ledger Evidence ID = hash(source type/id, claim, section, action_key, branches, quote)。claim和action_key本身会随模型措辞变化。直接以它生成action_key会形成循环，并不能稳定；现有Evidence ID冻结测试不得破坏。
- 15例共有319条3a身份记录，其中53条drug键没有RxCUI，包含benzodiazepines、药物类别、未映射名称等；不能虚构RxCUI，也不能把成分组合或类别强行变成单一成分。
- 建议另建只依赖来源定位与完整原句的source_sentence_anchor_id，保留现有Evidence ID生成方式；同句多行动按来源中已确认的实体位置/固定槽位编号，不按模型列表顺序。无法唯一定位、多段合并、总称/具体项冲突须标未决，禁止用模型措辞或旧key偷偷打破平局。新增证据不能重排已认可槽位。
- 建议有RxCUI继续RxCUI，无RxCUI药物类别也用原句锚点并标归一化未确认；也可由用户选择暂留旧key。该例外尚未获批，未实施。
- identity_feasibility.tsv/JSON列出全部319条旧key、Evidence IDs、是否有Accepted行；已有RxCUI的列旧→原值，其余PENDING。它是可行性清单，不冒充已完成的一一对应迁移表。待选择后再生成最终旧→新表和映射后零状态变化证明。

对当前正式账本的改前/改后status_diff为0（尚未刷新、尚未迁移key），对Accepted current完整输出也已保存。不能把这一结果解释为第2项迁移已完成；此前Accepted与账本的既存差异保留，不擅自升级。

## 3. 抽取三票方案（未实现、待审）

- temperature=0、每个固定来源单元k=0/1/2分别真实生成；原句、上下文、模型/Prompt版本不变，三票不能复制同一个响应缓存。源级票可由15例共用，但稳定性重复实验须隔离命名空间。
- 行动按稳定来源锚点与实体槽位对齐，取三票并集；未解决第2项前不能以名称相似度假装对齐。总称/具体器具并存时保留原文支持的具体项，总称记为上位描述附注；没有具体原文不能凭模型扩展。
- 条件按原文锚点、字段、操作符、数值/单位和分组对齐，多数票决定保留集合；任何存在/缺失、类型、条件范围或分组分歧，条目保持conditional并记录三份原始意见及各条件支持票数。少数票提出的条件保留为待核查，不静默删除后变为applicable。
- 模型不投临床状态；患者年龄/性别/变异等仍交原确定性规则。来源分歧不产生新的not_applicable。FDA来源优先规则不变；FDA条件抽取、行补抽、引文修复和文献回退若纳入三票，必须另行盘点其输入，不能用60个GeneReviews主段落的数字覆盖。
- 缺一票即未完成，不把票缺失记为多数；候选全集和所有原始票均保留。验收先列变化及原因，不自动改临床规则或Accepted。

### 调用量与费用的两种输入粒度

现行生产按Section（章节块）而非逐句/逐段抽取。15例当前共60个主块、去重54份来源输入；仅把这些输入由1票加到3票，新增120次（逐病例独立），或共用来源票时108次。按现有69份同模型3a-v5真实usage均价$0.00279004/次，新增抽取约$0.33480或$0.30132，重试另计，均已超过剩余额度；这不含FDA/文献回退/行补抽/新核查，不是完整15例重跑总价。

若“每个来源段落”按字面改为Paragraph/表格Row单元，目前是483个病例×单元。三票需1449次初始抽取，相对现行60次增加1389次；按章节历史均价粗略代理约$4.04总抽取/$3.88增量。由于粒度改变、单元更短，该均价不适合精确报价，不能据此直接批准执行；必须先审定拆分方式和全来源范围，再给完整报价。不能误报为966次增量：那是相对一个不存在的483次单票基线。

每例单元数及完整来源单元见three_vote_quote.json。4个没有选定GeneReviews章节的病例在此计数为0，仍可能有文献/症状回退源；本表明确不覆盖其新三票成本。合并后新增核查数量依赖新的并集与条件，尚不能静态给定，更不能默认0。建议先维持现有输入边界，完成身份设计与缓存回放，再审阅全来源追加盘点；本轮不申请花费已停止的额度。

## 产物与验证

审计目录runs/step3a-kind-key-audit-20261118；四次kind修复回放runs/step3a-kind-fix-v3-20261118，均强制--offline、禁止模型，只用已有免费响应/失败快照。AGXT1的high oral fluid intake和intravenous fluids保留是本轮验收断言；原kind_fix-v2日志有并发JSON写坏问题，回放工具已加锁并在finally写完整清单，v3仅修日志、不换模型输出，逐次行动一致性另核对。

第2项尚未实施，因此四次回放只能给kind修复后的对照，不能宣称措辞/key差异已消除。三类计数、全部差异和status_diff详见最终补充及analysis.json。

### kind修复后四次离线重算（尚未稳定化key）

| 回放 | 行动记录数 | 仅措辞/键表示差异 | 记录增加/减少 | 状态/条件/类型差异，待核查 |
|---|---:|---:|---:|---:|
| AGXT 1 | 26 | 10 | +3/−0 | 2 |
| AGXT 2 | 23 | 6 | +1/−0 | 5 |
| KMT2B 1 | 25 | 0 | +6/−2 | 9 |
| KMT2B 2 | 26 | 0 | +5/−0 | 9 |

AGXT1两项真实遗漏已恢复；新增记录中包括未识别的目标/行政候选，必须保持other待核查，不能称新增有效治疗。KMT2B的器具总称/具体项粒度差异尚存。措辞/key差异没有消除，因为第2项尚未实施；该表不是“完成1、2后”的最终验收。

所有四次原始回答不变、模型/公共网络调用0，缓存缺口只计待核查；3a组装到末端但缺合并/核查，整体仍incomplete。组装时账本自检无fail（不代表缺失核查已测）；1268项全量离线测试通过，涵盖生产入口保留AGXT两项、other未知条件与既有Evidence ID依赖关系。修复并发日志后四次行动内容逐一等于修日志前版本，没有挑选有利回答。正式账本改前→改后diff为0，Accepted current未改。

本轮结论：第1项已修复并验证；第2项等待原句锚点/无RxCUI例外的选择，旧→新最终映射及映射后零状态变化证明未完成；第3项仅提供输入粒度方案与部分可确定调用量，完整全来源15例报价需先审定范围，不能据主章节下界授权执行。本轮不运行模型。

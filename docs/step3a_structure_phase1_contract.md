# 3a结构驱动阶段1契约（2026-11-19修订）

> 历史设计参考：对应旧结构抽取实验已退役，本文不定义当前生产接口，也不恢复历史调用授权。与Step3后续适配有关的设计和未核实问题暂保留；当前入口见 [3a说明](step3a_contract.md)。

本接口只生成结构候选与审阅材料，不改正式Evidence Ledger、患者状态或生产v5路径。旧抽取保留。完整刷新与15例付费缺口收集继续延期。阶段2的授权实验及结果单列，不构成临床输出升级。

## 结构与来源单位

`genereviews.management_structure`从正文定位标题以Management开头的根，包括Management of ALS；不取摘要同名小节。保留XPath、来源SHA、行列跨度、全部多级表头和单元格列表树。19章验收保留51表、480/480内部列表项、3个多级表头。

表格治疗列逐列表项枚举，同行所有有明确语义的列按列名保存：Treatment Class/类别→category；Objective/目标→purpose；Manifestation/Concern/表现→condition。目的不作为患者条件；未知列只保留来源，不猜语义。

治疗路由全部表外p（含列表p、粗体所在段、接续段）按句扫描；有词典/词表命中则枚举名称和位置，无命中句标needs_classification。固定GeneReviews定义句non_action。剩余整段0仅表示已切句，不表示没有未判内容。原表格/列表的完整细节句仍可为detail，短前导语≤6词可命名行动，不能判的保留needs。

粗体上下文区分治疗名、类别/目的、表现。HPO精确匹配函数/阈值不变；未匹配且未确定为类别/目的的标签needs。接续段继承同小节最近标签，遇新标签/小节终止。DD/ID沿用原句模板及年龄来源，不判断患者；同一已知程序的模板/列表命名身份一致。

RxNorm本地名称表、独立可审词表及来源SHA保留。命中只是词面候选，不能证明当前句推荐或患者适用。正匹配的药物例子单列，X保留类别；普通非药物例子仍归父项，未知不当非药物。用户明确要求的neridronate补词保留RxNorm无匹配状态，不造RxCUI；用户要求的具体透析/移植示例也分别保留。

## 默认治疗路由与条件来源

Management根及所有未排除子节默认treatment。排除祖先优先：Evaluations Following Initial Diagnosis、Surveillance、专门Imaging、Evaluation of Relatives at Risk、Pregnancy Management（同名附注）、Therapies Under Investigation（研究线索）、Genetic Counseling相关。Agents/Circumstances to Avoid保持avoid。

Targeted Therapy/Therapies为targeted；Prevention为preventive；Acute为acute。表格See Targeted Therapy把表现列作为所指小节的附加条件来源，与原句条件并存，不判断患者满足。

人群标题复用已批准的性别/年龄/合子条件来源规则。按表型组织的标题仅对照病人Step2已选分支与已有同义词；已知不匹配标other_phenotype，无法对齐保留unknown，不改正式分支或患者临床结论。

Other及任何治疗节的无效/无获益/不推荐措辞保留negative_evidence，交核查，不自动推荐。当前核查设置不因指认模式而改变。

## 去重与审阅

同一小节同一RxNorm身份或显式词表/程序原名合并一个候选，全部来源单元及其各自条件保留；聚合条件仅作索引，不默认全局AND。正负来源可并存，负面标记不可隐藏。父类与具体方案不互相吞并：dialysis、hemodialysis、peritoneal dialysis及organ/liver/kidney/combined transplantation均独立。

`acceptance_structure.py`禁止模型和网络，生成15例计数及19章路由表；对“章节已记录但Management单元为0”抛错，不能默默健康0。route表按每个标题直接所属单元计；已处置表示结构分类/排除，不等于临床核查完成。

最新阶段1交付（历史资料已清理）含完整计数、两份清单和management_routes_actual.tsv。Accepted名称、原句定位、同行定位、未找到分别报告；后三者不算独立名称召回。无章节4例保留原路径；不得读取四个评测病例结构或跑评测Step3。任何正式Ledger变化必须先后保存完整status_diff并另经用户批准；本轮未升级current。

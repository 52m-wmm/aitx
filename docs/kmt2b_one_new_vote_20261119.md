# KMT2B 单票新增抽取结果 v1.0 — 2026-11-19

## 完成范围与停止状态

遵照用户最新“一票跑完汇报等批准”，只完成一票新增抽取：4份固定来源、4次真实请求，全部成功，无重试、响应缓存复用0。另一票未执行。已有首票是历史响应复用，不计本轮新调用；现在只有两份观察，不作三票多数裁决或三票稳定性通过结论。

执行区间 2026-11-19 05:10:12 PST 至 2026-11-19 05:13:28 PST，全部非高峰；nohup+caffeinate包裹。付费进程已退出。原始输入、响应、实际Call ID、usage、预留/结算日志均在runs/kmt2b-new-vote1-20261119。没有运行Step3b–3e，没有改医学规则、正式账本、Key登记表或Accepted。

## 费用与模型

- 本轮按usage及项目非高峰费率计 **$0.022005876**，全部4次usage完整、未知费用预留0；没有把missing usage记0。
- 旧$0.50实验已计$0.216072843，加本轮后$0.238078719，剩余 **$0.261921281**。最新预算指针runs/step3_remaining_budget.json；不能再把旧目录的$0.283927157当当前剩余。
- 此前$0.08子上限尚余$0.057994124，但用户已缩为一票，余额不构成执行下一票的批准。
- 提示输入4992缓存token+730未缓存token；输出36469 token，其中reasoning32788。服务端实际均为deepseek-flash，官方API、temperature0、3a-v5 Prompt及参数不变。文档型号DeepSeek-V4.1-Flash-1017，无法独立核验API别名背后的权重。
- 余额接口前后均返回18.00 CNY且账户可用。接口余额未显示即时扣款原因未确认，不据此把模型成本记0，也不以人民币差额换算美元。

## 原始抽取与行动集合

4份来源中，Management仍为空且一致，其余3份原始JSON均不同。固定原文未变，原始差异不来自新的检索或病例信息。

| 来源 | 首票原始条目 | 新票原始条目 |
|---|---:|---:|
| Management / Pregnancy Management | 7 | 7 |
| Management / Treatment of Manifestations | 21 | 20 |
| Management / Treatment of Manifestations / Developmental Delay / Intellectual Disability Management Issues | 8 | 7 |
| Management | 0 | 0 |

按相同当前代码进行缓存组装：首票26行动记录，新票23；均不含None found占位。按既有Key对齐，Key变化时只对同一字面名称补对齐，共21个可比较条目。未对改写名或总称做医学同义猜测。

| 观察 | 原始提取层 | 组装后的解释 |
|---|---|---|
| walkers、ankle-foot orthoses → adaptive aids | 新票用总称替代两项具体器具 | 首票两条具体记录消失、增加总称；这是粒度损失，不能说所有器具治疗都没召回，也不是后处理丢掉已提出的具体项 |
| 504 plan、DDA enrollment | 新票未抽出，固定输入仍有这些原文 | 两条行政/服务候选未进入组装；归上游遗漏观察，不等于两种治疗被证实不适用 |
| individualized education plan (IEP) → IEP | 名称缩写 | 旧全称记录换为缩写；审批别名登记表没有该新增身份，不自动改登记表或强配。不能计作真实新疗法 |
| feeding therapy在DD/ID段新增一次提及 | 首票其他段已有该行动 | 不是新增行动，但增加了来源和条件范围 |
| Speech-language therapy、AAC括号、PT/OT缩写等 | 名称/大小写/标点变化 | 部分既有类型键仍能对齐；引文claim及核查输入可能变化 |
| 孕期trihexyphenidyl → trixhexyphenidyl | 后者确实出现在固定来源，不一律当幻觉 | 本轮缓存中两种形式均可处理；孕期句仍不生成独立行动/缺失信息 |

全Key集合有5个旧记录无直接新匹配、2个新记录；其中含上述IEP改名与器具粒度变化，不能直接称“5个治疗漏召回、2个新治疗”。完整原始JSON Diff、同名字段Diff在analysis/raw_diffs.json，组装记录与匹配规则在analysis/summary.json。

## DBS专项：本票未复现回归

| 项目 | Key | 条件 | Evidence ID | 既有判定基础 |
|---|---|---|---|
| GPi-DBS | 相同 | 完全相同 | f79048a6b89a，相同 | conditional，source describes use; no explicit recommendation |
| subthalamic nucleus DBS | 相同 | 完全相同 | 435f3d2889a1，相同 | conditional，同上 |

两项源原文中dystonia条件仍由已有HPO匹配为pass，“仅描述使用”条件仍unknown，不变成not_applicable。泛称孕期DBS未被单独创建。这些是既有缓存与确定性组装的相同判定基础，不代表整例新增临床核查已完成。

## 条件变化与后续分类

21个对齐条目中11个条件记录不同；包括实际范围/字段变化、重复年龄条件以及仅措辞大小写差别，不能把11都算成11个新增医学限制。

| 行动 | 首票条件文字 | 新票条件文字 |
|---|---|---|
| chest physical therapy | respiratory compromise from chest deformities related to scoliosis; pulmonary infections | individuals with respiratory compromise from chest deformities related to scoliosis; respiratory compromise from chest deformities related to scoliosis |
| Speech-language therapy | 空 | developmental delay / intellectual disability; feeding skills and communication |
| applied behavior analysis (ABA) | Children; intervention type requires verification | behavioral, social, and adaptive strengths and weaknesses; intervention type requires verification |
| feeding therapy | safe to eat by mouth; difficulty feeding due to poor oral motor control | Ages 0-3 years; Ages 0-3 years; developmental delay / intellectual disability; Assuming that the individual is safe to eat by mouth; difficulty feeding due to poor oral motor control |
| developmental preschool | Ages 3-5 years | Ages 3-5 years; Ages 3-5 years; developmental delay / intellectual disability |
| antimuscarinic (anticholinergic) agents | confirmed diagnosis of a KMT2B-related disorder; motor manifestations | individuals with a confirmed diagnosis of a KMT2B-related disorder; motor manifestations |
| prophylactic antibiotics | during the winter months; respiratory compromise from chest deformities related to scoliosis; pulmonary infections | during the winter months; individuals with respiratory compromise from chest deformities related to scoliosis; pulmonary infections |
| physical therapy | joint contractures, hip dislocation, and/or kyphoscoliosis | developmental delay / intellectual disability; joint contractures, hip dislocation, and/or kyphoscoliosis |
| early intervention program | Ages 0-3 years | Ages 0-3 years; Ages 0-3 years; developmental delay / intellectual disability |
| occupational therapy | Fine motor dysfunction | developmental delay / intellectual disability; fine motor dysfunction |
| influenza immunizations | respiratory compromise from chest deformities related to scoliosis; pulmonary infections | individuals with respiratory compromise from chest deformities related to scoliosis; pulmonary infections |

有8个“确定性暂存状态”不同，但8个全部缺新的上下文响应，不能报告成8个确认的临床状态变化。正式实验status统一保留not_tested；不把unknown升级为适用。这些暂存值只解释抽取差异如何传播，不能当完整3a结果。

**药物/操作类型差异**：influenza immunizations首票kind=drug、新票kind=procedure，同一后处理代码按各自类型产生不同键。使用生产is_drug识别入口，旧为药物、新为非药物，可能影响药物安全覆盖清单。根因是原始kind不一致向后传播，不是本轮Key迁移把相同输入的药误丢。是否统一疫苗类型需审阅，此次不改规则。

本轮没有发现“相同有效抽取、相同核查输入却被确定性代码随机分级”的证据；也不能据此证明所有后处理都正确。来源条件/表现抽取差异、既有合法过滤、缓存未测三者分别记录，不把它们一律归为分类错误。

## Evidence ID差异

- 21个对齐条目中10个Evidence ID集合不同；DBS两项不变。
- 整个临时3a账本（含未对齐记录）新增29个ID、少20个ID。13组相同来源ID/章节/规范化原句的证据出现不同ID；原因可追溯到claim文字、原始类型/legacy key等身份组成字段变化，不是新增文献或换ID算法。
- 新选6个引文单位、不再选3个单位；所有仍来自同一冻结文档，不能称新检索6篇文献。
- 实际模型Call ID已正确保留为新票sample=1，未被缓存回放误写成首票sample=0；Evidence ID公式本来不依赖Call ID，因此它不是上述ID变动的原因。
- 完整旧/新ID与claim/action/原句对应在analysis/summary.json的same_source_quote_changed_ids、matched_changes；不自动修Evidence ID方案或正式证据。

## 未测与验收界限

新票缺75次context-check-v3请求（25组三票）及1次同义合并；首票同代码重组缺30次上下文+1次同义合并。新增待核查Key67个、不再待核查22个，不能只按76−31把45当全部新请求。以上全部未调用，没有额外收费。

同义合并缺失，组装为未合并清单；整例标incomplete/full_step3a_complete=false。来源新增一票本身完整4/4，不代表完整3a临床核查完成。只有历史首票和一票新数据，第三票尚未执行，不给三票多数结果。

status_diff.py完整输出：out/status_diff/kmt2b-one-vote-20261119/{first-vs-new,accepted-current}/，带分类/条件/引文/票信息。raw key/证据文字/未测标记均保留，原始diff计数不能替代本报告的归因，也不能据此更新Accepted。

## 执行与验证说明

临床代码/规则、4份输入、源快照及别名表哈希符合报价冻结。仅修缓存回放的追踪元数据：新票响应实际Call ID不得被首票selector覆盖；原报价临床fingerprint未变，执行封套记录此脚本SHA变化，不改模型输入或医学逻辑。

最初后台启动在shell退出时未保活；没有started/模型费用日志，也没有任何源请求进入执行。随后以受执行会话持有的nohup+caffeinate前台形式运行成功，仍具nohup/防睡眠保护，没有重复一票。当前付费进程均已退出。

1286项离线测试通过（13.46秒）；15份正式账本仍为Key切换后原SHA，所有历史/current基线不变；未写正式Step4报告。保存了唯一这一票，不追加第二票、不挑选更一致的输出。等待用户审阅后再决定是否批准下一票；本次余额不能作为自动续跑授权。

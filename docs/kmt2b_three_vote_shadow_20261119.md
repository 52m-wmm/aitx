# KMT2B三票Shadow结果 v1.0 — 2026-11-19

已完成第三票4/4来源抽取，4次独立真实请求、缓存响应复用0、重试0、全部非高峰；余额检查可用。新增费用$0.020626476，usage全部完整、未知预留0；两次新增票累计$0.042632352，小于$0.08。原$0.50实验累计$0.258705195，剩余$0.241294805。无其他新核查费用，无AGXT执行。模型deepseek-flash（文档V4.1-Flash-1017，别名权重不可独立核验），temperature0、3a-v5、固定来源/输入/规则不变。历史首票加本轮两次新票共三票，不声称历史票在同一时窗重新生成。

## 先行$0条件审计

11项中3项仅措辞不同（antimuscarinic、prophylactic antibiotics、influenza immunizations）；8项涉及新增/遗漏/范围变化，类别可重叠。完整条件、Evidence ID和原文见docs/kmt2b_two_vote_condition_audit_20261119.md及实验two_vote_condition_audit.json。chest PT表现字段变动、ABA儿童限定遗漏、DD/ID局部来源范围新增、年龄重复均保留审阅，未删除或自动施加医学限制。

## 三票召回及重点

相同代码缓存组装实际行动数26 / 23 / 25（去除占位）；这不是召回率或准确率，没有独立分母金标准。完整原始抽取含孕期附注等共41个严格规范化名称：23个三票出现、12个两票出现、6个单票出现；缩写/总称保持分列，所以不能称41种临床行动。

| 项目 | 票1/2/3 | 结论 |
|---|---|---|
| GPi-DBS | 有/有/有 | dystonia提取一致；第三票首字母大小写导致claim及ID变化，核查缓存未命中，不能宣称状态升级 |
| subthalamic DBS | 有/有/有 | EID 435f3d2889a1、条件及既有conditional基础一致 |
| 504 plan | 有/无/有 | 恢复抽取；第三票新增accommodations条件与DD/ID范围，保留待审 |
| DDA enrollment | 有/无/无 | single_vote仍保留needs_review，不因少数票删除 |
| walkers / ankle-foot orthoses | 有/无/有 | 原文具体项已恢复，分别保留 |
| adaptive aids | 无/有/无 | 单票总称保留待审；没有与具体器具合并 |
| individualized education plan (IEP) / IEP | 全称/缩写/缩写 | 字面候选分列并标明可能同义；未因缩写两票删全称的资格条件 |
| influenza immunizations kind | drug/procedure/drug | 有2票drug候选，多数不等于医学核验；保留类型分歧，未改变安全路由 |

原始孕期DBS一票名称为DBS/device、两票为deep brain stimulation (DBS)/procedure，属于原始附注，不是新建独立行动；生产孕期过滤保持原样。

## DBS条件与Evidence ID：区别抽取和分类

前两票GPi-DBS主EID f79048a6b89a，第三票b583b46e7b6d，原句相同、claim首字母大小写不同；ID公式未改。第三票没有新的核查缓存，recommendation=not_tested，R15结果未评估。暂存确定性值applicable只是缺核查的中间值，正式实验状态为not_tested；不是病人事实变了，不代表医学规则已放宽。Shadow联合保留旧票source describes use; no explicit recommendation条件，未用三票行动共识删除它。首票与第三票24项可对齐，12项全条件记录不同（11项提取条件不同），8项EID集合不同；7项暂存状态变化均缺新核查，不算确认的临床变化。

## Shadow规则与证据界限

严格按规范化名称建并集；single_vote全部保留needs_review。86个条件变体按完整字段（含op/value/unit）比较，54个只见于单票。两票以上完全一致仅标consensus_candidate；不声称语义等价，也不直接生效。所有条件包括少数票条件均保留原始字段、引用原句、来源章节、原始输入和票号。原始行动quote全部能在各自固定输入中找到，但逐字出现只证明文本出处，不证明它是医学资格条件。条件literal_support也仅为引文子串检查，不冒充语义核验。未确认条件全部保留审阅，不删除、不并入正式Ledger。

没有多数的kind保持null并保留票分布；已有多数也保留分歧。没有按类型优先级强裁。通用名/具体项、缩写不自动并。shadow.json的clinical_effective=false；缓存组装联合保留每一项条件变体，最终均not_tested。不是新的临床报告或完整3a验收。

第三票缺81次上下文核查及1次同义合并，全部未付费调用，整例incomplete。三票新来源完整并不代表三票完整分类核验。

## Accepted与逐项Diff

实验shadow/status_diff/保存三票两两比较、每票对Accepted、联合对Accepted的全部diff.json/diff.md/snapshot.json；vote4代表shadow联合视图，不是第四票真实抽取。只在比较副本里按已批准可逆别名恢复legacy身份以消除正式Key迁移噪音，历史/current文件不写。

联合diff含not_tested、候选并集和来源文字变化，不能当成获批状态变化或直接promote；其他病例的既存差异、RETEST缺基线也原样保留。

- vote1-vs-accepted（仅KMT2B）：{"status_changed": 21, "action_removed": 4, "action_added": 5}
- vote2-vs-accepted（仅KMT2B）：{"status_changed": 18, "action_removed": 7, "action_added": 5}
- vote2-vs-vote1（仅KMT2B）：{"details_changed": 13, "action_removed": 6, "action_added": 3}
- vote3-vs-accepted（仅KMT2B）：{"status_changed": 21, "action_removed": 4, "action_added": 4}
- vote3-vs-vote1（仅KMT2B）：{"details_changed": 14, "action_removed": 2, "action_added": 1}
- vote3-vs-vote2（仅KMT2B）：{"details_changed": 11, "action_added": 4, "action_removed": 2}
- vote4-vs-accepted（仅KMT2B）：{"action_removed": 6, "status_changed": 21, "action_added": 8}
- vote4-vs-vote1（仅KMT2B）：{"action_removed": 2, "details_changed": 26, "action_added": 3}
- vote4-vs-vote2（仅KMT2B）：{"action_removed": 3, "details_changed": 22, "action_added": 7}
- vote4-vs-vote3（仅KMT2B）：{"action_removed": 2, "details_changed": 25, "action_added": 4}

## 完整原始候选索引

| 名称 | 出现票 | 条件变体数 | Kind分歧 |
|---|---|---:|---|
| 504 plan | 1,3 | 2 | False |
| adaptive aids | 2 | 1 | False |
| ankle-foot orthoses | 1,3 | 0 | False |
| antimuscarinic (anticholinergic) agents | 1,2,3 | 4 | False |
| applied behavior analysis (aba) | 1,2,3 | 2 | False |
| augmentative and alternative communication (aac) | 1,3 | 1 | False |
| augmentative and alternative communication [aac] | 2 | 1 | False |
| baclofen | 1,2,3 | 1 | False |
| benzodiazepines | 1,2,3 | 1 | False |
| bilateral globus pallidus pars interna deep brain stimulation (gpi-dbs) | 1,2,3 | 1 | False |
| chest physical therapy | 1,2,3 | 5 | False |
| clonazepam | 1,2,3 | 2 | False |
| dbs | 3 | 2 | False |
| deep brain stimulation (dbs) | 1,2 | 3 | False |
| developmental disabilities administration (dda) enrollment | 1 | 0 | False |
| developmental preschool | 1,2,3 | 5 | False |
| domperidone | 1,2 | 3 | False |
| early intervention program | 1,2,3 | 5 | False |
| feeding therapy | 1,2,3 | 7 | False |
| gabapentin | 1,2,3 | 1 | False |
| iep | 2,3 | 1 | False |
| individualized education plan (iep) | 1 | 1 | False |
| influenza immunizations | 1,2,3 | 4 | True |
| levodopa | 1,2,3 | 1 | False |
| levodopa/carbidopa | 1,2,3 | 2 | False |
| metoclopramide | 1,2 | 3 | False |
| occupational therapy | 1,2,3 | 2 | False |
| occupational therapy (ot) | 1,3 | 2 | False |
| ondansetron | 1,2 | 3 | False |
| physical therapy | 1,2,3 | 2 | False |
| physical therapy (pt) | 1,3 | 2 | False |
| prophylactic antibiotics | 1,2,3 | 6 | False |
| speech services | 1,2,3 | 2 | False |
| speech-language therapy | 1,2,3 | 1 | False |
| subthalamic nucleus dbs | 1,2,3 | 1 | False |
| tailored exercise program | 1,2,3 | 1 | False |
| tetrabenazine | 1,2,3 | 1 | False |
| trihexiphenidyl | 1,2,3 | 1 | False |
| trihexyphenidyl | 1 | 1 | False |
| trixhexyphenidyl | 2,3 | 2 | False |
| walkers | 1,3 | 0 | False |

原始三票及生产缓存组装保存在各自实验目录；本实验shadow.json保留每项原始条件与完整原文输入。15份正式账本、所有历史/current基线SHA核对不变；未修改临床规则，不挑结果，不运行3b–3e，不执行AGXT、不更新Accepted。全量离线1287项通过；shadow投票保护测试覆盖单票条件不删除、总称不合并、无多数kind不强裁。

## 第三票条件含义补充

PT、OT、speech新增学业材料访问限定。固定原句为“Physical therapy (PT), occupational therapy (OT), and speech services will be provided in the IEP to the extent that the need affects the child's access to academic material.” 它支持IEP服务局部限定，不能自动限制所有康复；保留needs_review。feeding、early intervention、preschool仍增加DD/ID范围，第三票没有重复年龄，但不能因此删除其他来源条件。

第三票ABA恢复Children，与首票一致；第二票strengths/weaknesses保留待审。chest PT恢复pulmonary infections，但原文“because of the increased risk of pulmonary infections”属于风险语境，三票相同也不能证明患者必须已感染。504新增“who require accommodations or modifications”有原文，和DD/ID如何组合仍待核查。其余with/individuals with差异不能产生新排除。完整原文与条件逐票保留在shadow.json和各票replay.json；未新增数据源。

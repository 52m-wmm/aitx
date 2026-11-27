## 最新节点：2026-11-27 ClinVar三路召回修复完成，待审核

live.py完整转录本+cDNA/无版本转录本+cDNA/Gene+cDNA三路合并Variation ID去重，必要时分页；仅ClinVar空ESearch缓存24h到期刷新，其他缓存策略及原匹配/CDS等价/P-LP/疾病映射不变。pipeline补gene及searches溯源，不改评分/裁决/Step3，无LLM。
17例隔离检索35次外部GET；OTC新增接受VCV000011010（Pathogenic2星、CDS版本等价），拒绝161330；其他16例接受集合及完整L1–L4不变，COL1A1新增BMP1误召回正确拒。17例primary/分数/候选集合/L4不变；OTC仅L3及证据增加，患者机制仍unknown。新增11测试，全量1320pass/2skip/1既有报告排序fail。4534保护文件含共享HTTP缓存/正式输出及评分裁决代码不变，正式15例1090行diff0，current原缺失完整报错附，无promote。
结果/原答/逐例diff：out/clinvar-recall-fix-20261127/README.md。完成后停止等待人工审核，未刷新正式结果或页面。

## 最新节点：2026-11-27 第四轮 L1–L4 输出及15例离线验收完成，待审核

新增纯组装output.py，pipeline仅在末尾写layers（step2-l1-l4-v1），保留旧字段，不另建总账本、不改评分/裁决/Step1分析/Step3。L1保留原文四态及完整分子结果；L2原诊断/状态，大类无独立证据则unknown；L3全候选及证据方向/待核实；L4预测与数据库机制分开，患者机制unknown。四例新版抽取复用，其余13例明确legacy主体/四态缺口，无重抽。
15常规+ITPR1/SPTLC1=17离线回放，去掉layers后逐字段等于本轮改前，候选无丢失/引用可解析。15例13原自检通过、PFN1/THPO各原MONDO warn保留；额外两例通过。真实ANO10触发NMD、GRIN2B逃逸NMD及4组定向机制/裁决测试覆盖。新增12测试，全量1309pass/2skip/1既有报告排序fail。158保护文件不变；正式15例1090行diff0，current原缺失完整报错附，无promote。相对旧正式KMT2B累计resolved→ambiguous来自前三轮，本轮无新判断变化。LLM/新抽取/外部请求0。
完整四例中文逐字段页及JSON、17例结果/完整diff：out/step2-round4-20261127/README.md、review.html。完成后停止等人工审核。

## 最新节点：2026-11-27 Step1→Step2 分子衔接完成，待审核

本轮只改Step2 pipeline/resolve及独立入口，精确匹配Step1并使用合子状态；G2P等位/机制按路径筛查，缺第二等位/相位/受限集合/功能证据保留条件，预测不当事实。Step1无致病性预测器，未编造；错义+NMD不适用不证明无LoF。分子条件实际约束非明确诊断/非ClinVar的resolved选择，冲突降不确定，不新增硬排除或评分。四例基线逐字段等于第二轮，候选/分数/首位/状态均不变、依据新增。16新增测试，全量1297pass/2skip/1既有报告排序fail，四例自检通过；121保护文件不变，正式15例1090行diff0，current原缺失完整报错附，未promote。LLM/外部请求0，Step1分析、Step3、L1–L4未改。完整表格/原始分子信息/前后diff：out/step2-round3-20261127/README.md。停止等人工审核。

## 最新节点：2026-11-27 Step2 G2P + MICA B3 完成，待人工审核

复用第一轮四例抽取，新增直接G2P来源证据（OTC1、ITPR1 3；另两基因本导出无记录不作阴性）；不参与召回/权重/排除或确认患者变异机制。B3按明确零频率单条注释过滤+仅精确/祖先链匹配；患者入口过滤possible/unknown/general；多候选不能只凭MICA分差resolved。其他公式、权重、20%阈值不变。四组离线回放首位/状态均不变，ITPR1依据变化，SPTLC1 alternatives移出HSAN1A但完整候选保留。1281pass/2skip/1既有报告排序fail，四例自检通过，LLM0。正式Step1/2输出不变，15例1090行详细diff0；current原缺失完整报错附，未promote。Step1/3及L1–L4未改。报告、四组完整结果、改前快照、来源、SVG：out/step2-round2-20261127/README.md。完成后停止等人工审核。

## 最新节点：2026-11-26 Step2 临床事实单次抽取完成，待人工审核

用户授权第一轮仅事实抽取：移除三票/层级多数，原生四态和主体分类，补诊断/人口学/病史/治疗/检验/试验事实与原文。旧评分接口仅确定患者阳性/阴性；疾病召回/评分/裁决及Step3代码未改。四例真实抽取4次+选词3次，费用$0.023517792<$0.05；已告知高峰后用户“直接做”指示立即执行，无重试/截断/缺usage。首OTC文本value检查失败后复用原答；de novo规范化及症状日期不得冒作整体起病均确定性修复。EIF2B1综述零患者表型；OTC胎龄/确诊/住院/三治疗保留；ITPR1严重度/震颤起病/进展保留；SPTLC1很瘦独立保留。最终cache-only回放四例通过，139专项、全量1268通过/2skip/1改前复现的报告排序fail。6259保护文件SHA不变，正式15例1090行详细diff0；current原缺失完整报错保留，未promote。正式输出/页面未刷新，未跑疾病判定或Step3；数值检验/试验状态真实覆盖不足及SPTLC1远端范围映射仍待审。报告、逐项原文、原答、费用、改前快照和diff：out/step2-clinical-facts-20261126/README.md。已停止等人工审核。

## 最新节点：2026-11-26 ITPR1评分只读审计，未改数值规则

用户按先前问题清单要求将震颤加重/轻度运动迟缓/震颤起病用于评分。原HPO SHA回放三个phenotype对象完全一致，分数2.2418/2.1878/1.979；无算术错误。原三票未结构化抽取加重，mild仅quote，起病为症状级；原始同症状HPO注释无程度/起病修饰，疾病级course不能替代。SCA29本地含progressive2/10，SCA15含juvenile，不能按病名或典型年龄强扣分。撤回先前“这些遗漏导致候选分不开”的未经验证因果说法。无足够可比证据，未编造权重或数值修复，生产代码/Prompt/正式输出/基线均不改，模型/联网0。逐行源证据/原答/复算见out/itpr1-scoring-audit-20261126/；未生成修复后分数，后续须先建立同症状可比证据和通用计分规则。

## 最新节点：2026-11-26 SPTLC1两份新选择回答完成，仅隔离回放

用户授权补sample0/2并回放，验收前不刷新正式结果。非高峰串行2次、无重试/缺usage，$0.00057405（本轮帽$0.03）；原抽取及sample1复用。very thin三票均映射HP:0004325，但既有层级聚合被更具体Weight loss覆盖，不称最终新增独立症状。sample0感觉减退新答改为既有最终HP:0002936，票2→3，代表描述随之变化；其语义范围边界未修。诊断/候选分数/患者事实逐字段不变，仍ambiguous/low，8自检通过。固定原数据SHA及HGNC快照后旧回放精确等于正式结果；初始HGNC location差异另留痕。11952保护文件SHA不变，新答案仅out隔离，正式15例1090行详细diff0；current原缺失完整报错保留，无promote。完整结果/费用/原答/全diff：out/sptlc1-hpo-replay-20261126/。等待用户验收，未跑SYT1或Step3。

## 最新节点：2026-11-26 SPTLC1 HPO候选召回离线修复，映射待验证

用户只授权HPO映射修复及复用旧答离线验证，不刷新正式结果。通用同原文/同极性候选共享，仅补其他票既有精确命中的术语，不复制投票；精确匹配/Prompt/诊断规则不动。18官方病例16例抽取逐字段不变；SPTLC1两票新增体重偏低候选，SYT1两票新增眼形态候选，4份新选择请求缺缓存，未伪用旧编号答、未生成新诊断，不称完整映射验收通过。123专项通过，全量1252通过/2skip/1既有报告排序fail，改前代码同样复现该fail。11952保护文件SHA不变；正式15例1090分支行详细diff0。current开工前已缺失，完整报错保留，未重建/promote。模型/网络0，改前快照、全请求diff、代码diff及验证在out/step2-hpo-mapping-20261126/。其他Step2整改未做。

## 最新节点：2026-11-26 复杂条目合法保留Conditional

用户决定GoF/LoF功能实验、外部主方案依赖等剩余复杂项保留待核实，不强排、不逐条硬编码。该类未知不再仅因未自动排除算代码缺陷，也不称完整资格已通过。核对21项复杂研究均Conditional；既有OTC/CPS1独立硬冲突排除保留。未改生产逻辑/判定/prompt/页面，无新模型，前两轮离线修复仍待发布。契约已记录，核对清单out/step3b-complex-policy-20261126/verification.json。

## 最新节点：2026-11-26 NF1/NF2与GRIN2B/DPPM相关性补充，离线待发布

用户授权补guards.py跨病名守卫：登记疾病与入组患者路径共同限定时移出不相关患者疾病候选；匹配疾病基因/替代患者路径/已记录代谢证据保留。DPPM亲属/健康对照原文及资格未知单独保留，不作全研究资格排除。
15例459项离线相对上轮新增NF1八项NF2、GRIN2B一项DPPM筛除（10分支行），其他判定不变。相对正式结果累计另含上轮两项队列改判。108专项通过，全量1245通过/2历史skip/1既有排序fail。10767保护文件SHA不变，新模型/网络0，prompt不动，不更新缓存/页面、不promote。current原缺失完整报错已附。
报告out/step3b-disease-scope-20261126/README.md，diff为本轮、against-formal为累计待发布，change-explanations.json含逐项来源。

## 最新节点：2026-11-26 3b多队列年龄/性别修复，离线待发布

用户授权只改代码、prompt不动、复用回答。增加明确人口队列OR核验，全部冲突才排除；未知/可能适用/未解析队列保留，治疗臂不当人口组，登记较宽范围保留可能路径。
15例现有459项仅CFTR NCT06302270、NCT06797206由conditional变not_applicable，其他判定详细diff0。完整队列证据写审计及Ledger。Mini正文<12月/描述0–24月差异保留，新生儿采用保守非新生儿上界，不作年龄定义。
88专项通过；全量1223通过/2历史skip/1既有报告排序fail。10767保护文件含prompt、缓存、正式结果SHA不变，新模型/网络0，正式diff0，不刷页面、不promote。current原缺失完整报错已附。
报告out/step3b-cohort-20261126/README.md及verification.json。页面仍为上一批已发布定向修复结果。

## 最新节点：2026-11-26 定向修复及11项召回已发布最新缓存/页面

用户授权复用模型发布：15例全部预验收后通过results.run_case落盘；9改判/33相关性移出（分支diff9状态/63移出）与离线结果一致。PFN1 8+GRIN2B 3均保留conditional，15页面HTTP确认最新批次且11项可见。两例refresh_scope附最新召回验证来源，其他新检索命中不扩跑；DPPM相关性疑问仍保留。新模型/外部检索0、费用0，10491保护文件及既有3b缓存SHA不变，其他章节行动不变。current原本缺失，完整报错保留，未promote。报告out/step3b-final-publish-20261126/README.md及verification.json、diff；本轮批次20261126T155111–155112Z。后续费用账仍沿用eleven原state。

## 最新节点：2026-11-26 PFN1/GRIN2B再次检索，11项召回确认

用户仅授权两例重新检索/候选筛选。通用ALS/DEE全名和缩写原已存在，实际请求验证通过，无需重复改代码。隔离免费API29查询/33页完整下载，现役plan及相关性guard确认11/11进入analysed（PFN1 8、GRIN2B 3且两分支均命中）；11项输入与已有原答一致，复用核验均conditional，新模型0/$0，其他新命中不扩跑。51专项通过，10682保护文件SHA不变，正式缓存/页面未刷新。NCT06092346的DPPM相关性疑问仍未消解，召回成功不称临床适用。报告out/step3b-recall-recheck-20261126/README.md及逐项verification.json、target-screening.json。

## 最新节点：2026-11-26 3b定向冲突与相关性修复，离线待审

用户明确授权两处定向修复；此前“全面拿掉最后关卡”已撤销，本轮不是恢复全采纳。增加原文/事实锚定的合并症、合子状态、非无义变异、遗传型豁免冲突支持，模型调用前增加疾病基因/肿瘤相关性及血小板方向守卫；未知事实和复杂替代队列保留。15例492项现役pipeline离线重算，模型/网络0：9项改判，33项相关性移出（对应9状态行/63移出分支行）。61意见本轮消解12、原正确保持3、缺信息保持7、尚未消解39；两项孕妇/儿童队列仍待修。正式15例diff0，6415保护文件SHA不变，未刷缓存/页面、未promote；current原本缺失，完整报错保留。74专项通过，全量1197通过/2历史skip/1既有报告排序失败。报告out/step3b-targeted-20261126/README.md，review-61.md逐条对照、diff及change-explanations.json完整解释。后续付费仍从原eleven state续账，本轮费用0。

## 最新节点：2026-11-26 新召回11候选补跑完成并发布

用户“直接跑算了”授权：按现行计划/完整请求键检查11候选缓存0命中，非高峰11新调用全部成功，无重试/未知费用。PFN1 8项、GRIN2B 3项均conditional（尚需核实资格）；两病例最新缓存及页面HTTP逐项确认可见。原候选状态/其他章节不变；15例status_diff仅14新增分支行（8+3×2）。仅扩这11项，不包含其他宽检索新命中。
新增费用$0.002862198；沿用原$0.26总帽，累计占用$0.095659378（含原未知预留$0.0041335），剩$0.164340622。后续从out/step3b-eleven-20261126/state.json续账，不能回退旧all-run状态或重置预算。原费用日志/缓存保留。完整报告同目录README.md、verification.json、diff/；current仍原本缺失，完整报错保存，未promote。模型原答缓存保存，发布阶段无新调用；Step1/2/4/5未改。

## 最新节点：2026-11-26 3b最新判定已复用旧结果发布缓存和页面

用户授权不跑新模型：15例使用已保存试验和模型原答，通过现役pipeline重新核验/组装，全部预检查通过后由results.run_case发布.cache/step3b及正式账本。15页面HTTP确认最新批次；3状态变化和1措辞变化与离线审核一致，其他章节行动不变、检查无fail。模型/外部检索0，Step1/2/4/5、原LLM缓存及费用账SHA不变；批次标记saved_studies_and_model_answers，保留旧检索时间，不称新检索。新召回尚无模型回答的11项未纳入。本次未promote，current仍原本缺失，完整报错保存。报告out/step3b-publish-20261126/README.md、verification.json、diff/diff.md；15最新批次20261126T130409–130410Z。

## 最新节点：2026-11-26 3b通用疾病基因规则已修改并离线检查

用户明确批准推广到非基因治疗/ASO：删除研究类型和治疗方式门槛，保留明确基因要求、全患者基因、替代队列/主体/范围核验。普通随机治疗臂不当替代疾病队列，未明确对照保留；ACMG/AMP标准不当疾病路径，检测/取样/可选条款不作为排除依据。43专项通过，15例481项原试验/回答离线回放，3项conditional→not_applicable：COL1A1 NCT05432466、NCT05994664；PFN1 NCT05725759（要求SOD1）。OTC NCT07667387仅依据措辞变化。MPEDS有独立对照，保留conditional。正式输出diff0，模型/网络0，未发布页面、不promote；current原本缺失，完整报错附out/step3b-general-gene-20261126/README.md及current-diff.log。未包含新召回但未调用模型的11项，不称新检索全跑。

## 最新节点：2026-11-26 3b基因事实已与Step2亚型状态解耦

按用户明确授权，pipeline使用Step1全部报告基因，ambiguous不清空，跨分支基因保留；既有单一分子治疗靶点/队列范围/引用规则保留。模型分子冲突审计新增来源和证据边界，不推其他基因阴性。37专项通过；15例481项已存试验原答离线回放状态变化0，仅OTC靶点说明已确诊改已报告的1项详情变化。正式账本/页面不更新，正式diff0；current原本缺失，完整报错保留，不promote。模型/网络0，报告out/step3b-gene-facts-20261126/README.md。COL1A1两项因现有分子治疗范围门槛仍待复核，不代表已建立其与COL1A1的治疗关联。

## 最新节点：2026-11-26 ALS/DEE 11项召回已核验；COL1A1 guard仅评估

按用户指定补充PFN1通用ALS及GRIN2B通用DEE全名/缩写，保留其他缩写过滤与显式家族策略。隔离免费检索、实际plan验证11/11进入待模型筛选，34专项测试通过；模型0，正式账本/页面不刷新。对改前diff0；current仍缺失，完整输出保留。报告out/step3b-recall-20261126/README.md。
COL1A1两冲突除Step2 ambiguous外，也受single_target_conflict分子治疗范围限制；离线传入COL1A1仍accepted=False。病例无COL3A1阴性证据，建议保留证据核验、不直接采纳模型排除；未改医学逻辑/账本或升级基线。

## 最新节点：2026-11-26 新版3b 15例已运行并发布页面，医学差异待审核

用户“跑吧”授权，DMD沿用延期，4正式评测不跑；本轮$0.26总帽、非高峰、按上次报价HTTP快照及请求键运行。15例全部完成且自检无fail，15页面HTTP确认显示最新批次；338有usage请求+1次网络失败，已知$0.088663680，未知预留$0.004133500，预算占用$0.092797180；全局/本轮已对账，非精确总实付。生产其他步骤/正式HTTP缓存不变。
首AGXT暴露3b刷新丢失旧3c反向see_also链接：同一返回NCT保留既有链接后自检通过，资格逻辑不改；一次Python TLS失败与隔离脚本http命名遮蔽已留痕，费用不清零，同一请求体改隔离curl完成。1143测试pass/2历史skip/1既有报告排序失败。
对改前15例788→1139行动×分支行：384新增、33移出、168详情、3状态变更，全在3b。COL1A1两个COL3A1试验与EIF2B1一个Cree/EIF2B5条款试验not_applicable→conditional，需人工复核，不代表已满足；检索移出部分一般ALS研究等，存在召回风险，不能称临床全验收。current仍原本缺失，完整报错已附，不promote。报告out/step3b-all-run-20261126/README.md、verification.json、against-before/diff.md、change-review.json；原结果/快照/逐请求/完整费用日志同目录。

## 最新节点：2026-11-25 3b检索词已按授权调整，缓存报价完成，未跑模型

移除MONDO首父级机械扩充；新增search.py，使用疾病标准名/完整同义词、18组有MONDO来源的显式家族、病例报告基因独立补查。短符号用相邻遗传词组消歧，长/带数字符号直接查；search_genes与已确认致病genes分离，模型Prompt/参数/核验不改。16例含DMD仅检查，免费HTTP隔离快照已完整下载，449唯一请求/9命中/440缺失（原9643，减95.44%）。非高峰OTC样本外推$0.12668、512输出情景$0.25519，非保证；首轮保守预留$1.73373，全部截断重试极端$11.03687。排除延期DMD：338缺失，$0.10268/$0.20140情景，首轮预留$1.35378。模型0/$0，未刷新正式账本/页面、未导入HTTP正式缓存。
1142活动测试通过/2历史夹具skip/1既有报告排序失败；12097保护文件SHA不变，对改前15例788行详细diff0；原current缺失，完整报错已附，不重建不promote。缓存盘点不代表临床验收；基因查询仍可能命中体细胞/标志物，短语检索存在召回限制。完整报告out/step3b-search-20261125/README.md、quote.json、filled-audit.json、family-provenance.json及diff。尚未授权或执行模型运行。

## 最新节点：2026-11-25 3b全案例缓存检查与隔离报价完成

12练习+4复测含DMD只检查；4正式评测排除。原正式缓存仅OTC新版9答齐全，其余15例缺39个不同检索首页。免费CT.gov隔离下载185页后，按现役生产plan/request缓存键计9652唯一请求、9命中、9643缺失。模型0/$0，正式输出/缓存/预算等11064文件SHA不变。按9份OTC样本非高峰外推约$2.56、512输出token情景约$5.38，非保证；首轮保守预留$37.17、全截断重试极端$240.22。数量主要来自上级词过宽（hereditary disease、congenital nervous system disorder等），建议先讨论检索范围，未改代码/医学判定或执行付费。仅疾病标准名的隔离比较缺284但会漏家族性ALS，不能直接删所有父级。报告out/step3b-cache-audit-20261125/README.md、quote.json和逐例audit；下载仅在同目录http，未导入正式缓存。旧blind另外单列缺父级或上游过期，未计金额。

## 最新节点：2026-11-25 用户要求永久删除旧 run 归档

已按用户“旧数据删掉”指令删除项目外 run-history-20261125-complete.tar.gz 及对应 manifest，旧 run 不再可由本次归档恢复。最新批次、近三天 sessions、正式输出及原始缓存不变；runs 保留规则说明已同步。

## 最新节点：2026-11-25 runs 历史数据整理完成

用户要求每步保留最新、sessions只保留近三天。按实际最后活动时间保留72小时内8个完整session；3a保留每病例/来源章节最新16批次，3b保留每病例最新2批次；out/current同步最新3a选择。14645个过期/历史实验文件先逐项归档并校验再移除，原约1.85GB压缩为264.5MB，归档在项目外/Users/a00/aitx-archives/run-history-20261125-complete.tar.gz，runs约17.5MB。原始缓存、正式结果、全局费用/预算11064保护文件SHA不变；11页面显示最新批次。专项40通过/2历史夹具原规则跳过。新增cleanup_run_history.py默认仅预览，显式apply归档清理，未设自动任务；历史实验路径需从归档恢复。未改医学规则/Ledger/基线，原baseline本地删除状态未动。详情out/run-retention-20261125/README.txt及verification.json。

## 最新节点：2026-11-25 OTC新版3b完整缓存重跑通过

用户要求只跑OTC验证全链并显示最新。refresh_step3b.py --case PRAC-OTC --cache-only，LLM预算0，退出码0；9份模型回答全部复用缓存，无新增模型请求/$0。检索保存记录33条含重复/21项去重，保留7、排除14；15自检pass/1既有名称归一化warn/0fail。新批次.cache/step3b/PRAC-OTC/20261125T154952.484174Z complete，正式账本发布，页面HTTP200且显示该最新批次。其他步骤行动不变；1361保护文件仅正式OTC账本更新。对改前15例788行status_diff0；原current仍缺失，完整报错保存且未promote。生产代码/提示词/医学规则不改、不跑其他病例；缓存重算不代表今日联网核实登记或新模型调用，也不等于临床资格验收。完整审计out/step3b-otc-run-20261125/README.txt、audit.json、run.log及diff。

## 最新节点：2026-11-25 3b单链重构与旧实现退役

按用户授权重写简洁架构并删旧实现。生产入口统一aitx/step3/b/pipeline.py；screening负责计划/请求/核验，rules保留13个现役规则（AST不变），records为唯一落账器，results/presentation继续负责.cache/step3b批次和最新页面。旧criteria逐条映射链、_record、plan_branch/祖先遍历、5个依赖旧实现的实验/回放脚本退役，专属测试连同原源码已快照在out/step3b-rebuild-20261125/before，retired.json逐项说明；现役规则与报告测试保留/移植。Prompt/版本/参数/完整输入不变，8组改前冻结账本逐字段相等。未调用模型、未重跑正式病例、未改医学结论或基线；原current仍缺失，完整报错保留。旧测试退役不等于旧缺陷修复；当前仍是Conflict-Only初筛，不恢复旧逐条条件解释能力。专项73通过，全量1136通过/1既有报告排序失败；原另外3失败随旧映射专属测试退役而非修复。正式15例788行对改前diff0，26861数据文件SHA不变，AGXT/OTC页面HTTP200。3b Python实现1377→861行。详细架构见docs/step3b_contract.md，验证在同审计目录。

## 最新节点：2026-11-25 3b运行保存与最新页面接线整理

3b生产筛选/提示词/判定不变。独立refresh CLI改调aitx/step3/b/results.py，批次保存在.cache/step3b/<病例>/<UTC批次>，包含执行状态、病例、改前账本、完成账本和页面卡片；正式卡片转换移至presentation.py，旧导出CLI复用。页面/监听读取最新批次，失败显示错误不退旧；保留旧账本/导出兼容。现有AGXT-c33dup实验卡片与OTC正式卡片逐字复制入缓存，保留来源性质/原保存时间，旧文件不删。无病例重跑/模型调用，不修医学规则。详情与测试、保护哈希、完整status_diff输出见out/step3b-wiring-20261125；基线current开工前已缺失，不重建或promote。旧逐条条件映射回放代码仍有引用而保留，完整Step3仍受3a适配未完成限制。专项14通过；全量1237通过/4既有失败（与改前历史日志一致）；26855旧文件SHA不变，两页面HTTP200。

## 最新节点：2026-11-25 COL1A1与NF1引用错误已离线修复

用户明确批准第1项修复。复用现有显式hydrate_xml_references，仅恢复COL1A1 NBK1295块6与NF1 NBK1109-serial1块10；原选中ID/text/xml不变，5/6条引用均按提交XML的xref/rid恢复且在完整源XML中唯一定位。原response/parsed/成功结果保持字节不变，execution保留previous_error。两章节7/7和10/10完成待内容审核；40相关离线测试通过，页面HTTP200并展示最新完成状态。0模型调用/$0，最新预算仍按CFTR halves的0.319720769美元；未改生产代码/Ledger/判定/基线。1227文件保护核验仅两execution变化，新增两selection；快照/审计/引用目标/测试/page-check见out/step3a-col1a1-nf1-reference-fix-20261125。CFTR6行因条件适用范围争议暂不计确认漏选，筛选范围尚未统一，本次未改。

## 最新节点：2026-11-25 CFTR整表对半实验完成，6行仍未选

用户批准Table6b对半拆分试验；18行9/9、边界不跨rowspan，两半保留共同上下文/表名/完整表头/全部脚注。只替换输入XML，病例/其他Prompt/low/65536不变。2并发非高峰curl各1次、无重试，实际输入6490/6840tokens（原10284），均stop。第一半9行全选，第二半只选不育通用/男性2行；原6行全未选，原11行保留，女性行未选。此次拆小没有解决问题，不能证明8k阈值或仅凭此归因模型能力；尚未改Prompt。费用0.003428628美元，原$1总帽累计占用0.319720769，余0.680279231，原未知预留0.2092661保留。后续预算必须从out/step3a-cftr-halves-20261125/campaign-budget.json继续，不能回退旧账。1227正式结果保护SHA不变，实验未发布替换页面；生产代码/Ledger/判定/基线不改。记录同目录README.txt和review.json。

## 最新节点：2026-11-25 AGXT-c508GA第2块引用已离线恢复

用户要求逐个处理并批准首块：新增显式hydrate_xml_references，将来源关系从已提交XML的xref/rid确定性派生，模型references仅保留原始记录；原选中ID/范围校验不放宽，旧默认hydrate/run/recover及冻结Prompt不改。本次只恢复AGXT-c508GA NBK1283块2，N0043及text/xml原样；两文献rid在完整XML均唯一存在，位于Management映射外，未伪造N编号。response/parsed及其他成功结果原字节不变，新增selection，execution保留previous_error并显示12/12完成待内容审核。40相关离线测试通过，外网/LLM阻断恢复0调用/$0。改前代码/execution/结果哈希和核验见out/step3a-agxt-reference-fix-20261125/README.txt、audit.json、source-citation-targets.json。其他病例/Step1-4/Ledger/判定/基线不变；COL1A1与NF1引用错误、CFTR6行漏选未处理。原整批审计快照保留，预算仍$0.316292141。

## 最新节点：2026-11-25 3a逐例重跑结束，106/109协议通过，内容仍待复核

用户在TLS失败后授权继续、必要时逐例跑。保留成功原答，隔离脚本改用curl发送同一llm.chat请求，生产Prompt/low/65536/校验未改；病例章节顺序，先4并发，后未发出块及剩余网络失败改串行。11例16组合109目标块均有回答：106协议通过，3引用错误（AGXT-c508GA NBK1283块2、COL1A1 NBK1295块6、NF1 NBK1109块10），原答保留不补修/不重跑内容错误；8例13章节完整，4例无来源仍未知。
114尝试＝109有usage＋5TLS无响应；已知$0.107026041，未知预留$0.2092661，总占用$0.316292141/$1，剩$0.683707859（不是完整实付或新预算）。所有失败重试沿原总帽计费，累计账不得重复相加。CFTR Table6b抽查比前次实验少选6行（肠梗阻/反流/肝病/糖尿病/盐丢失脱水/心理健康）；完整原表仍展示，不能宣称医学验收通过。
11页面HTTP通过，16最新章节可见，执行按钮保持移除；106成功原答恢复一致、请求与冻结输入一致，11517原保护文件SHA不变，Ledger/判定/Step1/2/基线未改。完整连续账及失败出处见out/step3a-campaign-20261125/README.txt、final-audit.json、cftr-table-review.json。此次已停止调用，不自动为内容问题追加付费。

## 最新节点：2026-11-25 3a获批$1重跑因TLS中断停止；页面去掉执行控件

用户批准11例16章节109块整轮$1硬上限、全局4并发、失败不自动重试。非高峰余额13.72 CNY且可用；仅运行进程日帽调整为此前当日0.040894302+$1，不改配置。首AGXT-c33dup首组4请求：2成功，1/4块TLS EOF无响应，后续105请求未发，按约定全局停止。已知费用0.003425736；2次实付未知、预留0.0835058；合计预算占用0.086931536，剩0.913068464，非实付精确值。成功回答逐字原文恢复与已存selection一致，未声称医学全验收。保留失败请求和原答，不自动重发；重跑总账不得重置。页面最新该病例显示失败/2完成，其他病例未新建批次。11517旧保护文件SHA不变。out/step3a-campaign-20261125含run.py/campaign.json/run.log/audit.json，正式新批次runs/step3a/PRAC-AGXT-c33dup/structure-v2-20261125-NBK1283。
用户要求去掉页面“独立Step3a”操作区：整块批次操作、恢复、预算、付费执行按钮与专用JS已移除，保留结果/状态/原文；CLI/API仍可用。相关30项离线通过。

## 最新节点：2026-11-25 3a结构拆分接入与离线准备完成

生产3a已接入主题/整表分块和只读上下文，正文ID越界即停止；8000为结构拆分触发线，整块含上下文硬上限16000估算tokens，本批最大9959。small章节原Prompt不变，结构块补上下文规则，low/65536不变。页面每来源章节分别选最新批次，独立锚点/操作控件，完整原表高亮选择而不删行破坏rowspan，选择不等于适用。
11例16病例章节组合109块全部准备就绪，5524正文节点各覆盖一次/46表完整，4例缺来源保持未知。仅out/step3a-production-structure-20261125/prepared，未发布或调用。CLI/页面4并发；未来病例/章节顺序运行确保全局最多4请求。粗费用代理0.09–0.33美元非保证；4.49038435美元是全部满65536输出的极端预留，不是预计实付；预算逻辑未改，单章最大预留0.4985，日帽未提高，真实调用仍须先明确硬上限。相关36通过，全量1229通过/4既有失败。11517保护文件SHA不变，Step1/2、Ledger/判定未改；current基线原已缺失，status_diff完整错误输出已留，不声称基线diff0。页面HTTP/浏览器检查通过。详out/step3a-production-structure-20261125/README.txt。

## 最新节点：2026-11-25 3a 结构拆分与上下文分离实验通过两样本专项检查

用户要求试验拆法。仅隔离脚本：5段原文拆10主体块，1360非标题节点按序各覆盖一次，9表完整。AGXT RNAi与CFTR Table6b各一次非高峰deepseek-flash，low/65536不变；新增上下文/正文说明及实验选中ID范围约束，原文与上次逐节点相同。AGXT5/5正文且不再选共同总表；CFTR17/17相关/条件行，排除女性专属行及脚注12，男患者/伴侣说明、表头/其余脚注保留。原文片段逐字一致，无补修/重试。选中行拼表仍需处理rowspan，未实现紧凑渲染；不声称全病例医学验收。费用按项目率0.006002886美元，最大合计预留0.0894152，11555保护文件SHA不变。生产代码/Prompt/阈值/Ledger/基线/当前页面结果未改。记录out/step3a-structure-context-20261125/README.txt与review.html。

## 最新节点：2026-11-25 3a 两个 XML 结构实验完成，筛选仍偏宽

用户批准两代表输入并检查。仅AGXT-c33dup RNAi主题（带总述/Table7上下文）及CFTR完整Table6b各真实deepseek-flash一次，原Prompt/low/65536参数，无重试，非高峰；最大预留合计0.08919995美元，按项目费率记账0.004103268美元。实际输入9304/10142tokens，两次stop。AGXT主题5/5节点、CFTR预设17/17行覆盖，原文/表格/合并单元格/脚注保真；AGXT把共同总表也选为内容，CFTR整表全选含女性患者专属行，筛选不够精确，不作医学验收通过。两个约1万token输入成功，不据此推广全量；AGXT带上下文仍9514 XML估算tokens。11521保护文件SHA不变，生产阈值/Prompt/Ledger/基线/当前页面批次不改。完整输入/回答/预设检查/费用/审阅在out/step3a-structure-two-20261125/README.txt及review.html。

## 最新节点：2026-11-25 首批旧代码与重复准备结果清理完成

用户明确批准执行首批清单。删除fallback四个无引用辅助函数及专用hashlib/GUIDELINES，genereviews两个无引用上下文函数；其余函数AST与改前完全一致。删除out/step3a-source-selection/PRAC-OTC-prepared的29文件，逐文件证实有SHA一致的保留副本；当前两份OTC章节阅读结果、其他历史记录不删。全离线1225通过/4既有失败，未改测试；静态669→663函数、无零引用候选。11645保护文件SHA不变。基线原已缺失，status_diff前后均报错，完整输出与源码快照/局部补丁/保留副本清单见out/legacy-cleanup-applied-20261125/README.txt。不重建基线、不promote、不调用模型。

## 最新节点：2026-11-25 页面各步骤自动展示最新保存结果

用户要求所有Step自动展示最新结果。3a页面/运行按钮按最新批次读取，不再依赖current索引；执行批次按首个request.at、未执行按plan修改时间排序，未完成不退旧。current索引仅保留CLI默认操作用途。Step1/2沿用当前输出；3b按账本/导出保存时间选择；3c–3e只读展示现存账本记录；Step4展示已保存报告并说明未接入新3a；Step5无保存结果明确未知，不执行核查。Markdown报告加入文件监听。39相关离线测试通过，OTC页面HTTP200及内容验证通过，200批次文件及11317受保护缓存/输出哈希不变。无模型/重跑/判定变更，记录out/step3a-latest-display-20261125/tests.txt。

## 最新节点：2026-11-25 3a 批次归档与显式展示索引完成

用户批准整理3a数据。两份OTC批次从out/3a迁至runs/step3a/PRAC-OTC/，保留原批次名，200文件逐字一致；out/current.json显式指定PRAC-OTC-rerun-c4-20261125，不再按mtime选批次。prepare默认独立UTC时间戳目录，select显式切换但不代表审核；run/recover --case-id读当前索引，--output仍可用；已完成recover直接返回不改文件。32相关离线测试通过，CLI与页面HTTP200核验通过，11317受保护缓存/正式输出哈希不变。无模型调用、无病例重跑、无Ledger/判定修改。只整理3a，3b/数据集/历史实验暂留；记录out/step3a-storage-20261125/README.txt。旧批次内绝对路径保留为历史来源记录。

## 最新节点：2026-11-25 Step 3 a/b 目录迁移完成

按用户批准计划，3a 实现在 aitx/step3/a，3b 在 aitx/step3/b，总编排在 aitx/step3/pipeline.py；共享与 c/d/e 暂留 evidence。命令保持，3a Ledger 适配仍明确报错。30 个改动 Python 文件实现 AST 除导入/资源路径外相同，提示词逐字不变。专项28+156通过；全量1219通过/4失败，4项均在改前源码复现，未改判定修测试。当前 baseline 在开工前已缺失，两次 status_diff 完整报错保存在 out/step3-layout-20261125，不能称基线验收通过。正式输出/runs未变；GenCC已有下载片段在期间变为完整缓存，触发来源未确定，已保留差异，不能称缓存全部不变。详见该目录 README.txt、迁移清单及测试日志。

## 最新节点：2026-11-24 STOP PEDS两药窗口v4聚焦实验通过结构核验，待审核

用户再次允许仅一轮、只检查两药。完整User EligibilityCriteria与v3相同，未传患者；仅Prompt补足显式op和NOT窗口格式，复用原v3核验器，不改校验逻辑或原始回答。真实非高峰deepseek-flash一次、不重试，1461输入/554输出，项目费率$0.000513918。

本次四个药物原子均有op:atom，引用全部逐字；源式NOT(A OR B)与独立AND(NOT A,NOT B)各NOT均有相同>=3月lookback窗口，and also按AND保留。原核验器通过，六项专项离线通过；患者两药实际使用史仍unknown，不能据此称患者符合或整个non-HEMT已验收。enrollment锚点来自完整语境，末句未逐字含该词。

报告docs/experiments/step3b_stop_peds_drug_windows_v4_20261124.md；out/step3b-stop-peds-drug-windows-v4-20261124含真实输入/回答、v1-v2-v3-v4聚焦对照、Prompt/模型diff及完整status_diff。10196保护文件SHA不变，正式前后diff0，对current196既存差异逐项相等。不改生产/账本/基线，已停等审核，不扩展其他问题。

## 最新节点：2026-11-24 STOP PEDS两药否定/窗口聚焦实验完成，仍未完全正确

用户仅允许一轮、只检查non-HEMT末尾两药。完整EligibilityCriteria作上下文、无患者输入，一次真实非高峰deepseek-flash，1097输入/537输出，项目费率$0.00048675，不重试。模型已独立NOT两种药物，所有quote逐字通过，保留原NOT(A OR B)与等价AND(NOT A,NOT B)。但四个药物原子缺op:atom；独立窗口在正向atom而非约定NOT，源式无窗口，不能放行。患者用药史unknown，不作资格判断。cohort标签含cohort与检查器ID不同，仅标签别名，不当医学错误依据。

6专项离线通过；原始回答未补字段或改写。报告docs/experiments/step3b_stop_peds_drug_windows_20261124.md，out/step3b-stop-peds-drug-windows-20261124含逐引用/结构/窗口审计、v1/v2/v3聚焦对照、费用及全部status_diff。10173生产/基线/旧缓存/v1v2保护文件SHA不变，正式前后diff0，对current原196项逐项相等。只报告这一条部分改善仍不正确，已停止等审核，不扩其他问题。

## 最新节点：2026-11-24 STOP PEDS non-HEMT显式NOT v2实验完成，部分改善待审核

用户允许仅本研究一次LLM调用。独立实验Prompt禁止布尔0/1、要求显式NOT/AND/OR、两支资格、未来计划及独立药物窗口；完整User原文与上次逐字相同，不传病例。真实非高峰deepseek-flash一次、不重试，1761输入/5415输出，项目费率$0.003456702。4专项离线通过。

non-HEMT布尔数值2→0处、NOT0→4个；正向资格、HEMT>=3月lookback、未来一年无计划恢复。两种药物仍NOT(A OR B)共享窗口，未独立NOT，且taking lumacaftor-ivacaftor子引用不是原文，整条仍rejected/unknown。另有CF父子引用、主HEMT疗程字段和四条within原子枚举问题；全20条机械核验18/2→13/7，规则变化使该数不能作医学准确率。未修改原始回答、未放松校验或补票。

报告docs/experiments/step3b_stop_peds_not_v2_20261124.md；out/step3b-stop-peds-not-v2-20261124含真实messages/response、提示词diff、完整模型diff、全20条对照、NOT子树和逻辑审计、费用及完整status_diff。10146受保护文件SHA不变，包含生产/基线/旧缓存/上一实验；正式前后diff0，对current196既存项逐项不变。不发布、不promote、不扩病例，完成后停止等审核。

## 最新节点：2026-11-24 STOP PEDS完整上下文实验完成，待用户审核

用户明确启动后仅NCT06654752真实DeepSeek非高峰请求1次、不重试，完整原文含标题/嵌套/Markdown原字节输入，模型不接收患者事实。返回20条件/24outline，六条已审核专属条款队列归属6/6，年龄[6,19)/[3,6)完整；15岁main/non-HEMT条件性、preschool年龄路径不符，整体仍conditional，仅实验结果。

18条件通过机械引用/结构核验，2条拒绝unknown：CF组合引用压平换行（空白归一能匹配但本次严格连续引用拒绝）；non-HEMT用数字0编码否定，未输出NOT且部分资格/药物否定范围未独立结构化。时间窗部分仅留引用，不称完整医学验收。初次严格分析报错后仅离线逐条保留拒绝/unknown，原始回答不改、不补模型票。5专项通过；1227输入/4795输出，按项目费率$0.00306105，模型deepseek-flash。

报告docs/experiments/step3b_stop_peds_full_context_20261124.md；out/step3b-stop-peds-full-context-20261123沿用准备日期，含真实原回答/新旧完整diff/逐条结构与轨迹/费用/保护核验。10114受保护文件相对准备前只有此前用户批准的aitx/llm.py密钥变量改名不同；正式账本/基线/旧缓存不变。正式前后diff0，对current196既存项逐项相等；不发布、不promote、不扩其他病例、不自动续跑。停在用户审核点。

## 最新节点：2026-11-23 ENACT条件遗漏最小修复完成，仅离线候选

用户批准仅NCT07148739五条已核对条件，复用reviewed_rejected_lines配置并原位替换；r6/r8/r11/r12从not_assessed改unknown，r7保留完整肺病稳定性原句unknown（含否定/OR/抗生素4周），不解释复杂逻辑或放行拒绝映射。原check_mapping/sign_ok/提示词/缓存键不变，不把其他rejected自动当临床条件。

仅ENACT专项6测试通过，原缓存生产map_study/_record阻断socket/LLM回放；8接受/5拒绝完全相等，13要求及编号保持，范围外8条逐字段不变。候选仍conditional，reason更新为other及other trial criteria；新增完整inc5 verified代码证据1条，旧证据/其他行动/旧provenance和先例保留。自检15pass/1既有warn/0fail。正式/全部baseline/旧HTTP+LLM缓存10053文件SHA不变，不发布、不promote、不写批准记录，网络0/模型0/$0。

报告docs/experiments/step3b_enact_fix_20261123.md；out/step3b-enact-fix-20261123含改前快照、候选、完整新旧行动/行对应、完整字段diff、scoped-code.patch和全部status_diff。候选对改前1详情0状态；对current197项（15详情/3状态/18新增/4删除/157缺基线），原196项逐项保留仅新增ENACT详情。正式前后diff0，对current原196项不变。ETI/STOP此前候选未混入，不运行其他研究回归。

## 最新节点：2026-11-23 STOP PEDS队列最小修复完成，仅离线候选

用户批准仅修NCT06654752；六条已审核原文绑定队列，复用alternative/status_of队列内AND/队列间OR及共同fail优先。完整区间[6,19)/[3,6)确定性比较，原映射校验/拒绝不变；15岁仅main/non-HEMT活动，preschool原文转审计。HEMT疗程与非HEMT完整复合条款保留unknown，不用“用药存在”证明疗程或适用性；肺功能能力/ppFEV1绑定对应队列，共同CF诊断/排除保持。

仅STOP专项9测试通过；真实原缓存生产map_study/_record回放，socket/LLM阻断，映射完全相等。候选26→25要求，最终仍conditional、reason不变，自检15pass/1既有warn/0fail；共同要求仅局部顺序ID移动，旧证据和其他行动全保留。正式账本/全部baseline/旧LLM缓存5831文件SHA不变；不发布、不promote、不写批准记录，不运行其他研究回归，模型0/网络0/$0。

完整报告docs/experiments/step3b_stop_peds_fix_20261123.md；out/step3b-stop-peds-fix-20261123含改前快照、候选、原/新完整行动、逐行对应、字段级完整diff、scoped-code.patch及全部status_diff。候选对改前仅1详情0状态；对current197项（15详情/3状态/18新增/4删除/157缺基线），原196项逐项保留，唯一新增STOP详情。正式前后diff0、对current原196项不变。ETI候选未混入，本轮仍未医学验收exc7等其他问题。

## 最新节点：2026-11-23 ETI已确认拒绝片段最小修复完成，仅离线候选

用户确认仅修NCT07809867 inc1：保留原校验（>=8仍拒绝）和CF诊断pass，必要的F508del/ETI稳态片段不再消失。config/reviewed_trial_rejections.json精确登记人工已确认的NCT/条款/完整原文/两条拒绝理由；criteria只为仍未处理的已审核拒绝追加完整条款unknown，未审核/伪造/重复或已有有效映射的片段不自动变医学条件。旧模型票/提示词/数字比较规则不变，证据code来源保真，不重构。

仅ETI专项5测试通过；原缓存+生产map_study/_record离线回放，socket/LLM阻断，模型0/网络0/$0。候选保留原12要求及全部旧字段，追加r13 unknown和verified证据4cf0fa2b17f2，状态仍conditional、reason补充other trial criteria；整例候选自检通过。正式账本和baseline按用户边界不写回、不升级，所有旧LLM缓存SHA不变。

out/step3b-eti-rejected-fix-20261123含改前快照、eti-replay、保护核验和完整status_diff：候选对改前1详情0状态，对current197既存+候选项（15详情/3状态/18新增/4删除/157缺基线）；正式前后diff0、对current仍196项。报告docs/experiments/step3b_eti_rejected_fix_20261123.md。只保存candidate-ledgers，不运行其他试验回归，不处理STOP PEDS/ENACT等余项。

## 最新节点：2026-11-23 CFTR 3b缓存重放完成，逻辑核对未通过

用户要求跑PRAC-CFTR-F508del核对。仅冻结缓存3b：10个map_study真实缓存命中、当前plan_branch分类/排序/K上限复现一致、_record重建115条，自检无fail。1810去重=10逐条+105预筛不符合+59超限+1636过滤；105失败含104年龄/3性别（2重叠），不是全部年龄。10conditional/105not_applicable，核心字段与正式账本完全一致；未刷新试验/不跑整例Step1–5，真实LLM0/$0。

原文核对发现4项待修：NCT07809867同一inc1部分映射失败，F508del与ETI稳态8天条件未生成要求行；STOP PEDS队列年龄/HEMT仍平铺AND，学龄前无关unknown、6到<19下界映射拒绝；ENACT三联药two weeks、Pa培养、Three次IV加重及BMD近期用药等临床未映射条件被not_assessed忽略；STOP360AG排除段否定句极性待审。没有据此改代码或判定，不当医学验收通过。

产物out/step3b-cftr-replay-20261123含1810原缓存内容、10映射拒绝、115重放行动、4问题、改前快照与完整status_diff。正式前后diff0，对current196项原样保持（14详情/3状态/18新增/4删除/157缺基线）；正式输出和baseline全部SHA不变，不promote，不运行评测Step3+。报告docs/experiments/step3b_cftr_replay_20261123.md。

## 最新节点：2026-11-23 3b Biobank 主体与替代队列修复完成

用户授权继续第二项。诊断/基因确认比较先检查完整条款与父项中的亲属主体，不能用本人确诊证明亲属或家族史。替代关系必须有官方组描述和对应病种原句，复用既有alternative/status_of；缺失/冲突/强制AND不猜OR。trials检索增加ArmGroupLabel/ArmGroupDescription（官方元数据已核对），旧正文提示词/模型票不变，旧HTTP/LLM缓存不写。

只更新两例AGXT的NCT02026388：r1亲属pass→unknown，r4本人仍pass；双方按明确来源OR（复用上轮独立保存的官方全记录、与缓存eligibility全文一致），新增verified证据d888e182b64b。共同r2排除未知仍在，所以整项仍conditional，不因亲属未知阻塞本人队列。其余行动/旧要求ID原文引文/旧证据/PHYOX7首项和82前言要求不变。209离线通过、15Ledger自检通过，网络/LLM阻断回放成功，模型0/$0；仅额外核对官方字段元数据，不重新抓取临床记录。

改前快照/完整输出在out/step3b-biobank-subject-fix-20261123：本轮2详情0状态，current196项=14详情/3状态/18新增/4删除/157缺基线；原194项逐条完全保留。已发布两例subject-only账本，旧生成时间/指纹保留另记update元数据，不声称整例刷新；baseline/approvals SHA不变，不promote，不读评测/DMD，不重建Step4/5。详报docs/experiments/step3b_biobank_subject_fix_20261123.md。

## 最新节点：2026-11-23 3b 前言招募限制首项修复完成

用户明确批准先修 PHYOX7 前言问题：标题前非空区块保留、当前显式限制与硬事实比较，fail 优先为 not_applicable。新增 enrollment_note 类型（pre ID/正文 ID 保留），独立确定性识别当前年/月年龄与性别限制；核验原句/数字/比较符/单位，未知队列/历史/条件语境保留 unknown，不调用 LLM、不改正文提示词或缓存键。旧正文队列年龄规则不扩大；新限制在其保守处理之后加入。

15 例缓存离线更新，5 例/10 试验条目追加82前言要求（1 fail+81 unknown，未知不算医学条件已验收），只有 PRAC-AGXT-c33dup PHYOX7 conditional→not_applicable：当前 only enrolling under6，患者7岁；AGXT-c508GA 年龄未知保持 conditional。其他9条只增原文/来源/未知，状态不变；所有既有行动ID/key/旧要求行/旧证据逐一不变。195相关离线测试、15例Ledger自检通过；socket/LLM阻断回放成功，联网0/模型0/$0。Biobank问题不动，评测和DMD不运行。

改前完整快照和全部diff在 out/step3b-enrollment-note-fix-20261123：对改前1状态+9详情，对current完整194项（18新增/4删除/12详情/3状态/157缺基线），原185差异键全部保留；本轮9新键，PFN1另一条原属缺基线。已发布5例note-only账本；旧生成时间和指纹保留，另记update元数据，不声称整例刷新/新鲜。所有baseline SHA不变，不promote/不写approvals。详报 docs/experiments/step3b_enrollment_note_fix_20261123.md。

# 项目背景（给 Claude Code 的交接说明）

## 最新节点：2026-11-21 已批准144条来源层关联完成；不等于条件验收

用户批准315审核中的A102（25仅上下文）与B54中的42复用已审链接，只补来源层，其他159及226不调用。新增apply_condition_source_associations.py离线入口，输出out/structure-condition-links-applied-20261121为最新独立测试Ledger：144＝119仅来源关联＋25仅上下文，写test_only元数据、现有ID/证据引用不改。447审阅分布119来源层、25上下文、132旧同文未验收、159语义待审、12身份范围待审；171仅未应用数，不是全部医学未知。来源定位439/447（已有测试原句引用指针，含25上下文，不与之相加），8现有指针缺口＝5外部来源范围+3CFTR锚点，不当正文漏抽。前21来源修复全部保留。49应用记录引用现成T/范围配对证据，但未认定旧整条条件逻辑等价；本轮新增完整归属确认0，完整归属已确认总数仍未知/未逐条验收，不能以439、144、132或49作条件准确率。

150相关离线通过，新增统计测试重过；正式/测试改前后status_diff0，对current正式185/实验1296原项逐条不变。所有既有活动行动/要求/状态/证据、Action ID/key、旧票、医学规则、生产Ledger/缓存/runs/基线不变。当前source关联3条是旧核查理由，不伪作患者条件或推荐。159/226队列原字节保留，不调用API/LLM、$0、原累计$0.100842897不变，不读四评测、不进Phase3、不升级基线。详细报告docs/experiments/condition_source_associations_20261121.md及最新out含447原对象、144应用、171未应用、8引用缺口、全部字段Diff/status_diff/保护核验。

## 最新节点：2026-11-21 条件来源21处确定性修复完成，临床归属仍未完成

用户授权仅$0补11 FDA细条件和10 CFTR锚点，不动226语义、不转移条件或判患者满足。最新产物out/structure-condition-sources-20261121：FDA原set ID/版本/日期在本地缓存逐词验证、完整标签段落和JSON pointer保留；CFTR复用G._text原渲染精确匹配XPath，保留摘要/表题/同行/list，不放宽引文校验。两盐补充和一泻药的3条多位置来源全留，范围/患者unknown。共23新背景锚点，原Evidence ID保留在历史关系，既有ID/key/条件/状态/证据/旧票完全不改。LG背景claim带位置以避免多XPath同文互相覆盖，未改全局ID逻辑。新增retain_structure_condition_sources.py离线入口；structure_test_ledger.py仅加一行，把requirements引用的外部证据加入既有上下文保存，后续重建不再漏存，未采纳旧条件结果。

447条件现132同文结构化、244证据保留归属未核、17仅外部上下文、54无活动身份；本次21来源缺口0，但315仍未完成结构化对应/归属审阅，132仅文字匹配，不等于临床正确。活动requirement新增0，患者状态不变，226及4语义/AAC/tracheostomy等原待审不动，不调用、不进Phase3。149相关离线通过，正式/测试改前后diff0，对current正式185/实验1296原项不变；旧实验产物、生产输出/缓存/runs/基线SHA不变，原累计$0.100842897不变。报告docs/experiments/structure_condition_sources_20261121.md；完整21原词/缓存/XPath/上下文、447对照、3歧义、315待审、全字段Diff/status_diff/保护核验见最新out。未读四正式评测病例，不升级基线。

## 最新节点：2026-11-21 Phase 2候选质量审计完成，未完成医学验收

用户授权$0重建15例测试Ledger并审计候选，仅应用已审核来源关系。新增audit_structure_quality.py实验入口复用原装配器/列语义/缓存，从冻结XML/缓存重装后核对旧活动记录全等，再叠加测试来源元数据。两CFTR为上位/相关关系、physiotherapist提供者与PT/OT及EDS孕期分开、Botox仅具体产品关系、glucose & fat仅完整措施对齐；无同义扩大/ID合并/key改写/条件转移，Accepted名称253/264，AAC父类和tracheostomy继续needs_review。43名称仍43/43、来源42直接+1例子，旧票不重算。

out/structure-quality-audit-20261121为最新入口：392病例×候选（388旧活动新增+4来源恢复）、340唯一ID，分7原文明示新管理来源（2支持措施+5专科管理）、84重复/关系、41目的/剂量/说明、34检查/风险、226待语义。全为审计数据，不删除行动，不导出推荐；新患者推荐0，医学Recall未评。旧319行动=277活动身份+42身份差异：27已审来源、4关系未判等价、1OI例子、9既定、1tracheostomy待审（AAC父类另待审）。447旧要求=132同文结构化、223原证据归属未核、17仅外部上下文、54无活动身份、21未配对（11 phenylbutyrate FDA细条件未随主引文保留、10 CFTR摘要/标题/拼接锚点）。这些是真实条件接入待办，不是315正文漏抽，也不能宣称医学完整。此轮只审计，不补条件或临床判定。两未编号疾病交叉引用、10原无多数句继续未知。

147相关离线通过；正式/测试改前后status_diff0，对current正式185、实验1296原项逐条不变。所有既有活动行动/条件/状态/证据、旧票、生产输出、缓存/runs/基线SHA不变，原累计$0.100842897不变。详细报告docs/experiments/structure_quality_audit_20261121.md和out下完整候选/旧行动/447条件/21缺口/全字段Diff及status_diff。reassembled仅原装配检查点，旧名称统计不是新审计结论。不读四评测病例，不进Phase3、不自动调用或升级基线。

## 最新节点：2026-11-21 五项来源处置获批并完成

用户仅批准steroids登记OI原文例子、helmet同段缓存、Stressful situations avoid候选、GRIN2B/OTC speech共享尾词。新out/structure-five-approved-20261121已应用；来源候选4条复用Phase1或旧speech身份，仅存测试来源元数据/候选目录，未改活动行动。steroids不是独立行动恢复。43原文43/43，直接对应仍42/43，加1例子来源保留43/43；Accepted名称250→252/264，剩5（两CFTR/physiotherapist/宽类botulinum toxin/完整glucose&fat）。本次余4语义+AAC父类/tracheostomy两needs_review，不自动处理。145相关离线通过，正式/测试改前后diff0、对current185原项不变；所有旧票/ID/key/条件/状态/证据、医学规则、生产输出/缓存/runs/基线保持。仅19条背景锚点和批准来源元数据新增，旧out冻结。模型/API0、$0、原累计$0.100842897不变，不进Phase3、不读评测病例。脚本apply_structure_reviewed_five.py；详细报告docs/experiments/structure_five_approved_20261121.md。

## 最新节点：2026-11-21 已批准26项来源技术处理完成，23对应/4待审

用户批准42项审核中的26项$0技术处理，不合并ID或改key；3缺口和AAC父类只保留needs_review，不改旧票/不追认成功，7语义暂缓，其余保留。已在独立out/structure-source-links-applied-20261121完成：23条来源对应、helmet/Stressful emotional and physical situations/tracheostomy三项待审，AAC父类Alternative means of communication另待审；42分23对应+3待审+7语义暂缓+9既定（第16项AAC处置计既定，父类单列不重复计旧身份）。7语义为CFTR鼻窦/肠梗阻手术、COL1A1 physiotherapist/steroids、GRIN2B/OTC speech、OTC botulinum toxin。原五项外部来源不转成GeneReviews抽取，无Phase3。

只扩现有align_candidates可选reviewed_links入口并跳过needs_review，新增离线apply_structure_source_links实验脚本，复用Ledger/sourced/自检及旧规范source.action.key、evidence_id、XPath/冻结SHA、已有效缓存。23对应写入测试Ledger的来源关系，82旧源位置作background；所有原行动/候选ID、key、标签、活动evidence_ids、requirements、状态/原证据/旧票逐一保持。三个缺口及AAC父类复用Phase1原ID、旧多数roles=none，成功票0，不生成行动。组合关系与子项/单成分关系区分，Nuedexta不映射quinidine单药、RRT不把CKRT/CVVHD视为同义。医学推荐与条件逻辑未核查、不沿用旧临床结论，上下文核查设置未动。

43名称仍43/43（历史41严格名称多数+2别名），本轮来源对应41→42/43，剩COL1A1 steroids；旧key直接存在仍41/43，因未替换key/合并ID。Accepted技术来源对应238→250/264（12练习病例条目），另11 RETEST对应不伪作Accepted基线；不是医学Action Recall。144相关离线测试通过（禁外联及正式评测文件读取，日期仅测试进程固定已验收快照）。正式和测试改前后标准status_diff均0，对current185既有项逐条不变；原测试对生产key/status差异也不变，23链接Diff及4待审Diff单列，不能靠改key消除旧增删。新报告docs/experiments/structure_source_links_applied_20261121.md，完整42/43、源关系、测试Ledger/标准diff、核验、代码补丁在同out。模型/API0、$0，原累计$0.100842897不变，旧out/所有缓存/runs/基线原字节保留。不进Phase3，不自动处理7语义或恢复任何模型调用。

## 最新节点：2026-11-21 通用表头与独立测试Ledger已实现，医学验收未完成

用户授权本轮$0代码/离线验证：补13表头，复用Phase1结构、Phase2有效指认及已批准源内映射，组装独立测试Evidence Ledger；不改生产Ledger/基线/医学规则/已有Action ID和Key，不读四正式评测病例，不进Phase3。只扩现有column_semantic/table_rows，新增structure_test_ledger.py实验入口，复用原Ledger构造器和自检。Therapy Candidates实际是人群列，已纠正为scope；机制、年龄/体重数量分层、营养量、给药详情保留同行，不生成推荐。19章51表468行1307物理单元格全部有语义、480列表项逐树保留，未知表头0。表头未知分支仍保留，不猜新列。

独立产物out/structure-ledger-shadow-20261121：15例测试Ledger（11例新组装，4无章旧结果内容原样保留），所有段落、表格备注、651有效句指认保留背景证据。新组装全部conditional、患者条件unknown；other requirement测试待核查占位不是医学条件，不能计为医学正确。无效票和历史10未达多数句不变，不追认none+_new为行动。临床/逻辑/风险仍待既有上下文核查，设置与代码未动。指定missense仅pyridoxine、KMT确诊/IEP21关联、OTC蛋白24h不挂热量均离线回归；nedosiran GR>30/FDA≥30源别分开，FDA仅保留旧来源上下文。

新旧清单277既有身份保留、388未核候选、42旧身份未对应（12源锚点、7名称、15RETEST当前来源、5仅外部来源、2设计排除及1AAC别名），不把它们全算漏抽。名称匹配仍250/264；严格ID+来源对应238/264，仅候选层下界，医学Action Recall/正确性未计分。原43名称仍43/43，严格测试对应41/43，CFTR liver transplant、COL1A1 steroids不能跨来源/角色补齐。15来源写法差异、44同展示名组及327共原句多行动分别列，不合并ID。剩7名称同前，另2条病种链接/括号尾文未编号但原文已进背景、继续未知；其余582句中509编号、71既有过滤/标签/链接上下文。35旧缺口=31表格同行+4表外均保留，不代表医学条件全部解决。

142相关离线测试通过（外联socket及正式评测文件读取禁用，测试数据日期固定2026-11-20，未改TTL/缓存）；未运行会读评测文件的全套测试。正式前后status_diff0、对current185既有项逐条不变；完整正式/测试status_diff、15例汇总、KMT2B/两AGXT/ANO10逐行动原句详比、35前后、13表头逐项、7名称与未覆盖输入及保护SHA见同out。完整报告docs/experiments/structure_test_ledger_20261121.md。模型/API0、$0，原累计仍$0.100842897；不安排新调用或Phase3。下一步先审核真实Diff，再决定源锚点/RETEST名称逐项对接、语义人工核查或复用现有上下文核查缓存，不自动运行。

## 最新节点：2026-11-21 已审核15项限定名称处理完成，250名称对齐/7未知

用户批准待审15项的第1–9项来源内名称映射；11/13冷热增稠喂养作为原文明示措施保留；14仅Botox→onabotulinumtoxinA，不能等同所有botulinum toxin；10/12/15暂缓，核对speech原文、保留完整glucose&fat营养措施。本轮$0应用前9+两措施共11项来源名称，旧模型票不改。第14具体成分已记录但Accepted泛称botulinum toxin仍未判等价，不多算名称覆盖。Accepted名称239→250/264，余7=GRIN2B/OTC两speech、glucose&fat calories、泛称botulinum toxin、原3医学语义（CF鼻/窦范围、CF外科咨询≠实施手术、physiotherapist服务/提供者/孕期边界）。264 ID/原名/clinical source_refs无变更，无增删，不改key、医学规则/Ledger/Baseline。

两Speech章NBK501979/NBK154378冻结XML无连续speech therapy，存在“occupational, physical, speech, and feeding therapy”共享词组；OTC有IEP speech services，两章有feeding therapy提供者speech therapist，均不自动映射/不能说没有相关措施。第12完整Provide calories from glucose & fat保留，源句蛋白恢复≤24h不分给热量，更不映射成glucose单药。9名称及2明示措施各保留原来源/条件/表格全行，推荐和患者适用仍未知；13表头未批准不动。原43仍43/43=41严格+2旧批准映射，旧票/成功率不重算，不进Phase3。

代码只从既有deterministic脚本提取小align_source_name复用，新增structure_identify_reviewed_names.py离线入口与2必要测试；1408冻结快照离线通过，无API/LLM。out/structure-identify-names-reviewed-20261121含新Accepted名称对照（后续以此为准）、11应用记录/两措施/品牌成分/3暂缓、speech原文及7未知原因、全量名称diff JSON/表、代码补丁及完整status_diff。前后正式详细diff0，对current185既有项相同，所有旧结果/runs/.cache/baseline SHA不变。报告docs/experiments/structure_identify_names_reviewed_20261121.md，累计仍$0.100842897，不因余额追加调用。未自动处理7未知/13表头，不跑核查或评测Step3。

## 最新节点：2026-11-21 Phase 2确定性缺口已补，15/13/3继续待审

按用户授权$0补5药名/4处编号正文，应用另4结构缓存项。原句直接取既有表格单元，用新增number_table_unit（原structure_identify_sentence_repair.py）编号，不受同行已有行动限制；新离线编排脚本structure_identify_deterministic_repair.py无模型执行入口。dantrolene/tizanidine共用Q365/S1的T1/T2，tramadol Q366、topical capsaicin Q367、topical lidocaine Q368各S1/T1；完整同行/表头/列表树/XPath/范围保留，模型票0、条件未知、推荐未判。365旧输入/721正文逐条不改，新增后369/725。4确定性项=骨健康相关物质父类（不只steroids）、acetaminophen正确名称（完整4,000mg原文保留，不改旧Acetaminophen:4票）、Vitamin D/calcium组合来源分别枚举。无疾病专用规则，不把药名识别算推荐。

Accepted名称对照230→239/264，剩18=15名称映射+3医学语义人工待审，6既定排除/1AAC不变；43目标仍43/43=41严格多数+2批准映射，不把9确定性项加成模型票。15逐项建议/依据和13表头建议均单列未应用；3项医学语义继续人工，NF1原则备注不再跑。报告docs/experiments/structure_identify_deterministic_20261121.md，out/structure-identify-deterministic-20261121含新完整准备输入、5覆盖、9来源候选、239名称对照、15/13/3建议、完整status_diff和保护核验。后续名称审阅应以此新对照为准，不回退230旧文件。

全量1406离线通过（2项新增测试）。跨日GeneReviews索引TTL触发的下载尝试被socket拦截、无API请求；仅测试进程以ensure(today=2026-11-20)固定已验收数据日期重测，未改生产日期/TTL、未刷新缓存；仅阻断下载产生的空目录已恢复，原失败日志保留。全部旧结果/runs/.cache/正式输出/baseline SHA不变，264 ID/原名/clinical source_refs不改；前后详细diff0，对current185既有项逐条相同。模型/API0、$0，原累计仍$0.100842897，不进Phase3、不处理评测结构，不自动应用15/13或调用核查。

## 最新节点：2026-11-20 四项来源映射已应用；27名称/13表头新建议待审

用户批准之前4映射，仅已核对来源名对齐，不合并行动ID/改key。应用结果在out/structure-identify-mapping-applied-20261120：OI来源组合关联physical/occupational两个既有名称（非第三行动）；KMT2B两类别引用、不增方案；两CFTR别名完成限定来源对齐。43/43=41严格同名多数+2批准映射，严格多数仍41，旧票不改。Accepted名称对照230/264找到、27待审、6既定排除、1AAC；这不是临床状态。264行动ID/原名/source_refs完全保留、临床状态未知，全球词表和key不动。

剩余27逐项离线核对仅形成新建议，未再应用：4项现结构/缓存可解决、15名称映射待审、5编号正文遗漏、3语义复核（AI/人工）。5漏项=ANO10 dantrolene/tizanidine、COL1A1 tramadol/topical capsaicin/topical lidocaine，来自4处已存在XML/表格单元，当前准备S正文无这5药名且本地RxNorm都阳性；可$0补齐但先审核，不算通过，不是XML丢文。原伤口闭合Q110/S2–S4已有逐句正文，不误计漏项。3语义项=CF鼻/窦手术宽窄范围、CF手术咨询≠实施手术、physiotherapist服务/提供者及孕期来源边界；不自动扩大摘要来源/用孕期附注补普通行动。13未知表头均可按原结构给语义建议（剂量分层/营养量/机制/评估分组/来源疾病范围/给药详情），原unknown代码保持、建议未应用、不转患者满足或不适用。

报告docs/experiments/structure_identify_mapping_applied_20261120.md；同out目录有43覆盖、4批准应用记录、27逐项原文/缓存/原因、13表头原文/路由/建议、完整status_diff及保护核验。模型/API0、本轮$0，原累计仍$0.100842897，前后详细diff0、对current185既有项逐条相同；无正式医学规则/账本/baseline变化，不进Phase3，不处理评测结构。等待审核新27/13项，不能因“可解决”自动补正文/改别名/调用；NF1一般原则备注不再补跑。

## 最新节点：2026-11-20 Phase 2名称映射审核稿完成，模型继续暂停

用户决定NF1句子按一般处理原则备注保留、不再补跑；已在out/structure-identify-name-review-20261120/NF1-user-disposition.json记录来源决定，旧票/正式Ledger不改。$0离线核对4项映射，仅提案未应用：OI共享therapy对齐同章已有physical/occupational therapy（physical另有连续原词证明，组合不作第三行动、不自动等同physiotherapist）；KMT2B共享treatment拆为药物/手术两类别引用，不新增具体方案，不合并窄义dystonia标签，早期仍随专科参与；CFTR pancreatic enzyme replacement therapy→短名、contact precautions(gown & gloves)→核心名建议仅作用于已核对来源名称对照，保留全文限定，不全球剥词/括号、不合并Accepted行动ID/改key。

两别名原文已有有效多数，待审根因是词表长短名各自独立identity、aliases空，不是模型漏抽。当前43原文覆盖、41严格同名多数+2待审；若两别名批准预期为41严格+2映射，不称43严格。Accepted当前228/264名字找到、29待审（含这两别名，若仅别名批准预期待审27；未应用）、6设计排除、1AAC；OI共享对齐不解决physiotherapist。29不是29漏抽/补模型任务，完整名单及13种未知表头随报告。原35来源全保留、XML缺文0；临床条件/风险/推荐与技术解释仍有未知，Phase2未全验收、不进Phase3。本轮不安排新指认调用、0模型/API、$0；无生产代码/词表/医学规则/账本/baseline改动，详细diff0，对current185既有项相同。原累计仍$0.100842897。报告docs/experiments/structure_identify_name_review_20261120.md和out/structure-identify-name-review-20261120含4项原文/现有候选/建议/未应用标志、完整status_diff及SHA核验；先等用户审核映射，不自动应用或调用。

## 最新节点：2026-11-20 Phase 2 NF1单句三票完成，所有调用停止

用户仅批准来源角色复核后剩余NF1一句nonthinking三票，$0.01计原$0.20，仅非高峰、不自动补跑。已完成3请求/3答复，0重试/截断/格式失败/高峰/缺usage；冻结提示词及1024参数不变。角色3/3均none，actions/conditions空；第2/3票同时给_new原词“treated in the same manner as others w/similar pathology & tumor markers”，第1票无新词。标签100%一致但整份输出不全一致，新词仅2/3；未据泛化短语确认具体治疗，未把none或空conditions解释为无治疗/无条件。NF1语义仍待审，OI/KMT2B共享身份和两项全称/括号映射仍未知。不追加调用、不运行核查，不改医学规则/Ledger/baseline，不进Phase 3。

本次实测usage计费$0.000182070，原任务累计**$0.100842897**、$0.20余额$0.099157103。今后预算必须从out/structure-identify-nf1-one-20261120/shared-campaign-budget.json继续，不能回退旧incremental父总额。所有旧预算/答复/缓存只读，新记录隔离；余额不恢复调用授权。详细前后diff0，对current185既有项逐条相同；所有原保护SHA及冻结输入/核查器哈希不变。报告docs/experiments/structure_identify_nf1_one_20261120.md，产物out/structure-identify-nf1-one-20261120有三票原始输出、usage、分析/累计账本/完整status_diff和保护核验。无生产代码改动，本轮验证三答复原词/协议/预算/状态，未重跑整批。

## 最新节点：2026-11-20 Phase 2十二组来源角色复核完成，新3次提案待批准

用户拒绝先执行12×3，要求$0按列语义/路由/通用句式收窄。仅在原structure_identify_table_context.py补source_parts及3测试；不改生产医学规则/旧classify/核查器。33段来源角色分开：明确行动直接建立12个来源候选；管理目标、检查、资质、目的、风险和备注不混作治疗T。第7组四伤口操作直接保留、层数/留置时间原文挂接；第10组EEG为检查，清除/禁忌为风险，不据药名建立推荐；第12组ASM来源候选、医师资质和丙戊酸风险分别保留。既有核查器只能做具名条目的subject/evidence/limit/recommendation，不计算技术参数/药代或发现标准名；未调用它，未知仍未知。

最终新增指认仅原第8组NF1乳腺癌一般表述1句，T=[]（无已确定具体治疗名，不造T），只问是否存在可按原词抽出的行动或属于一般详情，不能给无主条件。原第3/4组共享词组仍有身份映射未知，不算两个标准名通过，也不为原文不存在的名字重问。旧36次/$0.05提案由新1×3=3次提案替代，均未执行；nonthinking/1024、仅非高峰，历史实测估计$0.000287–$0.000306，完整预留$0.0038109，建议子帽$0.01计入原$0.20；原累计$0.100660827不重置，未来上下文核查费用不含在此次提案且未经授权。

全量1404离线通过，所有旧结果/runs/.cache/正式Ledger/baseline保护SHA不变；详细前后status_diff0、对current185既有项逐条不变。模型/API0/$0，不进Phase 3、不读评测结构。报告docs/experiments/structure_identify_role_review_20261120.md，out/structure-identify-role-review-20261120含12组逐段来源角色/具体原文/T/新报价/完整status_diff及核验。等待用户新批准，不得执行旧提案或因预算余额自动调用。

## 最新节点：2026-11-20 Phase 2备注直接挂接完成，模型/API继续暂停

按用户$0最小修复要求，只修改structure_identify_table_context.py及必要测试：备注直接同行挂接，复用既有短名称/行动词表及83条同源同文有效缓存多数；不再仅因完整句或备注列统一待审。句尾词典命中不能冒充句首行动识别，药名字面命中仍只是提案，未答正文不填none，旧答复不改，条件/风险/适用性继续未知。原35处中31表格关系全部保留：12处完成表格来源处理，19处表格名称待判；4表外中2详情直接挂接、2共享词组待判，合计21处/12组（10表格+2正文）。14来源处理不是14医学语义通过；未知额外行动也不宣称不存在。

43项XML原文全部定位，41严格名称有效多数复用，2全称/括号变体继续映射待审，不自动登记别名。Accepted仅名称候选对照203→228/264（新增25源自既有结构/规则），29待审、6设计排除、1既定AAC别名；医学状态与基线不改。项目tests/全量1401离线通过，1016单元原文及保护SHA验证通过；改前详细快照已存，前后完整diff0、对current185既有项逐条不变。报告docs/experiments/structure_identify_table_attach_20261120.md，产物out/structure-identify-table-attach-20261120含35逐项、12组具体问题、43覆盖及完整status_diff。模型/API0/$0，不进Phase 3，不处理四正式评测，DMD延期；原付费累计不变，旧余额不构成授权。

## 最新节点：2026-11-20 Phase 2 XML同行结构/列名补充完成，模型继续暂停

按用户$0要求，新增实验适配器structure_identify_table_context.py（约150行）及4项测试，复用management().tables、原XML text/list树、route、row_semantic/classify/scan；没改生产医学规则/旧解析器/模型答复/Ledger/baseline。每单元保留章节/逻辑行/列/完整多级列名/原XPath/列表祖先，同排范围、目的、候选和备注由代码关联；备注新治疗只是提案，限制/风险未知，不广播给同行所有药物。

补充列名检查：Specific Drug / Therapy Candidates→候选，Indications→范围，Treatment Class→类别，Objective→目的，Considerations/Other→详情，Evaluation/Frequency沿用章节路由。按列名而非位置；药名位于剂量矩阵表头时其下值为详情，避免loading dosage中treatment误判。未知列保留待审，不以包含drug/treatment就认作治疗列；Drug Target/Treatment Resistance保持unknown。获批15例12章43种表头组合、13种未识别组合有原位置待审。

原35处逐项对照：31表内结构关系恢复，其中1处完整原文候选标签可直接处理；30表内仍需语义+4表外正文仍待判，合计34旧缺口，整理17上下文组（13表格行聚焦29文本单元+4正文）。原XML丢文0；25处原来只在行上下文未编号，10处有编号但无有效判断，4表外均已在旧输入。不能说31或35处已全部通过。新队列仅准备，不调用模型，不进Phase 3。

全量1398离线通过，正式状态本轮0变化、对current185既有项逐条相同；runs/.cache/全部baseline/100正式输出/所有旧实验结果SHA不变。报告docs/experiments/structure_identify_table_context_20261120.md，产物out/structure-identify-table-context-20261120（35对照、列名映射、未知列、17组needs_classification、完整status_diff）。API0/$0，不处理四正式评测，DMD延期；原任务累计仍$0.100660827，余额不构成调用授权。

## 前一节点：2026-11-20 Phase 2三点最小修复完成，模型调用继续暂停

用户只授权$0代码与离线验证：背景/题目分开、先编号治疗、逐句校验投票。新增实验模块structure_identify_sentence_repair.py及测试；未改生产医学规则、原严格validate、原majority或冻结SYSTEM。背景不带S编号；既有字典/短治疗名/缓存逐字提案生成后续候选T。回放始终使用旧题原T，不用新编号追认旧条件；未答正文没有none默认值。模型和外部API0次/$0，不恢复任何旧付费授权、不进Phase 3。

复用原167次：451个正文句子票，416有效92.24%、20未答、15校验失败；全缓存1948/1983有效98.23%。这是逐句新分母，不改旧102/167整题历史。完整新输入含721条正文、2163句子票；60条新编号正文没有本题三票，保守计入180未答票后完整有效率1948/2163=90.06%（未答200、错误15），不能用98.23%缓存子集分数宣称全量通过。64背景单位（50表现条件、2目的、1类别、11源XML上标引用）单列；未知标签/数值剂量留正文。43项严格名称多数24→41，2个全称/括号变体仍映射待审，不自动升级别名。Accepted264名称匹配203、待审54、设计排除6、AAC别名1，均是候选名对照而非医学基线升级。

原编号正文10句不足有效票；旧row-anchor再补编号60条，33条在其他题有同位置同原文多数，仅作来源引用、不伪装本题新输入的三票，27条无可用缓存。37条缺口记录按原文位置去重为35处正文，仍未知；Phase 2未宣称验收通过。新输入未发模型。1394全量离线通过（外网禁止，仅本机测试服务器），1948有效句子票用原T再验，关键AGXT/KMT2B条件保持通过。

runs/.cache/全部baseline、100正式输出及此前全量/修复/增量结果逐文件SHA不变；本轮正式diff0，对current185既有项逐条不变，未promote。产物out/structure-identify-sentence-repair-20261120，报告docs/experiments/structure_identify_sentence_repair_20261120.md。原付费任务累计仍$0.100660827，余额不构成补跑授权。评测结构不读/Step3不跑，DMD延期。

## 前一节点：2026-11-20 Phase 2增量167请求完成，仍未验收通过

用户批准增量167请求、硬上限$0.06计入原$0.20总帽，仅非高峰；已全部返回，102有效（61.08%）、65格式失败（27单位），零截断/传输失败/缺usage/高峰/reasoning。费用$0.022004031，原任务累计$0.100660827、总帽余额$0.099339173。**后续必须从此累计与out/structure-identify-incremental-20261120/shared-campaign-budget.json续算，不能重置回原父state旧余额。** 已停在获批清单末尾，不因余额尚余自动加跑。

合并365题/1095票，保留928份有效旧票（增量范围内13），1030有效94.06%、65格式失败（漏/多S46、非原词12、未知action T4、condition T2、角色不一致1），21题不足两份有效票，2句多数待审。43项输入全覆盖；24项严格名称形成有效多数、17项仅原始提案；另pancreatic enzyme replacement以更完整名称三有效票提取但身份映射待审，contact precautions以括号名称提案但无足够有效票，均未自行登记别名。Accepted264项名称匹配182（+24）、待审75、设计排除6、AAC别名1；KMT2B/AGXT指定检查保持通过。

1384全量离线通过，正式100输出/runs/正式缓存/全部baseline及原1020答复/修复产物逐文件SHA不变；本轮diff0，对current185既有项逐条不变，未promote、不进Phase 3、不改医学规则、不跑上下文核查。未读评测章节结构/跑Step3，DMD延期。执行器run_structure_identify_incremental.py复用原串行请求/预算守卫；产物out/structure-identify-incremental-20261120，报告docs/experiments/structure_identify_incremental_20261120.md。

### 前置免费修复结果

按用户要求兼容顶层额外type，复用1020份答复离线修复，原记录不改。最终933有效、69失败（29原单位）、18份XML证实无正文导航单列；正文有效率93.11%，原总数分母91.47%。原107份type之外失败中39修复、5导航排除、63仍失败；另6份旧校验未检查的句内_new移至顶层后暴露非原词，故剩69。缺临床S/缺T/非原词仍失败，不猜医学条件。

35遗漏表格单元格归31行、33短题，全行所有列编号并保留列头/XPath/行上下文；43/43 Accepted名称有原句与候选，候选输入不算模型召回，现有索引仅2项已名称匹配、41项待补题。Accepted264项名称对齐158、未匹配99、设计排除6、AAC别名1，指定KMT2B/AGXT检查保持通过，整体尚未验收。

补题提案60单位/167请求：33新表格题99次，10补候选原题30次，17临床正文S/T映射不变题只补38失败票、保留13有效票；2失败原题被新行覆盖不重复跑。预计$0.03890–0.04290，建议增量帽$0.06，仍计原同一任务$0.20（已花$0.078656796、余额$0.121343204）；**仅报价，当前未授权自动执行**。本轮新模型/HTTP0次/$0，不进Phase 3，不改医学规则/Accepted。全离线1382通过，正式100输出/runs/正式缓存/历史基线不改，本轮diff0，对current185项逐条不变。报告`docs/experiments/structure_identify_repair_20261120.md`，产物`out/structure-identify-repair-20261120`。

## 前一节点：2026-11-20 15例获批队列已完成，阶段2验收未通过

15例获批340题/1020次全部返回，费用及预算计入额均$0.078656796<$0.20；无缺usage、无传输失败、无截断、高峰0、reasoning0。KMT2B/AGXT指定检查全部通过，但冻结协议有效615、格式错405：298仅多顶层type字段，56 type+其他、30句号/顶层、13_new原词失败、6未知action T、2角色/条件不一致。仅在副本去掉精确type字段的免费诊断可有效913、仍107错，原记录未改；可投票题205→304，补充99题多数结果仅作提案。原始严格统计：135题不足两份有效票，2句多数待审，637源句中395句有汇总（46句来自两有效票一致），349句三有效票中291全票一致83.38%，408名称索引/240条件对/56多数新词均不是推荐。

输入编排覆盖有缺口：至少43个未对齐Accepted名称在35个未编号表格上下文单元格里，均treatment路由；例如ANO10备注中的riluzole和剂量/监测原句没有成为S。不是把model未抽到不存在的编号句子算医学否定。已产出35处补题清单与规范化副本，**未发送补题调用、未进入阶段3、未自动付费重跑或改冻结提示词**。Accepted严格身份对齐264项：154名称匹配、103待审、6设计排除、1 AAC别名。原始长表格单位名仍需命名审阅。推荐/描述/条件适用性仍未判断，上下文核查low/16384不改不跑。

全离线1375通过，1020唯一票/冻结输入/原词复制/模型名/上下文SHA/预算核对通过。正式账本/基线/缓存不改；本轮前后diff0、对current185既有项逐条相同。完整产物`out/structure-identify-full-20261120`；报告`docs/experiments/structure_identify_full_20261120.md`。原$0.20是同一全量任务合计帽，后续若获准补题需沿用本账本剩余额度，不可重置成新$0.20。完整刷新/缺口干跑继续延期，评测结构及Step3不读不跑，DMD延期。

用户随后明确“批准”15例阶段2全量报价，授权新的**合计硬上限$0.20**，仅非高峰：340题/1020次三票、256段与84表格待判单位，12不同章节在15例间共享，旧回归费用不重记。冻结提示词仍3a-identify-condition-pairs-v1、nonthinking/1024，不改上下文核查或生产v5。运行产物`out/structure-identify-full-20261120`，脚本`run_structure_identify_full.py`；首条表格三票通过后才继续全量。既有KMT2B五段T0/IEP候选和AGXT urologist候选保留。使用已安装httpx的IPv4/TLS1.2连接池，隔离到实验进程；免费连接探测与逐次预留留痕，不改生产网络。只重试无答复传输失败并保留预留，不重发已有答复；格式/截断留待审。不得扩大至完整刷新、上下文核查、阶段3或评测Step3，不升级基线。

用户授权只重跑AGXT原题2/25/34/39/42/45/51受影响句子、KMT2B抗胆碱药和IEP两段：9题12句、27份三票答复全部有效，零格式错/截断。condition恰有一个给定T；words只忽略大小写做本句连续子串校验并复制原写法，按(T,words)成对多数。missense只关联pyridoxine，confirmed diagnosis关联抗胆碱药，age21关联IEP services且不关联transition plan，均通过；nedosiran GR >30与FDA标签≥30按既有来源分列、不合并。12句7句全部原词/角色/行动一致，余5句差异保留；提供者资质等描述仍交上下文核查，不变成病人资格。缺条件仍未知，不推无条件。

按用户指令冻结`3a-identify-condition-pairs-v1`，SHA `92c1107cc252473e6eb92eec00d7e6a17e25b956f9b1ee3e5e66f66046eb2d5b`，记录`docs/step3a_identify_prompt.json`、3a契约和测试。non-thinking/1024/temp0；生产默认仍3a-v5，上下文核查仍low/16384且SHA不变。本次31总传输尝试，27有usage已知$0.002283054，一次超时三次TLS失败原记录保留，未知实付预留$0.005228500，预算上界$0.007511554<$0.02，全部非高峰、reasoning0。只显式补未返回票及后续票，不重发已返回答复。隔离curl可选IPv4/HTTP1.1/TLS1.2，生产网络不改。

原15例报价：11有章病例、12不同章，AGXT两例同章只计一次；256段加84个未被段落覆盖待判单位（61 table_treatment/23 row_anchor；74needs、10表内条件线索），340题/1020次。仅正文768次不是全量。按两例实测输入长度/输出句数外推、未来输入全冷缓存，预计$0.13319–0.14619，合计硬上限$0.20已由用户批准；较多无usage连接失败可能导致提前停。全输出保守预留$1.35477仅极端上界，非报价。不计完整刷新/上下文核查/无章v6.1费用。

全离线1373通过；100正式输出、runs、正式缓存、历史基线不改，current仍等于离线key升级快照，前后diff0，对current185既有项逐条相同，未promote。评测章节结构/Step3不读不跑，DMD延期。报告`docs/experiments/structure_identify_pairs_20261120.md`，产物`out/structure-identify-pairs-20261119`。

## 比赛

SAIL AI-Tx Challenge 最终赛：Actionability Report Generation。
官网 https://aitxchallenge.org/ ，提交页 https://aitxchallenge.org/models/ ，教程 https://aitxchallenge.org/tutorial/

- 输入：虚拟患者 JSON（基因变异列表 + 临床描述），见 `data/cases/aitx_final_patients.json`（4 个评测病例 AITX-40001 至 40004）
- 输出：每个病例一份 markdown 治疗可行性报告，组成一个 JSON 数组 `[{id, report_markdown}]` 上传
- 报告必须按顺序包含官方模板的全部章节：Summary；Tier 1（Existing Targeted Therapies / Supportive Management / Contraindications & Precautions）；Tier 2（Clinical Trial Eligibility / Off-label or Expanded-Access Therapies）；Tier 3（Bespoke Therapies / Drug Repurposing / Outcome Measures & Ranking）
- 硬规则：每条论断都要有可验证来源或推理；缺信息时写条件语句；同一行动不跨章节重复
- 评分：专家组人工评审，五个维度：事实准确性、完整性、证据与论证、优先级与校准、临床实用性。**写错比不写更糟**
- 截止 2026-12-01；报告必须由系统生成，**不能人工编辑**

## 用词约定（避免混淆）

- **参赛组**：Tier 1 ≤32B / Tier 2 ≤500B / Tier 3 不限（按模型总参数，开源权重）
- **证据层级**：报告里的已确立 / 新兴 / 假设性三层，每份报告三层都要写

## 已定决策

- 模型接口统一（`aitx/llm.py`，OpenAI 兼容，换模型只改环境变量）
- 开发期用 DeepSeek-V4.1-Flash-1017（官方 API 名 `deepseek-flash`，763B，属于参赛组 Tier 3）
- 对照：DeepSeek-V4-Flash-0423（284B，Tier 2，第三方平台调用）；第 4 周按同一评分标准对比后决定报哪个组
- 每次 LLM 调用记录服务端实际返回的模型名，防止别名被悄悄切换；跨接口复用缓存要求服务端模型名**完全一致**，并记录服务商
- 当天 LLM 费用上限 `AITX_LLM_BUDGET_USD`（默认 0.3 美元），每次调用前检查，超了就停下并保留已完成部分（退出码 4）
- **花钱规矩（2026-11-11，剩余预算约 \$2）**：每日上限恢复 \$0.3，不再临时提高；**任何 LLM 运行预计超过 \$0.1，先报价（调用次数 × 实测单价），等用户确认再跑**。修复阶段中间只跑离线测试，全部修复写完后练习病例全量重跑、验收一次，跑前报价。
- **例外记录**（每次超出日上限都要用户在对话里明确批准，并记在这里）：
  - 2026-11-11 周三 06:58（太平洋时间）：上下文核查已判条目验证（`scripts/validate_context_check.py`，81 次调用），用户批准**本次单次硬上限 \$0.20、覆盖当天日上限，仅此一次**；当天开跑前已花 \$0.5104，故本次运行的 `AITX_LLM_BUDGET_USD=0.7104`。实际 \$0.0538。
  - 2026-11-11 周三（太平洋时间，非高峰）：改核查问题后的复核（同一批 26 条已判条目，`context-check-v3`），用户批准**本次硬上限 \$0.10、覆盖当天日上限**；开跑前当天已花 \$0.5643，故 `AITX_LLM_BUDGET_USD=0.6643`。**注明**：这轮是在同一批题上改问题后的复核，只能确认没改坏；核查器的真实表现以 4 例复测为准，复测时单独报告核查器的抓住和误伤。
  - 2026-11-11 周三起（太平洋时间，非高峰）：修复后练习病例全量重跑（12 例，报价约 \$0.85、最坏 \$1.30），用户批准**整次重跑单次硬上限 \$1.30、覆盖日上限**：周三 20:30 起先试跑 PRAC-GRIN2B 一例（开跑前当天已花 \$0.6131），确认账本完整、无 fail 后，周四 02:05 起一次跑完其余 11 例（caffeinate 包住），其余 11 例的上限 = \$1.30 − 试跑实际花费。实际：试跑 \$0.0414 + 周三 20:41–22:00 跑完 10 例 \$0.8571（22:00 进高峰自动停）+ 周四 04:20 NF1 及全部验收 \$0.0923（与评测病例 Step 1–2 重跑合计，上限 \$0.15）= **\$0.991**。
  - 2026-11-12 周四 05:19（太平洋时间，非高峰）：两层修复 + 年龄段 + 会话日志后的 12 例缓存补跑与验收，用户批准上限 \$0.03（当天未超日上限 \$0.3）；实际 \$0.0305，**超出 \$0.0005**（并发调用落在上限检查之后），用户确认记录即可。
  - 2026-11-12 周四 06:3x（太平洋时间，非高峰）：按段落核查后的 12 例缓存补跑，分三段撞上限（\$0.08 → \$0.06）；收尾 KMT2B、NF1 与 3a–3e 验收，用户先选"明天、上限 \$0.03"，随即改为"继续跑就行"，按**当天例外、本次硬上限 \$0.03、覆盖日上限 \$0.3** 执行（开跑前当天已花 \$0.2935）。
  - 2026-11-12 周四 07:08 起（太平洋时间，非高峰）：补盐修复（同一引文多处出现分别核查）的练习病例重跑与验收 + 4 例复测（RETEST-CNNM4 / EIF2B1 / THPO / PFN1），用户批准**一次性例外、合计硬上限 \$0.60**（先报 \$0.47，看过调整后样本与报价后提高）；开跑前当天已花 \$0.3045。实际：补盐修复 \$0.059 + 复测 \$0.153 = **\$0.212**。
  - 2026-11-13 周五 07:xx（太平洋时间，非高峰）：R15「是否推荐」+ 3b 上一级疾病名检索 + 表型"可能存在"后，练习病例 12 例 + 复测 4 例重跑与全部验收，报价约 \$0.68（最坏 \$1.0），用户批准**一次性例外、硬上限 \$1.00**；另批 PFN1「是否推荐」low / high 对比 **\$0.05**。开跑前当天已花 \$0。实际：主运行 \$0.442 + 上一级疾病名规则补正后 PFN1 / GRIN2B 重跑 \$0.1085（同一例外内）= **\$0.551**；high 对比 **\$0.0248**。
- 优先用实时 API 获取数据，引用必须能解析到具体记录（URL / accession）

**2026-11-15 用户批准的下一轮**：第 5 项（目的条件 / HPO / 使用情境，30263c7）及人群小标题规则完成后，先离线全过并提交推送；太平洋时间 2026-11-16 周一 02:05 之后，以 `nohup` + `caffeinate`、`--offpeak-only` 重跑。整次硬上限 **\$0.12**（`AITX_LLM_BUDGET_USD`，已批准，无须再次报价批准），先 PRAC-AGXT-c33dup 确认账本完整无 fail，再其余练习 11 例与原复测 4 例，全部验收后重建 AGXT 报告。不得跑评测病例 Step 3 及之后；`acceptance_eval_cases.py --eval` 只验 Step 1 / 2。COL1A1 交替体位只看本次上下文核查是否补婴儿限定。

**2026-11-16 追加授权**：首段可核算费用 \$0.1094，因下一请求最大费用预留 \$0.0108 超过当时账本余量 \$0.0106 而提前停止，已完成病例保留。缓存补跑后剩 PRAC-OTC / GRIN2B / NF1、RETEST-EIF2B1 需要新调用；用户明确批准**本次合计总上限提高到 \$0.17**（追加 \$0.05，非另开一份预算）。继续非高峰、`nohup` + `caffeinate`；最终另报 GRIN2B / NF1 不在原新调用名单却未命中缓存的原因，以及超出原 \$0.10 估价的原因。

**2026-11-16 本轮完成**：代码 `34d69d2` 推送前离线 **1104/1104**；16 例 Step 3 账本均新鲜、无 fail；Step 1 / 2、3.0、3a **30/30**、3b **8/8**、3c **7/7**、3d **8/8**、3e **5/5**、评测病例 Step 1 / 2 `--eval` 全过，AGXT 报告重建、格式 PASS。共 18 条分支状态变化，没有新增不适用；COL1A1 交替体位**未补婴儿限定**。241 次请求、高峰 0 次，其中 240 次有用量，已知费用 **\$0.1387**；CFTR 一次 `usage=null`，其费用**未知**（原工具按 0 算，未及时拦下，不把它当成精确实付）。按请求上限保守计入后整次上界 **\$0.1495 < \$0.17**。GRIN2B / NF1 因严格 HPO 映射删掉程度核查题而换缓存键，合计漏列 24 次 / \$0.010821；DMD 有 51 次 / \$0.039362 仅因本次新增人群小标题而触发，扣除这一新增范围的已知费用约 \$0.0993。完整变化清单、费用核对、未改的肝移植机制误抽情境问题见 `docs/context_check_contract.md` 第 18 节。网络断开通过临时 curl 传输重试，未改临床规则；评测病例 Step 3 及之后未运行。

## 改动审批规则（2026-11-05）

**2026-11-16 审阅追加批准**：删除 AGXT 肝移植的机制误抽情境（情境只取本条行 / 段落的病人状态或时机）；原文性别未知时，X 染色体基因 + 半合子可推断男性，作为推理证据入账，原文性别优先。费用缺 usage 按请求预留上限记预算、标记实付未知。COL1A1 交替体位只加核查漏判测试，不加代码规则。全离线测试通过后缓存重跑 AGXT 两例和 DMD、全部验收、重建 AGXT 报告；**本次任何真实 LLM 调用先报价**。支持核查假拦 3/17 已在 11-15 存档存在，本轮不改。

**2026-11-16 审阅修正缓存阶段（已按用户决定收尾）**：`3bfdd33` 已推送，离线 **1127/1127**；AGXT 两例及其他 13 例缓存成功，状态变化 0、无账本 fail，AGXT 报告已重建、格式 PASS。Step 1 / 2、3a 30/30、3b 8/8、3c 7/7、3e 5/5、评测 Step 1 / 2 全过；3.0 未完成、3d 两项因 DMD 输出过期未计分。用户选择**本次只用缓存、不花钱**，不批准本次新增 $0.25 报价；保留半合子推断性别代码，**DMD 因性别推断改动而过期，待下次影响 DMD 的改动时一并重跑**。不再为本轮单独重跑 DMD，不按全套验收通过汇报。新增费用 **$0**。COL1A1 漏婴儿限定已入独立测试集，不改代码规则。最新版报告：`out/step4/PRAC-AGXT-c33dup.md`；本轮验收汇总：`out/acceptance/review_20261116.json`。详情见上下文核查契约第 19 节。

**2026-11-16 AGXT 二次审阅授权**：只用缓存、不花钱；修复碎石表现条件被推荐句覆盖、Summary 仅列具体病人变量、3b 多疾病诊断清单复用已批准的确诊与满足其一规则、靶向药先引完整 FDA 适应证再引 GeneReviews。离线测试通过后缓存重跑 AGXT 两例及可跑验收，重建报告；任何新 LLM 请求先报价。DMD 延期决定继续有效。上次 3.0 实际停止在重建 DMD 所需的未缓存核查，不是仅因读取到旧输出的过期标记。

**2026-11-16 AGXT 二次审阅完成**：代码 `11f38b0`，离线 **1137/1137**；15 例只用 LLM 缓存重跑、账本新鲜无 fail、行动总状态变化 0。Step 1 / 2、3a 30/30、3b 8/8、3c 7/7、3e 5/5、评测 Step 1 / 2 全过，AGXT 报告已重建、格式 PASS。3.0 按 DMD 延期保留 deferred；3d 6/8，DMD 两项过期不计分。**DMD 因性别推断改动而过期，待下次影响 DMD 的改动时一并重跑**；未重跑或改写其账本。新增费用 **$0（真实 LLM 请求 0 次）**。最新版报告仍为 `out/step4/PRAC-AGXT-c33dup.md`；本次验收汇总 `out/acceptance/agxt_review2_20261116.json`；根因和详情见上下文核查契约第 20 节。

**2026-11-16 AGXT 三次审阅授权**：本次只用 LLM 缓存、不花钱。干预试验优先、类内按未知数并截前 5；定制疗法逐项显示已有事实和理由，未记录的靶器官保持未知；已满足的替代诊断 / 条件不再挂其他选项；3c 先例变异只记描述；阴性药物引结果句；重定位写出阴性检索来源及计数；Summary 合并 kidney function / eGFR 并去重。补测试后缓存重跑 AGXT 和可跑验收，重建报告；DMD 延期继续有效。当前高峰只执行 cache-only 路径，真实请求前的高峰保护仍开。

**2026-11-16 AGXT 三次审阅完成**：代码 `bedd040`，离线 **1155/1155**；15 例缓存重跑、账本新鲜无 fail、行动总状态变化 0。Step 1 / 2、3a 30/30、3b 8/8、3c 7/7、3e 5/5、评测 Step 1 / 2 全过；3d 6/8，DMD 两项过期未计分，3.0 仍延期。七项报告修改已核对，报告格式 PASS。前 5 全为干预试验；CRYSTAL 仍排第 6（25 个未知项），按五条上限折叠，观察性研究全部在后。实际未记录靶器官，保留未知。**真实 LLM 请求 0 次，费用 $0**；高峰仅走缓存路径，调用前高峰保护仍开。报告 `out/step4/PRAC-AGXT-c33dup.md`；本轮结果 `out/acceptance/agxt_review3_20261116.json`；详情见上下文核查契约第 21 节。DMD 延期原决定不变。

**2026-11-17 官方模板与证据链审阅授权**：只用 LLM 缓存，缺缓存即停，真实调用先报价。本轮用户要求 0–11 项，覆盖标题逐字对照、三层 Summary、三块结局指标、完整支持治疗与干预试验、变异事实来源、移植选择原句，以及全部行动 / 负面结论 / 指标的 Evidence ID、安全检查覆盖范围和 Step 5 确定性校验。官方模板原文保存 `data/aitxchallenge_report_template.md`；这轮规则覆盖此前试验五条上限及仅呈现代码技术理由的做法。技术前提无账本来源时删除论证、标“未确认”，不补编 AAV / Prime Editing / ASO 技术依据；不改变 Step 3 判定。未检查的安全项必须写“未检查”，空数组不能推成无风险。不新增临床数据源，只把账本已有 FDA / NCT / GeneReviews 来源中的原文记入账本。报告生成后自动执行 `scripts/validate_report.py` 使用的检查，不通过退出。**DMD 因性别推断改动而过期，待下次影响 DMD 的改动时一并重跑**；本轮不为其启动新调用。

**2026-11-17 官方模板与证据链审阅完成**：实现代码至 `b8e986b`；离线 **1186/1186**。15 例只用 LLM 缓存完成，新鲜账本无 fail，所有行动 / 分支状态及 3d classification 变化 **0**；末次补全安全展示后，AGXT 两例及可跑验收再次缓存完成。Step 1 / 2、3a **30/30**、3b **8/8**、3c **7/7**、3e **5/5**、评测 Step 1 / 2、报告格式及 Step 5 确定性检查全部 PASS；3d **6/8**，DMD 两项过期未计分、整体 FAIL，3.0 仍延期，未称全套通过。报告列全 **6** 项已分析干预试验、**4** 项观察研究汇总、**11** 项支持治疗；证据表 **285** 个 ID 均存在、verified、定义唯一。全部账本 **10** 项药物均列安全覆盖，含未检查的吡哆醇和 Stiripentol；无来源技术理由删除、前提标未确认。基线没有 ID 重复、没有“空数组=无相互作用”、没有 RNAi 移植决策论断，未改这些临床判断。COL1A1 交替体位仍未补婴儿限定（历史核查漏判，不加代码规则）；支持核查仍假拦 **3/17**，本轮未新增。**全部尝试合计真实 DeepSeek 请求 0 次、新增费用 $0**；未跑评测病例 Step 3 及以后，DMD 账本字节未改。缓存工作未传启动即拦缓存的 CLI `--offpeak-only`，真实请求前的高峰保护一直保留，且 cache-only / 零预算双重禁用新调用。报告：`out/step4/PRAC-AGXT-c33dup.md`；验收汇总：`out/acceptance/agxt_template_review_20261117.json`；核实及结果见 Step 4 契约第 20–21 节。**DMD 因性别推断改动而过期，待下次影响 DMD 的改动时一并重跑**。

- **只会把判定结果放宽成"有条件"的改动**（如把某条要求改判为"未知"），可以先做后报。
- **可能产生新的"不适用"（或把未知变成确定的满足 / 不满足）的改动**，先报给用户确认，再改。
- 无论哪种，都要补离线测试和反向验证，并在契约里记下原因。

## 开发方式

**离线测试环境**（2026-11-12）：项目目录下的 `.venv/`（已在 .gitignore），系统 Python 3.9 建立，只装了 pytest。之前放在会话临时目录里的环境被系统清理掉了，不要再放临时目录。
```
/usr/bin/python3 -m venv .venv && .venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q tests
```
查看页依赖（fastapi、httpx、uvicorn）也已装进 `.venv`（2026-11-13，用户同意）：`.venv/bin/python -m pip install fastapi httpx uvicorn`。全部离线测试约 80 秒。

按节点逐步构建，**每个节点有契约文档（docs/）、离线测试（tests/）和联网验收脚本（scripts/acceptance_*.py），验收通过才进入下一步。**

**新章节首次接入流水线，先用 1 个病例小规模试跑**（2026-11-06 定）：确认账本能完整写出（`out/step3/<病例>.json` 真的落盘）、`checks` 里没有 fail，再跑其余病例。
起因：3d 首次接入时，新行动行缺 `status_by_branch`，账本在每个病例的最后一步抛 `KeyError`，12 个病例的 LLM 调用全部白花（约 \$0.19），一条输出都没写出来。
同理适用于：改动账本结构、新增校验、换提示词版本。小规模试跑用缓存（`AITX_LLM_CACHE_ONLY=1`）能跑通的部分先跑，必须联网的那一步再放非高峰。

| 步骤 | 内容 | 状态 |
| --- | --- | --- |
| 1 | 变异解析（确定性，无 LLM） | ✅ step1.1 已验收（2026-11-03，tag `step1.1-accepted`）：自检 6 独立重新翻译，16 个变异全部一致、反向验证全 fail；输出 schema v1.2 另含外显子布局和 AlphaFold 结构事实（pLDDT、RSA、8 Å 邻居） |
| 2 | 疾病归一化（基因 → OMIM / GenCC / GeneReviews） | ✅ 已验收（2026-10-28，tag `step2-accepted`）：`--fresh-llm` 硬性项全过；离线测试 135 个全过；症状提取测试集 32 条精确率/召回率 1.0（集合偏简单）；剩余问题见契约“已知局限” |
| 2.5 | 审查用查看页面 | ✅ 本地 Web 应用 `scripts/viewer_app.py`（FastAPI，127.0.0.1:8765，实时刷新、页面上重跑、运行记录）+ 静态导出 `scripts/build_viewer.py`；前端二期（Step 1 平面三图、3D 结构）完成 |
| 2.1 | Step 2 局限改进 | ✅ 已验收（2026-11-03，tag `step2.1-accepted`）：难题测试集、缺失类术语否定规则（修复 CBAVD）、起病年龄由代码映射到 HPO 起病术语；语义检索暂缓（剩余漏提不是检索问题）。详见 Step 2 契约 v2.5 |
| 3.0 | 证据账本与公共基础 | ✅ 已验收（2026-11-03，tag `step3.0-accepted`）：联网验收硬性项全过；规则 16 基因起草、独立支持度核查。规则现状（2026-11-06 审阅后，审阅表 `docs/rules_review_2026-11-05.md`）：共 15 条，**4 条已加载、11 条已否决、0 条待审**。COL1A1-1/2/3/4 收窄条件后重跑支持度核查仍卡在"结论"与"适用范围"，COL1A1-6 是"often lead to"，2026-11-06 一并否决："报告过 / 常常"不足以支撑"指向某个病"，涉及外显子丢失与剪接的又依赖 Step 1 不做的剪接预测；不新增提示型规则。契约 `docs/step3_0_contract.md` |
| 3a | 已确立层（Existing Targeted / Supportive / Contraindications） | ✅ 已验收（2026-11-04，tag `step3a-accepted`）；补充修复（提示词 `3a-v5`：表格行与段首限定作条件、治疗类转介、漏抽补抽、放宽从句、按变量合并缺失信息等）✅ 已验收（2026-11-05，tag `step3a.1-accepted`）：6 个练习病例 20/20 核实期望成立。规则变更见 3a 契约文末 |
| 3b | 临床试验 | ✅ 已验收（2026-11-05，tag `step3b-accepted`）：5 个练习病例 8/8 核实期望成立；逐条标准映射（LLM 映射、代码核验与比较）、病人事实模块、eGFR 公式（与 NKF 计算器核对）。契约 `docs/step3b_contract.md` |
| 3c | 老药新用 / 扩展使用（Off-label & Expanded Access） | ✅ 已验收（2026-11-06，tag `step3c-accepted`）：5 个练习病例 7/7 核实期望成立、全部新鲜输出、账本校验全过。契约 `docs/step3c_contract.md`（规则变更见文末 1–15 条） |
| 3d | 定制疗法（Bespoke Therapies） | ✅ 已验收（2026-11-08，tag `step3d-accepted`）：12 个练习病例 8/8 核实期望成立、全部新鲜输出。48 条判定中 12 条"无法评估"（25%）：PAM 5、结构域 3、天然跳跃证据 3、上调靶点 1——全是审阅决定暂缓接入的数据源，**没有一条因机制取不到**（GeneReviews 供得上）。契约 `docs/step3d_contract.md` |
| 3e | 药物重定位（Drug Repurposing） | ✅ 已验收（2026-11-08，tag `step3e-accepted`）：5/5 核实期望成立。12 个练习病例里只有 GRIN2B 产出候选（62 条机制记录排除 56 条，全因方向相反；保留 NEBOGLAMINE / RAPASTINEL / APIMOSTINEL，均标注"对本亚基选择性未知"）；DMD 的外显子跳跃 ASO 按药物类型转交 3d；其余基因在 Open Targets 无药物记录，整节留"检索无结果"负面证据。契约 `docs/step3e_contract.md` |
| 盲测 | 在未调过参的病例上量写错 / 漏写 / 有条件率 | **修复阶段已收尾（2026-11-15，tag `step3-fix-accepted`）**：复测 4 例（retest-20261112）发现的 Tier 1 写错全部修复，PFN1、EIF2B1 用于修复不计入盲测率，按既定规则不再开新一轮复测；结论与已知局限见 `docs/experiments/blind_test_results.md` 文末，存档 `out/archive/step3-fix-accepted-20261115/`。此前：**批次 20261108 已跑完（2026-11-11），进入修复阶段**：修复计划 `docs/post_blind_fix_plan.md`（审阅通过后开工）；结果与事故记录 `docs/experiments/blind_test_results.md`（B 组前 4 批因病例文件字段名写错、在无描述条件下运行，已修工具并全部重跑）。方案 `docs/blind_test_plan.md`（v0.2，2026-11-08）；机械召回评估方案 `docs/blind_recall_plan.md`（v1.0 定稿，2026-11-10，B 组跑完后统一计算）：A 组 2 个（Phase 1 Validator）+ B 组 10 个（5 个有 GeneReviews 专章、5 个只有 GenCC Definitive 评级，后者的临床描述由代码按 HPO 表型合成并标注）；抽样规则写死可复现，抽到的基因先过目；机器先判六项可机判的检查，其余列给审阅人；**盲测期间冻结代码**；写错率偏高的处理顺序已定（先通用修复 → 换新一批验证 → 3a 必须修好或降为有条件才能进 Step 4，3d/3e 降级措辞或整节写无法评估）。约 \$0.5，待充值后执行 |
| 4 | 报告组装（按官方模板生成 markdown、格式校验、引用核验） | `aitx/report/` + `scripts/build_report.py`，不用 LLM；2026-11-17 按官方原文、完整试验 / 支持治疗、证据链和安全覆盖修订，PRAC-AGXT-c33dup 报告重建，格式与确定性核验 PASS；待用户内容审阅，详见 Step 4 契约第 19–21 节 |
| 5 | 对照病人条件 + 报告组装 + 格式校验 + 引用核验 | **确定性部分已实现**（2026-11-17）：`scripts/validate_report.py`，生成后自动校验标题、Evidence ID、计数及临床数量原句，失败非零退出；医学语义支持度部分未实现，不能据此称完整 Step 5 验收通过 |

## 医学文献阅读规则（2026-11-11）

`docs/clinical_reading_rules.md`：**怎么读来源**的规则（不是医学知识），从盲测写错中提炼，每条附盲测正反例和测试集条目。两个用途：
- Step 3 语义核查（上下文核查）提示词的依据——提示词只写原则，规则里的例子不得进提示词（测试集泄漏检查会拦）；
- **审查任何报告 / 账本输出时，逐条过文末的审查清单**（基因是病因还是标志物、表格行所属亚型、他基因 / 他亚型 / 他物种证据、不良反应≠治疗先例、禁忌例外从句极性、条件程度不放大、完整上下文等）。
新的写错先归到已有规则，归不进去才新增规则。

## 练习与验收数据

`data/cases/practice/official_examples.json`：官网 Phase 0 的 12 个示例病例，临床描述逐字取自官网（2026-11-03 核对；SLC35A2 拆为 ex7 / ex8），部分有标准答案（例如 KMT2B c.8079delC 不触发 NMD）。
开发调试优先用这些练习病例，最后才跑 4 个评测病例，避免过拟合。

### 评测病例的保险（2026-11-08）

**起因**：一条不带 `--case` 的 `run_pipeline.py --from-step 3` 按 `CASE_FILES` 跑了全部文件，把 AITX-40001/40002/40003 的 step 3 输出重新生成了（40004 保持 11-03 的旧文件）。跑它们本身不算过拟合，**看它们的输出并据此调代码才算**；当时已立即停掉进程，没有读这三个文件的内容。
**处置**：`out/step3/AITX-4000{1,2,3,4}.json` 四个文件已删除，回到"评测病例未跑"的状态（step 3 之后没有任何产物，最近的查看页导出是 11-05，早于这次误跑）。`out/step1`、`out/step2` 下评测病例的旧输出保留——它们是确定性变异解析和疾病归一化，不含治疗内容。
**保险**：
- `run_pipeline.py` 不带 `--eval` 时**跳过**评测病例并打印 `[HELD BACK]`；**点名**跑（`--case AITX-4000x` 或直接给它们的文件）会被拒绝并提示用 `--eval`；评测病例的 id 从它们自己的文件读，不靠名字猜。
- 所有 step 3 验收脚本（3.0 / 3a / 3b / 3c / 3d / 3e）调用 `runmeta.refuse_eval_cases`，碰到评测病例直接退出；`acceptance_step3_0.py` 里原来打印 AITX-40003 分支的那段已删除。
- 测试 `tests/test_eval_holdback.py`（含静态检查：任何 step 3 验收脚本或期望文件都不许出现评测病例 id）。
- **Step 1 / Step 2 的评测病例期望已挪走**（2026-11-08 决定）：这些期望当年是按公开数据库记录（RefSeq、UniProt、OMIM、ClinVar）定的，所以保留，但移到 `scripts/acceptance_eval_cases.py`，**只有加 `--eval` 才会运行**；`acceptance_step1.py` / `acceptance_step2.py` 现在只读练习病例并调用 `refuse_eval_cases`。期望内容和出处存 `data/eval/eval_case_expectations.json`。
  - 被一起挪走的还有 Step 2 的一条硬检查（"同一基因里另一个变异不得用于排序"，原来写在 AITX-40002 上）。**2026-11-11 已补练习病例的等价反向用例**：PRAC-AGXT-c33dup 的 ClinVar 检索也返回了另一个致病变异 c.508G>A，必须被拒、不得用于排序；另加一条通用硬检查：每个练习病例用于排序的 ClinVar 记录都必须是病人自己的 c. 变化。
  - `acceptance_eval_cases.py` 的 Step 2 部分只读 `out/step2/` 已有输出，自己不跑流水线、不调 LLM。

## 用户背景

用户是 agent / RAG 工程师，非生物专业。解释生物概念时用软件类比，用中文交流。

## 2026-11-17 第三轮报告审阅追加规则

用户更正：Step 3d 的 classification、failed_criterion、exceptions、unassessable_reason 属于代码判定，必须按账本原文显示；上轮删除无来源技术论证的规则仅针对缺来源的文献性论证，不再据此隐藏代码结论。具体报告规则见 Step 4 契约第 22 节。

3b 已核实注册条款本身完整，问题来自缓存映射摘取残片 / 放行例外后沿用 exclusion。用户批准恢复完整原文并将无法可靠组合比较的例外条款保留 unknown，要求恢复文本为来源连续逐字子串；Known exclusions 新增必须为 0，有新增先停下汇报。第一次预检发现 AGXT 与 CFTR 各一条分组年龄误排除后已停止，正式账本未写入。用户随后批准统一规则：**只有结构化 minimumAge / maximumAge 总范围之外可产生年龄排除；文字分组年龄能明确匹配才满足，否则未知；已有分组识别只用于确认满足，不得产生排除**。不逐个扩充标题模式。最新 15 例、186 项试验缓存预检新增 Known exclusions 为 0；正式重跑后继续逐项对比。

本次只用缓存，真实调用 0 次的报价仍为 $0；缓存缺失即停，不启用新请求。新增回归后离线 1206 个测试通过。将继续生成 AGXT-c33dup、ANO10、KMT2B 三份报告并运行可跑验收；DMD 继续按原决定延期，评测病例不运行 Step 3 及以后。

**2026-11-17 第三轮审阅完成**：实现 `8e5ea29`，离线 **1206/1206**；15 例 LLM 缓存完成、新鲜账本无 fail。186 项试验 Known exclusions 列表完全一致，原始判定记录 **124 → 124**（试验内去重条件 **122 → 122**），新增 **0**；行动 / 分支总状态与 3d classification 变化 0。112 组条款表示 / 判定变化已逐项归档（100 年龄、12 完整例外合并），见 `out/acceptance/agxt_review3b_changes_20261117.md`。Step 1 / 2、3a 30/30、3b 8/8、3c 7/7、3e 5/5、评测 Step 1 / 2、三份报告格式 / Step 5 全过；3d 6/8 整体 FAIL，DMD 两项过期未计分，3.0 继续延期。**DMD 因性别推断改动而过期，待下次影响 DMD 的改动时一并重跑**，其字节未改；评测病例未跑 Step 3 及以后。报告：AGXT-c33dup 59,359 字节、ANO10 17,520、KMT2B 23,552，均 <60 KB；Evidence ID 定义分别 265 / 53 / 77 个，存在、verified、唯一，英文 / 官方标题 / 行内上限 / 去重 / 数值原句检查通过。3d 原判定与理由原样显示；例外原文完整、未知，不新增排除。COL1A1 交替体位仍漏婴儿限定，支持核查假拦仍历史 3/17。全部尝试真实 DeepSeek 请求 **0 次、费用 $0**。CNNM4 一次 HTTP 重试拼接响应错误在临时 curl 传输脚本修复，单条损坏 HTTP 缓存清除后续跑；不改临床代码、LLM 缓存。详情见 Step 4 契约第 23 节与 `out/acceptance/agxt_review3b_20261117.json`。

## 状态基线与报告契约（2026-11-17，当前必须遵循）

- 报告契约当前版本为 `docs/step4_contract.md` **v3.0**；Ranking、Summary、Clinical Trial Table 以其第 4 / 6.4 / 6.5 / 6.6 节为准，覆盖同主题旧记录。第五轮明确：试验按类型/招募/排除/关键纳入条件/未知数；超说明书按疗效方向与独立PMID数；Tier1 Summary先applicable再conditional；观察研究不进Summary。实现及尚未完成的缓存依赖见下方最新运行记录，不将局部通过当作整轮通过。
- 每次修改 Evidence Ledger 或判定逻辑，改前保存快照，改后必须附 `scripts/status_diff.py` 对 **baselines/current** 的输出（snapshot.json、diff.json、diff.md）；它逐病例记录行动×分支的状态、原因、Evidence ID，列出所有新增/删除、状态、原因和证据变化。缺输入报错；没有历史基线时不补旧状态。未解释的变化视为潜在缺陷，必须调查；账本自带 reason 不等于合理解释或批准。
- `baselines/historical/step3a.2-accepted/snapshot.json` 来自真实验收存档（提交 652f6c8，原 manifest SHA 核对），只读且永不覆盖。现有 15 例中只覆盖 11 例，4 个 RETEST 当时不存在，明确为缺基线。current 初始化为 historical 的字节副本，2026-11-17 已按用户明确批准的 A/B/D/E 部分升级为 529 行；未批准项不在其中。
- `scripts/promote_baseline.py` 只能在用户逐条批准实际 diff 后运行。批准文件必须精确覆盖每个 change_id，并匹配基线/候选 SHA-256 和 HEAD，含实际批准人、日期、总体及逐条理由；缺任何批准就停止。每次升级只追加 `baselines/approvals.md`，历史不改，代理不得自行批准。格式与命令见 `baselines/README.md`。
- 首次对比：历史 409、当前 790 个行动×分支项目；29 项直接匹配的状态变化，其中 11 项降为 not_applicable（KMT2B 6、CFTR 5）；另有细节变化 61、新增 231、删除 7、缺历史病例基线项目 157。完整工具输出在 `out/status_diff/initial-20261117/`，逐项追因与潜在缺陷在 `docs/experiments/status_baseline_review_20261117.md`。本轮没有改账本、重跑临床流水线或升级基线，真实 LLM 调用 0 次、费用 $0；全量离线 1223/1223。

**2026-11-17 基线审核落实**：用户批准 A 目的规则5、B CFTR新生儿5、D投票核查不确定性11、E指定结构变化。已先通过 `promote_baseline.py` 升级 **151 项**（A5/B5/D11/E新步骤124/键规范化2/over_cap4），current 529 行；历史409行只读未动。D11含6 scope+5 degree，两项 small-joint HPO 未知不在此批准组。C6、61项证据细节、其他未批准新增/删除、RETEST首次基线均未升级。4个RETEST待本轮报告审阅通过后再以当时结果建首个基线。

两项试验均仍RECRUITING，但NCT01822834明确non-CF/NTM且排除CF，NCT07513051是新生儿呼吸窘迫/CF-CPAP，与该CFTR病例无关，不是召回缺口，不改检索。61项ID差异不是算法变更：18仅新增证据、43内容/集合变化，旧ID全部能用当前算法重算；不满足“仅ID算法变更”的批量批准条件，继续待审。审计见 `docs/experiments/trial_recall_audit_20261117.md` 与 `docs/experiments/evidence_id_audit_20261117.md`。当前ID实现和身份上下文已冻结并补黄金向量测试；新增6条核查稳定性观察（KMT2B4药、ANO10两项混合病因），只记录缓存分歧，不添加病例代码规则。升级前离线1227项通过。接下来才实施已授权C修复与文字修正，对新current出diff，不自动升级修复结果。

**2026-11-17 C 修复与第四轮显示实现待缓存验收**：在151项基线升级提交58dd09f之后实施。R15来源措辞仅降为unknown/conditional，保留真实病人不符；Pregnancy Management只作已有同名行动附注，不单独产生行动/缺失信息；split文字为check votes disagreed; unknown，KMT2B四药状态不改。新增GPi/subthalamic DBS验收。按v2.0同步实现来源顺序Ranking、Summary正文一致/只统计显示行动、可读枚举、Note去重/NCT清理与脚注显示。脚注不改原始提取文本或原始Evidence ID，不改提示词/模型参数。离线1236项已过，接下来只缓存一次重生成15例和三份报告、验收、对current输出diff；缺缓存立即停，真实调用先报价，不自动升级C或RETEST首个基线。

**2026-11-17 C 修复缓存阶段结果（部分完成，不能称全部验收通过）**：代码至 `e1b7f56` 已推送，离线 **1238/1238**。实际完成14例整例缓存尝试；COL1A1候选出现physiotherapist两分支applicable→conditional，与用户“只改文字不改状态”冲突，已隔离候选并逐字恢复原正式账本，等待裁决。KMT2B移除孕期独立行动后3c新选中PMID 35418819/37168666/31388109，三篇无抽取缓存；第一篇被$0预算拦在真实请求之前，未覆盖原账本。另行只读3a专项自检和KMT2B五项验收 **5/5**，GPi/subthalamic为conditional且不再被已移除的孕期总类隐藏；另四个孕期独立项移除，四药split仅改文字、状态仍conditional。正式新鲜账本 **13/15**；Step1/2、评测Step1/2、3b **8/8**、3c **7/7**、3e **5/5** PASS；正式3a **25/32 FAIL**（KMT2B5、COL1A1 2过期未计分），3d **2/8 FAIL**（DMD2、KMT2B1、COL1A1 3过期未计分），3.0仍延期。**DMD 因性别推断改动而过期，待下次影响 DMD 的改动时一并重跑**，原文件未改。AGXT/ANO10已生成并通过格式和Step5，58,773/17,692字节；KMT2B完整报告尚未刷新。15例186项试验Known exclusions新增0；对改前的审阅候选共20状态变化、20孕期独立项删除、5细节变化，新增不适用0；两项physiotherapist未发布，其余R15放宽及孕期移除均逐项解释。current529行、历史409行SHA不变，C/证据61项/RETEST均不升级。本轮所有尝试 **真实DeepSeek请求0次，费用$0**，长任务nohup+caffeinate；缓存不传启动门禁CLI --offpeak-only，仍保留真实请求前高峰保护。详见 `docs/experiments/c_repair_review_20261117.md`、`out/acceptance/c_repair_review_20261117.json`；对current的正式输出 `out/status_diff/c-repair-20261117/canonical/`，另供审阅的KMT2B仅3a+隔离COL1A1候选输出在 `review/`，不得将它当整例新鲜账本或直接升级。报告：`out/step4/PRAC-AGXT-c33dup.md`、`out/step4/PRAC-ANO10.md`；submission只含这两例。

**2026-11-17 用户更正批准已落实，COL1A1 不再等待裁决**：用户明确撤销此例“只改文字不改状态”，批准 physiotherapist 两分支 applicable→conditional；旧 applicable 依赖孕期段落，对本病人无效，应按普通来源核查结果。代码 `26a54c5` 在不改变核查/分级的前提下，把 reason 写为普通 GeneReviews NBK1295 治疗段落对各诊断分支的适用范围尚未确认（source-scope check unknown），没有补写年龄/表现程度等临床条件。离线 **1240/1240**，正反测试过真实判定路径。已缓存重跑并正式发布 COL1A1；通过升级脚本仅纳入这两个 status/reason 变化，ID不变，批准与纠正原因追加 `baselines/approvals.md`；升级提交 `79e93d6`，current仍529行（累计153项已批准diff），历史409行不动，其他C/证据/RETEST不升级。14例完整缓存刷新成功，正式新鲜 **14/15**；KMT2B完整3c仍缺三篇缓存，保留原账本，另3a只读专项5/5。Step1/2、评测Step1/2、3b8/8、3c7/7、3e5/5 PASS；正式3a **27/32 FAIL**（KMT2B5过期），3d **5/8 FAIL**（DMD2/KMT2B1过期），3.0延期，不能称全套通过。**DMD 因性别推断改动而过期，待下次影响 DMD 的改动时一并重跑**，未改其原文件或运行评测Step3+。新增不适用0、15例186项试验Known exclusions完全一致；本次实际差异仅获批physiotherapist两分支及通用孕期规则移除四个独立项。AGXT/ANO10报告再次生成并通过格式及Step5，大小58,773/17,692 bytes；KMT2B完整报告仍延期。此次真实DeepSeek请求 **0次、费用$0**。最新汇总 `out/acceptance/col1a1_approved_20261117.json`；对新current的完整输出 `out/status_diff/col1a1-approved-20261117/canonical/`，改前对比 `since-before/`，KMT2B仅3a的C审阅 `review/`（不可当整例新鲜账本或直接升级）；详情见 `docs/experiments/c_repair_review_20261117.md` 第7节。

**2026-11-17 第五轮 $0 部分完成（真实调用未批准）**：提交4f243ab，契约升v3.0，排名/观察研究Summary排除规则及正反测试完成，离线1243项全过。14例整例缓存刷新，账本状态/原因/ID相较改前变化0，Known exclusions186项不变；Step1/2、评测Step1/2、3b8/8、3c7/7、3e5/5 PASS，正式3a27/32及3d5/8因KMT2B/DMD过期未全过，3.0延期。KMT2B只读3a5/5，正式账本与DMD未改，评测未跑Step3+。AGXT/ANO10报告重新生成并过格式及Step5，59,017/17,671 bytes。

第五轮明确批准的四项已用promote补升：此前误按投票分歧筛D组，漏掉ring splints及wrist/thumb braces两项HPO未知，现按braces×3批准补升；另删历史not_applicable的NCT01822834/NCT07513051。approvals.md记原因，current527行、累计157项已批diff，历史不动。原106新增/18删除/57细节的181项分类：病例级3b首接E同类25、3a来源/回退57、孕期删除16、本轮已批NCT删除2、证据内容/集合57、ID方案0、其他新增试验24。623个病例×旧ID重算一致。155项只形成未批准候选（593行），24项其他逐条待审；不升级提案或RETEST首个基线。完整分类与实际行见docs/experiments/status_diff_review5_20261117.md；新current完整diff在out/status_diff/review5-20261117/canonical/，KMT2B仅3a审阅在review/，155项提案在batch-proposal/；验收汇总out/acceptance/review5_20261117.json。

报价未授权、未运行：KMT2B两篇旧请求仍命中，移除孕期独立行动改变3c选文集合，三篇首次抽取无缓存，不是旧缓存失效。至少3次文章请求，后续核查/下游次数待抽取后确定，估价$0.01–$0.03、建议独立硬上限$0.06。Step2按15状态快照病例（含4RETEST、不含DMD）+4评测×5轮完整三票Step2=95轮；必需285次初始抽取、可选0–285次HPO选词，未计重试正常范围285–570。19例只读缓存形状预计445次（285+160），同接口模型18条历史样本均价估算$0.4244，建议独立硬上限$0.60；须逐病例逐轮隔离LLM缓存、固定资源/Step1、不覆盖正式Step2/共享缓存、不跑评测Step3+。官方当前非高峰费率已核实与项目一致。详见docs/experiments/review5_quotes_20261117.md；两报价均未批准，不能沿用已结束的$0.17额度。此次所有尝试真实DeepSeek请求0次、费用$0。

**2026-11-17 用户最新指示：LLM先停止**。暂停KMT2B $0.06刷新及Step2 $0.32稳定性真实调用；旧授权不代表可在明日自动恢复。已停用明日自动任务，当前无流水线/模型调用进程；等待用户明确恢复。$0代码与MONDO预审工作可继续。

**本次审核及最新停止指示**：已通过promote升级155项候选与AGXT/CFTR试验6行，共161项，current599行；COL1A1 EDS18行仍待预审后决定，未实现亚型排除规则。18行预审见docs/experiments/COL1A1_subtype_review_20261117.md；vascular MONDO层级接口超时，未当空祖先判排除；hEDS/HSD或关系中的HSD未映射保持未知。Summary Tier2已加简称/干预药物名（ABO-101示例），离线1244项通过，两报告格式/Step5通过；未重跑模型或整例验收，15例正式账本文件逐字未动，Known exclusions无变化。用户原授权KMT上限$0.06、Step2缩减65轮上限$0.32（既有结果额外一次），随后明确“llm的话先停止”，该最新指示覆盖执行安排。Step2自动任务step-2已PAUSED，KMT未启动，不自动恢复；实际调用0次。仅继续$0代码/数据审核工作。

**2026-11-18 Step 2 独立稳定性验收完成**：用户在先误选暂停后明确批准新报价（约$0.09、独立总上限$0.32），仅恢复本次四练习病例CFTR/COL1A1/GRIN2B/SLC35A2-ex8各5轮，不恢复旧65轮自动任务或KMT2B。20轮均原三票，独立空响应缓存、固定各病例原数据库快照及62份HTTP响应、nohup+caffeinate、非高峰串行，生产Step2代码/Prompt/参数未改；90次真实请求，响应缓存命中0、重试0、高峰0、usage缺失0，实计 **$0.055719696**。全部20轮自检通过，Top1/分支/状态/疾病候选集合变化0，内部60份诊断一致；**诊断稳定性通过，症状并非完全一致**：CFTR第3轮两票漏提chronic sinopulmonary disease，使最终HPO从HP:0005425泛化为HP:0002719，分数5.0933→4.964，明确诊断仍resolved。其余19轮HPO与各自参照一致，不挑结果、不改规则。冻结代码与全部20轮观测（含该波动）在baselines/step2/stability-20261118，current.json独立于行动current；状态diagnostic_stability_pass_with_documented_extraction_variability，不能称全字段稳定或总体准确率已证明。服务端只返回deepseek-flash别名，文档对应DeepSeek-V4.1-Flash-1017，不能独立验证权重版本。离线最终1247项通过（含重复执行在预检写盘前拒绝的保护测试；执行时实验脚本副本及哈希保留），69个正式输出/行动current文件哈希不变，未改Step3/4、未跑评测病例、未升级行动基线。完整结果/逐轮费用/原始Prompt/40对Diff见runs/step2-stability-20261118；验收报告docs/experiments/step2_stability_acceptance_20261118.md；随后制定docs/experiments/step3_staged_acceptance_plan_20261118.md，仅计划，未授权新调用。旧自动任务仍PAUSED，KMT2B仍暂停，DMD延期原决定不变。

**2026-11-18 四评测病例 Step 2 补测完成，后续先停在此**：用户批准 AITX-40001–40004 各5轮、只Step2、非高峰、独立硬上限$0.10；已完成20/20轮、每轮原三票，119次真实请求（60抽取+59选词），无响应缓存复用/重试/高峰/usage缺失，费用 **$0.068315367**。40002首选SCA29 MONDO:0007298及ambiguous **5/5一致**，40003首选HSAN1 MONDO:0018213及ambiguous **5/5一致**；其余两例5/5 resolved。全部60份内部诊断无分歧，最终HPO/候选集合/分支均稳定。40003个别票HPO有波动但合票稳定；40002仅de_novo引文跨度不同、含义不变。未调参、未改生产Step2/Prompt/参数、未跑评测Step3，69个正式输出/行动current文件哈希不变；原练习观测基线未覆盖。独立实验脚本增加显式输入文件/实验目录参数，共用原逐请求预留保护；离线1248项通过。完整结果、逐轮费用/Prompt/40对Diff在runs/step2-eval-stability-20261118，汇总out/acceptance/step2_eval_stability_20261118.json，文档docs/experiments/step2_eval_stability_20261118.md。

用户已批准三练习病例×2次完整无缓存Step3的独立上限$1.20，**随后要求“你先完成step2 我后续有安排”**：因此六次真实Step3尚未启动，等待后续安排，不自动执行。旧step-2自动任务仍PAUSED。此前获批KMT2B增量刷新已在隔离目录完成（3个有usage响应$0.007798854，另1次TLS中断实付未知、按请求上限$0.01230265计入预算，累计保守$0.020101504<$0.06）；自检通过，正式账本尚未发布，产物runs/step3-stability-20261118/kmt2b-refresh与kmt2b-publish，Diff已保存out/status_diff/stability-followup-20261118。CFTR泛化HPO缓存实验和报价已保存该运行目录；132组3a新上下文缺缓存、3c未测，临时结果不可当完整正式账本。其余Step3/4工作先暂停；DMD延期不变。

**2026-11-18 最新分阶段Step3决定及当前停止原因**：用户撤回一次性$1.20，改为先CFTR $0扰动实验、KMT2B $0.06增量刷新，再AGXT/KMT2B各2次独立完整Step3，独立硬上限$0.50，CFTR真实执行暂缓。余额接口执行前返回19.44 CNY且可用。CFTR缓存实验已完成但132组3a缺缓存、3c未测，可比较确定性条件变化0，不能称全量稳定；报告docs/experiments/cftr_hpo_sensitivity_20261118.md。KMT2B已从隔离缓存复核结果发布正式账本，自检无fail、专属3a5/5且fresh；2DBS降conditional、4孕期独立项删除、4reason文字改动均为既有授权修复，不升级Accepted，完整diff在out/status_diff/staged-step3-20261118/kmt2b-published-*。刷新已知$0.007798854+一次TLS实付未知按$0.01230265预留，独立预算记账$0.020101504<$0.06。

$0.50独立实验**尚无完整运行（0/4）**：首AGXT尝试因RxNav缺Nedosiran大小写查询停止，13响应$0.039876528；NLM文档核实大小写等价且已有两份响应同为2675287后，仅由既有响应生成别名输入夹具，代码未改、重新冻结，原费用日志全部计入同一上限。第二AGXT尝试因新完整行动名“vitamin C intake that exceeds the recommended allowance”触发快照外RxNav查询停止；增量12响应$0.043761663。累计25响应、已知$0.083638191，无usage缺失/高峰，剩余$0.416361809；两次输出截断按原策略各重试一次的费用均包含。没有为结果一致挑选输出，没有改规则或Accepted Baseline。先后目录runs/step3-staged-050-20261118与step3-staged-050-v2-20261118均state=stopped；不要把第二目录汇总25次再加首13次（已合并记账）。所有付费进程已结束。

后续$0预检使用自身已付费响应+既有缓存，记录107份HTTP响应，碰到新引文修复请求缺缓存，3a/3c仍未测。已向用户请求澄清：维持所有外部响应冻结只做$0，还是允许仅RxNav实体归一化新查询只读联网/记录版本（其余检索仍冻结），再在剩余额度内继续；**答复前不得恢复真实调用或擅自放宽冻结边界**。不能把空RxNav响应当临床不适用，也不能把整句改成vitamin C藏掉差异。结果与费用docs/experiments/step3_staged_results_20261118.md。status_diff可选--detailed已支持classification/条件/引用/投票，旧基线无详细字段明确unavailable；投票缺票算未测。Accepted current哈希不变，正式69文件只变了获批KMT2B，评测Step3未运行，DMD延期与旧自动任务PAUSED继续有效。

**2026-11-18 用户已明确放宽RxNav边界并授权剩余额度继续**：允许仅RxNav药名归一化只读联网，记录数据库/API版本并保存响应，其余外部检索仍冻结。原$0.50总账已知$0.083638191继续计入，剩余$0.416361809，不是新开$0.50。将使用新的v3夹具与独立空LLM命名空间开始四次完整执行，保留前两次未完成尝试，不跨运行复用响应。允许端点仅/REST/rxcui.json和/REST/rxcui/<数字>/related.json；版本接口在每次执行前后实查并核对。判定代码/Prompt/模型参数/Accepted Baseline不变。重新核实余额18.88 CNY且可用。其他来源新缺口仍必须抛错，不默认空结果。当前仅授权此边界，不恢复CFTR真实Step3，也不增加预算；1253项离线测试通过。

**2026-11-18 RxNav获批后的最终结果：本轮停止、完整稳定性仍未测**。四个v3预登记位置均已尝试，AGXT×2/KMT2B×2完整结果**0/4**；连同此前两次预备失败共60个真实响应、累计**$0.216072843/$0.50**，剩余$0.283927157。usage缺失0、高峰0，五次原策略截断重试费用已包含；不是额度耗尽，所有付费进程已结束。仅RxNav归一化联网，原5242份HTTP哈希未变，新增3份名称查询及1份版本响应；RxNorm 02-Nov-2026/API 3.1.357各次启动前与最终审计一致，异常退出没有正常逐次结束检查。恢复前余额18.88 CNY、结束18.00 CNY，未把余额差换算美元。

阻断根因为drug_key链在RxNav无匹配后继续查询冻结的FDA品牌归一化接口：AGXT两次分别为整句vitamin C限制和NSAID注意事项；KMT2B两次均为原Pregnancy Management来源拼写trixhexyphenidyl。归一化发生在孕期独立项过滤之前，故即使后续应只作附注也先触发新查询；仅调查，未改拼写、过滤顺序、来源权限或临床规则。原始相同源提示AGXT11份中8份回答不同、KMT2B5份中3份不同，但完整行动/状态/classification/条件/Evidence IDs/引用/核查票均**未测**，不得报告零变化或稳定性通过。未为得到一致结果挑选或额外重复运行；CFTR真实执行仍暂缓，Accepted Baseline未升级。

最终离线**1254项通过**；正式输出仍仅获批KMT2B增量发布有变，评测Step3+未跑，DMD延期、旧自动任务PAUSED不变。status_diff详细字段与独立核查票比较已测试；正式完整结果缺失时分析器明确unavailable。全部费用、原始抽取Diff、RxNav权限审计和失败日志见runs/step3-staged-050-v3-20261118；汇总out/acceptance/step3_staged_stability_20261118.json，说明docs/experiments/step3_staged_results_20261118.md第8节。下一步须先明确整条身份归一化链的数据冻结边界，本轮不自行扩大FDA/ChEMBL联网、不修临床规则、不继续付费。

**2026-11-18 $0 Step3环境审计完成，继续暂停真实调用**：用户要求保留$0.28393、不改临床规则/Accepted、不扩大联网。scripts/step3_preflight.py离线回放四个v3失败位置，逐候选走真实drug_key，固定GET/POST、封锁urllib/socket/llm.chat；全部四次历史停止URL和缓存Key复现，RxNav均已缓存无匹配，FDA响应缺失。入口按drug或Avoid段avoid收窄后5条候选缺口/4个唯一FDA查询（其中3个唯一查询造成四次历史中断），不能把初步保守扫描14条全当真实阻断。AGXT是注意事项名称改写/合并，KMT2B是原文trixhexyphenidyl与历史trihexyphenidyl抽取拼写差异，未证明新增临床行动；药名归一化先于孕期过滤的顺序未改。

实验脚本每次模型回答返回后立即保存Prompt、原始回答、已有分类字段，complete=false/safety_validation=incomplete；阶段异常finally另写incomplete.json，checkpoint不算完整验收。现有3a原始字段为kind、没有最终classification，明确未生成，不补写。四次历史原始回答在新审计目录补导出，原目录和夹具不改。已知候选Preflight退出2，能在再花钱前阻止已知缺口；不能保证开放模型名称或未生成3b–3e依赖全部覆盖，禁止宣称完整就绪。未来若再获批执行须重新冻结工具版本，不修改旧manifest。离线1258项全过，原始保存后模拟归一化失败专项4项再过，114份正式输出/基线哈希不变。真实调用0、费用$0，累计$0.216072843与剩余$0.283927157不变；不自动重跑。报告docs/experiments/step3_offline_environment_audit_20261118.md，完整链/URL/名称/RxCUI/HTTP与LLM键/历史对照见runs/step3-offline-audit-v2-20261118，旧初扫目录仅探索记录。

**2026-11-18 四次3a原始回答回放完成（仅$0模型费，不得自动启动报价方案）**：用户允许补取免费公共接口响应并隔离保存，要求先报价再批准真实3a。四次按指定raw_extractions走生产3a路径至组装末端，缺新的同义合并响应时仅保存未合并清单、明确incomplete；没有伪造模型回答。AGXT两次21/22行动，KMT2B两次20/21（不含None found占位）。按报告审计对齐三类：仅措辞10/6/0/0；行动记录增减−2/0/+1−2/0；状态、条件或类型差异1/5/9/9（全部待核查，非确认临床状态变化）。AGXT1高饮水和IV fluids被新回答列therapy而被现行词表过滤，KMT1具体器具变adaptive aids，未修规则。AGXT2腹膜透析oxalosis、KMT康复DD/ID及IEP等新增条件作为待核查差异列出。

已知4个唯一FDA URL均404，初回放共5次FDA查询。AGXT2个新ChEMBL查询请求失败无可用响应；首次探索生产_json吞掉了未完整记录的ChEMBL错误，第二轮补记RuntimeError失败类型/时间，不伪装成查无结果，仍按生产fallback继续并保留incomplete。首次探索该类网络重试准确次数未知，不能给出虚假总请求数。所有公共响应/错误只存实验http，不写正式缓存。四次共183个缺缓存上下文请求+4同义合并，独立回放补核查估$0.09945；精确Key去重156+4估$0.08643，只能叫回放补核查，不能叫独立稳定性。历史同模型context-check-v3 200份均价$0.00048246、3a-v5 69份均价$0.00279004。全部新的真实模型调用0、费用$0，剩余$0.283927157不动。

下一阶段等待批准：推荐KMT2B×2只3a，两个空LLM命名空间、固定外部夹具/代码/Prompt/患者输入、非高峰、跑前查余额；预计306请求、均价估$0.1753，含重试报价$0.18–$0.23、硬上限剩余$0.283927157。备选AGXT×2 343请求，均价$0.2301、含重试$0.25–$0.28；四次合计均价$0.4054已超剩余额度，不自动跑。动态合并/limit核查可能增加请求，按逐请求最大预留不足即停，不能承诺完成。不会把用户四舍五入$0.284作为额外预算。

scripts/replay_step3a.py新增原回答/历史缓存回放、公共GET隔离补取、禁止llm.chat、待核查统计及--offline复核；未修改生产判定或Accepted。纯离线复核AGXT1行动/条件及待核查Key完全相同，公共新请求0。1260离线测试全过，114正式输出/基线哈希不变。详情docs/experiments/step3a_replay_results_20261118.md，四次逐项清单/原始响应/失败记录/报价样本runs/step3a-replay-v2-20261118；对正式账本和Accepted的完整status_diff输出out/status_diff/step3a-replay-v2-20261118，汇总out/acceptance/step3a_replay_20261118.json。首轮探索目录runs/step3a-replay-20261118不是最终审计结论。此次未执行3b–3e，未生成临床Step4报告，未更新正式账本/基线；仍等待用户选择及批准真实3a方案。

**2026-11-18 用户继续暂停付费，先修kind/身份键并审三票方案；当前第2项等待必要澄清**：已实施未知kind保留：动作名称有明确类型线索则diet/procedure/device，无法映射other+kind_review_pending及unknown类型条件；不再因therapy未命中受控词表直接丢弃。已知康复类型、章节/孕期规则不变；未知目标/行政候选也只保留待核查，不变成确认适用。格式缺kind/空名抛错。15例选中GeneReviews60主块及实际行补抽缓存全检查，无缺缓存，34条病例×候选曾因未知/词表外类型被过滤（不等于34种未覆盖疗法）；另34条known avoid章节过滤单列，不扩大本次修复。完整名单及原句见runs/step3a-kind-key-audit-20261118。四次固定raw完全离线回放AGXT1/2行动26/23，KMT2B1/2 25/26；AGXT1 high oral fluid intake/IV fluids均恢复。日志线程并发写JSON问题已加锁并finally落完整快照，四次日志修复前后行动完全一致。1268项离线测试全过，回放组装自检无fail，但缺合并/新核查，整体仍incomplete。无模型调用、无新联网、费用$0，剩余$0.283927157不动。

第2项不能直接用现有Evidence ID造key：现有ID哈希含claim/action_key/branches，直接反向生成会循环且不稳定；319条3a身份记录中53个drug键没有RxCUI。已异步询问用户是否接受独立于旧Ledger ID的来源原句锚点、原句实体固定槽位、无RxCUI类别也用锚点并标未确认，或保留未映射旧key；答复前不得实施该替代方案或虚构RxCUI。identity_feasibility.tsv仅给已有RxCUI旧→原值，余项PENDING，不冒充完成映射。正式账本未刷新，Accepted未升级；对改前正式账本0diff及对Accepted完整diff在out/status_diff/kind-key-audit-20261118；四次kind-only完整diff在out/status_diff/step3a-kind-fix-v3-20261118。尚不能声称key差异消除，须用户明确后继续第2项及最终四次重算。

第3项未实施三票。方案：动作并集、来源锚点对齐条件多数、任一范围/存在/类型分歧conditional并保留少数条件；总称与具体项并存时保留原文具体项，留全部原始票，不改患者事实判定/FDA优先规则。粒度需审：现行15例60个Section输入、去重54份，主块加两票为120次逐病例独立或108次共享来源票；按69份历史均价$0.00279004为$0.33480/$0.30132追加抽取，已超剩余额度，且不含FDA/文献/行补抽/新核查，不能冒称完整15例总报价。字面逐Paragraph/Row是483病例×单元，三票1449次，相对现行60增加1389次；章节均价粗代理约$4.04总/$3.88增量，不是已验证单段价格，也不构成执行报价。4例无选定GR章节在主块数字为0，不代表文献回退无费用。详情docs/experiments/step3a_kind_key_review_20261118.md及three_vote_quote.json。真实调用继续停止，等澄清与审阅。

**2026-11-18 用户已接受原句锚点方案，但明确未审前不切换key；只读审计已完成**。锚点=SHA256(JSON[来源ID,来源原始章节路径,仅大小写/空白规范化的原句全文])，现有Evidence ID不变；同句多行动使用名称在保存的原句可读文本中的首次字面字符偏移，拒绝模型顺序、同义猜测或旧key平局。提案source_sentence:<hash>:p<offset>，另列偏移排序展示序号；offset为0起始原句位置，同时保存规范化偏移。无法唯一定位、跨句/路径歧义、不同旧键槽位碰撞或旧键拆分均单列。RxCUI药物不变，无RxCUI药物类别用锚点提案并标归一化未确认。

15例当前3a共319行动记录：65 RxCUI不变、147唯一原句锚点提案、107未决。旧key出现在Accepted current的272条记录中49/130/93；不可声称全319已可迁移。212可确定项在病例+旧key与病例+提案key双向一一对应，无合并/拆分。53个无RxCUI药物条目中36可提案、17未决。未决细分42字面名称在无终止标点片段（不擅自当完整句）、26多句/路径匹配、26未在引用范围定位字面名称及完整原句、13本读器暂未覆盖来源全文/章节信息；不把工具读取不足说成来源不存在或模型幻觉。完整107条单列docs/experiments/action_anchor_unresolved_20261118.md，319旧→新表runs/action-anchor-audit-spec-20261118/mapping.tsv/JSON；所有候选原句、偏移、Evidence IDs、原因保留。

scripts/experiments/audit_action_anchors.py为离线只读提案工具，固定本地数据、封锁模型和网络，不改生产身份函数。1273离线测试全过（13.11秒），114正式输出/基线文件哈希不变，改前→改后diff0，对Accepted current完整既存diff保留于out/status_diff/action-anchor-audit-20261118。费用$0、剩余$0.283927157不动。尚未切换key、未改Evidence IDs、未升级Accepted；等用户审阅映射/未决项，届时才可迁移并重新出diff，不提前将提案套入四次回放宣称key差异消除。kind修复已在ecc436d，三票仍只方案报价、真实调用暂停。最新说明docs/experiments/action_anchor_audit_20261118.md；旧kind/key review已添加后续批准说明，保留历史记录。

**2026-11-18 最新锚点补充规则已只读实现，完成新审计和15例三票费用；正式切换仍未授权**。用户允许完整句/完整单元格/完整列表项，无终止标点的单元格/列表项有效；按引文所在单位、同文档最早位置选锚点；无字面匹配用锚点+规范化名称，未覆盖来源用类型/来源ID+规范化名称，均name_dependent；仍不明确保留旧key。当前319记录四类：RxCUI65、锚点+偏移203、name_dependent49（锚点+名称36、来源ID+名称13）、旧key2。2条为COL1A1 contact sports（NBK1244与NBK1295跨文档无全局先后）与OTC protein intake（引用未能定位规则允许单位）。319旧/新按病例双向一一对应，53无RxCUI药物继续归一化未确认。完整映射runs/action-anchor-supplement-final-20261118/mapping.tsv/JSON。

只在current快照副本模拟：230行动×分支key变化，原始status_diff230新增/230删除；逆映射后0diff，并逐行断言current除身份字段外所有字段完全相同。实际Ledger未切换，114正式输出/基线哈希不变，改前正式diff0；canonical对current的既存差异保留另表，不能混称早已全匹配。输出out/status_diff/action-anchor-supplement-final-20261118，key-only-current-simulation给出raw及key-normalized diff。1276项离线测试通过（13.64秒），真实模型/公共联网0，费用$0，剩余$0.283927157保留。最新说明docs/experiments/action_anchor_supplement_20261118.md；旧107未决页面已标历史。

三票方案只设计未实施：沿用生产Section/Row/FDA条件/文献窗口，每输入3次temperature0，动作并集、条件多数、分歧conditional、保留原文支持的具体项和所有原始票；name_dependent不能假装措辞已稳定。单元身份的完整句/单元格/列表项不等于擅自把LLM输入拆成逐句，后者需另报价。15例纯缓存盘点因未保存404负响应而15/15中断（模型/网络均0，不伪造结果）；改用当前Ledger生成前最近相关session的历史输入，恢复全来源128请求、去重112：主GR60/54、行补抽37/33、FDA条件15/13、文献16/12。THPO明确无选定章节/文献count0及无实际3a行动，源抽取0不是默认缺日志0。逐例输入和session来源由scripts/quote_step3a_votes.py可复现。

15例额外两票：共用源224请求，按同模型69样本均价约$0.62497；不跨病例复用256请求约$0.71425。全新三票336源请求约$0.93745（独立每例384约$1.0714）。现有3a上下文2163请求Key约$1.04357，辅助56（章选择10/同义合并10/支持核查36）用合并源均价代理约$0.15624；全冷启动按旧行动集合基准2555请求/$2.13726，新增并集、补抽、引文修复、核查和重试另计，不保证完成。可按约$2.14基准、$3.00停止上限方案供将来审核，但不是申请/启用新额度。所有15例方案都超过当前余额预算，绝不执行。复用历史首票的224次不能声称本窗口新生成三票。完整盘点/估价runs/step3a-vote-quote-complete-20261118，均只15练习/复测，不涉及评测Step3+。

用户问“等我确认啥”已明确解释：审计/报价不等确认，继续完成；仅正式key切换依据用户“我确认后再切换”暂不执行，真实三票也未批准。当前应交付新提案和费用，不重复要求用户批准审计，不自动迁移或调用模型。

**2026-11-18 用户批准正式Key切换（不是医学Accepted升级），已完成15例$0验收**：按已批准319映射先查双向单射、所有行动等价类无新增合并/拆分、整对象可逆及证据完整一致，全部通过后切换252条正式3a行动记录。65 RxCUI/203锚点偏移/49 name_dependent/2旧key的方案不再优化。data/action_key_registry.json已启用，含全部旧→新别名、显式name_dependent及归一化未确认标记；完整备份/改前改后SHA/审批原表SHA和回滚所需注册表在runs/formal-key-switch-20261118。Evidence数组（含历史action.key出处）与Evidence ID生成方式不改；只转换机器身份字段。临床运行内存保持旧身份、Ledger.to_dict出口映射，报告前缀识药查可逆别名，避免药物类别锚点化后漏药；未注册新候选不强配已审批身份。

15/15回归：逆映射后与改前备份整对象严格相等，行动/分类/状态/条件/缺失信息/证据全不变；药物安全清单相同，隔离报告Markdown逐字相同、trace仅Key变。未写任何正式Step4报告。15例临时副本原始字节回滚验证及真实rollback逻辑单测通过；rollback命令支持部分应用恢复，拒绝覆盖未知后续修改，关闭向新key导出仍可解读归档新key。1282全量离线测试通过（12.86秒）。历史/current全部基线SHA不变，无Accepted升级；自改前规范化diff0。canonical对current既存差异仍为新增18、细节4、删除4、状态2、RETEST缺基线157，逐项断言本次没有新增/抹平。所有diff在out/status_diff/formal-key-switch-20261118。回滚：.venv/bin/python scripts/experiments/switch_action_keys.py rollback --out runs/formal-key-switch-20261118（当前未实际回滚）。

DBS专项：GPi-DBS与subthalamic nucleus DBS仍为supportive/conditional，reason均source describes use; no explicit recommendation；EIDs f79048a6b89a、435f3d2889a1不变，无本轮行动遗漏/条件变化。泛称孕期DBS不重建独立行动。本轮模型/公共联网0、费用$0，剩余$0.283927157不动。说明docs/experiments/formal_key_switch_and_kmt_quote_20261118.md，汇总out/acceptance/formal_key_switch_20261118.json。

**KMT2B下一轮仅报价，尚不授权真实调用**：固定当前4个源输入，复用既有真实首票，新增2票=8个首发（每源2次），temperature0、3a-v5及原参数16384/截断一次32768重试不变。按完全相同输入的2轮实测而非15例混合均价：8份完成响应$0.043733016，历史2次截断重试$0.020082222，剔除无需新调用的章选择后合计$0.063815238，约$0.064；拟本次硬上限$0.08，从旧剩余额度内扣、不新开总预算。历史参考约10物理请求含重试，8首发数固定、输出/重试/实付不保证固定。每请求最大预留，usage缺失/传输实付未知按预留，额度不足停且保留已完成；批准后仅非高峰、先查余额、强制两票独立真实请求不复用响应缓存，不执行3b–3e。

该$0.08只申请新增源抽取与必要重试；其他归一化/引文修复/同义合并/支持/上下文核查只用固定缓存，缺缓存待核查，不自动追加付费。先完成全部计划源抽取并保存原始输出，再缓存组装，避免归一化缺口阻断剩余抽取导致白花费。已$0按当前规则重组首票：26记录（比正式21多5项是上轮kind修复恢复的候选，不算新模型不稳定），缺上下文30及同义合并1，整体incomplete；两DBS确定性conditional、key和EIDs与正式一致。后续三票用同规则比较，合法目的/孕期过滤不当错误；缺核查不称分类错误，Evidence ID差异分解claim/原句/类型来源。只观察三票，不自动上线医学多数决规则、挑结果或更新Accepted。精确报价/冻结首票及代码数据哈希runs/kmt2b-call-approval-20261118；脚本scripts/experiments/quote_kmt2b_two_votes.py。全部15例三票继续不运行。需在Key验收完成后单独申请此限定$0.08调用批准，用户未答复前不得运行。


**2026-11-19 最新授权已执行完毕：只完成KMT2B一票新增抽取，已停止等审阅**。用户先批准限定抽取$0.08，随后明确“一票跑完汇报等批准”，后者覆盖此前新增两票计划。实际只跑4份固定来源各1次，4次独立真实请求、响应缓存复用0、重试0，05:10:12–05:13:28 PST非高峰，模型deepseek-flash、3a-v5/temperature0/原参数不变；执行前余额可用18.00CNY。usage全部完整，费用$0.022005876；旧$0.50实验累计$0.238078719，当前剩余$0.261921281（runs/step3_remaining_budget.json）。$0.08子上限未用完也不授权下一票；付费进程已结束，第二票未执行，必须等用户新的明确批准。余额接口前后同为18.00CNY，不能由此称费用0。

已有首票同规则26项，本票23项（不含占位），21项可直接Key/字面名称对齐：11项条件记录不同、10项Evidence ID集合不同；DBS两项Key/条件/ID完全相同，既有判定基础仍conditional、source describes use; no explicit recommendation。walkers/ankle-foot orthoses改为adaptive aids是上游具体度损失；504/DDA未抽出；IEP缩写属措辞；influenza immunizations从drug变procedure导致后续药物识别变化，单列审阅，不自动修规则。3/4原始来源JSON不同。8项暂存状态差异全部缺新核查，不能算确认临床状态变化。新增待核查75次上下文+1次同义合并均未调用，整例3a仍incomplete；只有历史首票加本票两份观察，不作三票多数或稳定性通过结论。

已保存原始输入/输出、真实sample=1 Call IDs、完整Diff和费用；缓存回放只修Call ID追踪元数据，不改医学逻辑/Prompt/模型输入。1286项离线测试通过，正式15例账本和所有历史/current基线SHA不变，不跑3b–3e、不改Accepted、不写正式报告。报告docs/experiments/kmt2b_one_new_vote_20261119.md；执行runs/kmt2b-new-vote1-20261119；汇总out/acceptance/kmt2b_one_vote_20261119.json；完整status_diff在out/status_diff/kmt2b-one-vote-20261119/{first-vs-new,accepted-current}/。所有旧“两票待批准”及$0.283927157余额记录均属历史，由本条覆盖。

**2026-11-19 KMT2B第三票按新授权完成，仅shadow**：先$0审计11项条件（3项仅措辞，8项涉及新增/遗漏/范围，原文保存），后按新增$0.03且累计$0.08授权非高峰完成4次真实抽取，无重试、无缓存复用，$0.020626476；两次新增票合计$0.042632352。旧$0.50实验累计$0.258705195，剩余$0.241294805，最新指针runs/step3_remaining_budget.json。模型/Prompt/来源/医学规则固定。第三票25实际行动，81上下文+1合并缺缓存，均未调用，incomplete。

GPi/subthalamic三票均抽到；GPi第三票首字母大小写改变claim/EID及核查键，旧R15未命中，暂存applicable不能当真实升级，最终not_tested；shadow保留旧describes_use条件。504及walkers/orthoses票1/3有、票2无，DDA只票1有，全部保留待审。原始41字面名称（含附注/缩写），23三票/12两票/6单票；86条件变体中54单票，全部保留。文字共识不自动生效，不删少数条件；总称/具体项不合并，无多数kind不强裁。influenza类型drug/procedure/drug分歧保留。正式15账本、历史/current全部SHA不变，1287离线测试通过，无AGXT或3b–3e、无Accepted更新。说明docs/experiments/kmt2b_three_vote_shadow_20261119.md和docs/experiments/kmt2b_two_vote_condition_audit_20261119.md；三票/联合对Accepted及两两diff在runs/kmt2b-third-vote-20261119/shadow/status_diff（vote4为联合视图，并非第四票）。临时比较副本逆转已批准别名消除Key噪音，不改正式Key或基线。不自动续跑。

**2026-11-19 条件稳定性修复仅$0部分完成，真实新版Prompt待批准**：核查cache_key只规范化Questions中的action claim大小写/空白，实际原文、患者/来源和Evidence ID公式不变；有等价实际命中/错误碰撞测试。3a-v6 Prompt禁止LLM推断章节/跨段条件，原句/表行明确条件才抽；现有population_requirements继续处理小标题人群。风险理由/预防目标不代表现患，阅读规则v1.3。未真实调用，不称新版Prompt已验证；不把旧三票冒充新版本输出。

旧KMT2B三票离线shadow原始86变体/54单票保留；保守归一后66条件/26单票，12表达冗余、8等价年龄表示折叠，42个跨票存在性分歧候选，35个潜在安全/资格关键分歧needs_review、阻止无条件适用。全部原文、字段、已有ID与少数票条件保留；17组历史从未分配ID（附注/被过滤/未匹配），明确标未分配并保留调用选择键，不造ID。非医生确认的42错误或35安全问题。正式15账本和全部baseline SHA不变，无AGXT、无81次核查、模型/新联网0、费用$0，无医学结论变更。重算scripts/experiments/kmt2b_condition_recount.py，产物runs/kmt2b-condition-recount-20261119，含current_semantic_diff/current-vs-accepted/shadow-vs-current及三票完整diff。详情docs/experiments/kmt2b_condition_recount_20261119.md。

新版KMT2B仅源抽取单票报价：固定4来源、4首发，重试另计，历史同源两票均价$0.021316176，新Prompt未实测，预计约$0.022、建议新增硬上限$0.03，若沿用KMT2B累计$0.08也足够。仅报价未授权；现余额$0.241294805不动。需明确批准才非高峰先查余额执行；无3b–3e/新核查/AGXT，不自动续跑。

本轮全量离线1293项通过；最终35关键待审组含3个多数票一致但原文是风险理由的条件，非只筛少数票。

**2026-11-19 用户批准3a-v6单票$0.03；已执行但未完成，预算保护停止，不续费**。非高峰先核实余额17.71CNY可用，四份user来源逐字不变，只换v6系统Prompt。Management完成0条$0.000088302；Treatment of Manifestations在16384截断（usage输出全部16384 reasoning），$0.010076004，未得到可用完整抽取。32768必要重试预留$0.0215752大于本次剩余$0.019835694，请求前阻止，没有发送。2真实请求、0实际重试、usage完整、peak0，合计$0.010164306；sources_completed=1/4，后两源未运行。KMT2B累计$0.052796658<$0.08，旧$0.50实验累计$0.268869501、剩余$0.231130499，最新runs/step3_remaining_budget.json。上级余额不授权突破本次帽。

42组分歧、3组风险误抽、DBS/504/DDA/器具均not_tested，不把没有响应当遗漏或修复，也不能说解决0项。仅空Management一致不足以验证新Prompt效果；不称初步/稳定性通过。没有核查/合并/其他Step/AGXT，无医学规则、正式Ledger、Accepted改动，15正式及所有baseline SHA不变，since-before diff0；对Accepted既有diff保留。报告docs/experiments/kmt2b_v6_initial_attempt_20261119.md；实验runs/kmt2b-v6-one-vote-20261119含全部输入/usage/停止及42+3逐项unknown。已停止付费，等待后续安排，不自行增额度或改参数。

**2026-11-19 KMT2B截断诊断/精简分块及新授权$0.06单票已完成，付费已停**：v6原截断reason/content=16384/0；v5两次截断15237/1147（核心正文7115字符）、15931/453（DD/ID3677），成功重试13472/2045及13886/805，不全是核心段。3a-v6.1只精简v6新增规则（执行前展示），结构原子行分块3500上限，4源1/3/2/1共7块，覆盖全文无重叠/丢失、超大单元报错，不再[:9000]裁切；每块真实出处再进原有行动合并。1297全量离线通过。

最新单次$0.06（新阶段，旧费保留）授权非高峰先查余额17.64CNY，以nohup+caffeinate完成7/7真实请求，响应复用0、截断0、重试0、usage完整，$0.030894018。KMT2B系列累计$0.083690676，原$0.50母实验累计$0.299763519、余$0.200236481；本次未用部分不自动续跑。单块DD/ID输出仍16107/16384，单次无截断不是稳定性保证。

两DBS/DDA/IEP在；504计划独立项缺失（只抽assistive devices）、walkers/ankle-foot orthoses仍概括为adaptive aids。28原始/28规范化条件，对照旧单票38/50/45、并集86，不以减少作正确性证明。感染风险误抽胸部PT/流感免疫2项改善，抗生素仍把pulmonary infections当manifestation。anticholinergic同句确诊限制漏抽，PT/OT/speech局部IEP范围漏抽待审；IEP明确资格、feeding安全口服、冬季/呼吸受限等保留；章节范围返回既有代码，本次未组装不能称已补齐。孕期antiemetic警示未抽、affected mother被当性别条件均待审，只作附注，不自动医学结论。旧42逐项审阅保留全部原文/EID及新Call ID，不按多数定正确。

只完成源抽取与离线审阅，未补81核查或同义模型，不跑其他Step/AGXT；15正式及所有baseline SHA不变、since-before diff0，Accepted未更新。报告docs/experiments/kmt2b_chunked_v6_result_20261119.md，诊断docs/experiments/kmt2b_chunking_diagnosis_20261119.md，实验runs/kmt2b-v6-chunked-20261119含7响应/块映射/费用/old42/status_diff，最新余额runs/step3_remaining_budget.json。付费已退出，不再自动执行；不称完整3a或稳定性通过。

**2026-11-19 分阶段v6.1：$0 examples完成，新增第二票运行异常已停，第三票不执行**。用户确认仅运行异常阻断第三票，单票医学缺口在完整三票后评估。停止契约docs/step3a_v6_1_stop_criteria.md v1.0：三票完整无截断；Accepted行动并集覆盖或逐条解释；多数生效条件无风险理由当现患；AGXT另须高饮水/IV fluids。未达标记known_limitations，不自动改Prompt/Accepted；两例达标才冻结工程版本，非医学审核。

examples-v1只对同原句明确X(e.g.A,B)/X such as A,B归并父项，examples保留成员原始名称/条件，不是化学同义词、不改RxCUI；不把成员资格当整个X资格。缺parent类型/范围时未知并待审，报告引用原句。适用adaptive aids/orthoses/walkers，也适用other agents下举例药物（levodopa独立），保留全部出处。生产已接入，正式Ledger不刷新。1303离线全过，覆盖结构、条件保留、报告原句、运行门禁。Prompt字节不改，仍3a-v6.1；旧第一票在shadow统一用相同后处理。

获批新增票2/3各独立$0.035，复用原7/7块第一票。本次非高峰余额核实后nohup+caffeinate，仅源抽取。两张新票计划请求顺序一致，将历史最大输出DD/ID第一块(0–3191)排最后，输入消息与第一票集合逐字相同，避免预留浪费，不改正文。票2六块完成，最后块16384全reasoning、内容0，截断；已花$0.031091418，余$0.003908582，32768重试预留$0.0209635不足，未发送。7真实请求、0实际重试、usage完整、peak0；无源输入缺失，缺完整raw块是截断所致，非FDA/RxNav缓存缺口。门禁已停父进程exit1，票3未started、无paid journal，conditional授权条件未满足，不可自动重试。母$0.50累计$0.330854937、余$0.169145063，未转用未执行票额度。

完整三票/无截断标准不满足；其他三票医学标准未计分，部分可用回答仅作待审观察。两份核心响应仍有抗生素感染风险误抽，不因第三票缺失删除。Accepted部分投影17直接+7examples解释，1历史trihexyphenidyl与源trixhexyphenidyl拼写待审；不是最终三票覆盖结论。未执行/报价AGXT，未冻结、不自动改提示词。15正式及全部baseline SHA未改，since-before diff0，current-vs-Accepted既存差异保留，无新医学结论。报告docs/experiments/kmt2b_phase1_examples_review_20261119.md，限制及提交说明素材docs/known_limitations.md；实验runs/kmt2b-v6_1-phase1-20261119含plan/各票完整输入/预算/截断/partial shadow/25行Accepted覆盖/完整status_diff。付费已停止，等用户后续安排。

**2026-11-19 KMT2B low单块诊断已完成但行动门槛失败，按用户条件停止，未切默认/未续跑**：仅DD/ID第一块3191字符、同3a-v6.1 Prompt/来源/模型/temperature0，一次真实reasoning_effort=low请求，无重试、无缓存复用、非高峰，先查余额17.23CNY。原16384请求预留超过$0.01，执行前披露本诊断上限14000；实际7401总输出=6832 reasoning+569内容，finish_reason stop，$0.004644600，usage完整。不得把14000参数差异或一次完成当成low稳定性证明。

诊断前固定8个源内命名行动门槛；低档返回7条，预定8项仅6项在，IEP独立行动及其资格条件缺失（同Prompt原档第一票曾明确返回）；504 plan也未返回，只抽assistive devices。PT/OT/speech学业访问限定恢复，但不抵销IEP遗漏；另v5票2中的home-based services未抽。逐项对照覆盖v6.1完整第一票和两份v5完整参考，限定相同输入范围，DDA在另一块不算遗漏。IEP仅出现在PT等引文中不算行动召回，门禁已补反例测试。1305离线全过。

未触发“完成且无明显遗漏”的后续授权：不改3a默认档位、不改重试策略、不补第二票、不跑第三票、不用后续$0.05（支出0）；诊断单独保存未补入票2，混档完整票0。第二票仍6/7原档，第三票未执行。母$0.50累计$0.335499537、余$0.164500463；本次$0.01未用部分不自动续用。15正式及全部baseline SHA不变、since-before diff0，Accepted不改，Prompt不改，无AGXT或工程冻结。

用户要求“DD/ID块持续推理失控（3/3次）”已记known_limitations；注明三份记录reasoning/总输出为15931/16384（v5整节截断）、15549/16107（v6.1首块完成近限）、16384/16384（第二票同块截断），不是三次完全同输入或三次全截断。报告docs/experiments/kmt2b_low_diagnostic_20261119.md，实验runs/kmt2b-low-diagnostic-20261119含预定门槛、完整输入/参数/API响应/usage、逐项原文条件比较、failed gate及完整status_diff；compare_kmt2b_low.py离线可复算。付费已停止，不追加模型或自动调提示词。

**2026-11-19 GeneReviews Management结构观察（$0，未做优化）已完成**：按用户最新全范围，15例现有练习/复测（官方11例排除延期DMD+4复测）及12例盲测，从407份当前/历史账本及会话输出的实际NBK证据/已选章节收集，去重19章，均使用本地genereviews_book/2026-11-03 XML。10例现存产物未记录实际使用NBK，不推断该基因无章节，未把SFTPC等目录候选强行纳入。只分析正文Management树，排除abstract摘要同名小节。

交付docs/structure_maps/：19章Markdown、index、KMT2B/AGXT/Hereditary Ataxia对比、unrecognized、带数据快照/源SHA/全部位置及来源链的manifest。逐小节列字数与形式，完整表头各级/行标签/单元格全文、粗体标签与段落、全部列表项及嵌套级；保留XPath/XML id/稳定锚点。按用户此前要求，三章HPO名称/同义词匹配仅作审阅附注，否→疑似不代表已确认治疗。指定Pregnancy/Evaluations/Surveillance/Relatives/Under Investigation标题及子节单独标记，未用于抽取或路由。

统计：166层级标题、51表468数据行、250列表701项（表外61列表221项，表内480项单列）、377自由正文段/16980 words、32套话命中单元（22段+10列表项，42签名命中，不重复计自由正文）。全部Management正文40190 words。总体模式：汇总表+标签9、汇总表+正文/列表5、粗体标签段落无表3、列表+正文无表/标签2、无结构正文0；排除指定非治疗标题后的纯结构视图为6/6/5/2/0，防止把评估/监测表当治疗汇总（KMT2B此视图为粗体标签+段落）。不是优化建议或临床分类。

XML解析失败0；记录4条呈现结构限制，涉及3表多级表头，其中AGXT Lumasiran Table8还嵌在list-item/p内，当前视图可能平铺。表内列表在行文本中不带原层级，地图另列原始项及位置。只观察未修生产解析器。6项必要解析测试通过，19章节/行/列表计数与唯一锚点/源SHA核对通过；生成时显式阻断LLM和网络入口仍完成，模型请求0/网络0/费用$0。aitx/config/data/流水线代码、15正式Ledger及全部baseline SHA均未改。未调默认、未生成治疗路由、未冻结/升级Accepted。遵守本轮不联网要求，仅本地提交，不push。

**2026-11-19 用户追加要求先做$0代码清理，3a结构改造暂停**：21个一次性脚本移至 `scripts/experiments/`、33份报告/实验计划移至 `docs/experiments/`；入口根定位、导入、活动链接与旧冻结路径映射同步维护，不改写runs/baselines/.cache。索引 `scripts/README.md`、`docs/README.md`；完整验收 `docs/cleanup_review.md`。生产 `aitx/` 不修改，只提供AST扫描663函数/方法的5项无引用候选，见 `docs/code_usage_review.md`，待用户批准才删；旧key计算/可逆导出与3a旧抽取仍在使用，保留。本地模型专用对照在实验脚本，无独立生产适配器可删。全量1312离线通过，7迁移CLI --help通过；生产指纹未变，无新增过期，不刷新已有过期或伪改_meta；清理前后详细status_diff0，对current641项既有原始差异逐条不变，不称对Accepted绝对diff0。模型/网络0，费用$0，不跑评测Step3。3a阶段1未验收代码独立保存在out/paused-3a-structure，不纳入本轮；本轮不继续3a或删除生产代码。

清理验收补充：全量测试暴露既有socket超时测试会把example.org假URL写进真实HTTP缓存（单文件时间戳变化）。已改测试使用tmp_path缓存，并按清理前SHA恢复该测试夹具原字节；最终全目录核对。没有生产代码或临床来源数据改动，不声称测试期间从未临时写入.cache。

**2026-11-19 用户批准删除5项，删除完成但缓存刷新遇缺口停止，等清理验收**：仅删除llm_samples、ClinVarRecord.is_plp、pathway_members、depends_on_unreported、trial_primary_outcomes及审批清单注明的UNREPORTED常量；其余生产AST严格相同，旧Key兼容与3a旧抽取不动。全量1312/1312离线通过，静态663→658且零无引用候选。生产指纹324958…→8ca1f79839da91697125c413ed78d4986778f323997daa9f091338d60cee7b53。15例先AGXT-c33dup，在隔离目录完成缓存Step1/2后，Step3章节选择缺3a-v6.1键532f55399f97221791e10025c4cb4f9d62f9721f4db1e7c2a7be2d8d1d34582f，按“缺缓存就停”全局停止，后续14例未启动，不补缓存、不付费。Step1内容0diff；隔离Step2补既有HGNC缓存location=2q37.3一项，未发布。删前cache-key函数对相同输入重算键一致，不改Prompt或降版本。正式输出不覆盖、不伪改_meta，因此正式前后status_diff0、对current641项既有diff逐条不变；不能称整例刷新验收通过。完整diff/日志/输入在out/cleanup-delete-20261119，报告docs/cleanup_delete_review.md。runs/baselines/.cache与100正式输出SHA无变化，缓存命中6、真实模型/外网0、费用$0，不升级基线、不跑评测Step3；先交用户验收清理结果，不继续3a阶段1。DMD延期保留。

**2026-11-19 清理获用户验收；生产提示词恢复v5，缓存刷新再次缺口停止**：按用户要求恢复established.PROMPT_VERSION=3a-v5，并恢复与step3a.1-accepted逐字一致的EXTRACT_SYSTEM及原每小节9000字符输入窗口；仅改版本号会错标v6.1输入，故同步恢复实际调用。v6.1提示词/3500无损分块移至scripts/experiments/step3a_v6_1.py，实验显式传版本。docs/step3a_accepted_prompt.json记录已验收版本/SHA，新增版本/正文hash/输入窗口/实验独立版本测试，旧分块测试改测实验模块。全量1315/1315通过（12.09秒）。

本次仅$0缓存刷新15例，排除DMD和评测，首AGXT-c33dup隔离Step1/2完成，Step3药名归一化缺FDA品牌名PYROPHOSPHATE-CONTAINING SOLUTIONS查询HTTP缓存159ce52a870af8cd93adf9adaa047be683bc41e7bb09f045126e69fe2518b7e6；不是LLM缺口，不把缺口当FDA阴性。按“缺缓存就停”停止，后续14例未启动，完整刷新0/15，正式输出未覆盖、不伪改_meta。真实模型/外网0，费用$0；不补缓存或改名。用户仅授权刷新完成后按mapping.tsv逐对证明状态/条件/证据相同的Key删除/新增成对promote；因前提未满足，本次未升级current、未写approvals、未做配对验收，也未开始3a阶段1。正式前后diff0，对current既有641项（248新增/234删除/2细节/RETEST缺基线157）完整保留，不称升级后残差。产物out/restore-v5-20261119，报告docs/experiments/restore_v5_20261119.md。后续先解决/裁决缓存缺口，不自动联网或恢复旧付费授权。

**2026-11-19 刷新边界获用户调整并已尝试，现因LLM缓存缺口停止**：允许仅RxNav/openFDA/ClinicalTrials.gov/PubMed E-utilities/Open Targets/ChEMBL在正式HTTP缓存缺失时联网补入；既有缓存不刷新不覆盖，每次URL/时间/缺失原因留痕。DeepSeek仍严格禁止，缺LLM缓存即停。新增scripts/public_cache_fill.py实施限定端点、missing-only、独占创建、逐次日志；aitx.http.cached_response识别新存储的显式HTTP错误并重放原错误语义，避免404丢失/被当成功响应。全量1320/1320离线通过（11.96秒）。

继续首AGXT缓存刷新，本次24次真实免费请求均openFDA且均404，响应正文/状态正式缓存新落盘24份，旧缓存逐字不变。随后非药物同义行动分组缺3a-v5 sample0缓存bc78363eaa472f4a7552d904f991ae34692d3149cf21d56e1a79c547cb45dd68，立即停止，DeepSeek0次/$0，完整刷新0/15，后续14例未启动，正式输出未覆盖，未promote/未写approvals，未开始3a阶段1。FDA PYROPHOSPHATE查询在11/18固定HTTP夹具已记录404；原HTTP层没有缓存HTTPError，故正式cache缺失。actions.py与ecc436d相同，属于原RxNav→FDA归一化链路，不是Key迁移新增请求。原因仅简述，证据及请求明细out/public-fill-refresh-20261119，报告docs/experiments/public_fill_refresh_20261119.md。正式前后diff0，对current641项既有差异不变（248增/234删/2细节/157缺基线）；不能称升级后剩余项。LLM缺口不绕过，不恢复旧付费授权。评测Step3和DMD均未运行。

**2026-11-19 用户停止缓存刷新，改为离线Key升级与3a阶段1；已完成工程产物，候选待用户审核**：保留24份openFDA 404缓存，不再运行完整刷新。用户明确授权按mapping.tsv直接转换current旧key（不依赖重跑）；scripts/experiments/migrate_current_keys_offline.py核对TSV与registry，使用promote升级230个行动×分支行的action_id，599行总数不变，全部非身份字段逐行完全相同；类别“仅 key 迁移（离线映射）”及460个成对增删diff记录进approvals。历史基线只读。当前正式账本对新current剩185项：RETEST缺基线157、COL1A1 EDS暂缓18、KMT2B四药reason4/孕期独立项删除4/两DBS来源措辞降级2；未随Key迁移升级任何医学差异。完整旧/新快照、批准和diff在out/offline-keys-structure-20261119/key-migration-applied及after-key-migration。

3a阶段1新structure模块和genereviews.management_structure显式接口实现确定性单位、标题路由、HPO标签/行上下文、举例父项、DD/ID原句模板年龄、孕期仅同名附注、表内列表树及多级表头；旧生产v5路径保留，不改正式Ledger。15例范围中11例有实际章节，去重12章344候选；另用原19章验证51表、480/480表内列表项、3多级表头保留。Accepted直接GR引用264身份/274分支行：173名称命中、42仅段落单元、17仅同行其他列、32未找到；后三类不当作已确认独立召回。192个新增/未对齐单位逐项列原句和理由，不称192个新增治疗；未找到项均给路由/XPath/原句。AGXT50项、KMT2B42项清单交用户审阅，gold仍pending_user_review，不进阶段2；KMT2B subthalamic DBS仅在GPi段落单元，未自动独立命名，walkers/orthoses保留adaptive aids示例。契约docs/step3a_structure_phase1_contract.md；报告docs/experiments/offline_keys_structure_20261119.md；全量1334/1334（12.14秒），真实模型/联网0、费用$0，正式100输出/runs/历史基线不改，仅current和批准记录按授权变更。阶段1对新current完整diff保留上述185项，自阶段1改前正式diff0。评测Step3不运行、DMD延期。完整刷新推迟到全部3a改造完成后；届时先“收集全部缺口不停止”的15例干跑，再一次性报价，不在本阶段执行或恢复任何旧付费额度。

**2026-11-19 阶段1审核修订与正文补充完成，待验收**：表头语义、avoid路由、短前导语分类、药物例子拆分已修，HPO匹配不变；治疗小节所有表外段落按句扫描，包括粗体及接续段。RxNorm本地表与186项可审词表提供名称候选，交叉引用表现列保留条件来源，未命中句needs，固定定义non_action。指定NF1/CFTR/OI药物及AGXT两种透析均覆盖，透析标签保留Prevent systemic oxalosis。neridronate免费RxNav缺失查询1次、无匹配，按用户指定补词，不伪造RxCUI，旧缓存不刷新、24份FDA404保留。原32项21名称命中、5仅原句定位、6未找到，11未独立覆盖逐项列出。AGXT/KMT2B分组及15例needs统计见out/structure-review2-20261119；剩余整段0不等于未知句0。全量1345通过，正式输出/runs/历史baseline不变，对改前diff0，对current185既有项逐条不变，未promote。阶段2只设计报价：KMT2B 58单位去重57题×3=171次，历史代理估计$0.755，保守建议单次上限$1.81，未执行、不沿用旧额度。模型0/$0，不跑评测Step3或DMD，完整刷新及全部付费缺口干跑继续延期。完整验收docs/experiments/structure_review2_20261119.md；设计docs/step3a_structure_phase2_design.md。

**2026-11-19 阶段1去重/路由修订及阶段2指认扩大验证收尾，AGXT待审**：Management默认治疗，仅指定检查/监测/亲属/孕期/研究/遗传咨询等排除；avoid独立，Prevention/Acute分类，人群标题沿用原规则，RRM2B按Step2表型保留other_phenotype；无效句负面证据交核查，父类和具体方案均保留。同节同身份合并多句证据，程序模板/列表PT等同名身份统一，条件不强制全局AND。AGXT每例50 action，KMT2B24；PFN1根Management of ALS原已定位，旧标题白名单排除了根及Symptom Management，反转后22 action/23 needs。19章166路径management_routes_actual.tsv、15例计数与来源核实见out/structure-review3-20261119。SFTPC Step2有关联NBK1230多基因章节，现有3a未用；外部治疗引文实际为3c PMID33179299，不把未选中说成无章节，不改账本。

旧阶段2单位/批量复制引文方案停止。新段落指认32题/58句，代码S/T编号、模型短JSON标签，新词由代码忽略大小写空白匹配后复制原写法。默认候选non-thinking/1024；context_check仍low/16384且文件SHA未变。按用户扩大验证上限0.05非高峰运行，续跑取消剩余low，保留8份low参考；KMT2B non-thinking三票96答复，86有效、10格式/引用失败、截断0；50/58句有三完整有效票，49/50角色/关联一致98%。action无T且无_new仅needs_review，不算格式错；多数待审2句，逐样本7次/3源句。旧失败_new“pharmacologic treatment”跳过原句and surgical，按新规则仍错，离线重校验未重发。其余9错为_new误放T槽位。三票多数_new trihexiphenidyl、benzodiazepines仅本题未列T原词，不称新药；31合并名称/4条件候选，Accepted25名对齐18，IEP/504/DDA/DBS名保留，抗胆碱药confirmed diagnosis仅随action原句保留，未成显式条件，该must未通过；IEP至21岁关联transition plan另待审。

已知费用0.00646368美元含两份复用单段实测；两次无usage保留0.002468预留，预算上界0.00893168<0.05，不称精确实付。旧2048单位失败0.00188145另计。所有答复/费用在out shadow，100正式输出/runs/历史baseline不改，对本轮改前diff0，对current185既有项完全相同，未promote。1362全量离线通过；未读取四评测病例章节结构，不跑评测Step3，DMD延期。AGXT必须用户审阅后才启动；不报15例全量价格，不自动扩大。完整报告docs/experiments/structure_identify_validation_20261119.md；阶段1docs/experiments/structure_review3_20261119.md；当前设计docs/step3a_structure_phase2_design.md。完整刷新与全部LLM缺口干跑继续延期。


**2026-11-19 用户审阅 KMT2B 后的五段修复及 AGXT 三票已完成**：新的合计硬上限 $0.03、仅非高峰；只重跑 KMT2B 原题 2/11/15/16/28，其余 27 段复用。T0 治疗标签、每句多角色、condition 必须有所属 T；AAC 按源文 e.g. 父类登记别名（旧版实际未输出父类，未伪称旧覆盖），孕期四项和 AFO/walkers 按设计排除。新 KMT2B 15/15 有效、零截断，五项修复通过；新 8 句 6/8 全票一致，含复用共 51/54（54/58 句有完整三票），95/96 主答有效，旧题 0 一份格式错及两句 pediatrician needs_review 保留。confirmed diagnosis 关联抗胆碱药，age21 关联 IEP services 且不关联 transition plan。

AGXT 完成 60 段/121 句/180 答复，178 有效、2 份 condition 无 T 格式错、零截断；120 句完整三票中 98 句一致。指定名称和原句覆盖，但共用 T 列表使总述句 missense 限定同时关联 RNA/移植等候选，7 句多目标条件关联待审，不能判整体通过。源文 nedosiran 是 eGFR >30，不改成用户简写 ≥30，边界差异单列；Accepted 23 名 22 匹配，Pharmacologic agents that can compromise kidney function 父类未独立命名。未扩大/报价 15 例；后续可考虑各角色独立列 T，本轮未改冻结提示词或追加验证。

195 次有 usage、已知 $0.010441770；另一次 curl35/TLS 失败无 usage 保留 $0.001225600，预算上界 $0.011667370 < $0.03，不称精确实付。用户续跑后仅补未返回的一票与后续 40 票，原失败记录保留，已返回格式失败不重发。高峰请求 0，reasoning tokens 0。上下文核查仍 low/16384 且 SHA 未变。全离线 1369 通过，100 正式输出/runs/正式缓存/历史基线未改，current 等于离线 key 迁移快照，前后 diff0、对 current185项逐条未变，未promote。未读四评测章节结构或跑 Step3，DMD延期。报告 docs/experiments/structure_identify_v2_20261119.md，完整产物 out/structure-identify-v2-20261119。

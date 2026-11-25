# 离线Key升级与3a阶段1结果

2026-11-19。已停止完整缓存刷新，不重启旧运行；保留先前新增的24份openFDA 404缓存。本轮模型0、联网0、费用$0，未跑评测病例Step3。

## 仅Key迁移（离线映射）

按用户本次明确授权，读取 `runs/action-anchor-supplement-final-20261118/mapping.tsv`，确认与现行导出registry一致；直接转换current的旧身份，不依赖重跑，不从正式账本吸收状态/证据。230个行动×分支行仅更换`action_id`，599行总数不变。每行其余字段完整相等；历史本来缺失的详细条件仍保持缺失，未伪称补齐。

通过 `promote_baseline.py` 升级并追加 [approvals.md](../../baselines/approvals.md)，类别为 **“仅 key 迁移（离线映射）”**。230对旧身份删除/新身份新增写入同一批准记录；基线原文、状态、原因、证据、分类等其他已有内容不变。历史基线只读未改。

- [旧基线快照](../../out/offline-keys-structure-20261119/key-migration-applied/before.json)
- [迁移候选及实际新current](../../out/offline-keys-structure-20261119/key-migration-applied/candidate.json)
- [逐行映射](../../out/offline-keys-structure-20261119/key-migration-applied/mapped-rows.json)、[本次批准凭据](../../out/offline-keys-structure-20261119/key-migration-applied/approval.json)
- [Key转换自身的完整diff](../../out/offline-keys-structure-20261119/key-migration-applied/diff.md)
- [转换前正式账本对current完整diff](../../out/offline-keys-structure-20261119/before/diff.md)

转换后，Key造成的成对增删噪音消失。正式账本对新current剩 **185项**（行动×分支行）：

| 类别 | 数量 |
|---|---:|
| RETEST缺Accepted基线 | 157 |
| COL1A1 EDS试验暂缓 | 18 |
| KMT2B四药reason文字差异 | 4 |
| KMT2B孕期独立行动删除 | 4 |
| KMT2B两DBS来源措辞降级 | 2 |

以上均未随Key转换升级。后10项是已记录的KMT2B历史差异：四个孕期独立项；GPi/subthalamic两DBS的applicable→conditional；四药投票分歧reason文字。[逐项分类](../../out/offline-keys-structure-20261119/remaining-categories.md)、[完整JSON](../../out/offline-keys-structure-20261119/remaining-categories.json)。

从641项移除230对Key增删后，并非简单剩181项：另有4项原先被不同Key掩盖的既有reason/status差异现在可直接比较，故最终为185项。基线非Key字段未变，没有产生新的临床判定。

## 3a阶段1已产出，等待清单审阅

新 [结构接口/契约](../step3a_structure_phase1_contract.md)并行保留旧v5路径。确定性枚举治疗列/表外列表/粗体标签，HPO匹配标签作表现条件，DD/ID走固定模板并引用原句；孕期只作同名附注，评估/监测/亲属/研究中疗法不产生Tier1候选。没有改变正式临床判定。

- **480/480** 个表内列表项保留嵌套层级；19章 **51表**、**3个多级表头**通过源XPath与SHA核对。[完整结构核对](../../out/offline-keys-structure-20261119/phase1/structure-validation.json)。
- 15例范围中11例有记录的章节，去重12章，产生 **344个结构候选单位**。另4例保留原路径，不推断新适用性。
- Accepted有GeneReviews直接引用的3a行动 **264个身份 / 274个分支行**。按身份统计：**173名称命中，42仅原文单元，17仅同行其他列，32未找到**。后三类不能当作已确认独立行动召回；不称100%召回或医学验收通过。[逐行动覆盖](../../out/offline-keys-structure-20261119/phase1/action-coverage.md)、[完整逐分支覆盖](../../out/offline-keys-structure-20261119/phase1/coverage.md)。
- **32个未找到行动**均保留原句、XPath及路由说明；包括剩余治疗正文待兜底，以及孕期/评估/Management外来源被新路由排除的差异。[逐项缺口](../../out/offline-keys-structure-20261119/phase1/missing-actions.md)。不因此删除Accepted。
- **192个新增或未对齐的结构单位**逐项列出原句及理由，包含父项、未判同义、叙述性列表和缺基线章节，不能直接称192项新增治疗。[逐项清单](../../out/offline-keys-structure-20261119/phase1/additional-candidates.md)。

### 待用户审核的小样本

- [AGXT完整候选清单：50项](../../out/offline-keys-structure-20261119/phase1/NBK1283.md) / [结构JSON](../../out/offline-keys-structure-20261119/phase1/NBK1283.json)。高饮水与IV fluids位于表/表外列表单位；血液/腹膜透析等未被独立结构命名的正文缺口另列。
- [KMT2B完整候选清单：42项](../../out/offline-keys-structure-20261119/phase1/NBK493766.md) / [结构JSON](../../out/offline-keys-structure-20261119/phase1/NBK493766.json)。IEP/504/DDA模板项在；walkers/ankle-foot orthoses保留为adaptive aids示例。subthalamic DBS仅定位到GPi段落单元，未自动拆成独立行动；叙述性DBS结果列表仍作为待审结构候选，不据此认定推荐。

清单审核状态仍为pending_user_review，不自动把本次生成物标为已验收金标准。未进入阶段2或调用模型。

## 测试与完整status_diff

全量离线 **1334/1334通过，12.14秒**；[日志](../../out/offline-keys-structure-20261119/tests.log)。覆盖Key单字段转换、碰撞拒绝、表格跨度/列表树、排除路由、模板年龄与原句、孕期附注等。

- [Key升级后对current完整diff](../../out/offline-keys-structure-20261119/after-key-migration/diff.md) / [JSON](../../out/offline-keys-structure-20261119/after-key-migration/diff.json)
- [阶段1后对current完整diff](../../out/offline-keys-structure-20261119/phase1-current/diff.md) / [JSON](../../out/offline-keys-structure-20261119/phase1-current/diff.json)：上述185项完全相同。
- [阶段1相对改前：0变化](../../out/offline-keys-structure-20261119/phase1-since-before/diff.md) / [JSON](../../out/offline-keys-structure-20261119/phase1-since-before/diff.json)
- [保护文件核对](../../out/offline-keys-structure-20261119/verification.json)、[汇总](../../out/offline-keys-structure-20261119/summary.json)。正式100个输出未改，runs和历史基线未改，24份404缓存保留；只修改获授权的current与批准记录。

按用户最新安排，完整刷新推迟到3a改造全部完成；届时先收集15例全部LLM缺口、不停止，再一次性报价。本次不运行刷新、干跑或付费调用。

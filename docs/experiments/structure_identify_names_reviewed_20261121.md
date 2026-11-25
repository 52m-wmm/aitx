# Step 3a：15项已审核名称的限定来源处理（2026-11-21）

本轮$0，LLM及外部API调用0。仅更新来源名称对照，正式Action ID、Key、医学规则、Ledger和Accepted Baseline不改；不把名称匹配视为推荐或患者适用，不进入Phase 3。

## 逐项处理

| 审核项 | 名称/内容 | 本轮结果 |
|---|---|---|
| 1 | AGXT-c33dup：可能损害肾功能的药物类别 | 仅此来源关联any pharmacologic agent与原Accepted复数标签，保留完整avoid原句 |
| 2 | AGXT-c508GA：同一类别 | 同源名称关联，两个病例共用来源，不当两次独立模型确认 |
| 3 | ANO10 occupational therapy | 用同章OT定义关联OT/PT原句，原Care by语境保留 |
| 4 | ANO10 physical therapy | 同章PT定义关联，来源范围不跨章节套用 |
| 5 | CFTR nutrient-dense food and supplements | 原文&版本与and标签作此来源的名称对齐，不全局重写符号 |
| 6 | CFTR laxative treatment | 对齐laxatives原词，If not obstructed及不同来源条件各自保留，不判无条件适用 |
| 7 | CFTR assisted reproductive technologies (ART) | 同章全称/缩写对齐，男女/行范围、注释及原文保留 |
| 8 | COL1A1 dermal wound closure without tension | 关联闭合且无张力原句，不改原技术细节，不计算缝线参数 |
| 9 | GRIN2B anti-seizure medication | 用ASM表注定义关联；experienced neurologist不变为患者资格 |
| 10 | GRIN2B speech therapy | **暂缓**；提交共享therapy原文及相关提供者表述，不自动映射 |
| 11 | OTC chilled feeds | 按原文明示措施保留；不追认旧模型成功票 |
| 12 | OTC glucose & fat calories | **暂缓名称对齐**；完整营养措施单列保留，不能映射到glucose单一成分 |
| 13 | OTC thickened feeds | 按原文明示措施保留，与chilled共用原句，各自名称来源分开 |
| 14 | OTC Botox | **仅Botox→onabotulinumtoxinA**；不等同所有botulinum toxin产品 |
| 15 | OTC speech therapy | **暂缓**；提交原文，不拿IEP speech services或feeding therapy提供者自动替代 |

第1–9项完成9项来源名称关联；第11、13项作为2项用户确认的原文明示措施保留。所有记录的临床适用性仍未知，推荐状态未判定，新增模型票为0。没有新增正式治疗。

每项保存原审核证据、来源XPath、原句和完整相关表格行，包含原列语义/注释及各自条件；没有把不同来源条件全局合并。全局词表、同义词算法和既有key函数未改。

[11项来源名称处理记录](../../out/structure-identify-names-reviewed-20261121/applied-name-alignments.json) · [冷热/增稠措施独立记录](../../out/structure-identify-names-reviewed-20261121/retained-feeding-measures.json)。

## 第14项：具体成分已对齐，泛称仍未知

旧原文和有效缓存提到Botox®；本地RxNorm产品表列出`onabotulinumtoxinA 100 UNT Injection [Botox]`和`onabotulinumtoxinA 200 UNT Injection [Botox]`。

本次只记录Botox与onabotulinumtoxinA这一具体成分的关系，不将目录规格当本病人剂量，也不推成所有botulinum toxin产品等价。Accepted原有泛称botulinum toxin的Action ID、Key和名称保持不变，其“名称完全对齐”状态仍待审；来源中已确认的窄义成分另外保留。

[品牌—具体成分证据与限制](../../out/structure-identify-names-reviewed-20261121/brand-specific-alignment.json)。因此此次名称对照不是251项，而是250项；不能靠扩大产品范围多算1项。

## 第10、15项：speech therapy直接原文核对

在所用本地冻结XML中，两章都未找到连续短语`speech therapy`，但均有共享后置名词therapy的列举：

GRIN2B / NBK501979：

> Ages 0-3 years. Referral to an early intervention program is recommended for access to occupational, physical, speech, and feeding therapy.

OTC / NBK154378：

> Ages 0-3 years. Referral to an early intervention program is recommended for access to occupational, physical, speech, and feeding therapy as well as infant mental health services, special educators, and sensory impairment specialists.

这不是“没有相关措施”的判定；是原词连续性与名称展开尚未获本轮批准。OTC另有IEP中的speech services；两章还在feeding therapy句中出现speech therapist提供者，不能把提供者表述直接改作speech therapy治疗名称。

两项按用户决定继续暂缓，保留0–3岁、早期干预及其他段落各自范围，不补模型票、不把旧非连续_new追认为成功。

[两章完整相关段落、原位置和连续短语核对结果](../../out/structure-identify-names-reviewed-20261121/speech-source-evidence.md)。

## 第12项：完整营养措施保留，不简单映射到glucose

保留的措施原词：

> Provide calories from glucose & fat

完整原句：

> Provide calories from glucose & fat; resume protein intake (in the form of natural protein & an essential amino acid mix) ≤24 hrs after protein intake was discontinued.

glucose与fat作为完整营养措施保留，后半句≤24 hrs仍随恢复蛋白摄入原文，不分给热量补给。没有据旧缓存单独列出的glucose将整项标为匹配；原Accepted名称glucose & fat calories的名称对齐继续暂缓。

[三项暂缓记录及完整营养措施](../../out/structure-identify-names-reviewed-20261121/deferred-source-review.json)。

## 重新生成Accepted名称对照

名称找到数**239→250/264（+11）**；其余为7项名称未知、6项既定设计排除及1项既定AAC别名。264条记录无增删，原名称、Action ID及clinical source_refs完全保留。这个状态是名称验收记录，不是正式医学状态。

剩余7项及原因：

| 名称 | 原因 |
|---|---|
| GRIN2B speech therapy | 共享therapy列举存在；连续标准名未见，本轮暂缓展开 |
| OTC speech therapy | 同上；speech services/提供者文字不自动视为同名证据 |
| OTC glucose & fat calories | 完整营养措施已保留，但名称对齐暂缓，不简化为glucose |
| OTC botulinum toxin | 只确认onabotulinumtoxinA，不能扩成全部产品等价 |
| CFTR nasal/sinus surgical intervention | 摘要宽泛表述与Management具体手术范围关系仍人工待审 |
| CFTR bowel-obstruction surgical management | 外科咨询不自动等于实施手术，仍人工待审 |
| COL1A1 physiotherapist | 服务/提供者身份及孕期来源边界仍人工待审 |

[完整新名称对照](../../out/structure-identify-names-reviewed-20261121/accepted-alignment.json) · [7项具体未知原因](../../out/structure-identify-names-reviewed-20261121/remaining-unknown-review.md)。

原43项目标集合仍43/43＝41严格同名多数＋2此前获批映射；本轮没有更改历史票、成功率或这个计数口径。13种表头建议和原3项医学语义人工待审保持不变；NF1一般原则备注不补跑，Phase 2未宣称全部验收。

## 修改摘要、必要测试及完整diff

- 从既有确定性名称对照脚本提取小函数`align_source_name`，原流程和本次流程共同复用，仅写派生名称状态、matched_names和解释，不写临床字段。
- 新增[离线已审核名称处理脚本](../../scripts/experiments/structure_identify_reviewed_names.py)，按已批准的审核序号与核对来源处理，不增加医学判断、全局别名规则或调用入口。
- 补[两项必要测试](../../tests/test_structure_identify_reviewed_names.py)：名称更新不动身份/临床字段；真实数据验证11项名称、2明示措施、窄义Botox、完整营养措施及speech暂缓边界。既有测试继续通过。

全量冻结快照离线**1408通过**，外网禁止，仅允许测试本机服务器；测试进程沿用已验收的数据日期2026-11-20，生产日期/缓存TTL未改。[测试日志](../../out/structure-identify-names-reviewed-20261121/tests.log)。

完整名称diff涵盖15条派生记录：11项名称验收状态变化，4项只补窄义证据/暂缓原因；没有记录增删或临床source_refs变化。正式账本详细前后diff为0，对current185项既有差异逐条相同。

- [完整名称diff表](../../out/structure-identify-names-reviewed-20261121/name-alignment-diff.md) · [所有变化字段及完整前后值](../../out/structure-identify-names-reviewed-20261121/name-alignment-diff.json)
- [本轮代码完整补丁（不含文档索引）](../../out/structure-identify-names-reviewed-20261121/code.diff)
- [对current完整status_diff](../../out/structure-identify-names-reviewed-20261121/status-diff-full.txt)
- [本轮前后完整status_diff](../../out/structure-identify-names-reviewed-20261121/status-diff-since-before.txt)
- [身份、临床引用、旧缓存和全部baseline保护核验](../../out/structure-identify-names-reviewed-20261121/verification.json)

本轮模型/API0、$0，原累计仍$0.100842897。不修改医学规则、正式Ledger或Accepted Baseline，不进Phase 3、不处理四个正式评测病例。

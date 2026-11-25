# Phase 2：细条件来源确定性修复

$0、模型/API0。11条FDA细条件按本地原SPL版本保留完整标签段落和JSON pointer；10条CFTR原句按既有genereviews._text精确匹配XPath，保留摘要、表题、同行及列表。多处同文位置分别保留，3条多来源范围仍unknown。

447条件：132同文结构化、244原证据已保留/归属未核、17仅外部上下文、54旧身份未进入活动测试行动。本次21处未配对来源已定位保留，剩余来源缺口0，不代表条件通过；315条仍未完成结构化对应/归属审阅，132条也仅为文字对应。

仅新增23条背景证据，没有新增活动requirement、患者满足判断或推荐。旧票、Action ID/key、原行动/条件/状态/证据、医学规则、生产Ledger、缓存/runs、基线不改。实验装配器补一行，将条件引用的外部证据纳入上下文，防止重建再漏存；不采纳旧临床判定。226项及AAC/tracheostomy等待审项不动，不进Phase3。

149相关离线测试通过，正式/测试改前后status_diff0，正式对current185、独立测试对current1296原项逐条不变。未读四正式评测病例。

[完整报告与21条原文/位置](../../out/structure-condition-sources-20261121/report.md)；[447条对照](../../out/structure-condition-sources-20261121/all-old-condition-audit.json)；[完整status_diff](../../out/structure-condition-sources-20261121/after-current/diff.md)；[测试Ledger字段Diff](../../out/structure-condition-sources-20261121/full-test-ledger-diff.json)。

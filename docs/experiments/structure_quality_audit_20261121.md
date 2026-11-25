# Phase 2测试Ledger候选质量审计

$0、LLM/API0，不读四个正式评测病例，不进Phase3。复用原装配器冻结XML/缓存重建15例，再叠加来源关系/审计元数据；旧活动行动、条件、状态、证据、ID/key均不变，生产Ledger、医学规则和基线不改。

已应用五项来源关系（两CFTR、提供者/服务分开、Botox具体产品、完整glucose & fat措施），均不转移临床结论。Accepted名称253/264，不是医学召回；AAC父类/tracheostomy继续needs_review。

392个病例×候选记录＝388原活动新增＋4源内恢复，对应340个唯一ID。7条来源明确的新管理措施（2支持措施、5专科管理），84重复/关系、41目的/剂量/说明、34检查/风险、226待语义判断；全部留待核查，不导出最终推荐。新增患者推荐0，医学召回未计分。

旧319行动有277活动身份、42身份差异逐项解释，不能视为42漏抽。447条旧要求中132同文结构化对应、223原证据保留但归属未核、17仅外部上下文、54无活动身份、21未配对：11 phenylbutyrate FDA条件片段、10 CFTR来源锚点。后续可$0补完整条件来源保存，但本轮不改条件判定，不自动修复或调用。

147相关离线通过。正式/测试改前后status_diff0，正式对current185和测试对current1296原项不变；保护SHA核对通过。新输出唯一入口是[out/structure-quality-audit-20261121/report.md](../../out/structure-quality-audit-20261121/report.md)，reassembled子目录为原装配检查点，不能拿其旧名称统计代替根目录审计结果。

[完整测试Ledger字段Diff](../../out/structure-quality-audit-20261121/full-test-ledger-diff.json)；[正式完整status_diff](../../out/structure-quality-audit-20261121/after-current/diff.md)；[候选逐项原文](../../out/structure-quality-audit-20261121/candidate-quality.md)；[旧42项](../../out/structure-quality-audit-20261121/old-unmatched.md)；[条件缺口](../../out/structure-quality-audit-20261121/condition-gaps.md)。

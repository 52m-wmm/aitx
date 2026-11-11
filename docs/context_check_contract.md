# 上下文核查契约（v1.0，2026-11-11）

> 模块 `aitx/evidence/context_check.py`；接入点：3a `established._records`（每个 Tier 1 条目在算状态之前）、3c `offlabel._drug`（每个先例）。
> 依据：`docs/clinical_reading_rules.md`（提示词只写原则，不放例子）；修复计划 `docs/post_blind_fix_plan.md` 第二节与架构原则。

## 1. 做什么

对每个要写进报告的条目，用**完整上下文 + 病人信息 + 固定核查问题**做一次 LLM 判断；**LLM 不给状态**，代码按答案增删要求行或改先例字段，账本照旧从要求行算状态。

## 2. 输入（全部由代码组装）

| 条目 | 上下文 |
| --- | --- |
| 3a，GeneReviews | 章节标题 + 小节路径 + 引文所在的表格行（连同表格标题行）或段落（`context_passage`） |
| 3a，FDA 说明书 / L3 文献 | 引文前后各约 1 200 字（文献另加开头 300 字） |
| 3c 先例 | 文章题目 + 完整摘要 |

病人信息（`patient_text`）：诊断、变异（含合子型）、年龄、性别、已识别的表型（存在 / 明确不存在）。

## 3. 核查问题

**3a**（每条都问前三项；后两项按条件问）：
| id | 问题 | 何时问 |
| --- | --- | --- |
| subject | 这段建议是否针对本病（或包含本病的病种群），而不只是别的病 / 亚型 / 基因 | 总问 |
| animal_only | 原文是否说这条建议只基于动物或实验室研究 | 总问 |
| limit | 原文是否把建议限于部分病人（按病人特征：严重程度、年龄、某个表现；不含地点或服务方式），若是请引原文 | 总问 |
| exemption:rN | 在"应避免"语境里，这个条件是不是豁免（可以用的例外）而不是触发条件 | 禁忌节、结果为未知的要求行 |
| meets:rN | 病人信息是否达到原文所说的程度 | 由病人事实判为满足的要求行 |

**3c**（每篇先例）：subject（用药病人是否是本病 / 本基因，引原文）、purpose（是否为治疗本病或其表现而用）、harm（是否描述该药造成或加重问题）、direction（improved / not_improved / worsened / mixed / not_stated，引原文）。

## 4. 判定（代码）

- 每个条目一次调用回答全部问题（结构化 JSON），**独立判 3 次**；一个问题只有 3 次一致才算该答案，否则为 split；缺答按 split；引文须逐字出现在上下文里才保留。
- **3a**（只会把条目推向"有条件"，唯一例外是豁免）：
  - subject 不是一致 "yes" → 加 scope 行"来源段落针对本病"（未知）→ 有条件；
  - animal_only 多数 "yes" → 加 scope 行"建议基于人的发现"（未知）→ 有条件；
  - limit 一致 "yes" 且引文逐字在上下文中、与已有要求不重复 → 加 limit 行（引文即要求）→ 有条件；
  - exemption 一致 "yes" → 该行改为 not_assessed、标 exemption，不再决定禁忌（可能由有条件变为适用）；
  - meets 不是一致 "yes" → 该行改为未知（degree），照常列入缺失信息。
- **3c**：
  - purpose 一致 "yes" 才是治疗先例；否则不进 3c，记入 `not_treatment_precedents`；
  - 不是治疗、且 harm 多数 "yes" → 不良反应报告，记入 `precaution_candidates`（只有 1 例时注明"个案：用后加重；不是禁忌"），**不写成禁忌**；
  - 治疗中出现副作用（purpose yes、harm yes）不影响先例，标 `side_effects`；
  - direction 一致时取其方向（improved → positive，not_improved / worsened → negative，mixed → mixed），否则 not_reported；有合并用药时 positive 记为 combined_unattributable；
  - subject 不是一致 "yes" → 先例标 `subject`（other / not_stated）并引原文，条目加 scope 行 → 有条件。
- **不检查的条目**：L4 人工核实的指南；**3a 中已经是"有条件"、又不在禁忌节的条目**（任何答案都只会让它保持有条件，查了不改变结果——记 `context_check.skipped`）。

## 5. 账本规则

要求行上的 `context_check` 标记（`ledger.CONTEXT_LINE_KINDS`）：
| 标记 | 含义 | 规则 |
| --- | --- | --- |
| scope | 来源范围的限制（不是病人变量） | 不要求逐字；不列入缺失信息 |
| limit | 原文的人群限定 | 必须逐字出现在 `action.context_check.passage` 里；不列入缺失信息 |
| exemption | 禁忌的豁免 | 结果必须是 not_assessed |
| degree | 病人事实没达到原文程度 | 普通未知，必须列入缺失信息 |

每条这类要求行的 note 必须写"context check: <原因>"。3a 条目的 `context_check` 记录保存每题的最终答案、3 次答案、引文、上下文和来源标题。

## 6. 试跑（GRIN2B，2026-11-11）

- 第一版 36 次调用，平均输入 866 / 输出 3 544 个词元（输出多为推理），约 \$0.0023 / 次——是估算的两倍。
- 发现并修正三处判定规则（都补了反向测试）：
  1. 治疗中出现的副作用（L-serine "irritability"、memantine "rare adverse events (3/15)"）被当成不良反应报告，两个真实先例被丢掉 → 改为只有"不是为治疗本病而用"才可能是不良反应报告；
  2. "In the US" 在 2:1 分歧下被当成病人限定 → limit 只认一致 "yes"，问题里排除地点和服务方式；
  3. "建议是否基于人的发现"对普通临床建议常答"未说明"，造成无谓降级 → 改问"原文是否说只基于动物或实验室研究"，多数 "yes" 才降级。
- 修正后 GRIN2B 各条目状态与核查前完全一致（没有误伤），两个先例保留，病人基因有原文引用（"GRIN2B, GRIN1 and GRIN2A variants"）。
- 加上"已是有条件的非禁忌条目不查"之后，GRIN2B 的 3a 只需查 1 条（原来 8 条）。

## 7. 测试

`tests/test_context_check.py`：一致 / 分歧合并、引文逐字过滤、各问题的判定（盲测例子：避免强光、丙戊酸、碳酸氢钠、肺移植、伏立康唑、辅酶 Q10、艾地苯醌）及反向用例（试跑里发现的三种误判）、账本对各类标记行的接受与拒绝、提示词里不含测试集材料。

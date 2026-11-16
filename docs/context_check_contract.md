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
- **不检查的条目**：只有 L4 人工核实的指南。**有条件条目照查**（2026-11-11 决定；曾试过"已有条件的非禁忌条目跳过"以省钱，已撤回）。
- **调用设置**（2026-11-11 决定，预算）：`reasoning_effort: "low"`（DeepSeek 聊天接口取值 none / low / high / max，默认 high，见 api-docs.deepseek.com）、精简 JSON（每题只给答案和不超过 20 词的引文，不给理由），提示词版本 `context-check-v2`。缓存只复用参数完全相同的答案。**是否采用以已判条目验证为准**：抓住 ≥ 80%、误伤 ≤ 5% 才采用（`scripts/validate_context_check.py`）。

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
- 曾加"已是有条件的非禁忌条目不查"以省钱，2026-11-11 按用户决定撤回：有条件条目照查。

## 7. 测试

`tests/test_context_check.py`：一致 / 分歧合并、引文逐字过滤、各问题的判定（盲测例子：避免强光、丙戊酸、碳酸氢钠、肺移植、伏立康唑、辅酶 Q10、艾地苯醌）及反向用例（试跑里发现的三种误判）、账本对各类标记行的接受与拒绝、提示词里不含测试集材料。

## 8. 已判条目验证（2026-11-11 周三 06:58，低推理强度 + 精简 JSON，`context-check-v2`）

单次硬上限 \$0.20（用户批准的一次性例外，见 CLAUDE.md）。81 次调用，实际 **\$0.0538**；每次平均输入 779 / 输出 963 个词元（其中推理 872），**\$0.00066 / 次**（默认 high 档实测 \$0.0023 / 次）。

**结果：抓住 10/13（76.9%），按预设口径误伤 2/13（15.4%）——未达标**（≥ 80%、≤ 5%）。

| 错误类别 | 抓住 | 没抓住的条目与原因 |
| --- | --- | --- |
| 状态（3a：动物模型 / 例外极性 / 程度） | 3/4 | **避免强光**：animal_only 三次答 yes / not_stated / no，无多数——原文是"对所有 RP 病人推荐"，依据却是动物模型，"是否只基于动物研究"问法让判断摇摆 |
| 疗效方向（3c） | 4/5 | **GEMIN5 辅酶 Q10**：三次一致判 mixed（"neurological improvements, although MRI abnormalities remained"）——读法本身站得住，但单篇报告的 mixed 被汇总成"报告相互矛盾"，措辞不对 |
| 不良反应当先例（3c） | 1/1 | — |
| 先例病人的基因 / 亚型（3c） | 2/3 | **艾地苯醌**：三次一致判 same——"a patient with Leigh syndrome"在疾病层面确实相符，问题把"病"和"基因"并成一问，没能问出"基因未说明" |

| 误伤类别 | 数量 | 说明 |
| --- | --- | --- |
| 3a 正确条目状态改变 | 0/11 | — |
| 3c 正确条目（必需脂肪酸、维生素 E） | 2/2 | 先例被标"病人基因未说明"（原文"Twenty patients with type I Charcot-Marie-Tooth disease"，未写基因）；**两条状态不变（原本就是有条件）**。按阅读规则 R3 这一标注本身是对的；按预设口径（先例不再算本病）计为误伤 |

**只加提示、未改状态的正确条目**：
- MPZ "surgery"（髋关节发育不良手术）被加了限定 "severe pes cavus foot deformity"——**张冠李戴**：同一段里另一句（骨科手术）的限定被算到这一条上；
- RRM2B "catabolism" 被加了 "unless the individual is on a ketogenic diet"——原文确有此限定（针对静脉给葡萄糖），属实。

**改法（待批准，未实施）**：见对话报告；只改核查问题和结论措辞模板，不加语义类代码规则。

## 9. 改问题后的复核（2026-11-11 周三 07:07，`context-check-v3`）——达标，采用 low 档 + 精简 JSON

改动（用户批准）：3c 把"病人是谁"拆成疾病、基因两问（基因未写即"未说明"）；3a 把"是否只基于动物研究"改成依据选择题（本病病人 / 其他基因或亚型的病人 / 动物或细胞 / 未说明，多数选后两种才降级）；3a 的限定问题只看本条的原文引文；单篇 mixed 报告的结论措辞改为"报告了改善，其他指标未改善"（新的汇总类别 `partial_improvement`，不再写"报告相互矛盾"）。
误伤口径改为**状态被改变或先例被剔除**（用户决定）。原因：必需脂肪酸 / 维生素 E 的"基因未说明"标注与艾地苯醌适用同一条规则 R3，原判"正确"是判定前后不一致，不是看结果后放宽。

单次硬上限 \$0.10（例外记录见 CLAUDE.md）。81 次调用，实际 **\$0.0488**；每次平均输出 913 个词元（推理 812）。

| 类别 | 结果 |
| --- | --- |
| 疗效方向（3c） | 抓住 5/5（辅酶 Q10 → partial_improvement；核黄素、静脉生酮乳剂、毛果芸香碱、甲泼尼龙 → reported_improvement） |
| 状态（3a） | 抓住 4/4（避免强光、碳酸氢钠、枸橼酸钠 → 有条件；丙戊酸 → 适用） |
| 不良反应当先例（3c） | 抓住 1/1（伏立康唑剔除） |
| 先例病人的基因 / 亚型（3c） | 抓住 3/3（西地那非、PXT3003、艾地苯醌） |
| 3a 正确条目 | 误伤 0/11 |
| 3c 正确条目 | 误伤 0/2 |
| **合计** | **抓住 13/13（100%），误伤 0/13（0%）——达标** |

只加提示、未改状态的正确条目 3 条：RRM2B 分解代谢（"unless the individual is on a ketogenic diet"，属实）；MPZ 必需脂肪酸、维生素 E（先例病人基因未说明，按 R3）。上一轮张冠李戴的"severe pes cavus foot deformity"不再出现。

**局限（用户要求注明）**：这一轮是在同一批题上改问题后的复核，只能确认没改坏；核查器的真实表现以 4 例复测为准，复测时单独报告核查器的抓住和误伤。

## 10. 两层修复：说明书决定的条件 / 限定是否病人所在那一行（2026-11-12，用户决定）

**起因**：修复后全量重跑，3a 验收 29/30——CFTR F508del 纯合 / ETI 被核查器从 GeneReviews 表 5 的一行（"heterozygous for p.Phe508del & a minimal function variant"）加了限定，变"有条件"；该行是另一种基因型的行，ETI 对本病人的适用由 FDA 说明书决定。

1. **落实 3a 已有分工（2026-11-04 定）**：靶向药有点名本病的 FDA 说明书时，适用条件由说明书决定。核查的主段落来自其他来源（GeneReviews / PubMed）时，核查得出的限定、范围、例外、程度**只记备注**（`context_check.label_decides`、`not_applied`），不改状态，也不问追问。不算新增语义规则。测试：`tests/test_established.py`（有说明书→只记备注；反向：无说明书→仍变有条件）。
2. **追问"这条限定是否病人所在的那一行 / 基因型"**（`questions_limit`）：只在限定题全票"是"且引文逐字核实后**单独再问一次**（3 票），主问题和其余条目的缓存不受影响。全票"是"（病人信息表明他就在这一行）→ 限定只记备注、不加条件行；"否 / 未说明 / 分歧"→ 照旧加限定（有条件）。测试：`tests/test_context_check.py`、`tests/test_established.py`；验证集新增追问题 `FOLLOWUP_EXPECT`（CFTR ETI，期望"否"）。
   - 审批类别：全票"是"会把一条本会是"有条件"的条目留在原状态，属"未知变确定"一类，用户 2026-11-12 明确指示加这一问。

**复核（2026-11-12 04:50，非高峰）**：验证集 13/13 抓住、0/13 误伤（主问题全部缓存命中），CFTR 追问 3 票"否"；CFTR 缓存重跑后 ETI 回到"适用"，3a 验收 `cftr-eti` 通过；同时 dornase alfa 的"After the newborn period"因说明书决定而只记备注（15 岁病人，原为有条件）。本次 39 次调用，\$0.0074。其余 11 例因代码指纹变化需缓存补跑（与会话日志 1a/1b 一起）。
**旁注（未改）**：CFTR 有 10 条以"Newborns"为限定的条目，追问对 15 岁病人答"否"，仍为有条件——限定写明的年龄段病人明确不在其中时应为"不适用"，属 B 类改动，记录待定。

## 11. 会话日志（1a）与账本归属（1b）（2026-11-12）

- `aitx/session.py`：每次 LLM 调用（含缓存命中）记一行到 `runs/sessions/<run_id>/calls.jsonl`——调用 ID（= 缓存键，命中与当初的真实调用同 ID）、病例、步骤、提示词版本、完整提示词、原始回答（真实调用另存思考内容）、请求 / 服务端模型名、服务商、是否命中、词元、费用、耗时；每步的运行中 / 完成 / 失败 / 停止、耗时、调用数、费用记到 `steps.jsonl`；完成的步骤把输入病例、上游指纹和输出存为快照 `<case>/step<N>.json`。流水线外的调用（验收、验证脚本）进 `adhoc-<日期>/`。`runs/` 不进仓库；测试写临时目录。
- 账本：各模块的 LLM 出处字典加 `call_id`（随证据的 `produced_by` 进账本）；上下文核查、追问、支持度核查的结果带 3 次投票的 `call_ids`；导出时每条行动附 `provenance`：`llm_calls`（产生其证据的调用）、`rules`（取证路径 / 规则，即证据的 `retrieved_by`）、`code_only`、`check_calls`（核查投票与追问的调用）。新检查 `llm_calls_attributed`（warn）：LLM 产生的证据或核查缺调用 ID 时提示。
- 测试：`tests/test_session.py`（真实调用与命中同 ID、完整提示与回答、费用只记真实调用、步骤事件与快照、流水线外进 adhoc；归属与反向缺 ID 告警）。

## 12. 年龄段限定由代码判定（2026-11-12，用户决定，B 类已批准）

核查器找到的限定若只是明确的年龄段（新生儿、婴儿、儿童、青少年、成人、儿科），且病例写明了年龄（Step 2 有原文引文），由代码按权威定义比对（`aitx/evidence/agebands.py`，不交给 LLM）：确定在段内且限定只说年龄段 → 满足（适用）；确定在段外且没有"或"的其他选项 → 不满足（**不适用**，条目留账本、不写进报告，同孕期条目）；年龄未写 → 未知（有条件，并列入缺失信息"age"）；落在各定义不一致的区间 → 未知。
边界：ICH E11（2000）第 2.5 节——足月新生儿 0–27 天、婴幼儿 28 天–23 个月、儿童 2–11 岁、青少年 12 至 16–18 岁（因地区而异）；与 WHO（青春期 10–19 岁）、临床常用"婴儿 <12 个月"、"children"泛指未成年人、21 CFR 814.3(s)（儿科器械至 21 岁）不一致的区间一律判未知。"After the newborn period"、"older than"、"younger than"等带关系词的限定不由这条判。
测试：`tests/test_agebands.py`（各年龄段段内 / 段外 / 有争议区间；反向：关系词、只说其他条件、"或"选项）、`tests/test_established.py`（年龄未知 → 有条件；段内 → 适用；段外 → 不适用；缺失信息列出年龄）。

## 13. 是否推荐（2026-11-12，用户决定，阅读规则 R15）
支持治疗与已有靶向疗法的条目，每个适用段落另问一次（单独调用、3 票，其他条目的缓存不受影响）："原文是在推荐这项措施，还是只描述常见用法或报告其无效？"（recommends / describes_use / reports_ineffective / not_stated）。所有被问的段落都全票答"描述用法"或"报告无效"时，加一条 `context_check = "recommendation"` 的不满足行，条目判不适用、留在账本、不写进报告；禁忌节和由说明书决定条件的药不问。投票调用 ID 记在 `context_check.recommendation.call_ids`（并计入 `provenance.check_calls`）。

## 14. 非推荐理由分三档（2026-11-15，用户决定）
账本理由：推荐（不加行）/ 描述用法（含结果不一致）/ 报告无效。"报告无效"只在 3 票都答"报告无效"、且段落没有"inconsistent / conflicting / mixed / variable results"类措辞时使用，否则记"描述用法"（`recommendation_reason`，`context_check.recommendation.reason`）。由代码判定，只改理由文字、不改状态。起因 EIF2B1 皮质类固醇（"used with inconsistent results in acute situations"）。测试 `tests/test_context_check.py`、`tests/test_established.py`。

## 15. 推荐句与局限句（2026-11-15 用户决定，冲击波碎石）
段落里"是否推荐"3 票答推荐、但推荐的原话不在条目自己的引文里时：引用含推荐原话的那一句作为主证据，条目原来的句子记为 `cautions`（报告里写成 "Caution (same source)"）；从那句局限句读出的表现条件改为推荐句（仍为有条件）。只对段落文本做，表格行不做。测试 `tests/test_established.py`。

## 16. 表现条件：目的、严格 HPO 映射、情境状语（2026-11-15 用户批准，第 5 项）
- **目的**：条件文字紧跟在预防性词（Prevent / Prevention of / Reduce / Decrease / Inhibit / Minimize / Lower / Limit）之后，或就在 Objective 栏的预防句里，且只看条目自己那一行 / 那一段；Treat / Manage / Control 或"Manifestation/Concern"栏里的表现仍是条件。目的记在 `purposes`，不作条件。
- **去掉目的只去掉目的本身**：同一行的"表现 / 问题"栏（如"[Manifestation/Concern: Bone health]"）补为条件；小标题、年龄、使用情境照旧保留。
- **严格 HPO 映射**：先精确名称 / 同义词；否则只有检索到的词条名称包含条件的每个实词才算映射上；依据记在 `patient_fact.match` 与行 note；映射不上保持有条件并注明。EIF2B1 物理治疗因此回退为有条件，记为严格映射的召回代价（用户接受）。
- **情境状语**：治疗栏（表格）整格、或段落里条目自己的列表项内的 during / when / whenever / while / in periods of / in case of 短语，按"使用情境"条件抽取（不论有没有目的从句）；"when possible / if appropriate"等不算；不跨逗号 / 分号列表项。
- 测试：`tests/test_established.py`。


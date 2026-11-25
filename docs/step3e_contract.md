# Step 3e 契约：药物重定位（Tier 3 · Drug Repurposing）——设计与历史修订

> 当前已有实现：`aitx/evidence/repurposing.py:add_repurposing`。下文为药物重定位设计及历史修订；代码存在不表示医学候选已获确认，历史提案不自动成为新授权。

本节产出的内容必须明确标为假设，不能写成建议或“可以试”。原设计将无人体先例的候选与3c区分；不能仅因靶点相符就纳入作用方向相反的药物。

## 1. 这一节回答什么

一条链，每一跳都要有数据库记录作证据：

```
病人的基因（Step 1 / Step 2）
  → 这个基因参与的通路、或它所属的蛋白家族 / 复合体     （证据：Reactome 通路记录）
    → 作用于该靶点（或该通路上其他成员）的药物           （证据：Open Targets 的 target→drug 记录、ChEMBL 的 mechanism 记录）
      → 这个药的作用方向是否与病人的分子缺陷相符          （证据：ChEMBL action_type / Open Targets mechanismOfAction，再对照 Step 3d 的疾病机制）
        → 有没有体外 / 动物证据支持用于这个基因的病       （证据：PubMed 记录，沿用 3c 的检索与引文核验模块）
```

每一跳的记录 id 都要进账本（`R-HSA-…`、`CHEMBL…`、Open Targets 的 `ENSG…` / `CHEMBL…`、PMID），**引用必须能解析到具体记录**。任何一跳拿不到记录，这条候选就不写。

## 2. 数据来源（2026-11-06 当场验证）

| 跳 | 来源 | 接口 | 已验证 |
| --- | --- | --- | --- |
| 基因 → 通路 | **Reactome** ContentService | `/ContentService/search/query?query=<基因>&species=Homo%20sapiens`；`/ContentService/data/participants/<stId>/referenceEntities` 取通路成员 | ✅ GRIN2B → `R-HSA-9609765`（Protein, UniProt Q13224）；通路 `R-HSA-9617324`（Negative regulation of NMDA receptor-mediated neuronal transmission）有 27 个实体，成员基因如 CAMK2A/B/D/G、ACTN2、CALM1 |
| 基因 → 通路（交叉核对） | **Open Targets Platform** GraphQL v4 | `target(ensemblId:…){pathways{pathwayId pathway topLevelTerm}}` | ✅ GRIN2B（ENSG00000273079）返回 11 条通路，`pathwayId` 就是 Reactome 的 stId，可与上一行互相核对 |
| 靶点 → 药物 | **Open Targets** GraphQL v4 | `target(ensemblId:…){drugAndClinicalCandidates{count rows{id maxClinicalStage drug{id name drugType maximumClinicalStage mechanismsOfAction{rows{mechanismOfAction actionType}}}}}}` | ✅ GRIN2B 返回 **31** 条候选，含 AMANTADINE（APPROVAL，Glutamate [NMDA] receptor antagonist）、ESKETAMINE（APPROVAL，negative allosteric modulator）、RAPASTINEL（PHASE_3，partial agonist）、APIMOSTINEL（PHASE_2，partial agonist）等 |
| 药物作用方向 | **ChEMBL** REST | `/chembl/api/data/target.json?target_components__accession=<UniProt>`；`/chembl/api/data/mechanism.json?target_chembl_id=<CHEMBL id>` | ✅ Q13224 → 4 个靶点记录（`CHEMBL1904` 单蛋白、`CHEMBL1907603` GRIN1/GRIN2B 复合体、`CHEMBL2094124` 受体家族组）；复合体 `CHEMBL1972` 上有 2 条 ANTAGONIST 机制，各带 3 条文献引用；**`CHEMBL1904`（GRIN2B 单蛋白）上 0 条机制** |
| 体外 / 动物证据 | **PubMed** E-utilities | 沿用 3c 的检索、摘要获取、PMC 开放获取全文与引文核验 | ✅（3c 已在用） |

**从验证里得到的三条教训，直接写成规则**：
1. **靶点记录有多个层级**：单个亚基、蛋白复合体、受体家族组。ChEMBL 把机制挂在复合体上（`CHEMBL1972`），挂在 GRIN2B 单蛋白上的是 0 条。所以查药必须沿"亚基 → 所属复合体 → 家族组"逐层查，并**在账本里写明这条机制是挂在哪一层**。
   **家族 / 复合体层级的机制可用**（2026-11-06 决定），但必须：① 结论句里写明"对本基因亚基的选择性未知"；② 排在"亚基层级有直接机制证据"的候选**之后**；③ 账本记录 `target_level` 字段（`subunit` / `complex` / `family_group`）和那条机制记录的 id。
2. **Open Targets 的 `pathwayId` 就是 Reactome stId**，所以两个来源能互相核对；不一致时按 Reactome 的记录为准，并把差异记进账本。
3. **方向问题最危险**：GRIN2B 的 31 条候选里绝大多数是 NMDA 受体**拮抗剂**。本项目的 GRIN2B 练习病例是**功能丧失**（p.Gln919Ter，无义变异），拮抗剂方向相反、只会更糟。所以方向判定是硬性的（见 3.3）。

## 3. 判定规则（代码为主，LLM 只用于从文献里抽取体外 / 动物证据，抽完过支持度核查）

### 3.1 入口条件
- 必须先有 Step 3d 的疾病机制（来自 GeneReviews，逐字引用）。**机制未知 → 整节写"无法评估：疾病机制无出处"，不产出任何候选。** 没有机制就判不了方向，而方向判错就是最严重的"写错"。
- 必须有 Step 1 的变异类型；嵌合 / X 失活的情形沿用 3d 的处置（写"无法评估"，列进缺失信息）。

### 3.2 候选怎么来
- **第一圈：同一靶点**。病人的基因本身作为靶点，取 Open Targets 的 `drugAndClinicalCandidates`，再用 ChEMBL 的 mechanism 核对作用方向。
- **第二圈：同一通路**。Reactome 通路里的其他成员基因作为靶点，同样取药。通路必须是**病人基因直接参与**的（Reactome 记录里有它），不是"相关通路"。每条候选要写清是通过哪条通路、哪个成员靶点到的。
- 上限：每个分支最多分析 10 个候选药（和 3b 的逐条上限一致），按"方向相符 + 证据强度 + 临床阶段"排序后取前 10，排除掉的记录数和理由写进账本。

### 3.3 方向判定（硬性，不符就不写）

| 病人的分子缺陷（来自 3d 机制） | 需要的药物方向 | 不符的方向（直接排除） |
| --- | --- | --- |
| 功能丧失 / 单倍剂量不足 | 激动剂、正向变构调节剂（PAM）、增强剂、伴侣分子（chaperone）、通读剂 | 拮抗剂、抑制剂、负向变构调节剂、阻断剂 |
| 功能获得（活性过强） | 拮抗剂、抑制剂、负向变构调节剂、阻断剂 | 激动剂、正向变构调节剂 |
| 显性负效应 | 只接受降低异常产物的手段（归 3d 的敲低），**3e 一般不写**，除非文献明确报告该药对显性负效应有效 | 其余 |

- 方向词从 ChEMBL 的 `action_type`（ANTAGONIST / AGONIST / POSITIVE ALLOSTERIC MODULATOR / INHIBITOR / BLOCKER / PARTIAL AGONIST …）和 Open Targets 的 `mechanismOfAction` 文本里取，**由代码按受控词表映射**，不让 LLM 判断方向。
- 词表里没有的方向词（例如 "modulator" 这种不分正负的）→ 该候选判"方向不明"，**不写进报告**，只记进账本的排除清单。
- `PARTIAL AGONIST`（部分激动剂）单独处理：对功能丧失**可以**写，但必须注明是部分激动剂；对功能获得不写。

### 3.4 与 3a / 3b / 3c 的分界（同一行动不跨章节重复）
- 这个药已经在 3a（已获批且适用）、3b（在招募试验里）或 3c（有人体先例）出现过 → **3e 不写**，只在账本里记一条"已在 X 章节"。沿用 3c 的 `source_alias` 去重（同一药物的不同写法也算同一个）。
- **3e 的定义性条件：没有人体先例。** 一旦检索到该药用于本病（或本基因的病）的人体报告，这条候选就属于 3c，3e 把它移交过去并记录。
- 3d 与 3e：定制手段（ASO / 基因替代 / 编辑）归 3d；小分子、已上市药物、营养补充剂的体外筛选结果归 3e（2026-11-05 决定）。

### 3.5 证据强度与措辞
- 每条候选必须标明最高证据层级：`in_vitro`（细胞 / 类器官）/ `animal_model` / `target_rationale_only`（只有靶点与方向相符，没有任何实验证据）。
- `target_rationale_only` 的候选**可以写进报告**（2026-11-06 决定），条件是三条同时满足：① 每一跳都有可解析的数据库记录；② 方向判定通过（不是"方向不明"）；③ 结论句明确标为假设。**每个分支最多 3 条**，按**证据链完整程度**排序（通路记录 + 亚基层级机制 + 明确方向词 齐全的在前；靠家族层级机制或靠通路成员间接到达的在后）。超出 3 条的只进账本，并在账本里记下被截掉的条数。
- 结论句由代码生成，固定措辞，不许出现 recommended / effective / proven / 可以试用：
  - 有体外证据：`A hypothesis only: <药> acts as a <方向> at <靶点>, which <基因> variants affect; <体外证据简述，附 PMID>. No human has been treated with it for this disease.`
  - 只有靶点理由：`A hypothesis only: <药> acts as a <方向> at <靶点>. No experimental evidence in this disease and no human precedent.`
- 剂量、给药途径一律不写（没有人体依据）。

## 4. 账本记录

- 章节 `drug_repurposing`（已在 `ledger.SECTIONS`，层级 hypothesized）。
- 每条候选一条行动记录：`action_key`（沿用 3c 的 `drug:rxcui:…` / `drug:chembl:…` 规范化）、`route`（同一靶点 / 同一通路 + 通路 id + 成员靶点）、`direction`（方向词 + 来源记录 id + 挂在哪一层靶点）、`evidence_level`、`pmids`、`conclusion`。
- 另记：`repurposing_searches`（每个分支：通路数、候选药数、各步筛掉多少及理由）、`excluded`（方向不符 / 方向不明 / 已在其他章节 / 无证据，各带记录 id）。
- 新增校验 `repurposing_consistent`：
  1. 每条候选的每一跳都有可解析的记录 id；
  2. 方向与 3d 机制相符（不符的不得出现在 actions 里）；
  3. 没有任何候选同时出现在 3a / 3b / 3c；
  4. 结论句不含禁用词，也不含剂量；
  5. 有人体先例的候选不得留在 3e；
  6. 每个分支要么有候选，要么有一条已核实的"检索无结果"负面证据。

## 5. 验收（只用练习病例；期望先人工核实原文后再写入 `data/eval/`）

**已写入 `data/eval/step3e_expectations.json`（2026-11-06，5 条，全部当场查库核实）**，验收脚本 `scripts/acceptance_step3e.py`：

| ID | 期望 | 核实依据 |
| --- | --- | --- |
| grin2b-pam-candidate | NEBOGLAMINE（NMDA 正向变构调节剂）作为假设出现，方向 up，层级 family_group，结论带"对本亚基选择性未知"、标为假设、无人体先例 | Open Targets ENSG00000273079：NEBOGLAMINE = CHEMBL1255840，action type POSITIVE ALLOSTERIC MODULATOR，机制靶点为 7 个 GRIN 亚基（故为家族层级） |
| grin2b-partial-agonist-labelled | RAPASTINEL 可写，但必须写明是部分激动剂 | 同上，action type PARTIAL AGONIST |
| grin2b-antagonists-excluded | 美金刚 / 金刚烷胺 / 艾司氯胺酮 / 阿坎酸不得出现，排除理由记账本 | 同上；阿坎酸 CHEMBL1201293 有 NMDA ANTAGONIST 与 GABA-A POSITIVE MODULATOR 两行，按靶点过滤后只剩前者 |
| grin2b-subunit-level-is-honest | 所有候选都是家族层级，`subunit_level_molecules` 为 0 | ChEMBL Q13224：CHEMBL1904（SINGLE PROTEIN）上机制数为 0 |
| agxt-no-candidates | AGXT 不写任何候选，只留一条已核实的"检索无结果"负面证据 | Open Targets ENSG00000172482：drug 记录 0 条（ANO10、SLC35A2、KMT2B 同样为 0） |

> 期望检查的是结构与方向，不是计数：数据库会更新，所以把当时的计数写在 source 里，日后不一致时能分清是库变了还是代码坏了。


**已知用例（审阅指定）：GRIN2B 的 NMDA 受体正向变构调节剂（PAM），只有体外研究。**

| 提议 ID | 病例 | 期望 | 待核实的依据 |
| --- | --- | --- | --- |
| grin2b-pam-hypothesis | PRAC-GRIN2B（p.Gln919Ter，无义，预测逃逸 NMD） | NMDA 受体 PAM 作为**假设性**候选出现在 3e：方向与功能丧失相符，证据层级 `in_vitro`，结论句写明无人体先例 | 需人工核实：① 3d 给出的 GRIN2B 机制（GeneReviews 原文）；② PAM 的体外研究 PMID 与原文句子；③ 该化合物在 ChEMBL / Open Targets 里的 action_type 确实是正向变构调节 |
| grin2b-antagonists-excluded | PRAC-GRIN2B | 美金刚、艾司氯胺酮等 NMDA **拮抗剂**不得出现在 3e（方向相反），且排除理由记在账本 | Open Targets 已查到：AMANTADINE = antagonist（APPROVAL）、ESKETAMINE = negative allosteric modulator（APPROVAL）。方向与功能丧失相反 |
| grin2b-memantine-not-duplicated | PRAC-GRIN2B | 美金刚如果已在 3c（本次运行里它确实作为 3c 条目出现过），3e 不重复 | 需核实当次运行的 3c 结果 |
| agxt-no-candidates | PRAC-AGXT-c33dup | 若没有方向相符且有实验证据的候选 → 整节写"检索无结果"的负面证据，**不写任何候选** | 反向验证：宁缺勿错 |
| col1a1-direction-mismatch | PRAC-COL1A1（机制为功能获得 / 显性负效应） | 任何"补充 / 增强 I 型胶原"方向的候选都不得出现 | 3d 已给出机制（GeneReviews NBK1295 原文） |

反向验证（离线测试）：
- 把 3d 机制改成"功能获得"，原本为功能丧失写的 PAM 候选必须消失；
- 方向词换成 "modulator"（不分正负）→ 候选被排除，理由记录；
- 把某候选也放进 3c → 3e 不再写它；
- 通路记录取不到 → 该候选不写，不允许只凭"同一受体家族"就写。

## 6. 费用与运行
- Reactome / Open Targets / ChEMBL 都是免费公开接口，无需密钥；按现有 `aitx/http.py` 缓存（记 sha256 和取用时间）。
- LLM 只用于从文献里抽体外 / 动物证据（每个候选 1 次，再过支持度核查），按非高峰规则运行，守当天预算上限。
- 预估：每个分支 10 个候选 × 1 次抽取 + 核查，和 3c 同量级。

## 7. 待定问题

### 已决定（2026-11-06）
- **只有靶点理由的候选**：可以写，条件是每一跳有数据库记录、方向判定通过、明确标为假设；每个分支最多 3 条，按证据链完整程度排序（见 3.5）。
- **ChEMBL 靶点层级**：家族 / 复合体层级的机制可用，但要写明"对本基因亚基的选择性未知"，并排在亚基层级有直接证据的候选之后（见第 2 节教训 1）。

### 待你决定（6 条，每条附我的建议）

2. **第二圈（同一通路）要不要限制跳数**：只取病人基因直接参与的通路成员（1 跳），还是允许"通路的上下游通路"（2 跳）？建议**只取 1 跳**。2 跳会把整个神经信号通路都拉进来，噪声远大于信息。
3. **候选上限 10 个够不够**，以及排序权重（方向相符是硬条件；其余按证据层级 → 临床阶段 → 是否已上市）。建议先按此实现，盲测后再调，并把权重列入盲测重点检查项。
4. **家族层级的候选能不能是某分支里唯一的候选？**（第 4 条已决定可用并降级排序，这一点仍未定）建议**可以，但要在结论句里再加一句"本分支没有亚基层级的直接证据"**，让读者知道这一节的证据底子有多薄。
5. **Open Targets 与 Reactome 通路不一致**时的处置：建议以 Reactome 为准、记录差异；是否需要第三个来源（如 WikiPathways）交叉核对，待定。
6. **营养补充剂的归属**：L-serine 这类在 3c 已有先例的，归 3c；若某补充剂只有体外证据，归 3e 还是仍按 3c 的"获取途径"处理？建议归 3e，但沿用 3c 的 `config/supplements.json` 判定获取途径。
7. **"没有人体先例"怎么判定才算可靠**：现在靠 3c 的检索结果。若 3c 检索因故失败（接口报错），3e 是否暂停输出？建议**暂停并写明原因**，否则可能把已有先例的药错放进 3e。
8. **与 Step 4 的接口**：3e 要向排序提供哪些字段？建议与 3d 一致：`evidence_level`、`direction_match`、`approved_elsewhere`（该药在别的病上是否已上市）、`premises_complete`。


## 8. 待定问题的处置（2026-11-06 审阅定稿）

| # | 问题 | 决定 |
| --- | --- | --- |
| 1 | 只有靶点理由的候选 | **可以写**：每一跳有记录 + 方向判定通过 + 明确标为假设；每分支最多 3 条，按证据链完整程度排序 |
| 2 | 同一通路的跳数 | **只取 1 跳**（病人基因直接参与的通路成员）。2 跳会把整个信号网络拉进来 |
| 3 | 候选上限与排序权重 | 上限 10；方向相符是硬条件；其余按"有无实验证据 → 靶点层级 → 到达路径 → 物种（动物优于细胞，仅作并列时的次序）→ 临床阶段"。**权重列入盲测重点检查项** |
| 4 | 家族 / 复合体层级的机制 | **可用**，但结论句写"对本基因亚基的选择性未知"，排在亚基层级有直接证据的候选之后，账本记 `target_level` |
| 5 | Open Targets 与 Reactome 通路不一致 | **以 Reactome 为准、记录差异**，暂不接第三个来源（两者本是同源数据，不一致多为版本差） |
| 6 | 营养补充剂归属 | 按有无人体先例分，与其他药一致：有先例归 3c，只有体外证据归 3e；归 3e 时仍用 `config/supplements.json` 判获取途径 |
| 7 | "没有人体先例"的可靠性 | 3c 检索失败时 **3e 暂停输出并写明原因**，否则可能把已有先例的药错放进 3e（把更强的证据降级成假设） |
| 8 | 交给 Step 4 的字段 | `evidence_level`、`direction_match`、`approved_elsewhere`、`premises_complete`，外加 `target_level`（家族层级在排序里降权） |

## 9. 实现（2026-11-06）

- 模块 `aitx/evidence/repurposing.py`，离线测试 `tests/test_repurposing.py`（先写测试，50 条）；账本校验 `repurposing_consistent`；账本另记 `repurposing_searches`（每个分支：机制、需要的方向、候选数、保留数、每条排除理由）。
- 新增 `aitx/http.py` 的 `post_json`（带缓存的 POST，GraphQL 只接受 POST；缓存键含请求体）。
- **实测发现并写成规则的两件事**：
  1. **机制记录必须是关于本基因的靶点**。阿坎酸（acamprosate）在 NMDA 受体上是 ANTAGONIST，同时在 GABA-A 受体上是 POSITIVE MODULATOR。不按靶点过滤，GABA-A 那条就会让它对 GRIN2B 功能丧失病人显示为"增强活性"的候选——这正是最严重的"写错"。`rows_for_target` 按机制行的 targets 过滤；同一靶点上若仍有正反两个方向，`one_direction` 判为不可用、不写。
  2. **靶点层级要看机制记录本身，不看基因**。GRIN2B 的三个候选（RAPASTINEL、APIMOSTINEL、NEBOGLAMINE）的机制行都列了 7 个 GRIN 靶点，所以它们是家族层级的论断，尽管 GRIN2B 在 ChEMBL 里有 SINGLE PROTEIN 记录（而该记录上的机制数是 0）。`level_from_rows` 据此判定，三条都带上"对本亚基选择性未知"。
- **GRIN2B 单病例离线试跑（不调用 LLM）**：50 条机制记录 → 按靶点过滤与方向判定后排除 28 条（全是 NMDA 拮抗剂，方向与功能丧失相反），保留 3 条；校验通过。首次联网接入（含文献证据抽取）排在周六补跑，按新规则先单病例、通过后再跑其余。

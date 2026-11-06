# Step 3e 契约：药物重定位（Tier 3 · Drug Repurposing）——草案 v0.1（待审，只写契约，未实现）

> 2026-11-06 起草，起草过程没有调用 LLM；下面提到的三个数据库都当场查过真实记录（见第 2 节"已验证"列）。
> 本节产出的全部是**假设性**内容。每一条都必须写成"假设"，不能写成建议，也不能说"可以试"。
> "写错比不写更糟"：**3e 没有人体先例**，这是它和 3c 的根本区别。宁可整节写"没有可引用的候选"，也不要把一个靶点相符但方向相反的药放进去。

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
1. **靶点记录有多个层级**：单个亚基、蛋白复合体、受体家族组。ChEMBL 把机制挂在复合体上（`CHEMBL1972`），挂在 GRIN2B 单蛋白上的是 0 条。所以查药必须沿"亚基 → 所属复合体 → 家族组"逐层查，并**在账本里写明这条机制是挂在哪一层**——挂在家族组上的药，对单个亚基的选择性未知。
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
- `target_rationale_only` 的候选**默认不写进报告**，只进账本；是否写由审阅决定（见待定问题 3）。
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

1. **只有靶点理由、没有任何实验证据的候选，写不写进报告？** 我的建议：**不写**，只进账本。理由：这类候选等于"这个药作用在相关蛋白上，方向也对"，没有任何实验支持，评审看到会认为是凑数；但账本留着，Step 4 排序时可以说明"还有 N 个仅靶点相符的候选未写入"。
2. **第二圈（同一通路）要不要限制跳数**：只取病人基因直接参与的通路成员（1 跳），还是允许"通路的上下游通路"（2 跳）？建议**只取 1 跳**。2 跳会把整个神经信号通路都拉进来，噪声远大于信息。
3. **候选上限 10 个够不够**，以及排序权重（方向相符是硬条件；其余按证据层级 → 临床阶段 → 是否已上市）。建议先按此实现，盲测后再调，并把权重列入盲测重点检查项。
4. **ChEMBL 靶点层级**：挂在"受体家族组"（如 `CHEMBL2094124`）上的机制要不要用？建议**用但降级**：注明"机制记录挂在受体家族层级，对该亚基的选择性未知"，并且这类候选不得是某个分支里唯一的候选。
5. **Open Targets 与 Reactome 通路不一致**时的处置：建议以 Reactome 为准、记录差异；是否需要第三个来源（如 WikiPathways）交叉核对，待定。
6. **营养补充剂的归属**：L-serine 这类在 3c 已有先例的，归 3c；若某补充剂只有体外证据，归 3e 还是仍按 3c 的"获取途径"处理？建议归 3e，但沿用 3c 的 `config/supplements.json` 判定获取途径。
7. **"没有人体先例"怎么判定才算可靠**：现在靠 3c 的检索结果。若 3c 检索因故失败（接口报错），3e 是否暂停输出？建议**暂停并写明原因**，否则可能把已有先例的药错放进 3e。
8. **与 Step 4 的接口**：3e 要向排序提供哪些字段？建议与 3d 一致：`evidence_level`、`direction_match`、`approved_elsewhere`（该药在别的病上是否已上市）、`premises_complete`。

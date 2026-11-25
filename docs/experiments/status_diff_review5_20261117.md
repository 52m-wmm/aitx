# 第五轮 diff 来源分类与待批准清单

固定输入为第五轮开始时的106新增 /18删除 /57细节，共181个行动×分支项目；不计仍待审的状态项和4个RETEST缺历史基线项。条数按分支计，不能用去重行动数代替。

| 来源组 | 新增 | 删除 | 细节 | 总数 | 状态 | 样例（最多3项，不足不编造） |
| --- | --- | --- | --- | --- | --- | --- |
| E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | 25 | 0 | 0 | 25 | 待一次性批准实际行；未升级 | PRAC-ANO10 / None found / MONDO:0013392；PRAC-GRIN2B / Online Study of People Who Have Genetic Changes and Features of Autism: Simons Searchlight (NCT01238250) / MONDO:0013509；PRAC-NF1 / Cyclin-Dependent Kinase (CDK)4/6 Inhibitor Abemaciclib for Neurofibromatosis Type I (NF1) Related Atypical Neurofibromas (NCT04750928) / MONDO:0018975 |
| 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | 57 | 0 | 0 | 57 | 待一次性批准实际行；未升级 | PRAC-ANO10 / riluzole / MONDO:0013392；PRAC-GRIN2B / physical therapy / MONDO:0013509；PRAC-SLC35A2-ex7 / start early intervention as soon as the delay is recognized / MONDO:0010478 |
| 已批准通用 Pregnancy Management 附注规则 | 0 | 16 | 0 | 16 | 待一次性批准实际行；未升级 | PRAC-AGXT-c33dup / adequate fluid intake / MONDO:0009823；PRAC-CFTR-F508del / fat-soluble vitamin A supplementation / MONDO:0009061；PRAC-OTC / intact versus essential amino acid supplementation / MONDO:0010703 |
| 本轮明确批准的两个无关试验删除（已升级） | 0 | 2 | 0 | 2 | 本轮已明确批准并升级 | PRAC-CFTR-F508del / Bronchiectasis and NTM Research Registry (NCT01822834) / MONDO:0009061；PRAC-CFTR-F508del / DIaphragmatic Swing According to Cpap Flow Output in NEOnates (DISCONEO) (NCT07513051) / MONDO:0009061 |
| 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | 0 | 0 | 57 | 57 | 待一次性批准实际行；未升级 | PRAC-AGXT-c33dup / Rare Kidney Stone Consortium Biobank (NCT02026388) / MONDO:0009823；PRAC-CFTR-F508del / Personalized Theratyping Trial (NCT03587961) / MONDO:0009061；PRAC-COL1A1 / Preliminary Evaluation of the Safety and Tolerability of SPOT-mRNA01 Subcutaneously Administered in Healthy Subjects (NCT06567119) / MONDO:0007522 |
| Evidence ID 方案变化 | 0 | 0 | 0 | 0 | 无此类差异 | 0项，无本批样例；ID方案实际未变 |
| 其他：已检索分支的新增试验召回 / 分析范围，逐条待审 | 24 | 0 | 0 | 24 | 逐条待审 | PRAC-AGXT-c33dup / RKSC (NCT00588562) / MONDO:0009823；PRAC-AGXT-c33dup / ProRKS (NCT02780297) / MONDO:0009823；PRAC-AGXT-c508GA / RKSC (NCT00588562) / MONDO:0009823 |

E 的25项是历史明确未运行的病例级3b首次接入（ANO10 1、GRIN2B14、NF1 10），不同于已升的124项全局3c/3d/3e新增。3a新增优先按实际来源归入回退/章节组，避免重复计数。

57个细节项的旧ID逐一用当前冻结算法重算，共623个病例×ID均一致；17项仅增加证据，40项删除或更换证据。29个为3b记录，28个为3a记录。不能以“ID方案变了”批量掩盖原文/条件/分支变化；JSON保留每行移除/新增ID、claim及原文供审。

可按已有批准类别一次性确认的实际行共155项（25+57+16+57），完整change_id在 `runs/review5-20261117/noise_classification.json` 的 pending_batch_change_ids；当前 approved=false。两项NCT删除已经单独获批，另24项其他不混入这155项。具体未批准候选与完整diff在 `out/status_diff/review5-20261117/batch-proposal/`：只包含这155项，候选593行，当前正式基线仍527行；没有调用promote升级此提案。

范围提示：155项中 KMT2B 的3b阴性检索ID细节仍取自保留的旧正式账本；其完整刷新尚缺3c缓存。这里仅列该字段的待审提案，不宣称KMT2B整例新鲜。所有旧ID均能按当前算法重算，不能把这些证据内容变化称为“纯ID方案迁移”。

## 其他24项：逐条清单

| Change ID | Case / Branch | Action / Source | New status | Known exclusions | 原因与待审点 |
| --- | --- | --- | --- | --- | --- |
| f9622032bf3b5584 | PRAC-AGXT-c33dup / MONDO:0009823 | RKSC (NCT00588562) / [registry](https://clinicaltrials.gov/study/NCT00588562) | conditional | 0 | excluded；新增查询1组；记录的上级病名：primary hyperoxaluria；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 6f3446215cb53e61 | PRAC-AGXT-c33dup / MONDO:0009823 | ProRKS (NCT02780297) / [registry](https://clinicaltrials.gov/study/NCT02780297) | conditional | 0 | excluded；新增查询1组；记录的上级病名：primary hyperoxaluria；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 904f9ab49bd9cdd2 | PRAC-AGXT-c508GA / MONDO:0009823 | RKSC (NCT00588562) / [registry](https://clinicaltrials.gov/study/NCT00588562) | conditional | 0 | excluded；新增查询1组；记录的上级病名：primary hyperoxaluria；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| b2017b1f265c1d7f | PRAC-AGXT-c508GA / MONDO:0009823 | ProRKS (NCT02780297) / [registry](https://clinicaltrials.gov/study/NCT02780297) | conditional | 0 | excluded；新增查询1组；记录的上级病名：primary hyperoxaluria；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| e4db6afbe941bbe9 | PRAC-CFTR-F508del / MONDO:0009061 | STOP PEDS RCT (NCT06654752) / [registry](https://clinicaltrials.gov/study/NCT06654752) | conditional | 0 | over_cap；新增查询1组；记录的上级病名：未记录上级病名；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| b69bcedb0b2d3778 | PRAC-CFTR-F508del / MONDO:0009061 | The Effects of Yoga Practice on Exercise Capacity, Arterial Stiffness, Respiratory Function, Peripheral Muscle Strength, Posture and Quality of Life in Children With Cystic Fibrosis (NCT07930221) / [registry](https://clinicaltrials.gov/study/NCT07930221) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询1组；记录的上级病名：未记录上级病名；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 7a63eebcfc700d0b | PRAC-COL1A1 / MONDO:0007522 | CARPE-CMD (NCT02050113) / [registry](https://clinicaltrials.gov/study/NCT02050113) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询1组；记录的上级病名：Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 3da4423142e21936 | PRAC-COL1A1 / MONDO:0020521 | CARPE-CMD (NCT02050113) / [registry](https://clinicaltrials.gov/study/NCT02050113) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询2组；记录的上级病名：Ehlers-Danlos syndrome, arthrochalasia type / Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| ff712e86b7ed5549 | PRAC-COL1A1 / MONDO:0007522 | Auricular Vagal Nerve Stimulation for Hypermobile Ehlers-Danlos Syndrome (NCT05212129) / [registry](https://clinicaltrials.gov/study/NCT05212129) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询1组；记录的上级病名：Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| f3c50ed2269ca725 | PRAC-COL1A1 / MONDO:0020521 | Auricular Vagal Nerve Stimulation for Hypermobile Ehlers-Danlos Syndrome (NCT05212129) / [registry](https://clinicaltrials.gov/study/NCT05212129) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询2组；记录的上级病名：Ehlers-Danlos syndrome, arthrochalasia type / Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 7f0f7cc274244ccf | PRAC-COL1A1 / MONDO:0007522 | DiSCOVER (NCT05432466) / [registry](https://clinicaltrials.gov/study/NCT05432466) | not_applicable | 2 | 旧账本未记录该NCT的分析/排除位置；新增查询1组；记录的上级病名：Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 6c9b480dbfd962df | PRAC-COL1A1 / MONDO:0020521 | DiSCOVER (NCT05432466) / [registry](https://clinicaltrials.gov/study/NCT05432466) | not_applicable | 2 | 旧账本未记录该NCT的分析/排除位置；新增查询2组；记录的上级病名：Ehlers-Danlos syndrome, arthrochalasia type / Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 87995a228e2bd3b6 | PRAC-COL1A1 / MONDO:0007522 | Heart Coherence Training on Vascular Ehlers-Danlos Syndrome Patients (NCT05994664) / [registry](https://clinicaltrials.gov/study/NCT05994664) | not_applicable | 2 | 旧账本未记录该NCT的分析/排除位置；新增查询1组；记录的上级病名：Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| bf8ce4b60db68bd7 | PRAC-COL1A1 / MONDO:0020521 | Heart Coherence Training on Vascular Ehlers-Danlos Syndrome Patients (NCT05994664) / [registry](https://clinicaltrials.gov/study/NCT05994664) | not_applicable | 2 | 旧账本未记录该NCT的分析/排除位置；新增查询2组；记录的上级病名：Ehlers-Danlos syndrome, arthrochalasia type / Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 94b1b4b4ec5252e3 | PRAC-COL1A1 / MONDO:0007522 | STABLE (NCT07464093) / [registry](https://clinicaltrials.gov/study/NCT07464093) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询1组；记录的上级病名：Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| aaac922edb7939c4 | PRAC-COL1A1 / MONDO:0020521 | STABLE (NCT07464093) / [registry](https://clinicaltrials.gov/study/NCT07464093) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询2组；记录的上级病名：Ehlers-Danlos syndrome, arthrochalasia type / Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 5418bb286fdd626e | PRAC-COL1A1 / MONDO:0007522 | Hamstring Strengthening in Hypermobile Conditions (NCT07626957) / [registry](https://clinicaltrials.gov/study/NCT07626957) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询1组；记录的上级病名：Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| aa97082b85bf9e8d | PRAC-COL1A1 / MONDO:0020521 | Hamstring Strengthening in Hypermobile Conditions (NCT07626957) / [registry](https://clinicaltrials.gov/study/NCT07626957) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询2组；记录的上级病名：Ehlers-Danlos syndrome, arthrochalasia type / Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 2c8d3e77f2a9afb6 | PRAC-COL1A1 / MONDO:0007522 | Regenerative Medicine for Joint Hypermobility and Instability (NCT07688096) / [registry](https://clinicaltrials.gov/study/NCT07688096) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询1组；记录的上级病名：Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 3da15aa21853328e | PRAC-COL1A1 / MONDO:0020521 | Regenerative Medicine for Joint Hypermobility and Instability (NCT07688096) / [registry](https://clinicaltrials.gov/study/NCT07688096) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询2组；记录的上级病名：Ehlers-Danlos syndrome, arthrochalasia type / Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 92f28a4b98d92299 | PRAC-COL1A1 / MONDO:0007522 | An Exercise and Lifestyle Programme for Adults With Vascular Ehlers-Danlos Syndrome: A Feasibility Study (NCT07697573) / [registry](https://clinicaltrials.gov/study/NCT07697573) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询1组；记录的上级病名：Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 7c563c13e877e940 | PRAC-COL1A1 / MONDO:0020521 | An Exercise and Lifestyle Programme for Adults With Vascular Ehlers-Danlos Syndrome: A Feasibility Study (NCT07697573) / [registry](https://clinicaltrials.gov/study/NCT07697573) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询2组；记录的上级病名：Ehlers-Danlos syndrome, arthrochalasia type / Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 89723a43cd5ac6c2 | PRAC-COL1A1 / MONDO:0007522 | CogSCC (NCT07743229) / [registry](https://clinicaltrials.gov/study/NCT07743229) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询1组；记录的上级病名：Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |
| 98e5e208b6636288 | PRAC-COL1A1 / MONDO:0020521 | CogSCC (NCT07743229) / [registry](https://clinicaltrials.gov/study/NCT07743229) | conditional | 0 | 旧账本未记录该NCT的分析/排除位置；新增查询2组；记录的上级病名：Ehlers-Danlos syndrome, arthrochalasia type / Ehlers-Danlos syndrome；新增召回/分析范围原因仍待逐项确认，查询全文与旧位置细节见JSON。 |

## 155项完整待批准行

| Change ID | 来源组 | Case | Action | Branch | Old → New |
| --- | --- | --- | --- | --- | --- |
| 5366172274fb5d99 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-ANO10 | None found | MONDO:0013392 | None → searched_none |
| fb5f514f2b8c4a61 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | Online Study of People Who Have Genetic Changes and Features of Autism: Simons Searchlight (NCT01238250) | MONDO:0013509 | None → conditional |
| ab1c286cf990ed01 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | Open-label, Single-arm Trial of Ganaxolone in CDD Patients 6 Months to Less Than 2 Years Old (NCT05249556) | MONDO:0014505 | None → not_applicable |
| 69f765836a08cb7a | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | ENDEAVOR (NCT05419492) | MONDO:0014505 | None → not_applicable |
| 72753fc03f6bd8f5 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | A Natural History Study Seeks to Understand the Clinical, Genomic, Pharmacological, Laboratory, and Dietary Determinates of Pyrimidine and Purine Metabolism Disorders (NCT06092346) | MONDO:0014505 | None → conditional |
| d785606a4ce5a37a | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | DEE-RETRO (NCT06380192) | MONDO:0014505 | None → conditional |
| b6d21abd46546d61 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | Beeline: A Phase 3 Study in GRIN-related Neurodevelopmental Disorder (NCT07224581) | MONDO:0013509 | None → conditional |
| 2623a3e4820f4c5d | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | Beeline: A Phase 3 Study in GRIN-related Neurodevelopmental Disorder (NCT07224581) | MONDO:0014505 | None → conditional |
| bd7adcabeab04295 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | TAP-GRIN: Interventional Study on Patients With GRIN-related Neurodevelopmental Disorders (NCT07377032) | MONDO:0013509 | None → conditional |
| 555f420a79938136 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | TAP-GRIN: Interventional Study on Patients With GRIN-related Neurodevelopmental Disorders (NCT07377032) | MONDO:0014505 | None → conditional |
| c167289982634d9d | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | A Study to Evaluate the Safety and Pharmacokinetics of RC001 in Children With Dravet Syndrome (NCT07675746) | MONDO:0014505 | None → not_applicable |
| 0dfbb4da4bd16873 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | A Study to Evaluate the Safety and Efficacy of CBD-OS in Participants With DEE (NCT07723976) | MONDO:0014505 | None → conditional |
| 67588e4672dd8fc7 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | A Fully Remote Feasibility Trial of Phenylbutyrate for SLC6A1-Related Disorders (NCT07847918) | MONDO:0014505 | None → not_applicable |
| 99b7dc1c2fd82246 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | IMPACT-Ready Study (NCT07931690) | MONDO:0013509 | None → conditional |
| 7bfe4c5d69ff210d | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-GRIN2B | IMPACT-Ready Study (NCT07931690) | MONDO:0014505 | None → conditional |
| c2afd8103740bb83 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-NF1 | Cyclin-Dependent Kinase (CDK)4/6 Inhibitor Abemaciclib for Neurofibromatosis Type I (NF1) Related Atypical Neurofibromas (NCT04750928) | MONDO:0018975 | None → conditional |
| 85a8c8880e7c5893 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-NF1 | Identification of Pre-Malignant Lesions In Pediatric Patients With Neurofibromatosis Type 1 Using Novel Magnetic Resonance Imaging Techniques Paired With Artificial Intelligence (NCT04763109) | MONDO:0018975 | None → conditional |
| bb9d4b67ffe375b9 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-NF1 | A Study to Evaluate the Feasibility of a Physiologic Biomarker to Assess Pain and Other Sensory Problems Using Pupillometry in Participants With Neurofibromatosis Type 1 (NF1) (NCT06507748) | MONDO:0018975 | None → conditional |
| fb54e8e297dec108 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-NF1 | INSPIRE-NF1 (NCT06541847) | MONDO:0018975 | None → conditional |
| db01af6b5f60b43b | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-NF1 | Clinical Study on the Treatment of Type I Neurofibromatosis With Smeitinib Hydrosulfate Capsule (NCT06620354) | MONDO:0018975 | None → conditional |
| 50b65292b8a41a89 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-NF1 | The Clinical Study of the Treatment of Patients With Type I Neurofibromatosis With Smetinib Hydrosulfate Capsule (NCT06621082) | MONDO:0018975 | None → conditional |
| 4c347f656c33ba0f | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-NF1 | iCanCope With NF: Innovating an Efficacious Digital Self-management and Transitional Care Program for Adolescents With Neurofibromatosis (NCT07077408) | MONDO:0018975 | None → conditional |
| ec11d579e5b1220b | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-NF1 | Tailoring an Online Platform to Promote Evidence-Based Care for Adults With Neurofibromatosis 1 and Low Health Literacy (NCT07233408) | MONDO:0018975 | None → conditional |
| 4f9690c07e0d2963 | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-NF1 | NF118 (NCT07521657) | MONDO:0018975 | None → conditional |
| 9d70be6b001119fd | E 同类：历史该病例 3b 明确 not_searched 后首次纳入 | PRAC-NF1 | A Study of Mirdametinib in Infants and Toddlers With Neurofibromatosis Type 1 Associated Plexiform Neurofibromas (NCT07850635) | MONDO:0018975 | None → conditional |
| 993a1d48e8bcb3ca | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | None found | MONDO:0013392 | None → searched_none |
| f304cd04284e5f38 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | None found | MONDO:0013392 | None → searched_none |
| 741e6cd68df0a8a2 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | modify food consistency | MONDO:0013392 | None → conditional |
| 3c241c8d1d313c77 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | nutritional & vitamin supplementation | MONDO:0013392 | None → conditional |
| b8e2158c3aef61dd | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | weight control | MONDO:0013392 | None → applicable |
| 413628fef93061d0 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | baclofen | MONDO:0013392 | None → conditional |
| c80f380c6ebd7b05 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | dantrolene | MONDO:0013392 | None → conditional |
| 3cd3fffb0c9e9d2f | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | riluzole | MONDO:0013392 | None → conditional |
| ebc212b83b835fb5 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | tizanidine | MONDO:0013392 | None → conditional |
| 6790dfb19a9814a2 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | surgical treatment | MONDO:0013392 | None → conditional |
| eedb60394f742f36 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | transcranial magnetic stimulation | MONDO:0013392 | None → applicable |
| bcfabfe63238734a | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | adaptive devices | MONDO:0013392 | None → applicable |
| 9f3c3e8dbce28b8d | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | alternative communication methods | MONDO:0013392 | None → conditional |
| 5c00b4ab998838cc | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | home adaptations | MONDO:0013392 | None → applicable |
| a584e0c1675c0301 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | occupational therapy | MONDO:0013392 | None → applicable |
| f821e921c1f5734f | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | physical therapy | MONDO:0013392 | None → applicable |
| 99e09baf5e1c2371 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-ANO10 | speech-language therapy | MONDO:0013392 | None → conditional |
| ffe2ba2244db3a29 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | None found | MONDO:0013509 | None → searched_none |
| fb50fc0cd49ecec0 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | None found | MONDO:0014505 | None → searched_none |
| bf0334a99a75e697 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | None found | MONDO:0013509 | None → searched_none |
| ea6dda13d716191a | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | None found | MONDO:0014505 | None → searched_none |
| dbd0cb993a74fccd | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | anti-seizure medication | MONDO:0013509 | None → applicable |
| 69c7de54bb33e0cc | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | anti-seizure medication | MONDO:0014505 | None → applicable |
| 88d0668b6a3813d5 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | durable medical equipment | MONDO:0013509 | None → conditional |
| baabf2ab318695d6 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | durable medical equipment | MONDO:0014505 | None → conditional |
| 2635a30b136c7d3c | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | early intervention program | MONDO:0013509 | None → conditional |
| d72488209163b587 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | early intervention program | MONDO:0014505 | None → conditional |
| ad59523409cd808f | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | feeding therapy | MONDO:0013509 | None → conditional |
| 79247702c43edc4d | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | feeding therapy | MONDO:0014505 | None → conditional |
| 5c3c93f73e2f96bf | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | occupational therapy | MONDO:0013509 | None → conditional |
| f57460b7f26f68ce | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | occupational therapy | MONDO:0014505 | None → conditional |
| 7d2158b682c6a1fa | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | developmental preschool | MONDO:0013509 | None → conditional |
| 54251b778463a852 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | developmental preschool | MONDO:0014505 | None → conditional |
| fccfed56b947196e | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | physical therapy | MONDO:0013509 | None → conditional |
| d5bd339bb981894f | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | physical therapy | MONDO:0014505 | None → conditional |
| cd039f7d0437512b | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | speech therapy | MONDO:0013509 | None → conditional |
| 2d68cd8cb9a86f78 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-GRIN2B | speech therapy | MONDO:0014505 | None → conditional |
| e56bf587616b6709 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | radiotherapy | MONDO:0018975 | None → conditional |
| a709a06cf63b1142 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | selumetinib | MONDO:0018975 | None → conditional |
| 34a4968d17e10172 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | mirdametinib | MONDO:0018975 | None → conditional |
| 874f37ff6cf1395d | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | bisphosphonate | MONDO:0018975 | None → conditional |
| e4a912206887a17a | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | MEK inhibitors | MONDO:0018975 | None → conditional |
| ba80f012d61b1e8c | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | Vitamin D | MONDO:0018975 | None → conditional |
| df23f7ad2f7858b5 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | calcium | MONDO:0018975 | None → conditional |
| 2be2e67dccc007c5 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | methylphenidate | MONDO:0018975 | None → conditional |
| fefc4854eb3a5eb0 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | complete surgical excision | MONDO:0018975 | None → conditional |
| 178e5011df1cda51 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | electrocautery | MONDO:0018975 | None → conditional |
| 70c1ab8f3b30bb1c | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | laser | MONDO:0018975 | None → conditional |
| f939f91a079e375f | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | radiotherapy | MONDO:0018975 | None → conditional |
| e4180c92ac9e19ef | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | surgical management | MONDO:0018975 | None → conditional |
| 292ff90857b6382f | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-NF1 | surgical removal | MONDO:0018975 | None → conditional |
| 8baf57c221a9d2ee | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-SLC35A2-ex7 | preschool education services in the least restrictive environment | MONDO:0010478 | None → applicable |
| 2cfd3b3cf1584e2c | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-SLC35A2-ex7 | start early intervention as soon as the delay is recognized | MONDO:0010478 | None → applicable |
| 800fa316a313d3b2 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-SLC35A2-ex7 | multidisciplinary developmental intervention team (developmental paediatrics or paediatric neurology, clinical psychology, occupational therapy, physiotherapy, special education, speech therapy) | MONDO:0010478 | None → applicable |
| 477249fa33a5b3a0 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-SLC35A2-ex8 | preschool education services in the least restrictive environment | MONDO:0010478 | None → applicable |
| 9f3242ec879c5623 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-SLC35A2-ex8 | start early intervention as soon as the delay is recognized | MONDO:0010478 | None → applicable |
| 53e356384cb67118 | 3a 来源 / 回退链新增（章节、综述、指南及阴性检索） | PRAC-SLC35A2-ex8 | multidisciplinary developmental intervention team (developmental paediatrics or paediatric neurology, clinical psychology, occupational therapy, physiotherapy, special education, speech therapy) | MONDO:0010478 | None → applicable |
| b9b61ff384279f3d | 已批准通用 Pregnancy Management 附注规则 | PRAC-AGXT-c33dup | adequate fluid intake | MONDO:0009823 | not_applicable → None |
| c3b5002b476ca207 | 已批准通用 Pregnancy Management 附注规则 | PRAC-AGXT-c33dup | intravenous fluid administration | MONDO:0009823 | not_applicable → None |
| 379fb54b5f5855a3 | 已批准通用 Pregnancy Management 附注规则 | PRAC-AGXT-c508GA | adequate fluid intake | MONDO:0009823 | conditional → None |
| f2c4d9d476851489 | 已批准通用 Pregnancy Management 附注规则 | PRAC-AGXT-c508GA | intravenous fluid administration | MONDO:0009823 | conditional → None |
| 080488172d59fc57 | 已批准通用 Pregnancy Management 附注规则 | PRAC-CFTR-F508del | fat-soluble vitamin A supplementation | MONDO:0009061 | not_applicable → None |
| 535195420e5579dc | 已批准通用 Pregnancy Management 附注规则 | PRAC-CFTR-F508del | folate supplementation | MONDO:0009061 | not_applicable → None |
| 7c2089d4166fd1bc | 已批准通用 Pregnancy Management 附注规则 | PRAC-CFTR-F508del | iron supplementation | MONDO:0009061 | not_applicable → None |
| 8d3ff0b246f0f547 | 已批准通用 Pregnancy Management 附注规则 | PRAC-CFTR-F508del | insulin | MONDO:0009061 | not_applicable → None |
| 4ed873fe2f88eb6a | 已批准通用 Pregnancy Management 附注规则 | PRAC-CFTR-F508del | airway clearance practices | MONDO:0009061 | not_applicable → None |
| 06f8f5c4ed2cbd8d | 已批准通用 Pregnancy Management 附注规则 | PRAC-COL1A1 | tranexamic acid | MONDO:0007522 | conditional → None |
| b0f4073d93f7bc12 | 已批准通用 Pregnancy Management 附注规则 | PRAC-COL1A1 | oxytocin | MONDO:0007522 | conditional → None |
| a30c08add1998ca3 | 已批准通用 Pregnancy Management 附注规则 | PRAC-COL1A1 | cesarean section | MONDO:0030854 | conditional → None |
| f1630a07822caef4 | 已批准通用 Pregnancy Management 附注规则 | PRAC-COL1A1 | episiotomy | MONDO:0007522 | conditional → None |
| 14cee1c876dcda7b | 已批准通用 Pregnancy Management 附注规则 | PRAC-OTC | intact versus essential amino acid supplementation | MONDO:0010703 | not_applicable → None |
| cb4406e5168da2c1 | 已批准通用 Pregnancy Management 附注规则 | PRAC-OTC | lipid emulsion | MONDO:0010703 | not_applicable → None |
| 723e5776ffadd48b | 已批准通用 Pregnancy Management 附注规则 | PRAC-OTC | dextrose | MONDO:0010703 | not_applicable → None |
| fb886e84217df4db | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | Rare Kidney Stone Consortium Biobank (NCT02026388) | MONDO:0009823 | conditional → conditional |
| 38693a830a5a47e6 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | PHYOX7 (NCT04580420) | MONDO:0009823 | conditional → conditional |
| ee33b34ac26af907 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | DAILY-LUMA (NCT06225882) | MONDO:0009823 | conditional → conditional |
| 4a4b2a4746dba8ac | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | CRYSTAL (NCT06465472) | MONDO:0009823 | conditional → conditional |
| 0e2746a0dc08ac99 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | Clinical Exploration Study of YOLT-203 in the Treatment of Type 1 Primary Hyperoxaluria (PH1) (NCT06511349) | MONDO:0009823 | conditional → conditional |
| d29f7c2807172323 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | Phase 1/2 Study of ABO-101 in Primary Hyperoxaluria Type 1 (redePHine) (NCT06839235) | MONDO:0009823 | conditional → conditional |
| 289a9badd2787599 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | Study of YOLT-203 in Children and Adults With Primary Hyperoxaluria Type 1 (PH1) (NCT07587021) | MONDO:0009823 | conditional → conditional |
| b04275addd9dba51 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | Phase I Exploratory Study of YOLT-203 in Patients With Primary Hyperoxaluria Type 1 (PH1) (NCT07776626) | MONDO:0009823 | conditional → conditional |
| 2a364f88dffb552c | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | liver transplant | MONDO:0009823 | conditional → conditional |
| 52ab9adfea7572f4 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | pyrophosphate-containing solutions | MONDO:0009823 | conditional → conditional |
| 35082c7626cdff51 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | potassium citrate | MONDO:0009823 | conditional → conditional |
| aee81bde01f5f829 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | sodium citrate | MONDO:0009823 | conditional → conditional |
| 0c620cf2dba8e5aa | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | dialysis | MONDO:0009823 | conditional → conditional |
| 697ea6089588ecad | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c33dup | shockwave lithotripsy | MONDO:0009823 | conditional → conditional |
| 3d0d87e9b5d0229f | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | Rare Kidney Stone Consortium Biobank (NCT02026388) | MONDO:0009823 | conditional → conditional |
| c2486eb39a7d74b5 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | PHYOX7 (NCT04580420) | MONDO:0009823 | conditional → conditional |
| 19cb2e0f459f3093 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | DAILY-LUMA (NCT06225882) | MONDO:0009823 | conditional → conditional |
| 13faa77e7f4dbf83 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | CRYSTAL (NCT06465472) | MONDO:0009823 | conditional → conditional |
| 539461a5f1af4161 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | Clinical Exploration Study of YOLT-203 in the Treatment of Type 1 Primary Hyperoxaluria (PH1) (NCT06511349) | MONDO:0009823 | conditional → conditional |
| f3dfcb4982c90071 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | Phase 1/2 Study of ABO-101 in Primary Hyperoxaluria Type 1 (redePHine) (NCT06839235) | MONDO:0009823 | conditional → conditional |
| a01f90935389d51f | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | Study of YOLT-203 in Children and Adults With Primary Hyperoxaluria Type 1 (PH1) (NCT07587021) | MONDO:0009823 | conditional → conditional |
| c999298f25c8b522 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | Phase I Exploratory Study of YOLT-203 in Patients With Primary Hyperoxaluria Type 1 (PH1) (NCT07776626) | MONDO:0009823 | conditional → conditional |
| e32309a713e05687 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | liver transplant | MONDO:0009823 | conditional → conditional |
| 3d997ed0b97c2574 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | pyrophosphate-containing solutions | MONDO:0009823 | conditional → conditional |
| c19c73d85ec24b6c | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | potassium citrate | MONDO:0009823 | conditional → conditional |
| 6f62538c379b752f | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | sodium citrate | MONDO:0009823 | conditional → conditional |
| 965ef34399a142b5 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | dialysis | MONDO:0009823 | conditional → conditional |
| 28b89e630cb11892 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-AGXT-c508GA | shockwave lithotripsy | MONDO:0009823 | conditional → conditional |
| 7d4b78e893b47b4a | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | Personalized Theratyping Trial (NCT03587961) | MONDO:0009061 | conditional → conditional |
| 95edd1d01f982efd | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | STOP360AG (NCT05548283) | MONDO:0009061 | conditional → conditional |
| 466187fdd481fe4f | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | Regional Monitoring of CF Lung Disease (NCT06339593) | MONDO:0009061 | conditional → conditional |
| 3303e97b1554a5c3 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | Targeting Inflammation With Losartan to Improve Response to Modulator Therapy in Cystic Fibrosis. (NCT06364176) | MONDO:0009061 | conditional → conditional |
| 5b0a73880315306f | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | ENACT (NCT07148739) | MONDO:0009061 | conditional → conditional |
| edd8f510fc683334 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | Safety and Efficacy of Inhaled BMD003 (CFTR mRNA) in Chinese Cystic Fibrosis Patients Aged ≥12 Years (NCT07485543) | MONDO:0009061 | conditional → conditional |
| 00078e7d0ef091a7 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | Pharmacokinetics of Elexacaftor/Tezacaftor/Ivacaftor in Cystic Fibrosis (NCT07809867) | MONDO:0009061 | conditional → conditional |
| 75642a1239a8a79f | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | Diagnostic Value of Oropharyngeal Suction and Effect of Respiratory Physiotherapy on the Detection of Microorganisms in the Pediatric Patient (NCT07903792) | MONDO:0009061 | conditional → conditional |
| 1456a0d4188418f8 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | aerosolized antibiotic | MONDO:0009061 | conditional → conditional |
| fe7a05cb63ae5b8e | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | bronchodilator | MONDO:0009061 | conditional → conditional |
| c984456d181d80c0 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | Gonadotropin ovulation induction | MONDO:0009061 | not_applicable → not_applicable |
| eca8410a75cd7246 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | laxative treatment | MONDO:0009061 | conditional → conditional |
| c282e26f69a28b16 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | airway clearance | MONDO:0009061 | conditional → conditional |
| 709dbdd505b3f7d8 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | Intrauterine insemination | MONDO:0009061 | not_applicable → not_applicable |
| f5a9b68f5f9296cd | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | IVF | MONDO:0009061 | not_applicable → not_applicable |
| 4a11c962f2f88402 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-CFTR-F508del | surgical intervention for nasal/sinus symptoms | MONDO:0009061 | conditional → conditional |
| c7041a954c71ca40 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-COL1A1 | Preliminary Evaluation of the Safety and Tolerability of SPOT-mRNA01 Subcutaneously Administered in Healthy Subjects (NCT06567119) | MONDO:0007522 | conditional → conditional |
| 03f93b0cf0af7f4c | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-COL1A1 | Preliminary Evaluation of the Safety and Tolerability of SPOT-mRNA01 Subcutaneously Administered in Healthy Subjects (NCT06567119) | MONDO:0020521 | conditional → conditional |
| 173d203ec1b7db32 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-COL1A1 | Preliminary Evaluation of the Safety and Tolerability of SPOT-mRNA01 Subcutaneously Administered in Healthy Subjects (NCT06567119) | MONDO:0030854 | conditional → conditional |
| 40c02dad1d652594 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-COL1A1 | VILLAREALFC (NCT07653633) | MONDO:0030854 | conditional → conditional |
| 77eb4735695ad72d | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-COL1A1 | alternating positions | MONDO:0030854 | conditional → conditional |
| 47786087bd16f68c | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-COL1A1 | occupational therapy | MONDO:0030854 | conditional → conditional |
| 087ce957dffa8276 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-KMT2B | None found | MONDO:0015004 | searched_none → searched_none |
| 9ba015865d5289a8 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-OTC | low-protein diet | MONDO:0010703 | conditional → conditional |
| 98d38d2d0f999e48 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-OTC | CKRT | MONDO:0010703 | conditional → conditional |
| a1b8fae9420dfc18 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-OTC | CVVHD | MONDO:0010703 | conditional → conditional |
| 0e13577b063def49 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-OTC | high-dose CKRT | MONDO:0010703 | conditional → conditional |
| 4ad249d6912da64e | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-OTC | intermittent HD | MONDO:0010703 | conditional → conditional |
| 05a3bdef1e6ec124 | 已批准修复后的证据内容 / 条款 / 集合变化，非 ID 算法变化 | PRAC-OTC | renal replacement therapy | MONDO:0010703 | conditional → conditional |

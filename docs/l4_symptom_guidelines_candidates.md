# L4 对症指南：候选清单（第 2 版，待审，未写入配置）

> 2026-11-04 整理。选源优先级（审阅决定）：① 国际学会（ILAE 等）→ ② 美国学会（AAP、AAN、AES 等）→ ③ 其他国家机构（NICE、IAP 等），
> 只有前两级确实没有可用的管理 / 干预类指南时才用第 ③ 级，并写明理由。支持治疗不含监测 / 筛查。
> 每条拟用段落都逐字核对过原文；**未核实的不写进 `config/symptom_guidelines.json`**。
> 自动抓取被拒（403 / 人机验证）的来源：只用人工在浏览器打开的公开页面核对，不绕过任何验证；核对过的段落、日期、网址存 `.cache/guidelines/`（不进仓库）。

## 癫痫

| 级别 | 指南 | 出处 | 拟用段落（逐字） | 核实 |
| --- | --- | --- | --- | --- |
| ① ILAE | ILAE 2023 新生儿癫痫发作抗癫痫药建议（Pressler et al., *Epilepsia* 2023） | UCL 存档开放获取 PDF | 只适用于新生儿；待选段落 | ⏳ 未逐字核对；只在病人为新生儿时适用 |
| ② AES | Evidence-based guideline: treatment of convulsive status epilepticus in children and adults（Glauser et al., *Epilepsy Curr* 2016;16(1):48–61；PMC4749120；DOI 10.5698/1535-7597-16.1.48；AES 发布，儿童神经病学会等认可） | https://pmc.ncbi.nlm.nih.gov/articles/PMC4749120/ | 摘要："In children, intravenous lorazepam and intravenous diazepam …"（儿童一线用药，Level A）| ✅ 经 NCBI E-utilities（efetch）取得摘要逐字核对；PMC 全文未经官方接口提供，只用摘要 |
| ② AAN/AES | Practice guideline update summary: Efficacy and tolerability of the new antiepileptic drugs I: Treatment of new-onset epilepsy（Kanner et al., *Neurology* 2018；DOI 10.1212/WNL.0000000000005755） | AAN 指南页 | 新发癫痫的药物选择推荐（如儿童失神癫痫 ethosuximide / valproic acid 先于 lamotrigine，Level B） | ⏳ 未逐字核对（仅二手摘要）；需确认 AAN 是否已复审或撤回（发布已 8 年） |
| ③ NICE | NG217 Epilepsies in children, young people and adults（2022-04-27 发布，2026-08-05 更新） | https://www.nice.org.uk/guidance/ng217 | 4.1.1 "Develop an individualised antiseizure medication treatment strategy …" | ✅ 已核对；**按优先级降为备选**：①② 没有覆盖"个体化治疗方案、转诊专科"这类一般管理条目时才用，理由须写进配置 |

**结论（待审）**：慢性癫痫的一般管理（个体化用药方案、转诊）在 ①② 级没有找到对应的现行管理指南：ILAE 只有新生儿专项，AES 是癫痫持续状态，AAN 是药物选择。建议：癫痫持续状态 / 急救用 AES 2016；一般管理用 NICE NG217 并写明上述理由。AAN 2018 核实现行状态后再决定。

## 发育迟缓 / 智力障碍

| 级别 | 指南 | 出处 | 拟用段落 | 核实 |
| --- | --- | --- | --- | --- |
| ① 国际 | 未找到国际学会的发育迟缓 / 智力障碍**干预或管理**指南（找到的国际文件多为病因评估） | — | — | — |
| ② AAP | Early Intervention, IDEA Part C Services, and the Medical Home: Collaboration for Best Practice and Best Outcomes（Adams RC, Tapia C, AAP Council on Children with Disabilities, *Pediatrics* 2013;132(4):e1073–e1088） | publications.aap.org | 0–3 岁转介早期干预（IDEA Part C）、家庭为中心的服务 | ⏳ 出版商页面有 Cloudflare 人机验证，未绕过；待 NCBI 检索恢复后用 PubMed 摘要核对；需确认是否经 AAP 复审（二手资料称 2017 复审） |
| ② AAP | Comprehensive Evaluation of the Child With ID or GDD（2014）、Genetic Evaluation …（2025） | — | — | ✗ 评估 / 遗传检测类，不是干预，不用 |
| ③ IAP | Diagnosis and Management of Global Development Delay（印度儿科学会三分会共识，Juneja M et al., *Indian Pediatr* 2022 在线优先） | https://indianpediatrics.net/epub022022/RECOMM-00406.pdf | 5D "Early intervention should be initiated soon after the delay is recognized, instead of waiting for a formal diagnosis."；多学科团队（作业治疗、物理治疗、言语治疗）原文 | ✅ PDF 原文逐字核对（存 `.cache/guidelines/`）；**备选**：AAP 2013 核实不了时才用 |

**结论（待审）**：首选 AAP 2013（核实后），覆盖 0–3 岁早期干预；3 岁以上的康复治疗（PT / OT / 言语）推荐 AAP 2013 未覆盖时，用 IAP 2022 并写明理由。

## 喂养困难

| 级别 | 指南 | 出处 | 拟用段落（逐字，已核对） |
| --- | --- | --- | --- |
| ① ESPGHAN（欧洲儿科胃肠肝病营养学会，国际学会） | ESPGHAN Guidelines for the Evaluation and Treatment of Gastrointestinal and Nutritional Complications in Children With Neurological Impairment（Romano C et al., *JPGN* 2017;65(2):242–264；DOI 10.1097/MPG.0000000000001646） | UCL Discovery 作者接受稿（开放获取），存 `.cache/guidelines/espghan2017/` | 1 "nutritional evaluation and management should be performed by a multidisciplinary team …"；11 "considering speech and language interventions in the treatment of NI children with oropharyngeal dysfunction …"；20 "considering use of enteral feeding if total oral feeding time exceeds 3 hours per day"；23 "using a gastrostomy as the preferred way to provide intragastric access for long term tube feeding in NI children"；25 "using enteral tube feeding in cases of unsafe or inefficient oral feeding, preferably before the development of undernutrition" |

核实：✅ 接受稿 PDF 逐字核对（正式出版版与接受稿可能有措辞差异；配置中注明"accepted manuscript"）。

## 待你决定

1. 癫痫一般管理用 NICE NG217（理由：①② 级无对应现行指南），是否同意。
2. AAN 2018 是否纳入（需先确认现行状态）。
3. 发育迟缓：AAP 2013 待 PubMed 摘要核实；3 岁以上康复推荐是否用 IAP 2022 补充。

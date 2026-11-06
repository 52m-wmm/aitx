# L4 对症指南：候选清单（第 3 版，待审，未写入配置）

> 2026-11-04 整理。选源优先级（审阅决定）：① 国际学会（ILAE 等）→ ② 美国学会（AAP、AAN、AES 等）→ ③ 其他国家机构（NICE、IAP 等），
> 只有前两级确实没有可用的管理 / 干预类指南时才用第 ③ 级，并写明理由。支持治疗不含监测 / 筛查。
> 每条拟用段落都逐字核对过原文；**未核实的不写进 `config/symptom_guidelines.json`**。
> 自动抓取被拒（403 / 人机验证）的来源：只用人工在浏览器打开的公开页面核对，不绕过任何验证；核对过的段落、日期、网址存 `.cache/guidelines/`（不进仓库）。

## 癫痫

| 级别 | 指南 | 出处 | 拟用段落（逐字） | 核实 |
| --- | --- | --- | --- | --- |
| ① ILAE | ILAE 2023 新生儿癫痫发作抗癫痫药建议（Pressler et al., *Epilepsia* 2023） | UCL 存档开放获取 PDF | 只适用于新生儿；待选段落 | ⏳ 未逐字核对；只在病人为新生儿时适用 |
| ② AES | Evidence-based guideline: treatment of convulsive status epilepticus in children and adults（Glauser et al., *Epilepsy Curr* 2016;16(1):48–61；PMC4749120；DOI 10.5698/1535-7597-16.1.48；AES 发布，儿童神经病学会等认可） | https://pmc.ncbi.nlm.nih.gov/articles/PMC4749120/ | 摘要："In children, intravenous lorazepam and intravenous diazepam …"（儿童一线用药，Level A）| ✅ 经 NCBI E-utilities（efetch）取得摘要逐字核对；PMC 全文未经官方接口提供，只用摘要 |
| ② AAN/AES | Practice guideline update summary: Efficacy and tolerability of the new antiepileptic drugs I: Treatment of new-onset epilepsy（Kanner et al., *Neurology* 2018；PMC6145382；DOI 10.1212/WNL.0000000000005755） | https://www.aan.com/Guidelines/home/GuidelineDetail/915 | 摘要："Unless there are compelling adverse-effect–related concerns, ethosuximide (ETS) or valproic acid (VPA) should be considered before LTG to decrease seizure frequency in treating absence seizures in childhood absence epilepsy (Level B)." | ✅ 现行状态已在 AAN 官网核对（"Reaffirmed on October 19, 2024."，浏览器打开公开页面，2026-11-05）；摘要经 E-utilities efetch 逐字核对，存 `.cache/guidelines/aan2018/` |
| ③ NICE | NG217 Epilepsies in children, young people and adults（2022-04-27 发布，2026-08-05 更新） | https://www.nice.org.uk/guidance/ng217 | 4.1.1 "Develop an individualised antiseizure medication treatment strategy …" | ✅ 已核对；**按优先级降为备选**：①② 没有覆盖"个体化治疗方案、转诊专科"这类一般管理条目时才用，理由须写进配置 |

**结论（待审）**：
- 癫痫持续状态 / 急救：AES 2016（②）。
- 新发癫痫的药物选择：AAN/AES 2018（②，2024 年复审确认）。只在药物推荐对应病人的发作类型时使用（如儿童失神癫痫），否则不写。
- 一般管理（个体化治疗方案、转诊专科）：①② 级仍未找到现行指南（2026-11-05 复查：ILAE 只有新生儿、婴儿痉挛、精神共病等专项；AES 2025 婴儿癫痫指南还在公开征求意见阶段，未定稿），所以用 NICE NG217（③），理由写进配置。

## 发育迟缓 / 智力障碍

| 级别 | 指南 | 出处 | 拟用段落 | 核实 |
| --- | --- | --- | --- | --- |
| ① 国际 | 未找到国际学会的发育迟缓 / 智力障碍**干预或管理**指南（找到的国际文件多为病因评估） | — | — | — |
| ② AAP | Early Intervention, IDEA Part C Services, and the Medical Home: Collaboration for Best Practice and Best Outcomes（Adams RC, Tapia C, AAP Council on Children with Disabilities, *Pediatrics* 2013;132(4):e1073–e1088） | publications.aap.org | 0–3 岁转介早期干预（IDEA Part C）、家庭为中心的服务 | 🔶 2026-11-05 经 E-utilities 核对：PMID 24082001，*Pediatrics* 2013;132(4):e1073-88，DOI 10.1542/peds.2013-2305，PubMed 文献类型 Journal Article + Review（AAP 临床报告，不是正式指南）。摘要逐字核对，存 `.cache/guidelines/aap2013/`；摘要里没有直接的推荐句，最接近的是 "Economic, health, and family-focused data each underscore the critical role of timely referral for relationship-based, individualized, accessible early intervention services"。**复审状态无法用 E-utilities 核实**：PubMed 收录的 16 条 "AAP Publications Reaffirmed / Retired" 通知（2017–2023）都没有摘要，看不到列了哪些文件；PubMed 记录本身也没有勘误或复审链接 |
| ② AAP | Comprehensive Evaluation of the Child With ID or GDD（2014）、Genetic Evaluation …（2025） | — | — | ✗ 评估 / 遗传检测类，不是干预，不用 |
| ③ IAP | Diagnosis and Management of Global Development Delay（印度儿科学会三分会共识，Juneja M et al., *Indian Pediatr* 2022 在线优先） | https://indianpediatrics.net/epub022022/RECOMM-00406.pdf | 5D "Early intervention should be initiated soon after the delay is recognized, instead of waiting for a formal diagnosis."；多学科团队（作业治疗、物理治疗、言语治疗）原文 | ✅ PDF 原文逐字核对（存 `.cache/guidelines/`）；**备选**：AAP 2013 核实不了时才用 |

**结论（待审，2026-11-05 更新）**：AAP 2013 的摘要已核实，但①摘要没有直接推荐句，②复审状态无法核实（E-utilities 范围内）。可选：
(a) 用摘要那句"及时转介早期干预服务"作为 0–3 岁的依据，配置里注明"临床报告，复审状态未核实"；
(b) 不用 AAP 2013，改用已逐字核对的 IAP 2022 第 5D 条（第 ③ 级，理由：②级唯一候选的现行状态无法核实）；
(c) 发育迟缓类别继续停用。建议 (b)：它有明确的推荐句，原文已核对。

## 喂养困难

| 级别 | 指南 | 出处 | 拟用段落（逐字，已核对） |
| --- | --- | --- | --- |
| ① ESPGHAN（欧洲儿科胃肠肝病营养学会，国际学会） | ESPGHAN Guidelines for the Evaluation and Treatment of Gastrointestinal and Nutritional Complications in Children With Neurological Impairment（Romano C et al., *JPGN* 2017;65(2):242–264；DOI 10.1097/MPG.0000000000001646） | UCL Discovery 作者接受稿（开放获取），存 `.cache/guidelines/espghan2017/` | 1 "nutritional evaluation and management should be performed by a multidisciplinary team …"；11 "considering speech and language interventions in the treatment of NI children with oropharyngeal dysfunction …"；20 "considering use of enteral feeding if total oral feeding time exceeds 3 hours per day"；23 "using a gastrostomy as the preferred way to provide intragastric access for long term tube feeding in NI children"；25 "using enteral tube feeding in cases of unsafe or inefficient oral feeding, preferably before the development of undernutrition" |

核实：✅ 接受稿 PDF 逐字核对（正式出版版与接受稿可能有措辞差异；配置中注明"accepted manuscript"）。

## 待你决定

1. 癫痫一般管理用 NICE NG217（理由：①② 级无对应现行指南），是否同意。
2. AAN/AES 2018：现行状态已确认（2024 年复审），是否纳入。
3. 发育迟缓：AAP 2013 摘要已核实但无直接推荐句、复审状态无法核实；选 (a) / (b) / (c)（见上，建议 (b)）。

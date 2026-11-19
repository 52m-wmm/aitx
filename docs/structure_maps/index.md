# GeneReviews Management结构地图索引 v1.2

按最新要求覆盖15例现有练习/复测及12例盲测实际用过的全部章节。只读核对27例的407份产物，NBK去重19章；成功19，失败0。LLM/联网请求0、费用$0；三章HPO匹配只是审阅附注，不改变治疗或患者适用性判定。

## 范围与计数规则

- 15例沿用项目既有范围：official_examples.json排除延期DMD后的11例，加retest-20261112.json的4例；12例盲测来自20261108.json。不纳入正式评测病例。
- 使用当前和历史执行产物的sourced NBK证据及已选supportive_tiers.chapters；不把基因索引候选、not_used章节或文中交叉引用当作已使用。来源追踪见manifest.json。
- 只取正文body中以Management开头的标题树（含Management of Hereditary Ataxia）；排除abstract摘要中的同名小节。包括Management内的评估、监测等所有内容，不按治疗内容筛选。
- 表格按table-wrap计，行数为XML非thead/tfoot数据行；列名与所有表头层级均保留。表内列表单列，不再计入表外列表项。
- 自由正文只计不在表格/列表内、非bold-only标题且未命中模板签名的p。列表条目只计自身文本，剔除嵌套列表/表格；同段中有内嵌表格时只计表外文本。
- 模板命中按文本单元去重，签名可在同单元命中多项；模板段不再计自由正文。列表中的模板仍属于列表，命中是注释，不能把各列简单相加当作文本总量。未命中不等于确定不是模板。
- words用Unicode词边界、保留词内连字符/撇号；chars为当前解析器规范化空白后的字符数。没有重新计算临床内容分类。
- anchor=NBK+XPath哈希，源XML SHA锁定版本，XML id若有则保留；完整原文在缓存XML位置，不复制整章正文。

## 章节汇总

| NBK / 章节 | 病例 | 表格行 | 表外列表项 | 表内列表项 | 自由正文段 / words | 套话命中单元 | 全Management words | 模式 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| [NBK1109 Neurofibromatosis 1](NBK1109.md) | PRAC-NF1 | 49 | 0 | 37 | 17 / 830 | 0 | 2240 | 汇总表+正文/列表 |
| [NBK1138 Hereditary Ataxia Overview](NBK1138.md) | PRAC-ANO10 | 24 | 0 | 20 | 3 / 93 | 0 | 891 | 汇总表+正文/列表 |
| [NBK1169 Autosomal Dominant Sleep-Related Hypermotor (Hyperkinetic) Epilepsy](NBK1169.md) | AITX-00011 | 15 | 11 | 16 | 12 / 395 | 5 | 1423 | 汇总表+标签段落 |
| [NBK1217 Urea Cycle Disorders Overview](NBK1217.md) | PRAC-OTC | 5 | 14 | 4 | 20 / 711 | 0 | 1482 | 汇总表+标签段落 |
| [NBK1244 Classic Ehlers-Danlos Syndrome](NBK1244.md) | PRAC-COL1A1 | 29 | 0 | 42 | 15 / 365 | 0 | 1509 | 汇总表+正文/列表 |
| [NBK1250 Cystic Fibrosis](NBK1250.md) | PRAC-CFTR-F508del | 63 | 16 | 66 | 15 / 675 | 0 | 2966 | 汇总表+标签段落 |
| [NBK1258 Childhood Ataxia with Central Nervous System Hypomyelination / Vanishing White Matter](NBK1258.md) | RETEST-EIF2B1 | 0 | 10 | 0 | 9 / 253 | 0 | 339 | 列表+正文（无汇总表/粗体标签） |
| [NBK1283 Primary Hyperoxaluria Type 1](NBK1283.md) | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA | 15 | 51 | 17 | 52 / 2589 | 0 | 5459 | 汇总表+标签段落 |
| [NBK1295 COL1A1- and COL1A2-Related Osteogenesis Imperfecta](NBK1295.md) | PRAC-COL1A1 | 35 | 9 | 35 | 45 / 3832 | 0 | 5402 | 汇总表+标签段落 |
| [NBK1358 Charcot-Marie-Tooth Hereditary Neuropathy Overview](NBK1358.md) | BLIND-MPZ | 0 | 4 | 0 | 16 / 586 | 0 | 668 | 列表+正文（无汇总表/粗体标签） |
| [NBK1417 Nonsyndromic Retinitis Pigmentosa Overview](NBK1417.md) | BLIND-SNRNP200 | 0 | 13 | 0 | 28 / 1281 | 0 | 1734 | 粗体标签+段落（无汇总表） |
| [NBK1450 Amyotrophic Lateral Sclerosis Overview](NBK1450.md) | RETEST-PFN1 | 0 | 3 | 0 | 13 / 556 | 0 | 950 | 粗体标签+段落（无汇总表） |
| [NBK154378 Ornithine Transcarbamylase Deficiency](NBK154378.md) | PRAC-OTC | 26 | 25 | 37 | 32 / 1421 | 5 | 4047 | 汇总表+标签段落 |
| [NBK195854 RRM2B Mitochondrial DNA Maintenance Defects](NBK195854.md) | BLIND-RRM2B | 69 | 0 | 62 | 15 / 477 | 0 | 1791 | 汇总表+正文/列表 |
| [NBK320989 Nuclear Gene-Encoded Leigh Syndrome Spectrum Overview](NBK320989.md) | BLIND-LRPPRC | 38 | 6 | 35 | 5 / 181 | 0 | 1239 | 汇总表+正文/列表 |
| [NBK493766 KMT2B-Related Disorders](NBK493766.md) | PRAC-KMT2B | 24 | 18 | 9 | 22 / 700 | 7 | 2028 | 汇总表+标签段落 |
| [NBK501979 GRIN2B-Related Neurodevelopmental Disorder](NBK501979.md) | PRAC-GRIN2B | 16 | 6 | 0 | 12 / 347 | 5 | 900 | 汇总表+标签段落 |
| [NBK525917 KCNT1-Related Epilepsy](NBK525917.md) | AITX-00011 | 0 | 17 | 0 | 21 / 631 | 5 | 1215 | 粗体标签+段落（无汇总表） |
| [NBK595821 Aromatic L-Amino Acid Decarboxylase Deficiency](NBK595821.md) | AITX-00007 | 60 | 18 | 100 | 25 / 1057 | 5 | 3907 | 汇总表+标签段落 |

合计：`{"management_roots": 19, "section_headings": 166, "bold_subheadings": 16, "paragraph_leadins": 98, "tables": 51, "table_rows": 468, "unknown_table_rows": 0, "lists_outside_tables": 61, "list_items": 221, "table_internal_list_items": 480, "free_paragraphs": 377, "free_words": 16980, "free_chars": 115987, "template_paragraphs": 22, "template_hits": 32, "template_signatures": 42, "issues": 4}`。

## 27例实际来源覆盖

| 病例 | 实际记录NBK |
|---|---|
| PRAC-AGXT-c33dup | NBK1283 |
| PRAC-AGXT-c508GA | NBK1283 |
| PRAC-ANO10 | NBK1138 |
| PRAC-CFTR-F508del | NBK1250 |
| PRAC-COL1A1 | NBK1244, NBK1295 |
| PRAC-GRIN2B | NBK501979 |
| PRAC-KMT2B | NBK493766 |
| PRAC-NF1 | NBK1109 |
| PRAC-OTC | NBK1217, NBK154378 |
| PRAC-SLC35A2-ex7 | 现存执行产物未记录实际使用NBK；不推断该基因没有章节 |
| PRAC-SLC35A2-ex8 | 现存执行产物未记录实际使用NBK；不推断该基因没有章节 |
| RETEST-CNNM4 | 现存执行产物未记录实际使用NBK；不推断该基因没有章节 |
| RETEST-EIF2B1 | NBK1258 |
| RETEST-PFN1 | NBK1450 |
| RETEST-THPO | 现存执行产物未记录实际使用NBK；不推断该基因没有章节 |
| AITX-00007 | NBK595821 |
| AITX-00011 | NBK1169, NBK525917 |
| BLIND-LRPPRC | NBK320989 |
| BLIND-MPZ | NBK1358 |
| BLIND-SNRNP200 | NBK1417 |
| BLIND-RRM2B | NBK195854 |
| BLIND-SFTPC | 现存执行产物未记录实际使用NBK；不推断该基因没有章节 |
| BLIND-FOXF1 | 现存执行产物未记录实际使用NBK；不推断该基因没有章节 |
| BLIND-GEMIN5 | 现存执行产物未记录实际使用NBK；不推断该基因没有章节 |
| BLIND-THRA | 现存执行产物未记录实际使用NBK；不推断该基因没有章节 |
| BLIND-PSMD12 | 现存执行产物未记录实际使用NBK；不推断该基因没有章节 |
| BLIND-MFSD2A | 现存执行产物未记录实际使用NBK；不推断该基因没有章节 |

## 套话观察签名（仅字符串匹配，无模板抽取实现）

- `ddid-intro`: The following information represents typical management recommendations for individuals with developmental delay / intellectual disability
- `early-intervention`: Referral to an early intervention program is recommended for access to occupational, physical, speech, and feeding therapy
- `early-intervention-us`: early intervention is a federally funded program available in all states
- `developmental-preschool`: In the US, developmental preschool through the local public school district is recommended
- `iep-qualification`: an individualized education plan (IEP) is developed for those who qualify
- `iep-services`: speech services will be provided in the IEP to the extent that the need affects the child's access to academic material
- `dda-enrollment`: Developmental Disabilities Administration (DDA) enrollment is recommended
- `feeding-oral-motor`: Assuming that the individual is safe to eat by mouth, feeding therapy
- `aba`: Children may qualify for and benefit from interventions such as applied behavior analysis (ABA)

[KMT2B / AGXT / Hereditary Ataxia对比](comparison.md) · [解析及结构限制清单](unrecognized.md)

10例现存产物没有实际使用NBK记录；不推断该基因没有GeneReviews。SFTPC抽样说明的NBK1230只属目录候选，未找到实际使用证据。等待审阅后再讨论切块/路由，本轮不实施优化。

## 章节模式（互斥、只看结构存在性，不用于路由）

| 模式 | 章节数 | NBK |
|---|---:|---|
| 列表+正文（无汇总表/粗体标签） | 2 | NBK1258, NBK1358 |
| 汇总表+标签段落 | 9 | NBK1169, NBK1217, NBK1250, NBK1283, NBK1295, NBK154378, NBK493766, NBK501979, NBK595821 |
| 汇总表+正文/列表 | 5 | NBK1109, NBK1138, NBK1244, NBK195854, NBK320989 |
| 粗体标签+段落（无汇总表） | 3 | NBK1417, NBK1450, NBK525917 |
| 无结构正文（无汇总表/粗体标签/列表） | 0 | — |

模式判定：先看有无汇总表、再看有无段首/独立粗体标签，最后看表外列表；正文/套话只作为形式注记。不将行内加粗剂量或表内粗体当作标签段落。各章所有小节的字数/原文在逐小节审阅中。

## 排除指定非治疗标题后的结构视图

此视图只使用上文已标出的Pregnancy/Evaluations/Surveillance/Relatives/Under Investigation标题，不作其他内容判定，也不用于抽取。总体模式中的“汇总表”仅表示XML表格；评估/监测表不能因此视为治疗汇总表。

| 模式 | 章节数 | NBK |
|---|---:|---|
| 列表+正文（无汇总表/粗体标签） | 2 | NBK1258, NBK1358 |
| 汇总表+标签段落 | 6 | NBK1169, NBK1217, NBK1283, NBK154378, NBK501979, NBK595821 |
| 汇总表+正文/列表 | 6 | NBK1109, NBK1138, NBK1244, NBK1250, NBK195854, NBK320989 |
| 粗体标签+段落（无汇总表） | 5 | NBK1295, NBK1417, NBK1450, NBK493766, NBK525917 |

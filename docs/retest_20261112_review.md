# 复测 retest-20261112 审阅表

由 `scripts/retest_report.py` 从账本生成；判定请写回判定文件。核查器的改动单列，逐条判断是抓住（改对了）还是误伤（改错了）。

## RETEST-CNNM4（B2）

- 变异：CNNM4 NM_020184.4 c.1312dup p.(Leu438ProfsTer9)（homozygous），ClinVar VCV000002847
- 描述（synthetic_from_hpo）：Visual impairment; Yellow-brown discoloration of the teeth; Enamel agenesis; Photophobia
- Step 2 诊断：resolved → Jalili syndrome ['OMIM:217080']
- 账本检查：全部通过（fail []，warn []）

### Tier 1 已有靶向疗法（1 条）
- **None found** — 检索无结果（searched GeneReviews and FDA labels; none found）

### Tier 1 支持治疗（1 条）
- **None found** — 检索无结果（searched GeneReviews and FDA labels; none found）

### Tier 1 禁忌与注意（1 条）
- **None found** — 检索无结果（searched GeneReviews and FDA labels; none found）

### Tier 2 临床试验（1 条）

### Tier 2 超说明书 / 扩展使用（1 条）
- **None found** — 检索无结果（searched PubMed and expanded-access records; no qualifying precedent）

### Tier 3 定制疗法（6 条）
- **ASO splice correction** — 不适用（ASO splice correction: does not apply to this variant - no evidence that this variant changes splicing; this is a limit …）
- **ASO exon skipping** — not_eligible（ASO exon skipping: not eligible - this is the first coding exon: skipping it would remove the start codon.）
- **RNA knockdown** — unable_to_assess（RNA knockdown: cannot be assessed from the information available - missing: disease mechanism not stated in GeneReviews …）
- **upregulation from the normal allele** — unable_to_assess（upregulation from the normal allele: cannot be assessed from the information available - missing: disease mechanism not …）
- **gene replacement (AAV)** — unable_to_assess（gene replacement (AAV): cannot be assessed from the information available - missing: disease mechanism not stated in Gen…）
- **base or prime editing** — theoretically_possible（base or prime editing: theoretically possible on molecular grounds alone.）

### Tier 3 药物重定位（0 条）
（无）

### 上下文核查做出的改动（逐条判：抓住 / 误伤）
（无）


## RETEST-EIF2B1（B1-L1）

- 变异：EIF2B1 NM_001414.4 c.547G>T p.Val183Phe（homozygous），ClinVar VCV000217277
- 描述（genereviews_verbatim）：Later-onset form: Initial motor and intellectual development is normal or mildly delayed. Neurologic deterioration has a chronic progressive or subacute course. Episodes of subacute deterioration may follow minor infection or minor head trauma and may lead to lethargy or coma. Truncal and appendicular ataxia Spasticity with increased tendon reflexes Peripheral nervous system is usually not involve…
- Step 2 诊断：ambiguous → leukoencephalopathy with vanishing white matter 1 ['OMIM:603896']；备选 ['congenital or early infantile CACH syndrome', 'late infantile CACH syndrome', 'juvenile or adult CACH syndrome']
- 账本检查：全部通过（fail []，warn ['drug_keys_normalized']）

### Tier 1 已有靶向疗法（1 条）
- **None found** — 检索无结果（searched GeneReviews and FDA labels; none found）

### Tier 1 支持治疗（13 条）
- **anti-seizure medication** — 适用（met: seizures）
  - 原文："Physical therapy and rehabilitation for motor dysfunction (mainly spasticity and ataxia); anti-seizure medication for seizures." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
  - 原文："Anti-seizure medication for treatment of seizures and abnormalities of behavior and mood" [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **antibiotics** — 有条件（depends on: minor infections）
  - 原文："Prevention of infections and fever when possible through the use of vaccinations, low-dose maintenance antibiotics during winter, antibiotics for minor infections, and antipyretics for fever." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
  - 原文："Considering the known adverse effect of fever, it is important to prevent infections and fever as much as possible (e.g., through the use of vaccinations, including anti-flu vaccination); low-dose maintenance antibiotics…" [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **antipyretics** — 有条件（depends on: fever）
  - 原文："Prevention of infections and fever when possible through the use of vaccinations, low-dose maintenance antibiotics during winter, antibiotics for minor infections, and antipyretics for fever." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
  - 原文："Considering the known adverse effect of fever, it is important to prevent infections and fever as much as possible (e.g., through the use of vaccinations, including anti-flu vaccination); low-dose maintenance antibiotics…" [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **corticosteroids** — 不适用（not met: the source recommends this measure）
  - 原文："Corticosteriods have been used with inconsistent results in acute situations, including intractable status epilepticus." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **maintenance antibiotics** — 有条件（depends on: during winter）
  - 原文："Prevention of infections and fever when possible through the use of vaccinations, low-dose maintenance antibiotics during winter, antibiotics for minor infections, and antipyretics for fever." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
  - 原文："Considering the known adverse effect of fever, it is important to prevent infections and fever as much as possible (e.g., through the use of vaccinations, including anti-flu vaccination); low-dose maintenance antibiotics…" [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **anti-flu vaccination** — 有条件（depends on: infections and fever）
  - 原文："Considering the known adverse effect of fever, it is important to prevent infections and fever as much as possible (e.g., through the use of vaccinations, including anti-flu vaccination); low-dose maintenance antibiotics…" [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **vaccinations** — 有条件（depends on: infections and fever）
  - 原文："Prevention of infections and fever when possible through the use of vaccinations, low-dose maintenance antibiotics during winter, antibiotics for minor infections, and antipyretics for fever." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
  - 原文："Considering the known adverse effect of fever, it is important to prevent infections and fever as much as possible (e.g., through the use of vaccinations, including anti-flu vaccination); low-dose maintenance antibiotics…" [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **Ankle-foot orthotics** — 有条件（depends on: hypotonia and weakness of ankle dorsiflexors）
  - 原文："Ankle-foot orthotics in individuals with hypotonia and weakness of ankle dorsiflexors" [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **preschool education services in the least restrictive environment** — 有条件（depends on: Children with GDD should receive preschool education services in the least restr）
  - 原文："Children with GDD should receive preschool education services in the least restrictive environment that is possible and appropriate to address their needs." [url https://indianpediatrics.net/epub022022/RECOMM-00406.pdf](https://indianpediatrics.net/epub022022/RECOMM-00406.pdf)
  - 原文："Children with GDD should receive preschool education services in the least restrictive environment that is possible and appropriate to address their needs." [url https://indianpediatrics.net/epub022022/RECOMM-00406.pdf](https://indianpediatrics.net/epub022022/RECOMM-00406.pdf)
- **helmet** — 有条件（depends on: For children）
  - 原文："For children, wearing a helmet when outside helps minimize the effects of head trauma." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
  - 原文："For children, wearing a helmet while outside helps minimize the effects of possible head trauma." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **start early intervention as soon as the delay is recognized** — 有条件（depends on: Early intervention should be initiated soon after the delay is recognized, inste）
  - 原文："Early intervention should be initiated soon after the delay is recognized, instead of waiting for a formal diagnosis." [url https://indianpediatrics.net/epub022022/RECOMM-00406.pdf](https://indianpediatrics.net/epub022022/RECOMM-00406.pdf)
  - 原文："Early intervention should be initiated soon after the delay is recognized, instead of waiting for a formal diagnosis." [url https://indianpediatrics.net/epub022022/RECOMM-00406.pdf](https://indianpediatrics.net/epub022022/RECOMM-00406.pdf)
- **physical therapy and rehabilitation** — 适用（met: motor dysfunction (mainly spasticity and ataxia)）
  - 原文："Physical therapy and rehabilitation for motor dysfunction (mainly spasticity and ataxia); anti-seizure medication for seizures." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
  - 原文："Physical therapy and rehabilitation for motor dysfunction (mainly spasticity and ataxia)" [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **multidisciplinary developmental intervention team (developmental paediatrics or paediatric neurology, clinical psychology, occupational therapy, physiotherapy, special education, speech therapy)** — 有条件（depends on: This requires a multi-disciplinary team consisting of developmental pediatrician）
  - 原文："This requires a multi-disciplinary team consisting of developmental pediatrician/pediatric neurologists, clinical psychologists, occupational therapists, physiotherapists, special educators and speech therapists." [url https://indianpediatrics.net/epub022022/RECOMM-00406.pdf](https://indianpediatrics.net/epub022022/RECOMM-00406.pdf)
  - 原文："This requires a multi-disciplinary team consisting of developmental pediatrician/pediatric neurologists, clinical psychologists, occupational therapists, physiotherapists, special educators and speech therapists." [url https://indianpediatrics.net/epub022022/RECOMM-00406.pdf](https://indianpediatrics.net/epub022022/RECOMM-00406.pdf)

### Tier 1 禁忌与注意（2 条）
- **Contact sports and other activities with a high risk of head trauma** — 适用（Management / Agents/Circumstances to Avoid）
  - 原文："Contact sports and other activities with a high risk of head trauma" [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **Stressful emotional and physical situations** — 适用（Management / Agents/Circumstances to Avoid）
  - 原文："Stressful emotional and physical situations (e.g., acute fright, fever and other causes of extreme temperatures, major surgery)" [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)

### Tier 2 临床试验（3 条）

### Tier 2 超说明书 / 扩展使用（3 条）
- **None found** — 检索无结果（searched PubMed and expanded-access records; no qualifying precedent）
- **None found** — 检索无结果（searched PubMed and expanded-access records; no qualifying precedent）
- **None found** — 检索无结果（searched PubMed and expanded-access records; no qualifying precedent）

### Tier 3 定制疗法（18 条）
- **ASO splice correction** — 不适用（ASO splice correction: does not apply to this variant - no evidence that this variant changes splicing; this is a limit …）
- **ASO exon skipping** — unable_to_assess（ASO exon skipping: cannot be assessed from the information available - missing: functional domains of the exon not check…）
- **RNA knockdown** — 不适用（RNA knockdown: does not apply to this variant - the mechanism is loss of function, so knocking the transcript down would…）
  - 原文："All disease-associated variants are loss-of-function variants, hampering eIF2B activity, thus impairing cell stress responses." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **upregulation from the normal allele** — not_graded（upregulation from the normal allele: no eligibility grade exists for this approach - homozygous leaves no normal copy to…）
  - 原文："All disease-associated variants are loss-of-function variants, hampering eIF2B activity, thus impairing cell stress responses." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **gene replacement (AAV)** — theoretically_possible（gene replacement (AAV): theoretically possible on molecular grounds alone.）
  - 原文："All disease-associated variants are loss-of-function variants, hampering eIF2B activity, thus impairing cell stress responses." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **base or prime editing** — theoretically_possible（base or prime editing: theoretically possible on molecular grounds alone.）
- **ASO splice correction** — 不适用（ASO splice correction: does not apply to this variant - no evidence that this variant changes splicing; this is a limit …）
- **ASO exon skipping** — unable_to_assess（ASO exon skipping: cannot be assessed from the information available - missing: functional domains of the exon not check…）
- **RNA knockdown** — 不适用（RNA knockdown: does not apply to this variant - the mechanism is loss of function, so knocking the transcript down would…）
  - 原文："All disease-associated variants are loss-of-function variants, hampering eIF2B activity, thus impairing cell stress responses." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **upregulation from the normal allele** — not_graded（upregulation from the normal allele: no eligibility grade exists for this approach - homozygous leaves no normal copy to…）
  - 原文："All disease-associated variants are loss-of-function variants, hampering eIF2B activity, thus impairing cell stress responses." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **gene replacement (AAV)** — theoretically_possible（gene replacement (AAV): theoretically possible on molecular grounds alone.）
  - 原文："All disease-associated variants are loss-of-function variants, hampering eIF2B activity, thus impairing cell stress responses." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **base or prime editing** — theoretically_possible（base or prime editing: theoretically possible on molecular grounds alone.）
- **ASO splice correction** — 不适用（ASO splice correction: does not apply to this variant - no evidence that this variant changes splicing; this is a limit …）
- **ASO exon skipping** — unable_to_assess（ASO exon skipping: cannot be assessed from the information available - missing: functional domains of the exon not check…）
- **RNA knockdown** — 不适用（RNA knockdown: does not apply to this variant - the mechanism is loss of function, so knocking the transcript down would…）
  - 原文："All disease-associated variants are loss-of-function variants, hampering eIF2B activity, thus impairing cell stress responses." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **upregulation from the normal allele** — not_graded（upregulation from the normal allele: no eligibility grade exists for this approach - homozygous leaves no normal copy to…）
  - 原文："All disease-associated variants are loss-of-function variants, hampering eIF2B activity, thus impairing cell stress responses." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **gene replacement (AAV)** — theoretically_possible（gene replacement (AAV): theoretically possible on molecular grounds alone.）
  - 原文："All disease-associated variants are loss-of-function variants, hampering eIF2B activity, thus impairing cell stress responses." [nbk NBK1258](https://www.ncbi.nlm.nih.gov/books/NBK1258/)
- **base or prime editing** — theoretically_possible（base or prime editing: theoretically possible on molecular grounds alone.）

### Tier 3 药物重定位（0 条）
（无）

### 上下文核查做出的改动（逐条判：抓住 / 误伤）
- corticosteroids（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation

## RETEST-THPO（B2）

- 变异：THPO NM_000460.4 c.112C>T p.Arg38Cys（heterozygous），ClinVar VCV000520806
- 描述（synthetic_from_hpo）：Thrombocytosis; Impaired ADP-induced platelet aggregation; Impaired epinephrine-induced platelet aggregation; Impaired collagen-induced platelet aggregation
- Step 2 诊断：ambiguous → thrombocythemia 1 ['OMIM:187950']；备选 ['hereditary thrombocytosis with transverse limb defect']
- 账本检查：全部通过（fail []，warn []）

### Tier 1 已有靶向疗法（1 条）
- **None found** — 检索无结果（searched GeneReviews and FDA labels; none found）

### Tier 1 支持治疗（1 条）
- **None found** — 检索无结果（searched GeneReviews and FDA labels; none found）

### Tier 1 禁忌与注意（1 条）
- **None found** — 检索无结果（searched GeneReviews and FDA labels; none found）

### Tier 2 临床试验（2 条）

### Tier 2 超说明书 / 扩展使用（2 条）
- **None found** — 检索无结果（searched PubMed and expanded-access records; no qualifying precedent）
- **None found** — 检索无结果（searched PubMed and expanded-access records; no qualifying precedent）

### Tier 3 定制疗法（12 条）
- **ASO splice correction** — 不适用（ASO splice correction: does not apply to this variant - no evidence that this variant changes splicing; this is a limit …）
- **ASO exon skipping** — not_eligible（ASO exon skipping: not eligible - exon coding length 128 nt is not a multiple of 3, so skipping it disrupts the reading …）
- **RNA knockdown** — unable_to_assess（RNA knockdown: cannot be assessed from the information available - missing: disease mechanism not stated in GeneReviews …）
- **upregulation from the normal allele** — unable_to_assess（upregulation from the normal allele: cannot be assessed from the information available - missing: disease mechanism not …）
- **gene replacement (AAV)** — unable_to_assess（gene replacement (AAV): cannot be assessed from the information available - missing: disease mechanism not stated in Gen…）
- **base or prime editing** — theoretically_possible（base or prime editing: theoretically possible on molecular grounds alone.）
- **ASO splice correction** — 不适用（ASO splice correction: does not apply to this variant - no evidence that this variant changes splicing; this is a limit …）
- **ASO exon skipping** — not_eligible（ASO exon skipping: not eligible - exon coding length 128 nt is not a multiple of 3, so skipping it disrupts the reading …）
- **RNA knockdown** — unable_to_assess（RNA knockdown: cannot be assessed from the information available - missing: disease mechanism not stated in GeneReviews …）
- **upregulation from the normal allele** — unable_to_assess（upregulation from the normal allele: cannot be assessed from the information available - missing: disease mechanism not …）
- **gene replacement (AAV)** — unable_to_assess（gene replacement (AAV): cannot be assessed from the information available - missing: disease mechanism not stated in Gen…）
- **base or prime editing** — theoretically_possible（base or prime editing: theoretically possible on molecular grounds alone.）

### Tier 3 药物重定位（0 条）
（无）

### 上下文核查做出的改动（逐条判：抓住 / 误伤）
（无）


## RETEST-PFN1（B1-L2）

- 变异：PFN1 NM_005022.4 c.211T>G p.Cys71Gly（heterozygous），ClinVar VCV000037034
- 描述（synthetic_from_hpo）：Spasticity; Dysarthria
- Step 2 诊断：ambiguous → amyotrophic lateral sclerosis []；备选 ['amyotrophic lateral sclerosis type 18']
- 账本检查：全部通过（fail []，warn ['drug_keys_normalized']）

### Tier 1 已有靶向疗法（1 条）
- **None found** — 检索无结果（searched GeneReviews and FDA labels; none found）

### Tier 1 支持治疗（32 条）
- **thickening liquids and pureeing solid food** — 有条件（depends on: Swallowing difficulties）
  - 原文："Swallowing difficulties can be alleviated by thickening liquids and pureeing solid food, as well as eventually using a gastrostomy tube to help maintain caloric intake and hydration." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **anticholinergic agents** — 有条件（depends on: Oral secretions）
  - 原文："Oral secretions in individuals with bulbar symptoms can be reduced with tricylic antidepressants and anticholinergic agents, thus reducing the need for suctioning." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **benzodiazepines** — 有条件（depends on: spasticity and muscle cramps）
  - 原文："Medications such as baclofen and benzodiazepines can help relieve spasticity and muscle cramps; however, weakness and lethargy are common side effects." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **Maharishi Amrit Kalesh** — 不适用（not met: the source recommends this measure）
  - 原文："Individuals with ALS commonly supplement their diets with vitamin E, vitamin C, B vitamins, selenium, zinc, coenzyme Q10, and herbal preparations such as ginseng, ginkgo biloba, and Maharishi Amrit Kalesh [Cameron & Rose…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **tricyclic antidepressants** — 有条件（depends on: Oral secretions）
  - 原文："Oral secretions in individuals with bulbar symptoms can be reduced with tricylic antidepressants and anticholinergic agents, thus reducing the need for suctioning." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **B vitamins** — 不适用（not met: the source recommends this measure）
  - 原文："Individuals with ALS commonly supplement their diets with vitamin E, vitamin C, B vitamins, selenium, zinc, coenzyme Q10, and herbal preparations such as ginseng, ginkgo biloba, and Maharishi Amrit Kalesh [Cameron & Rose…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **vitamin E** — 不适用（not met: the source recommends this measure）
  - 原文："Individuals with ALS commonly supplement their diets with vitamin E, vitamin C, B vitamins, selenium, zinc, coenzyme Q10, and herbal preparations such as ginseng, ginkgo biloba, and Maharishi Amrit Kalesh [Cameron & Rose…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **zinc** — 不适用（not met: the source recommends this measure）
  - 原文："Individuals with ALS commonly supplement their diets with vitamin E, vitamin C, B vitamins, selenium, zinc, coenzyme Q10, and herbal preparations such as ginseng, ginkgo biloba, and Maharishi Amrit Kalesh [Cameron & Rose…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **vitamin C** — 不适用（not met: the source recommends this measure）
  - 原文："Individuals with ALS commonly supplement their diets with vitamin E, vitamin C, B vitamins, selenium, zinc, coenzyme Q10, and herbal preparations such as ginseng, ginkgo biloba, and Maharishi Amrit Kalesh [Cameron & Rose…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **baclofen** — 有条件（depends on: spasticity and muscle cramps）
  - 原文："Medications such as baclofen and benzodiazepines can help relieve spasticity and muscle cramps; however, weakness and lethargy are common side effects." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **beta-carotene** — 不适用（not met: the source recommends this measure）
  - 原文："In a Cochrane Review, Orrell et al [2007] summarized and evaluated 21 clinical trials of antioxidant therapies in various combinations including: vitamin E, high-dose coenzyme Q10, vitamin C, selenium, beta-carotene, N-a…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **edaravone** — 有条件（depends on: early in the course of their illness）
  - 原文："Edaravone (Radicava®), approved in 2017 for use in patients with probable or definite ALS who are early in the course of their illness." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **N-acetylcysteine** — 不适用（not met: the source recommends this measure）
  - 原文："In a Cochrane Review, Orrell et al [2007] summarized and evaluated 21 clinical trials of antioxidant therapies in various combinations including: vitamin E, high-dose coenzyme Q10, vitamin C, selenium, beta-carotene, N-a…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **coenzyme Q10** — 不适用（not met: the source recommends this measure）
  - 原文："Individuals with ALS commonly supplement their diets with vitamin E, vitamin C, B vitamins, selenium, zinc, coenzyme Q10, and herbal preparations such as ginseng, ginkgo biloba, and Maharishi Amrit Kalesh [Cameron & Rose…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **ginkgo biloba** — 不适用（not met: the source recommends this measure）
  - 原文："Individuals with ALS commonly supplement their diets with vitamin E, vitamin C, B vitamins, selenium, zinc, coenzyme Q10, and herbal preparations such as ginseng, ginkgo biloba, and Maharishi Amrit Kalesh [Cameron & Rose…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **ginseng** — 不适用（not met: the source recommends this measure）
  - 原文："Individuals with ALS commonly supplement their diets with vitamin E, vitamin C, B vitamins, selenium, zinc, coenzyme Q10, and herbal preparations such as ginseng, ginkgo biloba, and Maharishi Amrit Kalesh [Cameron & Rose…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **dextromethorphan and quinidine** — 有条件（depends on: Pseudobulbar affect）
  - 原文："Pseudobulbar affect can be managed with antidepressants such as Nuedexta® (dextromethophan and quinidine)." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **riluzole** — 有条件（depends on: ALS）
  - 原文："Riluzole, now available both in tablet form as Rilutek® and as the oral suspension Teglutik®, appropriate for use in feeding tubes." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **L-methionine** — 不适用（not met: the source recommends this measure）
  - 原文："In a Cochrane Review, Orrell et al [2007] summarized and evaluated 21 clinical trials of antioxidant therapies in various combinations including: vitamin E, high-dose coenzyme Q10, vitamin C, selenium, beta-carotene, N-a…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **selegiline** — 不适用（not met: the source recommends this measure）
  - 原文："In a Cochrane Review, Orrell et al [2007] summarized and evaluated 21 clinical trials of antioxidant therapies in various combinations including: vitamin E, high-dose coenzyme Q10, vitamin C, selenium, beta-carotene, N-a…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **selenium** — 不适用（not met: the source recommends this measure）
  - 原文："Individuals with ALS commonly supplement their diets with vitamin E, vitamin C, B vitamins, selenium, zinc, coenzyme Q10, and herbal preparations such as ginseng, ginkgo biloba, and Maharishi Amrit Kalesh [Cameron & Rose…" [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **tracheostomy** — 适用（Management of ALS / Symptom Management）
  - 原文："Although tracheostomy and ventilatory support can extend life span, affected individuals often decline these interventions [Albert et al 1999]." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **alphabet board** — 有条件（depends on: speech and communication）
  - 原文："Low-tech (e.g., alphabet board) and high-tech (i.e., computer-assisted) devices can aid speech and communication." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **bathroom installments** — 有条件（depends on: activities of daily living at home）
  - 原文："Assistive devices, such as walkers or wheelchairs, can aid mobility; and others, such as bathroom installments, hospital bed, and Hoyer lift, can aid in activities of daily living at home." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **bilevel positive airway pressure** — 适用（Management of ALS / Symptom Management）
  - 原文："Ventilatory assistance may include use of bilevel positive airway pressure, which has played an increasing role in preserving and prolonging quality of life in persons with ALS." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **computer-assisted devices** — 有条件（depends on: speech and communication）
  - 原文："Low-tech (e.g., alphabet board) and high-tech (i.e., computer-assisted) devices can aid speech and communication." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **eye movement-controlled on-screen keyboard** — 有条件（depends on: communication）
  - 原文："The recent development of the eye movement-controlled on-screen keyboard may enable communication for individuals without any remaining limb function." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **gastrostomy tube** — 有条件（depends on: Swallowing difficulties）
  - 原文："Swallowing difficulties can be alleviated by thickening liquids and pureeing solid food, as well as eventually using a gastrostomy tube to help maintain caloric intake and hydration." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **hospital bed** — 有条件（depends on: activities of daily living at home）
  - 原文："Assistive devices, such as walkers or wheelchairs, can aid mobility; and others, such as bathroom installments, hospital bed, and Hoyer lift, can aid in activities of daily living at home." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **Hoyer lift** — 有条件（depends on: activities of daily living at home）
  - 原文："Assistive devices, such as walkers or wheelchairs, can aid mobility; and others, such as bathroom installments, hospital bed, and Hoyer lift, can aid in activities of daily living at home." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **walkers** — 有条件（depends on: mobility）
  - 原文："Assistive devices, such as walkers or wheelchairs, can aid mobility; and others, such as bathroom installments, hospital bed, and Hoyer lift, can aid in activities of daily living at home." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)
- **wheelchairs** — 有条件（depends on: mobility）
  - 原文："Assistive devices, such as walkers or wheelchairs, can aid mobility; and others, such as bathroom installments, hospital bed, and Hoyer lift, can aid in activities of daily living at home." [nbk NBK1450](https://www.ncbi.nlm.nih.gov/books/NBK1450/)

### Tier 1 禁忌与注意（1 条）
- **None found** — 检索无结果（searched GeneReviews and FDA labels; none found）

### Tier 2 临床试验（11 条）
- **RAPA-501 Therapy for ALS (NCT04220190)** — 有条件（depends on: age; bilirubin; creatinine; current medication; diagnosis; lab; other; pregnancy status; prior therapy）
  - 原文："History of documented pulmonary embolus within 6 months of enrollment." [nct NCT04220190](https://clinicaltrials.gov/study/NCT04220190)
  - 原文："Active uncontrolled infection" [nct NCT04220190](https://clinicaltrials.gov/study/NCT04220190)
- **MND-SMART (NCT04302870)** — 有条件（depends on: age）
  - 原文："minimumAge: 18 Years; maximumAge: none" [nct NCT04302870](https://clinicaltrials.gov/study/NCT04302870)
- **FB1006 (NCT05923905)** — 有条件（depends on: age; diagnosis; eGFR; lab; other; pregnancy status; prior therapy）
  - 原文："Suicide attempt or attempted suicide" [nct NCT05923905](https://clinicaltrials.gov/study/NCT05923905)
  - 原文："Combined with other neurological diseases similar to ALS symptoms, or affecting the evaluation of drug efficacy, such as cervical spondylotic myelopathy, lumbar spondylosis, dementia, etc." [nct NCT05923905](https://clinicaltrials.gov/study/NCT05923905)
- **ALCALS (NCT06126315)** — 有条件（depends on: age; current medication; diagnosis; lab; other; pregnancy status; prior therapy）
  - 原文："men unable to practice contraception for the duration of the treatment and three months after its completion" [nct NCT06126315](https://clinicaltrials.gov/study/NCT06126315)
  - 原文："Motor neuron disease (MND) other than ALS" [nct NCT06126315](https://clinicaltrials.gov/study/NCT06126315)
- **tDCS-ALS (NCT06719947)** — 有条件（depends on: age; diagnosis; lab; other; pregnancy status）
  - 原文："Age between 18 and 80 years;" [nct NCT06719947](https://clinicaltrials.gov/study/NCT06719947)
  - 原文："a history of epilepsy" [nct NCT06719947](https://clinicaltrials.gov/study/NCT06719947)
- **A Study to Evaluate the Efficacy and Safety of Different Doses of CB03-154 in Adult Patients With Amyotrophic Lateral Sclerosis (ALS) (NCT07082192)** — 有条件（depends on: age; bilirubin; current medication; diagnosis; eGFR; lab; other; participation in other trials; pregnancy st…）
  - 原文："a history of venous thrombosis" [nct NCT07082192](https://clinicaltrials.gov/study/NCT07082192)
  - 原文："Hepatitis B surface antigen (HBsAg) positive" [nct NCT07082192](https://clinicaltrials.gov/study/NCT07082192)
- **Efficacy and Safety of Masitinib in Combination With SoC Versus Placebo in the Treatment of ALS Patients (NCT07174492)** — 有条件（depends on: age; current medication; diagnosis; kidney function; lab; liver function; organ function; other; pregnancy s…）
  - 原文："clinically probable or definite ALS" [nct NCT07174492](https://clinicaltrials.gov/study/NCT07174492)
  - 原文："Female patients of childbearing potential and male patients must use a highly effective method of contraception during the trial and for a specified period afterwards" [nct NCT07174492](https://clinicaltrials.gov/study/NCT07174492)
- **This Study Evaluates the Safety, Target Engagement, and Preliminary Efficacy of Galunisertib (TGF-βR1/ALK5 Inhibitor)Combined With Nerandomilast (PDE4 Inhibitor) in GREM2-positive ALS, a Biomarker-defined Subgroup Hypothesized to Reflect Heightened TGF-β/SMAD-driven Astrocytic and Fibrotic Signaling (NCT07321860)** — 有条件（depends on: age; current medication; diagnosis; lab; other; participation in other trials; pregnancy status; prior thera…）
  - 原文："Diagnosis of primary lateral sclerosis (PLS)" [nct NCT07321860](https://clinicaltrials.gov/study/NCT07321860)
  - 原文："History of organ transplantation" [nct NCT07321860](https://clinicaltrials.gov/study/NCT07321860)
- **PREVAiLS (NCT07322003)** — 有条件（depends on: age; current medication; diagnosis; genetic confirmation; other; pregnancy status; prior therapy）
  - 原文："Slow vital capacity (SVC) greater or equal to 60% predicted." [nct NCT07322003](https://clinicaltrials.gov/study/NCT07322003)
  - 原文："substance abuse" [nct NCT07322003](https://clinicaltrials.gov/study/NCT07322003)
- **Efficacy and Safety of Tazbentetol in ALS Participants (NCT07325591)** — 有条件（depends on: age; current medication; diagnosis; other; pregnancy status; prior therapy）
  - 原文："Vaccines within 14 days" [nct NCT07325591](https://clinicaltrials.gov/study/NCT07325591)
  - 原文："Underlying physical or psychological condition prohibiting study completion" [nct NCT07325591](https://clinicaltrials.gov/study/NCT07325591)

### Tier 2 超说明书 / 扩展使用（1 条）
- **None found** — 检索无结果（searched PubMed and expanded-access records; no qualifying precedent）

### Tier 3 定制疗法（6 条）
- **ASO splice correction** — 不适用（ASO splice correction: does not apply to this variant - no evidence that this variant changes splicing; this is a limit …）
- **ASO exon skipping** — not_eligible（ASO exon skipping: not eligible - exon coding length 193 nt is not a multiple of 3, so skipping it disrupts the reading …）
- **RNA knockdown** — unable_to_assess（RNA knockdown: cannot be assessed from the information available - missing: disease mechanism not stated in GeneReviews …）
- **upregulation from the normal allele** — unable_to_assess（upregulation from the normal allele: cannot be assessed from the information available - missing: disease mechanism not …）
- **gene replacement (AAV)** — unable_to_assess（gene replacement (AAV): cannot be assessed from the information available - missing: disease mechanism not stated in Gen…）
- **base or prime editing** — theoretically_possible（base or prime editing: theoretically possible on molecular grounds alone.）

### Tier 3 药物重定位（0 条）
（无）

### 上下文核查做出的改动（逐条判：抓住 / 误伤）
- anticholinergic agents（Tier 1 支持治疗）：限定（只针对部分病人） — "individuals with bulbar symptoms" → unknown；context check: the passage limits this advice to some patients
- Maharishi Amrit Kalesh（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- tricyclic antidepressants（Tier 1 支持治疗）：限定（只针对部分病人） — "individuals with bulbar symptoms" → unknown；context check: the passage limits this advice to some patients
- B vitamins（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- vitamin E（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- zinc（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- vitamin C（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- beta-carotene（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- edaravone（Tier 1 支持治疗）：限定（只针对部分病人） — "probable or definite ALS" → unknown；context check: the passage limits this advice to some patients
- N-acetylcysteine（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- coenzyme Q10（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- ginkgo biloba（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- ginseng（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- L-methionine（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- selegiline（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- selenium（Tier 1 支持治疗）：recommendation — "the source recommends this measure" → fail；context check: the passage only describes use or reports no benefit; not a recommendation
- eye movement-controlled on-screen keyboard（Tier 1 支持治疗）：限定（只针对部分病人） — "individuals without any remaining limb function" → unknown；context check: the passage limits this advice to some patients

## THPO：3b 被癌症规则排除的试验

（没有试验因癌症规则被排除）


其余被排除的试验 621 条（相关性或状态等其他原因），见账本 `trial_searches`。

## 机器检查

```
{ "schema": "blind-machine-v1", "batch": "retest-20261112", "checked_at": 1794638256, "code_fingerprint": "7ef504ea358e040cfb09138ca470748e076e4c90e9d97c2927a32e480309766d", "frozen_as_drawn": false, "cases": { "RETEST-EIF2B1": { "ran": true, "entries": 40, "machine_wrong": 0, "ledger_ok": true, "freshness": { "fresh": true, "reasons": [] }, "upstream": { "phenotypes": 11, "facts": 0, "diagnosis": "ambiguous", "warnings": [ "no patient facts" ] }, "failed_checks": [], "sections": { "existing_targeted_therapies": 1, "supportive_management": 13, "contraindications_precautions": 2, "clinical_trial_eligibility": 3, "off_label_expanded_access": 3, "bespoke_therapies": 18, "drug_repurposing": 0 } }, "RETEST-PFN1": { "ran": true, "entries": 52, "machine_wrong": 0, "ledger_ok": true, "freshness": { "fresh": true, "reasons": [] }, "upstream": { "phenotypes": 2, "facts": 0, "diagnosis": "ambiguous", "warnings": [ "no patient facts" ] }, "failed_checks": [], "sections": { "existing_targeted_therapies": 1, "supportive_management": 32, "contraindications_precautions": 1, "clinical_trial_eligibility": 11, "off_label_expanded_access": 1, "bespoke_therapies": 6, "drug_repurposing": 0 } }, "RETEST-CNNM4": { "ran": true, "entries": 11, "machine_wrong": 0, "ledger_ok": true, "freshness": { "fresh": true, "reasons": [] }, "upstream": { "phenotypes": 4, "facts": 0, "diagnosis": "resolved", "warnings": [ "no patient facts" ] }, "failed_checks": [], "sections": { "existing_targeted_therapies": 1, "supportive_management": 1, "contraindications_precautions": 1, "clinical_trial_eligibility": 1, "off_label_expanded_access": 1, "bespoke_therapies": 6, "drug_repurposing": 0 } }, "RETEST-THPO": { "ran": true, "entries": 19, "machine_wrong": 0, "ledger_ok": true, "freshness": { "fresh": true, "reasons": [] }, "upstream": { "phenotypes": 4, "facts": 0, "diagnosis": "ambiguous", "warnings": [ "no patient facts" ] }, "failed_checks": [], "sections": { "existing_targeted_therapies": 1, "supportive_management": 1, "contraindications_precautions": 1, "clinical_trial_eligibility": 2, "off_label_expanded_access": 2, "bespoke_therapies": 12, "drug_repurposing": 0 } } }, "machine_wrong": [], "for_review": [ { "case": "RETEST-EIF2B1", "section": "supportive_management", "label": "anti-seizure medication", "conclusion": "", "status": { "MONDO:0015519": "applicable", "MONDO:0015520": "applicable", "MONDO:0020507": "applicable" }, "cites": [ { "type": "nbk", "id": "NBK1258", "url": "https://www.ncbi.nlm.nih.gov/books/NBK1258/", "quote": "Physical therapy and rehabilitation for motor dysfunction (mainly spasticity and ataxia); anti-seizure medication for seizures." }, { "type": "nbk", "id": "NBK1258", "url": "https://www.ncbi.nlm.nih.gov/books/NBK1258/", "quote": "Anti-seizure medication for treatment of seizures and abnormalities of behavior and mood" } ], "needs_review": [ "semantics: does the conclusion match the quote", "applicability: does it apply to this patient" ] }, { "case": "RETEST-EIF2B1", "section": "supportive_management", "label": "antibiotics", "conclusion": "", "status": { "MONDO:0015519": "conditional", "MONDO:0015520": "conditional", "MONDO:0020507": "conditional" }, "cites": [ { "type": "nbk", "id": "NBK1258", "url": "https://www.ncbi.nlm.nih.gov/books/NBK1258/", "quote": "Considering the known adverse effect of fever, it is important to prevent infections and fever as much as possible (e.g., through the use of vaccinations, including anti-flu vaccination); low-dose maintenance antibiotics during winter, antibiotics for minor infections, and antipyretics for fever are" }, { "type": "nbk", "id": "NBK1258", "url": "https://www.ncbi.nlm.nih.gov/books/NBK1258/", "quote": "Prevention of infections and fever when possible through the use of vaccinations, low-dose maintenance antibiotics during winter, antibiotics for minor infections, and antipyretics for fever." } ], "needs_review": [ "semantics: does the conclusion match the quote", "applicability: does it…
```


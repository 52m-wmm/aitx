# KMT2B两票条件差异审计（$0，第三票之前）

分类可重叠，计数单位为行动；新增/遗漏均指抽取字段差异，不代表医学条件被确认新增或废除。完整旧新条件、Evidence ID及原文见同目录JSON。

## chest physical therapy

措辞不同 / 条件范围改变 / 条件遗漏。individuals with不改含义；表现由pulmonary infections换为respiratory compromise，原句because of increased risk表示风险理由，不能自动把感染当现有表现。旧字段消失须保留审阅，不自动删医学条件。

票1原文证据：

- [d32c9973658b] For individuals with respiratory compromise from chest deformities related to scoliosis, prophylactic antibiotics during the winter months, regular chest physical therapy, and influenza immunizations should be considered because of the increased risk of pulmonary infections.
- [10091145c42e] pulmonary infections

票2原文证据：

- [3c85d937e95e] respiratory compromise from chest deformities related to scoliosis
- [06e6e916e18d] For individuals with respiratory compromise from chest deformities related to scoliosis, prophylactic antibiotics during the winter months, regular chest physical therapy, and influenza immunizations should be considered because of the increased risk of pulmonary infections.

## speech-language therapy

条件新增 / 条件范围改变。增加DD/ID及feeding skills and communication范围；需区分新增来源的局部条件与整项行动限制，不能将该范围施于所有speech来源。

票1原文证据：

- [6df8ab34284b] Physical therapy (PT), occupational therapy (OT), and speech services will be provided in the IEP to the extent that the need affects the child's access to academic material.
- [9ee135eeebe5] Speech-language therapy helps assist in feeding skills and communication.

票2原文证据：

- [9e56860cd49c] developmental delay / intellectual disability
- [f361a3159b34] Physical therapy (PT), occupational therapy (OT), and speech services will be provided in the IEP to the extent that the need affects the child's access to academic material.
- [c2d99894160f] feeding skills and communication
- [dc6d3c4a03ca] Speech-language therapy helps assist in feeding skills and communication.

## applied behavior analysis (ABA)

条件遗漏 / 条件新增 / 条件范围改变。Children在新条件中遗漏；strengths/weaknesses为个体化干预依据，是否为资格条件未确认。两者均保留needs_review。

票1原文证据：

- [7a0f875e413b] Children may qualify for and benefit from interventions such as applied behavior analysis (ABA).

票2原文证据：

- [df006d87646d] Children may qualify for and benefit from interventions such as applied behavior analysis (ABA).
- [a1e1f7a39268] behavioral, social, and adaptive strengths and weaknesses

## feeding therapy

措辞不同 / 条件新增 / 条件范围改变。safe to eat与Assuming safe含义相同；DD/ID及0–3岁来自新增段落，年龄重复，不能扩为所有feeding therapy的年龄上限。

票1原文证据：

- [620ade153582] difficulty feeding due to poor oral motor control
- [95e499e9758c] Assuming that the individual is safe to eat by mouth, feeding therapy, typically from an occupational or speech therapist, is recommended for affected individuals who have difficulty feeding due to poor oral motor control.

票2原文证据：

- [264caf0943a4] developmental delay / intellectual disability
- [620ade153582] difficulty feeding due to poor oral motor control
- [08783c35237e] Ages 0-3 years
- [a208580a9a5a] Referral to an early intervention program is recommended for access to occupational, physical, speech, and feeding therapy as well as infant mental health services, special educators, and sensory impairment specialists.
- [95e499e9758c] Assuming that the individual is safe to eat by mouth, feeding therapy, typically from an occupational or speech therapist, is recommended for affected individuals who have difficulty feeding due to poor oral motor control.

## developmental preschool

条件新增。重复3–5岁不构成新限制；DD/ID章节范围新入条件，保留来源范围审阅。

票1原文证据：

- [f0ff07a462f5] Ages 3-5 years
- [dca9182bbf01] In the US, developmental preschool through the local public school district is recommended.

票2原文证据：

- [c99e130ab91b] In the US, developmental preschool through the local public school district is recommended.
- [f0ff07a462f5] Ages 3-5 years
- [0fc268d8b804] developmental delay / intellectual disability

## antimuscarinic (anticholinergic) agents

措辞不同。individuals with不改变确诊条件；motor manifestations未变。

票1原文证据：

- [6061c8ac4e11] Antimuscarinic (anticholinergic) agents have significantly improved motor manifestations (~50%) in individuals with KMT2B-related disorders [Lange et al 2021, Aksoy et al 2022] and should be considered first-line pharmacologic treatment in individuals with a confirmed diagnosis of a KMT2B-related disorder.
- [4d085e49d2e8] motor manifestations

票2原文证据：

- [6061c8ac4e11] Antimuscarinic (anticholinergic) agents have significantly improved motor manifestations (~50%) in individuals with KMT2B-related disorders [Lange et al 2021, Aksoy et al 2022] and should be considered first-line pharmacologic treatment in individuals with a confirmed diagnosis of a KMT2B-related disorder.
- [4d085e49d2e8] motor manifestations

## prophylactic antibiotics

措辞不同。individuals with不改变范围，冬季及原pulmonary infections字段均保留；感染风险是否应为条件另待审，不改规则。

票1原文证据：

- [e20e85668e87] For individuals with respiratory compromise from chest deformities related to scoliosis, prophylactic antibiotics during the winter months, regular chest physical therapy, and influenza immunizations should be considered because of the increased risk of pulmonary infections.
- [54b388d841b0] pulmonary infections

票2原文证据：

- [e20e85668e87] For individuals with respiratory compromise from chest deformities related to scoliosis, prophylactic antibiotics during the winter months, regular chest physical therapy, and influenza immunizations should be considered because of the increased risk of pulmonary infections.
- [54b388d841b0] pulmonary infections

## physical therapy

条件新增 / 条件范围改变。增加DD/ID局部来源范围，不应自动限制其他段落已有PT行动。

票1原文证据：

- [7809fc6a543c] joint contractures, hip dislocation, and/or kyphoscoliosis
- [54615bc63548] Physical therapy (PT), occupational therapy (OT), and speech services will be provided in the IEP to the extent that the need affects the child's access to academic material.
- [d26ebb41f256] Early initiation of physical therapy and a tailored exercise program helps maintain function and prevent secondary orthopedic complications such as joint contractures, hip dislocation, and/or kyphoscoliosis.

票2原文证据：

- [3c673c8405bf] developmental delay / intellectual disability
- [7809fc6a543c] joint contractures, hip dislocation, and/or kyphoscoliosis
- [6194c866b947] Physical therapy (PT), occupational therapy (OT), and speech services will be provided in the IEP to the extent that the need affects the child's access to academic material.
- [d26ebb41f256] Early initiation of physical therapy and a tailored exercise program helps maintain function and prevent secondary orthopedic complications such as joint contractures, hip dislocation, and/or kyphoscoliosis.

## early intervention program

条件新增。0–3岁重复，DD/ID章节范围新增；重复年龄不构成新医学条件。

票1原文证据：

- [30a157cf429a] Ages 0-3 years
- [fc789a2107b4] Referral to an early intervention program is recommended for access to occupational, physical, speech, and feeding therapy as well as infant mental health services, special educators, and sensory impairment specialists.

票2原文证据：

- [30a157cf429a] Ages 0-3 years
- [cdff6411ad3d] developmental delay / intellectual disability
- [e30b1662945e] Referral to an early intervention program is recommended for access to occupational, physical, speech, and feeding therapy as well as infant mental health services, special educators, and sensory impairment specialists.

## occupational therapy

措辞不同 / 条件新增 / 条件范围改变。fine motor大小写不改含义，增加DD/ID局部来源范围。

票1原文证据：

- [de8e497e96cc] Fine motor dysfunction
- [5e4e9b9b6021] Occupational therapy is recommended to address fine motor skills that affect adaptive function such as feeding, grooming, dressing, and writing.
- [cfe8b363b238] Physical therapy (PT), occupational therapy (OT), and speech services will be provided in the IEP to the extent that the need affects the child's access to academic material.

票2原文证据：

- [668fe0fed7fd] developmental delay / intellectual disability
- [da6ea7993096] Physical therapy (PT), occupational therapy (OT), and speech services will be provided in the IEP to the extent that the need affects the child's access to academic material.
- [12a6d61ab700] fine motor dysfunction
- [eb75d3d55551] Occupational therapy is recommended to address fine motor skills that affect adaptive function such as feeding, grooming, dressing, and writing.

## influenza immunizations

措辞不同。individuals with不改变范围；另有kind分歧独立记录，不以条件措辞解释类型变化。

票1原文证据：

- [6998874cd20e] For individuals with respiratory compromise from chest deformities related to scoliosis, prophylactic antibiotics during the winter months, regular chest physical therapy, and influenza immunizations should be considered because of the increased risk of pulmonary infections.
- [f455af9539cf] pulmonary infections

票2原文证据：

- [2d377e22f306] pulmonary infections
- [0b81380edd78] For individuals with respiratory compromise from chest deformities related to scoliosis, prophylactic antibiotics during the winter months, regular chest physical therapy, and influenza immunizations should be considered because of the increased risk of pulmonary infections.


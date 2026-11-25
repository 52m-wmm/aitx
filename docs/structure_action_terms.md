# 结构扫描词表（待审阅）

> 历史设计参考：对应旧结构抽取实验已退役，本文不定义当前生产接口，也不恢复历史调用授权。与Step3后续适配有关的设计和未核实问题暂保留；当前入口见 [3a说明](step3a_contract.md)。

历史机器可读词表 `data/structure_action_terms.json` 已随旧结构抽取方案清理；下表仅保留当时的审阅记录。来源为15例Accepted；仅供原句匹配，不推断医学等价或临床推荐。单一RxNorm行动排除；drug:name未解析项和组合单列类型，不能冒充已确认非药物类别。neridronate由用户验收要求补入，RxNorm精确查询无匹配。

| 名称 | 原文别名 | 类型 | 来源病例 |
|---|---|---|---|
| activities with increased fall or high-impact collision risk |  | class_or_procedure_seed | PRAC-COL1A1 |
| adaptive devices |  | class_or_procedure_seed | PRAC-ANO10 |
| aerosolized antibiotic |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| airway clearance |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| alternating positions |  | class_or_procedure_seed | PRAC-COL1A1 |
| alternative communication methods |  | class_or_procedure_seed | PRAC-ANO10 |
| ammonia scavenger treatment |  | accepted_class_combination_or_unresolved_name | PRAC-OTC |
| ammonia scavengers |  | accepted_class_combination_or_unresolved_name | PRAC-OTC |
| anesthesia |  | class_or_procedure_seed | PRAC-COL1A1 |
| ankle-foot orthoses |  | class_or_procedure_seed | PRAC-KMT2B |
| Annual influenza vaccine |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| anti-parkinsonian medications |  | accepted_class_combination_or_unresolved_name | PRAC-OTC |
| anti-seizure medication |  | accepted_class_combination_or_unresolved_name | PRAC-GRIN2B |
| anti-seizure medications |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1 |
| antibiotics |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| antimuscarinic (anticholinergic) agents |  | accepted_class_combination_or_unresolved_name | PRAC-KMT2B |
| assisted reproductive technologies (ART) |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| augmentative and alternative communication (AAC) |  | class_or_procedure_seed | PRAC-KMT2B |
| benzodiazepine rescue for prolonged seizures (IV lorazepam or IV diazepam) |  | class_or_procedure_seed | PRAC-SLC35A2-ex7, PRAC-SLC35A2-ex8 |
| benzodiazepines |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1, PRAC-KMT2B |
| Bilateral globus pallidus pars interna deep brain stimulation (GPi-DBS) |  | class_or_procedure_seed | PRAC-KMT2B |
| bisphosphonate |  | accepted_class_combination_or_unresolved_name | PRAC-NF1 |
| bisphosphonates | bisphosphonate | class_or_procedure_seed | PRAC-COL1A1 |
| bone morphogenetic protein-2 |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1 |
| botulinum toxin |  | accepted_class_combination_or_unresolved_name | PRAC-OTC |
| braces |  | class_or_procedure_seed | PRAC-COL1A1 |
| bracing |  | class_or_procedure_seed | PRAC-COL1A1 |
| breast milk |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| bronchodilator |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| casts |  | class_or_procedure_seed | PRAC-COL1A1 |
| CFTR modulator therapy | CFTR modulators, CFTR modulator, CF transmembrane conductance regulator (CFTR) modulator therapy | class_or_procedure_seed | PRAC-CFTR-F508del |
| chest physical therapy |  | class_or_procedure_seed | PRAC-KMT2B |
| chilled feeds |  | class_or_procedure_seed | PRAC-OTC |
| CKRT |  | class_or_procedure_seed | PRAC-OTC |
| complete surgical excision |  | class_or_procedure_seed | PRAC-NF1 |
| contact precautions |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| Contact precautions (gown & gloves) |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| contact sports |  | class_or_procedure_seed | PRAC-COL1A1 |
| continuous insulin infusion |  | accepted_class_combination_or_unresolved_name | PRAC-OTC |
| COX-2 inhibitors |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1 |
| CVVHD |  | class_or_procedure_seed | PRAC-OTC |
| Dehydration |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| dermal wound closure without tension |  | class_or_procedure_seed | PRAC-COL1A1 |
| developmental preschool |  | class_or_procedure_seed | PRAC-GRIN2B, PRAC-KMT2B, PRAC-OTC |
| dialysis |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| double lung transplant |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| durable medical equipment |  | class_or_procedure_seed | PRAC-GRIN2B |
| durable medical equipment and positioning devices |  | class_or_procedure_seed | PRAC-OTC |
| early intervention program |  | class_or_procedure_seed | PRAC-GRIN2B, PRAC-KMT2B, PRAC-OTC |
| electrocautery |  | class_or_procedure_seed | PRAC-NF1 |
| Elexacaftor/tezacaftor/ivacaftor |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| Environmental smoke and inhalants |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| Eradication attempts |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| essential amino acid medical food |  | class_or_procedure_seed | PRAC-OTC |
| essential amino acid mix |  | class_or_procedure_seed | PRAC-OTC |
| essential amino acids |  | accepted_class_combination_or_unresolved_name | PRAC-OTC |
| excessive alcohol |  | class_or_procedure_seed | PRAC-COL1A1 |
| Exposure to respiratory infections |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| external braces |  | class_or_procedure_seed | PRAC-COL1A1 |
| Extra salt & water |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| Fasting |  | class_or_procedure_seed | PRAC-OTC |
| Fat-soluble vitamin supplements |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| feeding therapy |  | class_or_procedure_seed | PRAC-GRIN2B, PRAC-KMT2B, PRAC-OTC |
| fighting sports |  | class_or_procedure_seed | PRAC-COL1A1 |
| Foods high in oxalate |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| football |  | class_or_procedure_seed | PRAC-COL1A1 |
| G-tube |  | class_or_procedure_seed | PRAC-OTC |
| Gastrostomy tube |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| Gastrostomy tube feedings |  | class_or_procedure_seed | PRAC-OTC |
| gastrostomy tube placement |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| glucosamine & chondroitin |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1 |
| glucose & fat calories |  | class_or_procedure_seed | PRAC-OTC |
| Gonadotropin ovulation induction |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| hemodialysis |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| high oral fluid intake |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| high-dose CKRT |  | class_or_procedure_seed | PRAC-OTC |
| home adaptations |  | class_or_procedure_seed | PRAC-ANO10 |
| individualised antiseizure medication treatment strategy |  | class_or_procedure_seed | PRAC-SLC35A2-ex7, PRAC-SLC35A2-ex8 |
| influenza immunizations |  | accepted_class_combination_or_unresolved_name | PRAC-KMT2B |
| Inhaled corticosteroids &/or long-acting beta agonist |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| Insulin therapy |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| Intake of vitamin C that exceeds the recommended daily allowance |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| intermittent HD |  | class_or_procedure_seed | PRAC-OTC |
| intramedullary rodding |  | class_or_procedure_seed | PRAC-COL1A1 |
| Intrauterine insemination |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| Intravascular volume depletion |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| intravenous fluids |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| IVF |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| IVF w/intracytoplasmic sperm injection |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| knee or ankle braces |  | class_or_procedure_seed | PRAC-COL1A1 |
| laser |  | class_or_procedure_seed | PRAC-NF1 |
| laxative treatment |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| Laxatives |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| lifting an infant by the ankle when diapering |  | class_or_procedure_seed | PRAC-COL1A1 |
| liver transplant | liver transplantation | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA, PRAC-CFTR-F508del |
| Liver transplantation |  | class_or_procedure_seed | PRAC-OTC |
| Loop diuretics |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| low-protein diet |  | class_or_procedure_seed | PRAC-OTC |
| Lumacaftor/ivacaftor |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| MEK inhibitors | MEK inhibitor | class_or_procedure_seed | PRAC-NF1 |
| Microsurgical epididymal sperm aspiration |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| modified automobiles |  | class_or_procedure_seed | PRAC-COL1A1 |
| modify food consistency |  | class_or_procedure_seed | PRAC-ANO10 |
| multidisciplinary developmental intervention team (developmental paediatrics or paediatric neurology, clinical psychology, occupational therapy, physiotherapy, special education, speech therapy) |  | class_or_procedure_seed | PRAC-SLC35A2-ex7, PRAC-SLC35A2-ex8 |
| muscle relaxants |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1 |
| nasogastric tube |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| neridronate |  | user_required_name |  |
| NG-tube |  | class_or_procedure_seed | PRAC-OTC |
| nitrogen-scavenging drugs |  | accepted_class_combination_or_unresolved_name | PRAC-OTC |
| nonsteroidal anti-inflammatory drugs |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1 |
| Nonsteroidal anti-inflammatory drugs (NSAIDs) |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| NSAIDs |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1 |
| Nutrient-dense food & supplements |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| nutrient-dense food and supplements |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| nutritional & vitamin supplementation |  | class_or_procedure_seed | PRAC-ANO10 |
| occupational therapy |  | class_or_procedure_seed | PRAC-ANO10, PRAC-COL1A1, PRAC-GRIN2B, PRAC-KMT2B, PRAC-OTC |
| opioids |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1 |
| orthopedic procedures |  | class_or_procedure_seed | PRAC-OTC |
| orthotics |  | class_or_procedure_seed | PRAC-COL1A1 |
| osteotomy |  | class_or_procedure_seed | PRAC-COL1A1 |
| pancreatic enzyme replacement |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| Pancreatic enzyme replacement therapy |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| Paxlovid |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| percutaneous nephrolithotomy |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| peritoneal dialysis |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| Pharmacologic agents that can compromise kidney function |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| physical therapy |  | class_or_procedure_seed | PRAC-ANO10, PRAC-GRIN2B, PRAC-KMT2B, PRAC-OTC |
| physiotherapist |  | class_or_procedure_seed | PRAC-COL1A1 |
| Polypectomy |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| Postural drainage & percussion |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| preoperative and intraoperative traction |  | class_or_procedure_seed | PRAC-COL1A1 |
| preschool education services in the least restrictive environment |  | class_or_procedure_seed | PRAC-SLC35A2-ex7, PRAC-SLC35A2-ex8 |
| prophylactic antibiotics |  | accepted_class_combination_or_unresolved_name | PRAC-KMT2B |
| protective pads or bandages |  | class_or_procedure_seed | PRAC-COL1A1 |
| protein intake |  | class_or_procedure_seed | PRAC-OTC |
| pyrophosphate-containing solutions |  | accepted_class_combination_or_unresolved_name | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| radiotherapy |  | class_or_procedure_seed | PRAC-NF1 |
| reduction and realignment |  | class_or_procedure_seed | PRAC-COL1A1 |
| regular CKRT |  | class_or_procedure_seed | PRAC-OTC |
| renal replacement therapy |  | class_or_procedure_seed | PRAC-OTC |
| ring splints |  | class_or_procedure_seed | PRAC-COL1A1 |
| routine vaccinations |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| running |  | class_or_procedure_seed | PRAC-COL1A1 |
| salt supplementation |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| secondhand smoke |  | class_or_procedure_seed | PRAC-COL1A1 |
| segmental pedicle screw fixation |  | class_or_procedure_seed | PRAC-COL1A1 |
| serotonin/norepinephrine receptor inhibitors |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1 |
| shockwave lithotripsy |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| Sinus surgery |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| smoking |  | class_or_procedure_seed | PRAC-COL1A1 |
| soccer pads or ski stockings w/shin padding |  | class_or_procedure_seed | PRAC-COL1A1 |
| sodium phenylacetate & sodium benzoate |  | accepted_class_combination_or_unresolved_name | PRAC-OTC |
| soft neck collar |  | class_or_procedure_seed | PRAC-COL1A1 |
| speech therapy |  | class_or_procedure_seed | PRAC-GRIN2B, PRAC-OTC |
| Speech-language therapy |  | class_or_procedure_seed | PRAC-KMT2B |
| start early intervention as soon as the delay is recognized |  | class_or_procedure_seed | PRAC-SLC35A2-ex7, PRAC-SLC35A2-ex8 |
| steroids |  | class_or_procedure_seed | PRAC-COL1A1 |
| Stress |  | class_or_procedure_seed | PRAC-OTC |
| substances or medications that may affect bone health |  | class_or_procedure_seed | PRAC-COL1A1 |
| subthalamic nucleus DBS |  | class_or_procedure_seed | PRAC-KMT2B |
| sudden acceleration/deceleration movements |  | class_or_procedure_seed | PRAC-COL1A1 |
| surgery |  | class_or_procedure_seed | PRAC-COL1A1 |
| surgical intervention for nasal/sinus symptoms |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| surgical management |  | class_or_procedure_seed | PRAC-NF1 |
| surgical management for bowel obstruction |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| surgical removal |  | class_or_procedure_seed | PRAC-NF1 |
| surgical treatment |  | class_or_procedure_seed | PRAC-ANO10 |
| Systemic corticosteroids |  | class_or_procedure_seed | PRAC-OTC |
| Testicular biopsy & sperm extraction |  | class_or_procedure_seed | PRAC-CFTR-F508del |
| Tezacaftor/ivacaftor |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| thickened feeds |  | class_or_procedure_seed | PRAC-OTC |
| throwing a child in the air |  | class_or_procedure_seed | PRAC-COL1A1 |
| total energy |  | class_or_procedure_seed | PRAC-OTC |
| transcranial magnetic stimulation |  | class_or_procedure_seed | PRAC-ANO10 |
| tricyclic antidepressants |  | accepted_class_combination_or_unresolved_name | PRAC-COL1A1 |
| trihexiphenidyl |  | accepted_class_combination_or_unresolved_name | PRAC-KMT2B |
| ureteroscopy |  | class_or_procedure_seed | PRAC-AGXT-c33dup, PRAC-AGXT-c508GA |
| Vanzacaftor/tezacaftor/deutivacaftor |  | accepted_class_combination_or_unresolved_name | PRAC-CFTR-F508del |
| walkers |  | class_or_procedure_seed | PRAC-KMT2B |
| waterbed, adjustable air mattress, or viscoelastic foam mattress |  | class_or_procedure_seed | PRAC-COL1A1 |
| weight control |  | class_or_procedure_seed | PRAC-ANO10 |
| wheelchair customizations |  | class_or_procedure_seed | PRAC-COL1A1 |
| wheelchair or scooter |  | class_or_procedure_seed | PRAC-COL1A1 |
| wheelchairs |  | class_or_procedure_seed | PRAC-COL1A1 |
| wrist or wrist & thumb braces |  | class_or_procedure_seed | PRAC-COL1A1 |
| Zinc supplementations |  | class_or_procedure_seed | PRAC-CFTR-F508del |

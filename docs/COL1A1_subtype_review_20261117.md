# COL1A1 18项MONDO亚型预审：未应用新排除规则

仅使用登记原文、项目MONDO SSSOM映射和OLS层级，未调用模型。每个试验按两个病人诊断分支分别列出。此表是改代码前的报告，不是已发布的Known exclusion。

重要限制：vascular EDS的MONDO ID有本地映射，但OLS层级请求连续超时；未把失败返回当成空祖先。hEDS/HSD纳入条件存在明确“或”，HSD尚未可靠映射，所以不能仅据hEDS为兄弟就对整个试验新增排除。STABLE登记虽然宽泛列EDS，实际纳入条款是hEDS/HSD；不能仅凭宽泛Condition放行。

| Trial | 病人诊断/ID | 试验目标疾病 | MONDO ID | 关系 | 拟定结果 |
| --- | --- | --- | --- | --- | --- |
| NCT02050113 | 经典型 EDS / MONDO:0007522 | Ehlers-Danlos syndrome（宽泛EDS；其他靶疾病/症状见原始列表） | MONDO:0020066 | 祖先 | 保留；其他入排标准不变，未映射项未知，不宣称全部满足 |
| NCT02050113 | 关节松弛型 EDS 1型 / MONDO:0020521 | Ehlers-Danlos syndrome（宽泛EDS；其他靶疾病/症状见原始列表） | MONDO:0020066 | 祖先 | 保留；其他入排标准不变，未映射项未知，不宣称全部满足 |
| NCT05212129 | 经典型 EDS / MONDO:0007522 | hEDS 或 HSD（按纳入诊断条款；登记Condition另有宽泛病名） | hEDS: MONDO:0007523；HSD: 未映射 | hEDS为兄弟；HSD无法映射 | conditional；不能把hEDS/HSD的或关系当作仅hEDS而直接排除 |
| NCT05212129 | 关节松弛型 EDS 1型 / MONDO:0020521 | hEDS 或 HSD（按纳入诊断条款；登记Condition另有宽泛病名） | hEDS: MONDO:0007523；HSD: 未映射 | hEDS为兄弟；HSD无法映射 | conditional；不能把hEDS/HSD的或关系当作仅hEDS而直接排除 |
| NCT05432466 | 经典型 EDS / MONDO:0007522 | Vascular Ehlers-Danlos syndrome | MONDO:0017314 | 无法核实兄弟层级（ID已映射；非本身/非祖先已核实） | conditional；OLS祖先/父节点接口超时，不能以空祖先列表判排除 |
| NCT05432466 | 关节松弛型 EDS 1型 / MONDO:0020521 | Vascular Ehlers-Danlos syndrome | MONDO:0017314 | 无法核实兄弟层级（ID已映射；非本身/非祖先已核实） | conditional；OLS祖先/父节点接口超时，不能以空祖先列表判排除 |
| NCT05994664 | 经典型 EDS / MONDO:0007522 | Vascular Ehlers-Danlos syndrome | MONDO:0017314 | 无法核实兄弟层级（ID已映射；非本身/非祖先已核实） | conditional；OLS祖先/父节点接口超时，不能以空祖先列表判排除 |
| NCT05994664 | 关节松弛型 EDS 1型 / MONDO:0020521 | Vascular Ehlers-Danlos syndrome | MONDO:0017314 | 无法核实兄弟层级（ID已映射；非本身/非祖先已核实） | conditional；OLS祖先/父节点接口超时，不能以空祖先列表判排除 |
| NCT07464093 | 经典型 EDS / MONDO:0007522 | hEDS 或 HSD（按纳入诊断条款；登记Condition另有宽泛病名） | hEDS: MONDO:0007523；HSD: 未映射 | hEDS为兄弟；HSD无法映射 | conditional；不能把hEDS/HSD的或关系当作仅hEDS而直接排除 |
| NCT07464093 | 关节松弛型 EDS 1型 / MONDO:0020521 | hEDS 或 HSD（按纳入诊断条款；登记Condition另有宽泛病名） | hEDS: MONDO:0007523；HSD: 未映射 | hEDS为兄弟；HSD无法映射 | conditional；不能把hEDS/HSD的或关系当作仅hEDS而直接排除 |
| NCT07626957 | 经典型 EDS / MONDO:0007522 | hEDS 或 HSD（按纳入诊断条款；登记Condition另有宽泛病名） | hEDS: MONDO:0007523；HSD: 未映射 | hEDS为兄弟；HSD无法映射 | conditional；不能把hEDS/HSD的或关系当作仅hEDS而直接排除 |
| NCT07626957 | 关节松弛型 EDS 1型 / MONDO:0020521 | hEDS 或 HSD（按纳入诊断条款；登记Condition另有宽泛病名） | hEDS: MONDO:0007523；HSD: 未映射 | hEDS为兄弟；HSD无法映射 | conditional；不能把hEDS/HSD的或关系当作仅hEDS而直接排除 |
| NCT07688096 | 经典型 EDS / MONDO:0007522 | Ehlers-Danlos syndrome（宽泛EDS；其他靶疾病/症状见原始列表） | MONDO:0020066 | 祖先 | 保留；其他入排标准不变，未映射项未知，不宣称全部满足 |
| NCT07688096 | 关节松弛型 EDS 1型 / MONDO:0020521 | Ehlers-Danlos syndrome（宽泛EDS；其他靶疾病/症状见原始列表） | MONDO:0020066 | 祖先 | 保留；其他入排标准不变，未映射项未知，不宣称全部满足 |
| NCT07697573 | 经典型 EDS / MONDO:0007522 | Vascular Ehlers-Danlos syndrome | MONDO:0017314 | 无法核实兄弟层级（ID已映射；非本身/非祖先已核实） | conditional；OLS祖先/父节点接口超时，不能以空祖先列表判排除 |
| NCT07697573 | 关节松弛型 EDS 1型 / MONDO:0020521 | Vascular Ehlers-Danlos syndrome | MONDO:0017314 | 无法核实兄弟层级（ID已映射；非本身/非祖先已核实） | conditional；OLS祖先/父节点接口超时，不能以空祖先列表判排除 |
| NCT07743229 | 经典型 EDS / MONDO:0007522 | Ehlers-Danlos syndrome（宽泛EDS；其他靶疾病/症状见原始列表） | MONDO:0020066 | 祖先 | 保留；其他入排标准不变，未映射项未知，不宣称全部满足 |
| NCT07743229 | 关节松弛型 EDS 1型 / MONDO:0020521 | Ehlers-Danlos syndrome（宽泛EDS；其他靶疾病/症状见原始列表） | MONDO:0020066 | 祖先 | 保留；其他入排标准不变，未映射项未知，不宣称全部满足 |

判定方案待审：目标本身/祖先可保留；可靠映射且所有诊断备选均是兄弟时才加 trial targets another subtype (<名称>)；未映射或层级不可核实仍未知/conditional，不能凭名称相似度补全。新规则尚未实现或运行，故15例本轮新增Known exclusions为0；正式应用后再输出逐病例变化清单。

完整登记Condition列表见 runs/review6-20261117/COL1A1_subtype_proposal.json；MONDO SSSOM快照为2026-11-16，患者与hEDS的OLS祖先证据保存在同目录ancestors.json。

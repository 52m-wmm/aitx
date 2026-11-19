# KMT2B v6精简分块单票结果 v1.0 — 2026-11-19

**四份来源全部完成，7/7块，无截断、无重试，付费已停止。** 本轮$0.030894018，小于最新授权的单次$0.06。源抽取完成不等于完整Step3a验收，单票不证明稳定性通过。

## 诊断与实现

详见[kmt2b_chunking_diagnosis_20261119.md](kmt2b_chunking_diagnosis_20261119.md)。v6本次原截断reasoning/content=16384/0；v5历史两次截断分别15237/1147（核心段）及15931/453（DD/ID），并非都在核心段。两次成功重试分别13472/2045和13886/805。核心正文7115字符，DD/ID3677；块上限3500、按完整段/表行确定性切分，四源1/3/2/1块，原文无缺失/重叠。

执行前已展示精简后的新增规则，版本3a-v6.1，含义保持。分块与精简共同变化，不能区分哪一项造成效果。生产入口已接入无损分块，跨块条目保留真实调用出处后进入原有行动合并规则；本实验只源抽取和离线同名分组，不触发同义模型或临床分类。

## 费用、模型和执行范围

非高峰，执行前账户可用、余额17.64CNY，nohup+caffeinate。固定原四份来源正文逐字一致；模型deepseek-flash、temperature0、16384/必要重试32768不变。Prompt revision与每块输入SHA固定，原始7响应全部保存；响应缓存复用0（服务端输入token缓存不等于复用回答）。

7次真实请求、peak0、usage全部完整；50351总输出tokens中47090 reasoning、3261内容。各次总输出/reasoning为62/56、6627/5544、11446/10918、4163/3819、16107/15549、1159/1107、10787/10097。DD/ID第一块仍达到16107，距16384仅277；本次无截断不保证后续不会截断。

实际$0.030894018，本次剩余$0.029105982不构成续跑授权。此前KMT2B系列$0.052796658加本轮累计$0.083690676（本轮按用户最新单次$0.06阶段授权执行，旧费保留）；原$0.50母实验累计$0.299763519、余$0.200236481。账本runs/step3_remaining_budget.json已更新；未用余额接口延迟代替usage计费。

## 行动召回

| 重点 | 结果 | 原文与粒度 |
|---|---|---|
| GPi-DBS | 有 | 原文句同时命名两种DBS；返回完整解剖名称但省略GPi-DBS括号简称 |
| subthalamic nucleus DBS | 有 | 同句独立返回 |
| 504 plan | **未独立抽出** | 同句只返回assistive technology devices，不能当作504计划完整召回 |
| DDA enrollment | 有 | “Developmental Disabilities Administration (DDA) enrollment is recommended.” |
| ankle-foot orthoses / walkers | **未分别抽出** | 仅返回adaptive aids；原句明确举出两种器具，具体度缺失未解决 |
| IEP | 有 | 全称和明确资格条件均保留 |

所有输出33次条目提及，按原始名称规范化为30组；同名PT/OT/feeding在不同来源的提及保留所有原文条件，没有挑票。对旧三票并集的纯名称差别还包含缩写、括号、拼写和drug类别名，不能直接算作真实行动新增/删除。

新输出assistive technology devices有原文支持，但它不能替代遗漏的504 plan。antibiotics与旧prophylactic antibiotics、anticholinergic与旧antimuscarinic类别名的对应只用于本报告基于同句原文的审阅，不改正式Key。

孕期原文关于metoclopramide/domperidone/ondansetron诱发肌张力障碍的警示未被抽出。它们在既有规则中只可能是附注，不得据此新建独立行动；本轮不声称风险已消除。原始trixhexyphenidyl拼写沿用冻结来源，与历史trihexyphenidyl形式单列，不强改药物归一化。

## 条件数：不是越少越正确

本票原始条件变体28，按同一保守规范化规则仍28。旧v5三张单票分别38/50/45（规范化38/47/45）；旧三票并集86、规范化66。新单票与旧三票并集分母不同，不能用86→28宣称准确性或稳定性改善。全部字段、原句和实际Call ID在inspection.json中保留，未删除旧shadow中的医学条件。

## 三项感染风险误抽

共同原句：

> For individuals with respiratory compromise from chest deformities related to scoliosis, prophylactic antibiotics during the winter months, regular chest physical therapy, and influenza immunizations should be considered because of the increased risk of pulmonary infections.

| 行动 | 新版表现/条件 | 审阅 |
|---|---|---|
| chest physical therapy | respiratory compromise；保留相同使用情境 | 不再把pulmonary infections当现患，观察到改善；表现与情境内容重复仍待清理，未改临床规则 |
| influenza immunizations | manifestation空；保留respiratory compromise使用情境 | 不再把pulmonary infections当现患，观察到改善 |
| antibiotics（原句prophylactic antibiotics） | **manifestation仍为pulmonary infections**；呼吸受限、冬季均保留 | **误抽未消失**；because of increased risk不是病人已感染 |

因此2/3改善、1/3仍错误，不能宣称本问题全部修复。标签变为antibiotics不影响依据同一句原文定位这一误抽。

## 新增、遗漏和范围改变

- **明确限制漏抽**：anticholinergic agents引文含“should be considered first-line pharmacologic treatment in individuals with a confirmed diagnosis of a KMT2B-related disorder”，但requirements为空。确诊限制不能仅因为本病例恰好已确诊就从抽取中忽略。待复核，不自动将其视为无条件适用。
- **局部范围漏抽**：PT/OT/speech的IEP句含“to the extent that the need affects the child's access to academic material”，新版没有抽出。其是否应作为局部服务范围限制需保留审阅，不能宣称已正确删除。
- **明确条件保留**：IEP仍有“for those who qualify based on established motor, language, social, or cognitive delay”；feeding仍有safe to eat by mouth及poor oral motor control；抗生素仍有冬季及呼吸受限。ABA仍保留Children。
- **章节范围不再由模型复制**：DD/ID、Ages 0–3/3–5等不再出现在这些条目的LLM条件中，符合新版抽取边界。但本实验没有跑临床组装，不能宣称小标题条件已实际补齐。原条件仍保留在历史shadow，后续组装按既有代码处理；未被已有人群规则覆盖的疾病/表现范围继续待审。
- **DBS范围变化**：dystonia未在本次DBS的manifestation出现，原句本身仅描述使用，肌张力障碍来自小标题；不能因此把DBS定为不适用或无条件适用。旧R15与患者条件保留，不新增核查。
- **风险/目的区别有所改善**：adaptive aids的ambulation、PT预防骨科并发症不再被写成已有表现；但是否应保留其他局部必要条件仍逐项审阅，不以删条件奖励一致率。
- **新增描述性条件待审**：孕期药物条目将“affected mother”写成sex=female，来自先例母婴结局描述，不当然是独立适用门槛；孕期句仍只可作附注。所有未解决安全/资格分歧均保留needs_review，不产生新的临床结论。

## 旧42组分歧逐项投影

old42_review.json保留每组旧原文/Evidence ID、当前原句/Call ID及审阅，不用多数票判医学正确性：

| 观察类别 | 旧条件组数 |
|---|---:|
| 保留或换表达 | 11 |
| 章节/段落范围不再推断，代码处理尚未测 | 10 |
| 行动未召回或名称尚未唯一对上 | 12 |
| 同句确诊限制漏抽（同一医学条件的3种旧字段表示） | 3 |
| IEP局部服务范围待审 | 3 |
| 功能目标不再作表现 | 1 |
| 个体化治疗依据不再作表现 | 1 |
| 该条目感染风险不再作现患 | 1 |

总计42，不代表42个独立医学条件，更不代表42项已修复。另两项感染误抽旧三票均出现，不全属于这42组，故单独列三项风险核对。

## 验收边界与留存

离线1297项通过，覆盖无损分块/表行边界/出处、已有合并和临床规则。正式15份Ledger及全部历史/current基线SHA核对未变；since-before status_diff变化0，accepted-current保留全部既存差异。没有新的医学结论，没有跑其他Step、AGXT、新上下文/同义核查或报告生成，没有更新Accepted。

实验runs/kmt2b-v6-chunked-20261119保存：diagnostics.json、chunk_manifest.json、prompt_before/after、完整7块输入/响应、inspection.json、old42_review.json、费用、停止状态及status_diff。scripts/inspect_kmt2b_chunks.py完全离线复算。此轮只验证精简分块的初步效果：成功完成、截断未复现；行动/条件完整性仍有已知缺口，不宣称稳定性通过。

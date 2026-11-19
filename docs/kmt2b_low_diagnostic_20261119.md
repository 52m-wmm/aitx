# KMT2B DD/ID low档单次诊断 v1.0 — 2026-11-19

**本次完成，但行动门槛未通过，已停止。** 不将3a默认改为low，不改变原截断重试策略，不补第二票，不跑第三票，不动用后续$0.05，不改Prompt、临床规则或Accepted。

## 方法、费用与tokens

仅此前失败的DD/ID第一块（正文3191字符）一次真实执行；同3a-v6.1 Prompt、来源、模型deepseek-flash、temperature0。请求reasoning_effort=low，未复用LLM响应，无重试。非高峰，nohup+caffeinate，先核实账户可用余额17.23CNY。

单次$0.01预算下，原16384输出上限的预留超过额度；执行前已明确将本次诊断上限设14000、不重试，预留未超过$0.01。这是与历史档位比较的额外参数差异，不能把一切差异都归因于low。实际输出7401，未触及14000；没有硬截断。

| 指标 | 值 |
|---|---:|
| 实际请求／重试 | 1／0 |
| finish_reason | stop |
| prompt tokens | 1360（全部未缓存） |
| reasoning tokens | 6832 |
| 最终内容tokens | 569 |
| 总输出tokens | 7401 |
| 费用 | $0.004644600 |
| usage缺失／高峰请求 | 0／0 |

接口返回模型名为deepseek-flash；请求low有记录，但API未提供可独立核验的权重/effort内部配置。只按实际请求参数、返回内容和usage比较，不假定服务内部细节。

此前同一3191字符块的v6.1完整第一票是15549 reasoning / 558内容（16107总输出），第二票失败为16384／0。本次内容更短不代表更完整，reasoning仍占大头。

## 行动逐项比较（仅相同输入范围）

诊断前已固定8个清楚命名的目标行动，未在观察结果后挑选基准。DDA在另一块，本次不要求召回。两份v5历史完整整节回答按引文能否在本次块内找到限定比较范围，不把范围外条目算作low遗漏。

| 行动 | v6.1完整第一票 | v5历史票1 | v5历史票2 | 本次low |
|---|---|---|---|---|
| early intervention program | 有 | 有 | 有 | 有 |
| feeding therapy | 有 | 有 | 有 | 有 |
| developmental preschool | 有 | 有 | 有 | 有 |
| individualized education plan (IEP) | 有 | 有 | 有（IEP） | **无独立条目** |
| physical therapy | 有 | 有（PT） | 有 | 有 |
| occupational therapy | 有 | 有（OT） | 有 | 有 |
| speech services | 有 | 有 | 有 | 有 |
| 504 plan | 无 | 有 | 无 | **无独立条目** |
| assistive technology devices（非预定必需项） | 有 | 无 | 无 | 有 |
| home-based services（额外历史观察） | 无 | 无 | 有 | 无 |

low返回7个条目；第一票同块8个。PT等条目的引文中出现IEP，不等于IEP行动本身已返回；辅助技术设备也不能代替504计划。省略IEP是相对同Prompt、同输入的完整第一票的清楚召回退步。504缺口仍在；v5第二份还出现home-based services，本次未抽出，额外记录而不修改预先设定的门槛。

因此“完成且行动无明显遗漏”不成立。本次不能触发默认low或后续续跑授权。并非由一次诊断证明low普遍更差，而是本次预设门槛未通过。

## 条件逐项比较

- **IEP资格条件丢失**：第一票保留“for those who qualify based on established motor, language, social, or cognitive delay”，low整个独立IEP条目缺失，相应必要条件也未返回。原句完整存在输入中，不能归因于分块漏字或当作不需要该条件。
- **PT/OT/speech局部范围有所改善**：low均明确抽出“to the extent that the need affects the child's access to academic material”；第一票这些requirements为空。v5票1写较短的“in the IEP”，v5票2保留完整学业访问限定。改善不能抵销IEP行动遗漏而宣布通过。
- **504句中的对象条件**：low在assistive technology devices条目中抽出“who require accommodations or modifications”；v5票1将此条件挂在504 plan下。它不是同一个行动归属，不能自动视作504完整召回。按当前examples规则，这种成员条件应保留出处待审，不能套成整个父类的资格。
- **age/DD/ID标题范围**：low与v6.1完整第一票均不把它们复制进这些条目；v5两票对early intervention/feeding/preschool抽出了年龄界限。此差异符合v6.1把章节人群条件交回代码的边界，但本次没有运行组装，不能宣称条件已由代码实际补齐。
- **home-based services**：v5票2含“for children too medically unstable to attend”，本次无对应条目；作为历史附加缺口保留，不把来源中的限制删掉。

所有低档引文均能在该块找到。comparison.json为每个行动保存四份回答的原始name/kind/quote/manifestation/requirements；不是只给名称或把所有条件差异混为错误。只做源文比较，不计算新的患者适用状态。

## 投票和续跑状态

| 数据 | 组成及使用 |
|---|---|
| 已完成第一票 | 7块原档，保留 |
| 第二票 | 6块原档完整，1块仍缺；本次low诊断因门槛失败未补入 |
| 第三票 | 未执行 |
| 本次low诊断 | 1块独立观察，单独保留，不当成额外完整票 |

未产生获准进入合并的混档完整票。没有重复抽同一诊断并挑选结果，没有用low响应掩盖原截断。原档指此前未指定reasoning_effort的既有调用参数，不将服务内部行为当成已核实事实。

本次$0.01剩余$0.005355400不自动续用；后续$0.05支出0。母$0.50实验累计$0.335499537，剩余$0.164500463。原始响应、完整输入、参数、usage、预设门槛、逐项比较在runs/kmt2b-low-diagnostic-20261119。

## 工程状态与限制

“DD/ID块持续推理失控（3/3次）”已写入known_limitations，并逐项注明：三次均高reasoning，其中一次完成、两次截断；不是三次完全相同输入或三次都截断。新low诊断减少了消耗，却没有通过行动完整性门槛，因此不自动改Prompt/默认档位。

正式15例Ledger与全部历史/current基线不变，since-before diff0，Accepted既有差异保留。AGXT未执行或报价，工程版本未冻结。此诊断不构成稳定性或医学正确性通过。

# KMT2B截断诊断与分块 v1.0 — 2026-11-19

## 零费用诊断

下表内容tokens=completion_tokens−reasoning_tokens（服务端usage定义），不是截断字符串字符数。历史两个重试来自v5第一次独立运行，不是两个核心治疗段都截断。

| 请求 | 来源 | Prompt tokens | reasoning | 内容tokens | 总输出 |
|---|---|---:|---:|---:|---:|
| v5截断1 | 核心Treatment of Manifestations | 2357 | 15237 | 1147 | 16384 |
| v5重试1成功（上限32768） | 同核心段 | 2357 | 13472 | 2045 | 15517 |
| v5截断2 | DD/ID Management Issues | 1456 | 15931 | 453 | 16384 |
| v5重试2成功（上限32768） | 同DD/ID段 | 1456 | 13886 | 805 | 14691 |
| v6本次截断 | 核心Treatment of Manifestations | 2390 | 16384 | 0 | 16384 |

历史调用定位依据session成功重试的时间窗、call_id、原输入和底层llm_calls；完整usage和时间记录保存在本次实验diagnostics.json。v6的32768重试在预算前停止，未发出。三次截断reasoning占比分别93.00%、97.24%、100%，证明额度主要被思考占用；不证明唯一原因是Prompt。核心段user输入7165字符，其中正文7115；DD/ID为3793／3677。其他两段正文250和1510。

## 确定性分块

每块正文上限3500字符，小于核心正文一半3557.5。GeneReviews已有显示格式是一段或完整表行一行，按这些原子行打包，优先在适当小标题边界断开。保留全部空白/换行与字符，记录[start,end)偏移，不在句子、表行中截断；单个原子单位超过上限明确报错，不静默裁切。请求重复的Section元数据不属于原文正文，覆盖检查以正文为单位。

四源固定正文的块偏移：

- Management：0–250。
- Treatment：0–3227、3227–6580、6580–7115。
- DD/ID：0–3191、3191–3677。
- Pregnancy：0–1510。

全部块串接与旧固定正文严格相等，邻接边界相等，无缺失/重叠。原来生产入口[:9000]截取改为无损全覆盖分块。抽取条目携带对应chunk真实调用出处，再进入原有place/action规则，不在抽取层用多数或类型优先级删条目。跨块同名候选留所有原始条件和来源，临床组装沿用原合并规则。

## v6提示词精简（已于执行前展示）

版本标记3a-v6.1，保留v6的规则含义。新增段落替换为：

> Extract conditions only from the action's own sentence or complete table row. Do not infer conditions or manifestations from headings, context annotations or other paragraphs; code handles population headings. Prevention targets and risk rationales are not existing patient findings ("to prevent X", "because of the risk of X").

其余schema和规则不变；模型deepseek-flash、temperature0、16384/32768重试参数不变。精简与分块同时变化，本轮结果不能单独归因于某一个改动。完整Prompt前后文本在实验prompt_before.txt/prompt_after.txt。

## 执行边界与离线验证

用户最新授权是本次分块重跑$0.06硬上限，含重试，旧费用不清零；仍从原$0.50实验余额内扣，预算按每请求最坏费用预留。旧实验KMT2B累计$0.052796658单列，新的$0.06作为本次阶段帽；不把旧上限的未用部分当新增权限。非高峰，先核实余额，nohup+caffeinate，7个首发请求，缺额度停。只源抽取，不做新上下文、同义合并、其他Step或AGXT，不修改医学规则或Accepted。

分块回归先复现缺失实现的3个失败测试，再实现转绿；全量1297项通过。测试覆盖长文本、完整表行、偏移连续、无丢失/重叠、超长原子明确停止及每块调用出处。实验runs/kmt2b-v6-chunked-20261119留存诊断、块映射、输入SHA、执行与费用。

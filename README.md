# AI-Tx Challenge 流水线

按节点逐步构建。每个节点有明确的输入、输出和验收标准，验收通过才进入下一步。

| 步骤 | 内容 | 状态 |
| --- | --- | --- |
| 1 | 变异解析（确定性计算，无 LLM） | ✅ 已验收（2026-10-28）：离线测试 49 个全过；联网验收 15 个变异一致性校验全过、11 项标准答案全对 |
| 2 | 疾病归一化 | ✅ 联网验收 HARD 全过（2026-10-28）：练习病例 7 个标准答案全对，两个陷阱病例正确处理，缓存重跑一致；离线测试共 104 个全过。待办：不用缓存的 3 次重跑（DeepSeek 余额不足中断）、契约 v2.1 补充规则待审 |
| 3 | 疗法匹配 | 未开始 |
| 4 | 查现成方案（试验、获批药物、文献） | 未开始 |
| 5 | 对照病人条件 + 报告组装 | 未开始 |

## 环境要求

- Python 3.9 以上（Mac 自带的 `python3` 即可）
- 第 1 步**只用标准库**，不需要安装任何包
- 运行测试需要 `pytest`：`pip3 install pytest`

## 第 1 步：怎么运行

在项目根目录（本文件所在目录）执行：

```bash
# 1. 离线单元测试（不联网，约 1 秒）
python3 -m pytest -q

# 2. 联网验收：用官网示例的标准答案核对真实数据
python3 scripts/acceptance_step1.py

# 3. 对四个评测病例生成变异解析结果
python3 scripts/step1_variant.py data/cases/aitx_final_patients.json
```

结果在 `out/step1/<病例ID>.json`。字段含义见 `docs/step1_variant_contract.md`。

### 如果报 SSL 证书错误

用 python.org 安装包装的 Python 需要先运行一次证书安装：
在 Finder 打开"应用程序 → Python 3.x"，双击 `Install Certificates.command`。

### 可选：NCBI API key

不设置也能跑（每秒 3 次请求的限额足够）。如需更高限额：

```bash
export NCBI_API_KEY=你的key
```

## 第 2 步：怎么运行

需要联网和 LLM key（症状提取用到 LLM，其余全部是确定性计算）：

```bash
export AITX_LLM_API_KEY=你的key

# 1. 联网验收：练习病例的标准答案 + 评测病例人工核对项
python3 scripts/acceptance_step2.py
#    加 --fresh-llm 则不用 LLM 缓存，重新调用 3 次，报告一致性
python3 scripts/acceptance_step2.py --fresh-llm

# 2. 对四个评测病例生成疾病归一化结果
python3 scripts/step2_disease.py data/cases/aitx_final_patients.json
```

结果在 `out/step2/<病例ID>.json`，另有 `out/step2/sources_manifest.json` 记录所用数据快照。
字段含义见 `docs/step2_disease_contract.md`。

首次运行会下载约 125 MB 整包数据（GenCC、ClinGen、HPO、MONDO、Orphanet、GeneReviews、OMIM mim2gene）
到 `.cache/datasets/<名称>/<日期>/`，断线自动续传，下载后逐个做完整性校验；超过 7 天自动刷新。
正式提交时用 `AITX_DATASET_SNAPSHOT=YYYY-MM-DD` 固定一份快照。

## 目录结构

```
aitx/
  http.py              带磁盘缓存的 HTTP 请求，记录每个来源的访问时间
  llm.py               统一的模型接口（换模型只改环境变量）
  variant/
    hgvs.py            c. 和 p. 写法解析
    transcript.py      获取并解析 RefSeq 转录本记录
    profile.py         生成 VariantProfile：分类、外显子、NMD、机制假设、校验
  disease/
    datasets.py        整包数据下载（断点续传）、完整性校验、日期快照
    sources.py         各数据文件的解析器，每条记录带行号用于引用
    hpo.py             HPO 本体、信息量、症状相似度打分
    live.py            实时 API：ClinVar、MONDO（OLS4）、HGNC
    extract.py         LLM 提取症状和病人基本事实 + 逐条确定性校验
    resolve.py         候选疾病、证据强度、ClinVar 关联、遗传方式、首选选择
    pipeline.py        组装 DiseaseResolution 输出和校验
scripts/
  step1_variant.py     第 1 步命令行入口
  acceptance_step1.py  第 1 步联网验收
  step2_disease.py     第 2 步命令行入口
  acceptance_step2.py  第 2 步联网验收
data/cases/            四个评测病例 + 官网示例病例
docs/                  每一步的契约文档
tests/                 离线测试（合成转录本、合成本体，不联网）
```

## 模型配置（第 2 步起用到）

```bash
export AITX_LLM_BASE_URL=https://api.deepseek.com
export AITX_LLM_MODEL=deepseek-flash
export AITX_LLM_API_KEY=你的key
# 可选：服务端返回的模型名不以此开头就报错，防止别名被悄悄切换
export AITX_EXPECT_MODEL_PREFIX=deepseek-v4.1-flash
```

每次调用都会记录到 `runs/llm_calls.jsonl`，包括服务端实际返回的模型名。

# AI-Tx Challenge 流水线

按节点逐步构建。每个节点有明确的输入、输出和验收标准，验收通过才进入下一步。

| 步骤 | 内容 | 状态 |
| --- | --- | --- |
| 1 | 变异解析（确定性计算，无 LLM） | ✅ 已验收（2026-10-28）：离线测试 49 个全过；联网验收 15 个变异一致性校验全过、11 项标准答案全对 |
| 2 | 疾病归一化 | 未开始 |
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

## 目录结构

```
aitx/
  http.py              带磁盘缓存的 HTTP 请求，记录每个来源的访问时间
  llm.py               统一的模型接口（换模型只改环境变量）
  variant/
    hgvs.py            c. 和 p. 写法解析
    transcript.py      获取并解析 RefSeq 转录本记录
    profile.py         生成 VariantProfile：分类、外显子、NMD、机制假设、校验
scripts/
  step1_variant.py     第 1 步命令行入口
  acceptance_step1.py  第 1 步联网验收
data/cases/            四个评测病例 + 官网示例病例
docs/                  每一步的契约文档
tests/                 离线测试（合成转录本）
```

## 模型配置（第 3 步之后才用到）

```bash
export AITX_LLM_BASE_URL=https://api.deepseek.com
export AITX_LLM_MODEL=deepseek-flash
export AITX_LLM_API_KEY=你的key
# 可选：服务端返回的模型名不以此开头就报错，防止别名被悄悄切换
export AITX_EXPECT_MODEL_PREFIX=deepseek-v4.1-flash
```

每次调用都会记录到 `runs/llm_calls.jsonl`，包括服务端实际返回的模型名。

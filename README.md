# AI-Tx Challenge 流水线

按节点逐步构建。每个节点有明确的输入、输出和验收标准，验收通过才进入下一步。

| 步骤 | 内容 | 状态 |
| --- | --- | --- |
| 1 | 变异解析（确定性计算，无 LLM） | ✅ step1.1 已验收（2026-11-03，tag `step1.1-accepted`）：新增自检 6 独立重新翻译，16 个变异全部与 p. 写法一致，反向验证全部判 fail；输出另含外显子布局与 AlphaFold 结构事实（schema v1.2） |
| 2 | 疾病归一化 | ✅ 已验收（2026-10-28）：不用缓存的联网验收硬性项全过（练习病例 7 个标准答案、两个陷阱病例、ClinVar 精确匹配、缓存重跑一致）；离线测试 135 个全过；症状提取测试集精确率/召回率 1.0；已知局限见契约 |
| 2.1 | Step 2 局限改进 | ✅ 已验收（2026-11-03，tag `step2.1-accepted`）：否定词规则、起病年龄映射到 HPO 起病术语、难题测试集（见 Step 2 契约 v2.5） |
| 2.5 | 审查用查看页面 | ✅ 本地 Web 应用 + 静态快照导出；Step 1 三张平面图与 3D 结构已接入 |
| 3 | 疗法匹配 | 未开始（3.0 契约待写，待办见 `docs/step3_contract_todo.md`） |
| 4 | 查现成方案（试验、获批药物、文献） | 未开始 |
| 5 | 对照病人条件 + 报告组装 | 未开始 |

## 环境要求

- Python 3.9 以上（Mac 自带的 `python3` 即可）
- 流水线**只用标准库**，不需要安装任何包
- 运行测试需要 `pytest`：`pip3 install pytest`（查看应用的测试另需 `requirements-viewer.txt` 和 `httpx`，未安装时自动跳过）

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

- 自检 6（独立重新翻译）：按 c. 写法修改 NCBI mRNA，重新翻译到第一个终止密码子，与输入的 p. 写法比对，不一致判 fail。
- 结构事实：从 UniProt / AlphaFold DB 取预测结构（缓存在 `.cache/alphafold/`），记录变异位置的 pLDDT、相对溶剂可及性（RSA）和 8 Å 内的邻居。
  只作背景信息，取不到不会让第 1 步失败；设置 `AITX_SKIP_STRUCTURE=1` 可跳过。

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

# 2. 症状提取测试集（精确率、召回率、假阳性）
python3 scripts/eval_extraction.py

# 3. 对四个评测病例生成疾病归一化结果
python3 scripts/step2_disease.py data/cases/aitx_final_patients.json
```

结果在 `out/step2/<病例ID>.json`，另有 `out/step2/sources_manifest.json` 记录所用数据快照。
字段含义见 `docs/step2_disease_contract.md`。

首次运行会下载约 125 MB 整包数据（GenCC、ClinGen、HPO、MONDO、Orphanet、GeneReviews、OMIM mim2gene）
到 `.cache/datasets/<名称>/<日期>/`，断线自动续传，下载后逐个做完整性校验；超过 7 天自动刷新。
正式提交时用 `AITX_DATASET_SNAPSHOT=YYYY-MM-DD` 固定一份快照。

## 整条流水线：从任意一步开始

```bash
# 从第 1 步跑到当前已实现的最后一步
python3 scripts/run_pipeline.py data/cases/aitx_final_patients.json

# 复用已有的第 1 步结果，只重跑第 2 步及以后
python3 scripts/run_pipeline.py data/cases/aitx_final_patients.json --from-step 2

# 只跑某个病例（在全部病例文件里按编号查找），可重复 --case
python3 scripts/run_pipeline.py --case PRAC-OTC --from-step 2
```

每一步的输出 `out/step<N>/<病例ID>.json` 都带 `_meta`：生成它的病例输入指纹、所依赖的上游输出文件指纹、代码版本（git commit）。
用 `--from-step N` 时会核对前面各步的输出：缺失、由不同的病例输入生成、或建立在已被重跑的旧上游输出之上，都会报 `[STALE]` 并提示从哪一步重跑，**不会悄悄用旧结果**。
`scripts/step1_variant.py`、`scripts/step2_disease.py` 仍可单独运行用于调试，但它们的输出没有 `_meta`，流水线不会复用。

LLM 缓存（`.cache/llm/`）的键包含模型名、API 地址、提示词版本和完整提示词正文；改提示词或换模型后自动失效。
每条缓存还记录调用参数（temperature 等），参数不同不复用；设置了 `AITX_EXPECT_MODEL_PREFIX` 时，由其他模型生成的缓存也不复用。

## 审查用查看页面（Step 2.5）

### 本地 Web 应用（实时查看、页面上重跑）

```bash
pip3 install -r requirements-viewer.txt   # 只有查看应用需要 FastAPI / uvicorn，流水线本身只用标准库
python3 scripts/viewer_app.py             # 打开 http://127.0.0.1:8765/ （只绑定本机）
```

- 每次请求现场读取 `out/step*/` 渲染页面，模板与静态导出共用（`build_viewer.py`），改模板后下次请求即生效。
- 结果文件或模板变化后，已打开的页面几秒内自动刷新（SSE）。
- 病例页有“从第 N 步重跑”按钮：后台执行 `python3 -u scripts/run_pipeline.py --case <ID> --from-step N`，日志实时显示，跑完自动刷新。
  会走到 LLM 步骤的按钮旁有提示；默认用缓存，勾选“不用缓存”需二次确认。同一病例同时只能有一个运行任务。
- 首页“运行状态”默认折叠（有任务运行时自动展开），显示正在运行的任务和最近 5 条记录；完整记录在顶部导航的“运行记录”页。
  记录在 `out/viewer_runs/history.jsonl`，日志在 `out/viewer_runs/<运行ID>.log`，最多保留 200 条，更早的连同日志自动删除。
- 病例页的 Step 1 部分有三张平面图（密码子对比、按比例的蛋白长度条、按真实长度的外显子图 + 拼接标记 + NMD 结论）
  和 3D 蛋白结构（AlphaFold 预测，3Dmol.js；错义变异标红并显示 8 Å 内邻居，截短丢失部分变灰，可切换按 pLDDT 着色）。
  3D 视图只在应用中可用，静态快照里显示结构事实表。
- 界面只调用命令行能做的事，验收仍用命令行脚本。重跑若需要真正调用 LLM，启动应用前先设置 `AITX_LLM_API_KEY`。

### 静态快照导出

```bash
python3 scripts/build_viewer.py      # 读取 out/step*/ 生成静态 HTML 快照（中英文都生成）
open out/review/index.html           # 快照列表，点最新的一份
```

每次生成一份快照 `out/review/<时间>/`（总表、每个病例一页、与上一份快照的对比页），不需要服务器。
每页右上角有 中文 / EN 开关，切换后停留在同一位置，浏览器会记住选择；`--lang en` 只改没有记住选择时的默认语言。
页面上的数字全部读自结果文件，不重新计算、不调用 LLM。病例结果需先用 `scripts/run_pipeline.py` 生成（带来源记录）。

## 目录结构

```
aitx/
  runmeta.py           各步输出的读写与来源记录（输入指纹、上游指纹、代码版本）
  http.py              带磁盘缓存的 HTTP 请求，记录每个来源的访问时间
  llm.py               统一的模型接口（换模型只改环境变量）
  variant/
    hgvs.py            c. 和 p. 写法解析
    transcript.py      获取并解析 RefSeq 转录本记录
    profile.py         生成 VariantProfile：分类、外显子、NMD、机制假设、校验
    translate.py       独立重新翻译（自检 6）：按 c. 改 mRNA、翻译到第一个终止
    structure.py       AlphaFold 结构事实：异构体位置映射、pLDDT、RSA、8 Å 邻居
  disease/
    datasets.py        整包数据下载（断点续传）、完整性校验、日期快照
    sources.py         各数据文件的解析器，每条记录带行号用于引用
    hpo.py             HPO 本体、信息量、症状相似度打分
    live.py            实时 API：ClinVar、MONDO（OLS4）、HGNC
    extract.py         LLM 提取症状和病人基本事实 + 逐条确定性校验
    resolve.py         候选疾病、证据强度、ClinVar 关联、遗传方式、首选选择
    pipeline.py        组装 DiseaseResolution 输出和校验
scripts/
  run_pipeline.py      整条流水线入口，支持 --from-step / --to-step
  build_viewer.py      审查页面模板（9 个视图 + Step 1 图示）+ 静态快照导出，输出到 out/review/
  viewer_app.py        本地 Web 应用：实时渲染、自动刷新、页面上重跑（调用 run_pipeline.py）
  step1_variant.py     第 1 步命令行入口
  acceptance_step1.py  第 1 步联网验收
  step2_disease.py     第 2 步命令行入口
  acceptance_step2.py  第 2 步联网验收
data/cases/            四个评测病例 + 官网示例病例（12 个，逐字取自官网）+ Phase 1 验证病例
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
# 可选：同时在途的 LLM 请求数（默认 4）；结果与串行完全相同，只影响速度
export AITX_LLM_CONCURRENCY=4
```

每次调用都会记录到 `runs/llm_calls.jsonl`，包括服务端实际返回的模型名。

并发：每个病例的 3 次抽样（各自带一次“从候选中选择”）同时进行；验收脚本和症状测试集评估还会让多个病例同时跑。
所有线程共用一个上限 `AITX_LLM_CONCURRENCY`（只限真正发出的请求，缓存命中不受限）。缓存键和抽样序号与串行时相同，
结果按病例和抽样序号的顺序汇总，所以输出与串行逐字节一致。`run_pipeline.py` 仍按病例依次运行，病例内部并发。

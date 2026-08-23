# Figure Skill

统一科研画图工作流：扫描论文和实验文件，生成需人工确认的面板计划，再通过确定性 SVG/Matplotlib 后端生成可编辑图、PDF、PNG、数据溯源和 QA 报告。

Current internal release: `v0.4.0`

## 团队安装

团队成员获得 `MWM-Research/Figure-Skill` 私有仓库权限后，只需：

```powershell
codex plugin marketplace add MWM-Research/Figure-Skill
codex plugin add figure-skill@mwm-research
```

安装后新建一个 Codex 任务，直接使用：

```text
使用 $figure-skill 根据我的研究材料生成科研图。
```

第一次执行时，插件会在用户的 Codex 目录下创建按版本隔离的 Python 环境并安装锁定依赖；不会修改成员自己的项目环境。后续调用直接复用该环境。基础绘图不要求配置 API Key，PaperBanana 和 AutoFigure-Edit 缺失时会显示为可选增强未启用。

更新 Marketplace：

```powershell
codex plugin marketplace upgrade mwm-research
codex plugin add figure-skill@mwm-research
```

## 当前能力

- CSV、TSV、JSON、JSONL、XLSX 数据画像
- Methods 文本中的常见架构实体和显式数据流提取
- `illustration`、`data-plot`、`edit`、`composite` 路由
- 单组/多组柱状图、折线图、散点图和逐数值 provenance
- 2-10 节点的可编辑 SVG 与 `.drawio` 架构图
- 经过人工确认的 SVG 精确文本/属性编辑及逐操作 provenance
- 单面板、横向、纵向和 2 列网格组装
- SVG、PDF、PNG 导出及结构/来源 QA
- Happy Figure、PaperBanana、AutoFigure-Edit 的安全隔离适配器

## 快速开始

```powershell
$FigureSkill = Resolve-Path .\plugins\figure-skill\skills\figure-skill
python "$FigureSkill\scripts\figure.py" doctor
```

也可以在 Windows PowerShell 中使用包装入口：

```powershell
& "$FigureSkill\scripts\figure.ps1" doctor
```

先生成计划：

```powershell
python "$FigureSkill\scripts\figure.py" workflow `
  --input .\manual-validation\cases\composite `
  --brief "Create a method architecture and accuracy comparison figure" `
  --output .\outputs\demo `
  --stop-after-plan
```

人工检查并清空 `open_questions` 后继续：

```powershell
python "$FigureSkill\scripts\figure.py" workflow `
  --plan .\outputs\demo\figure-plan.json `
  --output .\outputs\demo `
  --approve-plan
```

编辑已有 SVG 时，先把明确操作写成 JSON 数组；不提供操作时计划会保留 `open_questions`，无法误审批：

```json
[
  {"op": "replace_text", "old": "Classifier", "new": "Retrieval", "expected_matches": 1},
  {"op": "set_attribute", "element_id": "module", "attribute": "fill", "value": "#333333"}
]
```

```powershell
python "$FigureSkill\scripts\figure.py" workflow `
  --input .\inputs\existing-figure `
  --brief "将 Classifier 精确替换为 Retrieval" `
  --route edit `
  --edit-operations .\inputs\existing-figure\edit-operations.json `
  --output .\outputs\edit-demo `
  --stop-after-plan
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\plugins\figure-skill\skills\figure-skill\tests -v
```

完整发布验收：

```powershell
.\scripts\verify_release.ps1 -RepairDrawio
```

构建不含密钥、虚拟环境和外部模型仓库的发布包：

```powershell
.\scripts\build_release.ps1
```

发布产物位于 `dist/figure-skill-v0.4.0.zip`，对应 SHA-256 写入同名 `.sha256` 文件。

外部生成服务默认不会执行。需要时先阅读 `plugins/figure-skill/skills/figure-skill/references/external-backends.md`，检查请求清单，再显式授权联网和凭据使用。

团队清单中各候选项目的取舍见 `plugins/figure-skill/skills/figure-skill/references/backend-selection.md`。当前默认选择作者版 PaperBanana；社区版保留为替代方案，托管网站不自动上传材料，失效仓库不作为依赖。

安装官方 draw.io Codex 插件：

```powershell
.\scripts\setup_drawio_plugin.ps1
```

脚本会先检查 Codex 插件市场；若 `openai-bundled` 仍指向旧 AppX 包，会改用当前安装包中的 manifest，然后安装并验证 `drawio@drawio`。没有 draw.io Desktop 时仍可生成原生 `.drawio`；安装桌面版后才能使用本地 ELK 布局以及嵌入 XML 的 PNG/SVG/PDF 导出。

如需准备固定版本的 PaperBanana 与 AutoFigure-Edit 独立运行环境：

```powershell
.\scripts\setup_external_backends.ps1
```

脚本会把固定 commit 的浅克隆和隔离环境放入 `.external/`（已忽略），并执行两个上游 CLI 的 `--help` 冒烟测试；不会读取或写入 API Key。AutoFigure-Edit 的本地 SAM3 仍按上游说明单独安装，也可在实际调用时选 `fal` 或 `roboflow` 后端。

如需丢弃旧外部虚拟环境并严格重建，可执行 `./scripts/setup_external_backends.ps1 -Recreate`；脚本会对两个环境执行 `pip check`，依赖冲突时不会写出成功报告。

准备 PaperBanana 请求时使用它自己的解释器：

```powershell
.\.external\venvs\paperbanana\Scripts\python.exe `
  .\plugins\figure-skill\skills\figure-skill\scripts\adapters\paperbanana_adapter.py `
  .\outputs\demo\figure-plan.json `
  --repo .\.external\upstreams\PaperBanana `
  --output-dir .\outputs\demo\external\paperbanana
```

AutoFigure-Edit 同理使用独立解释器。先不带 `--execute` 审查清单；配置环境变量后，才追加 `--execute --allow-network`：

```powershell
.\.external\venvs\autofigure-edit\Scripts\python.exe `
  .\plugins\figure-skill\skills\figure-skill\scripts\adapters\autofigure_edit_adapter.py `
  .\outputs\demo\figure-plan.json `
  --repo .\.external\upstreams\AutoFigure-Edit `
  --output-dir .\outputs\demo\external\autofigure `
  --provider openai_response --sam-backend fal `
  --input-figure .\inputs\existing.png
```

使用 OpenAI 兼容中转站时配置：

```text
AUTOFIGURE_CUSTOM_BASE_URL=https://your-relay.example/v1
AUTOFIGURE_API_KEY=<secure local value>
AUTOFIGURE_SVG_MODEL=<verified multimodal chat model>
```

运行时选择 `--provider custom`。中转站模型必须支持图片输入、`max_tokens` 以及标准 Chat Completions `choices`；仅能文本对话的模型不能用于 SVG 重建。

完全不使用付费分割服务时，将 `AUTOFIGURE_SAM_BACKEND` 设为 `none`。该模式跳过图标抠取，直接使用多模态模型进行纯 SVG 重建，适合流程图、架构图和文本框图；复杂插画的还原质量会低于 SAM 分割路线。

## 公开验收

2026-08-20 使用 UCI Iris、scikit-learn 官方 Pipeline 和 Wikimedia Commons CC0/公共领域图片完成公开验收。四条确定性路线全部通过；人工神经元纯 SVG 重建通过，复杂神经网络重建为警告；验收过程中修复散点轴选择、散点标题和内嵌位图误报成功三个问题。

详见 `manual-validation/public-acceptance-20260820/ACCEPTANCE_REPORT.md`。

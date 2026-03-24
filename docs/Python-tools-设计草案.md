# PPT Python tools 设计草案

## Purpose

本文档定义 `PPT-assistant-skill` 所依赖的 7 个 `Python tools` 的输入输出契约、前后置条件、退出码语义和错误语义。

目标不是写实现细节，而是先把工具边界固定住，让 `openClaw` 和后续脚本实现围绕同一套契约工作。

## Shared Conventions

### 1. 目录约定

所有工具都在单个 `project workspace` 内工作：

```text
PPT/{project_id}/
├── state.json
├── outline/
├── draft/
├── plan/
├── prompts/
├── assets/
├── deck/
└── exports/
```

### 2. 调用原则

- 所有工具必须显式接收 `project_dir` 或 `project_id + repo_root`
- 所有工具必须只读写本项目目录，不得跨项目写文件
- 所有工具成功后必须产出稳定文件，不得只返回终端文本
- 所有工具失败时必须返回非零 `exit code`

### 3. 状态交互原则

- 工具本身可以读取 `state.json` 做前置校验
- 是否推进 `current_state` 由 `openClaw` 决定
- 工具可以返回建议的 `next_state`，但不应自行决定整个工作流流转

### 4. 统一退出码建议

- `0`: 成功
- `10`: 输入错误 `InputError`
- `20`: 路径或项目错误 `ProjectResolutionError`
- `30`: 状态错误 `StateStoreError`
- `40`: 外部依赖或环境错误 `EnvironmentError`
- `50`: 模型或外部服务调用失败 `UpstreamServiceError`
- `60`: 输出校验失败 `OutputValidationError`

## Shared Schemas

### `outline.json`

```json
{
  "project_id": "03",
  "source_files": [
    {
      "path": "input/course_outline.docx",
      "type": "docx"
    }
  ],
  "title": "课程标题",
  "sections": [
    {
      "id": "sec-1",
      "title": "章节标题",
      "level": 1,
      "content": ["要点1", "要点2"]
    }
  ],
  "metadata": {}
}
```

### `slide_draft.json`

```json
{
  "project_id": "03",
  "slides": [
    {
      "page_id": "p1",
      "source_section": "sec-1",
      "title": "页标题",
      "bullets": ["要点1", "要点2"],
      "quote": "一句金句",
      "speaker_note": "讲述提示",
      "intent": "cover | content | quote | transition | summary"
    }
  ]
}
```

### `plan.json`

```json
{
  "project_id": "03",
  "target_b_ratio": 0.3,
  "actual_b_ratio": 0.29,
  "pages": [
    {
      "page_id": "p1",
      "category": "A",
      "layout_type": "text_logic",
      "prompt_strategy": "info_visual",
      "style_tags": ["business-clean", "minimal", "structured"]
    },
    {
      "page_id": "p2",
      "category": "B",
      "layout_type": "quote_visual",
      "prompt_strategy": "hero_visual",
      "style_tags": ["technology", "wide", "clean"]
    }
  ]
}
```

### `prompts.json`

```json
{
  "project_id": "03",
  "items": [
    {
      "page_id": "p1",
      "category": "A",
      "prompt_strategy": "info_visual",
      "prompt": "A clean business presentation background with strong information hierarchy ...",
      "negative_prompt": "watermark, text, logo, blurry, cluttered composition",
      "aspect_ratio": "16:9",
      "style_tags": ["business-clean", "minimal", "structured"]
    },
    {
      "page_id": "p2",
      "category": "B",
      "prompt_strategy": "hero_visual",
      "prompt": "A cinematic wide background ...",
      "negative_prompt": "watermark, text, logo, blurry",
      "aspect_ratio": "16:9",
      "style_tags": ["technology", "wide", "clean"]
    }
  ]
}
```

## Tool 1: `project_init.py`

### Purpose

初始化 `project workspace` 和最小 `state.json`。

### Inputs

- `project_id`
- `ppt_root`
- 可选：`force_create`
- 可选：`project_name`

### Outputs

- 创建 `PPT/{project_id}/`
- 创建子目录：`outline/`、`draft/`、`plan/`、`prompts/`、`assets/`、`deck/`、`exports/`
- 创建最小 `state.json`

### Preconditions

- `ppt_root` 必须存在
- `project_id` 必须合法且可映射为目录名

### Postconditions

- 项目目录结构完整
- `state.json.current_state` 初始化为 `Initialized` 或空状态

### Stdout

建议输出 JSON：

```json
{
  "project_id": "03",
  "project_dir": "PPT/03",
  "created": true
}
```

### Exit Codes

- `0`: 初始化成功
- `10`: 缺少 `project_id`
- `20`: `ppt_root` 不存在
- `60`: 目录已存在但结构不完整且未启用 `force_create`

### Error Semantics

- 不得覆盖已有项目，除非显式允许
- 不得创建半完成目录后静默成功

## Tool 2: `outline_ingest.py`

### Purpose

解析 `Word/PDF/text` 大纲，生成统一的 `outline.json`。

### Inputs

- `project_dir`
- `source_file` 或 `source_files`
- 可选：`source_type`
- 可选：`language`

### Outputs

- `outline/outline.json`

### Preconditions

- `project_dir` 存在
- 源文件存在且格式受支持

### Postconditions

- `outline.json` 可被后续 `slide_draft_generate.py` 消费
- 原始文件路径记录在 `source_files`

### Validation Rules

- 必须有 `title` 或至少一个 `section`
- `sections` 必须保持顺序
- 不得丢失层级关系

### Stdout

```json
{
  "project_id": "03",
  "artifact": "outline/outline.json",
  "sections_count": 12
}
```

### Exit Codes

- `0`: 成功
- `10`: 输入文件缺失或格式不支持
- `20`: `project_dir` 不存在
- `40`: 缺少解析依赖
- `60`: 解析成功但输出不满足 schema

## Tool 3: `slide_draft_generate.py`

### Purpose

基于 `outline.json` 生成逐页文案稿 `slide_draft.json`。

### Inputs

- `project_dir`
- `outline_path`
- 可选：`deck_style`
- 可选：`target_audience`
- 可选：`max_slides`
- 可选：`revision_instruction`

### Outputs

- `draft/slide_draft.json`

### Preconditions

- `outline.json` 存在且合法

### Postconditions

- 每一页都有稳定 `page_id`
- 页顺序明确
- 生成内容至少包含 `title`、`bullets`
- 视觉候选页应尽量给出 `quote` 或意图标签

### Validation Rules

- 页数不能为 0
- `page_id` 必须唯一
- 不得输出无法映射回源大纲的孤立页

### Stdout

```json
{
  "project_id": "03",
  "artifact": "draft/slide_draft.json",
  "slides_count": 28
}
```

### Exit Codes

- `0`: 成功
- `10`: 缺少必要输入
- `30`: `outline.json` 缺失或损坏
- `50`: LLM（大语言模型）调用失败
- `60`: 输出 schema 校验失败

### Error Semantics

- 生成失败时不得留下伪成功的空 `slide_draft.json`
- 如果是 revision（修订）模式，应保留旧版本，避免直接覆盖不可恢复

## Tool 4: `slide_plan_generate.py`

### Purpose

读取 `slide_draft.json`，输出页面类型规划与提示词策略规划 `plan.json`。

### Inputs

- `project_dir`
- `draft_path`
- 可选：`planning_rules`
- 可选：`visual_style_preset`
- 可选：`revision_instruction`

### Outputs

- `plan/plan.json`

### Preconditions

- `slide_draft.json` 存在且合法

### Postconditions

- 每页都必须有规划记录
- 每页必须归类为 A 或 B
- 每页都必须给出 `prompt_strategy`
- 每页都必须给出 `style_tags`
- 输出必须满足 A/B 比例约束

### Validation Rules

- `plan.pages` 数量必须与 `slides` 数量一致
- `page_id` 必须一一对应
- 不得出现未分类页面
- `actual_b_ratio` 必须落在允许区间内
- 总页数 `<= 4` 时至少 `1` 页 B 类，总页数 `> 4` 时至少 `2` 页 B 类

### Stdout

```json
{
  "project_id": "03",
  "artifact": "plan/plan.json",
  "a_pages": 20,
  "b_pages": 8,
  "actual_b_ratio": 0.29
}
```

### Exit Codes

- `0`: 成功
- `30`: `slide_draft.json` 缺失或损坏
- `50`: 模型分类或规划失败
- `60`: 输出不完整或无法对齐页数

## Tool 5: `visual_prompt_generate.py`

### Purpose

针对全部页面生成文生图提示词，输出 `prompts.json`。A/B 只影响提示词模板，不影响是否生成 prompt。

### Inputs

- `project_dir`
- `draft_path`
- `plan_path`
- 可选：`image_model_profile`
- 可选：`prompt_style_guide`
- 可选：`revision_instruction`

### Outputs

- `prompts/prompts.json`

### Preconditions

- `slide_draft.json` 存在
- `plan.json` 存在

### Postconditions

- 每个页面都有对应 prompt
- prompt 中包含视觉主体、风格、构图和负向约束
- A 类页与 B 类页必须使用不同的 `prompt_strategy`

### Validation Rules

- `items.page_id` 必须覆盖全部页面
- 必须指定 `aspect_ratio=16:9`
- `negative_prompt` 不得为空

### Stdout

```json
{
  "project_id": "03",
  "artifact": "prompts/prompts.json",
  "items_count": 28,
  "a_prompt_count": 20,
  "b_prompt_count": 8
}
```

### Exit Codes

- `0`: 成功
- `30`: `draft` 或 `plan` 缺失
- `50`: Prompt 生成失败
- `60`: 输出与页面全集或策略分布不一致

## Tool 6: `visual_asset_generate.py`

### Purpose

根据 `prompts.json` 生成全部页面所需图片资产。

### Inputs

- `project_dir`
- `prompts_path`
- 可选：`provider`
- 可选：`model`
- 可选：`seed`
- 可选：`overwrite`
- 可选：`target_pages`

### Outputs

- `assets/` 下图片文件
- 可选：`assets/manifest.json`

### Preconditions

- `prompts.json` 存在且合法
- 图像生成服务可访问

### Postconditions

- 每个目标 `page_id` 至少生成一张图
- 文件路径可回溯到 `page_id`
- 默认目标集合为全部页面

### Validation Rules

- 图片分辨率必须适配 `16:9`
- 不得接受明显带水印或错误尺寸的结果
- `manifest` 必须记录 `page_id -> file_path`

### Stdout

```json
{
  "project_id": "03",
  "generated_count": 8,
  "manifest": "assets/manifest.json"
}
```

### Exit Codes

- `0`: 成功
- `30`: `prompts.json` 缺失
- `40`: 缺少依赖或鉴权配置
- `50`: 图像服务调用失败
- `60`: 图片生成完成但校验不通过

### Error Semantics

- 部分页面失败时，不应伪装成全量成功
- 必须明确失败页列表

## Tool 7: `ppt_assemble.py`

### Purpose

读取文案、规划和图片资产，拼装首版或修订版 `deck.pptx`。

### Inputs

- `project_dir`
- `draft_path`
- `plan_path`
- 可选：`assets_manifest_path`
- 可选：`template_path`
- 可选：`theme_name`
- 可选：`revision_instruction`

### Outputs

- `deck/deck.pptx`

### Preconditions

- `slide_draft.json` 存在
- `plan.json` 存在
- 全部页面对应图片资产必须可用

### Postconditions

- 所有页面顺序与 `slide_draft.json` 一致
- 所有页面图片已嵌入
- 前景标题和主要正文保持可编辑
- 文件可被标准 `PPT` 软件打开

### Validation Rules

- 生成页数必须与 `slides` 数量一致
- 不得漏页、乱序或引用缺失图片
- 标题和主要正文不得为空白

### Stdout

```json
{
  "project_id": "03",
  "artifact": "deck/deck.pptx",
  "slides_count": 28
}
```

### Exit Codes

- `0`: 成功
- `30`: 上游产物缺失
- `40`: 模板、字体或运行依赖缺失
- `60`: 装配成功但输出校验失败

## Tool-to-State Mapping

- `project_init.py` -> 初始化项目，不直接对应 6 个主状态
- `outline_ingest.py` -> 产出 `OutlineImported`
- `slide_draft_generate.py` -> 产出 `DraftGenerated`
- `slide_plan_generate.py` -> 产出 `PlanConfirmed`
- `visual_prompt_generate.py` + `visual_asset_generate.py` -> 产出 `AssetsGenerated`
- `ppt_assemble.py` -> 产出 `DeckAssembled`

`FinalApproved` 由 `openClaw` 在用户确认后写入，不由单个工具直接产出。

## openClaw 调用规则

`openClaw` 调用任一工具前，必须先检查：

1. 当前 `project_id` 是否已确认
2. 当前 `state.json` 是否存在
3. 该工具的前置产物是否存在
4. 用户反馈是否要求局部回退

`openClaw` 调用任一工具后，必须：

1. 校验退出码
2. 校验产物文件是否存在
3. 校验产物是否满足最小 schema
4. 再决定是否推进状态

## Non-goals

本文档当前不包含：

- 具体 CLI（命令行）参数格式
- 具体实现库选型
- 具体 `Prompt` 模板内容
- 具体 `PPT` 模板设计
- 多用户并发锁设计

这些属于下一层实现设计，不属于当前契约层。

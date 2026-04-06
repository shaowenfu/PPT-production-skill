# 交互说明
当用户明确提到制作PPT或者使用本SKILL时，开始以下流程。
首先检查项目根目录下的 `.env` 中是否有以下必需的环境变量：
- `GOOGLE_API_KEY`：默认用于文本生成（文案扩写、提示词设计）和图像生成
- `DEEPSEEK_API_KEY`：可选，用于文本生成 fallback
- `OFOX_API_KEY`：可选，用于图像生成 fallback（火山引擎 Doubao）
默认不要连续跑完整条链路。每一步生成或修改中间产物后都先停下来，让用户确认，再进入下一步。

如果用户提供的是 `.docx`，先调用：
`python scripts/docx_to_text.py --input-docx <source.docx>`

然后使用生成的 `.txt` 继续后续流程；脚本会把图片提取到 `PPT/pic/`，并在文本中留下 `[此处有图片]<绝对路径>` 占位。
不要直接读取原始 `.docx` 作为文本源。

# 第0步
仓库的路径在本服务器上的位置为：`(这里由特定机器上的openClaw自己填充)`

# 第一步
调用 project_init.py 进行初始化。
- **参数**：`--project-dir`, `--project-name`
- **默认页数**：除非用户指定，否则规划按 **25页** 规模进行。
- **调用方式**：
`python scripts/project_init.py --project-dir (这里由特定机器上的openClaw自己填充)/PPT/项目名 --project-name "PPT名称"`

# 第二步
提取用户提供的 PPT 内容大纲，写入大纲文件
- **写入位置**：`PPT/<project_id>/outline/outline.md`
- **语言要求**：必须使用**简体中文**。
- **写入规则**：如果原始素材是 `.docx`，先跑 `scripts/docx_to_text.py` 转成 `.txt`，再基于 `.txt` 提取深度大纲；禁止直接读取原始 `.docx` 作为文本源。

# 第三步
生成分页规划（Slide Planning）
- **目标**：默认生成 **25页** 的逻辑分页。
- **写入位置**：`PPT/<project_id>/plan/plan.json`
- **规划逻辑**：细化 A/B 类页面分布，确保重要章节（如"痛点"、"技术重构"、"案例"）占用多页以保证深度。
- **A/B 类定义**：
  - **A 类（信息型视觉页）**：强调结构化信息承载、文字可读性、弱装饰背景、秩序感与清晰层次
  - **B 类（情绪型/金句型视觉页）**：强调视觉冲击、意象、氛围与核心表达，需要更强的背景画面和情绪渲染
- **B 类占比约束**：B 类页占比必须在 **20% - 40%**，禁止全是 A 类或全是 B 类的退化结果

## plan.json 格式参考

```json
{
  "project_id": "项目ID",
  "pages": [
    {
      "page_id": "p1",
      "title": "页面标题",
      "content_hint": "大纲内容片段或要点",
      "content_mode": "generated",
      "source_text": null,
      "category": "A",
      "layout_type": "bullet_list"
    }
  ],
  "target_b_ratio": 0.3,
  "actual_b_ratio": 0.28,
  "metadata": {}
}
```

**字段说明**：
- `page_id`: 页面唯一标识，格式为 p1, p2, p3...
- `title`: 页面标题
- `content_hint`: 大纲内容片段或要点提示
- `content_mode`: 页面内容来源，`"generated"` 表示需要 Draft 扩写，`"locked"` 表示用户已经给出了该页的 PPT 内容
- `source_text`: 当 `content_mode="locked"` 时的用户原始页面信息与文案来源
- `category`: 页面类别，可选值为 `"A"`（信息型）或 `"B"`（情绪型/金句型）
- `layout_type`: 布局类型，如 `bullet_list`, `cover`, `quote`, `transition`, `comparison`, `case_study` 等
- `target_b_ratio`: 目标 B 类页面占比（默认 0.3）
- `actual_b_ratio`: 实际 B 类页面占比

**内容模式约束**：
- `generated` 页面必须提供 `content_hint`，且不得提供 `source_text`
- `locked` 页面必须提供 `source_text`
- 一个项目允许同时混合 `generated` 和 `locked` 页面

# 第四步：深度文案扩写 (Deep Content Generation)
- **目标**：将分页规划中的简略 `content_hint` 扩展为深度业务逻辑（200-400 字）。
- **职能**：专注于内容深度与知识储备，不再关心排版。
- **输出**：写入 `draft/slide_draft.json`。
- **强制约束 (CRITICAL)**：
  - **必须分批执行**：单次处理严禁超过 **5页**（避免 JSON 截断或解析失败）。
  - **严苛 JSON 模式**：输出必须严格对齐 `SlideDraftSlide` 模式（仅包含 `page_id` 和 `content`）。
- **调用示例**：
  ```bash
  # 第一批
  python scripts/slide_draft_generate.py --project-dir PPT/ai_telecom --page-ids p1,p2,p3,p4,p5
  # 第二批
  python scripts/slide_draft_generate.py --project-dir PPT/ai_telecom --page-ids p6,p7,p8,p9,p10
  ```
- **执行要求**：
  - 产出后停下来，让用户先确认 `draft/slide_draft.json`

# 第五步：视觉导演与提示词设计 (Visual Prompt Design)
- **目标**：根据页面内容来源，生成“最终上屏文字”和导演级图像提示词。
- **写入位置**：
  - `PPT/<project_id>/prompts/screen_text.json`
  - `PPT/<project_id>/prompts/prompts.json`
- **强制约束**：
  - **分批处理**：默认 `--batch-size 5`，严禁调大。
  - **严苛 JSON 模式**：模型输出必须同时包含 `page_id`、`text`、`prompt`。
  - **固定内容模式**：若页面 `content_mode="locked"`，则输出的 `text` 和 `prompt` 必须忠实于用户给定页面信息，并整理成正常 PPT 文案；像 `封面：`、`副标题：`、`主讲：` 这类说明性标签默认不直接渲染到页面上，除非用户明确要求。
- **调用示例**：
  ```bash
  python scripts/visual_prompt_design.py --project-dir PPT/ai_telecom --batch-size 5
  python scripts/execute_step.py --step auto --project-dir PPT/ai_telecom
  ```
- **执行要求**：
  - 优先把 `screen_text.json` 发给用户确认，不要默认把完整 `prompts.json` 全量贴到对话里
  - 如果用户修改了 `screen_text.json`，进入第六步前必须同步更新 `prompts.json` 中对应的中文引号文本

# 第六步 & 第七步
批量生成图片并封装 PPTX
- **工具**：`scripts/visual_asset_generate.py` 和 `scripts/ppt_assemble.py`
- **模型配置**：
  - 默认文本生成：Google Gemini (`gemini-3-flash-preview`)
  - 默认图像生成：Google Gemini Image (`gemini-3.1-flash-image-preview`)
  - fallback：DeepSeek / Doubao
- **调用示例**：
  ```bash
  # 生成图片
  python scripts/visual_asset_generate.py --project-dir PPT/03

  # 封装 PPTX
  python scripts/ppt_assemble.py --project-dir PPT/03
  ```
- **执行要求**：
  - 第六步产图后先让用户确认图片，再进入第七步

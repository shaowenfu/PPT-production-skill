# 交互说明
当用户明确提到制作PPT或者使用本SKILL时，开始以下流程。
首先检查项目根目录下的 `.env` 中是否有以下必需的环境变量：
- `GOOGLE_API_KEY`：默认用于文本生成（文案扩写、提示词设计）和图像生成
- `DEEPSEEK_API_KEY`：可选，用于文本生成 fallback
- `OFOX_API_KEY`：可选，用于图像生成 fallback（火山引擎 Doubao）
默认自动执行前五步，第五步执行完毕后停下来询问用户是否继续。

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
- **写入规则**：直接利用自身的文档读取能力，从原始素材中提取深度大纲。

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
- `category`: 页面类别，可选值为 `"A"`（信息型）或 `"B"`（情绪型/金句型）
- `layout_type`: 布局类型，如 `bullet_list`, `cover`, `quote`, `transition`, `comparison`, `case_study` 等
- `target_b_ratio`: 目标 B 类页面占比（默认 0.3）
- `actual_b_ratio`: 实际 B 类页面占比

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

# 第五步：视觉导演与提示词设计 (Visual Prompt Design)
- **目标**：从深度稿（Draft）中蒸馏文案，并运用《非设计师设计指南》的对比原则，为图像模型生成导演级提示词。
- **写入位置**：`PPT/<project_id>/prompts/prompts.json`
- **强制约束**：
  - **分批处理**：默认 `--batch-size 5`，严禁调大。
  - **严苛 JSON 模式**：输出必须严格对齐 `PromptItem` 模式。
- **调用示例**：
  ```bash
  python scripts/visual_prompt_design.py --project-dir PPT/ai_telecom --batch-size 5
  ```

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

# 交互说明
当用户明确提到制作PPT或者使用本SKILL时，开始以下流程。

# 第0步
仓库的路径在本服务器上的位置为：`(这里由特定机器上的openClaw自己填充)`

# 第一步
调用 project_init.py 进行初始化。
- **参数**：`--project-dir`, `--project-name`
- **默认页数**：除非用户指定，否则规划按 **25页** 规模进行。
- **调用方式**：
`python3 scripts/project_init.py --project-dir (这里由特定机器上的openClaw自己填充)/PPT/项目名 --project-name "PPT名称"`

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

# 第四步
生成 PPT 逐页文案稿（Slide Draft Generation）
- **目标**：为每页 PPT 生成文案，且严格区分"画面极简文字"与"演讲背景知识"。
- **核心要求**：
    1. **文字分离**：`slide_text` 仅存放直接在PPT上展示的最终版本画面文本（短词、短语、大标题、数据、句子等）。所有的深度逻辑、行业数据、复杂长句必须存入 `speaker_note`（演讲备注）。
    2. **分批调用**：每批 5 页，确保 Agent 有足够的 Context 空间来发挥深度。
- **语言**：简体中文。
- **参数**：`--model` 可选值为 `gemini`（默认）或 `deepseek`。
- **环境变量**：
  - `gemini`: 需设置 `GEMINI_API_KEY`
  - `deepseek`: 需设置 `DEEPSEEK_API_KEY`
- **调用示例**：
  ```bash
  # 使用 Gemini（默认）
  python scripts/slide_draft_generate.py --project-dir PPT/03 --page-ids p1,p2,p3,p4,p5 --model gemini

  # 使用 DeepSeek
  python scripts/slide_draft_generate.py --project-dir PPT/03 --page-ids p1,p2,p3,p4,p5 --model deepseek
  ```

# 第五步
深度视觉设计提示词（Detailed Visual Prompt Design）
- **目标**：将第四步的**画面文案**与视觉指令完美融合，生成可直接输入给图像模型的 Prompt。
- **写入位置**：`PPT/<project_id>/prompts/prompts.json`

## 数据来源
从 `draft/slide_draft.json` 中提取每个 slide 的：
- `metadata.visual_style`：英文视觉风格描述（背景、色调、元素、氛围）
- `slide_text`：中文画面文字内容（短语、标签、数字）
- `title`：页面标题
- `quote`：金句（如有）

## 提示词法则（极为关键，防止中文乱码）

### 三段式结构
```
[Visual Style Description] + [Text to render exactly] + [Font & Layout Instructions]
```

1. **第一段：背景风格说明（英文）**
   - 直接使用 `visual_style` 字段内容
   - 包含：背景描述、色调(Color palette)、视觉元素(Visual elements)、氛围(Atmosphere)

2. **第二段：精准文本控制（中文）**
   - 格式：`Text to render exactly: - Label: "内容" - Label: "内容"`
   - 必须用双引号包裹中文文本
   - 示例：`Text to render exactly: Title: "趋势洞察", Subtitle: "AI时代通信运营新机遇"，text:"AI时当前通信行业线上运营陷入"高投入低转化"的困境：获客成本持续攀升，用户活跃度不断下滑，传统运营手段日渐失效。随着AI技术成熟，智能运营已成为破局关键，但多数企业缺乏落地方法，错失增长机遇。"

3. **第三段：字体与布局（英文）**
   - 指定字体风格、颜色、对齐方式
   - 示例：`Font style: bold sans-serif white text, main title centered large, subtitle below in smaller size.`

## 输出格式（prompts.json）

```json
{
  "project_id": "项目ID",
  "items": [
    {
      "page_id": "p1",
      "prompt": "[visual_style内容] Text to render exactly: Title: \"[title]\", Bullets: \"[slide_text[0]]\", \"[slide_text[1]]\". Font style: [字体布局说明]",
      "negative_prompt": "blurry, low quality, distorted text, watermark, signature",
      "aspect_ratio": "16:9",
      "style_tags": ["从plan继承"]
    }
  ]
}
```

## 批量处理建议
- 一次性生成所有 25 页的 prompts.json
- 确保 page_id 顺序与 plan.json 一致
- 每个 prompt 必须包含完整的 visual_style + text + font 三段
- 每个提示词末尾都统一加上禁止加上“AI生成”之类的水印。

# 第六步 & 第七步
批量生成图片并封装 PPTX
- **工具**：`scripts/visual_asset_generate.py` 和 `scripts/ppt_assemble.py`。
- **参数**：`--model` 可选值为 `gemini`（默认）或 `doubao`。
- **环境变量**：
  - `gemini`: 需设置 `GOOGLE_API_KEY`
  - `doubao`: 需设置 `OFOX_API_KEY`
- **调用示例**：
  ```bash
  # 使用 Gemini（默认）
  python scripts/visual_asset_generate.py --project-dir PPT/03 --model gemini

  # 使用火山引擎豆包
  python scripts/visual_asset_generate.py --project-dir PPT/03 --model doubao
  ```
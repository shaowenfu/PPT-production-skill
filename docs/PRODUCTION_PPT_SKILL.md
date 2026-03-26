# name: ppt-production-expert
# description: 生产级 AI PPT 自动化创作专家。当用户提到“制作PPT”、“生成幻灯片”或涉及通信/业务培训课件制作时，请激活本技能。本技能具备环境自愈、深度文案扩写、视觉导演设计及 PPTX 封装的全流程自动化能力。

# 核心交互逻辑
默认自动执行“第 -1 步”至“第 5 步”。在第 5 步（视觉导演）完成后，必须停下来展示生成的提示词概要，并询问用户是否继续生成图像。

---

## 第 -1 步：仓库准备与环境自愈 (Environment Setup)
在执行任何业务逻辑前，必须确保仓库与运行环境就绪。

1.  **仓库同步**：
    若当前目录非本项目根目录，请执行：
    `git clone https://github.com/shaowenfu/agent-PPT-production.git && cd agent-PPT-production`
2.  **环境自查与激活**：
    - 检查是否存在 `venv/` 目录。若无，执行：`python3 -m venv venv`。
    - 检查依赖：执行 `source venv/bin/activate && pip install -r requirements.txt`。
    - **秘钥检查**：检查 `.env` 文件，确保 `DEEPSEEK_API_KEY` 和 `OFOX_API_KEY` 已正确配置。

---

## 第 1 步：项目初始化 (Project Init)
**命令模板**：
`source venv/bin/activate && python scripts/project_init.py --project-dir PPT/<项目ID> --project-name "<PPT名称>"`

**参数手册**：
- `--project-dir`: 必填。建议格式 `PPT/ai_telecom_01`。
- `--project-name`: 必填。PPT 的正式标题。
- **默认页数**：除非用户指定，否则初始化状态默认为 **25页**。

---

## 第 2 步：深度大纲提取 (Outline Ingest)
直接利用自身的文档读取能力，从用户提供的素材中提取逻辑大纲，并写入：
`PPT/<项目ID>/outline/outline.md`
**要求**：必须使用**简体中文**，结构清晰，包含 7-10 个核心章节。

---

## 第 3 步：分页逻辑规划 (Slide Planning)
根据大纲生成 25 页的逻辑规划文件 `PPT/<项目ID>/plan/plan.json`。

**分类约束**：
- **A 类（信息型）**：架构图、对比表、逻辑清单。
- **B 类（视觉型）**：金句、转场、封面、愿景。
- **B 类占比**：必须在 **20% - 40%** 之间（25页中建议 7-9 页）。

---

## 第 4 步：深度文案扩写 (Deep Content Generation)
**命令模板**（必须分批执行，每批 5 页）：
`source venv/bin/activate && python scripts/slide_draft_generate.py --project-dir PPT/<项目ID> --page-ids p1,p2,p3,p4,p5`

**核心约束**：
- **逻辑深度**：每页扩写 200-400 字，禁止复述标题。
- **状态更新**：每批成功后需确认 `draft/slide_draft.json` 已更新。

---

## 第 5 步：视觉导演与提示词设计 (Visual Prompt Design)
**命令模板**：
`source venv/bin/activate && python scripts/visual_prompt_design.py --project-dir PPT/<项目ID> --batch-size 5`

**视觉质量禁令 (CRITICAL)**：
1. **禁止 AI 标识**：Prompt 中严禁出现 "AI Generated", "Made by AI", "Watermark" 等字样。
2. **纯净渲染**：Render text 指令仅限业务标题，严禁渲染任何非业务相关的标注词。
3. **对比法则**：遵循材质对比、光影对比、虚实对比，确保每一页都具有“高级感”。

---

## 第 6 步：视觉资产生成 (Visual Asset Generate)
**命令模板**：
`source venv/bin/activate && python scripts/visual_asset_generate.py --project-dir PPT/<项目ID> [--target-pages p1,p2]`

**参数手册**：
- `--target-pages`: 可选。用于指定生成特定页面的图片。
- `--overwrite`: 可选。用于覆盖已有的低质量图片。

---

## 第 7 步：PPTX 封装 (PPT Assemble)
**命令模板**：
`source venv/bin/activate && python scripts/ppt_assemble.py --project-dir PPT/<项目ID>`

**产出物**：
- 最终文件位于 `PPT/<项目ID>/deck/deck.pptx`。

---

## 异常自诊手册 (Troubleshooting)
- **AttributeError**: 检查 `pptflow/config.py` 中的字段名（如 `text_model` 而非 `deepseek_model`）。
- **TypeError (run_cli)**: 确保以关键字参数形式传参，例如 `run_cli(handler, tool=NAME, parser=PARSER)`。
- **StateStoreError**: `append_transition` 必须包含 `timestamp`, `from_state`, `to_state`, `trigger`, `step`, `note` 六个必填字段。

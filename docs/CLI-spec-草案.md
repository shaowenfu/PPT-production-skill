# PPT Python tools CLI spec

## Purpose
本文档定义 PPT 工具链中 4 个原子化 Python 脚本的统一命令行接口规范。
核心理念：Agent 负责“脑力”（大纲、规划、导演、提示词），脚本负责“体力”（批处理、API 搬运、封装）。

## 核心脚本清单
1. `project_init.py`：项目初始化与状态机建立。
2. `slide_draft_generate.py`：批量知识稿生成（分批调用 LLM）。
3. `visual_asset_generate.py`：阿里云百炼图像生成集成。
4. `ppt_assemble.py`：图像即页面（Image-as-Slide）封装。

## 通用参数与契约
- `--project-dir`: 项目根目录（如 `PPT/项目名`）。
- `--output-json`: 强制 `stdout` 输出 JSON 摘要。
- `--overwrite`: 允许覆盖已有产物。
- **退出码**：
  - `0`: 成功
  - `10`: `InputError` (参数或文件缺失)
  - `30`: `StateStoreError` (状态校验失败)
  - `50`: `UpstreamServiceError` (阿里云/OpenAI API 错误)

## 脚本详情

### 1. `project_init.py`
- **功能**：创建标准目录树及 `state.json`。
- **调用**：`python3 scripts/project_init.py --project-dir <path> --project-name <name>`

### 2. `slide_draft_generate.py`
- **功能**：根据大纲批量生成深度的知识全集。
- **调用**：`python3 scripts/slide_draft_generate.py --project-dir <path> --page-ids p1,p2,p3`
- **注意**：支持分页生成，防止上下文截断。

### 3. `visual_asset_generate.py`
- **功能**：集成阿里云百炼 `qwen-image-2.0-pro` 模型。
- **调用**：`python3 scripts/visual_asset_generate.py --project-dir <path> [--target-pages p1,p5]`
- **特性**：自动处理 16:9 分辨率、提示词扩展及图片下载。

### 4. `ppt_assemble.py`
- **功能**：将 `assets/*.png` 作为全屏背景插入 PPTX。
- **调用**：`python3 scripts/ppt_assemble.py --project-dir <path>`
- **特性**：不再渲染文本框，实现“所见即所得”的视觉交付。
